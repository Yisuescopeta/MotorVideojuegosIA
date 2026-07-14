from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from engine.core.runtime_logging import log_err, log_info, log_warn
from engine.scenes.scene import Scene
from engine.scenes.scene_flow import SceneFlowPolicy
from engine.scenes.scene_projection import SceneProjectionService

if TYPE_CHECKING:
    from engine.ecs.world import World


@dataclass
class SceneWorkspaceEntry:
    key: str
    scene: Scene
    edit_world: Optional["World"] = None
    runtime_world: Optional["World"] = None
    is_playing: bool = False
    selected_entity_name: Optional[str] = None
    selected_entity_id: Optional[str] = None
    dirty: bool = False
    pending_edit_world_sync_reason: Optional[str] = None
    dirty_before_pending_edit_world_sync: Optional[bool] = None
    edit_world_version: int = 0
    view_state: dict[str, Any] = field(default_factory=dict)

    @property
    def source_path(self) -> str:
        return str(self.scene.source_path or "")

    @property
    def active_world(self) -> Optional["World"]:
        return self.runtime_world if self.is_playing else self.edit_world

    @property
    def edit_world_sync_pending(self) -> bool:
        return self.pending_edit_world_sync_reason is not None


@dataclass(frozen=True)
class SceneSelectionSnapshot:
    entity_name: Optional[str]
    entity_id: Optional[str]


