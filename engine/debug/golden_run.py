from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from engine.debug.state_fingerprint import world_fingerprint


def capture_headless_run(
    game: Any,
    *,
    frames: int,
    dt: float = 1.0 / 60.0,
    capture_every: int = 1,
    include_initial_state: bool = True,
    float_precision: int = 6,
) -> dict[str, Any]:
    if game.world is None:
        raise RuntimeError("No active world to capture")
    if frames < 0:
        raise ValueError("frames must be >= 0")
    if capture_every <= 0:
        raise ValueError("capture_every must be > 0")

    captures: list[dict[str, Any]] = []
    if include_initial_state:
        captures.append(
            world_fingerprint(
                game.world,
                frame=game.time.frame_count,
                time=game.time.total_time,
                float_precision=float_precision,
            )
        )

    for index in range(frames):
        game.step_frame(dt)
        should_capture = ((index + 1) % capture_every) == 0 or index == frames - 1
        if should_capture and game.world is not None:
            captures.append(
                world_fingerprint(
                    game.world,
                    frame=game.time.frame_count,
                    time=game.time.total_time,
                    float_precision=float_precision,
                )
            )

    final_capture = captures[-1] if captures else world_fingerprint(
        game.world,
        frame=game.time.frame_count,
        time=game.time.total_time,
        float_precision=float_precision,
    )
    return {
        "seed": getattr(game, "random_seed", None),
        "frames_requested": frames,
        "dt": round(dt, float_precision),
        "capture_every": capture_every,
        "captures": captures,
        "final_world_hash": final_capture["world_hash"],
        "final_frame": final_capture["frame"],
        "final_time": final_capture["time"],
    }


def write_golden_run(report: dict[str, Any], path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return destination


def load_golden_run(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def compare_golden_runs(expected: dict[str, Any], actual: dict[str, Any]) -> list[str]:
    mismatches: list[str] = []
    if expected.get("final_world_hash") != actual.get("final_world_hash"):
        mismatches.append(
            f"final_world_hash: expected {expected.get('final_world_hash')} got {actual.get('final_world_hash')}"
        )
    if expected.get("final_frame") != actual.get("final_frame"):
        mismatches.append(f"final_frame: expected {expected.get('final_frame')} got {actual.get('final_frame')}")
    expected_captures = expected.get("captures", [])
    actual_captures = actual.get("captures", [])
    if len(expected_captures) != len(actual_captures):
        mismatches.append(f"capture_count: expected {len(expected_captures)} got {len(actual_captures)}")
        return mismatches
    for index, (expected_capture, actual_capture) in enumerate(zip(expected_captures, actual_captures)):
        if expected_capture.get("world_hash") != actual_capture.get("world_hash"):
            mismatches.append(
                f"capture[{index}].world_hash: expected {expected_capture.get('world_hash')} got {actual_capture.get('world_hash')}"
            )
        if expected_capture.get("frame") != actual_capture.get("frame"):
            mismatches.append(
                f"capture[{index}].frame: expected {expected_capture.get('frame')} got {actual_capture.get('frame')}"
            )
    return mismatches
