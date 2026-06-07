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
        super().__init__("Headless", width, height, 60, editor_enabled=False, hot_reload_enabled=False)
        from engine.editor.undo_redo import UndoRedoManager

        self._history_manager = UndoRedoManager()
        self.headless_running: bool = False
        self._install_headless_debug_tools()

    def _install_headless_debug_tools(self) -> None:
        from engine.app.debug_tools_controller import DebugToolsController

        self._debug_tools_controller = DebugToolsController(
            time_manager=self.time,
            timeline=self.timeline,
            profiler=self._profiler,
            hot_reload_manager=self.hot_reload_manager,
            perf_stats=self._perf_stats,
            perf_counters=self._perf_counters,
            get_state=lambda: self._state,
            get_world=lambda: self.world,
            set_world=self.set_world,
            get_scene_manager=lambda: self._scene_manager,
            get_level_loader=lambda: self._level_loader,
            get_rule_system=lambda: self._rule_system,
            get_collision_system=lambda: self._collision_system,
            get_render_system=lambda: self._render_system,
            get_physics_backend_registry=lambda: self._physics_backend_registry,
            get_width=lambda: self.width,
            get_show_performance_overlay=lambda: self.show_performance_overlay,
            set_show_performance_overlay=lambda value: setattr(self, "show_performance_overlay", value),
            get_debug_draw_colliders=lambda: self.debug_draw_colliders,
            set_debug_draw_colliders=lambda value: setattr(self, "debug_draw_colliders", value),
            get_debug_draw_labels=lambda: self.debug_draw_labels,
            set_debug_draw_labels=lambda value: setattr(self, "debug_draw_labels", value),
        )

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