class SceneWorkspace:
    """Owns workspace scene entries and edit/play lifecycle transitions."""

    def __init__(
        self,
        *,
        projection: SceneProjectionService,
        flow_policy: SceneFlowPolicy,
    ) -> None:
        self.entries: dict[str, SceneWorkspaceEntry] = {}
        self.active_scene_key: str = ""
        self._projection = projection
        self._flow_policy = flow_policy
        self._untitled_counter = 1

    def get_active_entry(self) -> Optional[SceneWorkspaceEntry]:
        return self.entries.get(self.active_scene_key) if self.active_scene_key else None

    def resolve_entry(self, key_or_path: Optional[str]) -> Optional[SceneWorkspaceEntry]:
        if key_or_path in (None, ""):
            return self.get_active_entry()
        if key_or_path in self.entries:
            return self.entries[str(key_or_path)]
        key_text = str(key_or_path)
        normalized = (
            self.normalize_path_reference(key_text)
            if key_text.endswith(".json") or "/" in key_text or "\\" in key_text
            else key_text
        )
        if normalized in self.entries:
            return self.entries[normalized]
        for entry in self.entries.values():
            if entry.source_path and self.normalize_path_reference(entry.source_path) == normalized:
                return entry
        return None

    def list_open_scenes(self) -> list[dict[str, Any]]:
        return [
            {
                "key": entry.key,
                "name": entry.scene.name,
                "path": entry.source_path,
                "dirty": entry.dirty,
                "is_active": entry.key == self.active_scene_key,
                "has_invalid_links": self._flow_policy.has_invalid_links(entry.scene),
            }
            for entry in self.entries.values()
        ]

    def get_scene_view_state(self, key: Optional[str] = None) -> dict[str, Any]:
        entry = self.resolve_entry(key)
        return copy.deepcopy(entry.view_state) if entry is not None else {}

    def set_scene_view_state(self, key: str, view_state: dict[str, Any]) -> bool:
        entry = self.resolve_entry(key)
        if entry is None:
            return False
        entry.view_state = copy.deepcopy(view_state)
        return True

    def get_workspace_state(self) -> dict[str, Any]:
        return {
            "open_scenes": [self._entry_path_or_key(entry) for entry in self.entries.values()],
            "active_scene": self._entry_path_or_key(self.get_active_entry()),
            "scene_view_states": {
                self._entry_path_or_key(entry): copy.deepcopy(entry.view_state)
                for entry in self.entries.values()
                if entry.view_state
            },
        }

    def activate_scene(self, key_or_path: str) -> Optional["World"]:
        entry = self.resolve_entry(key_or_path)
        active = self.get_active_entry()
        if entry is None:
            return None
        if active is not None and active.key != entry.key and active.is_playing:
            return None
        self.active_scene_key = entry.key
        if entry.edit_world is None:
            self.rebuild_edit_world(entry)
        return entry.active_world

    def close_scene(self, key_or_path: str, discard_changes: bool = False) -> bool:
        entry = self.resolve_entry(key_or_path)
        if entry is None or (entry.dirty and not discard_changes):
            return False
        was_active = entry.key == self.active_scene_key
        del self.entries[entry.key]
        if not self.entries:
            self.active_scene_key = ""
            return True
        if was_active:
            self.active_scene_key = next(iter(self.entries.keys()))
        return True

    def reset_workspace(self) -> None:
        self.entries.clear()
        self.active_scene_key = ""

    def load_scene(
        self,
        data: dict[str, Any],
        source_path: Optional[str] = None,
        activate: bool = True,
    ) -> "World":
        normalized_source_path = self.normalize_path_reference(source_path) if source_path else None
        prepared = self._flow_policy.prepare_payload(data)
        scene = self._projection.create_scene(prepared, source_path=normalized_source_path)
        key = self.build_scene_key(normalized_source_path, scene.name)
        entry = SceneWorkspaceEntry(
            key=key,
            scene=scene,
        )
        self._flow_policy.sync_links_from_metadata(entry.scene)
        world = self._projection.create_world(entry.scene)
        self.install_entry_state(entry, entry.scene, world)
        self.entries[key] = entry
        if activate or not self.active_scene_key:
            self.active_scene_key = key
        log_info(f"SceneManager: Scene '{entry.scene.name}' loaded in workspace.")
        return entry.edit_world  # type: ignore[return-value]

    def create_new_scene(self, name: str = "New Scene", activate: bool = True) -> "World":
        key = self._next_untitled_key()
        scene = self._projection.create_empty_scene(name)
        entry = SceneWorkspaceEntry(key=key, scene=scene)
        world = self._projection.create_world(scene)
        self.install_entry_state(entry, scene, world)
        self.entries[key] = entry
        if activate or not self.active_scene_key:
            self.active_scene_key = key
        log_info(f"SceneManager: Nueva escena '{name}' creada.")
        return entry.edit_world  # type: ignore[return-value]

    def enter_play(self) -> Optional["World"]:
        entry = self.get_active_entry()
        if entry is None or entry.edit_world is None:
            log_warn("SceneManager: no hay world para play")
            return None
        selection = self.capture_selection(entry)
        try:
            runtime_world = entry.edit_world.clone()
        except Exception as exc:
            entry.runtime_world = None
            entry.is_playing = False
            log_err(f"SceneManager: no se pudo entrar en PLAY por fallo de clonacion: {exc}")
            return None
        entry.runtime_world = runtime_world
        entry.is_playing = True
        self.restore_selection(entry, selection)
        return entry.runtime_world

    def exit_play(self) -> Optional["World"]:
        entry = self.get_active_entry()
        if entry is None:
            return None
        if entry.runtime_world is not None:
            runtime_name = entry.runtime_world.selected_entity_name
            if runtime_name:
                self.select_entity(entry, entity_name=runtime_name)
        entry.runtime_world = None
        entry.is_playing = False
        self.rebuild_edit_world(entry)
        return entry.edit_world

    def restore_world(self, world: "World") -> None:
        entry = self.get_active_entry()
        if entry is None or not entry.is_playing:
            print("[WARNING] SceneManager.restore_world: solo se puede restaurar en PLAY")
            return
        entry.runtime_world = world

    def reload_scene(self) -> Optional["World"]:
        entry = self.get_active_entry()
        if entry is None:
            return None
        entry.runtime_world = None
        entry.is_playing = False
        self.rebuild_edit_world(entry)
        self.clear_dirty(entry)
        return entry.edit_world

    def rekey_entry(self, entry: SceneWorkspaceEntry, new_key: str) -> None:
        old_key = entry.key
        if entry.source_path:
            entry.scene.set_source_path(self.normalize_path_reference(entry.source_path))
        if old_key == new_key:
            return
        self.entries.pop(old_key, None)
        entry.key = new_key
        self.entries[new_key] = entry
        if self.active_scene_key == old_key:
            self.active_scene_key = new_key

    def build_scene_key(self, source_path: Optional[str], scene_name: str) -> str:
        if source_path:
            return self.normalize_path_reference(source_path)
        return self._next_untitled_key(scene_name)

    def _next_untitled_key(self, scene_name: Optional[str] = None) -> str:
        suffix = f":{scene_name}" if scene_name else ""
        key = f"untitled:{self._untitled_counter}{suffix}"
        self._untitled_counter += 1
        return key

    @staticmethod
    def normalize_path_reference(path: str) -> str:
        return Path(path).resolve().as_posix()

    @staticmethod
    def entity_id_for_name(entry: SceneWorkspaceEntry, entity_name: Optional[str]) -> Optional[str]:
        if not entity_name:
            return None
        entity_data = entry.scene.find_entity(entity_name)
        entity_id = entity_data.get("id") if isinstance(entity_data, dict) else None
        return entity_id.strip() if isinstance(entity_id, str) and entity_id.strip() else None

    @staticmethod
    def entity_name_for_id(entry: SceneWorkspaceEntry, entity_id: Optional[str]) -> Optional[str]:
        if not entity_id:
            return None
        entity_data = entry.scene.find_entity_by_id(entity_id)
        entity_name = entity_data.get("name") if isinstance(entity_data, dict) else None
        return entity_name if isinstance(entity_name, str) and entity_name else None

    def capture_selection(self, entry: SceneWorkspaceEntry) -> SceneSelectionSnapshot:
        world_name = entry.active_world.selected_entity_name if entry.active_world is not None else None
        if world_name and entry.scene.find_entity(world_name) is not None:
            return SceneSelectionSnapshot(
                entity_name=world_name,
                entity_id=self.entity_id_for_name(entry, world_name),
            )
        entity_name = entry.selected_entity_name
        entity_id = entry.selected_entity_id or self.entity_id_for_name(entry, entity_name)
        resolved_name = self.entity_name_for_id(entry, entity_id) or entity_name
        return SceneSelectionSnapshot(entity_name=resolved_name, entity_id=entity_id)

    def select_entity(
        self,
        entry: SceneWorkspaceEntry,
        *,
        entity_name: Optional[str] = None,
        entity_id: Optional[str] = None,
    ) -> bool:
        if entity_name is None and entity_id is None:
            self.clear_selection(entry)
            return True
        if entity_id:
            resolved_entity = entry.scene.find_entity_by_id(entity_id)
        else:
            resolved_entity = entry.scene.find_entity(entity_name or "")
        if resolved_entity is None:
            return False
        resolved_name = str(resolved_entity.get("name", "") or "")
        resolved_id = resolved_entity.get("id")
        entry.selected_entity_name = resolved_name
        entry.selected_entity_id = resolved_id if isinstance(resolved_id, str) and resolved_id else None
        for world in (entry.edit_world, entry.runtime_world):
            if world is not None:
                world.selected_entity_name = resolved_name
        return True

    def restore_selection(self, entry: SceneWorkspaceEntry, snapshot: SceneSelectionSnapshot) -> None:
        if snapshot.entity_id and self.select_entity(entry, entity_id=snapshot.entity_id):
            return
        if snapshot.entity_name and self.select_entity(entry, entity_name=snapshot.entity_name):
            return
        self.clear_selection(entry)

    @staticmethod
    def clear_selection(entry: SceneWorkspaceEntry) -> None:
        entry.selected_entity_name = None
        entry.selected_entity_id = None
        for world in (entry.edit_world, entry.runtime_world):
            if world is not None:
                world.selected_entity_name = None

    @staticmethod
    def mark_dirty(entry: SceneWorkspaceEntry) -> None:
        entry.dirty = True

    @staticmethod
    def clear_dirty(entry: SceneWorkspaceEntry) -> None:
        entry.dirty = False

    @staticmethod
    def restore_dirty(entry: SceneWorkspaceEntry, value: bool) -> None:
        entry.dirty = bool(value)

    def prepare_scene_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._flow_policy.prepare_payload(payload)

    def sync_scene_links_from_feature_metadata(self, scene: Scene) -> None:
        self._flow_policy.sync_links_from_metadata(scene)

    def sync_feature_metadata_from_scene_links(self, entry: SceneWorkspaceEntry) -> None:
        scene_flow = self._flow_policy.sync_metadata_from_links(entry.scene)
        if entry.edit_world is None:
            return
        if scene_flow:
            entry.edit_world.feature_metadata["scene_flow"] = copy.deepcopy(scene_flow)
        else:
            entry.edit_world.feature_metadata.pop("scene_flow", None)

    def replace_entry_scene(
        self,
        entry: SceneWorkspaceEntry,
        data: dict[str, Any],
        *,
        source_path: Optional[str] = None,
    ) -> Scene:
        selection = self.capture_selection(entry)
        target_source_path = entry.scene.source_path if source_path is None else source_path
        prepared = self._flow_policy.prepare_payload(data)
        scene = self._projection.create_scene(
            prepared,
            source_path=target_source_path,
            fallback_name=entry.scene.name,
        )
        self._flow_policy.sync_links_from_metadata(scene)
        world = self._projection.create_world(scene)
        self.install_entry_state(entry, scene, world)
        self.restore_selection(entry, selection)
        return scene

    @staticmethod
    def install_entry_state(entry: SceneWorkspaceEntry, scene: Scene, world: "World") -> None:
        entry.scene = scene
        entry.edit_world = world
        entry.edit_world_version = world.version

    def rebuild_edit_world(
        self,
        entry: SceneWorkspaceEntry,
        *,
        selection: Optional[SceneSelectionSnapshot] = None,
    ) -> None:
        preserved_selection = selection or self.capture_selection(entry)
        edit_world = self._projection.create_world(entry.scene)
        self.install_entry_state(entry, entry.scene, edit_world)
        self.restore_selection(entry, preserved_selection)

    @staticmethod
    def _entry_path_or_key(entry: Optional[SceneWorkspaceEntry]) -> str:
        return "" if entry is None else (entry.source_path or entry.key)
