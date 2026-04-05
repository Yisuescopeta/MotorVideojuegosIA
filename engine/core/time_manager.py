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

import math

import pyray as rl


class TimeManager:
    """
    Gestiona el tiempo del juego: delta time, FPS y tiempo total.

    Debe llamarse update() una vez por frame para actualizar los valores.
    """

    # Maximum allowed frame time — clamps runaway deltas (e.g. debugger pause).
    # Values above this cap (0.1 s = 10 FPS floor) are treated as a single 100 ms step.
    _MAX_FRAME_TIME: float = 0.1

    def __init__(self) -> None:
        """Inicializa el gestor de tiempo con valores por defecto."""
        self._delta_time: float = 0.0
        self._total_time: float = 0.0
        self._fps: int = 0
        self._frame_count: int = 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _sanitize_frame_time(raw) -> float:
        """Return a safe non-negative float <= _MAX_FRAME_TIME from a raw pyray value.

        Handles ``None``, NaN, inf, negative, and oversized values that can occur
        in a PyInstaller-packaged context where the pyray CFFI wrapper may return
        ``None`` instead of a float when raylib has not yet fully initialised.
        """
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return 0.0
        if math.isnan(value) or math.isinf(value) or value < 0.0:
            return 0.0
        return min(value, TimeManager._MAX_FRAME_TIME)

    # ------------------------------------------------------------------
    # Public update API
    # ------------------------------------------------------------------

    def update(self) -> None:
        """
        Actualiza los valores de tiempo desde Raylib.
        Debe llamarse una vez al inicio de cada frame en modo gráfico.

        Guards against ``None`` / NaN / negative values returned by the pyray
        CFFI wrapper in a packaged (PyInstaller) standalone player context.
        """
        self._delta_time = self._sanitize_frame_time(rl.get_frame_time())
        self._total_time += self._delta_time
        raw_fps = rl.get_fps()
        self._fps = int(raw_fps) if isinstance(raw_fps, (int, float)) and raw_fps >= 0 else 0
        self._frame_count += 1

    def update_manual(self, dt: float) -> None:
        """
        Actualiza los valores de tiempo manualmente (Headless/Tests).

        Args:
            dt: Delta time en segundos.  ``None`` or invalid values are treated as 0.
        """
        safe_dt = self._sanitize_frame_time(dt)
        self._delta_time = safe_dt
        self._total_time += safe_dt
        self._fps = int(1.0 / safe_dt) if safe_dt > 0 else 0
        self._frame_count += 1

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

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
