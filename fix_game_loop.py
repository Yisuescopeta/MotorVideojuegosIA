import os

GAME_PY_PATH = r"c:\Users\usuario\Downloads\MotorVideojuegosIA-main\MotorVideojuegosIA-main\engine\core\game.py"

NEW_RUN_METHOD = """    def run(self) -> None:
        "Inicia el game loop."
        rl.init_window(self.width, self.height, self.title)
        rl.set_target_fps(self.target_fps)
        
        # Aplicar tema Raygui
        apply_unity_dark_theme()
        
        # Crear EditorLayout (necesita ventana Raylib inicializada)
        if self.editor_layout is None:
            self.editor_layout = EditorLayout(self.width, self.height)
        
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
                            name = os.path.splitext(filename)[0]
                            base_name = name
                            count = 1
                            while active_world.get_entity_by_name(name):
                                name = f"{base_name}_{count}"
                                count += 1
                                
                            print(f"[DROP] Creando entidad '{name}' desde {file_path}")
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
                          self.gizmo_system.update(active_world, mouse_world)
                     
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
            
            # Si estábamos en STEPPING, volvemos a PAUSED después de un frame
            if self._state == EngineState.STEPPING:
                self._state = EngineState.PAUSED
            
            # Renderizar FRAME (Safe)
            try:
                self._render_frame(active_world)
            except Exception as e:
                from engine.editor.console_panel import log_err
                log_err(f"CRITICAL RENDER ERROR: {e}")
        
        self._cleanup()
"""

def fix_game_loop():
    with open(GAME_PY_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    start_idx = -1
    end_idx = -1
    
    for i, line in enumerate(lines):
        if line.strip().startswith("def run(self) -> None:"):
            start_idx = i
        if line.strip().startswith("self._cleanup()") and start_idx != -1:
            end_idx = i
            # Don't break, find the last cleanup? No, run ends with cleanup
            # Actually, _cleanup is called at end of run.
            # And also defined later. "def _cleanup(self)"
            # We want the CALL.
            # Indentation check: call has 8 spaces. definition has 4.
            if line.startswith("        self._cleanup()"):
               end_idx = i
               break
    
    if start_idx != -1 and end_idx != -1:
        print(f"Replacing lines {start_idx} to {end_idx}")
        new_lines = lines[:start_idx] + [NEW_RUN_METHOD] + lines[end_idx+1:]
        
        with open(GAME_PY_PATH, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        print("Success")
    else:
        print("Could not find start/end")

if __name__ == "__main__":
    fix_game_loop()
