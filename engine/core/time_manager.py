"""
engine/core/time_manager.py - Gestión del tiempo del juego

PROPÓSITO:
    Proporciona acceso al delta time (tiempo entre frames) para que
    los sistemas puedan actualizar de forma independiente del framerate.

PROPIEDADES:
    - delta_time (float): Tiempo en segundos desde el último frame
    - fps (int): Frames por segundo actuales
    - total_time (float): Tiempo total transcurrido desde el inicio

EJEMPLO DE USO:
    time_mgr = TimeManager()
    time_mgr.update()  # Llamar cada frame
    velocidad = 100 * time_mgr.delta_time  # Movimiento independiente de FPS
"""

import pyray as rl


class TimeManager:
    """
    Gestiona el tiempo del juego: delta time, FPS y tiempo total.
    
    Debe llamarse update() una vez por frame para actualizar los valores.
    """
    
    def __init__(self) -> None:
        """Inicializa el gestor de tiempo con valores por defecto."""
        self._delta_time: float = 0.0
        self._total_time: float = 0.0
        self._fps: int = 0
        self._frame_count: int = 0
    
    def update(self) -> None:
        """
        Actualiza los valores de tiempo desde Raylib.
        Debe llamarse una vez al inicio de cada frame en modo gráfico.
        """
        self._delta_time = rl.get_frame_time()
        self._total_time += self._delta_time
        self._fps = rl.get_fps()
        self._frame_count += 1
        
    def update_manual(self, dt: float) -> None:
        """
        Actualiza los valores de tiempo manualmente (Headless/Tests).
        
        Args:
            dt: Delta time en segundos
        """
        self._delta_time = dt
        self._total_time += dt
        self._fps = int(1.0 / dt) if dt > 0 else 0
        self._frame_count += 1
    
    @property
    def delta_time(self) -> float:
        """Tiempo en segundos desde el último frame."""
        return self._delta_time
    
    @property
    def fps(self) -> int:
        """Frames por segundo actuales."""
        return self._fps
    
    @property
    def total_time(self) -> float:
        """Tiempo total transcurrido desde el inicio del juego."""
        return self._total_time

    @property
    def frame_count(self) -> int:
        """Numero de frames actualizados."""
        return self._frame_count

    @property
    def time(self) -> float:
        """Alias compatible con codigo existente."""
        return self._total_time
