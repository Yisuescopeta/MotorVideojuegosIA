from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

from engine.authoring.changes import Change
from engine.components.recttransform import RectTransform
from engine.components.transform import Transform
from engine.editor.console_panel import log_err, log_info, log_warn
from engine.scenes.scene import Scene
from engine.serialization.schema import migrate_scene_data, validate_scene_data

if TYPE_CHECKING:
    from engine.ecs.world import World
    from engine.levels.component_registry import ComponentRegistry


@dataclass
class SceneWorkspaceEntry:
    key: str
    scene: Scene
    edit_world: Optional["World"] = None
    runtime_world: Optional["World"] = None
    is_playing: bool = False
    selected_entity_name: Optional[str] = None
    dirty: bool = False
    edit_world_sync_pending: bool = False
    view_state: Dict[str, Any] = field(default_factory=dict)

    @property
    def source_path(self) -> str:
        return str(self.scene.source_path or "")

    @property
    def active_world(self) -> Optional["World"]:
        return self.runtime_world if self.is_playing else self.edit_world


class SceneManager:
    def __init__(self, registry: "ComponentRegistry") -> None:
        self._registry = registry
        self._entries: dict[str, SceneWorkspaceEntry] = {}
        self._active_scene_key: str = ""
        self._history: Any = None
        self._suspend_history: bool = False
        self._active_transaction: dict[str, Any] | None = None
        self._untitled_counter: int = 1
        self._clipboard: list[dict[str, Any]] = []
        self._clipboard_root_name: str = ""

    @property
    def current_scene(self) -> Optional[Scene]:
        entry = self._get_active_entry()
        return entry.scene if entry is not None else None

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
        return any(entry.dirty for entry in self._entries.values())

    @property
    def active_world(self) -> Optional["World"]:
        entry = self._get_active_entry()
        return entry.active_world if entry is not None else None

    @property
    def active_scene_key(self) -> str:
        return self._active_scene_key

    def set_history_manager(self, history: Any) -> None:
        self._history = history

    def list_open_scenes(self) -> list[Dict[str, Any]]:
        return [
            {
                "key": entry.key,
                "name": entry.scene.name,
                "path": entry.source_path,
                "dirty": entry.dirty,
                "is_active": entry.key == self._active_scene_key,
                "has_invalid_links": self._entry_has_invalid_links(entry),
            }
            for entry in self._entries.values()
        ]

    def get_scene_view_state(self, key: Optional[str] = None) -> Dict[str, Any]:
        entry = self._resolve_entry(key)
        return copy.deepcopy(entry.view_state) if entry is not None else {}

    def set_scene_view_state(self, key: str, view_state: Dict[str, Any]) -> bool:
        entry = self._resolve_entry(key)
        if entry is None:
            return False
        entry.view_state = copy.deepcopy(view_state)
        return True

    def get_workspace_state(self) -> Dict[str, Any]:
        return {
            "open_scenes": [self._entry_path_or_key(entry) for entry in self._entries.values()],
            "active_scene": self._entry_path_or_key(self._get_active_entry()),
            "scene_view_states": {
                self._entry_path_or_key(entry): copy.deepcopy(entry.view_state)
                for entry in self._entries.values()
                if entry.view_state
            },
        }

    def activate_scene(self, key_or_path: str) -> Optional["World"]:
        entry = self._resolve_entry(key_or_path)
        active = self._get_active_entry()
        if entry is None:
            return None
        if active is not None and active.key != entry.key and active.is_playing:
            return None
        self._active_scene_key = entry.key
        if entry.edit_world is None:
            self._rebuild_edit_world(entry)
        return entry.active_world

    def close_scene(self, key_or_path: str, discard_changes: bool = False) -> bool:
        entry = self._resolve_entry(key_or_path)
        if entry is None or (entry.dirty and not discard_changes):
            return False
        was_active = entry.key == self._active_scene_key
        del self._entries[entry.key]
        if not self._entries:
            self._active_scene_key = ""
            return True
        if was_active:
            self._active_scene_key = next(iter(self._entries.keys()))
        return True

    def reset_workspace(self) -> None:
        self._entries.clear()
        self._active_scene_key = ""
        self._clipboard = []
        self._clipboard_root_name = ""

    def load_scene(self, data: Dict[str, Any], source_path: Optional[str] = None, activate: bool = True) -> "World":
        data = migrate_scene_data(data)
        validation_errors = validate_scene_data(data)
        if validation_errors:
            raise ValueError(f"Invalid scene payload: {'; '.join(validation_errors)}")
        key = self._build_scene_key(source_path, data.get("name", "Untitled"))
        entry = SceneWorkspaceEntry(key=key, scene=Scene.from_dict(copy.deepcopy(data), source_path=source_path))
        self._sync_scene_links_from_feature_metadata(entry)
        self._rebuild_edit_world(entry)
        self._entries[key] = entry
        if activate or not self._active_scene_key:
            self._active_scene_key = key
        log_info(f"SceneManager: Scene '{entry.scene.name}' loaded in workspace.")
        return entry.edit_world  # type: ignore[return-value]

    def load_scene_from_file(self, path: str, activate: bool = True) -> Optional["World"]:
        resolved_path = Path(path).resolve().as_posix()
        existing = self._resolve_entry(resolved_path)
        if existing is not None:
            if activate:
                self._active_scene_key = existing.key
            return existing.edit_world
        try:
            with open(resolved_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception as exc:
            log_err(f"SceneManager: Error cargando {resolved_path}: {exc}")
            return None
        return self.load_scene(data, source_path=resolved_path, activate=activate)

    def get_edit_world(self) -> Optional["World"]:
        entry = self._get_active_entry()
        return entry.edit_world if entry is not None else None

    def create_new_scene(self, name: str = "New Scene", activate: bool = True) -> "World":
        key = f"untitled:{self._untitled_counter}"
        self._untitled_counter += 1
        entry = SceneWorkspaceEntry(key=key, scene=Scene(name))
        self._rebuild_edit_world(entry)
        self._entries[key] = entry
        if activate or not self._active_scene_key:
            self._active_scene_key = key
        log_info(f"SceneManager: Nueva escena '{name}' creada.")
        return entry.edit_world  # type: ignore[return-value]

    def enter_play(self) -> Optional["World"]:
        entry = self._get_active_entry()
        if entry is None or entry.edit_world is None:
            log_warn("SceneManager: no hay world para play")
            return None
        entry.selected_entity_name = entry.edit_world.selected_entity_name
        try:
            entry.runtime_world = entry.edit_world.clone()
        except Exception as exc:
            entry.runtime_world = None
            entry.is_playing = False
            log_err(f"SceneManager: no se pudo entrar en PLAY por fallo de clonacion: {exc}")
            return None
        if entry.selected_entity_name and entry.runtime_world.get_entity_by_name(entry.selected_entity_name) is not None:
            entry.runtime_world.selected_entity_name = entry.selected_entity_name
        entry.is_playing = True
        return entry.runtime_world

    def exit_play(self) -> Optional["World"]:
        entry = self._get_active_entry()
        if entry is None:
            return None
        if entry.runtime_world is not None:
            entry.selected_entity_name = entry.runtime_world.selected_entity_name or entry.selected_entity_name
        entry.runtime_world = None
        entry.is_playing = False
        entry.edit_world_sync_pending = False
        self._rebuild_edit_world(entry)
        return entry.edit_world

    def restore_world(self, world: "World") -> None:
        entry = self._get_active_entry()
        if entry is None or not entry.is_playing:
            print("[WARNING] SceneManager.restore_world: solo se puede restaurar en PLAY")
            return
        entry.runtime_world = world

    def reload_scene(self) -> Optional["World"]:
        entry = self._get_active_entry()
        if entry is None:
            return None
        entry.runtime_world = None
        entry.is_playing = False
        self._rebuild_edit_world(entry)
        entry.dirty = False
        entry.edit_world_sync_pending = False
        return entry.edit_world

    def apply_edit_to_world(self, entity_name: str, component_name: str, property_name: str, value: Any) -> bool:
        entry = self._get_active_entry()
        if entry is None or entry.is_playing or entry.edit_world is None:
            return False
        self._flush_pending_edit_world(entry)
        before = copy.deepcopy(entry.scene.to_dict())
        if not entry.scene.update_component(entity_name, component_name, property_name, value):
            if not self._update_prefab_component_override(entry, entity_name, component_name, property_name, value):
                return False
        if component_name == "SceneLink":
            self._sync_feature_metadata_from_scene_links(entry)
        self._rebuild_edit_world(entry)
        entry.dirty = True
        self._record_scene_change(entry, f"{entity_name}.{component_name}.{property_name}", before)
        return True

    def update_entity_property(self, entity_name: str, property_name: str, value: Any) -> bool:
        entry = self._get_active_entry()
        if entry is None or entry.is_playing:
            return False
        if property_name == "parent" and value is not None and not self._validate_parent(entry, entity_name, value):
            return False
        self._flush_pending_edit_world(entry)
        before = copy.deepcopy(entry.scene.to_dict())
        if not entry.scene.update_entity_property(entity_name, property_name, value):
            if not self._update_prefab_entity_override(entry, entity_name, property_name, value):
                return False
        self._rebuild_edit_world(entry)
        entry.dirty = True
        self._record_scene_change(entry, f"{entity_name}.{property_name}", before)
        return True

    def replace_component_data(self, entity_name: str, component_name: str, component_data: Dict[str, Any]) -> bool:
        entry = self._get_active_entry()
        if entry is None or entry.is_playing or entry.edit_world is None:
            return False
        self._flush_pending_edit_world(entry)
        before = copy.deepcopy(entry.scene.to_dict())
        if not entry.scene.replace_component_data(entity_name, component_name, copy.deepcopy(component_data)):
            if not self._replace_prefab_component_override(entry, entity_name, component_name, component_data):
                return False
        if component_name == "SceneLink":
            self._sync_feature_metadata_from_scene_links(entry)
        self._rebuild_edit_world(entry)
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
        self._flush_pending_edit_world(entry)
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
        self._flush_pending_edit_world(entry)
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
        for component_name in payload["components"].keys():
            payload["component_metadata"][component_name] = {"origin": self._registry.get_origin(component_name)}
        before = copy.deepcopy(entry.scene.to_dict())
        if not entry.scene.add_entity(payload):
            return False
        if not payload["component_metadata"]:
            payload.pop("component_metadata", None)
        if self._entity_has_scene_link(payload):
            self._sync_feature_metadata_from_scene_links(entry)
        self._rebuild_edit_world(entry)
        entry.dirty = True
        self._record_scene_change(entry, f"create_entity:{name}", before)
        return True

    def create_entity_from_data(self, entity_data: Dict[str, Any]) -> bool:
        entry = self._get_active_entry()
        if entry is None or entry.is_playing:
            return False
        self._flush_pending_edit_world(entry)
        payload = copy.deepcopy(entity_data)
        payload.setdefault("active", True)
        payload.setdefault("tag", "Untagged")
        payload.setdefault("layer", "Default")
        payload.setdefault("parent", None)
        payload.setdefault("components", {})
        payload.setdefault("component_metadata", {})
        for component_name in payload["components"].keys():
            payload["component_metadata"].setdefault(component_name, {})
            payload["component_metadata"][component_name].setdefault("origin", self._registry.get_origin(component_name))
        before = copy.deepcopy(entry.scene.to_dict())
        if not entry.scene.add_entity(payload):
            return False
        if self._entity_has_scene_link(payload):
            self._sync_feature_metadata_from_scene_links(entry)
        self._rebuild_edit_world(entry)
        entry.dirty = True
        self._record_scene_change(entry, f"create_entity:{payload.get('name', '')}", before)
        return True

    def remove_entity(self, entity_name: str) -> bool:
        entry = self._get_active_entry()
        if entry is None or entry.is_playing:
            return False
        self._flush_pending_edit_world(entry)
        before = copy.deepcopy(entry.scene.to_dict())

        # Orphan direct children: reparent them to the deleted entity's parent
        deleted_data = entry.scene.find_entity(entity_name)
        grandparent = deleted_data.get("parent") if deleted_data is not None else None
        for child_data in list(entry.scene.entities_data):
            if child_data.get("parent") != entity_name:
                continue
            child_name = child_data.get("name", "")
            # Compute child's current world transform before reparenting
            child_world = self._compute_world_transform_from_scene_data(entry, child_name)
            # Point child to grandparent (or None for root)
            child_data["parent"] = grandparent
            # Recalculate child's local transform to preserve world position
            if child_world is not None:
                cwx, cwy, cwr, cwsx, cwsy = child_world
                if grandparent is not None:
                    gp_world = self._compute_world_transform_from_scene_data(entry, grandparent)
                    if gp_world is not None:
                        gpx, gpy, gpr, gpsx, gpsy = gp_world
                        cwx -= gpx
                        cwy -= gpy
                        cwr -= gpr
                        cwsx = cwsx / gpsx if gpsx != 0 else cwsx
                        cwsy = cwsy / gpsy if gpsy != 0 else cwsy
                ct = child_data.get("components", {}).get("Transform")
                if ct is not None:
                    ct["x"] = cwx
                    ct["y"] = cwy
                    ct["rotation"] = cwr
                    ct["scale_x"] = cwsx
                    ct["scale_y"] = cwsy

        if not self._remove_single_entity(entry, entity_name):
            return False
        self._sync_feature_metadata_from_scene_links(entry)
        self._rebuild_edit_world(entry)
        entry.dirty = True
        self._record_scene_change(entry, f"remove_entity:{entity_name}", before)
        return True

    def add_component_to_entity(self, entity_name: str, component_name: str, component_data: Optional[Dict[str, Any]] = None) -> bool:
        entry = self._get_active_entry()
        if entry is None or entry.is_playing:
            return False
        self._flush_pending_edit_world(entry)
        before = copy.deepcopy(entry.scene.to_dict())
        data = component_data or {"enabled": True}
        if not entry.scene.add_component(entity_name, component_name, data):
            if not self._replace_prefab_component_override(entry, entity_name, component_name, data):
                return False
        entry.scene.set_component_metadata(entity_name, component_name, {"origin": self._registry.get_origin(component_name)})
        if component_name == "SceneLink":
            self._sync_feature_metadata_from_scene_links(entry)
        self._rebuild_edit_world(entry)
        entry.dirty = True
        self._record_scene_change(entry, f"add_component:{entity_name}.{component_name}", before)
        return True

    def remove_component_from_entity(self, entity_name: str, component_name: str) -> bool:
        entry = self._get_active_entry()
        if entry is None or entry.is_playing:
            return False
        self._flush_pending_edit_world(entry)
        before = copy.deepcopy(entry.scene.to_dict())
        if not entry.scene.remove_component(entity_name, component_name):
            if not self._remove_prefab_component_override(entry, entity_name, component_name):
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
        self._flush_pending_edit_world(entry)
        return entry.scene.find_entity(entity_name)

    def sync_from_edit_world(self, force: bool = False) -> bool:
        entry = self._get_active_entry()
        if entry is None or entry.is_playing or entry.edit_world is None:
            return False
        if not force and not entry.edit_world_sync_pending:
            return False
        return self._sync_entry_from_edit_world(entry)

    def mark_edit_world_dirty(self) -> bool:
        entry = self._get_active_entry()
        if entry is None or entry.is_playing or entry.edit_world is None:
            return False
        entry.dirty = True
        entry.edit_world_sync_pending = True
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
        if entry is None or entry.is_playing or entry.edit_world is None:
            return False
        entity = entry.edit_world.get_entity_by_name(entity_name)
        if entity is None:
            return False
        transform = entity.get_component(Transform)
        if transform is None:
            return False
        before = copy.deepcopy(entry.scene.to_dict()) if record_history else None
        transform.local_x = float(transform_state.get("x", transform.local_x))
        transform.local_y = float(transform_state.get("y", transform.local_y))
        transform.local_rotation = float(transform_state.get("rotation", transform.local_rotation))
        transform.local_scale_x = float(transform_state.get("scale_x", transform.local_scale_x))
        transform.local_scale_y = float(transform_state.get("scale_y", transform.local_scale_y))
        entry.selected_entity_name = entity_name
        entry.edit_world.selected_entity_name = entity_name
        entry.dirty = True
        entry.edit_world_sync_pending = True
        self._sync_entry_from_edit_world(entry)
        if record_history and before is not None:
            self._record_scene_change(entry, label or f"transform:{entity_name}", before)
        return True

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
        if entry is None or entry.is_playing or entry.edit_world is None:
            return False
        entity = entry.edit_world.get_entity_by_name(entity_name)
        if entity is None:
            return False
        rect_transform = entity.get_component(RectTransform)
        if rect_transform is None:
            return False
        before = copy.deepcopy(entry.scene.to_dict()) if record_history else None
        rect_transform.anchored_x = float(rect_state.get("anchored_x", rect_transform.anchored_x))
        rect_transform.anchored_y = float(rect_state.get("anchored_y", rect_transform.anchored_y))
        rect_transform.width = float(rect_state.get("width", rect_transform.width))
        rect_transform.height = float(rect_state.get("height", rect_transform.height))
        rect_transform.rotation = float(rect_state.get("rotation", rect_transform.rotation))
        rect_transform.scale_x = float(rect_state.get("scale_x", rect_transform.scale_x))
        rect_transform.scale_y = float(rect_state.get("scale_y", rect_transform.scale_y))
        entry.selected_entity_name = entity_name
        entry.edit_world.selected_entity_name = entity_name
        entry.dirty = True
        entry.edit_world_sync_pending = True
        self._sync_entry_from_edit_world(entry)
        if record_history and before is not None:
            self._record_scene_change(entry, label or f"rect_transform:{entity_name}", before)
        return True

    def set_selected_entity(self, entity_name: Optional[str]) -> bool:
        entry = self._get_active_entry()
        if entry is None or entry.active_world is None:
            return False
        if entity_name and entry.active_world.get_entity_by_name(entity_name) is None:
            return False
        entry.selected_entity_name = entity_name
        entry.active_world.selected_entity_name = entity_name
        if entry.edit_world is not None:
            entry.edit_world.selected_entity_name = entity_name
        if entry.runtime_world is not None:
            entry.runtime_world.selected_entity_name = entity_name
        return True

    def save_scene_to_file(self, path: str, key: Optional[str] = None) -> bool:
        entry = self._resolve_entry(key)
        if entry is None or entry.edit_world is None:
            return False
        try:
            # Saving should always serialize the live edit world so legacy
            # fields normalize into the canonical asset-reference shape.
            self._sync_entry_from_edit_world(entry)
            data = migrate_scene_data(entry.scene.to_dict())
            data["name"] = entry.scene.name
            validation_errors = validate_scene_data(data)
            if validation_errors:
                raise ValueError("; ".join(validation_errors))
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=4)
            entry.scene = Scene(data["name"], data, source_path=path)
            old_key = entry.key
            entry.key = self._build_scene_key(path, entry.scene.name)
            self._entries.pop(old_key, None)
            self._entries[entry.key] = entry
            if self._active_scene_key == old_key:
                self._active_scene_key = entry.key
            self._rebuild_edit_world(entry)
            entry.dirty = False
            entry.edit_world_sync_pending = False
            return True
        except Exception as exc:
            log_err(f"SceneManager: error al guardar en {path}: {exc}")
            return False

    def restore_scene_data(self, data: Dict[str, Any]) -> bool:
        entry = self._get_active_entry()
        if entry is None or entry.is_playing:
            return False
        entry.scene = Scene(data.get("name", entry.scene.name), copy.deepcopy(data), source_path=entry.scene.source_path)
        self._sync_scene_links_from_feature_metadata(entry)
        self._rebuild_edit_world(entry)
        entry.dirty = True
        entry.edit_world_sync_pending = False
        return True

    def set_entity_parent(self, entity_name: str, parent_name: Optional[str]) -> bool:
        """Reparent an entity, preserving its world-space transform."""
        entry = self._get_active_entry()
        if entry is None or entry.is_playing:
            return False
        if parent_name is not None and not self._validate_parent(entry, entity_name, parent_name):
            return False
        self._flush_pending_edit_world(entry)
        before = copy.deepcopy(entry.scene.to_dict())

        # Compute current world transform from scene data
        world_tx = self._compute_world_transform_from_scene_data(entry, entity_name)
        if world_tx is None:
            return self.update_entity_property(entity_name, "parent", parent_name)

        wx, wy, w_rot, w_sx, w_sy = world_tx

        # Update parent in scene data
        if not entry.scene.update_entity_property(entity_name, "parent", parent_name):
            return False

        # Compute new parent's world transform (if any)
        if parent_name is not None:
            parent_world = self._compute_world_transform_from_scene_data(entry, parent_name)
            if parent_world is not None:
                px, py, p_rot, p_sx, p_sy = parent_world
                new_local_x = wx - px
                new_local_y = wy - py
                new_local_rot = w_rot - p_rot
                new_local_sx = w_sx / p_sx if p_sx != 0 else w_sx
                new_local_sy = w_sy / p_sy if p_sy != 0 else w_sy
            else:
                new_local_x, new_local_y = wx, wy
                new_local_rot, new_local_sx, new_local_sy = w_rot, w_sx, w_sy
        else:
            new_local_x, new_local_y = wx, wy
            new_local_rot, new_local_sx, new_local_sy = w_rot, w_sx, w_sy

        # Write recalculated local transform back to scene data
        entity_data = entry.scene.find_entity(entity_name)
        if entity_data is not None:
            transform_data = entity_data.get("components", {}).get("Transform")
            if transform_data is not None:
                transform_data["x"] = new_local_x
                transform_data["y"] = new_local_y
                transform_data["rotation"] = new_local_rot
                transform_data["scale_x"] = new_local_sx
                transform_data["scale_y"] = new_local_sy

        self._rebuild_edit_world(entry)
        entry.dirty = True
        self._record_scene_change(entry, f"reparent:{entity_name}", before)
        return True

    def create_child_entity(self, parent_name: str, name: str, components: Optional[Dict[str, Dict[str, Any]]] = None) -> bool:
        """Create a new entity as a child. The provided component coords are local (no world-position preservation)."""
        if not self.create_entity(name, components=components):
            return False
        # Set parent directly without recalculating transform (coords are already local)
        return self.update_entity_property(name, "parent", parent_name)

    def instantiate_prefab(self, name: str, prefab_path: str, parent: Optional[str] = None, overrides: Optional[Dict[str, Any]] = None, root_name: Optional[str] = None) -> bool:
        return self.create_entity_from_data(
            {
                "name": name,
                "active": True,
                "tag": "Untagged",
                "layer": "Default",
                "parent": parent,
                "prefab_instance": {"prefab_path": prefab_path, "root_name": root_name or name, "overrides": copy.deepcopy(overrides or {})},
                "components": {},
                "component_metadata": {},
            }
        )

    def unpack_prefab(self, entity_name: str) -> bool:
        entry = self._get_active_entry()
        if entry is None or entry.is_playing or entry.edit_world is None:
            return False
        root = entry.edit_world.get_entity_by_name(entity_name)
        if root is None or root.prefab_instance is None:
            return False
        before = copy.deepcopy(entry.scene.to_dict())
        subtree = [root] + entry.edit_world.get_descendants(root.name)
        explicit_entities = []
        for entity in subtree:
            payload = entity.to_dict()
            payload.pop("id", None)
            payload.pop("prefab_instance", None)
            payload.pop("prefab_source_path", None)
            payload.pop("prefab_root_name", None)
            explicit_entities.append(payload)
        if not self._remove_entity_subtree(entry, entity_name):
            return False
        for payload in explicit_entities:
            entry.scene.add_entity(payload)
        self._sync_feature_metadata_from_scene_links(entry)
        self._rebuild_edit_world(entry)
        entry.dirty = True
        self._record_scene_change(entry, f"unpack_prefab:{entity_name}", before)
        return True

    def apply_prefab_overrides(self, entity_name: str) -> bool:
        entry = self._get_active_entry()
        if entry is None or entry.is_playing or entry.edit_world is None:
            return False
        from engine.assets.prefab import PrefabManager

        root = entry.edit_world.get_entity_by_name(entity_name)
        if root is None or root.prefab_instance is None:
            return False
        prefab_path = root.prefab_instance.get("prefab_path", "")
        resolved_path = (Path(entry.scene.source_path).resolve().parent / prefab_path).resolve().as_posix() if entry.scene.source_path else prefab_path
        before = copy.deepcopy(entry.scene.to_dict())
        if not PrefabManager.save_prefab(root, resolved_path, world=entry.edit_world):
            return False
        entity_data = entry.scene.find_entity(entity_name)
        if entity_data is None:
            return False
        entity_data["prefab_instance"]["overrides"] = {}
        self._rebuild_edit_world(entry)
        entry.dirty = True
        self._record_scene_change(entry, f"apply_prefab_overrides:{entity_name}", before)
        return True

    def duplicate_entity_subtree(self, entity_name: str, new_root_name: Optional[str] = None) -> bool:
        entry = self._get_active_entry()
        if entry is None or entry.is_playing or entry.edit_world is None:
            return False
        root = entry.edit_world.get_entity_by_name(entity_name)
        if root is None:
            return False
        before = copy.deepcopy(entry.scene.to_dict())
        subtree = [root] + entry.edit_world.get_descendants(root.name)
        new_root_name = new_root_name or f"{root.name}_copy"
        mapping = {root.name: new_root_name}
        for entity in subtree[1:]:
            suffix = entity.name[len(root.name):] if entity.name.startswith(root.name) else f"_{entity.name}"
            mapping[entity.name] = f"{new_root_name}{suffix}"
        for entity in subtree:
            payload = entity.to_dict()
            payload.pop("id", None)
            payload["name"] = mapping[entity.name]
            if payload.get("parent") in mapping:
                payload["parent"] = mapping[payload["parent"]]
            if payload.get("prefab_root_name") in mapping:
                payload["prefab_root_name"] = mapping[payload["prefab_root_name"]]
            entry.scene.add_entity(payload)
        self._sync_feature_metadata_from_scene_links(entry)
        self._rebuild_edit_world(entry)
        entry.dirty = True
        self._record_scene_change(entry, f"duplicate_entity:{entity_name}", before)
        return True

    def copy_entity_subtree(self, entity_name: str) -> bool:
        entry = self._get_active_entry()
        if entry is None or entry.edit_world is None:
            return False
        root = entry.edit_world.get_entity_by_name(entity_name)
        if root is None:
            return False
        subtree = [root] + entry.edit_world.get_descendants(root.name)
        mapping = {entity.name: {k: v for k, v in entity.to_dict().items() if k != "id"} for entity in subtree}
        self._clipboard = [mapping[entity.name] for entity in subtree]
        self._clipboard_root_name = root.name
        return True

    def paste_copied_entities(self, target_scene_key: Optional[str] = None) -> bool:
        entry = self._resolve_entry(target_scene_key)
        if entry is None or entry.is_playing or not self._clipboard:
            return False
        before = copy.deepcopy(entry.scene.to_dict())
        names_in_scene = {item.get("name", "") for item in entry.scene.entities_data}
        mapping: dict[str, str] = {}
        for payload in self._clipboard:
            original_name = str(payload.get("name", "") or "Entity")
            candidate = original_name if original_name not in names_in_scene else self._unique_entity_name(names_in_scene, f"{original_name}_copy")
            mapping[original_name] = candidate
            names_in_scene.add(candidate)
        for payload in self._clipboard:
            cloned = copy.deepcopy(payload)
            cloned["name"] = mapping[str(payload.get("name", ""))]
            if cloned.get("parent") in mapping:
                cloned["parent"] = mapping[str(cloned["parent"])]
            entry.scene.add_entity(cloned)
        self._sync_feature_metadata_from_scene_links(entry)
        self._rebuild_edit_world(entry)
        entry.dirty = True
        self._record_scene_change(entry, f"paste_entity:{self._clipboard_root_name}", before)
        return True

    def clear_dirty(self) -> None:
        entry = self._get_active_entry()
        if entry is not None:
            entry.dirty = False

    def clear_all_dirty(self) -> None:
        for entry in self._entries.values():
            entry.dirty = False

    def begin_transaction(self, label: str = "transaction", key: Optional[str] = None) -> bool:
        entry = self._resolve_entry(key)
        if entry is None or entry.is_playing or self._active_transaction is not None:
            return False
        self._active_transaction = {
            "label": label,
            "key": entry.key,
            "before": copy.deepcopy(entry.scene.to_dict()),
            "changes": [],
        }
        self._suspend_history = True
        return True

    def apply_change(self, change: Change | dict[str, Any], key: Optional[str] = None) -> bool:
        payload = change if isinstance(change, Change) else Change.from_dict(change)
        if payload.kind == "edit_component":
            success = self.apply_edit_to_world(payload.entity, payload.component, payload.field, payload.value)
        elif payload.kind == "set_entity_property":
            success = self.update_entity_property(payload.entity, payload.field, payload.value)
        elif payload.kind == "add_component":
            success = self.add_component_to_entity(payload.entity, payload.component, payload.data)
        elif payload.kind == "remove_component":
            success = self.remove_component_from_entity(payload.entity, payload.component)
        elif payload.kind == "create_entity":
            success = self.create_entity(payload.entity, payload.data.get("components"))
        elif payload.kind == "delete_entity":
            success = self.remove_entity(payload.entity)
        else:
            success = False
        if success and self._active_transaction is not None:
            self._active_transaction["changes"].append(payload.to_dict())
        return success

    def commit_transaction(self) -> Optional[Dict[str, Any]]:
        if self._active_transaction is None:
            return None
        transaction = self._active_transaction
        entry = self._resolve_entry(transaction["key"])
        if entry is None:
            self._active_transaction = None
            self._suspend_history = False
            return None
        after = copy.deepcopy(entry.scene.to_dict())
        label = str(transaction["label"])
        key = str(transaction["key"])
        if self._history is not None and transaction["before"] != after:
            self._history.push(
                label=label,
                undo=lambda key=key, before=transaction["before"]: self._restore_scene_data_for_key(key, before),
                redo=lambda key=key, after=after: self._restore_scene_data_for_key(key, after),
            )
        result = {
            "label": label,
            "scene_key": key,
            "changes": copy.deepcopy(transaction["changes"]),
        }
        self._active_transaction = None
        self._suspend_history = False
        return result

    def rollback_transaction(self) -> bool:
        if self._active_transaction is None:
            return False
        transaction = self._active_transaction
        self._active_transaction = None
        self._suspend_history = False
        return self._restore_scene_data_for_key(str(transaction["key"]), copy.deepcopy(transaction["before"]))

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
        before = copy.deepcopy(entry.scene.to_dict())
        scene_flow = entry.scene.feature_metadata.setdefault("scene_flow", {})
        if not isinstance(scene_flow, dict):
            scene_flow = {}
            entry.scene.feature_metadata["scene_flow"] = scene_flow
        if target_path:
            scene_flow[scene_key] = target_path
        else:
            scene_flow.pop(scene_key, None)
        self._sync_scene_links_from_feature_metadata(entry)
        if entry.edit_world is not None:
            entry.edit_world.feature_metadata["scene_flow"] = copy.deepcopy(scene_flow)
        entry.dirty = True
        self._record_scene_change(entry, f"scene_flow:{scene_key}", before)
        return True

    def _get_active_entry(self) -> Optional[SceneWorkspaceEntry]:
        return self._entries.get(self._active_scene_key) if self._active_scene_key else None

    def _resolve_entry(self, key_or_path: Optional[str]) -> Optional[SceneWorkspaceEntry]:
        if key_or_path in (None, ""):
            return self._get_active_entry()
        if key_or_path in self._entries:
            return self._entries[key_or_path]
        normalized = Path(key_or_path).resolve().as_posix() if str(key_or_path).endswith(".json") or "/" in str(key_or_path) or "\\" in str(key_or_path) else str(key_or_path)
        for entry in self._entries.values():
            if entry.source_path == normalized:
                return entry
        return None

    def resolve_entry(self, key_or_path: Optional[str]) -> Optional[SceneWorkspaceEntry]:
        """Retorna la entrada de workspace para una clave o ruta dada.

        Si key_or_path es None o vacío, retorna la entrada activa.
        """
        return self._resolve_entry(key_or_path)

    def _entry_path_or_key(self, entry: Optional[SceneWorkspaceEntry]) -> str:
        return "" if entry is None else (entry.source_path or entry.key)

    def _build_scene_key(self, source_path: Optional[str], scene_name: str) -> str:
        if source_path:
            return Path(source_path).resolve().as_posix()
        key = f"untitled:{self._untitled_counter}:{scene_name}"
        self._untitled_counter += 1
        return key

    def _rebuild_edit_world(self, entry: SceneWorkspaceEntry) -> None:
        selected_name = entry.selected_entity_name or (entry.edit_world.selected_entity_name if entry.edit_world is not None else None)
        entry.edit_world = entry.scene.create_world(self._registry)
        if selected_name and entry.edit_world.get_entity_by_name(selected_name) is not None:
            entry.edit_world.selected_entity_name = selected_name
            entry.selected_entity_name = selected_name
        else:
            entry.selected_entity_name = None
            entry.edit_world.selected_entity_name = None

    def _flush_pending_edit_world(self, entry: SceneWorkspaceEntry) -> None:
        if entry.edit_world_sync_pending and entry.key == self._active_scene_key:
            self.sync_from_edit_world(force=True)

    def _sync_entry_from_edit_world(self, entry: SceneWorkspaceEntry) -> bool:
        if entry.is_playing or entry.edit_world is None:
            return False
        entry.selected_entity_name = entry.edit_world.selected_entity_name
        data = entry.edit_world.serialize()
        data["name"] = entry.scene.name
        data["rules"] = entry.scene.rules_data
        data["feature_metadata"] = entry.scene.feature_metadata
        entry.scene = Scene(data["name"], data, source_path=entry.scene.source_path)
        self._sync_feature_metadata_from_scene_links(entry)
        entry.edit_world_sync_pending = False
        return True

    def _record_scene_change(self, entry: SceneWorkspaceEntry, label: str, before: Dict[str, Any]) -> None:
        if self._history is None or self._suspend_history:
            return
        after = copy.deepcopy(entry.scene.to_dict())
        key = entry.key
        self._history.push(label=label, undo=lambda key=key, before=before: self._restore_scene_data_for_key(key, before), redo=lambda key=key, after=after: self._restore_scene_data_for_key(key, after))

    def _restore_scene_data_for_key(self, key: str, data: Dict[str, Any]) -> bool:
        entry = self._resolve_entry(key)
        if entry is None or entry.is_playing:
            return False
        entry.scene = Scene(data.get("name", entry.scene.name), copy.deepcopy(data), source_path=entry.scene.source_path)
        self._sync_scene_links_from_feature_metadata(entry)
        self._rebuild_edit_world(entry)
        entry.dirty = True
        entry.edit_world_sync_pending = False
        return True

    def _remove_entity_subtree(self, entry: SceneWorkspaceEntry, entity_name: str) -> bool:
        entities = entry.scene.data.get("entities", [])
        names_to_remove = {entity_name}
        changed = True
        while changed:
            changed = False
            for entity_data in entities:
                if entity_data.get("parent") in names_to_remove and entity_data.get("name") not in names_to_remove:
                    names_to_remove.add(entity_data.get("name"))
                    changed = True
        before_count = len(entities)
        entry.scene.data["entities"] = [entity_data for entity_data in entities if entity_data.get("name") not in names_to_remove]
        return len(entry.scene.data["entities"]) != before_count

    def _compute_world_transform_from_scene_data(
        self, entry: SceneWorkspaceEntry, entity_name: str
    ) -> Optional[tuple[float, float, float, float, float]]:
        """Walk the parent chain in scene data to compute world transform.

        Returns (world_x, world_y, world_rotation, world_scale_x, world_scale_y)
        or None if the entity or its Transform component is missing.
        """
        entity_data = entry.scene.find_entity(entity_name)
        if entity_data is None:
            return None
        transform = entity_data.get("components", {}).get("Transform")
        if transform is None:
            return None
        tx = float(transform.get("x", 0.0))
        ty = float(transform.get("y", 0.0))
        t_rot = float(transform.get("rotation", 0.0))
        t_sx = float(transform.get("scale_x", 1.0))
        t_sy = float(transform.get("scale_y", 1.0))
        parent_name = entity_data.get("parent")
        visited: set[str] = {entity_name}
        while parent_name is not None:
            if parent_name in visited:
                break
            visited.add(parent_name)
            parent_data = entry.scene.find_entity(parent_name)
            if parent_data is None:
                break
            pt = parent_data.get("components", {}).get("Transform")
            if pt is None:
                break
            tx += float(pt.get("x", 0.0))
            ty += float(pt.get("y", 0.0))
            t_rot += float(pt.get("rotation", 0.0))
            t_sx *= float(pt.get("scale_x", 1.0))
            t_sy *= float(pt.get("scale_y", 1.0))
            parent_name = parent_data.get("parent")
        return tx, ty, t_rot, t_sx, t_sy

    def _remove_single_entity(self, entry: SceneWorkspaceEntry, entity_name: str) -> bool:
        """Remove only the named entity from scene data (no cascade)."""
        entities = entry.scene.data.get("entities", [])
        before_count = len(entities)
        entry.scene.data["entities"] = [
            ed for ed in entities if ed.get("name") != entity_name
        ]
        return len(entry.scene.data["entities"]) != before_count

    def _validate_parent(self, entry: SceneWorkspaceEntry, entity_name: str, parent_name: str) -> bool:
        if entity_name == parent_name:
            return False
        target = entry.scene.find_entity(entity_name)
        parent = entry.scene.find_entity(parent_name)
        if target is None or parent is None:
            return False
        visited = {entity_name}
        current = parent_name
        while current is not None:
            if current in visited:
                return False
            visited.add(current)
            current_entity = entry.scene.find_entity(current)
            current = current_entity.get("parent") if current_entity is not None else None
        return True

    def _update_prefab_component_override(self, entry: SceneWorkspaceEntry, entity_name: str, component_name: str, property_name: str, value: Any) -> bool:
        if entry.edit_world is None:
            return False
        entity = entry.edit_world.get_entity_by_name(entity_name)
        if entity is None or entity.prefab_root_name is None:
            return False
        root_scene_data = entry.scene.find_entity(entity.prefab_root_name)
        if root_scene_data is None or "prefab_instance" not in root_scene_data:
            return False
        overrides = self._ensure_prefab_override_ops(root_scene_data)
        self._upsert_prefab_override_operation(
            overrides,
            {
                "op": "set_field",
                "target": entity.prefab_source_path or "",
                "component": component_name,
                "field": property_name,
                "value": copy.deepcopy(value),
            },
            match_keys=("op", "target", "component", "field"),
        )
        return True

    def _update_prefab_entity_override(self, entry: SceneWorkspaceEntry, entity_name: str, property_name: str, value: Any) -> bool:
        if entry.edit_world is None:
            return False
        entity = entry.edit_world.get_entity_by_name(entity_name)
        if entity is None or entity.prefab_root_name is None:
            return False
        root_scene_data = entry.scene.find_entity(entity.prefab_root_name)
        if root_scene_data is None or "prefab_instance" not in root_scene_data:
            return False
        overrides = self._ensure_prefab_override_ops(root_scene_data)
        self._upsert_prefab_override_operation(
            overrides,
            {
                "op": "set_entity_property",
                "target": entity.prefab_source_path or "",
                "field": property_name,
                "value": copy.deepcopy(value),
            },
            match_keys=("op", "target", "field"),
        )
        return True

    def _replace_prefab_component_override(self, entry: SceneWorkspaceEntry, entity_name: str, component_name: str, component_data: Dict[str, Any]) -> bool:
        if entry.edit_world is None:
            return False
        entity = entry.edit_world.get_entity_by_name(entity_name)
        if entity is None or entity.prefab_root_name is None:
            return False
        root_scene_data = entry.scene.find_entity(entity.prefab_root_name)
        if root_scene_data is None or "prefab_instance" not in root_scene_data:
            return False
        overrides = self._ensure_prefab_override_ops(root_scene_data)
        self._upsert_prefab_override_operation(
            overrides,
            {
                "op": "replace_component",
                "target": entity.prefab_source_path or "",
                "component": component_name,
                "data": copy.deepcopy(component_data),
            },
            match_keys=("op", "target", "component"),
        )
        return True

    def _remove_prefab_component_override(self, entry: SceneWorkspaceEntry, entity_name: str, component_name: str) -> bool:
        if entry.edit_world is None:
            return False
        entity = entry.edit_world.get_entity_by_name(entity_name)
        if entity is None or entity.prefab_root_name is None:
            return False
        root_scene_data = entry.scene.find_entity(entity.prefab_root_name)
        if root_scene_data is None or "prefab_instance" not in root_scene_data:
            return False
        overrides = self._ensure_prefab_override_ops(root_scene_data)
        self._remove_prefab_override_operations(
            overrides,
            target=entity.prefab_source_path or "",
            component=component_name,
        )
        overrides.setdefault("operations", []).append(
            {
                "op": "remove_component",
                "target": entity.prefab_source_path or "",
                "component": component_name,
            }
        )
        return True

    def _ensure_prefab_override_ops(self, root_scene_data: Dict[str, Any]) -> Dict[str, Any]:
        prefab_instance = root_scene_data.setdefault("prefab_instance", {})
        overrides = prefab_instance.setdefault("overrides", {})
        if "operations" in overrides:
            return overrides
        operations: list[dict[str, Any]] = []
        for target_path, payload in list(overrides.items()):
            if not isinstance(payload, dict):
                continue
            for field_name in ("active", "tag", "layer", "parent"):
                if field_name in payload:
                    operations.append(
                        {
                            "op": "set_entity_property",
                            "target": target_path,
                            "field": field_name,
                            "value": copy.deepcopy(payload[field_name]),
                        }
                    )
            components = payload.get("components", {})
            if isinstance(components, dict):
                for component_name, component_payload in components.items():
                    operations.append(
                        {
                            "op": "replace_component",
                            "target": target_path,
                            "component": component_name,
                            "data": copy.deepcopy(component_payload),
                        }
                    )
        prefab_instance["overrides"] = {"operations": operations}
        return prefab_instance["overrides"]

    def _upsert_prefab_override_operation(
        self,
        overrides: Dict[str, Any],
        operation: Dict[str, Any],
        *,
        match_keys: tuple[str, ...],
    ) -> None:
        operations = overrides.setdefault("operations", [])
        for index, existing in enumerate(operations):
            if not isinstance(existing, dict):
                continue
            if all(existing.get(key) == operation.get(key) for key in match_keys):
                operations[index] = operation
                return
        operations.append(operation)

    def _remove_prefab_override_operations(
        self,
        overrides: Dict[str, Any],
        *,
        target: str,
        component: str | None = None,
    ) -> None:
        operations = overrides.setdefault("operations", [])
        filtered = []
        for operation in operations:
            if not isinstance(operation, dict):
                filtered.append(operation)
                continue
            if operation.get("target") != target:
                filtered.append(operation)
                continue
            if component is not None and operation.get("component") != component:
                filtered.append(operation)
                continue
        overrides["operations"] = filtered

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
                if flow_key and flow_key in scene_flow:
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
