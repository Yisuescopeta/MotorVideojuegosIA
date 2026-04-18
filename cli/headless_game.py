"""
cli/headless_game.py - Headless runtime entrypoint
"""

import time
from typing import Callable

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
        scene_manager = self._scene_manager

        active_world = self.world
        self._perf_stats["render"] = 0.0
        self._perf_stats["inspector"] = 0.0
        self._perf_stats["hierarchy"] = 0.0
        self._perf_stats["selection_gizmo"] = 0.0
        self._perf_stats["scripts"] = 0.0
        self._perf_stats["gameplay"] = 0.0
        self._perf_stats["animation"] = 0.0
        self._perf_stats["ui"] = 0.0

        on_edit_scripts_ran: Callable[[], None] | None = None
        if scene_manager is not None:
            manager = scene_manager

            def sync_edit_world() -> None:
                manager.sync_from_edit_world()

            on_edit_scripts_ran = sync_edit_world

        # EngineAPI.step() runs through HeadlessGame, so the shared runtime
        # foundation must also drive the public headless path.
        self._run_runtime_tick(
            active_world,
            dt,
            viewport_size=(float(self.width), float(self.height)),
            active_tab="GAME",
            should_render_like=active_world is not None,
            on_edit_scripts_ran=on_edit_scripts_ran,
        )

        self._perf_stats["frame"] = (time.perf_counter() - frame_start) * 1000.0
        should_collect_metrics = self._should_collect_metrics()
        should_sample_metrics = self._metrics_sample_every <= 1 or (
            self._metrics_frame_index % self._metrics_sample_every == 0
        )
        self._metrics_frame_index += 1
        if should_collect_metrics:
            self._update_perf_counters(active_world)
        if should_collect_metrics and should_sample_metrics:
            self._record_profiler_frame(
                active_world,
                deep=self._should_collect_deep_metrics(),
            )

    def step_frame(self, dt: float = 1.0 / 60.0) -> None:
        """Avanza manualmente un frame."""
        self.update_headless(dt)

    def request_shutdown(self) -> None:
        super().request_shutdown()
        self.headless_running = False
