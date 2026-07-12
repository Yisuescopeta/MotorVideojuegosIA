from __future__ import annotations

import copy
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

from engine.authoring.changes import Change
from engine.components.recttransform import RectTransform
from engine.components.transform import Transform
from engine.core.runtime_logging import log_err
from engine.scenes.change_history import SceneChangeCoordinator, SceneChangeCoordinatorContext
from engine.scenes.contracts import (
    SceneAuthoringPort,
    SceneManagerAuthoringAdapter,
    SceneManagerRuntimeAdapter,
    SceneManagerWorkspaceAdapter,
    SceneRuntimePort,
    SceneWorkspacePort,
)
from engine.scenes.scene import Scene
from engine.scenes.scene_persistence import (
    COMPACT_SCENE_SAVE_ENTITY_THRESHOLD as _COMPACT_SCENE_SAVE_ENTITY_THRESHOLD,
)
from engine.scenes.scene_persistence import (
    COMPACT_SCENE_SAVE_SEPARATORS as _COMPACT_SCENE_SAVE_SEPARATORS,
)
from engine.scenes.scene_persistence import (
    ScenePersistenceService,
    SceneStorageReadError,
)
from engine.scenes.storage import SceneStorage
from engine.scenes.structural_authoring import SceneStructuralAuthoring, SceneStructuralAuthoringContext
from engine.scenes.workspace_lifecycle import SceneWorkspace, SceneWorkspaceEntry
from engine.serialization.json_value import clone_json_value
from engine.serialization.schema import build_canonical_scene_payload, migrate_scene_data, validate_scene_data

if TYPE_CHECKING:
    from engine.ecs.world import World
    from engine.levels.component_registry import ComponentRegistry

LEGACY_AUTHORING_SYNC_REASON = "legacy_authoring"
TRANSIENT_PREVIEW_SYNC_REASON = "transient_preview"
COMPACT_SCENE_SAVE_ENTITY_THRESHOLD = _COMPACT_SCENE_SAVE_ENTITY_THRESHOLD
COMPACT_SCENE_SAVE_SEPARATORS = _COMPACT_SCENE_SAVE_SEPARATORS


@dataclass
class AuthoringComponentDelta:
    entity_name: str
    component_name: str
    old_properties: Dict[str, Any] = field(default_factory=dict)
    new_properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AuthoringTransactionState:
    label: str
    key: str
    changes: Dict[tuple[str, str], AuthoringComponentDelta] = field(default_factory=dict)


@dataclass(frozen=True)
class _SerializableMutationSnapshot:
    scene_data: Dict[str, Any]
    selected_entity_name: Optional[str]
    selected_entity_id: Optional[str]
    dirty: bool
    pending_edit_world_sync_reason: Optional[str]


