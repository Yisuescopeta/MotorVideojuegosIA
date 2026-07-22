from __future__ import annotations

import copy
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

from engine.authoring.changes import Change
from engine.core.runtime_logging import log_err, log_warn
from engine.scenes.change_history import SceneChangeCoordinator
from engine.scenes.contracts import (
    SceneAuthoringPort,
    SceneManagerAuthoringAdapter,
    SceneManagerRuntimeAdapter,
    SceneManagerWorkspaceAdapter,
    SceneRuntimePort,
    SceneWorkspacePort,
)
from engine.scenes.edit_sync import (
    LEGACY_AUTHORING_SYNC_REASON,
    SceneEditSyncCoordinator,
)
from engine.scenes.edit_sync import (
    TRANSIENT_PREVIEW_SYNC_REASON as TRANSIENT_PREVIEW_SYNC_REASON,
)
from engine.scenes.incremental_authoring import SceneIncrementalAuthoring
from engine.scenes.legacy_world_authoring_adapter import LegacyWorldAuthoringAdapter
from engine.scenes.prefab_overrides import PrefabOverrideService
from engine.scenes.post_commit import ScenePostCommitEventPublisher
from engine.scenes.projection_integrity import ProjectionIntegrityAction
from engine.scenes.scene import Scene
from engine.scenes.scene_flow import SceneFlowPolicy
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
from engine.scenes.scene_projection import SceneProjectionService
from engine.scenes.serializable_authoring import SceneSerializableAuthoring
from engine.scenes.serializable_mutation import SerializableMutationCoordinator
from engine.scenes.storage import SceneStorage
from engine.scenes.structural_authoring import SceneStructuralAuthoring
from engine.scenes.workspace_lifecycle import SceneWorkspace, SceneWorkspaceEntry

if TYPE_CHECKING:
    from engine.ecs.world import World
    from engine.levels.component_registry import ComponentRegistry

COMPACT_SCENE_SAVE_ENTITY_THRESHOLD = _COMPACT_SCENE_SAVE_ENTITY_THRESHOLD
COMPACT_SCENE_SAVE_SEPARATORS = _COMPACT_SCENE_SAVE_SEPARATORS


