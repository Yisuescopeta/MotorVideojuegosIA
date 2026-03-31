"""
cli/headless_game.py - Headless runtime entrypoint
"""

import time

from engine.core.game import Game


class HeadlessGame(Game):
    """
    Version del juego que no abre ventana ni renderiza.
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

        last_time = time.time()
        while self.headless_running:
            current_time = time.time()
            dt = current_time - last_time
            last_time = current_time
            if dt > 0.1:
                dt = 0.1
            self.update_headless(dt)
            time.sleep(0.001)

    def update_headless(self, dt: float) -> None:
        """Ejecuta un frame de logica sin renderizado."""
        frame_start = time.perf_counter()
        self.time.update_manual(dt)

        active_world = self.world
        self._perf_stats["render"] = 0.0
        self._perf_stats["inspector"] = 0.0
        self._perf_stats["hierarchy"] = 0.0
        self._perf_stats["selection_gizmo"] = 0.0
        self._perf_stats["scripts"] = 0.0
        self._perf_stats["gameplay"] = 0.0
        self._perf_stats["animation"] = 0.0
        self._perf_stats["ui"] = 0.0

        if self._state.is_edit():
            if self._selection_system is not None and active_world is not None:
                pass
            if self._script_behaviour_system is not None and active_world is not None:
                scripts_start = time.perf_counter()
                self._script_behaviour_system.update(active_world, dt, is_edit_mode=True)
                self._perf_stats["scripts"] = (time.perf_counter() - scripts_start) * 1000.0

        if active_world is not None and (self._state.allows_physics() or self._state.allows_gameplay()):
            gameplay_start = time.perf_counter()
            self._update_gameplay(active_world, dt)
            self._perf_stats["gameplay"] = (time.perf_counter() - gameplay_start) * 1000.0

        animation_start = time.perf_counter()
        self._update_animation(active_world, dt)
        self._perf_stats["animation"] = (time.perf_counter() - animation_start) * 1000.0

        if active_world is not None:
            ui_start = time.perf_counter()
            self._update_ui_overlay(active_world, (float(self.width), float(self.height)))
            self._perf_stats["ui"] = (time.perf_counter() - ui_start) * 1000.0

        if self._state.is_edit() and self._scene_manager is not None:
            self._scene_manager.sync_from_edit_world()

        self._perf_stats["frame"] = (time.perf_counter() - frame_start) * 1000.0
        self._update_perf_counters(active_world)
        self._record_profiler_frame(active_world)

    def step_frame(self, dt: float = 1.0 / 60.0) -> None:
        """Avanza manualmente un frame."""
        self.update_headless(dt)

    def request_shutdown(self) -> None:
        super().request_shutdown()
        self.headless_running = False
