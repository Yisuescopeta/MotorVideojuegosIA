from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from engine.api import EngineAPI
from engine.debug.benchmark_scenarios import build_benchmark_scenario


BENCHMARK_REPORT_VERSION = 1


def _resolve_scene_path(scene_path: str, project_root: Path) -> Path:
    path = Path(scene_path)
    if path.is_absolute():
        return path.resolve()
    return (project_root / path).resolve()


def _write_scene(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    return path


def _elapsed_ms(start: float) -> float:
    return (time.perf_counter() - start) * 1000.0


def _system_metric(report: dict[str, Any], name: str, field: str) -> float:
    systems = report.get("systems", {})
    system_entry = systems.get(name, {})
    return float(system_entry.get(field, 0.0))


def _counter_metric(report: dict[str, Any], bucket: str, name: str) -> float:
    counters = report.get("counters", {})
    counter_bucket = counters.get(bucket, {})
    return float(counter_bucket.get(name, 0.0))


def _build_summary(report: dict[str, Any]) -> dict[str, float]:
    return {
        "frame_avg_ms": _system_metric(report, "frame", "avg_ms"),
        "frame_max_ms": _system_metric(report, "frame", "max_ms"),
        "gameplay_avg_ms": _system_metric(report, "gameplay", "avg_ms"),
        "gameplay_max_ms": _system_metric(report, "gameplay", "max_ms"),
        "candidate_solids_avg": _counter_metric(report, "avg", "physics_candidate_solids"),
        "candidate_solids_max": _counter_metric(report, "max", "physics_candidate_solids"),
        "collision_candidates_avg": _counter_metric(report, "avg", "collision_candidates"),
        "collision_candidates_max": _counter_metric(report, "max", "collision_candidates"),
        "collision_pairs_tested_avg": _counter_metric(report, "avg", "collision_pairs_tested"),
        "collision_pairs_tested_max": _counter_metric(report, "max", "collision_pairs_tested"),
        "collision_hits_avg": _counter_metric(report, "avg", "collision_hits"),
        "collision_hits_max": _counter_metric(report, "max", "collision_hits"),
        "entities_avg": _counter_metric(report, "avg", "entities"),
        "entities_max": _counter_metric(report, "max", "entities"),
        "draw_calls_avg": _counter_metric(report, "avg", "draw_calls"),
        "draw_calls_max": _counter_metric(report, "max", "draw_calls"),
        "render_entities_avg": _counter_metric(report, "avg", "render_entities"),
        "render_entities_max": _counter_metric(report, "max", "render_entities"),
    }


def run_benchmark(
    *,
    scenario: str | None = None,
    scene_path: str | None = None,
    project_root: str | None = None,
    backend: str = "legacy_aabb",
    mode: str = "play",
    frames: int = 120,
    dt: float = 1.0 / 60.0,
    seed: int | None = None,
    deep: bool = False,
    static_count: int = 100,
    dynamic_count: int = 12,
    entity_count: int = 1000,
    columns: int = 10,
    spacing: float = 24.0,
    velocity: float = 160.0,
    tilemap_width: int = 128,
    tilemap_height: int = 128,
) -> dict[str, Any]:
    if bool(scenario) == bool(scene_path):
        raise ValueError("Provide exactly one of scenario or scene_path")

    normalized_mode = str(mode or "play").strip().lower() or "play"
    if normalized_mode not in {"play", "edit"}:
        raise ValueError(f"Unsupported benchmark mode: {mode}")

    frame_count = max(1, int(frames))
    delta_time = float(dt)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        parameters: dict[str, Any] = {}
        source: str
        scenario_name: str | None = None
        resolved_scene_path: Path
        operations: dict[str, Any] = {}

        if scenario is not None:
            source = "scenario"
            scenario_name = str(scenario)
            benchmark_project_root = temp_root / "benchmark_project"
            scene_payload, parameters = build_benchmark_scenario(
                scenario_name,
                backend=backend,
                static_count=static_count,
                dynamic_count=dynamic_count,
                entity_count=entity_count,
                columns=columns,
                spacing=spacing,
                velocity=velocity,
                tilemap_width=tilemap_width,
                tilemap_height=tilemap_height,
            )
            resolved_scene_path = _write_scene(
                benchmark_project_root / "levels" / f"{scenario_name}.json",
                scene_payload,
            )
            resolved_project_root = benchmark_project_root
        else:
            source = "scene"
            resolved_project_root = (
                Path(project_root).expanduser().resolve() if project_root else Path(os.getcwd()).resolve()
            )
            resolved_scene_path = _resolve_scene_path(str(scene_path), resolved_project_root)

        api = EngineAPI(
            project_root=resolved_project_root.as_posix(),
            global_state_dir=(temp_root / "global_state").as_posix(),
        )
        try:
            load_start = time.perf_counter()
            api.load_level(resolved_scene_path.as_posix())
            operations["load_level"] = {"ms": _elapsed_ms(load_start)}
            if api.game is None:
                raise RuntimeError("Engine game is not initialized")
            game = api.game
            if seed is not None:
                api.set_seed(seed)
            if source == "scene":
                result = api.set_physics_backend(backend)
                if not result["success"]:
                    raise RuntimeError(str(result["message"]))

            previous_sample_every = int(getattr(game, "_metrics_sample_every", 1))
            previous_overlay = bool(getattr(game, "show_performance_overlay", False))
            previous_runtime_metrics = bool(getattr(game, "enable_runtime_metrics", False))
            previous_deep = bool(getattr(game, "enable_deep_profiling", False))

            try:
                if scenario_name == "transform_edit_stress":
                    target_entity = str(parameters.get("target_entity") or f"Entity_{max(0, int(entity_count) - 1)}")
                    target_component = str(parameters.get("target_component") or "Transform")
                    target_property = str(parameters.get("target_property") or "x")
                    target_value = parameters.get("target_value", 123456.0)
                    edit_start = time.perf_counter()
                    edit_result = api.edit_component(target_entity, target_component, target_property, target_value)
                    operations["transform_edit"] = {
                        "ms": _elapsed_ms(edit_start),
                        "success": bool(edit_result.get("success", False)),
                        "target_entity": target_entity,
                        "field": f"{target_component}.{target_property}",
                    }

                if normalized_mode == "play":
                    play_start = time.perf_counter()
                    api.play()
                    operations["edit_to_play"] = {"ms": _elapsed_ms(play_start)}

                render_system = getattr(game, "render_system", None)
                active_world = game.world
                if render_system is not None and active_world is not None and hasattr(render_system, "profile_world"):
                    render_prep_start = time.perf_counter()
                    render_stats = render_system.profile_world(
                        active_world,
                        viewport_size=(float(getattr(game, "width", 800)), float(getattr(game, "height", 600))),
                    )
                    operations["render_preparation"] = {
                        "ms": _elapsed_ms(render_prep_start),
                        "stats": render_stats,
                    }

                api.reset_profiler(
                    run_label=f"benchmark:{scenario_name or resolved_scene_path.name}:{normalized_mode}"
                )
                game.show_performance_overlay = False
                game.enable_runtime_metrics = True
                game.enable_deep_profiling = bool(deep)
                game._metrics_sample_every = 1

                for _ in range(frame_count):
                    game.step_frame(delta_time)

                profiler_report = api.get_profiler_report()
                world = game.world
                resolved_backend = (
                    game._resolve_physics_backend_name(world)
                    if world is not None and hasattr(game, "_resolve_physics_backend_name")
                    else str(backend)
                )
                if normalized_mode == "play":
                    stop_start = time.perf_counter()
                    api.stop()
                    operations["play_to_edit"] = {"ms": _elapsed_ms(stop_start)}
            finally:
                game._metrics_sample_every = previous_sample_every
                game.show_performance_overlay = previous_overlay
                game.enable_runtime_metrics = previous_runtime_metrics
                game.enable_deep_profiling = previous_deep

        finally:
            api.shutdown()

    last_sample = dict(profiler_report.get("last_frame", {}))
    return {
        "benchmark_version": BENCHMARK_REPORT_VERSION,
        "source": source,
        "scenario_name": scenario_name,
        "scene_path": None if scenario_name is not None else resolved_scene_path.as_posix(),
        "backend": resolved_backend,
        "mode": normalized_mode,
        "frames_requested": frame_count,
        "profiler_frames_recorded": int(profiler_report.get("frames", 0)),
        "dt": delta_time,
        "parameters": parameters,
        "operations": operations,
        "profiler_report": profiler_report,
        "last_sample": last_sample,
        "summary": _build_summary(profiler_report),
    }
