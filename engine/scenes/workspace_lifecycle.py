from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional

from engine.editor.console_panel import log_err, log_info, log_warn
from engine.scenes.scene import Scene
from engine.scenes.storage import JsonSceneStorage, SceneStorage

if TYPE_CHECKING:
    from engine.ecs.world import World

LEGACY_EDIT_WORLD_SYNC_REASON = "legacy_authoring"


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

    @edit_world_sync_pending.setter
    def edit_world_sync_pending(self, value: bool) -> None:
        self.pending_edit_world_sync_reason = LEGACY_EDIT_WORLD_SYNC_REASON if value else None
        if not value:
            self.dirty_before_pending_edit_world_sync = None


class SceneWorkspace:
    """Owns workspace scene entries and edit/play lifecycle transitions."""

    def __init__(
        self,
        *,
        validate_scene_payload: Callable[[dict[str, Any]], dict[str, Any]],
        build_scene_key: Callable[[Optional[str], str], str],
        create_untitled_key: Callable[[str], str],
        rebuild_edit_world: Callable[[SceneWorkspaceEntry], None],
        sync_scene_links_from_feature_metadata: Callable[[SceneWorkspaceEntry], None],
        entry_has_invalid_links: Callable[[SceneWorkspaceEntry], bool],
    ) -> None:
        self.entries: dict[str, SceneWorkspaceEntry] = {}
        self.active_scene_key: str = ""
        self._validate_scene_payload = validate_scene_payload
        self._build_scene_key = build_scene_key
        self._create_untitled_key = create_untitled_key
        self._rebuild_edit_world = rebuild_edit_world
        self._sync_scene_links_from_feature_metadata = sync_scene_links_from_feature_metadata
        self._entry_has_invalid_links = entry_has_invalid_links

    def get_active_entry(self) -> Optional[SceneWorkspaceEntry]:
        return self.entries.get(self.active_scene_key) if self.active_scene_key else None

    def resolve_entry(self, key_or_path: Optional[str]) -> Optional[SceneWorkspaceEntry]:
        if key_or_path in (None, ""):
            return self.get_active_entry()
        if key_or_path in self.entries:
            return self.entries[str(key_or_path)]
        key_text = str(key_or_path)
        normalized = (
            Path(key_text).resolve().as_posix()
            if key_text.endswith(".json") or "/" in key_text or "\\" in key_text
            else key_text
        )
        for entry in self.entries.values():
            if entry.source_path == normalized:
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
                "has_invalid_links": self._entry_has_invalid_links(entry),
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
            self._rebuild_edit_world(entry)
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
        payload = self._validate_scene_payload(data)
        key = self._build_scene_key(source_path, payload.get("name", "Untitled"))
        entry = SceneWorkspaceEntry(key=key, scene=Scene.from_dict(copy.deepcopy(payload), source_path=source_path))
        self._sync_scene_links_from_feature_metadata(entry)
        self._rebuild_edit_world(entry)
        self.entries[key] = entry
        if activate or not self.active_scene_key:
            self.active_scene_key = key
        log_info(f"SceneManager: Scene '{entry.scene.name}' loaded in workspace.")
        return entry.edit_world  # type: ignore[return-value]

    def load_scene_from_file(
        self,
        path: str,
        activate: bool = True,
        storage: Optional[SceneStorage] = None,
    ) -> Optional["World"]:
        resolved_path = Path(path).resolve().as_posix()
        existing = self.resolve_entry(resolved_path)
        if existing is not None:
            if activate:
                self.active_scene_key = existing.key
            return existing.edit_world
        try:
            data = (storage or JsonSceneStorage()).load(resolved_path)
        except Exception as exc:
            log_err(f"SceneManager: Error cargando {resolved_path}: {exc}")
            return None
        return self.load_scene(data, source_path=resolved_path, activate=activate)

    def create_new_scene(self, name: str = "New Scene", activate: bool = True) -> "World":
        key = self._create_untitled_key(name)
        entry = SceneWorkspaceEntry(key=key, scene=Scene(name))
        self._rebuild_edit_world(entry)
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
        entry.selected_entity_name = entry.edit_world.selected_entity_name
        entry.selected_entity_id = self._entity_id_for_name(entry, entry.selected_entity_name) or entry.selected_entity_id
        try:
            entry.runtime_world = entry.edit_world.clone()
        except Exception as exc:
            entry.runtime_world = None
            entry.is_playing = False
            log_err(f"SceneManager: no se pudo entrar en PLAY por fallo de clonacion: {exc}")
            return None
        selected_name = self._entity_name_for_id(entry, entry.selected_entity_id) or entry.selected_entity_name
        if selected_name and entry.runtime_world.get_entity_by_name(selected_name) is not None:
            entry.runtime_world.selected_entity_name = selected_name
            entry.selected_entity_name = selected_name
        entry.is_playing = True
        return entry.runtime_world

    def exit_play(self) -> Optional["World"]:
        entry = self.get_active_entry()
        if entry is None:
            return None
        if entry.runtime_world is not None:
            entry.selected_entity_name = entry.runtime_world.selected_entity_name or entry.selected_entity_name
            entry.selected_entity_id = self._entity_id_for_name(entry, entry.selected_entity_name) or entry.selected_entity_id
        entry.runtime_world = None
        entry.is_playing = False
        entry.edit_world_sync_pending = False
        self._rebuild_edit_world(entry)
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
        self._rebuild_edit_world(entry)
        entry.dirty = False
        entry.edit_world_sync_pending = False
        return entry.edit_world

    def rekey_entry(self, entry: SceneWorkspaceEntry, new_key: str) -> None:
        old_key = entry.key
        if old_key == new_key:
            return
        self.entries.pop(old_key, None)
        entry.key = new_key
        self.entries[new_key] = entry
        if self.active_scene_key == old_key:
            self.active_scene_key = new_key

    @staticmethod
    def _entity_id_for_name(entry: SceneWorkspaceEntry, entity_name: Optional[str]) -> Optional[str]:
        if not entity_name:
            return None
        entity_data = entry.scene.find_entity(entity_name)
        entity_id = entity_data.get("id") if isinstance(entity_data, dict) else None
        return entity_id.strip() if isinstance(entity_id, str) and entity_id.strip() else None

    @staticmethod
    def _entity_name_for_id(entry: SceneWorkspaceEntry, entity_id: Optional[str]) -> Optional[str]:
        if not entity_id:
            return None
        entity_data = entry.scene.find_entity_by_id(entity_id)
        entity_name = entity_data.get("name") if isinstance(entity_data, dict) else None
        return entity_name if isinstance(entity_name, str) and entity_name else None

    @staticmethod
    def _entry_path_or_key(entry: Optional[SceneWorkspaceEntry]) -> str:
        return "" if entry is None else (entry.source_path or entry.key)
