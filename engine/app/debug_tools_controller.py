from __future__ import annotations

import gc
import importlib
import json
import time
from typing import TYPE_CHECKING, Any, Callable, Optional

import pyray as rl
from engine.components.canvas import Canvas
from engine.components.scriptbehaviour import ScriptBehaviour
from engine.components.uibutton import UIButton
from engine.debug.profiler import EngineProfiler
from engine.debug.timeline import Timeline
from engine.editor.console_panel import log_err, log_info
from engine.physics.registry import PhysicsBackendRegistry

if TYPE_CHECKING:
    from engine.core.engine_state import EngineState
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
        self._memory_cache: dict[str, Any] = {
            "world_id": None,
            "world_version": None,
            "timestamp": 0.0,
            "data": self._empty_memory_counters(),
        }

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
        from engine.core.engine_state import EngineState

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
        from engine.core.engine_state import EngineState

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
            gc_counts = gc.get_count()
            counters = {
                "entities": 0,
                "components": 0,
                "component_count": 0,
                "render_entities": 0,
                "draw_calls": 0,
                "batches": 0,
                "tilemap_chunks": 0,
                "tilemap_chunk_rebuilds": 0,
                "render_target_passes": 0,
                "physics_ccd_bodies": 0,
                "physics_contacts": 0,
                "physics_candidate_solids": 0,
                "collision_candidates": 0,
                "collision_pairs_tested": 0,
                "collision_hits": 0,
                "canvases": 0,
                "buttons": 0,
                "scripts": 0,
                "gc_gen0_count": gc_counts[0],
                "gc_gen1_count": gc_counts[1],
                "gc_gen2_count": gc_counts[2],
                "textures_loaded": 0,
                "texture_load_failures": 0,
                "texture_cache_approx_bytes": 0,
                "render_sorted_entities_cache_size": 0,
                "render_graph_pass_cache_size": 0,
                "tilemap_chunk_cache_size": 0,
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
        physics_candidate_solids = 0
        collision_candidates = 0
        collision_pairs_tested = 0
        collision_hits = 0

        render_system = self._get_render_system()
        if render_system is not None and hasattr(render_system, "get_last_render_stats"):
            render_stats = render_system.get_last_render_stats()
            render_entities = int(render_stats.get("render_entities", 0))
            draw_calls = int(render_stats.get("draw_calls", 0))
            batches = int(render_stats.get("batches", 0))
            tilemap_chunks = int(render_stats.get("tilemap_chunks", 0))
            tilemap_chunk_rebuilds = int(render_stats.get("tilemap_chunk_rebuilds", 0))
            render_target_passes = int(render_stats.get("render_target_passes", 0))

        component_count = self._count_world_components(active_world)
        gc_gen0_count, gc_gen1_count, gc_gen2_count = gc.get_count()
        texture_metrics = self._collect_texture_metrics(render_system)
        cache_metrics = self._collect_cache_metrics(render_system)

        resolved_backend = self._get_physics_backend_registry().resolve(active_world)
        backend = resolved_backend.backend
        if backend is not None:
            backend_metrics = backend.get_step_metrics()
            physics_ccd_bodies = int(backend_metrics.get("ccd_bodies", 0))
            physics_contacts = int(backend_metrics.get("contacts", 0))
            physics_candidate_solids = int(backend_metrics.get("candidate_solids", 0))

        collision_system = self._get_collision_system()
        if collision_system is not None and hasattr(collision_system, "get_step_metrics"):
            collision_metrics = collision_system.get_step_metrics()
            collision_candidates = int(collision_metrics.get("candidate_pairs", 0))
            collision_pairs_tested = int(collision_metrics.get("narrow_phase_pairs", 0))
            collision_hits = int(collision_metrics.get("actual_collisions", 0))

        counters = {
            "entities": active_world.entity_count(),
            "components": component_count,
            "component_count": component_count,
            "render_entities": render_entities,
            "draw_calls": draw_calls,
            "batches": batches,
            "tilemap_chunks": tilemap_chunks,
            "tilemap_chunk_rebuilds": tilemap_chunk_rebuilds,
            "render_target_passes": render_target_passes,
            "physics_ccd_bodies": physics_ccd_bodies,
            "physics_contacts": physics_contacts,
            "physics_candidate_solids": physics_candidate_solids,
            "collision_candidates": collision_candidates,
            "collision_pairs_tested": collision_pairs_tested,
            "collision_hits": collision_hits,
            "canvases": len(active_world.get_entities_with(Canvas)),
            "buttons": len(active_world.get_entities_with(UIButton)),
            "scripts": len(active_world.get_entities_with(ScriptBehaviour)),
            "gc_gen0_count": int(gc_gen0_count),
            "gc_gen1_count": int(gc_gen1_count),
            "gc_gen2_count": int(gc_gen2_count),
            **texture_metrics,
            **cache_metrics,
        }
        self._perf_counters.clear()
        self._perf_counters.update(counters)

    def _count_world_components(self, active_world: "World") -> int:
        total = 0
        for entity in active_world.iter_all_entities():
            if hasattr(entity, "iter_components"):
                total += sum(1 for _ in entity.iter_components())
            elif hasattr(entity, "get_all_components"):
                total += len(entity.get_all_components())
        return total

    def _collect_texture_metrics(self, render_system: Any) -> dict[str, int]:
        metrics = {
            "textures_loaded": 0,
            "texture_load_failures": 0,
            "texture_cache_approx_bytes": 0,
        }
        texture_manager = getattr(render_system, "texture_manager", None)
        if texture_manager is None or not hasattr(texture_manager, "get_metrics"):
            return metrics
        raw_metrics = texture_manager.get_metrics()
        metrics["textures_loaded"] = int(raw_metrics.get("loaded_count", 0))
        metrics["texture_load_failures"] = int(raw_metrics.get("failed_count", 0))
        metrics["texture_cache_approx_bytes"] = int(raw_metrics.get("approx_memory", 0))
        return metrics

    def _collect_cache_metrics(self, render_system: Any) -> dict[str, int]:
        metrics = {
            "render_sorted_entities_cache_size": 0,
            "render_graph_pass_cache_size": 0,
            "tilemap_chunk_cache_size": 0,
        }
        if render_system is None:
            return metrics
        sorted_entities_cache = getattr(render_system, "_sorted_entities_cache", None)
        if sorted_entities_cache is not None:
            metrics["render_sorted_entities_cache_size"] = len(sorted_entities_cache)
        render_graph_cache = getattr(render_system, "_render_graph_cache", None)
        if isinstance(render_graph_cache, dict):
            passes = render_graph_cache.get("passes", [])
            metrics["render_graph_pass_cache_size"] = len(passes) if hasattr(passes, "__len__") else 0
        tilemap_chunk_cache = getattr(render_system, "_tilemap_chunk_cache", None)
        if tilemap_chunk_cache is not None:
            metrics["tilemap_chunk_cache_size"] = len(tilemap_chunk_cache)
        return metrics

    def _empty_memory_counters(self) -> dict[str, float]:
        return {"world_json_bytes": 0.0, "entity_avg_json_bytes": 0.0}

    def _process_memory_counters(self) -> dict[str, float]:
        try:
            psutil = importlib.import_module("psutil")
            memory_info = psutil.Process().memory_info()
        except Exception:
            return {}
        return {
            "process_rss_bytes": float(getattr(memory_info, "rss", 0.0)),
            "process_vms_bytes": float(getattr(memory_info, "vms", 0.0)),
        }

    def approximate_memory_counters(self, active_world: Optional["World"]) -> dict[str, float]:
        if active_world is None:
            return self._empty_memory_counters()
        world_id = int(id(active_world))
        world_version = int(getattr(active_world, "version", 0))
        now = time.perf_counter()
        if (
            self._memory_cache.get("world_id") == world_id
            and self._memory_cache.get("world_version") == world_version
            and (now - float(self._memory_cache.get("timestamp", 0.0))) <= 1.0
        ):
            return dict(self._memory_cache.get("data", self._empty_memory_counters()))
        try:
            payload = active_world.serialize()
            encoded = json.dumps(payload, separators=(",", ":"), ensure_ascii=True)
            total_bytes = float(len(encoded.encode("utf-8")))
        except Exception as exc:
            log_err(f"approximate_memory_counters: serialización fallida: {exc}")
            total_bytes = 0.0
        entity_count = max(1, active_world.entity_count())
        data = {
            "world_json_bytes": total_bytes,
            "entity_avg_json_bytes": total_bytes / entity_count,
        }
        self._memory_cache = {
            "world_id": world_id,
            "world_version": world_version,
            "timestamp": now,
            "data": data,
        }
        return dict(data)

    def record_profiler_frame(
        self,
        active_world: Optional["World"],
        *,
        frame_time_ms: float | None = None,
        deep: bool = False,
    ) -> None:
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
        memory = self.approximate_memory_counters(active_world) if deep else self._empty_memory_counters()
        memory.update(self._process_memory_counters())
        self._profiler.record_frame(
            timings_ms=timings_ms,
            counters=dict(self._perf_counters),
            memory=memory,
            mode=str(self._get_state()),
            frame_index=int(self._time_manager.frame_count),
            backend=backend_name,
            backend_metrics=backend_metrics,
        )

    def draw_performance_overlay(self) -> None:
        if not self._get_show_performance_overlay():
            return

        panel_width = 260
        panel_height = 288
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
            f"phys candidates: {self._perf_counters.get('physics_candidate_solids', 0)}",
            panel_x + 10,
            text_y,
            10,
            rl.SKYBLUE,
        )
        text_y += 14
        rl.draw_text(
            f"collision cand/tests: {self._perf_counters.get('collision_candidates', 0)}/{self._perf_counters.get('collision_pairs_tested', 0)}",
            panel_x + 10,
            text_y,
            10,
            rl.SKYBLUE,
        )
        text_y += 14
        rl.draw_text(
            f"collision hits: {self._perf_counters.get('collision_hits', 0)}",
            panel_x + 10,
            text_y,
            10,
            rl.SKYBLUE,
        )
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
