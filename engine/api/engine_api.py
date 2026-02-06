"""
engine/api/engine_api.py - Fachada principal del motor

PROPÓSITO:
    Punto de entrada único para control programático del motor.
    Abstrae la complejidad interna (Game, SceneManager, Systems).
"""

from typing import Optional, List, Any, Dict
import json

from cli.headless_game import HeadlessGame
from cli.runner import CLIRunner
from engine.core.engine_state import EngineState
from engine.scenes.scene_manager import SceneManager
from engine.levels.component_registry import create_default_registry
from engine.events.event_bus import EventBus
from engine.events.rule_system import RuleSystem
from engine.systems.physics_system import PhysicsSystem
from engine.systems.collision_system import CollisionSystem
from engine.systems.animation_system import AnimationSystem
from engine.inspector.inspector_system import InspectorSystem
from engine.systems.selection_system import SelectionSystem

from engine.api.types import EngineStatus, EntityData, ActionResult
from engine.api.errors import (
    EntityNotFoundError, 
    ComponentNotFoundError, 
    InvalidOperationError,
    LevelLoadError
)

class EngineAPI:
    """
    API pública para controlar el motor de videojuegos.
    """
    
    def __init__(self) -> None:
        self.game: Optional[HeadlessGame] = None
        self.scene_manager: Optional[SceneManager] = None
        self._initialize_engine()
        
    def _initialize_engine(self) -> None:
        """Configura el motor en modo headless."""
        self.game = HeadlessGame()
        registry = create_default_registry()
        self.scene_manager = SceneManager(registry)
        
        # Configurar sistemas
        event_bus = EventBus() # type: ignore
        # Inicializar sistemas
        systems = [
            PhysicsSystem(gravity=600),
            CollisionSystem(event_bus),
            AnimationSystem(event_bus),
            InspectorSystem(),
            SelectionSystem()
        ]
        
        self.game.set_scene_manager(self.scene_manager)
        self.game.set_physics_system(systems[0])
        self.game.set_collision_system(systems[1])
        self.game.set_animation_system(systems[2])
        self.game.set_inspector_system(systems[3])
        self.game.set_selection_system(systems[4])
        self.game.set_event_bus(event_bus)
        
    # === CONTROL DE EJECUCIÓN ===
        
    def load_level(self, path: str) -> None:
        """Carga un nivel desde archivo JSON."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if self.scene_manager:
                world = self.scene_manager.load_scene(data)
                if self.game:
                    self.game.set_world(world)
        except Exception as e:
            raise LevelLoadError(f"Fallo al cargar {path}: {e}")

    def step(self, frames: int = 1) -> None:
        """Avanza la simulación N frames."""
        if not self.game:
            return
        
        for _ in range(frames):
            self.game.step_frame()
            
    def play(self) -> None:
        """Cambia a modo PLAY."""
        if self.game:
            self.game.play()
            
    def stop(self) -> None:
        """Detiene la simulación (vuelve a EDIT)."""
        if self.game:
            self.game.stop()
            
    def get_status(self) -> EngineStatus:
        """Obtiene información del estado actual."""
        if not self.game:
            raise RuntimeError("Engine not initialized")
            
        world = self.game.world
        count = world.entity_count() if world else 0
        
        return {
            "state": str(self.game.state),
            "frame": 0, # TODO: Expose frame count in TimeManager
            "time": self.game.time.total_time,
            "fps": self.game.time.fps,
            "entity_count": count
        }

    # === INSPECCIÓN Y EDICIÓN ===

    def get_entity(self, name: str) -> EntityData:
        """Obtiene datos de una entidad."""
        if not self.game or not self.game.world:
            raise RuntimeError("No world loaded")
            
        entity = self.game.world.get_entity_by_name(name)
        if not entity:
            raise EntityNotFoundError(f"Entity '{name}' not found")
            
        # Serializar componentes
        components_data = {}
        for comp_type, comp in entity._components.items():
            if hasattr(comp, "to_dict"):
                components_data[comp_type.__name__] = comp.to_dict()
                
        return {
            "name": entity.name,
            "components": components_data
        }

    def edit_component(self, entity_name: str, component: str, property: str, value: Any) -> ActionResult:
        """
        Modifica una propiedad de un componente (Solo en EDIT).
        """
        if not self.scene_manager:
            return {"success": False, "message": "SceneManager not ready", "data": None}
            
        if self.game and self.game.is_play_mode:
             raise InvalidOperationError("Cannot edit in PLAY mode")
             
        success = self.scene_manager.apply_edit_to_world(entity_name, component, property, value)
        if success:
            return {"success": True, "message": "Edit applied", "data": None}
        else:
            return {"success": False, "message": "Edit failed (check names/property)", "data": None}
    
    def shutdown(self) -> None:
        """Libera recursos."""
        if self.game:
            self.game.headless_running = False
