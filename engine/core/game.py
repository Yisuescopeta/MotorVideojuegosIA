"""
engine/core/game.py - Clase principal del juego con gestión de escenas

PROPÓSITO:
    Gestiona ventana, game loop, sistemas, estados y escenas.

ESTADOS:
    - EDIT: Modo edición (usa World desde Scene)
    - PLAY: Modo juego (usa RuntimeWorld - copia)
    - PAUSED: Modo pausado

CONTROLES:
    - ESPACIO: Play (EDIT → PLAY, crea RuntimeWorld)
    - P: Pause/Resume
    - ESC: Stop (→ EDIT, restaura World)
    - R: Recargar escena
    - TAB: Inspector
"""

from typing import TYPE_CHECKING, Optional
import pyray as rl

from engine.core.time_manager import TimeManager
from engine.core.engine_state import EngineState

if TYPE_CHECKING:
    from engine.ecs.world import World
    from engine.systems.render_system import RenderSystem
    from engine.systems.physics_system import PhysicsSystem
    from engine.systems.collision_system import CollisionSystem
    from engine.systems.animation_system import AnimationSystem
    from engine.inspector.inspector_system import InspectorSystem
    from engine.levels.level_loader import LevelLoader
    from engine.events.event_bus import EventBus
    from engine.events.rule_system import RuleSystem
    from engine.scenes.scene_manager import SceneManager