class SceneManager:
    def __init__(self, registry: "ComponentRegistry") -> None:
        self._registry = registry
        self._workspace = SceneWorkspace(
            validate_scene_payload=self._validated_scene_payload,
            build_scene_key=self._build_scene_key,
            create_untitled_key=self._create_untitled_scene_key,
            rebuild_edit_world=self._rebuild_edit_world,
            sync_scene_links_from_feature_metadata=self._sync_scene_links_from_feature_metadata,
            entry_has_invalid_links=self._entry_has_invalid_links,
        )
        self._persistence = ScenePersistenceService()
        self._untitled_counter: int = 1
        self._change_history = SceneChangeCoordinator(
            SceneChangeCoordinatorContext(
                resolve_entry=self._resolve_entry,
                restore_entry_scene=self._restore_entry_scene,
                snapshot_scene=lambda entry: copy.deepcopy(entry.scene.to_dict()),
                edit_component=self.apply_edit_to_world,
                set_entity_property=self.update_entity_property,
                add_component=lambda entity, component, data: self.add_component_to_entity(entity, component, component_data=data),
                remove_component=self.remove_component_from_entity,
                create_entity=self.create_entity,
                delete_entity=self.remove_entity,
            )
        )
        self._structural_authoring = SceneStructuralAuthoring(
            SceneStructuralAuthoringContext(
                get_active_entry=self._get_active_entry,
                resolve_entry=self._resolve_entry,
                flush_pending_edit_world=self._flush_pending_edit_world,
                rebuild_edit_world=self._rebuild_edit_world,
                record_scene_change=self._record_scene_change,
                sync_scene_links_from_feature_metadata=self._sync_feature_metadata_from_scene_links,
                create_entity=self.create_entity,
                create_entity_from_data=self.create_entity_from_data,
                update_entity_property=self.update_entity_property,
                unique_entity_name=self._unique_entity_name,
            )
        )
        self._runtime_port: SceneRuntimePort = SceneManagerRuntimeAdapter(self)
        self._authoring_port: SceneAuthoringPort = SceneManagerAuthoringAdapter(self)
        self._workspace_port: SceneWorkspacePort = SceneManagerWorkspaceAdapter(self)
        self._runtime_signal_compiler: Optional[Callable[[Scene, "World"], int]] = None
        self._authoring_transaction: AuthoringTransactionState | None = None
        self._on_scene_saved_callbacks: list[Callable[[str, Dict[str, Any]], None]] = []
        self._scene_file_mtimes: dict[str, float] = {}

    @property
    def _entries(self) -> dict[str, SceneWorkspaceEntry]:
        return self._workspace.entries

    @property
    def _active_scene_key(self) -> str:
        return self._workspace.active_scene_key

    @_active_scene_key.setter
    def _active_scene_key(self, value: str) -> None:
        self._workspace.active_scene_key = value

    @property
    def current_scene(self) -> Optional[Scene]:
        entry = self._get_active_entry()
        return entry.scene if entry is not None else None

    @property
    def runtime_port(self) -> SceneRuntimePort:
        return self._runtime_port

    @property
    def authoring_port(self) -> SceneAuthoringPort:
        return self._authoring_port

    @property
    def workspace_port(self) -> SceneWorkspacePort:
        return self._workspace_port

    @property
    def scene_name(self) -> str:
        scene = self.current_scene
        return scene.name if scene is not None else "Sin escena"

    @property
    def is_playing(self) -> bool:
        entry = self._get_active_entry()
        return bool(entry.is_playing) if entry is not None else False

    @property
    def is_dirty(self) -> bool:
        entry = self._get_active_entry()
        return bool(entry.dirty) if entry is not None else False

    @property
    def has_unsaved_scenes(self) -> bool:
        return any(entry.dirty for entry in self._workspace.entries.values())

    @property
    def active_world(self) -> Optional["World"]:
        entry = self._get_active_entry()
        return entry.active_world if entry is not None else None

    @property
    def active_scene_key(self) -> str:
        return self._workspace.active_scene_key

    def set_history_manager(self, history: Any) -> None:
        self._change_history.set_history_manager(history)

    def set_runtime_signal_compiler(
        self,
        compiler: Optional[Callable[[Scene, "World"], int]],
    ) -> None:
        self._runtime_signal_compiler = compiler

    def register_on_scene_saved(self, callback: Callable[[str, Dict[str, Any]], None]) -> None:
        """Register a callback invoked after each successful save_scene_to_file.

        Callback signature: callback(path: str, info: dict) -> None.
        Info dict keys: 'key', 'scene_name', 'entity_count'.
        Callback exceptions are logged and never make the save fail.
        """
        if callback not in self._on_scene_saved_callbacks:
            self._on_scene_saved_callbacks.append(callback)

    def unregister_on_scene_saved(self, callback: Callable[[str, Dict[str, Any]], None]) -> None:
        """Remove a previously registered on_scene_saved callback."""
        try:
            self._on_scene_saved_callbacks.remove(callback)
        except ValueError:
            pass

    def _fire_on_scene_saved(self, path: str, key: str, scene_name: str, entity_count: int) -> None:
        info: Dict[str, Any] = {"key": key, "scene_name": scene_name, "entity_count": entity_count}
        for callback in self._on_scene_saved_callbacks:
            try:
                callback(path, info)
            except Exception as exc:
                log_err(f"SceneManager: on_scene_saved callback raised {type(exc).__name__}: {exc}")

    def refresh_active_scene_if_stale(self) -> Optional["World"]:
        """Reload active scene from disk if file mtime changed and scene is not dirty.

        Safe guard: if the scene has unsaved authoring changes (dirty=True),
        the refresh is skipped to avoid silently discarding them. Returns the
        edit_world (refreshed or existing) or None if no active entry.
        """
        entry = self._get_active_entry()
        if entry is None:
            return None
        raw_source = entry.source_path
        if not raw_source:
            return entry.edit_world
        if entry.dirty:
            return entry.edit_world
        resolved_source = str(Path(raw_source).resolve())
        try:
            current_mtime = self._persistence.get_mtime(resolved_source)
        except OSError:
            return entry.edit_world
        if current_mtime is None:
            return entry.edit_world
        previous_mtime = self._scene_file_mtimes.get(resolved_source)
        if previous_mtime is not None and current_mtime <= previous_mtime:
            return entry.edit_world
        try:
            loaded = self._persistence.load(resolved_source)
        except Exception as exc:
            log_err(f"SceneManager: failed to reload stale scene from {resolved_source}: {exc}")
            return entry.edit_world
        try:
            self._install_scene_payload(entry, loaded.payload, source_path=resolved_source)
            entry.dirty = False
            self._scene_file_mtimes[resolved_source] = current_mtime
        except Exception as exc:
            log_err(f"SceneManager: failed to install refreshed scene payload from {resolved_source}: {exc}")
        return entry.edit_world

    def list_open_scenes(self) -> list[Dict[str, Any]]:
        return self._workspace.list_open_scenes()

    def get_feature_metadata(self) -> Dict[str, Any]:
        entry = self._get_active_entry()
        if entry is None:
            return {}
        return copy.deepcopy(entry.scene.feature_metadata)

    def get_active_scene_summary(self) -> Dict[str, Any]:
        entry = self._get_active_entry()
        if entry is None:
            return {}
        return {
            "key": entry.key,
            "name": entry.scene.name,
            "path": entry.scene.source_path or "",
            "dirty": bool(entry.dirty),
        }

    def get_component_data(self, entity_name: str, component_name: str) -> Optional[Dict[str, Any]]:
        entry = self._get_active_entry()
        if entry is None:
            return None
        self._flush_pending_edit_world(entry, failure_context=f"read_component:{entity_name}.{component_name}")
        entity_data = entry.scene.find_entity(entity_name)
        if entity_data is None:
            return None
        component_data = entity_data.get("components", {}).get(component_name)
        if not isinstance(component_data, dict):
            return None
        return copy.deepcopy(component_data)

    def ensure_scene_open(self, scene_ref: str, activate: bool = False) -> Optional[SceneWorkspaceEntry]:
        normalized_ref = str(scene_ref or "").strip()
        if not normalized_ref:
            return self._get_active_entry()
        entry = self._resolve_entry(normalized_ref)
        if entry is None and normalized_ref.endswith(".json"):
            self.load_scene_from_file(normalized_ref, activate=activate)
            entry = self._resolve_entry(normalized_ref)
        elif activate and entry is not None:
            self.activate_scene(normalized_ref)
        return entry

    def find_entity_data_for_scene(self, scene_ref: str | None, entity_name: str) -> Optional[Dict[str, Any]]:
        entry = self.ensure_scene_open(str(scene_ref or ""), activate=False) if scene_ref not in (None, "") else self._get_active_entry()
        if entry is None:
            return None
        entity_data = entry.scene.find_entity(entity_name)
        return copy.deepcopy(entity_data) if isinstance(entity_data, dict) else None

    def get_component_data_for_scene(
        self,
        scene_ref: str | None,
        entity_name: str,
        component_name: str,
    ) -> Optional[Dict[str, Any]]:
        entity_data = self.find_entity_data_for_scene(scene_ref, entity_name)
        if entity_data is None:
            return None
        components = entity_data.get("components", {})
        if not isinstance(components, dict):
            return None
        component_data = components.get(component_name)
        return copy.deepcopy(component_data) if isinstance(component_data, dict) else None

    def list_scene_entities(self, scene_ref: str | None = None) -> list[Dict[str, Any]]:
        entry = self.ensure_scene_open(str(scene_ref or ""), activate=False) if scene_ref not in (None, "") else self._get_active_entry()
        if entry is None:
            return []
        entities: list[Dict[str, Any]] = []
        for entity_data in entry.scene.entities_data:
            if not isinstance(entity_data, dict):
                continue
            components = entity_data.get("components", {})
            component_names = sorted(components.keys()) if isinstance(components, dict) else []
            entities.append(
                {
                    "name": str(entity_data.get("name", "") or ""),
                    "scene_name": entry.scene.name,
                    "scene_path": entry.source_path,
                    "scene_key": entry.key,
                    "scene_ref": entry.source_path or entry.key,
                    "has_scene_link": "SceneLink" in component_names,
                    "component_names": component_names,
                }
            )
        return entities

    def upsert_component_for_scene(
        self,
        scene_ref: str,
        entity_name: str,
        component_name: str,
        component_data: Dict[str, Any],
        *,
        record_history: bool = True,
    ) -> bool:
        entry = self.ensure_scene_open(scene_ref, activate=False)
        if entry is None or entry.is_playing:
            return False
        if entry.key == self._active_scene_key and not self._flush_pending_edit_world(
            entry,
            failure_context=f"upsert_component:{entity_name}.{component_name}",
        ):
            return False
        if entry.scene.find_entity(entity_name) is None:
            return False
        snapshot = self._capture_serializable_mutation(entry)
        before = snapshot.scene_data
        normalized_payload = self._canonicalize_component_payload(component_name, component_data)
        if not entry.scene.replace_component_data(entity_name, component_name, normalized_payload):
            if not entry.scene.add_component(entity_name, component_name, normalized_payload):
                return False
            entry.scene.set_component_metadata(
                entity_name,
                component_name,
                {"origin": self._registry.get_origin(component_name)},
            )
        if component_name == "SceneLink":
            self._sync_feature_metadata_from_scene_links(entry)
        if not self._commit_serializable_scene_mutation(
            entry,
            snapshot,
            failure_context=f"upsert_component:{entity_name}.{component_name}",
        ):
            return False
        entry.dirty = True
        if record_history and entry.key == self._active_scene_key:
            self._record_scene_change(entry, f"{entity_name}.{component_name}", before)
        return True

    def remove_component_for_scene(
        self,
        scene_ref: str,
        entity_name: str,
        component_name: str,
        *,
        record_history: bool = True,
    ) -> bool:
        entry = self.ensure_scene_open(scene_ref, activate=False)
        if entry is None or entry.is_playing:
            return False
        if entry.key == self._active_scene_key and not self._flush_pending_edit_world(
            entry,
            failure_context=f"remove_component:{entity_name}.{component_name}",
        ):
            return False
        if entry.scene.find_entity(entity_name) is None:
            return False
        current = self.get_component_data_for_scene(scene_ref, entity_name, component_name)
        if current is None:
            return False
        snapshot = self._capture_serializable_mutation(entry)
        before = snapshot.scene_data
        if not entry.scene.remove_component(entity_name, component_name):
            return False
        if component_name == "SceneLink":
            self._sync_feature_metadata_from_scene_links(entry)
        if not self._commit_serializable_scene_mutation(
            entry,
            snapshot,
            failure_context=f"remove_component:{entity_name}.{component_name}",
        ):
            return False
        entry.dirty = True
        if record_history and entry.key == self._active_scene_key:
            self._record_scene_change(entry, f"remove_component:{entity_name}.{component_name}", before)
        return True

    def get_scene_view_state(self, key: Optional[str] = None) -> Dict[str, Any]:
        return self._workspace.get_scene_view_state(key)

    def set_scene_view_state(self, key: str, view_state: Dict[str, Any]) -> bool:
        return self._workspace.set_scene_view_state(key, view_state)

    def get_workspace_state(self) -> Dict[str, Any]:
        return self._workspace.get_workspace_state()

    def activate_scene(self, key_or_path: str) -> Optional["World"]:
        return self._workspace.activate_scene(key_or_path)

    def close_scene(self, key_or_path: str, discard_changes: bool = False) -> bool:
        return self._workspace.close_scene(key_or_path, discard_changes=discard_changes)

    def reset_workspace(self) -> None:
        self._workspace.reset_workspace()
        self._structural_authoring.reset_state()

    def load_scene(self, data: Dict[str, Any], source_path: Optional[str] = None, activate: bool = True) -> "World":
        world = self._workspace.load_scene(data, source_path=source_path, activate=activate)
        if world is not None and source_path:
            try:
                resolved_path = str(Path(source_path).resolve())
                mtime = self._persistence.get_mtime(resolved_path)
                if mtime is not None:
                    self._scene_file_mtimes[resolved_path] = mtime
            except OSError:
                pass
        return world

    def load_scene_from_file(
        self,
        path: str,
        activate: bool = True,
        storage: Optional[SceneStorage] = None,
    ) -> Optional["World"]:
        resolved_path = self._persistence.resolve_path(path)
        workspace_path = resolved_path.as_posix()
        existing = self._workspace.resolve_entry(workspace_path)
        if existing is not None:
            if activate:
                self._workspace.active_scene_key = existing.key
            world = existing.edit_world
            try:
                mtime = self._persistence.get_mtime(resolved_path)
                if mtime is not None:
                    self._scene_file_mtimes[str(resolved_path)] = mtime
            except OSError:
                pass
            return world
        try:
            loaded = self._persistence.load(resolved_path, storage=storage)
        except SceneStorageReadError as exc:
            log_err(f"SceneManager: Error cargando {workspace_path}: {exc}")
            return None
        world = self._workspace.load_scene(
            loaded.payload,
            source_path=workspace_path,
            activate=activate,
        )
        if world is not None and loaded.mtime is not None:
            self._scene_file_mtimes[str(resolved_path)] = loaded.mtime
        return world

    def get_edit_world(self) -> Optional["World"]:
        self.refresh_active_scene_if_stale()
        entry = self._get_active_entry()
        return entry.edit_world if entry is not None else None

    def create_new_scene(self, name: str = "New Scene", activate: bool = True) -> "World":
        return self._workspace.create_new_scene(name, activate=activate)

    def enter_play(self) -> Optional["World"]:
        runtime_world = self._workspace.enter_play()
        entry = self._get_active_entry()
        if runtime_world is None or entry is None:
            return runtime_world
        self._compile_runtime_signals_for_entry(entry, runtime_world)
        return runtime_world

    def exit_play(self) -> Optional["World"]:
        return self._workspace.exit_play()

    def restore_world(self, world: "World") -> None:
        self._workspace.restore_world(world)

    def reload_scene(self) -> Optional["World"]:
        return self._workspace.reload_scene()

    def apply_edit_to_world(self, entity_name: str, component_name: str, property_name: str, value: Any) -> bool:
        entry = self._get_active_entry()
        if entry is None or entry.is_playing or entry.edit_world is None:
            return False
        if component_name == "Transform" and property_name in ("x", "y", "rotation", "scale_x", "scale_y"):
            return self.apply_transform_state(
                entity_name,
                {property_name: value},
                entry.key,
                record_history=True,
                label=f"{entity_name}.{component_name}.{property_name}",
            )
        if component_name == "RectTransform" and property_name in (
            "anchored_x",
            "anchored_y",
            "width",
            "height",
            "rotation",
            "scale_x",
            "scale_y",
        ):
            return self.apply_rect_transform_state(
                entity_name,
                {property_name: value},
                entry.key,
                record_history=True,
                label=f"{entity_name}.{component_name}.{property_name}",
            )
        if not self._flush_pending_edit_world(entry, failure_context=f"{entity_name}.{component_name}.{property_name}"):
            return False
        snapshot = self._capture_serializable_mutation(entry)
        before = snapshot.scene_data
        if not entry.scene.update_component(entity_name, component_name, property_name, value):
            if not self._structural_authoring.update_prefab_component_override(entry, entity_name, component_name, property_name, value):
                return False
        if component_name == "SceneLink":
            self._sync_feature_metadata_from_scene_links(entry)
        if not self._commit_serializable_scene_mutation(
            entry,
            snapshot,
            failure_context=f"{entity_name}.{component_name}.{property_name}",
        ):
            return False
        entry.dirty = True
        self._record_scene_change(entry, f"{entity_name}.{component_name}.{property_name}", before)
        return True

    def update_entity_property(self, entity_name: str, property_name: str, value: Any) -> bool:
        entry = self._get_active_entry()
        if entry is None or entry.is_playing:
            return False
        entity_id = self._entity_id_for_name(entry, entity_name)
        if property_name == "parent" and value is not None and not self._structural_authoring.validate_parent(entry, entity_name, value):
            return False
        if not self._flush_pending_edit_world(entry, failure_context=f"{entity_name}.{property_name}"):
            return False
        snapshot = self._capture_serializable_mutation(entry)
        before = snapshot.scene_data
        if not entry.scene.update_entity_property(entity_name, property_name, value):
            if not self._structural_authoring.update_prefab_entity_override(entry, entity_name, property_name, value):
                return False
        if property_name == "name" and isinstance(value, str):
            selected_matches = (
                (entity_id is not None and entry.selected_entity_id == entity_id)
                or (entry.selected_entity_id is None and entry.selected_entity_name == entity_name)
            )
            if selected_matches:
                entry.selected_entity_name = value
                entry.selected_entity_id = entity_id
            if entry.edit_world is not None and entry.edit_world.selected_entity_name == entity_name:
                entry.edit_world.selected_entity_name = value
        if not self._commit_serializable_scene_mutation(
            entry,
            snapshot,
            failure_context=f"{entity_name}.{property_name}",
        ):
            return False
        entry.dirty = True
        self._record_scene_change(entry, f"{entity_name}.{property_name}", before)
        return True

    def set_entity_groups(self, entity_name: str, groups: list[str]) -> bool:
        return self.update_entity_property(entity_name, "groups", groups)

    def replace_component_data(self, entity_name: str, component_name: str, component_data: Dict[str, Any]) -> bool:
        entry = self._get_active_entry()
        if entry is None or entry.is_playing or entry.edit_world is None:
            return False
        if not self._flush_pending_edit_world(entry, failure_context=f"{entity_name}.{component_name}"):
            return False
        snapshot = self._capture_serializable_mutation(entry)
        before = snapshot.scene_data
        normalized_component_data = self._canonicalize_component_payload(component_name, component_data)
        if not entry.scene.replace_component_data(entity_name, component_name, normalized_component_data):
            if not self._structural_authoring.replace_prefab_component_override(entry, entity_name, component_name, component_data):
                return False
        if component_name == "SceneLink":
            self._sync_feature_metadata_from_scene_links(entry)
        if not self._commit_serializable_scene_mutation(
            entry,
            snapshot,
            failure_context=f"{entity_name}.{component_name}",
        ):
            return False
        entry.dirty = True
        self._record_scene_change(entry, f"{entity_name}.{component_name}", before)
        return True

    def get_component_metadata(self, entity_name: str, component_name: str) -> Dict[str, Any]:
        entry = self._get_active_entry()
        return entry.scene.get_component_metadata(entity_name, component_name) if entry is not None else {}

    def set_component_metadata(self, entity_name: str, component_name: str, metadata: Dict[str, Any]) -> bool:
        entry = self._get_active_entry()
        if entry is None or entry.is_playing:
            return False
        if not self._flush_pending_edit_world(entry, failure_context=f"{entity_name}.{component_name}.metadata"):
            return False
        before = copy.deepcopy(entry.scene.to_dict())
        if not entry.scene.set_component_metadata(entity_name, component_name, metadata):
            return False
        self._rebuild_edit_world(entry)
        entry.dirty = True
        self._record_scene_change(entry, f"{entity_name}.{component_name}.metadata", before)
        return True

    def create_entity(self, name: str, components: Optional[Dict[str, Dict[str, Any]]] = None) -> bool:
        entry = self._get_active_entry()
        if entry is None or entry.is_playing:
            return False
        if not self._flush_pending_edit_world(entry, failure_context=f"create_entity:{name}"):
            return False
        payload = {
            "name": name,
            "active": True,
            "tag": "Untagged",
            "layer": "Default",
            "parent": None,
            "components": components
            or {"Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0}},
            "component_metadata": {},
        }
        components_payload = payload["components"]
        metadata_payload = payload["component_metadata"]
        if isinstance(components_payload, dict) and isinstance(metadata_payload, dict):
            for component_name in components_payload.keys():
                metadata_payload[component_name] = {"origin": self._registry.get_origin(str(component_name))}
        canonical_entity = self._add_entity_incrementally(entry, payload, failure_context=f"create_entity:{name}")
        if canonical_entity is None:
            return False
        entry.dirty = True
        self._record_entity_create_delta(entry, f"create_entity:{name}", canonical_entity)
        return True

    def create_entity_from_data(self, entity_data: Dict[str, Any]) -> bool:
        entry = self._get_active_entry()
        if entry is None or entry.is_playing:
            return False
        entity_name = str(entity_data.get("name", "") or "")
        if not self._flush_pending_edit_world(entry, failure_context=f"create_entity:{entity_name}"):
            return False
        payload = clone_json_value(entity_data)
        payload.setdefault("active", True)
        payload.setdefault("tag", "Untagged")
        payload.setdefault("layer", "Default")
        payload.setdefault("parent", None)
        payload.setdefault("components", {})
        payload.setdefault("component_metadata", {})
        for component_name in payload["components"].keys():
            payload["component_metadata"].setdefault(component_name, {})
            payload["component_metadata"][component_name].setdefault("origin", self._registry.get_origin(component_name))
        canonical_entity = self._add_entity_incrementally(
            entry,
            payload,
            failure_context=f"create_entity:{payload.get('name', '')}",
        )
        if canonical_entity is None:
            return False
        entry.dirty = True
        self._record_entity_create_delta(
            entry,
            f"create_entity:{payload.get('name', '')}",
            canonical_entity,
        )
        return True

    def remove_entity(self, entity_name: str) -> bool:
        return self._structural_authoring.remove_entity(entity_name)

    def add_component_to_entity(self, entity_name: str, component_name: str, component_data: Optional[Dict[str, Any]] = None) -> bool:
        entry = self._get_active_entry()
        if entry is None or entry.is_playing:
            return False
        if not self._flush_pending_edit_world(entry, failure_context=f"add_component:{entity_name}.{component_name}"):
            return False
        snapshot = self._capture_serializable_mutation(entry)
        before = snapshot.scene_data
        data = self._canonicalize_component_payload(component_name, component_data or {"enabled": True})
        if not entry.scene.add_component(entity_name, component_name, data):
            if not self._structural_authoring.replace_prefab_component_override(entry, entity_name, component_name, data):
                return False
        entry.scene.set_component_metadata(entity_name, component_name, {"origin": self._registry.get_origin(component_name)})
        if component_name == "SceneLink":
            self._sync_feature_metadata_from_scene_links(entry)
        if not self._commit_serializable_scene_mutation(
            entry,
            snapshot,
            failure_context=f"add_component:{entity_name}.{component_name}",
        ):
            return False
        entry.dirty = True
        self._record_scene_change(entry, f"add_component:{entity_name}.{component_name}", before)
        return True

    def remove_component_from_entity(self, entity_name: str, component_name: str) -> bool:
        entry = self._get_active_entry()
        if entry is None or entry.is_playing:
            return False
        if not self._flush_pending_edit_world(entry, failure_context=f"remove_component:{entity_name}.{component_name}"):
            return False
        before = copy.deepcopy(entry.scene.to_dict())
        if not entry.scene.remove_component(entity_name, component_name):
            if not self._structural_authoring.remove_prefab_component_override(entry, entity_name, component_name):
                return False
        if component_name == "SceneLink":
            self._sync_feature_metadata_from_scene_links(entry)
        self._rebuild_edit_world(entry)
        entry.dirty = True
        self._record_scene_change(entry, f"remove_component:{entity_name}.{component_name}", before)
        return True

    def set_component_enabled(self, entity_name: str, component_name: str, enabled: bool) -> bool:
        return self.apply_edit_to_world(entity_name, component_name, "enabled", enabled)

    def find_entity_data(self, entity_name: str) -> Optional[Dict[str, Any]]:
        entry = self._get_active_entry()
        if entry is None:
            return None
        self._flush_pending_edit_world(entry, failure_context=f"read_entity:{entity_name}")
        return entry.scene.find_entity(entity_name)

    def find_entity_data_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        entry = self._get_active_entry()
        if entry is None:
            return None
        self._flush_pending_edit_world(entry, failure_context=f"read_entity_id:{entity_id}")
        return entry.scene.find_entity_by_id(entity_id)

    def update_entity_property_by_id(self, entity_id: str, property_name: str, value: Any) -> bool:
        entity_data = self.find_entity_data_by_id(entity_id)
        entity_name = entity_data.get("name") if isinstance(entity_data, dict) else None
        return self.update_entity_property(entity_name, property_name, value) if isinstance(entity_name, str) else False

    def apply_edit_to_world_by_id(self, entity_id: str, component_name: str, property_name: str, value: Any) -> bool:
        entity_data = self.find_entity_data_by_id(entity_id)
        entity_name = entity_data.get("name") if isinstance(entity_data, dict) else None
        return self.apply_edit_to_world(entity_name, component_name, property_name, value) if isinstance(entity_name, str) else False

    def replace_component_data_by_id(self, entity_id: str, component_name: str, component_data: Dict[str, Any]) -> bool:
        entity_data = self.find_entity_data_by_id(entity_id)
        entity_name = entity_data.get("name") if isinstance(entity_data, dict) else None
        return self.replace_component_data(entity_name, component_name, component_data) if isinstance(entity_name, str) else False

    def add_component_to_entity_by_id(
        self,
        entity_id: str,
        component_name: str,
        component_data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        entity_data = self.find_entity_data_by_id(entity_id)
        entity_name = entity_data.get("name") if isinstance(entity_data, dict) else None
        return self.add_component_to_entity(entity_name, component_name, component_data) if isinstance(entity_name, str) else False

    def remove_component_from_entity_by_id(self, entity_id: str, component_name: str) -> bool:
        entity_data = self.find_entity_data_by_id(entity_id)
        entity_name = entity_data.get("name") if isinstance(entity_data, dict) else None
        return self.remove_component_from_entity(entity_name, component_name) if isinstance(entity_name, str) else False

    def remove_entity_by_id(self, entity_id: str) -> bool:
        entity_data = self.find_entity_data_by_id(entity_id)
        entity_name = entity_data.get("name") if isinstance(entity_data, dict) else None
        return self.remove_entity(entity_name) if isinstance(entity_name, str) else False

    def sync_from_edit_world(self, force: bool = False) -> bool:
        """Deprecated: use EngineAPI or SceneManager public methods instead.

        Legacy method that syncs pending changes from edit_world back to the serialized scene.
        Prefer authoring through SceneManager structural authoring methods or EngineAPI delegates.
        """
        warnings.warn(
            "sync_from_edit_world() is deprecated. Use EngineAPI or SceneManager public methods instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        entry = self._get_active_entry()
        if entry is None or entry.is_playing or entry.edit_world is None:
            return False
        if not force and not self._has_pending_legacy_world_sync(entry):
            return False
        return self._sync_entry_from_edit_world(entry)

    def mark_edit_world_dirty(self, reason: str = LEGACY_AUTHORING_SYNC_REASON) -> bool:
        entry = self._get_active_entry()
        if entry is None or entry.is_playing or entry.edit_world is None:
            return False
        # Preview edits (for example gizmo drags in progress) stay in edit_world only
        # and must not turn the scene into persistible dirty state.
        if reason == TRANSIENT_PREVIEW_SYNC_REASON:
            if not self._has_pending_legacy_world_sync(entry):
                entry.pending_edit_world_sync_reason = TRANSIENT_PREVIEW_SYNC_REASON
            return True
        if not self._has_pending_legacy_world_sync(entry):
            entry.dirty_before_pending_edit_world_sync = entry.dirty
        entry.dirty = True
        entry.pending_edit_world_sync_reason = LEGACY_AUTHORING_SYNC_REASON
        return True

    def set_feature_metadata(self, key: str, value: Any) -> bool:
        entry = self._get_active_entry()
        if entry is None or entry.is_playing:
            return False
        if not self._flush_pending_edit_world(entry, failure_context=f"feature_metadata:{key}"):
            return False
        snapshot = self._capture_serializable_mutation(entry)
        before = snapshot.scene_data
        entry.scene.set_feature_metadata(key, copy.deepcopy(value))
        if not self._commit_serializable_scene_mutation(
            entry,
            snapshot,
            failure_context=f"feature_metadata:{key}",
        ):
            return False
        entry.dirty = True
        self._record_scene_change(entry, f"feature_metadata:{key}", before)
        return True

    def apply_transform_state(
        self,
        entity_name: str,
        transform_state: Dict[str, Any],
        key_or_path: Optional[str] = None,
        *,
        record_history: bool = False,
        label: str | None = None,
    ) -> bool:
        entry = self._resolve_entry(key_or_path)
        if entry is None:
            return False
        if self._can_apply_direct_transform_state(entry, entity_name):
            return self._apply_direct_transform_state(
                entry,
                entity_name,
                transform_state,
                record_history=record_history,
                label=label or f"transform:{entity_name}",
            )
        return self._apply_authoring_component_state(
            entry,
            entity_name,
            "Transform",
            transform_state,
            editable_fields=("x", "y", "rotation", "scale_x", "scale_y"),
            record_history=record_history,
            label=label or f"transform:{entity_name}",
        )

    def apply_rect_transform_state(
        self,
        entity_name: str,
        rect_state: Dict[str, Any],
        key_or_path: Optional[str] = None,
        *,
        record_history: bool = False,
        label: str | None = None,
    ) -> bool:
        entry = self._resolve_entry(key_or_path)
        if entry is None:
            return False
        if self._can_apply_direct_component_state(entry, entity_name, "RectTransform"):
            return self._apply_direct_component_state(
                entry,
                entity_name,
                "RectTransform",
                rect_state,
                editable_fields=("anchored_x", "anchored_y", "width", "height", "rotation", "scale_x", "scale_y"),
                record_history=record_history,
                label=label or f"rect_transform:{entity_name}",
            )
        return self._apply_authoring_component_state(
            entry,
            entity_name,
            "RectTransform",
            rect_state,
            editable_fields=("anchored_x", "anchored_y", "width", "height", "rotation", "scale_x", "scale_y"),
            record_history=record_history,
            label=label or f"rect_transform:{entity_name}",
        )

    def set_selected_entity(self, entity_name: Optional[str]) -> bool:
        entry = self._get_active_entry()
        if entry is None or entry.active_world is None:
            return False
        if entity_name and entry.active_world.get_entity_by_name(entity_name) is None:
            return False
        entry.selected_entity_name = entity_name
        entry.selected_entity_id = self._entity_id_for_name(entry, entity_name)
        entry.active_world.selected_entity_name = entity_name
        if entry.edit_world is not None:
            entry.edit_world.selected_entity_name = entity_name
        if entry.runtime_world is not None:
            entry.runtime_world.selected_entity_name = entity_name
        return True

    def save_scene_to_file(
        self,
        path: str,
        key: Optional[str] = None,
        compact_save: Optional[bool] = None,
        storage: Optional[SceneStorage] = None,
    ) -> bool:
        entry = self._resolve_entry(key)
        if entry is None or entry.edit_world is None:
            return False
        try:
            # Only legacy world-only authoring is flushed back into Scene before save.
            # Transient previews are intentionally discarded by the rebuild below.
            if self._has_pending_transient_preview(entry):
                self._rebuild_edit_world(entry)
                self._clear_pending_edit_world_sync(entry)
            elif self._has_pending_legacy_world_sync(entry):
                if not self._flush_pending_edit_world(entry, failure_context=f"save_scene:{Path(path).name}"):
                    return False
            elif entry.edit_world.version != entry.edit_world_version:
                self._sync_entry_from_edit_world(entry)
            data = self._validated_scene_payload(entry.scene.to_dict())
            saved = self._persistence.save(
                path,
                data,
                compact_save=compact_save,
                storage=storage,
            )
            self._install_scene_payload(entry, saved.payload, source_path=path)
            self._workspace.rekey_entry(entry, self._build_scene_key(path, entry.scene.name))
            entry.dirty = False
            self._clear_pending_edit_world_sync(entry)
            if saved.mtime is not None:
                self._scene_file_mtimes[saved.resolved_path] = saved.mtime
            self._fire_on_scene_saved(
                saved.resolved_path,
                entry.key,
                entry.scene.name,
                saved.entity_count,
            )
            return True
        except Exception as exc:
            log_err(f"SceneManager: error al guardar en {path}: {exc}")
            return False

    def restore_scene_data(self, data: Dict[str, Any]) -> bool:
        entry = self._get_active_entry()
        if entry is None or entry.is_playing:
            return False
        try:
            self._restore_entry_scene(entry, data)
        except ValueError:
            return False
        entry.dirty = True
        return True

    def set_entity_parent(self, entity_name: str, parent_name: Optional[str]) -> bool:
        """Reparent an entity, preserving its world-space transform."""
        return self._structural_authoring.set_entity_parent(entity_name, parent_name)

    def create_child_entity(self, parent_name: str, name: str, components: Optional[Dict[str, Dict[str, Any]]] = None) -> bool:
        """Create a new entity as a child. The provided component coords are local (no world-position preservation)."""
        return self._structural_authoring.create_child_entity(parent_name, name, components)

    def instantiate_prefab(self, name: str, prefab_path: str, parent: Optional[str] = None, overrides: Optional[Dict[str, Any]] = None, root_name: Optional[str] = None) -> bool:
        return self._structural_authoring.instantiate_prefab(name, prefab_path, parent, overrides, root_name)

    def create_prefab(
        self,
        entity_name: str,
        prefab_path: str,
        *,
        replace_original: bool = False,
        instance_name: Optional[str] = None,
        prefab_locator: Optional[str] = None,
    ) -> bool:
        return self._structural_authoring.create_prefab(
            entity_name,
            prefab_path,
            replace_original=replace_original,
            instance_name=instance_name,
            prefab_locator=prefab_locator,
        )

    def unpack_prefab(self, entity_name: str) -> bool:
        return self._structural_authoring.unpack_prefab(entity_name)

    def apply_prefab_overrides(self, entity_name: str) -> bool:
        return self._structural_authoring.apply_prefab_overrides(entity_name)

    def duplicate_entity_subtree(self, entity_name: str, new_root_name: Optional[str] = None) -> bool:
        return self._structural_authoring.duplicate_entity_subtree(entity_name, new_root_name)

    def copy_entity_subtree(self, entity_name: str) -> bool:
        return self._structural_authoring.copy_entity_subtree(entity_name)

    def paste_copied_entities(self, target_scene_key: Optional[str] = None) -> bool:
        return self._structural_authoring.paste_copied_entities(target_scene_key)

    def clear_dirty(self) -> None:
        entry = self._get_active_entry()
        if entry is not None:
            entry.dirty = False

    def clear_all_dirty(self) -> None:
        for entry in self._entries.values():
            entry.dirty = False

    def begin_transaction(self, label: str = "transaction", key: Optional[str] = None) -> bool:
        return self._change_history.begin_transaction(label=label, key=key)

    def apply_change(self, change: Change | dict[str, Any], key: Optional[str] = None) -> bool:
        return self._change_history.apply_change(change, key=key)

    def commit_transaction(self) -> Optional[Dict[str, Any]]:
        return self._change_history.commit_transaction()

    def rollback_transaction(self) -> bool:
        return self._change_history.rollback_transaction()

    def begin_authoring_transaction(self, label: str, key_or_path: Optional[str] = None) -> bool:
        entry = self._resolve_entry(key_or_path)
        if entry is None or entry.is_playing or self._authoring_transaction is not None:
            return False
        self._authoring_transaction = AuthoringTransactionState(
            label=str(label or "authoring_transaction"),
            key=entry.key,
        )
        return True

    def update_authoring_transaction(
        self,
        entity_name: str,
        component_name: str,
        component_state: Dict[str, Any],
        key_or_path: Optional[str] = None,
    ) -> bool:
        if self._authoring_transaction is None:
            return False
        entry = self._resolve_entry(key_or_path)
        if entry is None or entry.key != self._authoring_transaction.key:
            return False
        if component_name == "Transform":
            return self.apply_transform_state(entity_name, component_state, entry.key, record_history=True)
        if component_name == "RectTransform":
            return self.apply_rect_transform_state(entity_name, component_state, entry.key, record_history=True)
        return False

    def commit_authoring_transaction(self) -> Optional[Dict[str, Any]]:
        transaction = self._authoring_transaction
        if transaction is None:
            return None
        self._authoring_transaction = None
        changes = [
            copy.deepcopy(delta)
            for delta in transaction.changes.values()
            if delta.old_properties != delta.new_properties
        ]
        if changes:
            key = transaction.key
            undo_changes = copy.deepcopy(changes)
            redo_changes = copy.deepcopy(changes)
            self._change_history.record_differential_change(
                label=transaction.label,
                undo=lambda key=key, changes=undo_changes: self._apply_authoring_transaction_deltas(
                    key,
                    changes,
                    use_old=True,
                ),
                redo=lambda key=key, changes=redo_changes: self._apply_authoring_transaction_deltas(
                    key,
                    changes,
                    use_old=False,
                ),
            )
        return {
            "label": transaction.label,
            "scene_key": transaction.key,
            "changed_component_count": len(changes),
        }

    def cancel_authoring_transaction(self) -> bool:
        transaction = self._authoring_transaction
        if transaction is None:
            return False
        self._authoring_transaction = None
        return self._apply_authoring_transaction_deltas(
            transaction.key,
            list(transaction.changes.values()),
            use_old=True,
        )

    def get_scene_flow(self) -> Dict[str, str]:
        entry = self._get_active_entry()
        if entry is None:
            return {}
        result: Dict[str, str] = {}
        metadata = entry.scene.feature_metadata.get("scene_flow", {})
        if isinstance(metadata, dict):
            result.update({str(key): str(value) for key, value in metadata.items() if str(key).strip() and str(value).strip()})
        for entity_data in entry.scene.entities_data:
            scene_link = entity_data.get("components", {}).get("SceneLink")
            if isinstance(scene_link, dict):
                flow_key = str(scene_link.get("flow_key", "") or "").strip()
                target_path = str(scene_link.get("target_path", "") or "").strip()
                if flow_key and target_path:
                    result[flow_key] = target_path
        return result

    def set_scene_flow_target(self, key: str, target_path: str) -> bool:
        entry = self._get_active_entry()
        if entry is None or entry.is_playing:
            return False
        scene_key = str(key).strip()
        if not scene_key:
            return False
        if not self._flush_pending_edit_world(entry, failure_context=f"scene_flow:{scene_key}"):
            return False
        snapshot = self._capture_serializable_mutation(entry)
        before = snapshot.scene_data
        scene_flow = entry.scene.feature_metadata.setdefault("scene_flow", {})
        if not isinstance(scene_flow, dict):
            scene_flow = {}
            entry.scene.feature_metadata["scene_flow"] = scene_flow
        if target_path:
            scene_flow[scene_key] = target_path
        else:
            scene_flow.pop(scene_key, None)
            if not scene_flow:
                entry.scene.feature_metadata.pop("scene_flow", None)
        self._sync_scene_links_from_feature_metadata(entry)
        if not self._commit_serializable_scene_mutation(
            entry,
            snapshot,
            failure_context=f"scene_flow:{scene_key}",
        ):
            return False
        entry.dirty = True
        self._record_scene_change(entry, f"scene_flow:{scene_key}", before)
        return True

    def _compile_runtime_signals_for_entry(self, entry: SceneWorkspaceEntry, runtime_world: "World") -> None:
        compiler = self._runtime_signal_compiler
        if compiler is None:
            return
        try:
            compiler(entry.scene, runtime_world)
        except Exception as exc:
            log_err(f"SceneManager: no se pudieron compilar las señales runtime: {exc}")

    def _get_active_entry(self) -> Optional[SceneWorkspaceEntry]:
        return self._workspace.get_active_entry()

    def _resolve_entry(self, key_or_path: Optional[str]) -> Optional[SceneWorkspaceEntry]:
        return self._workspace.resolve_entry(key_or_path)

    def resolve_entry(self, key_or_path: Optional[str]) -> Optional[SceneWorkspaceEntry]:
        """Retorna la entrada de workspace para una clave o ruta dada.

        Si key_or_path es None o vacío, retorna la entrada activa.
        """
        return self._resolve_entry(key_or_path)

    def _entry_path_or_key(self, entry: Optional[SceneWorkspaceEntry]) -> str:
        return "" if entry is None else (entry.source_path or entry.key)

    def _create_untitled_scene_key(self, scene_name: str) -> str:
        _ = scene_name
        key = f"untitled:{self._untitled_counter}"
        self._untitled_counter += 1
        return key

    def _build_scene_key(self, source_path: Optional[str], scene_name: str) -> str:
        if source_path:
            return Path(source_path).resolve().as_posix()
        key = f"untitled:{self._untitled_counter}:{scene_name}"
        self._untitled_counter += 1
        return key

    def _validated_scene_payload(self, data: Dict[str, Any]) -> Dict[str, Any]:
        payload = migrate_scene_data(copy.deepcopy(data))
        validation_errors = validate_scene_data(payload)
        if validation_errors:
            raise ValueError(f"Invalid scene payload: {'; '.join(validation_errors)}")
        return payload

    def _canonicalize_component_payload(self, component_name: str, component_data: Dict[str, Any]) -> Dict[str, Any]:
        payload = copy.deepcopy(component_data)
        rebuilt_component = self._registry.create(component_name, payload)
        if rebuilt_component is None or not hasattr(rebuilt_component, "to_dict"):
            return payload
        rebuilt_payload = rebuilt_component.to_dict()
        return copy.deepcopy(rebuilt_payload) if isinstance(rebuilt_payload, dict) else payload

    def _build_canonical_scene_payload(
        self,
        entry: SceneWorkspaceEntry,
        world_snapshot: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        edit_world = entry.edit_world
        if edit_world is None and world_snapshot is None:
            raise ValueError("Cannot build scene payload without edit world")
        if world_snapshot is not None:
            snapshot_source = world_snapshot
        else:
            if edit_world is None:
                raise ValueError("Cannot build scene payload without edit world")
            snapshot_source = edit_world.serialize()
        snapshot = copy.deepcopy(snapshot_source)
        payload = build_canonical_scene_payload(
            scene_name=entry.scene.name,
            world_snapshot=snapshot,
            rules_data=entry.scene.rules_data,
            feature_metadata=entry.scene.feature_metadata,
        )
        return self._validated_scene_payload(payload)

    def _restore_entry_scene(self, entry: SceneWorkspaceEntry, data: Dict[str, Any]) -> None:
        self._install_scene_payload(entry, data)

    def _install_scene_payload(
        self,
        entry: SceneWorkspaceEntry,
        data: Dict[str, Any],
        *,
        source_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = self._validated_scene_payload(data)
        target_source_path = entry.scene.source_path if source_path is None else source_path
        entry.scene = Scene(payload.get("name", entry.scene.name), payload, source_path=target_source_path)
        self._sync_scene_links_from_feature_metadata(entry)
        self._rebuild_edit_world(entry)
        self._clear_pending_edit_world_sync(entry)
        return payload

    def _rebuild_edit_world(self, entry: SceneWorkspaceEntry) -> None:
        world_selected_name = entry.edit_world.selected_entity_name if entry.edit_world is not None else None
        selected_id = entry.selected_entity_id or self._entity_id_for_name(entry, entry.selected_entity_name)
        if selected_id is None:
            selected_id = self._entity_id_for_name(entry, world_selected_name)
        selected_name = self._entity_name_for_id(entry, selected_id) or entry.selected_entity_name or world_selected_name
        entry.edit_world = entry.scene.create_world(self._registry)
        if selected_name and entry.edit_world.get_entity_by_name(selected_name) is not None:
            entry.edit_world.selected_entity_name = selected_name
            entry.selected_entity_name = selected_name
            entry.selected_entity_id = self._entity_id_for_name(entry, selected_name)
        else:
            entry.selected_entity_name = None
            entry.selected_entity_id = None
            entry.edit_world.selected_entity_name = None
        entry.edit_world_version = entry.edit_world.version

    def _add_entity_incrementally(
        self,
        entry: SceneWorkspaceEntry,
        payload: Dict[str, Any],
        *,
        failure_context: str,
    ) -> Optional[Dict[str, Any]]:
        entity_name = str(payload.get("name", "") or "")
        if entry.edit_world is None or not entry.scene.add_entity(payload):
            return None
        canonical_entity = entry.scene.find_entity(entity_name)
        if canonical_entity is None:
            return None
        try:
            entry.scene.materialize_entity(entry.edit_world, self._registry, canonical_entity)
        except Exception as exc:
            entry.scene.remove_entity_by_id(str(canonical_entity.get("id", "") or ""))
            log_err(f"SceneManager: rejected incremental entity during {failure_context}: {exc}")
            return None
        if self._entity_has_scene_link(canonical_entity):
            self._sync_feature_metadata_from_scene_links(entry)
        self._clear_pending_edit_world_sync(entry)
        entry.edit_world_version = entry.edit_world.version
        return canonical_entity

    def _record_entity_create_delta(
        self,
        entry: SceneWorkspaceEntry,
        label: str,
        entity_data: Dict[str, Any],
    ) -> None:
        key = entry.key
        payload = clone_json_value(entity_data)
        entity_id = str(entity_data.get("id", "") or "")
        self._change_history.record_differential_change(
            label=label,
            undo=lambda key=key, entity_id=entity_id: self._remove_entity_create_delta(key, entity_id),
            redo=lambda key=key, payload=payload: self._restore_entity_create_delta(key, payload),
        )

    def _remove_entity_create_delta(self, key: str, entity_id: str) -> bool:
        entry = self._resolve_entry(key)
        if entry is None or entry.is_playing or entry.edit_world is None:
            return False
        entity_data = entry.scene.find_entity_by_id(entity_id)
        if entity_data is None:
            return False
        entity_name = str(entity_data.get("name", "") or "")
        had_scene_link = self._entity_has_scene_link(entity_data)
        if not entry.scene.remove_entity_by_id(entity_id):
            return False
        self._remove_world_entity_projection(entry.edit_world, entity_name, entity_id)
        if had_scene_link:
            self._sync_feature_metadata_from_scene_links(entry)
        self._clear_pending_edit_world_sync(entry)
        entry.edit_world_version = entry.edit_world.version
        entry.dirty = True
        return True

    def _restore_entity_create_delta(self, key: str, entity_data: Dict[str, Any]) -> bool:
        entry = self._resolve_entry(key)
        if entry is None or entry.is_playing:
            return False
        restored = self._add_entity_incrementally(
            entry,
            clone_json_value(entity_data),
            failure_context=f"redo_create_entity:{entity_data.get('name', '')}",
        )
        if restored is None:
            return False
        entry.dirty = True
        return True

    @staticmethod
    def _remove_world_entity_projection(world: "World", entity_name: str, entity_id: str) -> None:
        from engine.components.transform import Transform

        root = world.get_entity_by_serialized_id(entity_id) or world.get_entity_by_name(entity_name)
        targets = [
            entity
            for entity in world.iter_all_entities()
            if entity is root or entity.prefab_root_name == entity_name
        ]
        for entity in reversed(targets):
            transform = entity.get_component(Transform)
            if transform is not None and transform.parent is not None:
                transform.parent = None
            world.remove_entity(entity.id)

    def _entity_id_for_name(self, entry: SceneWorkspaceEntry, entity_name: Optional[str]) -> Optional[str]:
        if not entity_name:
            return None
        entity_data = entry.scene.find_entity(entity_name)
        entity_id = entity_data.get("id") if isinstance(entity_data, dict) else None
        return entity_id.strip() if isinstance(entity_id, str) and entity_id.strip() else None

    def _entity_name_for_id(self, entry: SceneWorkspaceEntry, entity_id: Optional[str]) -> Optional[str]:
        if not entity_id:
            return None
        entity_data = entry.scene.find_entity_by_id(entity_id)
        entity_name = entity_data.get("name") if isinstance(entity_data, dict) else None
        return entity_name if isinstance(entity_name, str) and entity_name else None

    def _has_pending_legacy_world_sync(self, entry: SceneWorkspaceEntry) -> bool:
        return entry.pending_edit_world_sync_reason == LEGACY_AUTHORING_SYNC_REASON

    def _has_pending_transient_preview(self, entry: SceneWorkspaceEntry) -> bool:
        return entry.pending_edit_world_sync_reason == TRANSIENT_PREVIEW_SYNC_REASON

    def _clear_pending_edit_world_sync(self, entry: SceneWorkspaceEntry) -> None:
        entry.pending_edit_world_sync_reason = None
        entry.dirty_before_pending_edit_world_sync = None

    def _reject_invalid_pending_edit_world(
        self,
        entry: SceneWorkspaceEntry,
        *,
        failure_context: str,
        error: ValueError,
    ) -> bool:
        self._rebuild_edit_world(entry)
        entry.dirty = (
            entry.dirty_before_pending_edit_world_sync
            if entry.dirty_before_pending_edit_world_sync is not None
            else entry.dirty
        )
        self._clear_pending_edit_world_sync(entry)
        log_err(
            f"SceneManager: rejected invalid legacy authoring snapshot during {failure_context}: {error}"
        )
        return False

    def _flush_pending_edit_world(
        self,
        entry: SceneWorkspaceEntry,
        *,
        failure_context: str = "legacy_authoring_flush",
    ) -> bool:
        if not self._has_pending_legacy_world_sync(entry) or entry.key != self._active_scene_key:
            return True
        try:
            return self.sync_from_edit_world(force=True)
        except ValueError as exc:
            return self._reject_invalid_pending_edit_world(
                entry,
                failure_context=failure_context,
                error=exc,
            )

    def _can_apply_direct_transform_state(self, entry: SceneWorkspaceEntry, entity_name: str) -> bool:
        return self._can_apply_direct_component_state(entry, entity_name, "Transform")

    def _can_apply_direct_component_state(self, entry: SceneWorkspaceEntry, entity_name: str, component_name: str) -> bool:
        if entry.is_playing:
            return False
        entity_data = entry.scene.find_entity(entity_name)
        if entity_data is None:
            return False
        component_data = entity_data.get("components", {}).get(component_name)
        return isinstance(component_data, dict)

    def _apply_direct_transform_state(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: str,
        transform_state: Dict[str, Any],
        *,
        record_history: bool,
        label: str,
    ) -> bool:
        old_properties, new_properties = self._apply_transform_properties_to_entry(
            entry,
            entity_name,
            transform_state,
        )
        if not new_properties:
            return True
        if self._record_authoring_transaction_delta(
            entry,
            entity_name,
            "Transform",
            old_properties,
            new_properties,
        ):
            return True
        if record_history:
            key = entry.key
            old_snapshot = copy.deepcopy(old_properties)
            new_snapshot = copy.deepcopy(new_properties)
            self._change_history.record_differential_change(
                label=label,
                undo=lambda key=key, entity_name=entity_name, old=old_snapshot: self._apply_transform_history_delta(
                    key,
                    entity_name,
                    old,
                ),
                redo=lambda key=key, entity_name=entity_name, new=new_snapshot: self._apply_transform_history_delta(
                    key,
                    entity_name,
                    new,
                ),
            )
        return True

    def _apply_direct_component_state(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: str,
        component_name: str,
        component_state: Dict[str, Any],
        *,
        editable_fields: tuple[str, ...],
        record_history: bool,
        label: str,
    ) -> bool:
        old_properties, new_properties = self._apply_component_properties_to_entry(
            entry,
            entity_name,
            component_name,
            component_state,
            editable_fields=editable_fields,
        )
        if not new_properties:
            return True
        if self._record_authoring_transaction_delta(
            entry,
            entity_name,
            component_name,
            old_properties,
            new_properties,
        ):
            return True
        if record_history:
            key = entry.key
            old_snapshot = copy.deepcopy(old_properties)
            new_snapshot = copy.deepcopy(new_properties)
            self._change_history.record_differential_change(
                label=label,
                undo=lambda key=key, entity_name=entity_name, component_name=component_name, old=old_snapshot: self._apply_component_history_delta(
                    key,
                    entity_name,
                    component_name,
                    old,
                ),
                redo=lambda key=key, entity_name=entity_name, component_name=component_name, new=new_snapshot: self._apply_component_history_delta(
                    key,
                    entity_name,
                    component_name,
                    new,
                ),
            )
        return True

    def _apply_transform_history_delta(
        self,
        key: str,
        entity_name: str,
        properties: Dict[str, Any],
    ) -> bool:
        entry = self._resolve_entry(key)
        if entry is None:
            return False
        self._apply_transform_properties_to_entry(entry, entity_name, properties)
        return True

    def _apply_component_history_delta(
        self,
        key: str,
        entity_name: str,
        component_name: str,
        properties: Dict[str, Any],
    ) -> bool:
        entry = self._resolve_entry(key)
        if entry is None:
            return False
        editable_fields = self._editable_fields_for_authoring_component(component_name)
        if editable_fields is None:
            return False
        self._apply_component_properties_to_entry(
            entry,
            entity_name,
            component_name,
            properties,
            editable_fields=editable_fields,
        )
        return True

    def _apply_transform_properties_to_entry(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: str,
        transform_state: Dict[str, Any],
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        entity_data = entry.scene.find_entity(entity_name)
        if entity_data is None:
            return {}, {}
        component_data = entity_data.get("components", {}).get("Transform")
        if not isinstance(component_data, dict):
            return {}, {}

        editable_fields = ("x", "y", "rotation", "scale_x", "scale_y")
        old_properties: Dict[str, Any] = {}
        new_properties: Dict[str, Any] = {}
        for field_name in editable_fields:
            if field_name not in transform_state:
                continue
            value = float(transform_state[field_name])
            previous = component_data.get(field_name)
            if previous == value:
                continue
            old_properties[field_name] = previous
            new_properties[field_name] = value
            component_data[field_name] = value

        if not new_properties:
            return old_properties, new_properties

        entry.selected_entity_name = entity_name
        entry.selected_entity_id = self._entity_id_for_name(entry, entity_name)
        entry.dirty = True
        self._clear_pending_edit_world_sync(entry)
        self._apply_transform_properties_to_edit_world(entry, entity_name, component_data)
        if entry.edit_world is not None:
            entry.edit_world_version = entry.edit_world.version
        return old_properties, new_properties

    def _apply_component_properties_to_entry(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: str,
        component_name: str,
        component_state: Dict[str, Any],
        *,
        editable_fields: tuple[str, ...],
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        entity_data = entry.scene.find_entity(entity_name)
        if entity_data is None:
            return {}, {}
        component_data = entity_data.get("components", {}).get(component_name)
        if not isinstance(component_data, dict):
            return {}, {}

        old_properties: Dict[str, Any] = {}
        new_properties: Dict[str, Any] = {}
        for field_name in editable_fields:
            if field_name not in component_state:
                continue
            value = float(component_state[field_name])
            previous = component_data.get(field_name)
            if previous == value:
                continue
            old_properties[field_name] = previous
            new_properties[field_name] = value
            component_data[field_name] = value

        if not new_properties:
            return old_properties, new_properties

        entry.selected_entity_name = entity_name
        entry.selected_entity_id = self._entity_id_for_name(entry, entity_name)
        entry.dirty = True
        self._clear_pending_edit_world_sync(entry)
        self._apply_component_properties_to_edit_world(entry, entity_name, component_name, component_data)
        if entry.edit_world is not None:
            entry.edit_world_version = entry.edit_world.version
        return old_properties, new_properties

    def _record_authoring_transaction_delta(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: str,
        component_name: str,
        old_properties: Dict[str, Any],
        new_properties: Dict[str, Any],
    ) -> bool:
        transaction = self._authoring_transaction
        if transaction is None:
            return False
        if transaction.key != entry.key:
            return False
        delta_key = (entity_name, component_name)
        delta = transaction.changes.get(delta_key)
        if delta is None:
            delta = AuthoringComponentDelta(entity_name=entity_name, component_name=component_name)
            transaction.changes[delta_key] = delta
        for field_name, old_value in old_properties.items():
            if field_name not in delta.old_properties:
                delta.old_properties[field_name] = old_value
            delta.new_properties[field_name] = new_properties[field_name]
            if delta.new_properties[field_name] == delta.old_properties[field_name]:
                delta.old_properties.pop(field_name, None)
                delta.new_properties.pop(field_name, None)
        if not delta.new_properties:
            transaction.changes.pop(delta_key, None)
        return True

    def _apply_authoring_transaction_deltas(
        self,
        key: str,
        changes: list[AuthoringComponentDelta],
        *,
        use_old: bool,
    ) -> bool:
        entry = self._resolve_entry(key)
        if entry is None:
            return False
        for delta in changes:
            editable_fields = self._editable_fields_for_authoring_component(delta.component_name)
            if editable_fields is None:
                return False
            properties = delta.old_properties if use_old else delta.new_properties
            self._apply_component_properties_to_entry(
                entry,
                delta.entity_name,
                delta.component_name,
                properties,
                editable_fields=editable_fields,
            )
        return True

    def _editable_fields_for_authoring_component(self, component_name: str) -> tuple[str, ...] | None:
        if component_name == "Transform":
            return ("x", "y", "rotation", "scale_x", "scale_y")
        if component_name == "RectTransform":
            return ("anchored_x", "anchored_y", "width", "height", "rotation", "scale_x", "scale_y")
        return None

    def _apply_transform_properties_to_edit_world(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: str,
        properties: Dict[str, Any],
    ) -> None:
        if entry.edit_world is None:
            return
        entity = entry.edit_world.get_entity_by_name(entity_name)
        if entity is None:
            return
        transform = entity.get_component(Transform)
        if transform is None:
            return
        field_to_attribute = {
            "x": "local_x",
            "y": "local_y",
            "rotation": "local_rotation",
            "scale_x": "local_scale_x",
            "scale_y": "local_scale_y",
        }
        changed = False
        for field_name, value in properties.items():
            attribute = field_to_attribute.get(field_name)
            if attribute is None:
                continue
            next_value = float(value)
            if getattr(transform, attribute) == next_value:
                continue
            setattr(transform, attribute, next_value)
            changed = True
        if changed:
            entry.edit_world.touch_transform()

    def _apply_component_properties_to_edit_world(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: str,
        component_name: str,
        properties: Dict[str, Any],
    ) -> None:
        if component_name == "Transform":
            self._apply_transform_properties_to_edit_world(entry, entity_name, properties)
            return
        if entry.edit_world is None:
            return
        entity = entry.edit_world.get_entity_by_name(entity_name)
        if entity is None:
            return
        component = entity.get_component(RectTransform) if component_name == "RectTransform" else None
        if component is None:
            return
        editable_fields = {"anchored_x", "anchored_y", "width", "height", "rotation", "scale_x", "scale_y"}
        changed = False
        for field_name, value in properties.items():
            if field_name not in editable_fields or not hasattr(component, field_name):
                continue
            next_value = float(value)
            if getattr(component, field_name) == next_value:
                continue
            setattr(component, field_name, next_value)
            changed = True
        if changed:
            entry.edit_world.touch_ui_layout()

    def _sync_entry_from_edit_world(self, entry: SceneWorkspaceEntry) -> bool:
        if entry.is_playing or entry.edit_world is None:
            return False
        entry.selected_entity_name = entry.edit_world.selected_entity_name
        entry.selected_entity_id = self._entity_id_for_name(entry, entry.selected_entity_name)
        data = self._build_canonical_scene_payload(entry)
        self._install_scene_payload(entry, data)
        self._sync_feature_metadata_from_scene_links(entry)
        if entry.edit_world is not None:
            entry.edit_world_version = entry.edit_world.version
        self._clear_pending_edit_world_sync(entry)
        return True

    def _commit_serializable_scene_mutation(
        self,
        entry: SceneWorkspaceEntry,
        snapshot: _SerializableMutationSnapshot,
        *,
        failure_context: str,
    ) -> bool:
        try:
            self._install_scene_payload(entry, entry.scene.to_dict())
            return True
        except ValueError as exc:
            self._restore_serializable_mutation(entry, snapshot)
            log_err(f"SceneManager: rejected invalid serializable mutation during {failure_context}: {exc}")
            return False

    def _capture_serializable_mutation(self, entry: SceneWorkspaceEntry) -> _SerializableMutationSnapshot:
        return _SerializableMutationSnapshot(
            scene_data=copy.deepcopy(entry.scene.to_dict()),
            selected_entity_name=entry.selected_entity_name,
            selected_entity_id=entry.selected_entity_id,
            dirty=entry.dirty,
            pending_edit_world_sync_reason=entry.pending_edit_world_sync_reason,
        )

    def _restore_serializable_mutation(
        self,
        entry: SceneWorkspaceEntry,
        snapshot: _SerializableMutationSnapshot,
    ) -> None:
        self._restore_entry_scene(entry, snapshot.scene_data)
        entry.selected_entity_name = snapshot.selected_entity_name
        entry.selected_entity_id = snapshot.selected_entity_id
        if entry.edit_world is not None:
            entry.edit_world.selected_entity_name = snapshot.selected_entity_name
        entry.dirty = snapshot.dirty
        entry.pending_edit_world_sync_reason = snapshot.pending_edit_world_sync_reason

    def _apply_authoring_component_state(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: str,
        component_name: str,
        component_state: Dict[str, Any],
        *,
        editable_fields: tuple[str, ...],
        record_history: bool,
        label: str,
    ) -> bool:
        if entry.is_playing:
            return False
        current_state = self._load_authoring_component_state(entry, entity_name, component_name)
        if current_state is None:
            return False
        updated_state = copy.deepcopy(current_state)
        for field_name in editable_fields:
            if field_name not in component_state:
                continue
            updated_state[field_name] = float(component_state[field_name])
        snapshot = self._capture_serializable_mutation(entry)
        before = snapshot.scene_data
        entry.selected_entity_name = entity_name
        entry.selected_entity_id = self._entity_id_for_name(entry, entity_name)
        if not entry.scene.replace_component_data(entity_name, component_name, updated_state):
            if not self._structural_authoring.replace_prefab_component_override(entry, entity_name, component_name, updated_state):
                return False
        if not self._commit_serializable_scene_mutation(
            entry,
            snapshot,
            failure_context=label,
        ):
            return False
        entry.dirty = True
        entry.edit_world_sync_pending = False
        if record_history and before is not None:
            self._record_scene_change(entry, label, before)
        return True

    def _load_authoring_component_state(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: str,
        component_name: str,
    ) -> Optional[Dict[str, Any]]:
        entity_data = entry.scene.find_entity(entity_name)
        if entity_data is not None:
            component_data = entity_data.get("components", {}).get(component_name)
            if isinstance(component_data, dict):
                return copy.deepcopy(component_data)
        if entry.edit_world is None:
            return None
        entity = entry.edit_world.get_entity_by_name(entity_name)
        if entity is None:
            return None
        component: Any
        if component_name == "Transform":
            component = entity.get_component(Transform)
        elif component_name == "RectTransform":
            component = entity.get_component(RectTransform)
        else:
            component = None
        if component is None or not hasattr(component, "to_dict"):
            return None
        component_data = component.to_dict()
        return copy.deepcopy(component_data) if isinstance(component_data, dict) else None

    def _record_scene_change(self, entry: SceneWorkspaceEntry, label: str, before: Dict[str, Any]) -> None:
        self._change_history.record_scene_change(entry, label, before)

    def _restore_scene_data_for_key(self, key: str, data: Dict[str, Any]) -> bool:
        return self._change_history.restore_scene_data_for_key(key, data)

    def _remove_entity_subtree(self, entry: SceneWorkspaceEntry, entity_name: str) -> bool:
        return self._structural_authoring.remove_entity_subtree(entry, entity_name)

    def _compute_world_transform_from_scene_data(
        self, entry: SceneWorkspaceEntry, entity_name: str
    ) -> Optional[tuple[float, float, float, float, float]]:
        return self._structural_authoring.compute_world_transform_from_scene_data(entry, entity_name)

    def _remove_single_entity(self, entry: SceneWorkspaceEntry, entity_name: str) -> bool:
        return self._structural_authoring.remove_single_entity(entry, entity_name)

    def _validate_parent(self, entry: SceneWorkspaceEntry, entity_name: str, parent_name: str) -> bool:
        return self._structural_authoring.validate_parent(entry, entity_name, parent_name)

    def _update_prefab_component_override(self, entry: SceneWorkspaceEntry, entity_name: str, component_name: str, property_name: str, value: Any) -> bool:
        return self._structural_authoring.update_prefab_component_override(entry, entity_name, component_name, property_name, value)

    def _update_prefab_entity_override(self, entry: SceneWorkspaceEntry, entity_name: str, property_name: str, value: Any) -> bool:
        return self._structural_authoring.update_prefab_entity_override(entry, entity_name, property_name, value)

    def _replace_prefab_component_override(self, entry: SceneWorkspaceEntry, entity_name: str, component_name: str, component_data: Dict[str, Any]) -> bool:
        return self._structural_authoring.replace_prefab_component_override(entry, entity_name, component_name, component_data)

    def _remove_prefab_component_override(self, entry: SceneWorkspaceEntry, entity_name: str, component_name: str) -> bool:
        return self._structural_authoring.remove_prefab_component_override(entry, entity_name, component_name)

    def _ensure_prefab_override_ops(self, root_scene_data: Dict[str, Any]) -> Dict[str, Any]:
        return self._structural_authoring.ensure_prefab_override_ops(root_scene_data)

    def _upsert_prefab_override_operation(
        self,
        overrides: Dict[str, Any],
        operation: Dict[str, Any],
        *,
        match_keys: tuple[str, ...],
    ) -> None:
        self._structural_authoring.upsert_prefab_override_operation(overrides, operation, match_keys=match_keys)

    def _remove_prefab_override_operations(
        self,
        overrides: Dict[str, Any],
        *,
        target: str,
        component: str | None = None,
    ) -> None:
        self._structural_authoring.remove_prefab_override_operations(overrides, target=target, component=component)

    def _sync_feature_metadata_from_scene_links(self, entry: SceneWorkspaceEntry) -> None:
        scene_flow = self.get_scene_flow() if entry.key == self._active_scene_key else {}
        if entry.key != self._active_scene_key:
            metadata = entry.scene.feature_metadata.get("scene_flow", {})
            if isinstance(metadata, dict):
                scene_flow = {str(key): str(value) for key, value in metadata.items() if str(key).strip() and str(value).strip()}
            for entity_data in entry.scene.entities_data:
                scene_link = entity_data.get("components", {}).get("SceneLink")
                if isinstance(scene_link, dict):
                    flow_key = str(scene_link.get("flow_key", "") or "").strip()
                    target_path = str(scene_link.get("target_path", "") or "").strip()
                    if flow_key:
                        if target_path:
                            scene_flow[flow_key] = target_path
                        else:
                            scene_flow.pop(flow_key, None)
        if scene_flow:
            entry.scene.feature_metadata["scene_flow"] = scene_flow
        else:
            entry.scene.feature_metadata.pop("scene_flow", None)
        if entry.edit_world is not None:
            entry.edit_world.feature_metadata["scene_flow"] = copy.deepcopy(scene_flow)

    def _sync_scene_links_from_feature_metadata(self, entry: SceneWorkspaceEntry) -> None:
        scene_flow = entry.scene.feature_metadata.get("scene_flow", {})
        if not isinstance(scene_flow, dict):
            return
        for entity_data in entry.scene.entities_data:
            scene_link = entity_data.get("components", {}).get("SceneLink")
            if isinstance(scene_link, dict):
                flow_key = str(scene_link.get("flow_key", "") or "").strip()
                if flow_key and "target_path" not in scene_link:
                    scene_link["target_path"] = str(scene_flow.get(flow_key, "") or "")

    def _entry_has_invalid_links(self, entry: SceneWorkspaceEntry) -> bool:
        for entity_data in entry.scene.entities_data:
            scene_link = entity_data.get("components", {}).get("SceneLink")
            if isinstance(scene_link, dict) and not str(scene_link.get("target_path", "") or "").strip():
                return True
        return False

    def _entity_has_scene_link(self, entity_data: Dict[str, Any]) -> bool:
        return "SceneLink" in entity_data.get("components", {})

    def _unique_entity_name(self, existing_names: set[str], base_name: str) -> str:
        candidate = base_name
        suffix = 1
        while candidate in existing_names:
            candidate = f"{base_name}_{suffix}"
            suffix += 1
        return candidate
