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
import os

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
    from engine.systems.selection_system import SelectionSystem
    from cli.script_executor import ScriptExecutor

from engine.debug.timeline import Timeline
from engine.editor.hierarchy_panel import HierarchyPanel
from engine.editor.gizmo_system import GizmoSystem
from engine.editor.editor_layout import EditorLayout
from engine.editor.raygui_theme import apply_unity_dark_theme


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
        self._event_bus: Optional["EventBus"] = None
        self._rule_system: Optional["RuleSystem"] = None
        self._selection_system: Optional["SelectionSystem"] = None
        
        self.script_executor: Optional["ScriptExecutor"] = None
        
        # Debug / Timeline
        self.timeline: "Timeline" = Timeline(capacity=1000)
        
        # Editor Panels
        self.hierarchy_panel: Optional["HierarchyPanel"] = HierarchyPanel()
        self.gizmo_system: Optional["GizmoSystem"] = GizmoSystem()
        self.editor_layout: Optional["EditorLayout"] = None
        
        # Gestión de escenas
             
        # Gestión de escenas
        # Gestión de escenas
        self._scene_manager: Optional["SceneManager"] = None
        
        # Estado de Persistencia
        self.current_scene_path: str = "levels/demo_level.json" # Default por ahora
    
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
        # Conectar scene_manager si ya existe
        if self._scene_manager is not None:
            self._inspector_system.set_scene_manager(self._scene_manager)
    
    def set_level_loader(self, loader: "LevelLoader") -> None:
        self._level_loader = loader
    
    def set_event_bus(self, event_bus: "EventBus") -> None:
        self._event_bus = event_bus
    
    def set_rule_system(self, rule_system: "RuleSystem") -> None:
        self._rule_system = rule_system
    
    def set_scene_manager(self, manager: "SceneManager") -> None:
        self._scene_manager = manager
        # Conectar inspector al scene_manager para edición
        if self._inspector_system is not None:
            self._inspector_system.set_scene_manager(manager)
            
    def set_selection_system(self, system: "SelectionSystem") -> None:
        self._selection_system = system
        
    def set_script_executor(self, executor: "ScriptExecutor") -> None:
        """Asigna un ejecutor de scripts para automatización visual."""
        self.script_executor = executor
    
    # === GAME LOOP ===
    
    def run(self) -> None:
        """Inicia el game loop."""
        rl.init_window(self.width, self.height, self.title)
        rl.set_target_fps(self.target_fps)
        
        # Aplicar tema Raygui
        apply_unity_dark_theme()
        
        self.running = True
        print(f"[INFO] Motor iniciado en modo: {self._state}")
        
        while self.running and not rl.window_should_close():
            self.time.update()
            dt = self.time.delta_time
            
            # World activo
            active_world = self.world
            
            self._process_input()
            
            # Script Update (Visual Automation)
            if self.script_executor:
                running = self.script_executor.update()
                if not running:
                    print("[INFO] Script finalizado.")
                    # Opcional: Cerrar juego al terminar script
                    # self.running = False
            
            # Sistemas de edición
            if self._state.is_edit():
                # Calcular Mouse World Pos (corrección de coordenadas)
                ignore_mouse = False
                mouse_world = rl.Vector2(rl.get_mouse_x(), rl.get_mouse_y())
                mouse_in_scene = True
                
                if self.editor_layout:
                    mouse_world = self.editor_layout.get_scene_mouse_pos()
                    mouse_in_scene = self.editor_layout.is_mouse_in_scene_view()
                    # Si el mouse no está en la escena y no estamos arrastrando, ignorar
                    # Pero si estamos arrastrando un Gizmo, necesitamos seguir recibiendo updates (drag fuera de view)
                    if not mouse_in_scene and not (self.gizmo_system and self.gizmo_system.is_dragging):
                        ignore_mouse = True

                # Gizmos (input capture priority)
                if self.gizmo_system is not None and active_world is not None:
                    # Gizmo necesita update si está arrastrando O si el mouse está en escena
                    if self.gizmo_system.is_dragging or mouse_in_scene:
                         self.gizmo_system.update(active_world, mouse_world)
                    
                if self._selection_system is not None and active_world is not None:
                    # Solo seleccionar si click en escena y gizmo no consumió el click
                    # Comprobación de Gizmo is_dragging insuficiente porque el click inicial puede ser en gizmo
                    # Gizmo debería devolver si consumió input. Por ahora check is_dragging/active_mode
                    gizmo_active = False
                    if self.gizmo_system:
                         # Si hover mode != NONE, el gizmo va a consumir el click
                         if self.gizmo_system.hover_mode.value != 1: # 1 = NONE
                             gizmo_active = True
                             
                    if mouse_in_scene and not gizmo_active and not (self.gizmo_system and self.gizmo_system.is_dragging):
                        self._selection_system.update(active_world, mouse_world)
            
            if self._inspector_system is not None:
                # Ahora inspector.update necesita el world para coordinar la selección
                self._inspector_system.update(
                    dt, 
                    world=active_world, 
                    is_edit_mode=self.is_edit_mode
                )
            
            self._update_animation(active_world, dt)
            
            self._update_animation(active_world, dt)
            
            # Actualización de gameplay (Física, Colisiones, Reglas)
            if self._state.allows_physics() or self._state.allows_gameplay():
                self._update_gameplay(active_world, dt)
            
            # Si estábamos en STEPPING, volvemos a PAUSED después de un frame
            if self._state == EngineState.STEPPING:
                self._state = EngineState.PAUSED
            
            # Renderizar
            
            # Renderizar
            # Wrapper de input del layout
            if self.editor_layout:
                 if rl.is_window_resized():
                     self.editor_layout.update_layout(rl.get_screen_width(), rl.get_screen_height())
                     self.width = rl.get_screen_width()
                     self.height = rl.get_screen_height()
                     
                 self.editor_layout.update_input()
                 
                 # Procesar requests de UI
                 if self.editor_layout.request_play:
                     self.editor_layout.request_play = False
                     if self._state == EngineState.EDIT:
                         self.play()
                         self.editor_layout.active_tab = "GAME"
                     else:
                         self.stop()
                         self.editor_layout.active_tab = "SCENE"
                 
                 # --- DRAG & DROP LOGIC ---
                 if self._state.is_edit() and self.editor_layout.project_panel and self.editor_layout.project_panel.dragging_file:
                     if rl.is_mouse_button_released(rl.MOUSE_BUTTON_LEFT):
                         # Soltó el archivo. ¿Dónde?
                         if self.editor_layout.is_mouse_in_scene_view() and active_world is not None:
                             file_path = self.editor_layout.project_panel.dragging_file
                             drop_pos = self.editor_layout.get_scene_mouse_pos()
                             
                             # Crear entidad
                             filename = os.path.basename(file_path)
                             name = os.path.splitext(filename)[0]
                             
                             # Evitar duplicados simples
                             base_name = name
                             count = 1
                             while active_world.get_entity_by_name(name):
                                 name = f"{base_name}_{count}"
                                 count += 1
                                 
                             print(f"[DROP] Creando entidad '{name}' desde {file_path}")
                             
                             new_ent = active_world.create_entity(name)
                             
                             # Components
                             from engine.components.transform import Transform
                             from engine.components.sprite import Sprite
                             from engine.components.collider import Collider
                             
                             new_ent.add_component(Transform(drop_pos.x, drop_pos.y))
                             new_ent.add_component(Sprite(file_path)) # Sprite carga la textura
                             # Idealmente el sprite setea width/height, collider usa defaults
                             new_ent.add_component(Collider(32, 32)) # Default size
                             
                             active_world.selected_entity_name = name

            # Renderizar
            rl.begin_drawing()
            rl.clear_background(rl.DARKGRAY)
            
            # --- SCENE VIEW RENDER ---
            if self.is_edit_mode and self.editor_layout and self.editor_layout.active_tab == "SCENE":
                self.editor_layout.begin_scene_render()
                
                # Render World (Editor)
                if self._render_system is not None and active_world is not None:
                     self._render_system.render(active_world, override_camera=self.editor_layout.editor_camera)

                # Render Gizmos
                if self.gizmo_system is not None and active_world is not None:
                    self.gizmo_system.render(active_world)
                    
                self.editor_layout.end_scene_render()
            
            # --- GAME VIEW RENDER ---
            if self.editor_layout and self.editor_layout.active_tab == "GAME":
                # Si estamos en PLAY, usamos el world activo (runtime)
                # Si estamos en EDIT, podríamos mostrar una preview o pantalla negra
                target_world = self.world if self.is_play_mode or self.is_paused else None
                
                self.editor_layout.begin_game_render()
                if target_world and self._render_system:
                    # Render normal del juego (sin cámara de editor)
                    self._render_system.render(target_world)
                else:
                    # Mensaje "Press Play"
                    rl.draw_text("Press PLAY to start", 10, 10, 20, rl.GRAY)
                    
                self.editor_layout.end_game_render()
            
            # --- MAIN SCREEN RENDER ---
            
            if self.editor_layout:
                # Dibujar todo el layout
                is_playing = (self._state == EngineState.PLAY or self._state == EngineState.PAUSED)
                self.editor_layout.draw_layout(is_playing)
            else:
                 # Fallback modo sin layout
                 if self._render_system is not None and active_world is not None:
                    self._render_system.render(active_world)

            self._draw_debug_info()
            
            # UI Panels (Overlays)
            # Solo mostrar paneles UI si estamos en modo Editor (o si queremos ver debug en juego)
            # Unity muestra Hierarchy en Play Mode, así que lo dejamos.
            if self.hierarchy_panel is not None and active_world is not None:
                if self.editor_layout:
                    rect = self.editor_layout.hierarchy_rect
                    self.hierarchy_panel.render(
                        active_world, 
                        int(rect.x), int(rect.y), 
                        int(rect.width), int(rect.height)
                    )
                else:
                    self.hierarchy_panel.render(active_world, 0, 0, 200, self.height)
            
            if self._inspector_system is not None and active_world is not None:
                if self.editor_layout:
                    rect = self.editor_layout.inspector_rect
                    self._inspector_system.render(
                        active_world, 
                        int(rect.x), int(rect.y), 
                        int(rect.width), int(rect.height),
                        is_edit_mode=self.is_edit_mode
                    )
                else:
                    self._inspector_system.render(
                        active_world, 
                        self.width - 300, 0, 300, self.height,
                        is_edit_mode=self.is_edit_mode
                    )
            
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
        # P -> Pause Toggle (Solo si ya estamos jugando)
        if rl.is_key_pressed(rl.KEY_P):
            if self._state == EngineState.PLAY:
                self.pause()
            elif self._state == EngineState.PAUSED:
                self.pause() # Resume
        
        # ESC -> Stop (Solo si estamos jugando)
        if rl.is_key_pressed(rl.KEY_ESCAPE):
            if self._state in (EngineState.PLAY, EngineState.PAUSED, EngineState.STEPPING):
                self.stop()
                if self.editor_layout:
                    self.editor_layout.active_tab = "SCENE"
                
        # Controles de Debug (solo en PAUSE/PLAY)
        if self._state in (EngineState.PAUSED, EngineState.PLAY):
            # F10: Step
            if rl.is_key_pressed(rl.KEY_F10):
                self.step()
            
            # F5: Quick Save Snapshot
            if rl.is_key_pressed(rl.KEY_F5):
                self.save_snapshot()
            
            # F6: Quick Load Last Snapshot
            if rl.is_key_pressed(rl.KEY_F6):
                self.load_last_snapshot()
        
        if rl.is_key_pressed(rl.KEY_R):
            self._reload_scene()

        # F11: Fullscreen
        if rl.is_key_pressed(rl.KEY_F11):
            # Toggle Fullscreen
            # Nota: En Raylib a veces es mejor usar ToggleBorderlessWindowed para evitar cambios de resolución
            current = rl.is_window_fullscreen()
            if not current:
                # Maximizar antes de fullscreen ayuda en algunos OS
                display = rl.get_current_monitor()
                rl.set_window_size(rl.get_monitor_width(display), rl.get_monitor_height(display))
                rl.toggle_fullscreen()
            else:
                rl.toggle_fullscreen()
                rl.set_window_size(self.width, self.height) # Restaurar (aunque deberíamos guardar el tamaño previo)
    
        # Ctrl+S: Save
        if rl.is_key_down(rl.KEY_LEFT_CONTROL) and rl.is_key_pressed(rl.KEY_S):
            self.save_current_scene()
            
    def save_current_scene(self) -> None:
        """Guarda la escena actual a disco."""
        if self._scene_manager is None:
            print("[ERROR] No hay SceneManager activo, no se puede guardar.")
            return
            
        print(f"[INFO] Guardando escena en: {self.current_scene_path}")
        success = self._scene_manager.save_scene_to_file(self.current_scene_path)
        if success:
             # Feedback visual simple (Flash o log)
             print("[INFO] Guardado completado.")
        else:
             print("[ERROR] Fallo al guardar.")
    
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

    def _update_gameplay(self, world: "World", dt: float) -> None:
        """Actualiza la lógica del juego (Física, Colisiones, Reglas)."""
        if self._physics_system is not None and self._state.allows_physics():
            self._physics_system.update(world, dt)
            
        if self._collision_system is not None and self._state.allows_gameplay():
            self._collision_system.update(world)
            
    def step(self) -> None:
        """Avanza exactamente un frame de simulación."""
        if self._state == EngineState.EDIT:
            return
            
        # Si estamos en PLAY, pausamos primero
        if self._state == EngineState.PLAY:
            self.pause()
            
        # Cambiamos a STEPPING para permitir un update
        print("[DEBUG] Step frame")
        self._state = EngineState.STEPPING
        
    def save_snapshot(self) -> None:
        """Guarda un snapshot del estado actual."""
        if self.world is None:
            return
        
        self.timeline.add_snapshot(self.world, self.time.frame_count, self.time.time)
        print(f"[DEBUG] Snapshot saved. Total: {self.timeline.count()}")
        
    def load_last_snapshot(self) -> None:
        """Carga el último snapshot guardado."""
        snapshot = self.timeline.get_latest_snapshot()
        if snapshot is None:
            print("[DEBUG] No snapshots available")
            return
            
        # Restaurar estado
        if self._scene_manager is not None:
            # Reemplazar el mundo activo en scene_manager
            self._scene_manager.restore_world(snapshot.restore())
            # Actualizar referencia local
            self._world = self._scene_manager.active_world
            
            # Reconfigurar sistemas
            if self._rule_system is not None and self._world is not None:
                self._rule_system.set_world(self._world)
                
            print(f"[DEBUG] Snapshot loaded. Frame: {snapshot.frame}")
    
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
