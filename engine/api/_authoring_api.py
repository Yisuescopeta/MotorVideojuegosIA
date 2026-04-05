from __future__ import annotations

import copy
from typing import Any, Dict, Optional

from engine.api._context import EngineAPIComponent
from engine.api.types import ActionResult
from engine.authoring.changes import Change
from engine.components.rigidbody import RigidBody
from engine.components.tilemap import Tilemap

_UNSET = object()


class AuthoringAPI(EngineAPIComponent):
    """Authoring-oriented entity, component, prefab, and serialized data endpoints."""

    def begin_transaction(self, label: str = "transaction") -> ActionResult:
        if self.scene_manager is None:
            return self.fail("SceneManager not ready")
        success = self.scene_manager.begin_transaction(label=label)
        return self.ok("Transaction started", {"label": label}) if success else self.fail("Transaction start failed")

    def apply_change(self, change: Dict[str, Any]) -> ActionResult:
        if self.scene_manager is None:
            return self.fail("SceneManager not ready")
        success = self.scene_manager.apply_change(Change.from_dict(change))
        return self.ok("Change applied", {"change": change}) if success else self.fail("Change apply failed")

    def commit_transaction(self) -> ActionResult:
        if self.scene_manager is None:
            return self.fail("SceneManager not ready")
        result = self.scene_manager.commit_transaction()
        return self.ok("Transaction committed", result) if result is not None else self.fail("Transaction commit failed")

    def rollback_transaction(self) -> ActionResult:
        if self.scene_manager is None:
            return self.fail("SceneManager not ready")
        success = self.scene_manager.rollback_transaction()
        return self.ok("Transaction rolled back") if success else self.fail("Transaction rollback failed")

    def create_entity(self, name: str, components: Optional[Dict[str, Dict[str, Any]]] = None) -> ActionResult:
        self.ensure_edit_mode()
        if self.scene_manager is None:
            return self.fail("SceneManager not ready")
        success = self.scene_manager.create_entity(name, components=components)
        return self.ok("Entity created", {"entity": name}) if success else self.fail("Entity already exists")

    def delete_entity(self, name: str) -> ActionResult:
        self.ensure_edit_mode()
        if self.scene_manager is None:
            return self.fail("SceneManager not ready")
        success = self.scene_manager.remove_entity(name)
        return self.ok("Entity removed", {"entity": name}) if success else self.fail("Entity not found")

    def set_entity_active(self, name: str, active: bool) -> ActionResult:
        self.ensure_edit_mode()
        return self._apply_entity_property(name, "active", active, "Entity active updated")

    def set_entity_tag(self, name: str, tag: str) -> ActionResult:
        self.ensure_edit_mode()
        return self._apply_entity_property(name, "tag", tag, "Entity tag updated")

    def set_entity_layer(self, name: str, layer: str) -> ActionResult:
        self.ensure_edit_mode()
        return self._apply_entity_property(name, "layer", layer, "Entity layer updated")

    def set_entity_parent(self, name: str, parent_name: Optional[str]) -> ActionResult:
        self.ensure_edit_mode()
        if self.scene_manager is None:
            return self.fail("SceneManager not ready")
        success = self.scene_manager.set_entity_parent(name, parent_name)
        return self.ok("Entity parent updated", {"entity": name, "parent": parent_name}) if success else self.fail("Entity parent update failed")

    def create_child_entity(
        self,
        parent_name: str,
        name: str,
        components: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> ActionResult:
        self.ensure_edit_mode()
        if self.scene_manager is None:
            return self.fail("SceneManager not ready")
        success = self.scene_manager.create_child_entity(parent_name, name, components=components)
        return self.ok("Child entity created", {"entity": name, "parent": parent_name}) if success else self.fail("Child entity creation failed")

    def add_component(self, entity_name: str, component_name: str, data: Optional[Dict[str, Any]] = None) -> ActionResult:
        self.ensure_edit_mode()
        if self.scene_manager is None:
            return self.fail("SceneManager not ready")
        success = self.scene_manager.add_component_to_entity(entity_name, component_name, component_data=data)
        return self.ok("Component added", {"entity": entity_name, "component": component_name}) if success else self.fail("Component add failed")

    def remove_component(self, entity_name: str, component_name: str) -> ActionResult:
        self.ensure_edit_mode()
        if self.scene_manager is None:
            return self.fail("SceneManager not ready")
        success = self.scene_manager.remove_component_from_entity(entity_name, component_name)
        return self.ok("Component removed", {"entity": entity_name, "component": component_name}) if success else self.fail("Component remove failed")

    def edit_component(self, entity_name: str, component: str, property: str, value: Any) -> ActionResult:
        self.ensure_edit_mode()
        if self.scene_manager is None:
            return self.fail("SceneManager not ready")
        success = self.scene_manager.apply_edit_to_world(entity_name, component, property, value)
        return self.ok("Edit applied") if success else self.fail("Edit failed (check names/property)")

    def set_component_enabled(self, entity_name: str, component_name: str, enabled: bool) -> ActionResult:
        return self.edit_component(entity_name, component_name, "enabled", enabled)

    def create_camera2d(
        self,
        name: str,
        transform: Optional[Dict[str, Any]] = None,
        camera: Optional[Dict[str, Any]] = None,
    ) -> ActionResult:
        self.ensure_edit_mode()
        components: Dict[str, Dict[str, Any]] = {
            "Transform": {
                "enabled": True,
                "x": 0.0,
                "y": 0.0,
                "rotation": 0.0,
                "scale_x": 1.0,
                "scale_y": 1.0,
            },
            "Camera2D": {
                "enabled": True,
                "offset_x": 0.0,
                "offset_y": 0.0,
                "zoom": 1.0,
                "rotation": 0.0,
                "is_primary": True,
                "follow_entity": "",
                "framing_mode": "platformer",
                "dead_zone_width": 0.0,
                "dead_zone_height": 0.0,
                "clamp_left": None,
                "clamp_right": None,
                "clamp_top": None,
                "clamp_bottom": None,
                "recenter_on_play": True,
            },
        }
        if transform:
            components["Transform"].update(transform)
        if camera:
            components["Camera2D"].update(camera)
        return self.create_entity(name, components=components)

    def update_camera2d(self, entity_name: str, properties: Dict[str, Any]) -> ActionResult:
        self.ensure_edit_mode()
        for property_name, value in properties.items():
            result = self.edit_component(entity_name, "Camera2D", property_name, value)
            if not result["success"]:
                return result
        return self.ok("Camera2D updated", {"entity": entity_name})

    def set_camera_framing(self, entity_name: str, framing: Dict[str, Any]) -> ActionResult:
        return self.update_camera2d(entity_name, framing)

    def create_input_map(self, name: str, bindings: Optional[Dict[str, Any]] = None) -> ActionResult:
        self.ensure_edit_mode()
        components: Dict[str, Dict[str, Any]] = {
            "Transform": {
                "enabled": True,
                "x": 0.0,
                "y": 0.0,
                "rotation": 0.0,
                "scale_x": 1.0,
                "scale_y": 1.0,
            },
            "InputMap": {
                "enabled": True,
                "move_left": "A,LEFT",
                "move_right": "D,RIGHT",
                "move_up": "W,UP",
                "move_down": "S,DOWN",
                "action_1": "SPACE",
                "action_2": "ENTER",
            },
        }
        if bindings:
            components["InputMap"].update(bindings)
        return self.create_entity(name, components=components)

    def update_input_map(self, entity_name: str, bindings: Dict[str, Any]) -> ActionResult:
        self.ensure_edit_mode()
        for property_name, value in bindings.items():
            result = self.edit_component(entity_name, "InputMap", property_name, value)
            if not result["success"]:
                return result
        return self.ok("InputMap updated", {"entity": entity_name})

    def create_audio_source(
        self,
        name: str,
        transform: Optional[Dict[str, Any]] = None,
        audio: Optional[Dict[str, Any]] = None,
    ) -> ActionResult:
        self.ensure_edit_mode()
        components: Dict[str, Dict[str, Any]] = {
            "Transform": {
                "enabled": True,
                "x": 0.0,
                "y": 0.0,
                "rotation": 0.0,
                "scale_x": 1.0,
                "scale_y": 1.0,
            },
            "AudioSource": {
                "enabled": True,
                "asset": {"guid": "", "path": ""},
                "asset_path": "",
                "volume": 1.0,
                "pitch": 1.0,
                "loop": False,
                "play_on_awake": False,
                "spatial_blend": 0.0,
            },
        }
        if transform:
            components["Transform"].update(transform)
        if audio:
            components["AudioSource"].update(audio)
        return self.create_entity(name, components=components)

    def update_audio_source(self, entity_name: str, properties: Dict[str, Any]) -> ActionResult:
        self.ensure_edit_mode()
        for property_name, value in properties.items():
            result = self.edit_component(entity_name, "AudioSource", property_name, value)
            if not result["success"]:
                return result
        return self.ok("AudioSource updated", {"entity": entity_name})

    def add_script_behaviour(
        self,
        entity_name: str,
        module_path: str,
        public_data: Optional[Dict[str, Any]] = None,
        run_in_edit_mode: bool = False,
        enabled: bool = True,
    ) -> ActionResult:
        self.ensure_edit_mode()
        return self.add_component(
            entity_name,
            "ScriptBehaviour",
            {
                "enabled": enabled,
                "script": {"guid": "", "path": ""},
                "module_path": module_path,
                "run_in_edit_mode": run_in_edit_mode,
                "public_data": public_data or {},
            },
        )

    def update_script_behaviour(self, entity_name: str, properties: Dict[str, Any]) -> ActionResult:
        self.ensure_edit_mode()
        for property_name, value in properties.items():
            result = self.edit_component(entity_name, "ScriptBehaviour", property_name, value)
            if not result["success"]:
                return result
        return self.ok("ScriptBehaviour updated", {"entity": entity_name})

    def set_script_public_data(self, entity_name: str, public_data: Dict[str, Any]) -> ActionResult:
        self.ensure_edit_mode()
        return self.edit_component(entity_name, "ScriptBehaviour", "public_data", public_data)

    def set_feature_metadata(self, key: str, value: Any) -> ActionResult:
        self.ensure_edit_mode()
        if self.scene_manager is None:
            return self.fail("No scene loaded")
        if not self.scene_manager.set_feature_metadata(key, value):
            return self.fail("Feature metadata update failed")
        return self.ok("Feature metadata updated", {"key": key})

    def set_sorting_layers(self, order: list[str]) -> ActionResult:
        self.ensure_edit_mode()
        metadata = self.api.get_feature_metadata()
        render_2d = dict(metadata.get("render_2d", {}))
        render_2d["sorting_layers"] = self.normalize_sorting_layers(order)
        return self.set_feature_metadata("render_2d", render_2d)

    def set_render_order(self, entity_name: str, sorting_layer: str, order_in_layer: int) -> ActionResult:
        self.ensure_edit_mode()
        self.require_entity(entity_name)
        layer_name = sorting_layer.strip() or "Default"
        current_layers = self.normalize_sorting_layers(
            self.api.get_feature_metadata().get("render_2d", {}).get("sorting_layers", ["Default"])
        )
        if layer_name not in current_layers:
            return self.fail(f"Sorting layer '{layer_name}' is not configured")
        clamped_order = self.clamp_render_order(order_in_layer)
        has_component = self.load_component_payload(entity_name, "RenderOrder2D") is not None
        if not has_component:
            return self.add_component(
                entity_name,
                "RenderOrder2D",
                {"enabled": True, "sorting_layer": layer_name, "order_in_layer": clamped_order},
            )
        result = self.edit_component(entity_name, "RenderOrder2D", "sorting_layer", layer_name)
        if not result["success"]:
            return result
        return self.edit_component(entity_name, "RenderOrder2D", "order_in_layer", clamped_order)

    def set_physics_layer_collision(self, layer_a: str, layer_b: str, enabled: bool) -> ActionResult:
        self.ensure_edit_mode()
        metadata = self.api.get_feature_metadata()
        physics_2d = dict(metadata.get("physics_2d", {}))
        matrix = dict(physics_2d.get("layer_matrix", {}))
        matrix[f"{layer_a}|{layer_b}"] = bool(enabled)
        matrix[f"{layer_b}|{layer_a}"] = bool(enabled)
        physics_2d["layer_matrix"] = matrix
        return self.set_feature_metadata("physics_2d", physics_2d)

    def set_physics_backend(self, backend_name: str) -> ActionResult:
        self.ensure_edit_mode()
        normalized = str(backend_name or "").strip() or "legacy_aabb"
        if self.game is None or not self.game.knows_physics_backend(normalized):
            return self.fail(f"Unsupported physics backend: {normalized}")
        metadata = self.api.get_feature_metadata()
        physics_2d = dict(metadata.get("physics_2d", {}))
        physics_2d["backend"] = normalized
        result = self.set_feature_metadata("physics_2d", physics_2d)
        if result["success"] and self.game is not None:
            self.game.refresh_runtime_physics_backend()
        return result

    def set_rigidbody_constraints(self, entity_name: str, constraints: list[str]) -> ActionResult:
        self.ensure_edit_mode()
        normalized = RigidBody.normalize_constraints(constraints)
        invalid = [value for value in constraints if str(value).strip() not in RigidBody.VALID_CONSTRAINTS]
        if invalid:
            return self.fail(f"Unsupported constraints: {invalid}")
        if not normalized:
            normalized = ["None"]
        freeze_x = "FreezePositionX" in normalized
        freeze_y = "FreezePositionY" in normalized

        result = self.edit_component(entity_name, "RigidBody", "freeze_x", freeze_x)
        if not result["success"]:
            return result
        result = self.edit_component(entity_name, "RigidBody", "freeze_y", freeze_y)
        if not result["success"]:
            return result
        return self.edit_component(entity_name, "RigidBody", "constraints", normalized)

    def create_tilemap(
        self,
        entity_name: str,
        *,
        cell_width: int = 16,
        cell_height: int = 16,
        orientation: str = "orthogonal",
        tileset: str = "",
        layers: Optional[list[Dict[str, Any]]] = None,
    ) -> ActionResult:
        self.ensure_edit_mode()
        if self.scene_manager is None:
            return self.fail("SceneManager not ready")
        has_tilemap = self.load_component_payload(entity_name, "Tilemap") is not None
        tileset_ref = self.api.get_asset_reference(tileset) if tileset else {"guid": "", "path": ""}
        payload = Tilemap(
            cell_width=cell_width,
            cell_height=cell_height,
            orientation=orientation,
            tileset=tileset_ref if (tileset_ref.get("guid") or tileset_ref.get("path")) else tileset,
            tileset_path=tileset_ref.get("path", "") or tileset,
            layers=layers or [],
        ).to_dict()
        success = (
            self.scene_manager.replace_component_data(entity_name, "Tilemap", payload)
            if has_tilemap
            else self.scene_manager.add_component_to_entity(entity_name, "Tilemap", payload)
        )
        return self.ok("Tilemap updated", {"entity": entity_name}) if success else self.fail("Tilemap update failed")

    def set_tilemap_tile(
        self,
        entity_name: str,
        layer_name: str,
        x: int,
        y: int,
        tile_id: str,
        *,
        source: str = "",
        flags: Optional[list[str]] = None,
        tags: Optional[list[str]] = None,
        custom: Optional[Dict[str, Any]] = None,
    ) -> ActionResult:
        self.ensure_edit_mode()
        if self.scene_manager is None:
            return self.fail("SceneManager not ready")
        payload = self._load_tilemap_payload(entity_name)
        if payload is None:
            return self.fail("Tilemap not found")
        tilemap = Tilemap.from_dict(payload)
        source_ref = self.api.get_asset_reference(source) if source else {}
        tilemap.set_tile(
            layer_name,
            x,
            y,
            tile_id,
            source=source_ref if (source_ref.get("guid") or source_ref.get("path")) else source,
            flags=flags,
            tags=tags,
            custom=custom,
        )
        success = self.scene_manager.replace_component_data(entity_name, "Tilemap", tilemap.to_dict())
        return self.ok("Tilemap tile updated", {"entity": entity_name, "layer": layer_name, "x": x, "y": y}) if success else self.fail("Tilemap tile update failed")

    def clear_tilemap_tile(self, entity_name: str, layer_name: str, x: int, y: int) -> ActionResult:
        self.ensure_edit_mode()
        if self.scene_manager is None:
            return self.fail("SceneManager not ready")
        payload = self._load_tilemap_payload(entity_name)
        if payload is None:
            return self.fail("Tilemap not found")
        tilemap = Tilemap.from_dict(payload)
        tilemap.clear_tile(layer_name, x, y)
        success = self.scene_manager.replace_component_data(entity_name, "Tilemap", tilemap.to_dict())
        return self.ok("Tilemap tile cleared", {"entity": entity_name, "layer": layer_name, "x": x, "y": y}) if success else self.fail("Tilemap tile clear failed")

    def get_tilemap(self, entity_name: str) -> Dict[str, Any]:
        payload = self._load_tilemap_payload(entity_name)
        return payload or {}

    def list_animator_states(self, entity_name: str) -> list[Dict[str, Any]]:
        entity = self.require_entity(entity_name)
        from engine.components.animator import Animator

        animator = entity.get_component(Animator)
        if animator is None:
            return []
        result: list[Dict[str, Any]] = []
        for state_name, state_data in animator.to_dict().get("animations", {}).items():
            payload = dict(state_data)
            payload["state_name"] = state_name
            payload["is_default"] = animator.default_state == state_name
            result.append(payload)
        return result

    def set_animator_sprite_sheet(self, entity_name: str, asset_path: str) -> ActionResult:
        self.ensure_edit_mode()
        return self.edit_component(entity_name, "Animator", "sprite_sheet", asset_path)

    def upsert_animator_state(
        self,
        entity_name: str,
        state_name: str,
        slice_names: list[str],
        fps: float,
        loop: bool,
        on_complete: Optional[str],
        set_default: bool = False,
    ) -> ActionResult:
        self.ensure_edit_mode()
        if self.scene_manager is None:
            return self.fail("SceneManager not ready")
        if not state_name.strip():
            return self.fail("Animator state name is required")
        payload = self._load_animator_payload(entity_name)
        if payload is None:
            return self.fail("Animator not found")
        animations = payload.setdefault("animations", {})
        existing = dict(animations.get(state_name, {"frames": [0]}))
        existing["slice_names"] = list(slice_names)
        existing["fps"] = float(fps)
        existing["loop"] = bool(loop)
        existing["on_complete"] = on_complete if (on_complete in animations and on_complete != state_name) else None
        animations[state_name] = existing
        if set_default or not payload.get("default_state"):
            payload["default_state"] = state_name
        if payload.get("current_state") not in animations:
            payload["current_state"] = payload["default_state"]
        success = self.scene_manager.replace_component_data(entity_name, "Animator", payload)
        return self.ok("Animator state updated", {"entity": entity_name, "state": state_name}) if success else self.fail("Animator state update failed")

    def set_animator_state_frames(
        self,
        entity_name: str,
        state_name: str,
        slice_names: list[str],
        fps: Optional[float] = None,
        loop: Optional[bool] = None,
        on_complete: Any = _UNSET,
        set_default: bool = False,
    ) -> ActionResult:
        self.ensure_edit_mode()
        if self.scene_manager is None:
            return self.fail("SceneManager not ready")
        payload = self._load_animator_payload(entity_name)
        if payload is None:
            return self.fail("Animator not found")
        animations = payload.setdefault("animations", {})
        if state_name not in animations:
            return self.fail("Animator state not found")
        state = dict(animations.get(state_name, {}))
        state["slice_names"] = list(slice_names)
        if fps is not None:
            state["fps"] = float(fps)
        if loop is not None:
            state["loop"] = bool(loop)
        if on_complete is not _UNSET:
            state["on_complete"] = on_complete if (on_complete in animations and on_complete != state_name) else None
        animations[state_name] = state
        if set_default or not payload.get("default_state"):
            payload["default_state"] = state_name
        if payload.get("current_state") not in animations:
            payload["current_state"] = payload["default_state"]
        success = self.scene_manager.replace_component_data(entity_name, "Animator", payload)
        return self.ok("Animator frames updated", {"entity": entity_name, "state": state_name}) if success else self.fail("Animator frames update failed")

    def remove_animator_state(self, entity_name: str, state_name: str) -> ActionResult:
        self.ensure_edit_mode()
        if self.scene_manager is None:
            return self.fail("SceneManager not ready")
        payload = self._load_animator_payload(entity_name)
        if payload is None:
            return self.fail("Animator not found")
        animations = payload.setdefault("animations", {})
        if state_name not in animations:
            return self.fail("Animator state not found")
        del animations[state_name]
        next_default = next(iter(animations.keys()), "")
        if payload.get("default_state") == state_name:
            payload["default_state"] = next_default
        if payload.get("current_state") == state_name:
            payload["current_state"] = payload.get("default_state", next_default)
        for animation in animations.values():
            if animation.get("on_complete") == state_name:
                animation["on_complete"] = None
        success = self.scene_manager.replace_component_data(entity_name, "Animator", payload)
        return self.ok("Animator state removed", {"entity": entity_name, "state": state_name}) if success else self.fail("Animator state remove failed")

    def duplicate_animator_state(self, entity_name: str, source_state: str, new_state_name: Optional[str] = None) -> ActionResult:
        self.ensure_edit_mode()
        if self.scene_manager is None:
            return self.fail("SceneManager not ready")
        if not source_state.strip():
            return self.fail("Source state name is required")
        payload = self._load_animator_payload(entity_name)
        if payload is None:
            return self.fail("Animator not found")
        animations = payload.setdefault("animations", {})
        if source_state not in animations:
            return self.fail(f"Source state '{source_state}' not found")

        base_name = new_state_name.strip() if new_state_name else f"{source_state}_copy"
        final_name = base_name
        suffix = 1
        while final_name in animations:
            final_name = f"{base_name}_{suffix}"
            suffix += 1

        animations[final_name] = copy.deepcopy(animations[source_state])
        success = self.scene_manager.replace_component_data(entity_name, "Animator", payload)
        return self.ok("Animator state duplicated", {"entity": entity_name, "state": final_name}) if success else self.fail("Animator state duplicate failed")

    def rename_animator_state(self, entity_name: str, old_name: str, new_name: str) -> ActionResult:
        self.ensure_edit_mode()
        if self.scene_manager is None:
            return self.fail("SceneManager not ready")
        if not old_name.strip() or not new_name.strip():
            return self.fail("State names cannot be empty")
        if old_name == new_name:
            return self.ok("No rename needed", {"entity": entity_name, "state": new_name})
        payload = self._load_animator_payload(entity_name)
        if payload is None:
            return self.fail("Animator not found")
        animations = payload.setdefault("animations", {})
        if old_name not in animations:
            return self.fail(f"State '{old_name}' not found")
        if new_name in animations:
            return self.fail(f"State '{new_name}' already exists")

        animations[new_name] = animations.pop(old_name)
        if payload.get("default_state") == old_name:
            payload["default_state"] = new_name
        if payload.get("current_state") == old_name:
            payload["current_state"] = new_name
        for animation in animations.values():
            if animation.get("on_complete") == old_name:
                animation["on_complete"] = new_name

        success = self.scene_manager.replace_component_data(entity_name, "Animator", payload)
        return self.ok("Animator state renamed", {"entity": entity_name, "state": new_name}) if success else self.fail("Animator state rename failed")

    def set_animator_flip(self, entity_name: str, flip_x: Optional[bool] = None, flip_y: Optional[bool] = None) -> ActionResult:
        self.ensure_edit_mode()
        animator_data = self._load_animator_payload(entity_name)
        if animator_data is None:
            return self.fail("Animator not found")
        if flip_x is not None:
            animator_data["flip_x"] = bool(flip_x)
        if flip_y is not None:
            animator_data["flip_y"] = bool(flip_y)
        if self.scene_manager is None:
            return self.fail("SceneManager not ready")
        success = self.scene_manager.replace_component_data(entity_name, "Animator", animator_data)
        return self.ok("Animator flip updated", {"entity": entity_name}) if success else self.fail("Animator flip update failed")

    def set_animator_speed(self, entity_name: str, speed: float) -> ActionResult:
        self.ensure_edit_mode()
        animator_data = self._load_animator_payload(entity_name)
        if animator_data is None:
            return self.fail("Animator not found")
        animator_data["speed"] = max(0.01, float(speed))
        if self.scene_manager is None:
            return self.fail("SceneManager not ready")
        success = self.scene_manager.replace_component_data(entity_name, "Animator", animator_data)
        return self.ok("Animator speed updated", {"entity": entity_name, "speed": animator_data["speed"]}) if success else self.fail("Animator speed update failed")

    def get_animator_info(self, entity_name: str) -> Dict[str, Any]:
        animator_data = self._load_animator_payload(entity_name)
        if animator_data is None:
            return {"exists": False}

        animations = animator_data.get("animations", {})
        states_info = []
        for state_name, state_data in animations.items():
            frame_count = len(state_data.get("slice_names", [])) or len(state_data.get("frames", []))
            duration = (frame_count / max(0.001, state_data.get("fps", 8.0))) if frame_count > 0 else 0.0
            states_info.append({
                "name": state_name,
                "frame_count": frame_count,
                "fps": state_data.get("fps", 8.0),
                "loop": state_data.get("loop", True),
                "on_complete": state_data.get("on_complete"),
                "duration_seconds": round(duration, 3),
                "is_default": animator_data.get("default_state", "") == state_name,
            })

        return {
            "exists": True,
            "sprite_sheet": animator_data.get("sprite_sheet_path", ""),
            "frame_width": animator_data.get("frame_width", 32),
            "frame_height": animator_data.get("frame_height", 32),
            "flip_x": animator_data.get("flip_x", False),
            "flip_y": animator_data.get("flip_y", False),
            "speed": animator_data.get("speed", 1.0),
            "default_state": animator_data.get("default_state", ""),
            "current_state": animator_data.get("current_state", ""),
            "states": states_info,
        }

    def create_animator_state(
        self,
        entity_name: str,
        state_name: str,
        slice_names: Optional[list[str]] = None,
        fps: float = 8.0,
        loop: bool = True,
        on_complete: Optional[str] = None,
    ) -> ActionResult:
        return self.upsert_animator_state(
            entity_name,
            state_name,
            slice_names or [],
            fps=fps,
            loop=loop,
            on_complete=on_complete,
            set_default=False,
        )

    def _apply_entity_property(self, name: str, property_name: str, value: Any, message: str) -> ActionResult:
        if self.scene_manager is None:
            return self.fail("SceneManager not ready")
        success = self.scene_manager.update_entity_property(name, property_name, value)
        return self.ok(message, {"entity": name}) if success else self.fail("Entity property update failed")

    def _load_animator_payload(self, entity_name: str) -> Optional[Dict[str, Any]]:
        return self.load_component_payload(entity_name, "Animator")

    def _load_tilemap_payload(self, entity_name: str) -> Optional[Dict[str, Any]]:
        return self.load_component_payload(entity_name, "Tilemap")
