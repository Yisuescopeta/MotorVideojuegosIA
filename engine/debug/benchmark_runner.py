from __future__ import annotations

import gc
import json
import math
import os
import platform
import statistics
import tempfile
import time
from pathlib import Path
from typing import Any

from engine.api import EngineAPI
from engine.components.transform import Transform
from engine.debug.benchmark_scenarios import build_benchmark_scenario
from engine.scenes.scene_manager import COMPACT_SCENE_SAVE_ENTITY_THRESHOLD, SceneManager

BENCHMARK_REPORT_VERSION = 4
MIN_OPERATION_WARMUP = 1
MIN_OPERATION_REPEATS = 7


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


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = max(0, min(len(ordered) - 1, math.ceil(percentile * len(ordered)) - 1))
    return ordered[index]


def _repeated_measurement(samples: list[float], *, warmup: int) -> dict[str, Any]:
    median_ms = statistics.median(samples)
    mad_ms = statistics.median(abs(sample - median_ms) for sample in samples)
    timer_resolution_ms = time.get_clock_info("perf_counter").resolution * 1000.0
    return {
        "ms": median_ms,
        "median_ms": median_ms,
        "mad_ms": mad_ms,
        "noise_floor_ms": max(mad_ms, timer_resolution_ms),
        "p95_ms": _percentile(samples, 0.95),
        "samples_ms": samples,
        "classification": "repeated_gate",
        "warmup": warmup,
    }


def _measure_repeated(callback: Any, *, warmup: int, repeats: int) -> dict[str, Any]:
    for _ in range(max(0, int(warmup))):
        callback()
    samples: list[float] = []
    for _ in range(max(1, int(repeats))):
        started = time.perf_counter()
        callback()
        samples.append(_elapsed_ms(started))
    return _repeated_measurement(samples, warmup=max(0, int(warmup)))