class SceneManager:
    def __init__(self, registry: "ComponentRegistry") -> None:
        self._registry = registry
        self._flow_policy = SceneFlowPolicy()
        self._projection = SceneProjectionService(registry)
        self._workspace = SceneWorkspace(
            projection=self._projection,
            flow_policy=self._flow_policy,
        )
        self._edit_sync = SceneEditSyncCoordinator(self._workspace, self._projection)
        self._legacy_world_authoring = LegacyWorldAuthoringAdapter(self._edit_sync)
        self._serializable_mutations = SerializableMutationCoordinator(
            self._workspace,
            self._projection,
            self._edit_sync,
        )
        self._post_commit_events = ScenePostCommitEventPublisher()
        self._persistence = ScenePersistenceService()
        self._change_history = SceneChangeCoordinator()
        self._incremental_authoring = SceneIncrementalAuthoring(
            self._workspace,
            self._edit_sync,
            self._change_history,
        )
        self._prefab_overrides = PrefabOverrideService()
        self._serializable_authoring = SceneSerializableAuthoring(
            self._workspace,
            self._edit_sync,
            self._serializable_mutations,
            self._projection,
            self._change_history,
            self._prefab_overrides,
            self._flow_policy,
            self._registry,
            self._post_commit_events,
        )
        self._structural_authoring = SceneStructuralAuthoring(
            self._workspace,
            self._serializable_authoring.transaction_pipeline,
            self._serializable_authoring.entity_authoring,
            self._prefab_overrides,
        )
        self._runtime_port: SceneRuntimePort = SceneManagerRuntimeAdapter(self)
        self._authoring_port: SceneAuthoringPort = SceneManagerAuthoringAdapter(self)
        self._workspace_port: SceneWorkspacePort = SceneManagerWorkspaceAdapter(self)
        self._runtime_signal_compiler: Optional[Callable[[Scene, "World"], int]] = None
        self._on_scene_saved_callbacks: list[Callable[[str, Dict[str, Any]], None]] = []
        self._scene_file_mtimes: dict[str, float] = {}

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

    @property
    def post_commit_events(self) -> ScenePostCommitEventPublisher:
        """Editor post-commit notifications; never a mutation authority."""
        return self._post_commit_events

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
        resolved_source = self._workspace.normalize_path_reference(raw_source)
        mtime_key = self._mtime_key(resolved_source)
        try:
            current_mtime = self._persistence.get_mtime(resolved_source)
        except OSError:
            return entry.edit_world
        if current_mtime is None:
            return entry.edit_world
        previous_mtime = self._scene_file_mtimes.get(mtime_key)
        if previous_mtime is not None and current_mtime <= previous_mtime:
            return entry.edit_world
        try:
            loaded = self._persistence.load(resolved_source)
        except Exception as exc:
            log_err(f"SceneManager: failed to reload stale scene from {resolved_source}: {exc}")
            return entry.edit_world
        try:
            if not self._edit_sync.inspect_integrity(
                entry,
                action=ProjectionIntegrityAction.RELOAD,
            ).allowed:
                log_warn(
                    f"SceneManager: skipped stale reload for '{entry.key}' due to projection divergence"
                )
                return entry.edit_world
            self._workspace.replace_entry_scene(entry, loaded.payload, source_path=resolved_source)
            self._edit_sync.clear_pending(entry)
            self._workspace.clear_dirty(entry)
            self._scene_file_mtimes[mtime_key] = current_mtime
        except Exception as exc:
            log_err(f"SceneManager: failed to install refreshed scene payload from {resolved_source}: {exc}")
        return entry.edit_world

    def list_open_scenes(self) -> list[Dict[str, Any]]:
        return self._workspace.list_open_scenes()

    def get_feature_metadata(self) -> Dict[str, Any]:
        return self._serializable_authoring.get_feature_metadata()

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
        return self._serializable_authoring.get_component_data(
            entity_name,
            component_name,
        )

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
        entry = (
            self.ensure_scene_open(str(scene_ref or ""), activate=False)
            if scene_ref not in (None, "")
            else self._get_active_entry()
        )
        if entry is None:
            return None
        return self._serializable_authoring.find_entity_data_for_entry(
            entry,
            entity_name,
        )

    def get_component_data_for_scene(
        self,
        scene_ref: str | None,
        entity_name: str,
        component_name: str,
    ) -> Optional[Dict[str, Any]]:
        entry = (
            self.ensure_scene_open(str(scene_ref or ""), activate=False)
            if scene_ref not in (None, "")
            else self._get_active_entry()
        )
        if entry is None:
            return None
        return self._serializable_authoring.get_component_data_for_entry(
            entry,
            entity_name,
            component_name,
        )

    def list_scene_entities(self, scene_ref: str | None = None) -> list[Dict[str, Any]]:
        entry = (
            self.ensure_scene_open(str(scene_ref or ""), activate=False)
            if scene_ref not in (None, "")
            else self._get_active_entry()
        )
        if entry is None:
            return []
        return self._serializable_authoring.list_scene_entities(entry)

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
        if entry is None:
            return False
        return self._serializable_authoring.upsert_component_for_scene(
            entry,
            entity_name,
            component_name,
            component_data,
            record_history=record_history,
        )

    def remove_component_for_scene(
        self,
        scene_ref: str,
        entity_name: str,
        component_name: str,
        *,
        record_history: bool = True,
    ) -> bool:
        entry = self.ensure_scene_open(scene_ref, activate=False)
        if entry is None:
            return False
        return self._serializable_authoring.remove_component_for_scene(
            entry,
            entity_name,
            component_name,
            record_history=record_history,
        )

    def get_scene_view_state(self, key: Optional[str] = None) -> Dict[str, Any]:
        return self._workspace.get_scene_view_state(key)

    def set_scene_view_state(self, key: str, view_state: Dict[str, Any]) -> bool:
        return self._workspace.set_scene_view_state(key, view_state)

    def get_workspace_state(self) -> Dict[str, Any]:
        return self._workspace.get_workspace_state()

    def activate_scene(self, key_or_path: str) -> Optional["World"]:
        target = self._workspace.resolve_entry(key_or_path)
        active = self._get_active_entry()
        if target is None:
            return None
        if active is not None and active.key != target.key:
            if not self._edit_sync.prepare_for_save(
                active,
                failure_context="activate_scene",
                action=ProjectionIntegrityAction.LIFECYCLE,
            ):
                return None
        return self._workspace.activate_scene(key_or_path)

    def close_scene(self, key_or_path: str, discard_changes: bool = False) -> bool:
        entry = self._workspace.resolve_entry(key_or_path)
        if entry is None:
            return False
        if not self._edit_sync.prepare_for_save(
            entry,
            failure_context="close_scene",
            action=ProjectionIntegrityAction.LIFECYCLE,
        ):
            return False
        return self._workspace.close_scene(key_or_path, discard_changes=discard_changes)

    def reset_workspace(self) -> None:
        self._workspace.reset_workspace()
        self._structural_authoring.reset_state()

    def load_scene(self, data: Dict[str, Any], source_path: Optional[str] = None, activate: bool = True) -> "World":
        world = self._workspace.load_scene(data, source_path=source_path, activate=activate)
        if world is not None and source_path:
            try:
                resolved_path = self._workspace.normalize_path_reference(source_path)
                mtime = self._persistence.get_mtime(resolved_path)
                if mtime is not None:
                    self._scene_file_mtimes[self._mtime_key(resolved_path)] = mtime
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
        workspace_path = self._workspace.normalize_path_reference(str(resolved_path))
        mtime_key = self._mtime_key(resolved_path)
        existing = self._workspace.resolve_entry(workspace_path)
        if existing is not None:
            if activate:
                return self.activate_scene(existing.key)
            return existing.edit_world
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
            self._scene_file_mtimes[mtime_key] = loaded.mtime
        return world

    def get_edit_world(self) -> Optional["World"]:
        self.refresh_active_scene_if_stale()
        entry = self._get_active_entry()
        return entry.edit_world if entry is not None else None

    def create_new_scene(self, name: str = "New Scene", activate: bool = True) -> "World":
        return self._workspace.create_new_scene(name, activate=activate)

    def enter_play(self) -> Optional["World"]:
        entry = self._get_active_entry()
        if entry is None or not self._edit_sync.prepare_for_save(
            entry,
            failure_context="enter_play",
            action=ProjectionIntegrityAction.PLAY,
        ):
            return None
        runtime_world = self._workspace.enter_play()
        entry = self._get_active_entry()
        if runtime_world is None or entry is None:
            return runtime_world
        self._compile_runtime_signals_for_entry(entry, runtime_world)
        return runtime_world

    def exit_play(self) -> Optional["World"]:
        entry = self._get_active_entry()
        edit_world = self._workspace.exit_play()
        if entry is not None:
            self._edit_sync.clear_pending(entry)
        return edit_world

    def restore_world(self, world: "World") -> None:
        self._workspace.restore_world(world)

    def reload_scene(self) -> Optional["World"]:
        entry = self._get_active_entry()
        if entry is None or not self._edit_sync.prepare_for_save(
            entry,
            failure_context="reload_scene",
            action=ProjectionIntegrityAction.RELOAD,
        ):
            return None
        edit_world = self._workspace.reload_scene()
        if entry is not None:
            self._edit_sync.clear_pending(entry)
        return edit_world

    def apply_edit_to_world(self, entity_name: str, component_name: str, property_name: str, value: Any) -> bool:
        entry = self._get_active_entry()
        if entry is None or entry.is_playing or entry.edit_world is None:
            return False
        if self._incremental_authoring.supports(component_name, property_name):
            apply_state = (
                self.apply_transform_state if component_name == "Transform" else self.apply_rect_transform_state
            )
            return apply_state(
                entity_name,
                {property_name: value},
                entry.key,
                record_history=True,
                label=f"{entity_name}.{component_name}.{property_name}",
            )
        return self._serializable_authoring.apply_edit_to_world(
            entity_name,
            component_name,
            property_name,
            value,
        )

    def update_entity_property(self, entity_name: str, property_name: str, value: Any) -> bool:
        entry = self._get_active_entry()
        if entry is None:
            return False
        if (
            property_name == "parent"
            and value is not None
            and not self._structural_authoring.validate_parent(entry, entity_name, value)
        ):
            return False
        return self._serializable_authoring.update_entity_property(
            entity_name,
            property_name,
            value,
        )

    def set_entity_groups(self, entity_name: str, groups: list[str]) -> bool:
        return self._serializable_authoring.set_entity_groups(entity_name, groups)

    def replace_component_data(self, entity_name: str, component_name: str, component_data: Dict[str, Any]) -> bool:
        return self._serializable_authoring.replace_component_data(
            entity_name,
            component_name,
            component_data,
        )

    def get_component_metadata(self, entity_name: str, component_name: str) -> Dict[str, Any]:
        return self._serializable_authoring.get_component_metadata(
            entity_name,
            component_name,
        )

    def set_component_metadata(self, entity_name: str, component_name: str, metadata: Dict[str, Any]) -> bool:
        return self._serializable_authoring.set_component_metadata(
            entity_name,
            component_name,
            metadata,
        )

    def create_entity(self, name: str, components: Optional[Dict[str, Dict[str, Any]]] = None) -> bool:
        return self._serializable_authoring.create_entity(name, components)

    def create_entity_from_data(self, entity_data: Dict[str, Any]) -> bool:
        return self._serializable_authoring.create_entity_from_data(entity_data)

    def remove_entity(self, entity_name: str) -> bool:
        return self._structural_authoring.remove_entity(entity_name)

    def add_component_to_entity(
        self, entity_name: str, component_name: str, component_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        return self._serializable_authoring.add_component_to_entity(
            entity_name,
            component_name,
            component_data,
        )

    def remove_component_from_entity(self, entity_name: str, component_name: str) -> bool:
        return self._serializable_authoring.remove_component_from_entity(
            entity_name,
            component_name,
        )

    def set_component_enabled(self, entity_name: str, component_name: str, enabled: bool) -> bool:
        return self._serializable_authoring.set_component_enabled(
            entity_name,
            component_name,
            enabled,
        )

    def find_entity_data(self, entity_name: str) -> Optional[Dict[str, Any]]:
        return self._serializable_authoring.find_entity_data(entity_name)

    def find_entity_data_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        return self._serializable_authoring.find_entity_data_by_id(entity_id)

    def update_entity_property_by_id(self, entity_id: str, property_name: str, value: Any) -> bool:
        entry = self._get_active_entry()
        if entry is None:
            return False
        if property_name == "parent" and value is not None:
            entity_data = self._serializable_authoring.find_entity_data_by_id(entity_id)
            entity_name = entity_data.get("name") if isinstance(entity_data, dict) else None
            if not isinstance(entity_name, str) or not self._structural_authoring.validate_parent(
                entry,
                entity_name,
                value,
            ):
                return False
        return self._serializable_authoring.update_entity_property_by_id(
            entity_id,
            property_name,
            value,
        )

    def apply_edit_to_world_by_id(self, entity_id: str, component_name: str, property_name: str, value: Any) -> bool:
        return self._serializable_authoring.apply_edit_to_world_by_id(
            entity_id,
            component_name,
            property_name,
            value,
        )

    def replace_component_data_by_id(self, entity_id: str, component_name: str, component_data: Dict[str, Any]) -> bool:
        return self._serializable_authoring.replace_component_data_by_id(
            entity_id,
            component_name,
            component_data,
        )

    def add_component_to_entity_by_id(
        self,
        entity_id: str,
        component_name: str,
        component_data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        return self._serializable_authoring.add_component_to_entity_by_id(
            entity_id,
            component_name,
            component_data,
        )

    def remove_component_from_entity_by_id(self, entity_id: str, component_name: str) -> bool:
        return self._serializable_authoring.remove_component_from_entity_by_id(
            entity_id,
            component_name,
        )

    def remove_entity_by_id(self, entity_id: str) -> bool:
        entity_data = self.find_entity_data_by_id(entity_id)
        entity_name = entity_data.get("name") if isinstance(entity_data, dict) else None
        return self.remove_entity(entity_name) if isinstance(entity_name, str) else False

    def sync_from_edit_world(self) -> bool:
        """Deprecated: use EngineAPI or SceneManager public methods instead.

        Legacy method that syncs pending changes from edit_world back to the serialized scene.
        Prefer authoring through SceneManager structural authoring methods or EngineAPI delegates.
        """
        warnings.warn(
            "sync_from_edit_world() is deprecated. Use EngineAPI or SceneManager public methods instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._legacy_world_authoring.sync_pending()

    def mark_edit_world_dirty(self, reason: str = LEGACY_AUTHORING_SYNC_REASON) -> bool:
        if reason == TRANSIENT_PREVIEW_SYNC_REASON:
            return self._edit_sync.mark_edit_world_dirty(reason=reason)
        return self._legacy_world_authoring.mark_dirty(reason=reason)

    def set_feature_metadata(self, key: str, value: Any) -> bool:
        return self._serializable_authoring.set_feature_metadata(key, value)

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
        if self._incremental_authoring.apply_state(
            entry,
            entity_name,
            "Transform",
            transform_state,
            record_history=record_history,
            label=label or f"transform:{entity_name}",
        ):
            return True
        return self._serializable_authoring.apply_authoring_component_state(
            entry,
            entity_name,
            "Transform",
            transform_state,
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
        if self._incremental_authoring.apply_state(
            entry,
            entity_name,
            "RectTransform",
            rect_state,
            record_history=record_history,
            label=label or f"rect_transform:{entity_name}",
        ):
            return True
        return self._serializable_authoring.apply_authoring_component_state(
            entry,
            entity_name,
            "RectTransform",
            rect_state,
            record_history=record_history,
            label=label or f"rect_transform:{entity_name}",
        )

    def set_selected_entity(self, entity_name: Optional[str]) -> bool:
        entry = self._get_active_entry()
        if entry is None:
            return False
        return self._workspace.select_entity(entry, entity_name=entity_name)

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
            if not self._edit_sync.prepare_for_save(
                entry,
                failure_context=f"save_scene:{Path(path).name}",
            ):
                return False
            data = self._projection.validate_payload(self._flow_policy.prepare_payload(entry.scene.to_dict()))
            saved = self._persistence.save(
                path,
                data,
                compact_save=compact_save,
                storage=storage,
            )
            self._workspace.replace_entry_scene(entry, saved.payload, source_path=path)
            self._workspace.rekey_entry(entry, self._workspace.build_scene_key(path, entry.scene.name))
            self._workspace.clear_dirty(entry)
            self._edit_sync.clear_pending(entry)
            if saved.mtime is not None:
                self._scene_file_mtimes[self._mtime_key(saved.resolved_path)] = saved.mtime
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
        return self._serializable_mutations.restore_scene_data(
            self._workspace.active_scene_key,
            data,
        )

    def set_entity_parent(self, entity_name: str, parent_name: Optional[str]) -> bool:
        """Reparent an entity, preserving its world-space transform."""
        return self._structural_authoring.set_entity_parent(entity_name, parent_name)

    def create_child_entity(
        self, parent_name: str, name: str, components: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> bool:
        """Create a new entity as a child. The provided component coords are local (no world-position preservation)."""
        return self._structural_authoring.create_child_entity(parent_name, name, components)

    def instantiate_prefab(
        self,
        name: str,
        prefab_path: str,
        parent: Optional[str] = None,
        overrides: Optional[Dict[str, Any]] = None,
        root_name: Optional[str] = None,
    ) -> bool:
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
            self._workspace.clear_dirty(entry)

    def clear_all_dirty(self) -> None:
        for entry in self._workspace.entries.values():
            self._workspace.clear_dirty(entry)

    def begin_transaction(self, label: str = "transaction", key: Optional[str] = None) -> bool:
        if self._change_history.has_active_transaction:
            return False
        entry = self._resolve_entry(key)
        if entry is None or entry.is_playing:
            return False
        before = self._serializable_mutations.snapshot_entry_scene_data(entry)
        return self._change_history.begin_transaction(
            label=label,
            scene_key=entry.key,
            before=before,
        )

    def apply_change(self, change: Change | dict[str, Any], key: Optional[str] = None) -> bool:
        _ = key
        payload = change if isinstance(change, Change) else Change.from_dict(change)
        metadata = copy.deepcopy(payload.to_dict())
        if payload.kind == "edit_component":
            success = self.apply_edit_to_world(
                payload.entity,
                payload.component,
                payload.field,
                payload.value,
            )
        elif payload.kind == "set_entity_property":
            success = self.update_entity_property(
                payload.entity,
                payload.field,
                payload.value,
            )
        elif payload.kind == "add_component":
            success = self.add_component_to_entity(
                payload.entity,
                payload.component,
                component_data=payload.data,
            )
        elif payload.kind == "remove_component":
            success = self.remove_component_from_entity(
                payload.entity,
                payload.component,
            )
        elif payload.kind == "create_entity":
            components = payload.data.get("components") if isinstance(payload.data, dict) else None
            success = self.create_entity(payload.entity, components)
        elif payload.kind == "delete_entity":
            success = self.remove_entity(payload.entity)
        else:
            return False
        if success and self._change_history.has_active_transaction:
            self._change_history.append_transaction_change(metadata)
        return success

    def commit_transaction(self) -> Optional[Dict[str, Any]]:
        key = self._change_history.active_transaction_scene_key
        if key is None:
            return None
        entry = self._resolve_entry(key)
        if entry is None:
            self._change_history.discard_transaction()
            return None
        after = self._serializable_mutations.snapshot_entry_scene_data(entry)
        return self._change_history.commit_transaction(
            after,
            self._serializable_mutations.restore_scene_data,
        )

    def rollback_transaction(self) -> bool:
        return self._change_history.rollback_transaction(
            self._serializable_mutations.restore_scene_data,
        )

    def begin_authoring_transaction(self, label: str, key_or_path: Optional[str] = None) -> bool:
        entry = self._resolve_entry(key_or_path)
        return entry is not None and self._incremental_authoring.begin_transaction(entry, label)

    def update_authoring_transaction(
        self,
        entity_name: str,
        component_name: str,
        component_state: Dict[str, Any],
        key_or_path: Optional[str] = None,
    ) -> bool:
        entry = self._resolve_entry(key_or_path)
        return entry is not None and self._incremental_authoring.update_transaction(
            entry,
            entity_name,
            component_name,
            component_state,
        )

    def commit_authoring_transaction(self) -> Optional[Dict[str, Any]]:
        return self._incremental_authoring.commit_transaction()

    def cancel_authoring_transaction(self) -> bool:
        return self._incremental_authoring.cancel_transaction()

    def get_scene_flow(self) -> Dict[str, str]:
        entry = self._get_active_entry()
        return self._flow_policy.get_effective_flow(entry.scene) if entry is not None else {}

    def set_scene_flow_target(self, key: str, target_path: str) -> bool:
        return self._serializable_authoring.set_scene_flow_target(key, target_path)

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

    def projection_integrity_allows(
        self,
        key_or_path: Optional[str] = None,
        *,
        action: ProjectionIntegrityAction = ProjectionIntegrityAction.EXPORT,
    ) -> bool:
        """Check an open scene without promoting EditWorld data to Scene."""
        entry = self._resolve_entry(key_or_path)
        if entry is None:
            return True
        return self._edit_sync.inspect_integrity(entry, action=action).allowed

    @staticmethod
    def _mtime_key(path: str | Path) -> str:
        return str(Path(path).resolve())
