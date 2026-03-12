"""
cli/headless_game.py - Versión del juego sin interfaz gráfica

PROPÓSITO:
    Permite ejecutar el motor en modo "headless" (sin ventana).
    Útil para tests automatizados, entrenamiento de IA o servidores.

DIFERENCIAS CON GAME:
    - No inicializa ventana de Raylib
    - No llama a render() ni draw()
    - El bucle principal es controlado externamente o por step()
"""

from typing import Optional
import time

from engine.core.game import Game
from engine.core.engine_state import EngineState

class HeadlessGame(Game):
    """
    Versión del juego que no abre ventana ni renderiza.
    """
    
    def __init__(self, width: int = 800, height: int = 600) -> None:
        super().__init__("Headless", width, height, 60)
        self.headless_running: bool = False
        
    def run(self) -> None:
        """
        Sobrescribe run() para no abrir ventana.
        En modo headless, run() ejecuta un bucle infinito hasta que se detenga.
        """
        self.headless_running = True
        print(f"[INFO] HeadlessGame iniciado en modo: {self._state}")
        
        # Simulación de bucle de juego
        last_time = time.time()
        
        while self.headless_running:
            current_time = time.time()
            dt = current_time - last_time
            last_time = current_time
            
            # Limitar dt para estabilidad (como en time_manager)
            if dt > 0.1: dt = 0.1
            
            self.update_headless(dt)
            
            # Pequeño sleep para no saturar CPU en bucle vacío
            time.sleep(0.001)
            
    def update_headless(self, dt: float) -> None:
        """Ejecuta un frame de lógica sin renderizado."""
        self.time.update_manual(dt)
        
        active_world = self.world
        
        # Procesar selección (si aplica en headless)
        if self._state.is_edit():
            if self._selection_system is not None and active_world is not None:
                # Nota: SelectionSystem usa mouse, en headless no hará nada útil
                # pero lo mantenemos por compatibilidad
                pass
            if self._script_behaviour_system is not None and active_world is not None:
                self._script_behaviour_system.update(active_world, dt, is_edit_mode=True)
        
        # Actualización de gameplay
        if self._state.allows_physics() or self._state.allows_gameplay():
            self._update_gameplay(active_world, dt)
            
        # Animación (avanza lógica interna)
        self._update_animation(active_world, dt)

        if self._state.is_edit() and self._scene_manager is not None:
            self._scene_manager.sync_from_edit_world()
    
    def step_frame(self, dt: float = 1.0/60.0) -> None:
        """Avanza manualmente un frame (útil para tests deterministicos)."""
        self.update_headless(dt)
