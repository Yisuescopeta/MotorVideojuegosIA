from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Callable, Optional

import pyray as rl

from engine.components.canvas import Canvas
from engine.components.scriptbehaviour import ScriptBehaviour
from engine.components.uibutton import UIButton
from engine.core.engine_state import EngineState
from engine.debug.profiler import EngineProfiler
from engine.debug.timeline import Timeline
from engine.editor.console_panel import log_err, log_info
from engine.physics.registry import PhysicsBackendRegistry

if TYPE_CHECKING:
    from engine.core.hot_reload import HotReloadManager
    from engine.core.time_manager import TimeManager
    from engine.ecs.world import World


class DebugToolsController:
    """Owns debug tooling, profiling, and snapshot helpers for Game."""

    def __init__(
        self,
        *,
        time_manager: "TimeManager",
        timeline: Timeline,
        profiler: EngineProfiler,
        hot_reload_manager: "HotReloadManager",
        perf_stats: dict[str, float],
        perf_counters: dict[str, int],
        get_state: Callable[[], EngineState],
        get_world: Callable[[], Optional["World"]],
        set_world: Callable[[Optional["World"]], None],
        get_scene_manager: Callable[[], Any],
        get_level_loader: Callable[[], Any],
        get_rule_system: Callable[[], Any],
        get_collision_system: Callable[[], Any],
        get_render_system: Callable[[], Any],
        get_physics_backend_registry: Callable[[], PhysicsBackendRegistry],
        get_width: Callable[[], int],
        get_show_performance_overlay: Callable[[], bool],
        set_show_performance_overlay: Callable[[bool], None],
        get_debug_draw_colliders: Callable[[], bool],
        set_debug_draw_colliders: Callable[[bool], None],
        get_debug_draw_labels: Callable[[], bool],
        set_debug_draw_labels: Callable[[bool], None],
    ) -> None:
        self._time_manager = time_manager
        self._timeline = timeline
        self._profiler = profiler
        self._hot_reload_manager = hot_reload_manager
        self._perf_stats = perf_stats
        self._perf_counters = perf_counters
        self._get_state = get_state
        self._get_world = get_world
        self._set_world = set_world
        self._get_scene_manager = get_scene_manager
        self._get_level_loader = get_level_loader
        self._get_rule_system = get_rule_system
        self._get_collision_system = get_collision_system
        self._get_render_system = get_render_system
        self._get_physics_backend_registry = get_physics_backend_registry
        self._get_width = get_width
        self._get_show_performance_overlay = get_show_performance_overlay
        self._set_show_performance_overlay = set_show_performance_overlay
        self._get_debug_draw_colliders = get_debug_draw_colliders
        self._set_debug_draw_colliders = set_debug_draw_colliders
        self._get_debug_draw_labels = get_debug_draw_labels
        self._set_debug_draw_labels = set_debug_draw_labels

    def apply_render_debug_options(self, render_system: Any) -> None:
        if render_system is None or not hasattr(render_system, "set_debug_options"):
            return
        render_system.set_debug_options(
            draw_colliders=self._get_debug_draw_colliders(),
            draw_labels=self._get_debug_draw_labels(),
        )

    def reset_profiler(self, run_label: str = "default") -> None:
        self._profiler.begin_run(run_label=run_label)

    def get_profiler_report(self) -> dict[str, Any]:
        return self._profiler.to_report()

    def handle_debug_shortcuts(
        self,
        *,
        step_callback: Callable[[], None],
        toggle_fullscreen_callback: Callable[[], None],
    ) -> None:
        state = self._get_state()
        if state in (EngineState.PAUSED, EngineState.PLAY):
            if rl.is_key_pressed(rl.KEY_F10):
                step_callback()
            if rl.is_key_pressed(rl.KEY_F5):
                self.save_snapshot()
            if rl.is_key_pressed(rl.KEY_F6):
                self.load_last_snapshot()

        if rl.is_key_pressed(rl.KEY_F11):
            toggle_fullscreen_callback()

        if rl.is_key_pressed(rl.KEY_F8):
            reloaded = self._hot_reload_manager.check_for_changes()
            if reloaded:
                for module_name in reloaded:
                    log_info(f"Hot-reload: {module_name} recargado")
            else:
                log_info("Hot-reload: Sin cambios detectados")
            for err in self._hot_reload_manager.get_errors():
                log_err(err)

        if rl.is_key_pressed(rl.KEY_F9):
            enabled = not self._get_show_performance_overlay()
            self._set_show_performance_overlay(enabled)
            log_info(f"Performance overlay: {'ON' if enabled else 'OFF'}")

        if (
            rl.is_key_pressed(rl.KEY_F7)
            and not rl.is_key_down(rl.KEY_LEFT_CONTROL)
            and not rl.is_key_down(rl.KEY_RIGHT_CONTROL)
        ):
            enabled = not self._get_debug_draw_colliders()
            self._set_debug_draw_colliders(enabled)
            render_system = self._get_render_system()
            if render_system is not None and hasattr(render_system, "set_debug_options"):
                render_system.set_debug_options(draw_colliders=enabled)
            log_info(f"Collider overlay: {'ON' if enabled else 'OFF'}")

        if (rl.is_key_down(rl.KEY_LEFT_CONTROL) or rl.is_key_down(rl.KEY_RIGHT_CONTROL)) and rl.is_key_pressed(rl.KEY_F7):
            enabled = not self._get_debug_draw_labels()
            self._set_debug_draw_labels(enabled)
            render_system = self._get_render_system()
            if render_system is not None and hasattr(render_system, "set_debug_options"):
                render_system.set_debug_options(draw_labels=enabled)
            log_info(f"Debug labels: {'ON' if enabled else 'OFF'}")

    def save_snapshot(self) -> None:
        world = self._get_world()
        if world is None:
            return
        self._timeline.add_snapshot(world, self._time_manager.frame_count, self._time_manager.time)
        print(f"[DEBUG] Snapshot saved. Total: {self._timeline.count()}")

    def load_last_snapshot(self) -> None:
        snapshot = self._timeline.get_latest_snapshot()
        if snapshot is None:
            print("[DEBUG] No snapshots available")
            return

        scene_manager = self._get_scene_manager()
        if scene_manager is not None:
            scene_manager.restore_world(snapshot.restore())
            self._set_world(scene_manager.active_world)
            restored_world = self._get_world()
            rule_system = self._get_rule_system()
            if rule_system is not None and restored_world is not None:
                rule_system.set_world(restored_world)
            print(f"[DEBUG] Snapshot loaded. Frame: {snapshot.frame}")

    def draw_debug_info(self) -> None:
        state = self._get_state()
        width = self._get_width()
        state_color = {
            EngineState.EDIT: rl.SKYBLUE,
            EngineState.PLAY: rl.GREEN,
            EngineState.PAUSED: rl.ORANGE,
        }
        rl.draw_text(f"[{state}]", width // 2 - 40, 10, 20, state_color.get(state, rl.WHITE))
        rl.draw_text(f"FPS: {self._time_manager.fps}", 10, 10, 20, rl.GREEN)

        active_world = self._get_world()
        if active_world is not None:
            rl.draw_text(f"Entities: {active_world.entity_count()}", 10, 35, 16, rl.LIGHTGRAY)

        collision_system = self._get_collision_system()
        if collision_system is not None and state == EngineState.PLAY:
            collisions = len(collision_system.get_collisions())
            color = rl.YELLOW if collisions > 0 else rl.LIGHTGRAY
            rl.draw_text(f"Collisions: {collisions}", 10, 55, 16, color)

        scene_manager = self._get_scene_manager()
        level_loader = self._get_level_loader()
        if scene_manager is not None:
            rl.draw_text(f"Scene: {scene_manager.scene_name}", 10, 75, 14, rl.SKYBLUE)
        elif level_loader is not None:
            rl.draw_text(f"Level: {level_loader.current_level_name}", 10, 75, 14, rl.SKYBLUE)

        rule_system = self._get_rule_system()
        if rule_system is not None and state == EngineState.PLAY:
            rl.draw_text(
                f"Rules: {rule_system.rules_count} | Exec: {rule_system.rules_executed_count}",
                10,
                95,
                12,
                rl.ORANGE,
            )

    def update_perf_counters(self, active_world: Optional["World"]) -> None:
        if active_world is None:
            counters = {
                "entities": 0,
                "render_entities": 0,
                "draw_calls": 0,
                "batches": 0,
                "tilemap_chunks": 0,
                "tilemap_chunk_rebuilds": 0,
                "render_target_passes": 0,
                "physics_ccd_bodies": 0,
                "physics_contacts": 0,
                "canvases": 0,
                "buttons": 0,
                "scripts": 0,
            }
            self._perf_counters.clear()
            self._perf_counters.update(counters)
            return

        render_entities = 0
        draw_calls = 0
        batches = 0
        tilemap_chunks = 0
        tilemap_chunk_rebuilds = 0
        render_target_passes = 0
        physics_ccd_bodies = 0
        physics_contacts = 0

        render_system = self._get_render_system()
        if render_system is not None and hasattr(render_system, "get_last_render_stats"):
            render_stats = render_system.get_last_render_stats()
            render_entities = int(render_stats.get("render_entities", 0))
            draw_calls = int(render_stats.get("draw_calls", 0))
            batches = int(render_stats.get("batches", 0))
            tilemap_chunks = int(render_stats.get("tilemap_chunks", 0))
            tilemap_chunk_rebuilds = int(render_stats.get("tilemap_chunk_rebuilds", 0))
            render_target_passes = int(render_stats.get("render_target_passes", 0))

        resolved_backend = self._get_physics_backend_registry().resolve(active_world)
        backend = resolved_backend.backend
        if backend is not None:
            backend_metrics = backend.get_step_metrics()
            physics_ccd_bodies = int(backend_metrics.get("ccd_bodies", 0))
            physics_contacts = int(backend_metrics.get("contacts", 0))

        counters = {
            "entities": active_world.entity_count(),
            "render_entities": render_entities,
            "draw_calls": draw_calls,
            "batches": batches,
            "tilemap_chunks": tilemap_chunks,
            "tilemap_chunk_rebuilds": tilemap_chunk_rebuilds,
            "render_target_passes": render_target_passes,
            "physics_ccd_bodies": physics_ccd_bodies,
            "physics_contacts": physics_contacts,
            "canvases": len(active_world.get_entities_with(Canvas)),
            "buttons": len(active_world.get_entities_with(UIButton)),
            "scripts": len(active_world.get_entities_with(ScriptBehaviour)),
        }
        self._perf_counters.clear()
        self._perf_counters.update(counters)

    def approximate_memory_counters(self, active_world: Optional["World"]) -> dict[str, float]:
        if active_world is None:
            return {"world_json_bytes": 0.0, "entity_avg_json_bytes": 0.0}
        try:
            payload = active_world.serialize()
            encoded = json.dumps(payload, separators=(",", ":"), ensure_ascii=True)
            total_bytes = float(len(encoded.encode("utf-8")))
        except Exception as exc:
            log_err(f"approximate_memory_counters: serialización fallida: {exc}")
            total_bytes = 0.0
        entity_count = max(1, active_world.entity_count())
        return {
            "world_json_bytes": total_bytes,
            "entity_avg_json_bytes": total_bytes / entity_count,
        }

    def record_profiler_frame(self, active_world: Optional["World"], *, frame_time_ms: float | None = None) -> None:
        resolved_backend = self._get_physics_backend_registry().resolve(active_world)
        backend_name = resolved_backend.effective_backend or resolved_backend.requested_backend
        backend_metrics = resolved_backend.backend.get_step_metrics() if resolved_backend.backend is not None else {}
        timings_ms = {
            "frame": float(frame_time_ms if frame_time_ms is not None else self._perf_stats.get("frame", 0.0)),
            "render": float(self._perf_stats.get("render", 0.0)),
            "inspector": float(self._perf_stats.get("inspector", 0.0)),
            "hierarchy": float(self._perf_stats.get("hierarchy", 0.0)),
            "ui": float(self._perf_stats.get("ui", 0.0)),
            "scripts": float(self._perf_stats.get("scripts", 0.0)),
            "selection_gizmo": float(self._perf_stats.get("selection_gizmo", 0.0)),
        }
        if active_world is not None:
            timings_ms["animation"] = float(self._perf_stats.get("animation", 0.0))
            timings_ms["gameplay"] = float(self._perf_stats.get("gameplay", 0.0))
        self._profiler.record_frame(
            timings_ms=timings_ms,
            counters=dict(self._perf_counters),
            memory=self.approximate_memory_counters(active_world),
            mode=str(self._get_state()),
            frame_index=int(self._time_manager.frame_count),
            backend=backend_name,
            backend_metrics=backend_metrics,
        )

    def draw_performance_overlay(self) -> None:
        if not self._get_show_performance_overlay():
            return

        panel_width = 260
        panel_height = 246
        panel_x = self._get_width() - panel_width - 12
        panel_y = 12
        panel_rect = rl.Rectangle(panel_x, panel_y, panel_width, panel_height)
        rl.draw_rectangle_rec(panel_rect, rl.Color(15, 18, 22, 220))
        rl.draw_rectangle_lines_ex(panel_rect, 1, rl.Color(80, 120, 160, 255))
        rl.draw_text("Performance", panel_x + 10, panel_y + 8, 14, rl.RAYWHITE)

        rows = [
            ("frame", self._perf_stats.get("frame", 0.0)),
            ("render", self._perf_stats.get("render", 0.0)),
            ("inspector", self._perf_stats.get("inspector", 0.0)),
            ("hierarchy", self._perf_stats.get("hierarchy", 0.0)),
            ("ui", self._perf_stats.get("ui", 0.0)),
            ("scripts", self._perf_stats.get("scripts", 0.0)),
            ("selection", self._perf_stats.get("selection_gizmo", 0.0)),
        ]
        text_y = panel_y + 32
        for label, value in rows:
            color = rl.ORANGE if value > 8.0 else rl.LIGHTGRAY
            rl.draw_text(f"{label:>10}: {value:5.2f} ms", panel_x + 10, text_y, 10, color)
            text_y += 16

        text_y += 4
        rl.draw_text(f"entities: {self._perf_counters.get('entities', 0)}", panel_x + 10, text_y, 10, rl.SKYBLUE)
        text_y += 14
        rl.draw_text(f"drawables: {self._perf_counters.get('render_entities', 0)}", panel_x + 10, text_y, 10, rl.SKYBLUE)
        text_y += 14
        rl.draw_text(
            f"draws/batches: {self._perf_counters.get('draw_calls', 0)}/{self._perf_counters.get('batches', 0)}",
            panel_x + 10,
            text_y,
            10,
            rl.SKYBLUE,
        )
        text_y += 14
        rl.draw_text(f"rt passes: {self._perf_counters.get('render_target_passes', 0)}", panel_x + 10, text_y, 10, rl.SKYBLUE)
        text_y += 14
        rl.draw_text(f"ccd bodies: {self._perf_counters.get('physics_ccd_bodies', 0)}", panel_x + 10, text_y, 10, rl.SKYBLUE)
        text_y += 14
        rl.draw_text(
            f"canvases/buttons: {self._perf_counters.get('canvases', 0)}/{self._perf_counters.get('buttons', 0)}",
            panel_x + 10,
            text_y,
            10,
            rl.SKYBLUE,
        )
        text_y += 14
        rl.draw_text(f"scripts: {self._perf_counters.get('scripts', 0)}", panel_x + 10, text_y, 10, rl.SKYBLUE)
        text_y += 16
        rl.draw_text(
            f"F7 colliders: {'ON' if self._get_debug_draw_colliders() else 'OFF'} | Ctrl+F7 labels: {'ON' if self._get_debug_draw_labels() else 'OFF'}",
            panel_x + 10,
            text_y,
            10,
            rl.GRAY,
        )