def _measure_play_transitions(
    api: EngineAPI,
    *,
    warmup: int,
    repeats: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    for _ in range(max(0, int(warmup))):
        api.play()
        api.stop()

    edit_to_play_samples: list[float] = []
    play_to_edit_samples: list[float] = []
    for _ in range(max(1, int(repeats))):
        started = time.perf_counter()
        api.play()
        edit_to_play_samples.append(_elapsed_ms(started))

        started = time.perf_counter()
        api.stop()
        play_to_edit_samples.append(_elapsed_ms(started))

    return (
        _repeated_measurement(edit_to_play_samples, warmup=max(0, int(warmup))),
        _repeated_measurement(play_to_edit_samples, warmup=max(0, int(warmup))),
    )


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
        "swept_checks_avg": _counter_metric(report, "avg", "physics_swept_checks"),
        "swept_checks_max": _counter_metric(report, "max", "physics_swept_checks"),
        "aabb_builds_avg": _counter_metric(report, "avg", "physics_aabb_builds"),
        "aabb_builds_max": _counter_metric(report, "max", "physics_aabb_builds"),
        "shape_builds_avg": _counter_metric(report, "avg", "physics_shape_builds"),
        "shape_builds_max": _counter_metric(report, "max", "physics_shape_builds"),
        "aabb_cache_hits_avg": _counter_metric(report, "avg", "physics_aabb_cache_hits"),
        "aabb_cache_hits_max": _counter_metric(report, "max", "physics_aabb_cache_hits"),
        "shape_cache_hits_avg": _counter_metric(report, "avg", "physics_shape_cache_hits"),
        "shape_cache_hits_max": _counter_metric(report, "max", "physics_shape_cache_hits"),
        "spatial_cell_size_avg": _counter_metric(report, "avg", "physics_spatial_cell_size"),
        "spatial_cell_size_max": _counter_metric(report, "max", "physics_spatial_cell_size"),
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
    operation_warmup: int = 1,
    operation_repeats: int = 3,
) -> dict[str, Any]:
    if bool(scenario) == bool(scene_path):
        raise ValueError("Provide exactly one of scenario or scene_path")

    normalized_mode = str(mode or "play").strip().lower() or "play"
    if normalized_mode not in {"play", "edit"}:
        raise ValueError(f"Unsupported benchmark mode: {mode}")

    frame_count = max(1, int(frames))
    delta_time = float(dt)
    requested_operation_warmup = max(0, int(operation_warmup))
    requested_operation_repeats = max(1, int(operation_repeats))
    effective_operation_warmup = max(MIN_OPERATION_WARMUP, requested_operation_warmup)
    effective_operation_repeats = max(MIN_OPERATION_REPEATS, requested_operation_repeats)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        parameters: dict[str, Any] = {}
        source: str
        scenario_name: str | None = None
        resolved_scene_path: Path
        operations: dict[str, Any] = {}
        physics_metric_samples: list[dict[str, float]] = []

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
            gc.collect()
            load_start = time.perf_counter()
            api.load_level(resolved_scene_path.as_posix())
            operations["load_level"] = {
                "ms": _elapsed_ms(load_start),
                "classification": "one_shot_diagnostic",
            }
            if api.game is None:
                raise RuntimeError("Engine game is not initialized")
            game = api.game
            scene_manager = getattr(game, "_scene_manager", None)
            edit_world = scene_manager.get_edit_world() if scene_manager is not None else game.world
            current_scene = scene_manager.current_scene if scene_manager is not None else None
            if edit_world is not None:
                operations["world_clone"] = _measure_repeated(
                    edit_world.clone,
                    warmup=effective_operation_warmup,
                    repeats=effective_operation_repeats,
                )
                operations["world_serialize"] = _measure_repeated(
                    edit_world.serialize,
                    warmup=effective_operation_warmup,
                    repeats=effective_operation_repeats,
                )

                def query_ecs() -> None:
                    edit_world.get_entities_with(Transform)
                    edit_world.group_registry.list_groups()
                    edit_world.get_children(None)

                operations["ecs_queries"] = _measure_repeated(
                    query_ecs,
                    warmup=effective_operation_warmup,
                    repeats=effective_operation_repeats,
                )
            if current_scene is not None:
                operations["scene_create_world"] = _measure_repeated(
                    lambda: current_scene.create_world(api._registry),
                    warmup=effective_operation_warmup,
                    repeats=effective_operation_repeats,
                )
                probe_index = len(current_scene.entities_data)
                operations["scene_add_entity_canonicalization"] = _measure_repeated(
                    lambda: current_scene._canonicalize_entity_for_add(
                        {
                            "name": f"BenchmarkProbe_{probe_index}",
                            "components": {
                                "Transform": {
                                    "enabled": True,
                                    "x": 0.0,
                                    "y": 0.0,
                                    "rotation": 0.0,
                                    "scale_x": 1.0,
                                    "scale_y": 1.0,
                                }
                            },
                        }
                    ),
                    warmup=effective_operation_warmup,
                    repeats=effective_operation_repeats,
                )
                scene_entity_count = len(current_scene.entities_data)
                if scene_manager is not None and scene_entity_count > COMPACT_SCENE_SAVE_ENTITY_THRESHOLD:
                    scene_save_root = temp_root / "scene_save"
                    scene_save_root.mkdir(parents=True, exist_ok=True)
                    scene_save_path = scene_save_root / "benchmark_scene.json"
                    workspace_key_before_save = scene_manager.active_scene_key
                    scene_save_manager = SceneManager(api._registry)
                    scene_save_manager.load_scene(current_scene.to_dict())

                    def save_scene() -> None:
                        if not scene_save_manager.save_scene_to_file(scene_save_path.as_posix()):
                            raise RuntimeError("Scene save benchmark failed")

                    operations["scene_save"] = _measure_repeated(
                        save_scene,
                        warmup=effective_operation_warmup,
                        repeats=effective_operation_repeats,
                    )
                    if scene_manager.active_scene_key != workspace_key_before_save:
                        raise RuntimeError("Scene save benchmark mutated the primary workspace")
                    operations["scene_save"].update(
                        {
                            "entity_count": scene_entity_count,
                            "compact_threshold": COMPACT_SCENE_SAVE_ENTITY_THRESHOLD,
                            "workspace_isolated": True,
                        }
                    )
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
                    target_entity_data = current_scene.find_entity(target_entity) if current_scene is not None else None
                    component_data = (
                        target_entity_data.get("components", {}).get(target_component, {})
                        if isinstance(target_entity_data, dict)
                        else {}
                    )
                    original_value = component_data.get(target_property, 0.0)
                    if original_value == target_value:
                        alternate_value = float(target_value) + 1.0 if isinstance(target_value, (int, float)) else ""
                    else:
                        alternate_value = original_value
                    next_value = target_value

                    def edit_transform() -> None:
                        nonlocal next_value
                        edit_result = api.edit_component(
                            target_entity,
                            target_component,
                            target_property,
                            next_value,
                        )
                        if not bool(edit_result.get("success", False)):
                            raise RuntimeError("Transform edit benchmark failed")
                        next_value = alternate_value if next_value == target_value else target_value

                    operations["transform_edit"] = _measure_repeated(
                        edit_transform,
                        warmup=effective_operation_warmup,
                        repeats=effective_operation_repeats,
                    )
                    final_edit_result = api.edit_component(
                        target_entity,
                        target_component,
                        target_property,
                        target_value,
                    )
                    final_scene = scene_manager.current_scene if scene_manager is not None else None
                    final_entity_data = final_scene.find_entity(target_entity) if final_scene is not None else None
                    final_component_data = (
                        final_entity_data.get("components", {}).get(target_component, {})
                        if isinstance(final_entity_data, dict)
                        else {}
                    )
                    operations["transform_edit"].update({
                        "success": bool(final_edit_result.get("success", False)),
                        "target_entity": target_entity,
                        "field": f"{target_component}.{target_property}",
                        "final_value": target_value,
                        "final_observed_value": final_component_data.get(target_property),
                    })

                if normalized_mode == "play":
                    edit_to_play, play_to_edit = _measure_play_transitions(
                        api,
                        warmup=effective_operation_warmup,
                        repeats=effective_operation_repeats,
                    )
                    operations["edit_to_play"] = edit_to_play
                    operations["play_to_edit"] = play_to_edit
                    api.play()

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
                        "classification": "one_shot_diagnostic",
                        "stats": render_stats,
                        "visible_entities": int(render_stats.get("spatial_visible_entities", render_stats.get("render_entities", 0))),
                        "total_entities": int(render_stats.get("spatial_total_entities", render_stats.get("render_entities", 0))),
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
                    active_world = game.world
                    if active_world is not None:
                        resolved = game._physics_backend_registry.resolve(active_world)
                        if resolved.backend is not None:
                            physics_metric_samples.append({
                                str(key): float(value)
                                for key, value in resolved.backend.get_step_metrics().items()
                                if isinstance(value, (int, float))
                            })

                profiler_report = api.get_profiler_report()
                world = game.world
                resolved_backend = (
                    game._resolve_physics_backend_name(world)
                    if world is not None and hasattr(game, "_resolve_physics_backend_name")
                    else str(backend)
                )
                if normalized_mode == "play":
                    api.stop()
                    operations["play_to_edit"]["final_mode"] = "edit" if game.is_edit_mode else "play"
                if physics_metric_samples:
                    cold = physics_metric_samples[0]
                    hot = physics_metric_samples[-1]
                    operations["physics_cache_metrics"] = {
                        "classification": "one_shot_diagnostic",
                        "cold_frame": cold,
                        "hot_frame": hot,
                        "aabb_build_reduction": cold.get("aabb_builds", 0.0)
                        - hot.get("aabb_builds", 0.0),
                        "shape_build_reduction": cold.get("shape_builds", 0.0)
                        - hot.get("shape_builds", 0.0),
                        "candidate_reduction": cold.get("candidate_solids", 0.0)
                        - hot.get("candidate_solids", 0.0),
                    }
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
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "measurement": {
            "warmup": effective_operation_warmup,
            "repeats": effective_operation_repeats,
            "requested_warmup": requested_operation_warmup,
            "requested_repeats": requested_operation_repeats,
            "minimum_warmup": MIN_OPERATION_WARMUP,
            "minimum_repeats": MIN_OPERATION_REPEATS,
        },
        "parameters": parameters,
        "operations": operations,
        "profiler_report": profiler_report,
        "last_sample": last_sample,
        "summary": _build_summary(profiler_report),
    }
