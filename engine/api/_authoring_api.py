from __future__ import annotations

import copy
import math
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

    def snap_entities_to_grid(
        self,
        entity_names: list[str],
        *,
        step_x: float = 16.0,
        step_y: Optional[float] = None,
        target: str = "auto",
        mode: str = "round",
    ) -> ActionResult:
        self.ensure_edit_mode()
        if self.scene_manager is None:
            return self.fail("SceneManager not ready")
        normalized_entities = self._normalize_entity_names(entity_names)
        if not normalized_entities:
            return self.fail("At least one entity is required")
        normalized_target = self._normalize_authoring_target(target)
        normalized_mode = str(mode or "round").strip().lower()
        if normalized_mode not in {"round", "floor", "ceil"}:
            return self.fail(f"Unsupported snap mode: {mode}")
        snap_y = float(step_y if step_y is not None else step_x)
        if abs(float(step_x)) <= 1e-6 or abs(snap_y) <= 1e-6:
            return self.fail("Grid steps must be non-zero")

        if not self.scene_manager.begin_transaction(label="snap-entities-to-grid"):
            return self.fail("Transaction start failed")
        try:
            snapped: list[Dict[str, Any]] = []
            for entity_name in normalized_entities:
                binding = self._resolve_spatial_binding(entity_name, normalized_target)
                if binding is None:
                    raise ValueError(f"Entity '{entity_name}' has no supported transform for snap")
                before_x = float(binding["x"])
                before_y = float(binding["y"])
                after_x = self._snap_value(before_x, float(step_x), normalized_mode)
                after_y = self._snap_value(before_y, snap_y, normalized_mode)
                if not self.edit_component(entity_name, binding["component"], binding["x_field"], after_x)["success"]:
                    raise ValueError(f"Failed to snap {entity_name} X")
                if not self.edit_component(entity_name, binding["component"], binding["y_field"], after_y)["success"]:
                    raise ValueError(f"Failed to snap {entity_name} Y")
                snapped.append(
                    {
                        "entity": entity_name,
                        "component": binding["component"],
                        "before": {"x": before_x, "y": before_y},
                        "after": {"x": after_x, "y": after_y},
                    }
                )
            committed = self.scene_manager.commit_transaction()
            if committed is None:
                raise ValueError("Transaction commit failed")
            return self.ok("Entities snapped to grid", {"entities": snapped, "transaction": committed})
        except Exception as exc:
            self.scene_manager.rollback_transaction()
            return self.fail(str(exc))

    def duplicate_entities(
        self,
        entity_names: list[str],
        *,
        offset_x: float = 16.0,
        offset_y: float = 16.0,
        include_children: bool = True,
        name_suffix: str = "_copy",
    ) -> ActionResult:
        self.ensure_edit_mode()
        if self.scene_manager is None:
            return self.fail("SceneManager not ready")
        normalized_entities = self._normalize_entity_names(entity_names)
        if not normalized_entities:
            return self.fail("At least one entity is required")
        root_entities = self._prune_child_entities(normalized_entities) if include_children else normalized_entities
        if not self.scene_manager.begin_transaction(label="duplicate-entities"):
            return self.fail("Transaction start failed")
        try:
            created: list[Dict[str, Any]] = []
            for entity_name in root_entities:
                duplicates = self._duplicate_entity_tree(
                    entity_name,
                    offset_x=float(offset_x),
                    offset_y=float(offset_y),
                    include_children=include_children,
                    name_suffix=name_suffix,
                )
                created.extend(duplicates)
            committed = self.scene_manager.commit_transaction()
            if committed is None:
                raise ValueError("Transaction commit failed")
            return self.ok("Entities duplicated", {"created": created, "transaction": committed})
        except Exception as exc:
            self.scene_manager.rollback_transaction()
            return self.fail(str(exc))

    def align_entities(
        self,
        entity_names: list[str],
        *,
        axis: str = "x",
        mode: str = "min",
        target: str = "auto",
    ) -> ActionResult:
        self.ensure_edit_mode()
        if self.scene_manager is None:
            return self.fail("SceneManager not ready")
        normalized_entities = self._normalize_entity_names(entity_names)
        if len(normalized_entities) < 2:
            return self.fail("At least two entities are required")
        normalized_axis = str(axis or "x").strip().lower()
        if normalized_axis not in {"x", "y"}:
            return self.fail(f"Unsupported align axis: {axis}")
        normalized_mode = str(mode or "min").strip().lower()
        if normalized_mode not in {"min", "max", "center", "average"}:
            return self.fail(f"Unsupported align mode: {mode}")
        normalized_target = self._normalize_authoring_target(target)

        bindings = [self._resolve_spatial_binding(entity_name, normalized_target) for entity_name in normalized_entities]
        resolved_bindings: list[Dict[str, Any]] = []
        for binding in bindings:
            if binding is None:
                return self.fail("All entities must have a supported transform for alignment")
            resolved_bindings.append(binding)
        positions = [float(binding[normalized_axis]) for binding in resolved_bindings]
        if normalized_mode == "min":
            target_value = min(positions)
        elif normalized_mode == "max":
            target_value = max(positions)
        elif normalized_mode == "center":
            target_value = (min(positions) + max(positions)) * 0.5
        else:
            target_value = sum(positions) / len(positions)

        if not self.scene_manager.begin_transaction(label="align-entities"):
            return self.fail("Transaction start failed")
        try:
            aligned: list[Dict[str, Any]] = []
            for entity_name, binding in zip(normalized_entities, resolved_bindings):
                field_name = binding["x_field"] if normalized_axis == "x" else binding["y_field"]
                before_value = float(binding[normalized_axis])
                if not self.edit_component(entity_name, binding["component"], field_name, target_value)["success"]:
                    raise ValueError(f"Failed to align {entity_name}")
                aligned.append(
                    {
                        "entity": entity_name,
                        "component": binding["component"],
                        "axis": normalized_axis,
                        "before": before_value,
                        "after": float(target_value),
                    }
                )
            committed = self.scene_manager.commit_transaction()
            if committed is None:
                raise ValueError("Transaction commit failed")
            return self.ok("Entities aligned", {"entities": aligned, "transaction": committed})
        except Exception as exc:
            self.scene_manager.rollback_transaction()
            return self.fail(str(exc))

    def stamp_prefab(
        self,
        prefab_path: str,
        placements: list[Dict[str, Any]],
        *,
        parent: Optional[str] = None,
    ) -> ActionResult:
        self.ensure_edit_mode()
        if self.scene_manager is None:
            return self.fail("SceneManager not ready")
        normalized_placements = self._normalize_placements(placements)
        if not normalized_placements:
            return self.fail("At least one placement is required")
        if not self.scene_manager.begin_transaction(label="stamp-prefab"):
            return self.fail("Transaction start failed")
        try:
            stamped: list[Dict[str, Any]] = []
            for index, placement in enumerate(normalized_placements):
                instance_name = str(placement.get("name", "") or "").strip()
                if not instance_name:
                    instance_name = self._generate_unique_entity_name(self._prefab_base_name(prefab_path), suffix=f"_{index}")
                placement_parent = str(placement.get("parent", parent) or "").strip() or None
                overrides = self._build_placement_overrides(placement)
                result = self.api.instantiate_prefab(
                    prefab_path,
                    name=instance_name,
                    parent=placement_parent,
                    overrides=overrides or None,
                )
                if not result["success"]:
                    raise ValueError(result["message"] or "Prefab instantiation failed")
                stamped.append(
                    {
                        "entity": instance_name,
                        "parent": placement_parent,
                        "position": self._read_entity_position(instance_name),
                    }
                )
            committed = self.scene_manager.commit_transaction()
            if committed is None:
                raise ValueError("Transaction commit failed")
            return self.ok("Prefab stamped", {"instances": stamped, "transaction": committed})
        except Exception as exc:
            self.scene_manager.rollback_transaction()
            return self.fail(str(exc))

    def stamp_entities_from_source(
        self,
        source_entity: str,
        placements: list[Dict[str, Any]],
        *,
        include_children: bool = True,
    ) -> ActionResult:
        self.ensure_edit_mode()
        if self.scene_manager is None:
            return self.fail("SceneManager not ready")
        self.require_entity(source_entity)
        normalized_placements = self._normalize_placements(placements)
        if not normalized_placements:
            return self.fail("At least one placement is required")
        if not self.scene_manager.begin_transaction(label="stamp-entities-from-source"):
            return self.fail("Transaction start failed")
        try:
            stamped: list[Dict[str, Any]] = []
            for placement in normalized_placements:
                base_name = str(placement.get("name", "") or "").strip() or source_entity
                duplicate_root = self._duplicate_entity_tree(
                    source_entity,
                    offset_x=0.0,
                    offset_y=0.0,
                    include_children=include_children,
                    explicit_root_name=self._generate_unique_entity_name(base_name),
                    parent_override=str(placement.get("parent", "") or "").strip() or None,
                )[0]["entity"]
                self._apply_optional_position(duplicate_root, placement)
                stamped.append(
                    {
                        "entity": duplicate_root,
                        "parent": str(placement.get("parent", "") or "").strip() or None,
                        "position": self._read_entity_position(duplicate_root),
                    }
                )
            committed = self.scene_manager.commit_transaction()
            if committed is None:
                raise ValueError("Transaction commit failed")
            return self.ok("Entity stamp created", {"instances": stamped, "transaction": committed})
        except Exception as exc:
            self.scene_manager.rollback_transaction()
            return self.fail(str(exc))

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
        tileset_mode: str = "grid",
        tileset: str = "",
        layers: Optional[list[Dict[str, Any]]] = None,
        tileset_tile_width: int = 16,
        tileset_tile_height: int = 16,
        tileset_columns: int = 0,
        tileset_spacing: int = 0,
        tileset_margin: int = 0,
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
            tileset_mode=tileset_mode,
            tileset=tileset_ref if (tileset_ref.get("guid") or tileset_ref.get("path")) else tileset,
            tileset_path=tileset_ref.get("path", "") or tileset,
            layers=layers or [],
            tileset_tile_width=tileset_tile_width,
            tileset_tile_height=tileset_tile_height,
            tileset_columns=tileset_columns,
            tileset_spacing=tileset_spacing,
            tileset_margin=tileset_margin,
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
        slice_name: str = "",
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
            slice_name=slice_name,
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

    def get_tilemap_layer(self, entity_name: str, layer_name: str) -> Dict[str, Any]:
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
        metadata: Dict[str, Any] | None = None,
    ) -> ActionResult:
        self.ensure_edit_mode()
        if self.scene_manager is None:
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
        success = self.scene_manager.replace_component_data(entity_name, "Tilemap", tilemap.to_dict())
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
        metadata: Dict[str, Any] | None = None,
    ) -> ActionResult:
        self.ensure_edit_mode()
        if self.scene_manager is None:
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
        success = self.scene_manager.replace_component_data(entity_name, "Tilemap", tilemap.to_dict())
        return self.ok("Tilemap layer updated", {"entity": entity_name, "layer": layer_name}) if success else self.fail("Tilemap layer update failed")

    def delete_tilemap_layer(self, entity_name: str, layer_name: str) -> ActionResult:
        self.ensure_edit_mode()
        if self.scene_manager is None:
            return self.fail("SceneManager not ready")
        payload = self._load_tilemap_payload(entity_name)
        if payload is None:
            return self.fail("Tilemap not found")
        tilemap = Tilemap.from_dict(payload)
        success = tilemap.remove_layer(layer_name)
        if not success:
            return self.fail(f"Layer '{layer_name}' not found")
        success = self.scene_manager.replace_component_data(entity_name, "Tilemap", tilemap.to_dict())
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
        custom: Dict[str, Any] | None = None,
        animated: bool = False,
        animation_id: str = "",
        terrain_type: str = "",
        slice_name: str = "",
    ) -> ActionResult:
        self.ensure_edit_mode()
        if self.scene_manager is None:
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
            slice_name=slice_name,
        )
        success = self.scene_manager.replace_component_data(entity_name, "Tilemap", tilemap.to_dict())
        return self.ok("Tilemap tile full updated", {"entity": entity_name, "layer": layer_name, "x": x, "y": y}) if success else self.fail("Tilemap tile update failed")

    def bulk_set_tilemap_tiles(
        self,
        entity_name: str,
        layer_name: str,
        tiles: list[Dict[str, Any]],
    ) -> ActionResult:
        self.ensure_edit_mode()
        if self.scene_manager is None:
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
                slice_name=str(tile_spec.get("slice_name", "")),
            )
            count += 1
        success = self.scene_manager.replace_component_data(entity_name, "Tilemap", tilemap.to_dict())
        return self.ok("Bulk tiles set", {"entity": entity_name, "layer": layer_name, "count": count}) if success else self.fail("Bulk tile update failed")

    def fill_tilemap_rect(
        self,
        entity_name: str,
        layer_name: str,
        x_start: int,
        y_start: int,
        x_end: int,
        y_end: int,
        tile_id: str,
        *,
        source: str = "",
        flags: list[str] | None = None,
        tags: list[str] | None = None,
        custom: Dict[str, Any] | None = None,
        animated: bool = False,
        animation_id: str = "",
        terrain_type: str = "",
        slice_name: str = "",
    ) -> ActionResult:
        self.ensure_edit_mode()
        if self.scene_manager is None:
            return self.fail("SceneManager not ready")
        payload = self._load_tilemap_payload(entity_name)
        if payload is None:
            return self.fail("Tilemap not found")
        tilemap = Tilemap.from_dict(payload)
        source_ref = self.api.get_asset_reference(source) if source else {}
        count = tilemap.fill_rect(
            layer_name,
            x_start,
            y_start,
            x_end,
            y_end,
            tile_id,
            source=source_ref if (source_ref.get("guid") or source_ref.get("path")) else source,
            flags=flags,
            tags=tags,
            custom=custom,
            animated=animated,
            animation_id=animation_id,
            terrain_type=terrain_type,
            slice_name=slice_name,
        )
        success = self.scene_manager.replace_component_data(entity_name, "Tilemap", tilemap.to_dict())
        return self.ok(
            "Tilemap rect filled",
            {
                "entity": entity_name,
                "layer": layer_name,
                "count": count,
                "x_start": int(x_start),
                "y_start": int(y_start),
                "x_end": int(x_end),
                "y_end": int(y_end),
            },
        ) if success else self.fail("Tilemap rect fill failed")

    def clear_tilemap_rect(
        self,
        entity_name: str,
        layer_name: str,
        x_start: int,
        y_start: int,
        x_end: int,
        y_end: int,
    ) -> ActionResult:
        self.ensure_edit_mode()
        if self.scene_manager is None:
            return self.fail("SceneManager not ready")
        payload = self._load_tilemap_payload(entity_name)
        if payload is None:
            return self.fail("Tilemap not found")
        tilemap = Tilemap.from_dict(payload)
        count = 0
        x0 = min(int(x_start), int(x_end))
        x1 = max(int(x_start), int(x_end))
        y0 = min(int(y_start), int(y_end))
        y1 = max(int(y_start), int(y_end))
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                if tilemap.get_tile(layer_name, x, y) is None:
                    continue
                tilemap.clear_tile(layer_name, x, y)
                count += 1
        success = self.scene_manager.replace_component_data(entity_name, "Tilemap", tilemap.to_dict())
        return self.ok(
            "Tilemap rect cleared",
            {
                "entity": entity_name,
                "layer": layer_name,
                "count": count,
                "x_start": x0,
                "y_start": y0,
                "x_end": x1,
                "y_end": y1,
            },
        ) if success else self.fail("Tilemap rect clear failed")

    def configure_tilemap_tileset(
        self,
        entity_name: str,
        *,
        tileset: str | None = None,
        tileset_mode: str | None = None,
        tileset_tile_width: int | None = None,
        tileset_tile_height: int | None = None,
        tileset_columns: int | None = None,
        tileset_spacing: int | None = None,
        tileset_margin: int | None = None,
    ) -> ActionResult:
        self.ensure_edit_mode()
        if self.scene_manager is None:
            return self.fail("SceneManager not ready")
        payload = self._load_tilemap_payload(entity_name)
        if payload is None:
            return self.fail("Tilemap not found")
        tilemap = Tilemap.from_dict(payload)
        if tileset is not None:
            tileset_ref = self.api.get_asset_reference(tileset) if tileset else {"guid": "", "path": ""}
            tilemap.sync_tileset_reference(tileset_ref if (tileset_ref.get("guid") or tileset_ref.get("path")) else tileset)
        if tileset_mode is not None:
            normalized_mode = str(tileset_mode or "grid").strip().lower()
            if normalized_mode not in Tilemap.VALID_TILESET_MODES:
                return self.fail(f"Unsupported tileset mode: {tileset_mode}")
            tilemap.tileset_mode = normalized_mode
        if tileset_tile_width is not None:
            tilemap.tileset_tile_width = max(1, int(tileset_tile_width))
        if tileset_tile_height is not None:
            tilemap.tileset_tile_height = max(1, int(tileset_tile_height))
        if tileset_columns is not None:
            tilemap.tileset_columns = max(0, int(tileset_columns))
        if tileset_spacing is not None:
            tilemap.tileset_spacing = max(0, int(tileset_spacing))
        if tileset_margin is not None:
            tilemap.tileset_margin = max(0, int(tileset_margin))
        success = self.scene_manager.replace_component_data(entity_name, "Tilemap", tilemap.to_dict())
        return self.ok(
            "Tilemap tileset configured",
            {
                "entity": entity_name,
                "tileset_mode": tilemap.tileset_mode,
                "tileset_path": tilemap.tileset_path,
            },
        ) if success else self.fail("Tilemap tileset update failed")

    def resize_tilemap(
        self,
        entity_name: str,
        cell_width: int,
        cell_height: int,
        *,
        offset_x: int = 0,
        offset_y: int = 0,
    ) -> ActionResult:
        self.ensure_edit_mode()
        if self.scene_manager is None:
            return self.fail("SceneManager not ready")
        payload = self._load_tilemap_payload(entity_name)
        if payload is None:
            return self.fail("Tilemap not found")
        tilemap = Tilemap.from_dict(payload)
        tilemap.resize(cell_width, cell_height, offset_x=offset_x, offset_y=offset_y)
        success = self.scene_manager.replace_component_data(entity_name, "Tilemap", tilemap.to_dict())
        return self.ok("Tilemap resized", {"entity": entity_name, "cell_width": cell_width, "cell_height": cell_height}) if success else self.fail("Tilemap resize failed")

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

    def set_animator_anchor_mode(self, entity_name: str, anchor_mode: str) -> ActionResult:
        self.ensure_edit_mode()
        normalized_mode = str(anchor_mode or "legacy_center").strip().lower()
        from engine.components.animator import Animator

        if normalized_mode not in Animator.VALID_ANCHOR_MODES:
            return self.fail(f"Unsupported animator anchor mode: {anchor_mode}")
        return self.edit_component(entity_name, "Animator", "anchor_mode", normalized_mode)

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
        # Keep a valid default state (non-empty string required by schema)
        if not next_default:
            next_default = state_name  # Keep the removed state name as placeholder
        if payload.get("default_state") == state_name:
            payload["default_state"] = next_default
        if payload.get("current_state") == state_name:
            payload["current_state"] = payload.get("default_state", next_default)
        for animation in animations.values():
            if animation.get("on_complete") == state_name:
                animation["on_complete"] = None
        controller_payload = self._load_animator_controller_payload(entity_name)
        if self._animator_controller_references_clip(controller_payload, state_name):
            return self.fail("AnimatorController still references this Animator state; update the controller first")
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
        controller_payload = self._load_animator_controller_payload(entity_name)
        if self._animator_controller_references_clip(controller_payload, old_name):
            return self.fail("AnimatorController still references this Animator state; update the controller first")

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

        controller_data = self._load_animator_controller_payload(entity_name)
        controller_summary = {
            "exists": False,
            "enabled": False,
            "entry_state": "",
            "state_count": 0,
            "transition_count": 0,
            "parameter_count": 0,
            "states": [],
        }
        if controller_data is not None:
            controller_states = controller_data.get("states", {})
            controller_summary = {
                "exists": True,
                "enabled": bool(controller_data.get("enabled", True)),
                "entry_state": str(controller_data.get("entry_state", "") or ""),
                "state_count": len(controller_states) if isinstance(controller_states, dict) else 0,
                "transition_count": len(controller_data.get("transitions", [])) if isinstance(controller_data.get("transitions"), list) else 0,
                "parameter_count": len(controller_data.get("parameters", {})) if isinstance(controller_data.get("parameters"), dict) else 0,
                "states": [
                    {
                        "name": state_name,
                        "animation_state": str(state_payload.get("animation_state", "") or ""),
                    }
                    for state_name, state_payload in (controller_states.items() if isinstance(controller_states, dict) else [])
                    if isinstance(state_payload, dict)
                ],
            }

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
            "controller": controller_summary,
        }

    def get_animator_controller(self, entity_name: str) -> Dict[str, Any]:
        controller_data = self._load_animator_controller_payload(entity_name)
        if controller_data is None:
            return {"exists": False}
        payload = copy.deepcopy(controller_data)
        payload["exists"] = True
        return payload

    def set_animator_controller(self, entity_name: str, controller_payload: Dict[str, Any]) -> ActionResult:
        self.ensure_edit_mode()
        if self.scene_manager is None:
            return self.fail("SceneManager not ready")
        animator_payload = self._load_animator_payload(entity_name)
        if animator_payload is None:
            return self.fail("Animator not found")
        from engine.components.animator_controller import AnimatorController

        controller_data = AnimatorController.from_dict(controller_payload or {}).to_dict()
        has_component = self._load_animator_controller_payload(entity_name) is not None
        success = (
            self.scene_manager.replace_component_data(entity_name, "AnimatorController", controller_data)
            if has_component
            else self.scene_manager.add_component_to_entity(entity_name, "AnimatorController", controller_data)
        )
        return self.ok("AnimatorController updated", {"entity": entity_name}) if success else self.fail("AnimatorController update failed")

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

    def create_animator_state_from_slices(
        self,
        entity_name: str,
        state_name: str,
        asset_path: str,
        slice_names: list[str],
        *,
        fps: float = 8.0,
        loop: bool = True,
        on_complete: Optional[str] = None,
        set_default: bool = False,
        order_mode: str = "selection",
    ) -> ActionResult:
        self.ensure_edit_mode()
        if self.scene_manager is None:
            return self.fail("SceneManager not ready")
        if self.asset_service is None:
            return self.fail("Asset service not ready")
        if not state_name.strip():
            return self.fail("Animator state name is required")
        payload = self._load_animator_payload(entity_name)
        if payload is None:
            return self.fail("Animator not found")
        try:
            clip = self.asset_service.build_animation_from_slices(
                asset_path,
                slice_names,
                state_name=state_name,
                fps=fps,
                loop=loop,
                on_complete=on_complete,
                order_mode=order_mode,
            )
        except Exception as exc:
            return self.fail(f"Animator slices build failed: {exc}")

        animations = payload.setdefault("animations", {})
        animation_payload = dict(clip["animation"])
        animation_payload["on_complete"] = on_complete if (on_complete in animations and on_complete != state_name) else None
        animations[state_name] = animation_payload
        payload["sprite_sheet"] = asset_path
        payload["sprite_sheet_path"] = asset_path
        if set_default or not payload.get("default_state"):
            payload["default_state"] = state_name
        if payload.get("current_state") not in animations:
            payload["current_state"] = payload["default_state"]
        success = self.scene_manager.replace_component_data(entity_name, "Animator", payload)
        if not success:
            return self.fail("Animator state update failed")
        return self.ok(
            "Animator state created from slices",
            {
                "entity": entity_name,
                "state": state_name,
                "sprite_sheet": asset_path,
                "animation": animation_payload,
                "preview": clip["preview"],
            },
        )

    def _apply_entity_property(self, name: str, property_name: str, value: Any, message: str) -> ActionResult:
        if self.scene_manager is None:
            return self.fail("SceneManager not ready")
        success = self.scene_manager.update_entity_property(name, property_name, value)
        return self.ok(message, {"entity": name}) if success else self.fail("Entity property update failed")

    def _load_animator_payload(self, entity_name: str) -> Optional[Dict[str, Any]]:
        return self.load_component_payload(entity_name, "Animator")

    def _load_animator_controller_payload(self, entity_name: str) -> Optional[Dict[str, Any]]:
        return self.load_component_payload(entity_name, "AnimatorController")

    def _animator_controller_references_clip(self, controller_payload: Optional[Dict[str, Any]], clip_name: str) -> bool:
        if controller_payload is None:
            return False
        states = controller_payload.get("states", {})
        if not isinstance(states, dict):
            return False
        for state_payload in states.values():
            if not isinstance(state_payload, dict):
                continue
            if str(state_payload.get("animation_state", "") or "") == clip_name:
                return True
        return False

    def _load_tilemap_payload(self, entity_name: str) -> Optional[Dict[str, Any]]:
        return self.load_component_payload(entity_name, "Tilemap")

    def _normalize_entity_names(self, entity_names: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for value in entity_names:
            entity_name = str(value or "").strip()
            if not entity_name or entity_name in seen:
                continue
            self.require_entity(entity_name)
            normalized.append(entity_name)
            seen.add(entity_name)
        return normalized

    def _normalize_authoring_target(self, target: str) -> str:
        normalized = str(target or "auto").strip().lower()
        if normalized not in {"auto", "transform", "recttransform"}:
            raise ValueError(f"Unsupported authoring target: {target}")
        return normalized

    def _resolve_spatial_binding(self, entity_name: str, target: str) -> Optional[Dict[str, Any]]:
        entity = self.require_entity(entity_name)
        transform_payload = self.load_component_payload(entity_name, "Transform")
        rect_payload = self.load_component_payload(entity_name, "RectTransform")
        if target == "transform":
            return self._transform_binding("Transform", transform_payload, "x", "y")
        if target == "recttransform":
            return self._transform_binding("RectTransform", rect_payload, "anchored_x", "anchored_y")
        if rect_payload is not None:
            return self._transform_binding("RectTransform", rect_payload, "anchored_x", "anchored_y")
        if transform_payload is not None:
            return self._transform_binding("Transform", transform_payload, "x", "y")
        if entity is None:
            return None
        return None

    def _transform_binding(
        self,
        component_name: str,
        payload: Optional[Dict[str, Any]],
        x_field: str,
        y_field: str,
    ) -> Optional[Dict[str, Any]]:
        if payload is None:
            return None
        return {
            "component": component_name,
            "x_field": x_field,
            "y_field": y_field,
            "x": float(payload.get(x_field, 0.0)),
            "y": float(payload.get(y_field, 0.0)),
        }

    def _snap_value(self, value: float, step: float, mode: str) -> float:
        ratio = float(value) / float(step)
        if mode == "floor":
            snapped = math.floor(ratio)
        elif mode == "ceil":
            snapped = math.ceil(ratio)
        else:
            snapped = round(ratio)
        return float(snapped * step)

    def _prune_child_entities(self, entity_names: list[str]) -> list[str]:
        roots: list[str] = []
        selected = set(entity_names)
        for entity_name in entity_names:
            entity = self.require_entity(entity_name)
            current_parent = entity.parent_name
            keep = True
            while current_parent is not None:
                if current_parent in selected:
                    keep = False
                    break
                parent_entity = self.require_entity(current_parent)
                current_parent = parent_entity.parent_name
            if keep:
                roots.append(entity_name)
        return roots

    def _duplicate_entity_tree(
        self,
        entity_name: str,
        *,
        offset_x: float,
        offset_y: float,
        include_children: bool,
        name_suffix: str = "_copy",
        explicit_root_name: Optional[str] = None,
        parent_override: Optional[str] = None,
    ) -> list[Dict[str, Any]]:
        source_entity = self.api.get_entity(entity_name)
        root_name = explicit_root_name or self._generate_unique_entity_name(entity_name, suffix=name_suffix)
        source_parent = source_entity.get("parent")
        root_parent = parent_override if parent_override is not None else source_parent
        created: list[Dict[str, Any]] = []
        self._create_entity_copy(
            source_entity,
            new_name=root_name,
            parent_name=root_parent,
            apply_offset=True,
            offset_x=offset_x,
            offset_y=offset_y,
        )
        created.append({"source": entity_name, "entity": root_name, "parent": root_parent})
        if include_children:
            for child in self._collect_entity_subtree(entity_name):
                child_entity = self.api.get_entity(child)
                relative_parent = str(child_entity.get("parent", "") or "")
                if not relative_parent:
                    continue
                if relative_parent == entity_name:
                    duplicated_parent = root_name
                else:
                    duplicated_parent = self._duplicated_name_for_source(relative_parent, created)
                duplicated_name = self._generate_unique_entity_name(child, suffix=name_suffix)
                self._create_entity_copy(
                    child_entity,
                    new_name=duplicated_name,
                    parent_name=duplicated_parent,
                    apply_offset=False,
                    offset_x=0.0,
                    offset_y=0.0,
                )
                created.append({"source": child, "entity": duplicated_name, "parent": duplicated_parent})
        return created

    def _duplicated_name_for_source(self, source_name: str, created: list[Dict[str, Any]]) -> str:
        for item in created:
            if item.get("source") == source_name:
                return str(item.get("entity"))
        raise ValueError(f"Duplicated parent for '{source_name}' not found")

    def _collect_entity_subtree(self, root_name: str) -> list[str]:
        names: list[str] = []
        world = self.game.world if self.game is not None else None
        if world is None:
            return names
        queue = [root_name]
        while queue:
            current = queue.pop(0)
            for child in world.get_children(current):
                names.append(child.name)
                queue.append(child.name)
        return names

    def _create_entity_copy(
        self,
        source_entity: Dict[str, Any],
        *,
        new_name: str,
        parent_name: Optional[str],
        apply_offset: bool,
        offset_x: float,
        offset_y: float,
    ) -> None:
        components = copy.deepcopy(source_entity.get("components", {}))
        if apply_offset:
            transform_payload = components.get("Transform")
            if isinstance(transform_payload, dict):
                transform_payload["x"] = float(transform_payload.get("x", 0.0)) + offset_x
                transform_payload["y"] = float(transform_payload.get("y", 0.0)) + offset_y
            rect_payload = components.get("RectTransform")
            if isinstance(rect_payload, dict):
                rect_payload["anchored_x"] = float(rect_payload.get("anchored_x", 0.0)) + offset_x
                rect_payload["anchored_y"] = float(rect_payload.get("anchored_y", 0.0)) + offset_y
        result = (
            self.create_child_entity(parent_name, new_name, components=components)
            if parent_name
            else self.create_entity(new_name, components=components)
        )
        if not result["success"]:
            raise ValueError(result["message"] or f"Failed to create '{new_name}'")
        if bool(source_entity.get("active", True)) is False:
            if not self.set_entity_active(new_name, False)["success"]:
                raise ValueError(f"Failed to restore active state for '{new_name}'")
        tag = str(source_entity.get("tag", "Untagged") or "Untagged")
        if tag and tag != "Untagged":
            if not self.set_entity_tag(new_name, tag)["success"]:
                raise ValueError(f"Failed to restore tag for '{new_name}'")
        layer = str(source_entity.get("layer", "Default") or "Default")
        if layer and layer != "Default":
            if not self.set_entity_layer(new_name, layer)["success"]:
                raise ValueError(f"Failed to restore layer for '{new_name}'")
        component_metadata = source_entity.get("component_metadata", {})
        if isinstance(component_metadata, dict):
            for component_name, metadata in component_metadata.items():
                if self.scene_manager is not None and isinstance(metadata, dict):
                    if not self.scene_manager.set_component_metadata(new_name, component_name, copy.deepcopy(metadata)):
                        raise ValueError(f"Failed to restore metadata for '{new_name}.{component_name}'")

    def _generate_unique_entity_name(self, base_name: str, *, suffix: str = "_copy") -> str:
        candidate = str(base_name or "Entity").strip() or "Entity"
        if not self._entity_exists(candidate):
            return candidate
        index = 1
        while True:
            generated = f"{candidate}{suffix}{index}" if suffix and suffix.startswith("_") else f"{candidate}{suffix}{index}"
            if not self._entity_exists(generated):
                return generated
            index += 1

    def _entity_exists(self, entity_name: str) -> bool:
        try:
            self.require_entity(entity_name)
            return True
        except Exception:
            return False

    def _normalize_placements(self, placements: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
        normalized: list[Dict[str, Any]] = []
        for placement in placements:
            if not isinstance(placement, dict):
                continue
            normalized.append(dict(placement))
        return normalized

    def _apply_optional_position(self, entity_name: str, placement: Dict[str, Any]) -> None:
        x = placement.get("x")
        y = placement.get("y")
        target = str(placement.get("target", "auto") or "auto")
        if x is None and y is None:
            return
        binding = self._resolve_spatial_binding(entity_name, self._normalize_authoring_target(target))
        if binding is None:
            return
        if x is not None:
            if not self.edit_component(entity_name, binding["component"], binding["x_field"], float(x))["success"]:
                raise ValueError(f"Failed to place '{entity_name}' on X")
        if y is not None:
            if not self.edit_component(entity_name, binding["component"], binding["y_field"], float(y))["success"]:
                raise ValueError(f"Failed to place '{entity_name}' on Y")

    def _build_placement_overrides(self, placement: Dict[str, Any]) -> Dict[str, Any]:
        x = placement.get("x")
        y = placement.get("y")
        target = self._normalize_authoring_target(str(placement.get("target", "transform") or "transform"))
        if x is None and y is None:
            return {}
        component_name = "RectTransform" if target == "recttransform" else "Transform"
        x_field = "anchored_x" if component_name == "RectTransform" else "x"
        y_field = "anchored_y" if component_name == "RectTransform" else "y"
        operations: list[Dict[str, Any]] = []
        if x is not None:
            operations.append({"op": "set_field", "target": "", "component": component_name, "field": x_field, "value": float(x)})
        if y is not None:
            operations.append({"op": "set_field", "target": "", "component": component_name, "field": y_field, "value": float(y)})
        return {"operations": operations} if operations else {}

    def _read_entity_position(self, entity_name: str) -> Dict[str, Any]:
        binding = self._resolve_spatial_binding(entity_name, "auto")
        if binding is None:
            return {}
        return {
            "component": binding["component"],
            "x": float(binding["x"]),
            "y": float(binding["y"]),
        }

    def _prefab_base_name(self, prefab_path: str) -> str:
        normalized = str(prefab_path or "").replace("\\", "/").rstrip("/")
        stem = normalized.split("/")[-1]
        if "." in stem:
            stem = stem.rsplit(".", 1)[0]
        return stem or "Prefab"
