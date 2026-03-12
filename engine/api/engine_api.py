"""
engine/api/engine_api.py - Fachada publica del motor y del authoring IA-first
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from cli.headless_game import HeadlessGame
from engine.api.errors import (
    ComponentNotFoundError,
    EntityNotFoundError,
    InvalidOperationError,
    LevelLoadError,
)
from engine.api.types import ActionResult, EngineStatus, EntityData
from engine.events.event_bus import EventBus
from engine.inspector.inspector_system import InspectorSystem
from engine.levels.component_registry import create_default_registry
from engine.project.project_service import ProjectService
from engine.scenes.scene_manager import SceneManager
from engine.systems.animation_system import AnimationSystem
from engine.systems.audio_system import AudioSystem
from engine.systems.collision_system import CollisionSystem
from engine.systems.input_system import InputSystem
from engine.systems.physics_system import PhysicsSystem
from engine.systems.player_controller_system import PlayerControllerSystem
from engine.systems.script_behaviour_system import ScriptBehaviourSystem
from engine.systems.selection_system import SelectionSystem
from engine.assets.asset_service import AssetService


class EngineAPI:
    """
    API publica para controlar el motor y editar el contenido sin usar internals.
    """

    def __init__(self) -> None:
        self.game: Optional[HeadlessGame] = None
        self.scene_manager: Optional[SceneManager] = None
        self.project_service: Optional[ProjectService] = None
        self.asset_service: Optional[AssetService] = None
        self._registry = create_default_registry()
        self._initialize_engine()

    def _initialize_engine(self) -> None:
        self.game = HeadlessGame()
        self.scene_manager = SceneManager(self._registry)
        self.project_service = ProjectService(os.getcwd())
        self.asset_service = AssetService(self.project_service)

        event_bus = EventBus()  # type: ignore
        self.game.set_scene_manager(self.scene_manager)
        self.game.set_project_service(self.project_service)
        self.game.set_physics_system(PhysicsSystem(gravity=600))
        self.game.set_collision_system(CollisionSystem(event_bus))
        self.game.set_animation_system(AnimationSystem(event_bus))
        self.game.set_inspector_system(InspectorSystem())
        self.game.set_selection_system(SelectionSystem())
        self.game.set_event_bus(event_bus)
        self.game.set_input_system(InputSystem())
        self.game.set_player_controller_system(PlayerControllerSystem())
        self.game.set_script_behaviour_system(ScriptBehaviourSystem())
        self.game.set_audio_system(AudioSystem())

    def load_level(self, path: str) -> None:
        """Carga una escena JSON en el motor."""
        try:
            resolved_path = self.project_service.resolve_path(path).as_posix() if self.project_service is not None else path
            with open(resolved_path, "r", encoding="utf-8") as file:
                data = json.load(file)
            if self.scene_manager is None or self.game is None:
                raise RuntimeError("Engine not initialized")
            world = self.scene_manager.load_scene(data)
            self.game.set_world(world)
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

    def step(self, frames: int = 1) -> None:
        if self.game is None:
            return
        for _ in range(frames):
            self.game.step_frame()

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
        entity = self._require_entity(name)
        components_data: Dict[str, Any] = {}
        for comp_type, component in entity._components.items():
            if hasattr(component, "to_dict"):
                components_data[comp_type.__name__] = component.to_dict()
        return {
            "name": entity.name,
            "active": entity.active,
            "tag": entity.tag,
            "layer": entity.layer,
            "components": components_data,
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
        return self._ok("Feature metadata updated", {"key": key})

    def get_feature_metadata(self) -> Dict[str, Any]:
        """Devuelve la metadata extendida de la escena."""
        if self.scene_manager is None or self.scene_manager.current_scene is None:
            return {}
        return self.scene_manager.current_scene.feature_metadata

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

    def open_project(self, path: str) -> ActionResult:
        if self.project_service is None or self.game is None:
            return self._fail("Project service not ready")
        success = self.game.open_project(path)
        if not success:
            return self._fail("Open project failed")
        return self._ok("Project opened", {"path": self.project_service.project_root.as_posix()})

    def list_project_assets(self, search: str = "") -> list[Dict[str, Any]]:
        if self.asset_service is None:
            return []
        return self.asset_service.list_assets(search=search)

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

    def create_animator_state(
        self,
        entity_name: str,
        state_name: str,
        slice_names: Optional[list[str]] = None,
        fps: float = 8.0,
        loop: bool = True,
        on_complete: Optional[str] = None,
    ) -> ActionResult:
        entity = self._require_entity(entity_name)
        from engine.components.animator import Animator

        animator = entity.get_component(Animator)
        if animator is None:
            return self._fail("Animator not found")
        animations = animator.to_dict()["animations"]
        animations[state_name] = {
            "frames": animator.animations.get(state_name).frames if state_name in animator.animations else [0],
            "slice_names": slice_names or [],
            "fps": fps,
            "loop": loop,
            "on_complete": on_complete,
        }
        return self.edit_component(entity_name, "Animator", "animations", animations)

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

    def _ensure_edit_mode(self) -> None:
        if self.game is not None and not self.game.is_edit_mode:
            raise InvalidOperationError("Cannot edit in PLAY mode")

    def _ok(self, message: str, data: Any = None) -> ActionResult:
        return {"success": True, "message": message, "data": data}

    def _fail(self, message: str) -> ActionResult:
        return {"success": False, "message": message, "data": None}
