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
from engine.core.hot_reload import HotReloadManager
from engine.editor.undo_redo import UndoRedoManager
from engine.project.project_service import ProjectService
from engine.config import EDIT_ANIMATION_SPEED, TIMELINE_CAPACITY, SCRIPTS_DIRECTORY, AUTOSAVE_INTERVAL
from engine.editor.console_panel import log_info, log_err

if TYPE_CHECKING:
    from engine.ecs.world import World
    from engine.components.camera2d import Camera2D
    from engine.systems.render_system import RenderSystem
    from engine.systems.physics_system import PhysicsSystem
    from engine.systems.collision_system import CollisionSystem
    from engine.systems.animation_system import AnimationSystem
    from engine.systems.audio_system import AudioSystem
    from engine.systems.input_system import InputSystem
    from engine.systems.player_controller_system import PlayerControllerSystem
    from engine.systems.script_behaviour_system import ScriptBehaviourSystem
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
    
    EDIT_ANIMATION_SPEED: float = EDIT_ANIMATION_SPEED
    
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
        self._audio_system: Optional["AudioSystem"] = None
        self._input_system: Optional["InputSystem"] = None
        self._player_controller_system: Optional["PlayerControllerSystem"] = None
        self._script_behaviour_system: Optional["ScriptBehaviourSystem"] = None
        self._inspector_system: Optional["InspectorSystem"] = None
        self._level_loader: Optional["LevelLoader"] = None
        self._event_bus: Optional["EventBus"] = None
        self._event_bus: Optional["EventBus"] = None
        self._rule_system: Optional["RuleSystem"] = None
        self._selection_system: Optional["SelectionSystem"] = None
        
        self.script_executor: Optional["ScriptExecutor"] = None
        
        # Debug / Timeline
        self.timeline: "Timeline" = Timeline(capacity=TIMELINE_CAPACITY)
        
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
        
        # Hot-Reload
        self.hot_reload_manager: HotReloadManager = HotReloadManager(SCRIPTS_DIRECTORY)
        self.hot_reload_manager.scan_directory()

        self._project_service: Optional[ProjectService] = None
        self._history_manager: UndoRedoManager = UndoRedoManager()
        
        self.autosave_timer: float = 0.0
    
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

    @property
    def audio_system(self) -> Optional["AudioSystem"]:
        return self._audio_system
    
    # === MÉTODOS DE CONTROL DE ESTADO ===
    
    def play(self) -> None:
        """Inicia el juego (EDIT -> PLAY)."""
        if self._state != EngineState.EDIT:
            return
        
        print("[INFO] Estado: EDIT -> PLAY")
        
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
                if self._script_behaviour_system is not None:
                    self._script_behaviour_system.on_play(runtime_world)
        
        self._state = EngineState.PLAY
        
        if self._event_bus is not None:
            self._event_bus.emit("on_play", {})
    
    def pause(self) -> None:
        """Pausa/Resume el juego (PLAY <-> PAUSED)."""
        if self._state == EngineState.PLAY:
            print("[INFO] Estado: PLAY -> PAUSED")
            self._state = EngineState.PAUSED
        elif self._state == EngineState.PAUSED:
            print("[INFO] Estado: PAUSED -> PLAY")
            self._state = EngineState.PLAY
    
    def stop(self) -> None:
        """Detiene el juego y vuelve a edición."""
        if self._state not in (EngineState.PLAY, EngineState.PAUSED):
            return
        
        print("[INFO] Estado: -> EDIT (restaurando escena)")
        
        # Limpiar reglas y eventos
        if self._rule_system is not None:
            self._rule_system.clear_rules()
        if self._event_bus is not None:
            self._event_bus.clear_history()
        if self._script_behaviour_system is not None and self.world is not None:
            self._script_behaviour_system.on_stop(self.world)
        
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
        if self._project_service is not None:
            self._render_system.set_project_service(self._project_service)
    
    def set_physics_system(self, system: "PhysicsSystem") -> None:
        self._physics_system = system
    
    def set_collision_system(self, system: "CollisionSystem") -> None:
        self._collision_system = system
    
    def set_animation_system(self, system: "AnimationSystem") -> None:
        self._animation_system = system

    def set_audio_system(self, system: "AudioSystem") -> None:
        self._audio_system = system

    def set_input_system(self, system: "InputSystem") -> None:
        self._input_system = system

    def set_player_controller_system(self, system: "PlayerControllerSystem") -> None:
        self._player_controller_system = system

    def set_script_behaviour_system(self, system: "ScriptBehaviourSystem") -> None:
        self._script_behaviour_system = system
        self._script_behaviour_system.set_hot_reload_manager(self.hot_reload_manager)
        if self._scene_manager is not None:
            self._script_behaviour_system.set_scene_manager(self._scene_manager)
    
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
        self._scene_manager.set_history_manager(self._history_manager)
        # Conectar inspector al scene_manager para edición
        if self._inspector_system is not None:
            self._inspector_system.set_scene_manager(manager)
        if self._script_behaviour_system is not None:
            self._script_behaviour_system.set_scene_manager(manager)
        if self.hierarchy_panel is not None:
            self.hierarchy_panel.set_scene_manager(manager)
            
    def set_selection_system(self, system: "SelectionSystem") -> None:
        self._selection_system = system
        
    def set_script_executor(self, executor: "ScriptExecutor") -> None:
        """Asigna un ejecutor de scripts para automatización visual."""
        self.script_executor = executor

    def set_project_service(self, service: ProjectService) -> None:
        self._project_service = service
        if self._render_system is not None:
            self._render_system.set_project_service(service)
        self.hot_reload_manager.scripts_dir = service.get_project_path("scripts").as_posix()
        self.hot_reload_manager.scan_directory()
        if self._script_behaviour_system is not None:
            self._script_behaviour_system.set_hot_reload_manager(self.hot_reload_manager)
        if self.editor_layout is not None and self.editor_layout.project_panel is not None:
            self.editor_layout.project_panel.set_project_service(service)
            self.editor_layout.set_recent_projects(service.list_recent_projects())
        last_scene = service.get_last_scene()
        if last_scene:
            self.current_scene_path = service.resolve_path(last_scene).as_posix()

    def open_project(self, path: str) -> bool:
        if self._project_service is None or self._scene_manager is None:
            return False
        try:
            manifest = self._project_service.open_project(path)
        except Exception as exc:
            log_err(f"Open Project failed: {exc}")
            return False

        self._history_manager.clear()
        self.set_project_service(self._project_service)
        levels_root = self._project_service.get_project_path("levels")
        last_scene = self._project_service.get_last_scene()
        scene_path = self._project_service.resolve_path(last_scene).as_posix() if last_scene else ""
        if not scene_path or not os.path.exists(scene_path):
            candidates = sorted(levels_root.glob("*.json"))
            scene_path = candidates[0].as_posix() if candidates else ""

        self.stop()
        if scene_path:
            world = self._scene_manager.load_scene_from_file(scene_path)
            if world is not None:
                self._world = world
                self.current_scene_path = scene_path
                self._project_service.set_last_scene(scene_path)
        else:
            self._world = self._scene_manager.create_new_scene(manifest.name)
            self.current_scene_path = ""

        if self.editor_layout is not None:
            self.editor_layout.project_panel.set_project_service(self._project_service)
            self.editor_layout.set_recent_projects(self._project_service.list_recent_projects())
        log_info(f"Proyecto activo: {manifest.name}")
        return True
    
    # === GAME LOOP ===
    
    def run(self) -> None:
        "Inicia el game loop."
        rl.init_window(self.width, self.height, self.title)
        rl.set_target_fps(self.target_fps)
        
        # Aplicar tema Raygui
        apply_unity_dark_theme()
        
        # Crear EditorLayout (necesita ventana Raylib inicializada)
        if self.editor_layout is None:
            self.editor_layout = EditorLayout(self.width, self.height)
            if self._project_service is not None:
                self.editor_layout.project_panel.set_project_service(self._project_service)
                self.editor_layout.set_recent_projects(self._project_service.list_recent_projects())
        
        self.running = True
        print(f"[INFO] Motor iniciado en modo: {self._state}")
        
        while self.running and not rl.window_should_close():
            self.time.update()
            dt = self.time.delta_time
            
            # World activo
            active_world = self.world
            
            self._process_input()
            
            # --- AUTO-SAVE ---
            if self._state == EngineState.EDIT and self._scene_manager:
                self.autosave_timer += dt
                if self.autosave_timer >= AUTOSAVE_INTERVAL:
                    self.autosave_timer = 0.0
                    self._scene_manager.save_scene_to_file("autosave.json")
                    log_info("[AUTOSAVE] Scene saved to autosave.json")

            # Script Update (Visual Automation)
            if self.script_executor:
                running = self.script_executor.update()
                if not running:
                    print("[INFO] Script finalizado.")

            # Sistemas de edición (Layout, Gizmos, Selection)
            # Permite interacción si está en EDIT O si está en PLAY pero viendo la escena
            enable_scene_interaction = self._state.is_edit() or (self.editor_layout and self.editor_layout.active_tab == "SCENE")
            
            # 1. Update Layout Input (Always, for toolbar/tabs)
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
                
                if self.editor_layout.request_pause:
                    self.editor_layout.request_pause = False
                    if self._state in (EngineState.PLAY, EngineState.PAUSED):
                        self.pause()
                
                # --- SCENE UI REQUESTS ---
                self._process_ui_requests()

                if self.editor_layout.request_step:
                    self.editor_layout.request_step = False
                    if self._state in (EngineState.PLAY, EngineState.PAUSED):
                        self.step()
                
                # --- DRAG & DROP LOGIC ---
                if self._state.is_edit() and self.editor_layout.project_panel and self.editor_layout.project_panel.dragging_file:
                    if rl.is_mouse_button_released(rl.MOUSE_BUTTON_LEFT):
                        if self.editor_layout.is_mouse_in_scene_view() and active_world is not None:
                            file_path = self.editor_layout.project_panel.dragging_file
                            drop_pos = self.editor_layout.get_scene_mouse_pos()
                            
                            filename = os.path.basename(file_path)
                            name, ext = os.path.splitext(filename)
                            
                            if ext.lower() == ".prefab":
                                # Instantiate Prefab
                                print(f"[DROP] Instantiating Prefab '{name}' from {file_path}")
                                from engine.assets.prefab import PrefabManager
                                prefab_data = PrefabManager.load_prefab_data(file_path)
                                if prefab_data and self._scene_manager is not None:
                                    unique_name = name
                                    count = 1
                                    while active_world.get_entity_by_name(unique_name):
                                        unique_name = f"{name}_{count}"
                                        count += 1
                                    prefab_data["name"] = unique_name
                                    transform_data = prefab_data.setdefault("components", {}).setdefault("Transform", {})
                                    transform_data["x"] = drop_pos.x
                                    transform_data["y"] = drop_pos.y
                                    if self._scene_manager.create_entity_from_data(prefab_data):
                                        active_world.selected_entity_name = unique_name
                            else:
                                # Default: Create Sprite Entity
                                base_name = name
                                count = 1
                                while active_world.get_entity_by_name(name):
                                    name = f"{base_name}_{count}"
                                    count += 1
                                    
                                print(f"[DROP] Creating Sprite Entity '{name}' from {file_path}")
                                if self._scene_manager is not None:
                                    created = self._scene_manager.create_entity(
                                        name,
                                        {
                                            "Transform": {
                                                "enabled": True,
                                                "x": drop_pos.x,
                                                "y": drop_pos.y,
                                                "rotation": 0.0,
                                                "scale_x": 1.0,
                                                "scale_y": 1.0,
                                            },
                                            "Sprite": {
                                                "enabled": True,
                                                "texture_path": file_path,
                                                "width": 0,
                                                "height": 0,
                                                "origin_x": 0.5,
                                                "origin_y": 0.5,
                                                "flip_x": False,
                                                "flip_y": False,
                                                "tint": [255, 255, 255, 255],
                                            },
                                            "Collider": {
                                                "enabled": True,
                                                "width": 32,
                                                "height": 32,
                                                "offset_x": 0.0,
                                                "offset_y": 0.0,
                                                "is_trigger": False,
                                            },
                                        },
                                    )
                                    if created:
                                        active_world.selected_entity_name = name
                                else:
                                    new_ent = active_world.create_entity(name)
                                    from engine.components.transform import Transform
                                    from engine.components.sprite import Sprite
                                    from engine.components.collider import Collider
                                    new_ent.add_component(Transform(drop_pos.x, drop_pos.y))
                                    new_ent.add_component(Sprite(file_path)) 
                                    new_ent.add_component(Collider(32, 32)) 
                                    active_world.selected_entity_name = name

            # 2. Gizmos & Selection (Only if interaction enabled)
            if enable_scene_interaction:
                 mouse_world = rl.Vector2(0,0)
                 mouse_in_scene = False
                 if self.editor_layout:
                     mouse_world = self.editor_layout.get_scene_mouse_pos()
                     mouse_in_scene = self.editor_layout.is_mouse_in_scene_view()
                     # CRITICAL: Prevent scene interaction (selection/gizmo) if mouse is over Inspector
                     if self.editor_layout.is_mouse_in_inspector():
                         mouse_in_scene = False

                 # Gizmos
                 if self.gizmo_system is not None and active_world is not None:
                     if self.gizmo_system.is_dragging or mouse_in_scene:
                          # Pass current tool from editor layout
                          tool = self.editor_layout.current_tool if self.editor_layout else "Move"
                          self.gizmo_system.update(active_world, mouse_world, tool)
                     
                 if self._selection_system is not None and active_world is not None:
                     gizmo_active = False
                     if self.gizmo_system:
                          if self.gizmo_system.hover_mode.value != 1: 
                              gizmo_active = True
                              
                     if not gizmo_active and mouse_in_scene and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
                         self._selection_system.update(active_world, mouse_world)

            # Update Animation (Only in Play/Step mode)
            if self._state.allows_gameplay():
                try:
                    self._update_animation(active_world, dt)
                except Exception as e:
                    from engine.editor.console_panel import log_err
                    log_err(f"Animation error: {e}")
            
            # Actualización de gameplay (Física, Colisiones, Reglas)
            if self._state.allows_physics() or self._state.allows_gameplay():
                try:
                    self._update_gameplay(active_world, dt)
                except Exception as e:
                    from engine.editor.console_panel import log_err
                    log_err(f"Gameplay error: {e}")

            if self._state == EngineState.EDIT and active_world is not None and self._script_behaviour_system is not None:
                try:
                    self._script_behaviour_system.update(active_world, dt, is_edit_mode=True)
                except Exception as e:
                    from engine.editor.console_panel import log_err
                    log_err(f"ScriptBehaviour error: {e}")
            
            # Si estábamos en STEPPING, volvemos a PAUSED después de un frame
            if self._state == EngineState.STEPPING:
                self._state = EngineState.PAUSED

            if self._state == EngineState.EDIT and self._scene_manager is not None:
                self._scene_manager.sync_from_edit_world()
            
            # Renderizar FRAME (Safe)
            try:
                self._render_frame(active_world)
            except Exception as e:
                from engine.editor.console_panel import log_err
                log_err(f"CRITICAL RENDER ERROR: {e}")
        
        self._cleanup()
    
    def _update_animation(self, world: Optional["World"], dt: float) -> None:
        if self._animation_system is None or world is None:
            return
        
        if self._state.allows_animation():
            self._animation_system.update(world, dt)
        elif self._state.allows_animation_preview():
            self._animation_system.update(world, dt * self.EDIT_ANIMATION_SPEED)
    
    def _process_input(self) -> None:
        # SPACE -> Play/Stop Toggle
        if rl.is_key_pressed(rl.KEY_SPACE):
            if self._state == EngineState.EDIT:
                self.play()
                if self.editor_layout:
                    self.editor_layout.active_tab = "GAME"
            elif self._state in (EngineState.PLAY, EngineState.PAUSED, EngineState.STEPPING):
                self.stop()
                if self.editor_layout:
                    self.editor_layout.active_tab = "SCENE"
        
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
    
        # F8: Hot-Reload Scripts
        if rl.is_key_pressed(rl.KEY_F8):
            reloaded = self.hot_reload_manager.check_for_changes()
            if reloaded:
                for mod_name in reloaded:
                    log_info(f"Hot-reload: {mod_name} recargado")
            else:
                log_info("Hot-reload: Sin cambios detectados")
            # Log errors if any
            for err in self.hot_reload_manager.get_errors():
                log_err(err)
        
        # Ctrl+S: Save
        if rl.is_key_down(rl.KEY_LEFT_CONTROL) and rl.is_key_pressed(rl.KEY_S):
            self.save_current_scene()
        if rl.is_key_down(rl.KEY_LEFT_CONTROL) and rl.is_key_pressed(rl.KEY_Z):
            self._history_manager.undo()
        if rl.is_key_down(rl.KEY_LEFT_CONTROL) and rl.is_key_pressed(rl.KEY_Y):
            self._history_manager.redo()
            
    def save_current_scene(self) -> None:
        """Guarda la escena actual a disco."""
        if self._scene_manager is None:
            print("[ERROR] No hay SceneManager activo, no se puede guardar.")
            return
            
        print(f"[INFO] Guardando escena en: {self.current_scene_path}")
        success = self._scene_manager.save_scene_to_file(self.current_scene_path)
        if success:
             if self._project_service is not None and self.current_scene_path:
                 self._project_service.set_last_scene(self.current_scene_path)
             self._scene_manager.clear_dirty()
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
        if self._input_system is not None:
            self._input_system.update(world)
        if self._player_controller_system is not None:
            self._player_controller_system.update(world)
        if self._script_behaviour_system is not None:
            self._script_behaviour_system.update(world, dt, is_edit_mode=False)
        if self._physics_system is not None and self._state.allows_physics():
            self._physics_system.update(world, dt)
            
        if self._collision_system is not None and self._state.allows_gameplay():
            self._collision_system.update(world)
        if self._audio_system is not None:
            self._audio_system.update(world)
            
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
    
    def _render_frame(self, active_world: "World") -> None:
        """Renderiza un frame completo de la aplicación (Scene, Game, UI)."""
        rl.begin_drawing()
        rl.clear_background(rl.DARKGRAY)
        
        try:
            # --- WINDOW RESIZE HANDLING ---
            if rl.is_window_resized():
                self.width = rl.get_screen_width()
                self.height = rl.get_screen_height()
                if self.editor_layout:
                    self.editor_layout.update_layout(self.width, self.height)

            # --- SCENE VIEW RENDER ---
            # Renderizar Scene siempre que la pestaña esté activa (Edit o Play)
            if self.editor_layout and self.editor_layout.active_tab == "SCENE":
                self.editor_layout.begin_scene_render()
                
                # Render World (Editor Camera)
                if self._render_system is not None and active_world is not None:
                     self._render_system.render(active_world, use_world_camera=False)

                # Render Gizmos
                if self.gizmo_system is not None and active_world is not None:
                    self.gizmo_system.render(active_world)
                    
                self.editor_layout.end_scene_render()
            
            # --- GAME VIEW RENDER ---
            if self.editor_layout and self.editor_layout.active_tab == "GAME":
                target_world = self.world if self._state == EngineState.PLAY or self._state == EngineState.PAUSED else None
                
                self.editor_layout.begin_game_render()
                if target_world and self._render_system:
                    texture = self.editor_layout.game_texture.texture
                    viewport_size = (float(texture.width), float(texture.height))
                    self._render_system.render(target_world, viewport_size=viewport_size)
                else:
                    rl.draw_text("Press PLAY to start", 10, 10, 20, rl.GRAY)
                    
                self.editor_layout.end_game_render()
            
            # --- MAIN SCREEN RENDER (LAYOUT & OVERLAYS) ---
            if self.editor_layout:
                is_playing = (self._state == EngineState.PLAY or self._state == EngineState.PAUSED)
                self.editor_layout.draw_layout(is_playing)
            else:
                 # Fallback
                 if self._render_system is not None and active_world is not None:
                    self._render_system.render(active_world)

            # Inspector Render (Overlay on Layout)
            if self._inspector_system is not None and active_world is not None:
                if self.editor_layout:
                    rect = self.editor_layout.inspector_rect
                    self._inspector_system.render(
                        active_world, 
                        int(rect.x), int(rect.y), 
                        int(rect.width), int(rect.height),
                        is_edit_mode=self.is_edit_mode
                    )

            self._draw_debug_info()
            
            # Hierachy Panel Overlay
            if self.hierarchy_panel is not None and active_world is not None:
                if self.editor_layout:
                    rect = self.editor_layout.hierarchy_rect
                    self.hierarchy_panel.render(active_world, int(rect.x), int(rect.y), int(rect.width), int(rect.height))
                else:
                    self.hierarchy_panel.render(active_world, 0, 0, 200, self.height)

        finally:
            rl.end_drawing()

    def _cleanup(self) -> None:
        self.running = False
        if self._render_system is not None:
            self._render_system.cleanup()
        rl.close_window()
    
    def _process_ui_requests(self) -> None:
        """Procesa peticiones de UI (Escenas, Menús de archivo)."""
        if self.editor_layout is None or self._scene_manager is None: return

        if self.editor_layout.project_panel and self.editor_layout.project_panel.request_open_sprite_editor_for:
            target_asset = self.editor_layout.project_panel.request_open_sprite_editor_for
            self.editor_layout.project_panel.request_open_sprite_editor_for = None
            if self._inspector_system is not None and hasattr(self._inspector_system, "open_sprite_editor"):
                self._inspector_system.open_sprite_editor(target_asset)

        if self.editor_layout.request_browse_project:
            self.editor_layout.request_browse_project = False
            try:
                import tkinter
                from tkinter import filedialog
                root = tkinter.Tk()
                root.withdraw()
                path = filedialog.askdirectory(initialdir=os.getcwd(), title="Open Project")
                root.destroy()
                if path:
                    self.editor_layout.pending_project_path = path
            except Exception as e:
                print(f"[ERROR] Open Project browse failed: {e}")

        if self.editor_layout.pending_project_path and not self.editor_layout.show_project_dirty_modal:
            target_project = self.editor_layout.pending_project_path
            if self._scene_manager.is_dirty:
                self.editor_layout.show_project_dirty_modal = True
            else:
                self.editor_layout.pending_project_path = ""
                self.open_project(target_project)

        if self.editor_layout.project_switch_decision:
            decision = self.editor_layout.project_switch_decision
            self.editor_layout.project_switch_decision = ""
            target_project = self.editor_layout.pending_project_path
            if decision == "save":
                self.save_current_scene()
                if target_project:
                    self.editor_layout.pending_project_path = ""
                    self.open_project(target_project)
            elif decision == "discard":
                self._scene_manager.clear_dirty()
                if target_project:
                    self.editor_layout.pending_project_path = ""
                    self.open_project(target_project)
            else:
                self.editor_layout.pending_project_path = ""

        # NEW SCENE
        if self.editor_layout.request_new_scene:
            self.editor_layout.request_new_scene = False
            self.stop() # Ensure Edit Mode
            self._world = self._scene_manager.create_new_scene("New Scene")
            print("[GUI] New Scene created")

        # SAVE SCENE
        if self.editor_layout.request_save_scene:
            self.editor_layout.request_save_scene = False
            try:
                import tkinter
                from tkinter import filedialog
                root = tkinter.Tk()
                root.withdraw()
                path = filedialog.asksaveasfilename(
                    defaultextension=".json",
                    filetypes=[("Scene Files", "*.json"), ("All Files", "*.*")],
                    initialdir=self._project_service.get_project_path("levels").as_posix() if self._project_service is not None else os.getcwd(),
                    title="Save Scene As"
                )
                root.destroy()
                if path:
                    self.current_scene_path = path
                    self._scene_manager.save_scene_to_file(path)
            except Exception as e:
                print(f"[ERROR] Save Dialog failed: {e}")
                # Fallback
                self._scene_manager.save_scene_to_file("scene_backend_save.json")

        # LOAD SCENE
        if self.editor_layout.request_load_scene:
            self.editor_layout.request_load_scene = False
            try:
                import tkinter
                from tkinter import filedialog
                root = tkinter.Tk()
                root.withdraw()
                path = filedialog.askopenfilename(
                    filetypes=[("Scene Files", "*.json"), ("All Files", "*.*")],
                    initialdir=self._project_service.get_project_path("levels").as_posix() if self._project_service is not None else os.getcwd(),
                    title="Open Scene"
                )
                root.destroy()
                if path:
                    self.stop() # Ensure Edit Mode
                    self._world = self._scene_manager.load_scene_from_file(path)
                    self.current_scene_path = path
                    if self._project_service is not None:
                        self._project_service.set_last_scene(path)
            except Exception as e:
                print(f"[ERROR] Load Dialog failed: {e}")
