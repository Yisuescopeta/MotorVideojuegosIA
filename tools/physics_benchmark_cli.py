from __future__ import annotations

import argparse
import json
import time

from engine.api import EngineAPI


def build_benchmark_scene(box_count: int, ccd: bool) -> dict:
    entities = [
        {
            "name": "Floor",
            "active": True,
            "tag": "",
            "layer": "Gameplay",
            "components": {
                "Transform": {"enabled": True, "x": 0.0, "y": 220.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                "Collider": {"enabled": True, "shape_type": "box", "width": 320.0, "height": 24.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
            },
        }
    ]
    for index in range(box_count):
        entities.append(
            {
                "name": f"Box_{index}",
                "active": True,
                "tag": "",
                "layer": "Gameplay",
                "components": {
                    "Transform": {"enabled": True, "x": float((index % 5) * 18 - 36), "y": float(20 + (index // 5) * 18), "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                    "RigidBody": {"enabled": True, "body_type": "dynamic", "gravity_scale": 1.0, "velocity_x": 0.0, "velocity_y": 0.0, "is_grounded": False, "collision_detection_mode": "continuous" if ccd else "discrete"},
                    "Collider": {"enabled": True, "shape_type": "box", "width": 16.0, "height": 16.0, "density": 1.0, "friction": 0.3, "restitution": 0.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
                },
            }
        )
    return {
        "name": "Physics Benchmark",
        "entities": entities,
        "rules": [],
        "feature_metadata": {"physics_2d": {"backend": "box2d"}},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark de step para backend de fisica.")
    parser.add_argument("--backend", default="box2d", choices=["legacy_aabb", "box2d"])
    parser.add_argument("--boxes", type=int, default=20)
    parser.add_argument("--frames", type=int, default=180)
    parser.add_argument("--ccd", action="store_true")
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        project_root = root / "PhysicsBench"
        scene_path = project_root / "levels" / "bench_scene.json"
        scene_path.parent.mkdir(parents=True, exist_ok=True)
        payload = build_benchmark_scene(max(1, int(args.boxes)), bool(args.ccd))
        payload["feature_metadata"]["physics_2d"]["backend"] = args.backend
        scene_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        api = EngineAPI(project_root=project_root.as_posix(), global_state_dir=(root / "global_state").as_posix())
        try:
            api.load_level(scene_path.as_posix())
            api.play()
            start = time.perf_counter()
            api.step(int(args.frames))
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            game = api.game
            world = game.world if game is not None else None
            backend_name = (
                game._resolve_physics_backend_name(world)
                if game is not None and world is not None and hasattr(game, "_resolve_physics_backend_name")
                else args.backend
            )
            backend = getattr(game, "_physics_backends", {}).get(backend_name) if game is not None else None
            backend_metrics = backend.get_step_metrics() if backend is not None and hasattr(backend, "get_step_metrics") else {}
            report = {
                "backend": args.backend,
                "frames": int(args.frames),
                "boxes": int(args.boxes),
                "ccd": bool(args.ccd),
                "total_step_ms": round(elapsed_ms, 4),
                "avg_step_ms": round(elapsed_ms / max(1, int(args.frames)), 6),
                "backend_metrics": backend_metrics,
            }
            if args.output:
                Path(args.output).write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps(report, indent=2))
        finally:
            api.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
