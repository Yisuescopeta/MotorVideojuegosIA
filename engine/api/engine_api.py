"""
engine/api/engine_api.py - Fachada publica del motor
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from cli.headless_game import HeadlessGame
from engine.api.errors import (
    EntityNotFoundError,
    InvalidOperationError,
    LevelLoadError,
)
from engine.api.types import ActionResult, EngineStatus, EntityData
from engine.assets.asset_service import AssetService
from engine.assets.prefab import PrefabManager
from engine.authoring.changes import Change
from engine.components.canvas import Canvas
from engine.components.recttransform import RectTransform
from engine.components.renderorder2d import RenderOrder2D
from engine.components.rigidbody import RigidBody
from engine.components.tilemap import Tilemap
from engine.components.uibutton import UIButton
from engine.components.uitext import UIText
from engine.events.event_bus import EventBus
from engine.inspector.inspector_system import InspectorSystem
from engine.levels.component_registry import create_default_registry
from engine.physics.box2d_backend import Box2DPhysicsBackend
from engine.project.project_service import ProjectService
from engine.scenes.scene_manager import SceneManager
from engine.systems.animation_system import AnimationSystem
from engine.systems.audio_system import AudioSystem
from engine.systems.character_controller_system import CharacterControllerSystem
from engine.systems.collision_system import CollisionSystem
from engine.systems.input_system import InputSystem
from engine.systems.physics_system import PhysicsSystem
from engine.systems.player_controller_system import PlayerControllerSystem
from engine.systems.render_system import RenderSystem
from engine.systems.script_behaviour_system import ScriptBehaviourSystem
from engine.systems.selection_system import SelectionSystem
from engine.systems.ui_render_system import UIRenderSystem
from engine.systems.ui_system import UISystem

_UNSET = object()


class EngineAPI:
    """
    API publica para controlar el motor y editar el contenido sin usar internals.
    """

    def __init__(
        self,
        project_root: str | None = None,
        global_state_dir: str | None = None,
        sandbox_paths: bool = False,
    ) -> None:
        self.game: Optional[HeadlessGame] = None
        self.scene_manager: Optional[SceneManager] = None
        self.project_service: Optional[ProjectService] = None
        self.asset_service: Optional[AssetService] = None
        self._registry = create_default_registry()
        self._project_root = project_root or os.getcwd()
        self._global_state_dir = global_state_dir
        self._sandbox_paths = bool(sandbox_paths)
        self._initialize_engine()

    def _initialize_engine(self) -> None:
        self.game = HeadlessGame()
        self.scene_manager = SceneManager(self._registry)
        self.project_service = ProjectService(self._project_root, global_state_dir=self._global_state_dir)
        self.asset_service = AssetService(self.project_service)

        event_bus = EventBus()  # type: ignore
        self.game.set_scene_manager(self.scene_manager)
        self.game.set_project_service(self.project_service)
        self.game.set_render_system(RenderSystem())
        self.game.set_physics_system(PhysicsSystem(gravity=600))
        self.game.set_collision_system(CollisionSystem(event_bus))
        self.game.set_animation_system(AnimationSystem(event_bus))
        self.game.set_inspector_system(InspectorSystem())
        self.game.set_selection_system(SelectionSystem())
        self.game.set_event_bus(event_bus)
        self.game.set_input_system(InputSystem())
        self.game.set_character_controller_system(CharacterControllerSystem())
        self.game.set_player_controller_system(PlayerControllerSystem())
        self.game.set_script_behaviour_system(ScriptBehaviourSystem())
        self.game.set_audio_system(AudioSystem())
        self.game.set_ui_system(UISystem())
        self.game.set_ui_render_system(UIRenderSystem())
        self._register_optional_box2d_backend()

    def _register_optional_box2d_backend(self) -> None:
        if self.game is None or self.game._physics_system is None or self.game._event_bus is None:
            return
        try:
            self.game.set_physics_backend(
                Box2DPhysicsBackend(gravity=self.game._physics_system.gravity, event_bus=self.game._event_bus),
                backend_name="box2d",
            )
        except Exception as exc:
            print(f"[WARNING] Box2D backend unavailable: {exc}")

    def attach_runtime(self, game: Any, scene_manager: SceneManager, project_service: ProjectService) -> None:
        self.game = game
        self.scene_manager = scene_manager
        self.project_service = project_service
        self.asset_service = AssetService(project_service)
        if hasattr(self.game, "set_project_service"):
            self.game.set_project_service(project_service)

    def load_level(self, path: str) -> None:
        """Carga una escena JSON en el motor."""
        try:
            if self.scene_manager is None or self.game is None:
                raise RuntimeError("Engine not initialized")
            resolved_path = self._resolve_api_path(path, purpose="load level").as_posix()
            load_target = resolved_path if self._sandbox_paths else path
            if not self.game.load_scene_by_path(load_target):
                with open(resolved_path, "r", encoding="utf-8") as file:
                    data = json.load(file)
                world = self.scene_manager.load_scene(data, source_path=resolved_path)
                self.game.set_world(world)
                self.game.current_scene_path = resolved_path
                if self.project_service is not None:
                    self.project_service.set_last_scene(resolved_path)
        except Exception as exc:
            raise LevelLoadError(f"Fallo al cargar {path}: {exc}")

    def play(self) -> None:
        if self.game is not None:
            self.game.play()

    def stop(self) -> None:
        if self.game is not None:
            self.game.stop()

    def set_seed(self, seed: int | None) -> ActionResult:
        if self.game is None:
            return self._fail("Engine not initialized")
        self.game.set_seed(seed)
        return self._ok("Seed updated", {"seed": self.game.random_seed})

    def begin_transaction(self, label: str = "transaction") -> ActionResult:
        if self.scene_manager is None:
            return self._fail("SceneManager not ready")
        success = self.scene_manager.begin_transaction(label=label)
        return self._ok("Transaction started", {"label": label}) if success else self._fail("Transaction start failed")

    def apply_change(self, change: Dict[str, Any]) -> ActionResult:
        if self.scene_manager is None:
            return self._fail("SceneManager not ready")
        success = self.scene_manager.apply_change(Change.from_dict(change))
        return self._ok("Change applied", {"change": change}) if success else self._fail("Change apply failed")

    def commit_transaction(self) -> ActionResult:
        if self.scene_manager is None:
            return self._fail("SceneManager not ready")
        result = self.scene_manager.commit_transaction()
        return self._ok("Transaction committed", result) if result is not None else self._fail("Transaction commit failed")

    def rollback_transaction(self) -> ActionResult:
        if self.scene_manager is None:
            return self._fail("SceneManager not ready")
        success = self.scene_manager.rollback_transaction()
        return self._ok("Transaction rolled back") if success else self._fail("Transaction rollback failed")

    def undo(self) -> ActionResult:
        if self.game is None:
            return self._fail("Engine not initialized")
        success = self.game.undo()
        return self._ok("Undo applied") if success else self._fail("Undo unavailable")

    def redo(self) -> ActionResult:
        if self.game is None:
            return self._fail("Engine not initialized")
        success = self.game.redo()
        return self._ok("Redo applied") if success else self._fail("Redo unavailable")

    def step(self, frames: int = 1) -> None:
        if self.game is None:
            return
        if hasattr(self.game, "step_frame"):
            for _ in range(frames):
                self.game.step_frame()
            return
        if hasattr(self.game, "step"):
            for _ in range(frames):
                self.game.step()

    def get_recent_events(self, count: int = 50) -> list[Dict[str, Any]]:
        """Devuelve eventos recientes en formato serializable sin exponer internals."""
        if self.game is None or self.game._event_bus is None:
            return []
        limit = max(0, int(count))
        events = self.game._event_bus.get_recent_events(limit)
        return [
            {
                "name": str(event.name),
                "data": json.loads(json.dumps(event.data, ensure_ascii=True, default=str)),
            }
            for event in events
        ]

    def reset_profiler(self, run_label: str = "default") -> ActionResult:
        if self.game is None:
            return self._fail("Engine not initialized")
        self.game.reset_profiler(run_label=run_label)
        return self._ok("Profiler reset", {"run_label": run_label})

    def get_profiler_report(self) -> Dict[str, Any]:
        if self.game is None:
            return {}
        return self.game.get_profiler_report()

    def configure_debug_overlay(
        self,
        *,
        draw_colliders: Optional[bool] = None,
        draw_labels: Optional[bool] = None,
        draw_tile_chunks: Optional[bool] = None,
        draw_camera: Optional[bool] = None,
        primitives: Optional[list[Dict[str, Any]]] = None,
    ) -> ActionResult:
        if self.game is None or self.game._render_system is None:
            return self._fail("Render system not ready")
        self.game.debug_draw_colliders = self.game.debug_draw_colliders if draw_colliders is None else bool(draw_colliders)
        self.game.debug_draw_labels = self.game.debug_draw_labels if draw_labels is None else bool(draw_labels)
        self.game._render_system.set_debug_options(
            draw_colliders=draw_colliders,
            draw_labels=draw_labels,
            draw_tile_chunks=draw_tile_chunks,
            draw_camera=draw_camera,
        )
        if primitives is not None:
            self.game._render_system.set_debug_primitives(primitives)
        return self._ok(
            "Debug overlay configured",
            {
                "draw_colliders": self.game._render_system.debug_draw_colliders,
                "draw_labels": self.game._render_system.debug_draw_labels,
                "draw_tile_chunks": self.game._render_system.debug_draw_tile_chunks,
                "draw_camera": self.game._render_system.debug_draw_camera,
                "primitive_count": len(getattr(self.game._render_system, "_debug_primitives", [])),
            },
        )

    def clear_debug_primitives(self) -> ActionResult:
        if self.game is None or self.game._render_system is None:
            return self._fail("Render system not ready")
        self.game._render_system.clear_debug_primitives()
        return self._ok("Debug primitives cleared")

    def get_debug_geometry_dump(
        self,
        viewport_width: int = 800,
        viewport_height: int = 600,
    ) -> Dict[str, Any]:
        if self.game is None or self.game._render_system is None or self.game.world is None:
            return {}
        return self.game._render_system.get_debug_geometry_dump(
            self.game.world,
            viewport_size=(float(viewport_width), float(viewport_height)),
        )

    def get_status(self) -> EngineStatus:
        if self.game is None:
            raise RuntimeError("Engine not initialized")
        world = self.game.world
        return {
            "state": str(self.game.state),
            "frame": self.game.time.frame_count,
            "time": self.game.time.total_time,
            "fps": self.game.time.fps,
            "entity_count": world.entity_count() if world else 0,
        }

    def list_entities(
        self,
        tag: Optional[str] = None,
        layer: Optional[str] = None,
        active: Optional[bool] = None,
    ) -> list[EntityData]:
        """Devuelve la escena completa en formato serializable."""
        if self.game is None or self.game.world is None:
            return []
        entities: list[EntityData] = []
        for entity in self.game.world.get_all_entities():
            if tag is not None and entity.tag != tag:
                continue
            if layer is not None and entity.layer != layer:
                continue
            if active is not None and entity.active != active:
                continue
            entities.append(self.get_entity(entity.name))
        return entities

    def get_entity(self, name: str) -> EntityData:
        """Obtiene datos de una entidad."""
        if not self.game or not self.game.world:
            raise RuntimeError("No world loaded")

        entity = self.game.world.get_entity_by_name(name)
        if not entity:
            raise EntityNotFoundError(f"Entity '{name}' not found")

        # Serializar componentes
        components_data: Dict[str, Any] = {}
        for comp_type, comp in entity._components.items():
            if hasattr(comp, "to_dict"):
                components_data[comp_type.__name__] = comp.to_dict()

        return {
            "name": entity.name,
            "active": entity.active,
            "tag": entity.tag,
            "layer": entity.layer,
            "parent": entity.parent_name,
            "prefab_instance": entity.prefab_instance,
            "components": components_data,
            "component_metadata": {
                comp_type.__name__: dict(entity.get_component_metadata(comp_type))
                for comp_type in entity._components.keys()
            },
        }

    def create_entity(self, name: str, components: Optional[Dict[str, Dict[str, Any]]] = None) -> ActionResult:
        self._ensure_edit_mode()
        if self.scene_manager is None:
            return self._fail("SceneManager not ready")
        success = self.scene_manager.create_entity(name, components=components)
        return self._ok("Entity created", {"entity": name}) if success else self._fail("Entity already exists")

    def delete_entity(self, name: str) -> ActionResult:
        self._ensure_edit_mode()
        if self.scene_manager is None:
            return self._fail("SceneManager not ready")
        success = self.scene_manager.remove_entity(name)
        return self._ok("Entity removed", {"entity": name}) if success else self._fail("Entity not found")

    def set_entity_active(self, name: str, active: bool) -> ActionResult:
        self._ensure_edit_mode()
        return self._apply_entity_property(name, "active", active, "Entity active updated")

    def set_entity_tag(self, name: str, tag: str) -> ActionResult:
        self._ensure_edit_mode()
        return self._apply_entity_property(name, "tag", tag, "Entity tag updated")

    def set_entity_layer(self, name: str, layer: str) -> ActionResult:
        self._ensure_edit_mode()
        return self._apply_entity_property(name, "layer", layer, "Entity layer updated")

    def set_entity_parent(self, name: str, parent_name: Optional[str]) -> ActionResult:
        self._ensure_edit_mode()
        if self.scene_manager is None:
            return self._fail("SceneManager not ready")
        success = self.scene_manager.set_entity_parent(name, parent_name)
        return self._ok("Entity parent updated", {"entity": name, "parent": parent_name}) if success else self._fail("Entity parent update failed")

    def create_child_entity(
        self,
        parent_name: str,
        name: str,
        components: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> ActionResult:
        self._ensure_edit_mode()
        if self.scene_manager is None:
            return self._fail("SceneManager not ready")
        success = self.scene_manager.create_child_entity(parent_name, name, components=components)
        return self._ok("Child entity created", {"entity": name, "parent": parent_name}) if success else self._fail("Child entity creation failed")

    def add_component(self, entity_name: str, component_name: str, data: Optional[Dict[str, Any]] = None) -> ActionResult:
        self._ensure_edit_mode()
        if self.scene_manager is None:
            return self._fail("SceneManager not ready")
        success = self.scene_manager.add_component_to_entity(entity_name, component_name, component_data=data)
        return self._ok("Component added", {"entity": entity_name, "component": component_name}) if success else self._fail("Component add failed")

    def remove_component(self, entity_name: str, component_name: str) -> ActionResult:
        self._ensure_edit_mode()
        if self.scene_manager is None:
            return self._fail("SceneManager not ready")
        success = self.scene_manager.remove_component_from_entity(entity_name, component_name)
        return self._ok("Component removed", {"entity": entity_name, "component": component_name}) if success else self._fail("Component remove failed")

    def edit_component(self, entity_name: str, component: str, property: str, value: Any) -> ActionResult:
        self._ensure_edit_mode()
        if self.scene_manager is None:
            return self._fail("SceneManager not ready")
        success = self.scene_manager.apply_edit_to_world(entity_name, component, property, value)
        return self._ok("Edit applied") if success else self._fail("Edit failed (check names/property)")

    def set_component_enabled(self, entity_name: str, component_name: str, enabled: bool) -> ActionResult:
        """Activa o desactiva un componente usando la misma via de authoring."""
        return self.edit_component(entity_name, component_name, "enabled", enabled)

    def create_camera2d(
        self,
        name: str,
        transform: Optional[Dict[str, Any]] = None,
        camera: Optional[Dict[str, Any]] = None,
    ) -> ActionResult:
        """Crea una entidad con Transform y Camera2D usando solo datos serializables."""
        self._ensure_edit_mode()
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
        """Actualiza varias propiedades de Camera2D en la misma via serializable."""
        self._ensure_edit_mode()
        for property_name, value in properties.items():
            result = self.edit_component(entity_name, "Camera2D", property_name, value)
            if not result["success"]:
                return result
        return self._ok("Camera2D updated", {"entity": entity_name})

    def set_camera_framing(self, entity_name: str, framing: Dict[str, Any]) -> ActionResult:
        """Atajo para actualizar framing/clamp de Camera2D usando datos serializables."""
        return self.update_camera2d(entity_name, framing)

    def get_primary_camera(self) -> Optional[EntityData]:
        """Devuelve la camara primaria activa si existe."""
        if self.game is None or self.game.world is None:
            return None
        from engine.components.camera2d import Camera2D
        from engine.components.transform import Transform

        for entity in self.game.world.get_entities_with(Transform, Camera2D):
            camera_component = entity.get_component(Camera2D)
            if camera_component is not None and camera_component.is_primary:
                return self.get_entity(entity.name)
        return None

    def create_input_map(self, name: str, bindings: Optional[Dict[str, Any]] = None) -> ActionResult:
        """Crea una entidad con InputMap serializable y editable por API."""
        self._ensure_edit_mode()
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
        """Actualiza bindings de InputMap sin usar internals del motor."""
        self._ensure_edit_mode()
        for property_name, value in bindings.items():
            result = self.edit_component(entity_name, "InputMap", property_name, value)
            if not result["success"]:
                return result
        return self._ok("InputMap updated", {"entity": entity_name})

    def get_input_state(self, entity_name: str) -> Dict[str, float]:
        """Devuelve el ultimo estado calculado por InputSystem para una entidad."""
        from engine.components.inputmap import InputMap

        entity = self._require_entity(entity_name)
        input_map = entity.get_component(InputMap)
        if input_map is None:
            return {}
        return dict(input_map.last_state)

    def inject_input_state(self, entity_name: str, state: Dict[str, float], frames: int = 1) -> ActionResult:
        """Inyecta input en el runtime usando la API publica."""
        if self.game is None:
            return self._fail("Engine not initialized")
        if self.game._input_system is None:
            return self._fail("Input system not ready")
        normalized_name = str(entity_name).strip()
        if not normalized_name:
            return self._fail("Entity name is required")
        normalized_frames = max(1, int(frames))
        self.game._input_system.inject_state(normalized_name, dict(state), frames=normalized_frames)
        return self._ok(
            "Input injected",
            {
                "entity": normalized_name,
                "state": dict(state),
                "frames": normalized_frames,
            },
        )

    def create_audio_source(
        self,
        name: str,
        transform: Optional[Dict[str, Any]] = None,
        audio: Optional[Dict[str, Any]] = None,
    ) -> ActionResult:
        """Crea una entidad con AudioSource serializable."""
        self._ensure_edit_mode()
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
        """Actualiza propiedades serializables de AudioSource."""
        self._ensure_edit_mode()
        for property_name, value in properties.items():
            result = self.edit_component(entity_name, "AudioSource", property_name, value)
            if not result["success"]:
                return result
        return self._ok("AudioSource updated", {"entity": entity_name})

    def get_audio_state(self, entity_name: str) -> Dict[str, Any]:
        """Devuelve el estado serializable de AudioSource para inspeccion no visual."""
        from engine.components.audiosource import AudioSource

        entity = self._require_entity(entity_name)
        audio_source = entity.get_component(AudioSource)
        if audio_source is None:
            return {}
        return audio_source.to_dict()

    def add_script_behaviour(
        self,
        entity_name: str,
        module_path: str,
        public_data: Optional[Dict[str, Any]] = None,
        run_in_edit_mode: bool = False,
        enabled: bool = True,
    ) -> ActionResult:
        """Añade un ScriptBehaviour serializable a una entidad editable por API."""
        self._ensure_edit_mode()
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
        """Actualiza varias propiedades serializables de ScriptBehaviour."""
        self._ensure_edit_mode()
        for property_name, value in properties.items():
            result = self.edit_component(entity_name, "ScriptBehaviour", property_name, value)
            if not result["success"]:
                return result
        return self._ok("ScriptBehaviour updated", {"entity": entity_name})

    def get_script_public_data(self, entity_name: str) -> Dict[str, Any]:
        """Expone la bolsa de datos persistente del ScriptBehaviour."""
        from engine.components.scriptbehaviour import ScriptBehaviour

        entity = self._require_entity(entity_name)
        script_behaviour = entity.get_component(ScriptBehaviour)
        if script_behaviour is None:
            return {}
        return dict(script_behaviour.public_data)

    def set_script_public_data(self, entity_name: str, public_data: Dict[str, Any]) -> ActionResult:
        """Actualiza la bolsa serializable public_data de un ScriptBehaviour."""
        self._ensure_edit_mode()
        return self.edit_component(entity_name, "ScriptBehaviour", "public_data", public_data)

    def set_feature_metadata(self, key: str, value: Any) -> ActionResult:
        """Guarda metadata serializable de escena para input, backlog u otras capacidades."""
        self._ensure_edit_mode()
        if self.scene_manager is None or self.scene_manager.current_scene is None:
            return self._fail("No scene loaded")
        self.scene_manager.current_scene.set_feature_metadata(key, value)
        if self.game is not None and self.game.world is not None:
            self.game.world.feature_metadata[key] = value
        return self._ok("Feature metadata updated", {"key": key})

    def set_sorting_layers(self, order: list[str]) -> ActionResult:
        self._ensure_edit_mode()
        metadata = self.get_feature_metadata()
        render_2d = dict(metadata.get("render_2d", {}))
        render_2d["sorting_layers"] = self._normalize_sorting_layers(order)
        return self.set_feature_metadata("render_2d", render_2d)

    def set_render_order(self, entity_name: str, sorting_layer: str, order_in_layer: int) -> ActionResult:
        self._ensure_edit_mode()
        entity = self._require_entity(entity_name)
        layer_name = sorting_layer.strip() or "Default"
        current_layers = self._normalize_sorting_layers(
            self.get_feature_metadata().get("render_2d", {}).get("sorting_layers", ["Default"])
        )
        if layer_name not in current_layers:
            return self._fail(f"Sorting layer '{layer_name}' is not configured")
        clamped_order = self._clamp_render_order(order_in_layer)
        has_component = any(comp.__name__ == "RenderOrder2D" for comp in entity._components.keys())
        if not has_component:
            result = self.add_component(
                entity_name,
                "RenderOrder2D",
                {"enabled": True, "sorting_layer": layer_name, "order_in_layer": clamped_order},
            )
            return result
        result = self.edit_component(entity_name, "RenderOrder2D", "sorting_layer", layer_name)
        if not result["success"]:
            return result
        return self.edit_component(entity_name, "RenderOrder2D", "order_in_layer", clamped_order)

    def set_physics_layer_collision(self, layer_a: str, layer_b: str, enabled: bool) -> ActionResult:
        self._ensure_edit_mode()
        metadata = self.get_feature_metadata()
        physics_2d = dict(metadata.get("physics_2d", {}))
        matrix = dict(physics_2d.get("layer_matrix", {}))
        matrix[f"{layer_a}|{layer_b}"] = bool(enabled)
        matrix[f"{layer_b}|{layer_a}"] = bool(enabled)
        physics_2d["layer_matrix"] = matrix
        return self.set_feature_metadata("physics_2d", physics_2d)

    def set_physics_backend(self, backend_name: str) -> ActionResult:
        self._ensure_edit_mode()
        normalized = str(backend_name or "").strip() or "legacy_aabb"
        if normalized not in {"legacy_aabb", "box2d"}:
            return self._fail(f"Unsupported physics backend: {normalized}")
        available_backends = getattr(self.game, "_physics_backends", {}) if self.game is not None else {}
        if normalized not in available_backends:
            return self._fail(f"Physics backend not available in this runtime: {normalized}")
        metadata = self.get_feature_metadata()
        physics_2d = dict(metadata.get("physics_2d", {}))
        physics_2d["backend"] = normalized
        result = self.set_feature_metadata("physics_2d", physics_2d)
        if result["success"] and self.game is not None and hasattr(self.game, "_refresh_default_physics_backend"):
            self.game._refresh_default_physics_backend()
        return result

    def query_physics_aabb(self, left: float, top: float, right: float, bottom: float) -> list[Dict[str, Any]]:
        if self.game is None or self.game.world is None:
            return []
        backend_name = self.game._resolve_physics_backend_name(self.game.world) if hasattr(self.game, "_resolve_physics_backend_name") else "legacy_aabb"
        backend = getattr(self.game, "_physics_backends", {}).get(backend_name)
        if backend is None:
            return []
        return backend.query_aabb(self.game.world, (left, top, right, bottom))

    def query_physics_ray(
        self,
        origin_x: float,
        origin_y: float,
        direction_x: float,
        direction_y: float,
        max_distance: float,
    ) -> list[Dict[str, Any]]:
        if self.game is None or self.game.world is None:
            return []
        backend_name = self.game._resolve_physics_backend_name(self.game.world) if hasattr(self.game, "_resolve_physics_backend_name") else "legacy_aabb"
        backend = getattr(self.game, "_physics_backends", {}).get(backend_name)
        if backend is None:
            return []
        return backend.query_ray(
            self.game.world,
            (origin_x, origin_y),
            (direction_x, direction_y),
            max_distance,
        )

    def set_rigidbody_constraints(self, entity_name: str, constraints: list[str]) -> ActionResult:
        """Configura constraints estilo Unity para RigidBody usando estado serializable."""
        self._ensure_edit_mode()
        normalized = RigidBody.normalize_constraints(constraints)
        invalid = [value for value in constraints if str(value).strip() not in RigidBody.VALID_CONSTRAINTS]
        if invalid:
            return self._fail(f"Unsupported constraints: {invalid}")
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

    def instantiate_prefab(
        self,
        path: str,
        name: Optional[str] = None,
        parent: Optional[str] = None,
        overrides: Optional[Dict[str, Any]] = None,
    ) -> ActionResult:
        self._ensure_edit_mode()
        if self.scene_manager is None or self.project_service is None:
            return self._fail("SceneManager not ready")
        try:
            resolved_path = self._resolve_api_path(path, purpose="instantiate prefab")
        except InvalidOperationError as exc:
            return self._fail(str(exc))
        prefab_data = PrefabManager.load_prefab_data(resolved_path.as_posix())
        if prefab_data is None:
            return self._fail("Prefab not found")
        entity_name = name or prefab_data.get("root_name", "Prefab")
        scene_source_path = self.scene_manager.current_scene.source_path if self.scene_manager.current_scene is not None else None
        if scene_source_path:
            prefab_locator = Path(os.path.relpath(resolved_path.as_posix(), Path(scene_source_path).resolve().parent.as_posix())).as_posix()
        else:
            prefab_locator = self.project_service.to_relative_path(resolved_path)
        success = self.scene_manager.instantiate_prefab(
            entity_name,
            prefab_path=prefab_locator,
            parent=parent,
            overrides=overrides,
            root_name=prefab_data.get("root_name", entity_name),
        )
        return self._ok("Prefab instantiated", {"entity": entity_name}) if success else self._fail("Prefab instantiation failed")

    def unpack_prefab(self, entity_name: str) -> ActionResult:
        self._ensure_edit_mode()
        if self.scene_manager is None:
            return self._fail("SceneManager not ready")
        success = self.scene_manager.unpack_prefab(entity_name)
        return self._ok("Prefab unpacked", {"entity": entity_name}) if success else self._fail("Prefab unpack failed")

    def apply_prefab_overrides(self, entity_name: str) -> ActionResult:
        self._ensure_edit_mode()
        if self.scene_manager is None:
            return self._fail("SceneManager not ready")
        success = self.scene_manager.apply_prefab_overrides(entity_name)
        return self._ok("Prefab overrides applied", {"entity": entity_name}) if success else self._fail("Prefab apply failed")

    def get_feature_metadata(self) -> Dict[str, Any]:
        """Devuelve la metadata extendida de la escena."""
        if self.scene_manager is None or self.scene_manager.current_scene is None:
            return {}
        return self.scene_manager.current_scene.feature_metadata

    def get_scene_connections(self) -> Dict[str, str]:
        if self.scene_manager is None:
            return {}
        return self.scene_manager.get_scene_flow()

    def list_open_scenes(self) -> list[Dict[str, Any]]:
        if self.scene_manager is None:
            return []
        return self.scene_manager.list_open_scenes()

    def get_active_scene(self) -> Dict[str, Any]:
        if self.scene_manager is None or self.scene_manager.current_scene is None:
            return {}
        return {
            "key": self.scene_manager.active_scene_key,
            "name": self.scene_manager.current_scene.name,
            "path": self.scene_manager.current_scene.source_path or "",
            "dirty": self.scene_manager.is_dirty,
        }

    def activate_scene(self, key_or_path: str) -> ActionResult:
        if self.game is None:
            return self._fail("Engine not initialized")
        success = self.game._activate_scene_workspace_tab(self._resolve_scene_reference(key_or_path))
        return self._ok("Scene activated", self.get_active_scene()) if success else self._fail("Scene activation failed")

    def close_scene(self, key_or_path: str, discard_changes: bool = False) -> ActionResult:
        if self.game is None or self.scene_manager is None:
            return self._fail("Engine not initialized")
        resolved_ref = self._resolve_scene_reference(key_or_path)
        if not discard_changes:
            entry = self.scene_manager._resolve_entry(resolved_ref)  # type: ignore[attr-defined]
            if entry is not None and entry.dirty:
                return self._fail("Scene has unsaved changes")
        success = self.game._close_scene_workspace_tab(resolved_ref, discard_changes=discard_changes)
        return self._ok("Scene closed", {"open_scenes": self.list_open_scenes()}) if success else self._fail("Scene close failed")

    def save_scene(self, key_or_path: Optional[str] = None, path: Optional[str] = None) -> ActionResult:
        if self.scene_manager is None:
            return self._fail("SceneManager not ready")
        target = self._resolve_scene_reference(key_or_path or self.scene_manager.active_scene_key)
        entry = self.scene_manager._resolve_entry(target)  # type: ignore[attr-defined]
        if entry is None:
            return self._fail("Scene not found")
        target_path = path or entry.source_path
        if not target_path:
            return self._fail("Scene has no save path")
        try:
            if path:
                target_path = self._resolve_api_path(path, purpose="save scene").as_posix()
        except InvalidOperationError as exc:
            return self._fail(str(exc))
        success = self.scene_manager.save_scene_to_file(target_path, key=entry.key)
        if not success:
            return self._fail("Scene save failed")
        if self.game is not None:
            self.game._sync_scene_workspace_ui(apply_view_state=True)
        return self._ok("Scene saved", {"path": target_path, "scene": self.get_active_scene()})

    def copy_entity_to_scene(self, entity_name: str, target_scene: str) -> ActionResult:
        self._ensure_edit_mode()
        if self.scene_manager is None:
            return self._fail("SceneManager not ready")
        if not self.scene_manager.copy_entity_subtree(entity_name):
            return self._fail("Entity copy failed")
        if not self.scene_manager.paste_copied_entities(self._resolve_scene_reference(target_scene)):
            return self._fail("Entity paste failed")
        if self.game is not None:
            self.game._sync_scene_workspace_ui(apply_view_state=False)
        return self._ok("Entity copied to scene", {"entity": entity_name, "target_scene": target_scene})

    def set_scene_link(
        self,
        entity_name: str,
        target_path: str,
        flow_key: str = "",
        preview_label: str = "",
    ) -> ActionResult:
        self._ensure_edit_mode()
        if self.scene_manager is None or self.project_service is None:
            return self._fail("SceneManager not ready")
        normalized_target = self.project_service.to_relative_path(target_path) if target_path else ""
        payload = {
            "enabled": True,
            "target_path": normalized_target,
            "flow_key": str(flow_key or "").strip(),
            "preview_label": str(preview_label or "").strip(),
        }
        entity = self.scene_manager.find_entity_data(entity_name)
        if entity is None:
            return self._fail("Entity not found")
        has_link = "SceneLink" in entity.get("components", {})
        success = (
            self.scene_manager.replace_component_data(entity_name, "SceneLink", payload)
            if has_link
            else self.scene_manager.add_component_to_entity(entity_name, "SceneLink", payload)
        )
        return self._ok("SceneLink updated", {"entity": entity_name, "target_path": normalized_target}) if success else self._fail("SceneLink update failed")

    def create_canvas(
        self,
        name: str = "Canvas",
        reference_width: int = 800,
        reference_height: int = 600,
        sort_order: int = 0,
    ) -> ActionResult:
        self._ensure_edit_mode()
        components: Dict[str, Dict[str, Any]] = {
            "Canvas": {
                "enabled": True,
                "render_mode": "screen_space_overlay",
                "reference_width": reference_width,
                "reference_height": reference_height,
                "match_mode": "stretch",
                "sort_order": sort_order,
            },
            "RectTransform": {
                "enabled": True,
                "anchor_min_x": 0.0,
                "anchor_min_y": 0.0,
                "anchor_max_x": 1.0,
                "anchor_max_y": 1.0,
                "pivot_x": 0.0,
                "pivot_y": 0.0,
                "anchored_x": 0.0,
                "anchored_y": 0.0,
                "width": 0.0,
                "height": 0.0,
                "rotation": 0.0,
                "scale_x": 1.0,
                "scale_y": 1.0,
            },
        }
        return self.create_entity(name, components=components)

    def create_ui_element(
        self,
        name: str,
        parent: str,
        rect_transform: Optional[Dict[str, Any]] = None,
    ) -> ActionResult:
        self._ensure_edit_mode()
        components: Dict[str, Dict[str, Any]] = {
            "RectTransform": {
                "enabled": True,
                "anchor_min_x": 0.5,
                "anchor_min_y": 0.5,
                "anchor_max_x": 0.5,
                "anchor_max_y": 0.5,
                "pivot_x": 0.5,
                "pivot_y": 0.5,
                "anchored_x": 0.0,
                "anchored_y": 0.0,
                "width": 100.0,
                "height": 40.0,
                "rotation": 0.0,
                "scale_x": 1.0,
                "scale_y": 1.0,
            }
        }
        if rect_transform:
            components["RectTransform"].update(rect_transform)
        return self.create_child_entity(parent, name, components=components)

    def set_rect_transform(self, entity_name: str, properties: Dict[str, Any]) -> ActionResult:
        self._ensure_edit_mode()
        for property_name, value in properties.items():
            result = self.edit_component(entity_name, "RectTransform", property_name, value)
            if not result["success"]:
                return result
        return self._ok("RectTransform updated", {"entity": entity_name})

    def create_ui_text(
        self,
        name: str,
        text: str,
        parent: str,
        rect_transform: Optional[Dict[str, Any]] = None,
        font_size: int = 24,
        alignment: str = "center",
    ) -> ActionResult:
        self._ensure_edit_mode()
        result = self.create_ui_element(name=name, parent=parent, rect_transform=rect_transform)
        if not result["success"]:
            return result
        add_result = self.add_component(
            name,
            "UIText",
            {
                "enabled": True,
                "text": text,
                "font_size": font_size,
                "color": [255, 255, 255, 255],
                "alignment": alignment,
                "wrap": False,
            },
        )
        return add_result if not add_result["success"] else self._ok("UIText created", {"entity": name})

    def create_ui_button(
        self,
        name: str,
        label: str,
        parent: str,
        rect_transform: Optional[Dict[str, Any]] = None,
        on_click: Optional[Dict[str, Any]] = None,
    ) -> ActionResult:
        self._ensure_edit_mode()
        result = self.create_ui_element(name=name, parent=parent, rect_transform=rect_transform)
        if not result["success"]:
            return result
        add_result = self.add_component(
            name,
            "UIButton",
            {
                "enabled": True,
                "interactable": True,
                "label": label,
                "normal_color": [72, 72, 72, 255],
                "hover_color": [92, 92, 92, 255],
                "pressed_color": [56, 56, 56, 255],
                "disabled_color": [48, 48, 48, 200],
                "transition_scale_pressed": 0.96,
                "on_click": on_click or {"type": "emit_event", "name": "ui.button_clicked"},
            },
        )
        return add_result if not add_result["success"] else self._ok("UIButton created", {"entity": name})

    def set_button_on_click(self, entity_name: str, on_click: Dict[str, Any]) -> ActionResult:
        self._ensure_edit_mode()
        return self.edit_component(entity_name, "UIButton", "on_click", on_click)

    def list_ui_nodes(self) -> list[EntityData]:
        if self.game is None or self.game.world is None:
            return []
        nodes: list[EntityData] = []
        for entity in self.game.world.get_all_entities():
            if any(entity.has_component(component) for component in (Canvas, RectTransform, UIText, UIButton)):
                nodes.append(self.get_entity(entity.name))
        return nodes

    def get_ui_layout(self, entity_name: str) -> Dict[str, Any]:
        if self.game is None or self.game.world is None or self.game._ui_system is None:
            return {}
        self.game._update_ui_overlay(self.game.world, (float(self.game.width), float(self.game.height)))
        return self.game._ui_system.get_entity_screen_rect(entity_name) or {}

    def click_ui_button(self, entity_name: str) -> ActionResult:
        if self.game is None or self.game.world is None or self.game._ui_system is None:
            return self._fail("UI system not ready")
        clicked = self.game._ui_system.click_entity(self.game.world, entity_name, (float(self.game.width), float(self.game.height)))
        return self._ok("UIButton clicked", {"entity": entity_name}) if clicked else self._fail("UIButton click failed")

    def set_scene_connection(self, key: str, path: str) -> ActionResult:
        self._ensure_edit_mode()
        if self.scene_manager is None:
            return self._fail("SceneManager not ready")
        normalized = ""
        if path and self.project_service is not None:
            normalized = self.project_service.to_relative_path(path)
        success = self.scene_manager.set_scene_flow_target(key, normalized)
        return self._ok("Scene connection updated", {"key": key, "path": normalized}) if success else self._fail("Scene connection update failed")

    def set_next_scene(self, path: str) -> ActionResult:
        return self.set_scene_connection("next_scene", path)

    def set_menu_scene(self, path: str) -> ActionResult:
        return self.set_scene_connection("menu_scene", path)

    def set_previous_scene(self, path: str) -> ActionResult:
        return self.set_scene_connection("previous_scene", path)

    def load_scene(self, path: str) -> ActionResult:
        if self.game is None:
            return self._fail("Engine not initialized")
        success = self.game.load_scene_by_path(path)
        return self._ok("Scene loaded", {"path": self.game.current_scene_path}) if success else self._fail("Scene load failed")

    def create_scene(self, name: str) -> ActionResult:
        if self.game is None:
            return self._fail("Engine not initialized")
        success = self.game.create_scene(name)
        return self._ok("Scene created", {"path": self.game.current_scene_path}) if success else self._fail("Scene creation failed")

    def open_scene(self, path: str) -> ActionResult:
        return self.load_scene(path)

    def load_next_scene(self) -> ActionResult:
        if self.game is None:
            return self._fail("Engine not initialized")
        success = self.game.load_scene_flow_target("next_scene")
        return self._ok("Next scene loaded", {"path": self.game.current_scene_path}) if success else self._fail("Next scene is not configured")

    def load_menu_scene(self) -> ActionResult:
        if self.game is None:
            return self._fail("Engine not initialized")
        success = self.game.load_scene_flow_target("menu_scene")
        return self._ok("Menu scene loaded", {"path": self.game.current_scene_path}) if success else self._fail("Menu scene is not configured")

    def play_audio(self, entity_name: str) -> ActionResult:
        """Dispara un AudioSource por nombre de entidad."""
        if self.game is None or self.game.world is None or self.game.audio_system is None:
            return self._fail("Audio system not ready")
        success = self.game.audio_system.play(self.game.world, entity_name)
        return self._ok("Audio started", {"entity": entity_name}) if success else self._fail("Audio source not found or disabled")

    def stop_audio(self, entity_name: str) -> ActionResult:
        """Detiene un AudioSource por nombre de entidad."""
        if self.game is None or self.game.world is None or self.game.audio_system is None:
            return self._fail("Audio system not ready")
        success = self.game.audio_system.stop(self.game.world, entity_name)
        return self._ok("Audio stopped", {"entity": entity_name}) if success else self._fail("Audio source not found")

    def shutdown(self) -> None:
        if self.game is not None:
            self.game.headless_running = False

    def list_recent_projects(self) -> list[Dict[str, Any]]:
        if self.project_service is None:
            return []
        return self.project_service.list_recent_projects()

    def get_project_manifest(self) -> Dict[str, Any]:
        if self.project_service is None:
            return {}
        return self.project_service.get_project_summary()

    def open_project(self, path: str) -> ActionResult:
        if self.project_service is None or self.game is None:
            return self._fail("Project service not ready")
        success = self.game.open_project(path)
        if not success:
            return self._fail("Open project failed")
        return self._ok("Project opened", {"path": self.project_service.project_root.as_posix()})

    def get_editor_state(self) -> Dict[str, Any]:
        if self.project_service is None:
            return {}
        return self.project_service.load_editor_state()

    def save_editor_state(self, data: Dict[str, Any]) -> ActionResult:
        if self.project_service is None:
            return self._fail("Project service not ready")
        self.project_service.save_editor_state(data)
        return self._ok("Editor state saved", self.project_service.load_editor_state())

    def list_project_assets(self, search: str = "") -> list[Dict[str, Any]]:
        if self.asset_service is None:
            return []
        return self.asset_service.list_assets(search=search)

    def list_project_prefabs(self) -> list[str]:
        if self.project_service is None or not self.project_service.has_project:
            return []
        prefabs_root = self.project_service.get_project_path("prefabs")
        return [
            self.project_service.to_relative_path(path)
            for path in sorted(prefabs_root.rglob("*.json"))
            if path.is_file()
        ]

    def list_project_scripts(self) -> list[str]:
        if self.project_service is None or not self.project_service.has_project:
            return []
        scripts_root = self.project_service.get_project_path("scripts")
        return [
            self.project_service.to_relative_path(path)
            for path in sorted(scripts_root.rglob("*.py"))
            if path.is_file()
        ]

    def refresh_asset_catalog(self) -> ActionResult:
        if self.asset_service is None:
            return self._fail("Asset service not ready")
        catalog = self.asset_service.refresh_catalog()
        return self._ok("Asset catalog refreshed", {"count": len(catalog.get("assets", [])), "catalog": catalog})

    def build_asset_artifacts(self) -> ActionResult:
        if self.asset_service is None:
            return self._fail("Asset service not ready")
        report = self.asset_service.build_asset_artifacts()
        return self._ok("Asset artifacts built", report)

    def create_asset_bundle(self) -> ActionResult:
        if self.asset_service is None:
            return self._fail("Asset service not ready")
        report = self.asset_service.create_bundle()
        return self._ok("Asset bundle created", report)

    def find_assets(
        self,
        search: str = "",
        asset_kind: str = "",
        importer: str = "",
        extensions: Optional[list[str]] = None,
    ) -> list[Dict[str, Any]]:
        if self.asset_service is None:
            return []
        return self.asset_service.find_assets(search=search, asset_kind=asset_kind, importer=importer, extensions=extensions)

    def get_asset_reference(self, locator: str) -> Dict[str, str]:
        if self.asset_service is None:
            return {"guid": "", "path": ""}
        return self.asset_service.get_asset_reference(locator)

    def move_asset(self, locator: str, destination_path: str) -> ActionResult:
        if self.asset_service is None:
            return self._fail("Asset service not ready")
        moved = self.asset_service.move_asset(locator, destination_path)
        return self._ok("Asset moved", moved) if moved is not None else self._fail("Asset move failed")

    def rename_asset(self, locator: str, new_name: str) -> ActionResult:
        if self.asset_service is None:
            return self._fail("Asset service not ready")
        renamed = self.asset_service.rename_asset(locator, new_name)
        return self._ok("Asset renamed", renamed) if renamed is not None else self._fail("Asset rename failed")

    def reimport_asset(self, locator: str) -> ActionResult:
        if self.asset_service is None:
            return self._fail("Asset service not ready")
        reimported = self.asset_service.reimport_asset(locator)
        return self._ok("Asset reimported", reimported) if reimported is not None else self._fail("Asset reimport failed")

    def get_asset_metadata(self, asset_path: str) -> Dict[str, Any]:
        if self.asset_service is None:
            return {}
        return self.asset_service.load_metadata(asset_path)

    def save_asset_metadata(self, asset_path: str, metadata: Dict[str, Any]) -> ActionResult:
        if self.asset_service is None:
            return self._fail("Asset service not ready")
        saved = self.asset_service.save_metadata(asset_path, metadata)
        return self._ok("Asset metadata saved", saved)

    def create_grid_slices(
        self,
        asset_path: str,
        cell_width: int,
        cell_height: int,
        margin: int = 0,
        spacing: int = 0,
        pivot_x: float = 0.5,
        pivot_y: float = 0.5,
        naming_prefix: Optional[str] = None,
    ) -> ActionResult:
        if self.asset_service is None:
            return self._fail("Asset service not ready")
        metadata = self.asset_service.generate_grid_slices(
            asset_path,
            cell_width=cell_width,
            cell_height=cell_height,
            margin=margin,
            spacing=spacing,
            pivot_x=pivot_x,
            pivot_y=pivot_y,
            naming_prefix=naming_prefix,
        )
        return self._ok("Grid slices created", metadata)

    def list_asset_slices(self, asset_path: str) -> list[Dict[str, Any]]:
        if self.asset_service is None:
            return []
        return self.asset_service.list_slices(asset_path)

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
        self._ensure_edit_mode()
        entity = self._require_entity(entity_name)
        has_tilemap = any(comp.__name__ == "Tilemap" for comp in entity._components.keys())
        tileset_ref = self.get_asset_reference(tileset) if tileset else {"guid": "", "path": ""}
        payload = Tilemap(
            cell_width=cell_width,
            cell_height=cell_height,
            orientation=orientation,
            tileset=tileset_ref if (tileset_ref.get("guid") or tileset_ref.get("path")) else tileset,
            tileset_path=tileset_ref.get("path", "") or tileset,
            layers=layers or [],
        ).to_dict()
        if self.scene_manager is None:
            return self._fail("SceneManager not ready")
        success = (
            self.scene_manager.replace_component_data(entity_name, "Tilemap", payload)
            if has_tilemap
            else self.scene_manager.add_component_to_entity(entity_name, "Tilemap", payload)
        )
        return self._ok("Tilemap updated", {"entity": entity_name}) if success else self._fail("Tilemap update failed")

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
        self._ensure_edit_mode()
        if self.scene_manager is None:
            return self._fail("SceneManager not ready")
        payload = self._load_tilemap_payload(entity_name)
        if payload is None:
            return self._fail("Tilemap not found")
        tilemap = Tilemap.from_dict(payload)
        source_ref = self.get_asset_reference(source) if source else {}
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
        return self._ok("Tilemap tile updated", {"entity": entity_name, "layer": layer_name, "x": x, "y": y}) if success else self._fail("Tilemap tile update failed")

    def clear_tilemap_tile(self, entity_name: str, layer_name: str, x: int, y: int) -> ActionResult:
        self._ensure_edit_mode()
        if self.scene_manager is None:
            return self._fail("SceneManager not ready")
        payload = self._load_tilemap_payload(entity_name)
        if payload is None:
            return self._fail("Tilemap not found")
        tilemap = Tilemap.from_dict(payload)
        tilemap.clear_tile(layer_name, x, y)
        success = self.scene_manager.replace_component_data(entity_name, "Tilemap", tilemap.to_dict())
        return self._ok("Tilemap tile cleared", {"entity": entity_name, "layer": layer_name, "x": x, "y": y}) if success else self._fail("Tilemap tile clear failed")

    def get_tilemap(self, entity_name: str) -> Dict[str, Any]:
        payload = self._load_tilemap_payload(entity_name)
        return payload or {}

    def list_animator_states(self, entity_name: str) -> list[Dict[str, Any]]:
        entity = self._require_entity(entity_name)
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
        self._ensure_edit_mode()
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
        self._ensure_edit_mode()
        if self.scene_manager is None:
            return self._fail("SceneManager not ready")
        if not state_name.strip():
            return self._fail("Animator state name is required")
        payload = self._load_animator_payload(entity_name)
        if payload is None:
            return self._fail("Animator not found")
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
        return self._ok("Animator state updated", {"entity": entity_name, "state": state_name}) if success else self._fail("Animator state update failed")

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
        self._ensure_edit_mode()
        if self.scene_manager is None:
            return self._fail("SceneManager not ready")
        payload = self._load_animator_payload(entity_name)
        if payload is None:
            return self._fail("Animator not found")
        animations = payload.setdefault("animations", {})
        if state_name not in animations:
            return self._fail("Animator state not found")
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
        return self._ok("Animator frames updated", {"entity": entity_name, "state": state_name}) if success else self._fail("Animator frames update failed")

    def remove_animator_state(self, entity_name: str, state_name: str) -> ActionResult:
        self._ensure_edit_mode()
        if self.scene_manager is None:
            return self._fail("SceneManager not ready")
        payload = self._load_animator_payload(entity_name)
        if payload is None:
            return self._fail("Animator not found")
        animations = payload.setdefault("animations", {})
        if state_name not in animations:
            return self._fail("Animator state not found")
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
        return self._ok("Animator state removed", {"entity": entity_name, "state": state_name}) if success else self._fail("Animator state remove failed")

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

    def _require_entity(self, name: str):
        if self.game is None or self.game.world is None:
            raise RuntimeError("No world loaded")
        entity = self.game.world.get_entity_by_name(name)
        if entity is None:
            raise EntityNotFoundError(f"Entity '{name}' not found")
        return entity

    def _apply_entity_property(self, name: str, property_name: str, value: Any, message: str) -> ActionResult:
        if self.scene_manager is None:
            return self._fail("SceneManager not ready")
        success = self.scene_manager.update_entity_property(name, property_name, value)
        return self._ok(message, {"entity": name}) if success else self._fail("Entity property update failed")

    def _load_animator_payload(self, entity_name: str) -> Optional[Dict[str, Any]]:
        if self.scene_manager is None or self.scene_manager.current_scene is None:
            return None
        entity_data = self.scene_manager.current_scene.find_entity(entity_name)
        if entity_data is None:
            return None
        component_data = entity_data.get("components", {}).get("Animator")
        if component_data is None:
            return None
        return json.loads(json.dumps(component_data))

    def _load_tilemap_payload(self, entity_name: str) -> Optional[Dict[str, Any]]:
        if self.scene_manager is None or self.scene_manager.current_scene is None:
            return None
        entity_data = self.scene_manager.current_scene.find_entity(entity_name)
        if entity_data is None:
            return None
        component_data = entity_data.get("components", {}).get("Tilemap")
        if component_data is None:
            return None
        return json.loads(json.dumps(component_data))

    def _ensure_edit_mode(self) -> None:
        if self.game is not None and not self.game.is_edit_mode:
            raise InvalidOperationError("Cannot edit in PLAY mode")

    def _ok(self, message: str, data: Any = None) -> ActionResult:
        return {"success": True, "message": message, "data": data}

    def _fail(self, message: str) -> ActionResult:
        return {"success": False, "message": message, "data": None}

    def _normalize_sorting_layers(self, order: list[str]) -> list[str]:
        normalized: list[str] = ["Default"]
        seen = {"Default"}
        for entry in order:
            layer_name = str(entry).strip()
            if not layer_name or layer_name in seen:
                continue
            seen.add(layer_name)
            normalized.append(layer_name)
        return normalized

    def _clamp_render_order(self, value: int) -> int:
        return max(RenderOrder2D.MIN_ORDER_IN_LAYER, min(RenderOrder2D.MAX_ORDER_IN_LAYER, int(value)))

    def _resolve_scene_reference(self, key_or_path: str) -> str:
        if not key_or_path:
            return ""
        value = str(key_or_path)
        if self.project_service is None:
            return value
        if value.endswith(".json") or "/" in value or "\\" in value:
            return self.project_service.resolve_path(value).as_posix()
        return value

    def _resolve_api_path(self, path: str | os.PathLike[str], *, purpose: str) -> Path:
        candidate = Path(path)
        if self.project_service is not None:
            resolved = self.project_service.resolve_path(candidate)
            project_root = self.project_service.project_root
        else:
            resolved = candidate.expanduser().resolve()
            project_root = Path(self._project_root).resolve()
        if not self._sandbox_paths:
            return resolved
        try:
            resolved.relative_to(project_root)
        except ValueError as exc:
            raise InvalidOperationError(f"Sandbox blocked path outside project root during {purpose}: {resolved.as_posix()}") from exc
        return resolved