class Game:
    """Clase principal del motor con gestión de estados y escenas."""
    
    EDIT_ANIMATION_SPEED: float = 0.25
    
    def __init__(
        self,
        title: str = "Motor 2D",
        width: int = 800,
        height: int = 600,
        target_fps: int = 60
    ) -> None:
        self.title = title
        self.width = width
        self.height = height
        self.target_fps = target_fps
        
        self.running: bool = False
        self.time: TimeManager = TimeManager()
        
        # Estado del motor
        self._state: EngineState = EngineState.EDIT
        
        # World activo (cambia según estado)
        self._world: Optional["World"] = None
        
        # Sistemas
        self._render_system: Optional["RenderSystem"] = None
        self._physics_system: Optional["PhysicsSystem"] = None
        self._collision_system: Optional["CollisionSystem"] = None
        self._animation_system: Optional["AnimationSystem"] = None
        self._inspector_system: Optional["InspectorSystem"] = None
        self._level_loader: Optional["LevelLoader"] = None
        self._event_bus: Optional["EventBus"] = None
        self._rule_system: Optional["RuleSystem"] = None
        
        # Gestión de escenas
        self._scene_manager: Optional["SceneManager"] = None
    
    # === PROPIEDADES ===
    
    @property
    def state(self) -> EngineState:
        return self._state
    
    @property
    def is_edit_mode(self) -> bool:
        return self._state.is_edit()
    
    @property
    def is_play_mode(self) -> bool:
        return self._state.is_play()
    
    @property
    def is_paused(self) -> bool:
        return self._state.is_paused()
    
    @property
    def world(self) -> Optional["World"]:
        """World activo según el estado."""
        if self._scene_manager is not None:
            return self._scene_manager.active_world
        return self._world
    
    # === MÉTODOS DE CONTROL DE ESTADO ===
    
    def play(self) -> None:
        """Inicia el juego (EDIT → PLAY)."""
        if self._state != EngineState.EDIT:
            return
        
        print("[INFO] Estado: EDIT → PLAY")
        
        # Crear RuntimeWorld desde Scene
        if self._scene_manager is not None:
            runtime_world = self._scene_manager.enter_play()
            if runtime_world is not None:
                self._world = runtime_world
                
                # Reconfigurar RuleSystem con nuevo World
                if self._rule_system is not None:
                    self._rule_system.set_world(runtime_world)
                    # Recargar reglas desde Scene
                    scene = self._scene_manager.current_scene
                    if scene is not None:
                        self._rule_system.load_rules(scene.rules_data)
        
        self._state = EngineState.PLAY
        
        if self._event_bus is not None:
            self._event_bus.emit("on_play", {})
    
    def pause(self) -> None:
        """Pausa/Resume el juego (PLAY ↔ PAUSED)."""
        if self._state == EngineState.PLAY:
            print("[INFO] Estado: PLAY → PAUSED")
            self._state = EngineState.PAUSED
        elif self._state == EngineState.PAUSED:
            print("[INFO] Estado: PAUSED → PLAY")
            self._state = EngineState.PLAY
    
    def stop(self) -> None:
        """Detiene el juego y vuelve a edición."""
        if self._state not in (EngineState.PLAY, EngineState.PAUSED):
            return
        
        print("[INFO] Estado: → EDIT (restaurando escena)")
        
        # Limpiar reglas y eventos
        if self._rule_system is not None:
            self._rule_system.clear_rules()
        if self._event_bus is not None:
            self._event_bus.clear_history()
        
        # Restaurar World desde Scene
        if self._scene_manager is not None:
            edit_world = self._scene_manager.exit_play()
            if edit_world is not None:
                self._world = edit_world
        
        self._state = EngineState.EDIT
    
    # === SETTERS ===
    
    def set_world(self, world: "World") -> None:
        self._world = world
    
    def set_render_system(self, system: "RenderSystem") -> None:
        self._render_system = system
    
    def set_physics_system(self, system: "PhysicsSystem") -> None:
        self._physics_system = system
    
    def set_collision_system(self, system: "CollisionSystem") -> None:
        self._collision_system = system
    
    def set_animation_system(self, system: "AnimationSystem") -> None:
        self._animation_system = system
    
    def set_inspector_system(self, system: "InspectorSystem") -> None:
        self._inspector_system = system
    
    def set_level_loader(self, loader: "LevelLoader") -> None:
        self._level_loader = loader
    
    def set_event_bus(self, event_bus: "EventBus") -> None:
        self._event_bus = event_bus
    
    def set_rule_system(self, rule_system: "RuleSystem") -> None:
        self._rule_system = rule_system
    
    def set_scene_manager(self, manager: "SceneManager") -> None:
        self._scene_manager = manager
    
    # === GAME LOOP ===
    
    def run(self) -> None:
        """Inicia el game loop."""
        rl.init_window(self.width, self.height, self.title)
        rl.set_target_fps(self.target_fps)
        
        self.running = True
        print(f"[INFO] Motor iniciado en modo: {self._state}")
        
        while self.running and not rl.window_should_close():
            self.time.update()
            dt = self.time.delta_time
            
            # World activo
            active_world = self.world
            
            self._process_input()
            
            if self._inspector_system is not None:
                self._inspector_system.update(dt)
            
            self._update_animation(active_world, dt)
            
            if self._state.allows_physics():
                if self._physics_system is not None and active_world is not None:
                    self._physics_system.update(active_world, dt)
            
            if self._state.allows_gameplay():
                if self._collision_system is not None and active_world is not None:
                    self._collision_system.update(active_world)
            
            # Renderizar
            rl.begin_drawing()
            rl.clear_background(rl.DARKGRAY)
            
            if self._render_system is not None and active_world is not None:
                self._render_system.render(active_world)
            
            self._draw_debug_info()
            
            if self._inspector_system is not None and active_world is not None:
                self._inspector_system.render(active_world, self.width, self.height)
            
            rl.end_drawing()
        
        self._cleanup()
    
    def _update_animation(self, world: Optional["World"], dt: float) -> None:
        if self._animation_system is None or world is None:
            return
        
        if self._state.allows_animation():
            self._animation_system.update(world, dt)
        elif self._state.allows_animation_preview():
            self._animation_system.update(world, dt * self.EDIT_ANIMATION_SPEED)
    
    def _process_input(self) -> None:
        if rl.is_key_pressed(rl.KEY_SPACE):
            if self._state == EngineState.EDIT:
                self.play()
        
        if rl.is_key_pressed(rl.KEY_P):
            if self._state in (EngineState.PLAY, EngineState.PAUSED):
                self.pause()
        
        if rl.is_key_pressed(rl.KEY_ESCAPE):
            if self._state in (EngineState.PLAY, EngineState.PAUSED):
                self.stop()
        
        if rl.is_key_pressed(rl.KEY_R):
            self._reload_scene()
    
    def _reload_scene(self) -> None:
        """Recarga la escena actual."""
        print("[INFO] Recargando escena...")
        
        if self._rule_system is not None:
            self._rule_system.clear_rules()
        if self._event_bus is not None:
            self._event_bus.clear_history()
        
        if self._scene_manager is not None:
            self._world = self._scene_manager.reload_scene()
        elif self._level_loader is not None and self._world is not None:
            self._level_loader.reload(self._world)
    
    def _draw_debug_info(self) -> None:
        # Estado
        state_color = {
            EngineState.EDIT: rl.SKYBLUE,
            EngineState.PLAY: rl.GREEN,
            EngineState.PAUSED: rl.ORANGE
        }
        rl.draw_text(
            f"[{self._state}]",
            self.width // 2 - 40, 10, 20,
            state_color.get(self._state, rl.WHITE)
        )
        
        rl.draw_text(f"FPS: {self.time.fps}", 10, 10, 20, rl.GREEN)
        
        active_world = self.world
        if active_world is not None:
            rl.draw_text(f"Entities: {active_world.entity_count()}", 10, 35, 16, rl.LIGHTGRAY)
        
        if self._collision_system is not None and self._state == EngineState.PLAY:
            collisions = len(self._collision_system.get_collisions())
            color = rl.YELLOW if collisions > 0 else rl.LIGHTGRAY
            rl.draw_text(f"Collisions: {collisions}", 10, 55, 16, color)
        
        if self._scene_manager is not None:
            rl.draw_text(f"Scene: {self._scene_manager.scene_name}", 10, 75, 14, rl.SKYBLUE)
        elif self._level_loader is not None:
            rl.draw_text(f"Level: {self._level_loader.current_level_name}", 10, 75, 14, rl.SKYBLUE)
        
        if self._rule_system is not None and self._state == EngineState.PLAY:
            rl.draw_text(
                f"Rules: {self._rule_system.rules_count} | Exec: {self._rule_system.rules_executed_count}",
                10, 95, 12, rl.ORANGE
            )
        
        y = self.height - 45
        rl.draw_text("[SPACE] Play  [P] Pause  [ESC] Stop  [R] Reload", 10, y, 12, rl.GRAY)
    
    def _cleanup(self) -> None:
        self.running = False
        if self._render_system is not None:
            self._render_system.cleanup()
        rl.close_window()
