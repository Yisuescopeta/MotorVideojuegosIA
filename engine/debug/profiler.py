from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

PROFILE_REPORT_VERSION = 1


@dataclass
class ProfilerAccumulator:
    frame_count: int = 0
    total_time_ms: float = 0.0
    min_time_ms: float = 0.0
    max_time_ms: float = 0.0

    def add(self, value_ms: float) -> None:
        numeric = float(value_ms)
        if self.frame_count == 0:
            self.min_time_ms = numeric
            self.max_time_ms = numeric
        else:
            self.min_time_ms = min(self.min_time_ms, numeric)
            self.max_time_ms = max(self.max_time_ms, numeric)
        self.total_time_ms += numeric
        self.frame_count += 1

    def to_dict(self) -> dict[str, float]:
        avg = self.total_time_ms / self.frame_count if self.frame_count else 0.0
        return {
            "avg_ms": avg,
            "min_ms": self.min_time_ms if self.frame_count else 0.0,
            "max_ms": self.max_time_ms if self.frame_count else 0.0,
            "total_ms": self.total_time_ms,
        }


@dataclass
class EngineProfiler:
    run_label: str = "default"
    systems: dict[str, ProfilerAccumulator] = field(default_factory=dict)
    counters_totals: dict[str, float] = field(default_factory=dict)
    counters_max: dict[str, float] = field(default_factory=dict)
    last_frame: dict[str, Any] = field(default_factory=dict)
    frames: int = 0

    def begin_run(self, label: str = "default", run_label: str | None = None) -> None:
        resolved_label = run_label if run_label is not None else label
        self.run_label = str(resolved_label or "default")
        self.systems = {}
        self.counters_totals = {}
        self.counters_max = {}
        self.last_frame = {}
        self.frames = 0

    def record_frame(
        self,
        *,
        timings_ms: dict[str, float],
        counters: dict[str, int],
        memory: dict[str, float],
        mode: str,
        frame_index: int,
        backend: str,
        backend_metrics: dict[str, Any],
    ) -> None:
        self.frames += 1
        for name, value in timings_ms.items():
            self.systems.setdefault(name, ProfilerAccumulator()).add(float(value))
        numeric_counters = {str(name): float(value) for name, value in {**counters, **memory}.items()}
        for name, value in numeric_counters.items():
            self.counters_totals[name] = self.counters_totals.get(name, 0.0) + value
            self.counters_max[name] = max(self.counters_max.get(name, value), value)
        self.last_frame = {
            "frame": int(frame_index),
            "mode": str(mode),
            "backend": str(backend),
            "timings_ms": {key: float(value) for key, value in timings_ms.items()},
            "counters": {key: int(value) for key, value in counters.items()},
            "memory": {key: float(value) for key, value in memory.items()},
            "backend_metrics": copy.deepcopy(backend_metrics),
        }

    def to_report(self) -> dict[str, Any]:
        counters_avg = {
            name: (value / self.frames if self.frames else 0.0)
            for name, value in self.counters_totals.items()
        }
        return {
            "profile_version": PROFILE_REPORT_VERSION,
            "run_label": self.run_label,
            "frames": self.frames,
            "systems": {
                name: accumulator.to_dict()
                for name, accumulator in sorted(self.systems.items())
            },
            "counters": {
                "avg": counters_avg,
                "max": dict(sorted(self.counters_max.items())),
            },
            "last_frame": copy.deepcopy(self.last_frame),
        }
