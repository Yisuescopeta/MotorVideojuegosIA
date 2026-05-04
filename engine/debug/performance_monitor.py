"""
engine/debug/performance_monitor.py - Godot-style performance monitoring.
"""

from __future__ import annotations

from typing import Any


class PerformanceMonitor:
    """Godot-style performance monitoring."""

    def __init__(self) -> None:
        self.fps: float = 0.0
        self.frame_time: float = 0.0  # ms
        self.physics_time: float = 0.0  # ms
        self.render_time: float = 0.0  # ms
        self.process_time: float = 0.0  # ms
        self.entities_count: int = 0
        self.draw_calls: int = 0
        self.memory_usage: int = 0  # bytes

        self._frame_times: list[float] = []  # rolling buffer for FPS
        self._max_samples: int = 60

    def record_frame(
        self,
        delta_time: float,
        physics_time: float,
        render_time: float,
        entities: int,
        draw_calls: int,
    ) -> None:
        self.frame_time = delta_time * 1000.0
        self.physics_time = physics_time * 1000.0
        self.render_time = render_time * 1000.0
        self.process_time = max(0.0, self.frame_time - self.physics_time - self.render_time)
        self.entities_count = entities
        self.draw_calls = draw_calls

        self._frame_times.append(delta_time)
        if len(self._frame_times) > self._max_samples:
            self._frame_times.pop(0)
        avg = sum(self._frame_times) / len(self._frame_times)
        self.fps = 1.0 / avg if avg > 0 else 0.0

    def get_report(self) -> dict[str, Any]:
        return {
            "fps": round(self.fps, 1),
            "frame_time_ms": round(self.frame_time, 2),
            "physics_time_ms": round(self.physics_time, 2),
            "render_time_ms": round(self.render_time, 2),
            "process_time_ms": round(self.process_time, 2),
            "entities": self.entities_count,
            "draw_calls": self.draw_calls,
        }
