from __future__ import annotations

import copy
from typing import Any, Callable, Dict, Optional, Union

from engine.api._context import EngineAPIComponent
from engine.api.types import ActionResult
from engine.authoring.changes import Change
from engine.components.rigidbody import RigidBody
from engine.components.tilemap import Tilemap

_UNSET: Any = object()


class AuthoringAPI(EngineAPIComponent):
    """Authoring-oriented entity, component, prefab, and serialized data endpoints."""

    def begin_transaction(self, label: str = "transaction") -> ActionResult:
        """Start an undoable authoring transaction for the active scene.

        Args:
            label: Human-readable label for the undo history entry.

        Returns:
            ActionResult with transaction started confirmation, or failure if
            SceneManager is not ready.
        """
        if self.scene_authoring is None:
            return self.fail("SceneManager not ready")
        success = self.scene_authoring.begin_transaction(label=label)
        return self.ok("Transaction started", {"label": label}) if success else self.fail("Transaction start failed")

    def apply_change(self, change: dict[str, Any]) -> ActionResult:
        """Apply a single low-level authoring change to the active scene.

        Args:
            change: Dictionary representation of a Change object.

        Returns:
            ActionResult confirming the change was applied, or failure otherwise.
        """
        if self.scene_authoring is None:
            return self.fail("SceneManager not ready")
        success = self.scene_authoring.apply_change(Change.from_dict(change))
        return self.ok("Change applied", {"change": change}) if success else self.fail("Change apply failed")

    def commit_transaction(self) -> ActionResult:
        """Commit and close the current open transaction.

        Returns:
            ActionResult with transaction result data, or failure if commit fails.
        """
        if self.scene_authoring is None:
            return self.fail("SceneManager not ready")
        result = self.scene_authoring.commit_transaction()
        return self.ok("Transaction committed", result) if result is not None else self.fail("Transaction commit failed")

    def rollback_transaction(self) -> ActionResult:
        """Roll back the current open transaction, discarding all intermediate changes.

        Returns:
            ActionResult indicating rollback success or failure.
        """
        if self.scene_authoring is None:
            return self.fail("SceneManager not ready")
        success = self.scene_authoring.rollback_transaction()
        return self.ok("Transaction rolled back") if success else self.fail("Transaction rollback failed")

    def create_entity(
        self,
        name: str,
        components: Optional[Dict[str, dict[str, Any]]] = None,
        *,
        tag: Optional[str] = None,
        layer: Optional[str] = None,
        active: Optional[bool] = None,
    ) -> ActionResult:
        """Create a new entity in the active scene with optional component payloads.

        Args:
            name: Unique entity name within the scene.
            components: Mapping of component type names to their data dictionaries.
                Keys should match registered component names (e.g. "Transform",
                "RigidBody"). Defaults to None (no components).
            tag: Optional tag string applied after creation.
            layer: Optional layer name applied after creation.
            active: Optional active state applied after creation.

        Returns:
            ActionResult confirming entity creation or reporting that the name
            already exists.

        Example:
            >>> api.authoring.create_entity("Player", {"Transform": {"x": 0, "y": 0}})
            {'success': True, 'message': 'Entity created', 'data': {'entity': 'Player'}}
        """
        self.ensure_edit_mode()
        if self.scene_authoring is None:
            return self.fail("SceneManager not ready")
        success = self.scene_authoring.create_entity(name, components=components)
        if not success:
            return self.fail("Entity already exists")

        if tag is not None:
            result = self._apply_entity_property(name, "tag", tag, "Entity tag updated")
            if not result["success"]:
                return result
        if layer is not None:
            result = self._apply_entity_property(name, "layer", layer, "Entity layer updated")
            if not result["success"]:
                return result
        if active is not None:
            result = self._apply_entity_property(name, "active", active, "Entity active updated")
            if not result["success"]:
                return result

        return self.ok("Entity created", {"entity": name})

    def delete_entity(self, name: str) -> ActionResult:
        """Delete an entity and its children from the active scene.

        Args:
            name: Name of the entity to remove.

        Returns:
            ActionResult confirming removal or reporting that the entity was not found.
        """
        self.ensure_edit_mode()
        if self.scene_authoring is None:
            return self.fail("SceneManager not ready")
        success = self.scene_authoring.remove_entity(name)
        return self.ok("Entity removed", {"entity": name}) if success else self.fail("Entity not found")

    def set_entity_active(self, name: str, active: bool) -> ActionResult:
        """Enable or disable an entity in the active scene.

        Args:
            name: Name of the entity.
            active: True to activate, False to deactivate.

        Returns:
            ActionResult confirming the active state update.
        """
        self.ensure_edit_mode()
        return self._apply_entity_property(name, "active", active, "Entity active updated")

    def set_entity_tag(self, name: str, tag: str) -> ActionResult:
        """Assign a tag string to an entity for grouping and queries.

        Args:
            name: Name of the entity.
            tag: Tag value (e.g. "Player", "Enemy", "Collectible").

        Returns:
            ActionResult confirming the tag update.
        """
        self.ensure_edit_mode()
        return self._apply_entity_property(name, "tag", tag, "Entity tag updated")

    def set_entity_layer(self, name: str, layer: str) -> ActionResult:
        """Assign a rendering/physics layer to an entity.

        Args:
            name: Name of the entity.
            layer: Layer name (e.g. "Default", "UI", "Background").

        Returns:
            ActionResult confirming the layer update.
        """
        self.ensure_edit_mode()
        return self._apply_entity_property(name, "layer", layer, "Entity layer updated")

    def set_entity_parent(self, name: str, parent_name: Optional[str]) -> ActionResult:
        """Set or clear the parent transform of an entity.

        Args:
            name: Name of the child entity.
            parent_name: Name of the parent entity, or None to unparent.

        Returns:
            ActionResult confirming the parent update or failure.
        """
        self.ensure_edit_mode()
        if self.scene_authoring is None:
            return self.fail("SceneManager not ready")
        success = self.scene_authoring.set_entity_parent(name, parent_name)
        return self.ok("Entity parent updated", {"entity": name, "parent": parent_name}) if success else self.fail("Entity parent update failed")

    def create_child_entity(
        self,
        parent_name: str,
        name: str,
        components: Optional[Dict[str, dict[str, Any]]] = None,
    ) -> ActionResult:
        """Create a new entity as a child of an existing parent entity.

        Args:
            parent_name: Name of the parent entity.
            name: Unique name for the new child entity.
            components: Optional component data mapping, same format as create_entity.

        Returns:
            ActionResult confirming creation or reporting failure.
        """
        self.ensure_edit_mode()
        if self.scene_authoring is None:
            return self.fail("SceneManager not ready")
        success = self.scene_authoring.create_child_entity(parent_name, name, components=components)
        return self.ok("Child entity created", {"entity": name, "parent": parent_name}) if success else self.fail("Child entity creation failed")

    def add_component(self, entity_name: str, component_name: str, data: Optional[dict[str, Any]] = None) -> ActionResult:
        """Attach a new component to an existing entity.

        Args:
            entity_name: Name of the target entity.
            component_name: Registered component type name (e.g. "RigidBody",
                "Animator", "ScriptBehaviour").
            data: Component property payload. Defaults to None (component defaults).

        Returns:
            ActionResult confirming the component was added or reporting failure.
        """
        self.ensure_edit_mode()
        if self.scene_authoring is None:
            return self.fail("SceneManager not ready")
        success = self.scene_authoring.add_component_to_entity(entity_name, component_name, component_data=data)
        return self.ok("Component added", {"entity": entity_name, "component": component_name}) if success else self.fail("Component add failed")

    def replace_component_data(self, entity_name: str, component_name: str, data: dict[str, Any]) -> ActionResult:
        """Fully replace the data payload of an existing component.

        Args:
            entity_name: Name of the target entity.
            component_name: Component type name to replace.
            data: Complete new component data dictionary.

        Returns:
            ActionResult confirming replacement or failure.
        """
        self.ensure_edit_mode()
        if self.scene_authoring is None:
            return self.fail("SceneManager not ready")
        success = self.scene_authoring.replace_component_data(entity_name, component_name, data)
        return self.ok("Component replaced", {"entity": entity_name, "component": component_name}) if success else self.fail("Component replace failed")

    def remove_component(self, entity_name: str, component_name: str) -> ActionResult:
        """Remove a component from an entity.

        Args:
            entity_name: Name of the target entity.
            component_name: Component type name to remove.

        Returns:
            ActionResult confirming removal or failure.
        """
        self.ensure_edit_mode()
        if self.scene_authoring is None:
            return self.fail("SceneManager not ready")
        success = self.scene_authoring.remove_component_from_entity(entity_name, component_name)
        return self.ok("Component removed", {"entity": entity_name, "component": component_name}) if success else self.fail("Component remove failed")

    def edit_component(self, entity_name: str, component: str, property: str, value: Union[str, int, float, bool, list, dict, None]) -> ActionResult:
        """Set a single property on a component of an entity.

        Args:
            entity_name: Name of the target entity.
            component: Component type name (e.g. "Transform", "RigidBody").
            property: Property name to modify (e.g. "x", "speed", "enabled").
            value: New value for the property.

        Returns:
            ActionResult confirming the edit or failure (check names/property).
        """
        self.ensure_edit_mode()
        if self.scene_authoring is None:
            return self.fail("SceneManager not ready")
        success = self.scene_authoring.apply_edit_to_world(entity_name, component, property, value)
        return self.ok("Edit applied") if success else self.fail("Edit failed (check names/property)")

    def set_component_enabled(self, entity_name: str, component_name: str, enabled: bool) -> ActionResult:
        """Enable or disable a component on an entity via its 'enabled' property.

        Args:
            entity_name: Name of the target entity.
            component_name: Component type name.
            enabled: True to enable, False to disable.

        Returns:
            ActionResult confirming the toggle.
        """
        return self.edit_component(entity_name, component_name, "enabled", enabled)

    def create_camera2d(
        self,
        name: str,
        transform: Optional[dict[str, Any]] = None,
        camera: Optional[dict[str, Any]] = None,
    ) -> ActionResult:
        """Create an entity with Camera2D + Transform components preconfigured.

        Args:
            name: Entity name.
            transform: Optional overrides for the Transform component (x, y,
                rotation, scale_x, scale_y).
            camera: Optional overrides for the Camera2D component (offset_x,
                offset_y, zoom, rotation, is_primary, follow_entity, framing_mode,
                dead_zone_width, dead_zone_height, clamp_*, recenter_on_play).

        Returns:
            ActionResult confirming camera entity creation.
        """
        self.ensure_edit_mode()
        components: Dict[str, dict[str, Any]] = {
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

    def update_camera2d(self, entity_name: str, properties: dict[str, Any]) -> ActionResult:
        """Update multiple Camera2D properties on an entity at once.

        Args:
            entity_name: Name of the camera entity.
            properties: Mapping of Camera2D property names to new values.

        Returns:
            ActionResult confirming all properties were updated, or failure
            on the first property that fails.
        """
        self.ensure_edit_mode()
        for property_name, value in properties.items():
            result = self.edit_component(entity_name, "Camera2D", property_name, value)
            if not result["success"]:
                return result
        return self.ok("Camera2D updated", {"entity": entity_name})

    def set_camera_framing(self, entity_name: str, framing: dict[str, Any]) -> ActionResult:
        """Set camera framing properties (alias for update_camera2d).

        Args:
            entity_name: Name of the camera entity.
            framing: Dictionary of Camera2D framing-related properties.

        Returns:
            ActionResult confirming the framing update.
        """
        return self.update_camera2d(entity_name, framing)

    def create_input_map(self, name: str, bindings: Optional[dict[str, Any]] = None) -> ActionResult:
        """Create an entity with InputMap component for keyboard/gamepad bindings.

        Args:
            name: Entity name.
            bindings: Optional overrides for InputMap key-action bindings. Default
                bindings include WASD + arrow keys for movement and SPACE/ENTER
                for actions.

        Returns:
            ActionResult confirming InputMap entity creation.
        """
        self.ensure_edit_mode()
        components: Dict[str, dict[str, Any]] = {
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

    def update_input_map(self, entity_name: str, bindings: dict[str, Any]) -> ActionResult:
        """Update multiple InputMap key-action bindings at once.

        Args:
            entity_name: Name of the entity with InputMap component.
            bindings: Mapping of action names to key identifiers (e.g.
                {"move_left": "A,LEFT"}).

        Returns:
            ActionResult confirming all bindings were updated, or failure
            on the first property that fails.
        """
        self.ensure_edit_mode()
        for property_name, value in bindings.items():
            result = self.edit_component(entity_name, "InputMap", property_name, value)
            if not result["success"]:
                return result
        return self.ok("InputMap updated", {"entity": entity_name})

    def create_audio_source(
        self,
        name: str,
        transform: Optional[dict[str, Any]] = None,
        audio: Optional[dict[str, Any]] = None,
    ) -> ActionResult:
        """Create an entity with AudioSource + Transform components.

        Args:
            name: Entity name.
            transform: Optional Transform overrides.
            audio: Optional AudioSource property overrides (asset, asset_path,
                volume, pitch, loop, play_on_awake, spatial_blend).

        Returns:
            ActionResult confirming AudioSource entity creation.
        """
        self.ensure_edit_mode()
        components: Dict[str, dict[str, Any]] = {
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

    def update_audio_source(self, entity_name: str, properties: dict[str, Any]) -> ActionResult:
        """Update multiple AudioSource properties on an entity.

        Args:
            entity_name: Name of the entity with AudioSource component.
            properties: Mapping of AudioSource property names to new values.

        Returns:
            ActionResult confirming all properties were updated, or failure
            on the first property that fails.
        """
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
        public_data: Optional[dict[str, Any]] = None,
        run_in_edit_mode: bool = False,
        enabled: bool = True,
    ) -> ActionResult:
        """Attach a ScriptBehaviour component pointing to a Python script module.

        Args:
            entity_name: Name of the target entity.
            module_path: Python import path to the script module (e.g.
                "scripts.player_controller").
            public_data: Dictionary of public data exposed to the script.
            run_in_edit_mode: Whether the script runs outside Play mode.
            enabled: Whether the component starts enabled.

        Returns:
            ActionResult confirming ScriptBehaviour attachment.
        """
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

    def update_script_behaviour(self, entity_name: str, properties: dict[str, Any]) -> ActionResult:
        """Update multiple ScriptBehaviour properties at once.

        Args:
            entity_name: Name of the entity with ScriptBehaviour component.
            properties: Mapping of ScriptBehaviour property names to new values.

        Returns:
            ActionResult confirming all properties were updated, or failure
            on the first property that fails.
        """
        self.ensure_edit_mode()
        for property_name, value in properties.items():
            result = self.edit_component(entity_name, "ScriptBehaviour", property_name, value)
            if not result["success"]:
                return result
        return self.ok("ScriptBehaviour updated", {"entity": entity_name})

    def set_script_public_data(self, entity_name: str, public_data: dict[str, Any]) -> ActionResult:
        """Set the public_data dictionary on a ScriptBehaviour component.

        Args:
            entity_name: Name of the entity with ScriptBehaviour component.
            public_data: Full dictionary to store as public data.

        Returns:
            ActionResult confirming the update.
        """
        self.ensure_edit_mode()
        return self.edit_component(entity_name, "ScriptBehaviour", "public_data", public_data)

    def set_feature_metadata(self, key: str, value: Union[str, int, float, bool, list, dict, None]) -> ActionResult:
        """Persist a key-value pair in the scene's feature metadata.

        Feature metadata is the central place for scene-wide configuration like
        physics layer matrix, render sorting layers, and signal declarations.

        Args:
            key: Metadata key (e.g. "render_2d", "physics_2d", "signals").
            value: Arbitrary JSON-serializable value to store.

        Returns:
            ActionResult confirming the metadata was persisted.
        """
        self.ensure_edit_mode()
        if self.scene_authoring is None:
            return self.fail("No scene loaded")
        if not self.scene_authoring.set_feature_metadata(key, value):
            return self.fail("Feature metadata update failed")
        return self.ok("Feature metadata updated", {"key": key})

    def set_sorting_layers(self, order: list[str]) -> ActionResult:
        """Define the render sorting layer order for the scene.

        Args:
            order: List of layer names in draw order (first = back, last = front).

        Returns:
            ActionResult confirming the sorting layer configuration was saved.
        """
        self.ensure_edit_mode()
        metadata = self.api.get_feature_metadata()
        render_2d = dict(metadata.get("render_2d", {}))
        render_2d["sorting_layers"] = self.normalize_sorting_layers(order)
        return self.set_feature_metadata("render_2d", render_2d)

    def set_render_order(self, entity_name: str, sorting_layer: str, order_in_layer: int) -> ActionResult:
        """Set the sorting layer and draw order for a 2D renderable entity.

        If the entity does not have a RenderOrder2D component, one is created
        automatically.

        Args:
            entity_name: Name of the target entity.
            sorting_layer: Layer name that must exist in the configured sorting
                layers. Defaults to "Default" if empty.
            order_in_layer: Integer draw priority within the layer (higher = on top).

        Returns:
            ActionResult confirming the render order was set.
        """
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
        """Enable or disable physics collisions between two named layers.

        Args:
            layer_a: First layer name.
            layer_b: Second layer name.
            enabled: True to allow collisions, False to ignore.

        Returns:
            ActionResult confirming the collision matrix was updated.
        """
        self.ensure_edit_mode()
        metadata = self.api.get_feature_metadata()
        physics_2d = dict(metadata.get("physics_2d", {}))
        matrix = dict(physics_2d.get("layer_matrix", {}))
        matrix[f"{layer_a}|{layer_b}"] = bool(enabled)
        matrix[f"{layer_b}|{layer_a}"] = bool(enabled)
        physics_2d["layer_matrix"] = matrix
        return self.set_feature_metadata("physics_2d", physics_2d)

    def set_physics_backend(self, backend_name: str) -> ActionResult:
        """Select the active physics backend for the scene.

        Args:
            backend_name: Backend identifier (e.g. "legacy_aabb", "pymunk",
                "box2d"). Falls back to "legacy_aabb" if empty.

        Returns:
            ActionResult confirming the backend was changed, or failure if the
            backend is not supported.
        """
        self.ensure_edit_mode()
        normalized = str(backend_name or "").strip() or "legacy_aabb"
        runtime = self.runtime
        if runtime is None or not runtime.knows_physics_backend(normalized):
            return self.fail(f"Unsupported physics backend: {normalized}")
        metadata = self.api.get_feature_metadata()
        physics_2d = dict(metadata.get("physics_2d", {}))
        physics_2d["backend"] = normalized
        result = self.set_feature_metadata("physics_2d", physics_2d)
        if result["success"] and runtime is not None:
            runtime.refresh_runtime_physics_backend()
        return result

    def set_rigidbody_constraints(self, entity_name: str, constraints: list[str]) -> ActionResult:
        """Configure RigidBody freeze constraints (FreezePositionX, FreezePositionY).

        Args:
            entity_name: Name of the entity with RigidBody component.
            constraints: List of constraint names (e.g. ["FreezePositionX",
                "FreezePositionY"] or ["None"]).

        Returns:
            ActionResult confirming the constraints were applied.
        """
        self.ensure_edit_mode()
        normalized = RigidBody.normalize_constraints(constraints)
        invalid = [value for value in constraints if str(value).strip() not in RigidBody.VALID_CONSTRAINTS]
        if invalid:
            return self.fail(f"Unsupported constraints: {invalid}")
        if not normalized:
            normalized = ["None"]
        freeze_x = "FreezePositionX" in normalized
        freeze_y = "FreezePositionY" in normalized
        current = self.load_component_payload(entity_name, "RigidBody")
        if not isinstance(current, dict):
            return self.fail("Edit failed (check names/property)")

        changed = False
        for property_name, value in (
            ("freeze_x", freeze_x),
            ("freeze_y", freeze_y),
            ("constraints", normalized),
        ):
            if current.get(property_name) == value:
                continue
            result = self.edit_component(entity_name, "RigidBody", property_name, value)
            if not result["success"]:
                observed = self.load_component_payload(entity_name, "RigidBody")
                if not isinstance(observed, dict) or observed.get(property_name) != value:
                    return result
                current = observed
                continue
            current[property_name] = value
            changed = True
        return self.ok("RigidBody constraints applied") if changed or current else self.fail("Edit failed (check names/property)")

    def create_tilemap(
        self,
        entity_name: str,
        *,
        cell_width: int = 16,
        cell_height: int = 16,
        orientation: str = "orthogonal",
        tileset: str = "",
        layers: Optional[list[dict[str, Any]]] = None,
    ) -> ActionResult:
        """Create or replace a Tilemap component on an entity.

        If the entity already has a Tilemap component, its data is replaced.
        Otherwise, a new Tilemap component is created.

        Args:
            entity_name: Name of the target entity.
            cell_width: Width of each tile cell in pixels.
            cell_height: Height of each tile cell in pixels.
            orientation: Tilemap orientation (e.g. "orthogonal").
            tileset: Path or GUID for the tileset asset.
            layers: List of layer definition dictionaries.

        Returns:
            ActionResult confirming the tilemap was created or updated.
        """
        self.ensure_edit_mode()
        if self.scene_authoring is None:
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
            self.scene_authoring.replace_component_data(entity_name, "Tilemap", payload)
            if has_tilemap
            else self.scene_authoring.add_component_to_entity(entity_name, "Tilemap", payload)
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
        custom: Optional[dict[str, Any]] = None,
    ) -> ActionResult:
        """Place a tile at grid coordinates on a tilemap layer.

        Args:
            entity_name: Name of the tilemap entity.
            layer_name: Name of the target layer within the tilemap.
            x: Column index.
            y: Row index.
            tile_id: Tile identifier string.
            source: Asset path or GUID for the tile sprite.
            flags: Optional list of flag strings (e.g. ["flip_horizontal"]).
            tags: Optional list of tag strings for categorization.
            custom: Optional custom data dictionary for the tile.

        Returns:
            ActionResult confirming the tile was placed.
        """
        self.ensure_edit_mode()
        if self.scene_authoring is None:
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
        success = self.scene_authoring.replace_component_data(entity_name, "Tilemap", tilemap.to_dict())
        return self.ok("Tilemap tile updated", {"entity": entity_name, "layer": layer_name, "x": x, "y": y}) if success else self.fail("Tilemap tile update failed")

    def clear_tilemap_tile(self, entity_name: str, layer_name: str, x: int, y: int) -> ActionResult:
        """Remove a tile from a tilemap layer at grid coordinates.

        Args:
            entity_name: Name of the tilemap entity.
            layer_name: Name of the target layer.
            x: Column index.
            y: Row index.

        Returns:
            ActionResult confirming the tile was cleared.
        """
        self.ensure_edit_mode()
        if self.scene_authoring is None:
            return self.fail("SceneManager not ready")
        payload = self._load_tilemap_payload(entity_name)
        if payload is None:
            return self.fail("Tilemap not found")
        tilemap = Tilemap.from_dict(payload)
        tilemap.clear_tile(layer_name, x, y)
        success = self.scene_authoring.replace_component_data(entity_name, "Tilemap", tilemap.to_dict())
        return self.ok("Tilemap tile cleared", {"entity": entity_name, "layer": layer_name, "x": x, "y": y}) if success else self.fail("Tilemap tile clear failed")

    def get_tilemap(self, entity_name: str) -> dict[str, Any]:
        """Retrieve the full Tilemap component data for an entity.

        Args:
            entity_name: Name of the tilemap entity.

        Returns:
            Dictionary with the tilemap payload, or empty dict if not found.
        """
        payload = self._load_tilemap_payload(entity_name)
        return payload or {}

    def get_tilemap_layer(self, entity_name: str, layer_name: str) -> dict[str, Any]:
        """Retrieve a single tilemap layer's data.

        Args:
            entity_name: Name of the tilemap entity.
            layer_name: Name of the layer to retrieve.

        Returns:
            Dictionary with the layer data, or empty dict if not found.
        """
        payload = self._load_tilemap_payload(entity_name)
        if payload is None:
            return {}
        tilemap = Tilemap.from_dict(payload)
        layer = tilemap.get_layer(layer_name)
        return layer or {}

    def create_tilemap_layer(
        self,
        entity_name: str,
        layer_name: str,
        *,
        visible: bool = True,
        opacity: float = 1.0,
        locked: bool = False,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
        collision_layer: int = 0,
        tilemap_source: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ActionResult:
        """Add a new layer to an existing tilemap.

        Args:
            entity_name: Name of the tilemap entity.
            layer_name: Unique name for the new layer.
            visible: Whether the layer is visible.
            opacity: Layer opacity (0.0 to 1.0).
            locked: Whether the layer is locked for editing.
            offset_x: Horizontal offset in pixels.
            offset_y: Vertical offset in pixels.
            collision_layer: Collision layer mask for tiles on this layer.
            tilemap_source: Asset reference for the layer's tileset.
            metadata: Optional layer-level metadata dictionary.

        Returns:
            ActionResult confirming the layer was created.
        """
        self.ensure_edit_mode()
        if self.scene_authoring is None:
            return self.fail("SceneManager not ready")
        payload = self._load_tilemap_payload(entity_name)
        if payload is None:
            return self.fail("Tilemap not found")
        tilemap = Tilemap.from_dict(payload)
        source_ref = self.api.get_asset_reference(tilemap_source) if tilemap_source else {}
        layer = tilemap.add_layer(
            layer_name,
            visible=visible,
            opacity=opacity,
            locked=locked,
            offset_x=offset_x,
            offset_y=offset_y,
            collision_layer=collision_layer,
            tilemap_source=source_ref if (source_ref.get("guid") or source_ref.get("path")) else tilemap_source,
            metadata=metadata,
        )
        success = self.scene_authoring.replace_component_data(entity_name, "Tilemap", tilemap.to_dict())
        return self.ok("Tilemap layer created", {"entity": entity_name, "layer": layer.get("name")}) if success else self.fail("Tilemap layer creation failed")

    def update_tilemap_layer(
        self,
        entity_name: str,
        layer_name: str,
        *,
        visible: bool | None = None,
        opacity: float | None = None,
        locked: bool | None = None,
        offset_x: float | None = None,
        offset_y: float | None = None,
        collision_layer: int | None = None,
        tilemap_source: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ActionResult:
        """Update properties of an existing tilemap layer.

        Only properties provided (not None) are changed; others are left as-is.

        Args:
            entity_name: Name of the tilemap entity.
            layer_name: Name of the layer to update.
            visible: New visibility state (None = unchanged).
            opacity: New opacity (None = unchanged).
            locked: New locked state (None = unchanged).
            offset_x: New horizontal offset (None = unchanged).
            offset_y: New vertical offset (None = unchanged).
            collision_layer: New collision layer mask (None = unchanged).
            tilemap_source: New tileset reference (None = unchanged).
            metadata: New metadata dict (None = unchanged).

        Returns:
            ActionResult confirming the layer was updated, or failure if the
            layer was not found.
        """
        self.ensure_edit_mode()
        if self.scene_authoring is None:
            return self.fail("SceneManager not ready")
        payload = self._load_tilemap_payload(entity_name)
        if payload is None:
            return self.fail("Tilemap not found")
        tilemap = Tilemap.from_dict(payload)
        source_ref = self.api.get_asset_reference(tilemap_source) if tilemap_source is not None else None
        success = tilemap.set_layer_properties(
            layer_name,
            visible=visible,
            opacity=opacity,
            locked=locked,
            offset_x=offset_x,
            offset_y=offset_y,
            collision_layer=collision_layer,
            tilemap_source=source_ref if (source_ref is not None and (source_ref.get("guid") or source_ref.get("path"))) else tilemap_source,
            metadata=metadata,
        )
        if not success:
            return self.fail(f"Layer '{layer_name}' not found")
        success = self.scene_authoring.replace_component_data(entity_name, "Tilemap", tilemap.to_dict())
        return self.ok("Tilemap layer updated", {"entity": entity_name, "layer": layer_name}) if success else self.fail("Tilemap layer update failed")

    def delete_tilemap_layer(self, entity_name: str, layer_name: str) -> ActionResult:
        """Remove a layer from a tilemap.

        Args:
            entity_name: Name of the tilemap entity.
            layer_name: Name of the layer to delete.

        Returns:
            ActionResult confirming deletion, or failure if the layer was
            not found.
        """
        self.ensure_edit_mode()
        if self.scene_authoring is None:
            return self.fail("SceneManager not ready")
        payload = self._load_tilemap_payload(entity_name)
        if payload is None:
            return self.fail("Tilemap not found")
        tilemap = Tilemap.from_dict(payload)
        success = tilemap.remove_layer(layer_name)
        if not success:
            return self.fail(f"Layer '{layer_name}' not found")
        success = self.scene_authoring.replace_component_data(entity_name, "Tilemap", tilemap.to_dict())
        return self.ok("Tilemap layer deleted", {"entity": entity_name, "layer": layer_name}) if success else self.fail("Tilemap layer deletion failed")

    def set_tilemap_tile_full(
        self,
        entity_name: str,
        layer_name: str,
        x: int,
        y: int,
        tile_id: str,
        *,
        source: str = "",
        flags: list[str] | None = None,
        tags: list[str] | None = None,
        custom: dict[str, Any] | None = None,
        animated: bool = False,
        animation_id: str = "",
        terrain_type: str = "",
    ) -> ActionResult:
        """Place a tile with all extended properties at grid coordinates.

        Args:
            entity_name: Name of the tilemap entity.
            layer_name: Target layer name.
            x: Column index.
            y: Row index.
            tile_id: Tile identifier string.
            source: Asset path or GUID for the tile sprite.
            flags: Optional list of flags.
            tags: Optional list of tags.
            custom: Optional custom data.
            animated: Whether the tile is animated.
            animation_id: Animation identifier for animated tiles.
            terrain_type: Terrain classification for the tile.

        Returns:
            ActionResult confirming the tile was placed with full data.
        """
        self.ensure_edit_mode()
        if self.scene_authoring is None:
            return self.fail("SceneManager not ready")
        payload = self._load_tilemap_payload(entity_name)
        if payload is None:
            return self.fail("Tilemap not found")
        tilemap = Tilemap.from_dict(payload)
        source_ref = self.api.get_asset_reference(source) if source else {}
        tilemap.set_tile_full(
            layer_name,
            x,
            y,
            tile_id,
            source=source_ref if (source_ref.get("guid") or source_ref.get("path")) else source,
            flags=flags,
            tags=tags,
            custom=custom,
            animated=animated,
            animation_id=animation_id,
            terrain_type=terrain_type,
        )
        success = self.scene_authoring.replace_component_data(entity_name, "Tilemap", tilemap.to_dict())
        return self.ok("Tilemap tile full updated", {"entity": entity_name, "layer": layer_name, "x": x, "y": y}) if success else self.fail("Tilemap tile update failed")

    def bulk_set_tilemap_tiles(
        self,
        entity_name: str,
        layer_name: str,
        tiles: list[dict[str, Any]],
    ) -> ActionResult:
        """Place multiple tiles at once on a tilemap layer.

        Args:
            entity_name: Name of the tilemap entity.
            layer_name: Target layer name.
            tiles: List of tile specification dictionaries. Each dict may contain
                x, y, tile_id, source, flags, tags, custom, animated, animation_id,
                and terrain_type keys.

        Returns:
            ActionResult confirming the bulk operation with count of tiles set.
        """
        self.ensure_edit_mode()
        if self.scene_authoring is None:
            return self.fail("SceneManager not ready")
        payload = self._load_tilemap_payload(entity_name)
        if payload is None:
            return self.fail("Tilemap not found")
        tilemap = Tilemap.from_dict(payload)
        count = 0
        for tile_spec in tiles:
            x = int(tile_spec.get("x", 0))
            y = int(tile_spec.get("y", 0))
            tile_id = str(tile_spec.get("tile_id", ""))
            source = tile_spec.get("source", "")
            source_ref = self.api.get_asset_reference(source) if source else {}
            tilemap.set_tile_full(
                layer_name,
                x,
                y,
                tile_id,
                source=source_ref if (source_ref.get("guid") or source_ref.get("path")) else source,
                flags=tile_spec.get("flags"),
                tags=tile_spec.get("tags"),
                custom=tile_spec.get("custom"),
                animated=tile_spec.get("animated", False),
                animation_id=str(tile_spec.get("animation_id", "")),
                terrain_type=str(tile_spec.get("terrain_type", "")),
            )
            count += 1
        success = self.scene_authoring.replace_component_data(entity_name, "Tilemap", tilemap.to_dict())
        return self.ok("Bulk tiles set", {"entity": entity_name, "layer": layer_name, "count": count}) if success else self.fail("Bulk tile update failed")

    def set_cells_terrain_connect(
        self,
        entity_name: str,
        layer_name: str,
        cells: list[dict[str, int]],
        terrain_name: str,
    ) -> ActionResult:
        """Aplica autotile conectivo a celdas especificas usando TileSet terrain peering.

        Args:
            entity_name: Nombre de la entidad tilemap.
            layer_name: Nombre de la capa objetivo.
            cells: Lista de dicts con "x" e "y".
            terrain_name: Nombre del terreno para peering en el TileSet.

        Returns:
            ActionResult con count de celdas modificadas.
        """
        self.ensure_edit_mode()
        if self.scene_authoring is None:
            return self.fail("SceneManager not ready")
        payload = self._load_tilemap_payload(entity_name)
        if payload is None:
            return self.fail("Tilemap not found")
        tilemap = Tilemap.from_dict(payload)
        tileset = tilemap.get_tileset_resource()
        if tileset is None:
            return self.fail("No TileSet resource loaded for this tilemap")
        layer_dict = tilemap._find_layer(layer_name)
        if layer_dict is None:
            return self.fail(f"Layer '{layer_name}' not found")

        def _get_tile_at(lx: int, ly: int) -> dict[str, Any] | None:
            return tilemap.get_tile(layer_name, lx, ly)

        def _set_tile_at(lx: int, ly: int, tid: str) -> None:
            tilemap.set_tile(layer_name, lx, ly, tid)

        count = tileset.set_cells_terrain_connect(
            cells, terrain_name, _get_tile_at, _set_tile_at
        )
        success = self.scene_authoring.replace_component_data(
            entity_name, "Tilemap", tilemap.to_dict()
        )
        return (
            self.ok("Terrain connect applied", {"count": count})
            if success
            else self.fail("Tilemap save failed")
        )

    def resize_tilemap(
        self,
        entity_name: str,
        cell_width: int,
        cell_height: int,
        *,
        offset_x: int = 0,
        offset_y: int = 0,
    ) -> ActionResult:
        """Change the grid dimensions of a tilemap.

        Args:
            entity_name: Name of the tilemap entity.
            cell_width: New cell width in pixels.
            cell_height: New cell height in pixels.
            offset_x: Grid origin offset x.
            offset_y: Grid origin offset y.

        Returns:
            ActionResult confirming the resize operation.
        """
        self.ensure_edit_mode()
        if self.scene_authoring is None:
            return self.fail("SceneManager not ready")
        payload = self._load_tilemap_payload(entity_name)
        if payload is None:
            return self.fail("Tilemap not found")
        tilemap = Tilemap.from_dict(payload)
        tilemap.resize(cell_width, cell_height, offset_x=offset_x, offset_y=offset_y)
        success = self.scene_authoring.replace_component_data(entity_name, "Tilemap", tilemap.to_dict())
        return self.ok("Tilemap resized", {"entity": entity_name, "cell_width": cell_width, "cell_height": cell_height}) if success else self.fail("Tilemap resize failed")

    def list_animator_states(self, entity_name: str) -> list[dict[str, Any]]:
        """List all animation states defined on an entity's Animator component.

        Args:
            entity_name: Name of the entity with an Animator component.

        Returns:
            List of dictionaries, each representing an animation state with its
            name, frame data, fps, loop flag, on_complete target, and whether
            it is the default state.
        """
        entity = self.require_entity(entity_name)
        from engine.components.animator import Animator

        animator = entity.get_component(Animator)
        if animator is None:
            return []
        result: list[dict[str, Any]] = []
        for state_name, state_data in animator.to_dict().get("animations", {}).items():
            payload = dict(state_data)
            payload["state_name"] = state_name
            payload["is_default"] = animator.default_state == state_name
            result.append(payload)
        return result

    def set_animator_sprite_sheet(self, entity_name: str, asset_path: str) -> ActionResult:
        """Set the sprite sheet path for an Animator component.

        Args:
            entity_name: Name of the entity with an Animator component.
            asset_path: Path or asset reference to the sprite sheet image.

        Returns:
            ActionResult confirming the sprite sheet was updated.
        """
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
        """Create or update an animation state on an Animator component.

        Args:
            entity_name: Name of the entity with an Animator component.
            state_name: Unique name for the animation state.
            slice_names: List of sprite slice names composing the animation frames.
            fps: Frames per second for the animation playback.
            loop: Whether the animation loops.
            on_complete: Name of the state to transition to when animation completes,
                or None.
            set_default: If True, make this the default state.

        Returns:
            ActionResult confirming the animation state was upserted.
        """
        self.ensure_edit_mode()
        if self.scene_authoring is None:
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
        success = self.scene_authoring.replace_component_data(entity_name, "Animator", payload)
        return self.ok("Animator state updated", {"entity": entity_name, "state": state_name}) if success else self.fail("Animator state update failed")

    def set_animator_state_frames(
        self,
        entity_name: str,
        state_name: str,
        slice_names: list[str],
        fps: Optional[float] = None,
        loop: Optional[bool] = None,
        on_complete: Optional[Union[str, Callable[..., object]]] = _UNSET,
        set_default: bool = False,
    ) -> ActionResult:
        """Update frame data for an existing animation state.

        Only provided properties are changed; None values keep the current setting.

        Args:
            entity_name: Name of the entity with an Animator component.
            state_name: Name of the existing animation state to update.
            slice_names: New list of sprite slice names.
            fps: New frames per second (None = unchanged).
            loop: New loop flag (None = unchanged).
            on_complete: New on_complete target state (None = unchanged).
            set_default: If True, make this the default state.

        Returns:
            ActionResult confirming the frame data was updated.
        """
        self.ensure_edit_mode()
        if self.scene_authoring is None:
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
        success = self.scene_authoring.replace_component_data(entity_name, "Animator", payload)
        return self.ok("Animator frames updated", {"entity": entity_name, "state": state_name}) if success else self.fail("Animator frames update failed")

    def remove_animator_state(self, entity_name: str, state_name: str) -> ActionResult:
        """Remove an animation state from an Animator component.

        If the removed state was the default or current state, the next available
        state is promoted automatically.

        Args:
            entity_name: Name of the entity with an Animator component.
            state_name: Name of the state to remove.

        Returns:
            ActionResult confirming the state was removed.
        """
        self.ensure_edit_mode()
        if self.scene_authoring is None:
            return self.fail("SceneManager not ready")
        payload = self._load_animator_payload(entity_name)
        if payload is None:
            return self.fail("Animator not found")
        animations = payload.setdefault("animations", {})
        if state_name not in animations:
            return self.fail("Animator state not found")
        del animations[state_name]
        next_default = next(iter(animations.keys()), "")
        if not next_default:
            next_default = state_name
        if payload.get("default_state") == state_name:
            payload["default_state"] = next_default
        if payload.get("current_state") == state_name:
            payload["current_state"] = payload.get("default_state", next_default)
        for animation in animations.values():
            if animation.get("on_complete") == state_name:
                animation["on_complete"] = None
        success = self.scene_authoring.replace_component_data(entity_name, "Animator", payload)
        return self.ok("Animator state removed", {"entity": entity_name, "state": state_name}) if success else self.fail("Animator state remove failed")

    def duplicate_animator_state(self, entity_name: str, source_state: str, new_state_name: Optional[str] = None) -> ActionResult:
        """Clone an existing animation state with a new name.

        Args:
            entity_name: Name of the entity with an Animator component.
            source_state: Name of the state to duplicate.
            new_state_name: Name for the cloned state. If None, generates
                "{source_state}_copy" with auto-incrementing suffix.

        Returns:
            ActionResult confirming the state was duplicated with the final name.
        """
        self.ensure_edit_mode()
        if self.scene_authoring is None:
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
        success = self.scene_authoring.replace_component_data(entity_name, "Animator", payload)
        return self.ok("Animator state duplicated", {"entity": entity_name, "state": final_name}) if success else self.fail("Animator state duplicate failed")

    def rename_animator_state(self, entity_name: str, old_name: str, new_name: str) -> ActionResult:
        """Rename an existing animation state and update all references to it.

        Args:
            entity_name: Name of the entity with an Animator component.
            old_name: Current state name.
            new_name: New state name (must not already exist).

        Returns:
            ActionResult confirming the rename, or failure if names conflict or
            don't exist.
        """
        self.ensure_edit_mode()
        if self.scene_authoring is None:
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

        success = self.scene_authoring.replace_component_data(entity_name, "Animator", payload)
        return self.ok("Animator state renamed", {"entity": entity_name, "state": new_name}) if success else self.fail("Animator state rename failed")

    def set_animator_flip(self, entity_name: str, flip_x: Optional[bool] = None, flip_y: Optional[bool] = None) -> ActionResult:
        """Set horizontal or vertical flip for an Animator component.

        Args:
            entity_name: Name of the entity with an Animator component.
            flip_x: If not None, new horizontal flip state.
            flip_y: If not None, new vertical flip state.

        Returns:
            ActionResult confirming the flip was updated.
        """
        self.ensure_edit_mode()
        animator_data = self._load_animator_payload(entity_name)
        if animator_data is None:
            return self.fail("Animator not found")
        if flip_x is not None:
            animator_data["flip_x"] = bool(flip_x)
        if flip_y is not None:
            animator_data["flip_y"] = bool(flip_y)
        if self.scene_authoring is None:
            return self.fail("SceneManager not ready")
        success = self.scene_authoring.replace_component_data(entity_name, "Animator", animator_data)
        return self.ok("Animator flip updated", {"entity": entity_name}) if success else self.fail("Animator flip update failed")

    def set_animator_speed(self, entity_name: str, speed: float) -> ActionResult:
        """Set the global playback speed multiplier for an Animator component.

        Args:
            entity_name: Name of the entity with an Animator component.
            speed: Speed multiplier (clamped to minimum 0.01).

        Returns:
            ActionResult confirming the speed was updated with the applied value.
        """
        self.ensure_edit_mode()
        animator_data = self._load_animator_payload(entity_name)
        if animator_data is None:
            return self.fail("Animator not found")
        animator_data["speed"] = max(0.01, float(speed))
        if self.scene_authoring is None:
            return self.fail("SceneManager not ready")
        success = self.scene_authoring.replace_component_data(entity_name, "Animator", animator_data)
        return self.ok("Animator speed updated", {"entity": entity_name, "speed": animator_data["speed"]}) if success else self.fail("Animator speed update failed")

    def get_animator_info(self, entity_name: str) -> dict[str, Any]:
        """Get comprehensive information about an Animator component.

        Args:
            entity_name: Name of the entity with an Animator component.

        Returns:
            Dictionary with keys: exists, sprite_sheet, frame_width, frame_height,
            flip_x, flip_y, speed, default_state, current_state, and states list.
            If no Animator exists, returns {"exists": False}.
        """
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
        """Create a new animation state without making it the default.

        Convenience wrapper around upsert_animator_state with set_default=False.

        Args:
            entity_name: Name of the entity with an Animator component.
            state_name: Unique name for the new state.
            slice_names: List of sprite slice names (defaults to empty list).
            fps: Frames per second (default 8.0).
            loop: Whether the animation loops (default True).
            on_complete: Transition target state name or None.

        Returns:
            ActionResult confirming the animation state was created.
        """
        return self.upsert_animator_state(
            entity_name,
            state_name,
            slice_names or [],
            fps=fps,
            loop=loop,
            on_complete=on_complete,
            set_default=False,
        )

    # --- Señales declarativas persistentes (feature_metadata["signals"]) ---

    def list_signal_connections_declarative(self) -> list[dict[str, Union[str, int, float, bool, list, dict, None]]]:
        """Devuelve la lista de conexiones de señales declarativas persistentes en la escena activa."""
        metadata = self.api.get_feature_metadata()
        signals = metadata.get("signals", {})
        if not isinstance(signals, dict):
            return []
        connections = signals.get("connections", [])
        return copy.deepcopy(connections) if isinstance(connections, list) else []

    def get_signal_metadata(self) -> dict[str, Union[str, int, float, bool, list, dict, None]]:
        """Devuelve el bloque completo de metadata de señales de la escena activa."""
        metadata = self.api.get_feature_metadata()
        signals = metadata.get("signals", {})
        return copy.deepcopy(signals) if isinstance(signals, dict) else {}

    def add_signal_connection(self, connection_data: dict[str, Union[str, int, float, bool, list, dict, None]]) -> ActionResult:
        """Añade una conexión de señal declarativa a la escena activa."""
        self.ensure_edit_mode()
        if not isinstance(connection_data, dict):
            return self.fail("Connection data must be a dictionary")
        if "id" not in connection_data:
            return self.fail("Connection data must contain an 'id' field")

        metadata = self.api.get_feature_metadata()
        signals = dict(metadata.get("signals", {}))
        connections = list(signals.get("connections", []))

        existing_ids = {c.get("id") for c in connections if isinstance(c, dict)}
        if connection_data["id"] in existing_ids:
            return self.fail(f"Connection with id '{connection_data['id']}' already exists")

        connections.append(self._with_entity_signal_target_id(connection_data))
        signals["connections"] = connections
        return self.set_feature_metadata("signals", signals)

    def remove_signal_connection(self, connection_id: str) -> ActionResult:
        """Remueve una conexión de señal declarativa por su id."""
        self.ensure_edit_mode()
        metadata = self.api.get_feature_metadata()
        signals = dict(metadata.get("signals", {}))
        connections = list(signals.get("connections", []))

        new_connections = [c for c in connections if isinstance(c, dict) and c.get("id") != connection_id]

        if len(new_connections) == len(connections):
            return self.fail(f"Connection with id '{connection_id}' not found")

        signals["connections"] = new_connections
        return self.set_feature_metadata("signals", signals)

    def _apply_entity_property(self, name: str, property_name: str, value: Union[str, int, float, bool, list, dict, None], message: str) -> ActionResult:
        if self.scene_authoring is None:
            return self.fail("SceneManager not ready")
        existing = self.scene_authoring.find_entity_data(name)
        if isinstance(existing, dict) and existing.get(property_name) == value:
            return self.ok(message, {"entity": name})
        success = self.scene_authoring.update_entity_property(name, property_name, value)
        return self.ok(message, {"entity": name}) if success else self.fail("Entity property update failed")

    def _with_entity_signal_target_id(self, connection_data: dict[str, Union[str, int, float, bool, list, dict, None]]) -> dict[str, Union[str, int, float, bool, list, dict, None]]:
        payload = copy.deepcopy(connection_data)
        if self.scene_authoring is None:
            return payload
        target = payload.get("target")
        if not isinstance(target, dict):
            return payload
        if str(target.get("kind", "") or "").strip().lower() != "entity":
            return payload
        if isinstance(target.get("id"), str) and str(target.get("id")).strip():
            target["id"] = str(target["id"]).strip()
            return payload
        target_name = str(target.get("name", "") or "").strip()
        if not target_name:
            return payload
        find_entity_data = getattr(self.scene_authoring, "find_entity_data", None)
        entity_data = find_entity_data(target_name) if callable(find_entity_data) else None
        entity_id = entity_data.get("id") if isinstance(entity_data, dict) else None
        if isinstance(entity_id, str) and entity_id.strip():
            target["id"] = entity_id.strip()
        return payload

    def _load_animator_payload(self, entity_name: str) -> Optional[dict[str, Any]]:
        return self.load_component_payload(entity_name, "Animator")

    def _load_tilemap_payload(self, entity_name: str) -> Optional[dict[str, Any]]:
        return self.load_component_payload(entity_name, "Tilemap")
