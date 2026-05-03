"""engine/resources/curve_2d.py — Curve2D: Bezier curve resource (not a Component)."""

from __future__ import annotations

import math
from typing import Any


class Curve2D:
    """Standalone serializable Bezier curve resource.

    Points: list of dicts with {x, y, in_x, in_y, out_x, out_y}.
    Baked cache for fast sampling along the curve.
    """

    def __init__(self, bake_interval: float = 5.0):
        self._points: list[dict[str, float]] = []
        self.bake_interval: float = max(0.1, float(bake_interval))
        self._baked_points: list[dict[str, float]] = []
        self._baked_distances: list[float] = []
        self._baked_total_length: float = 0.0
        self._dirty: bool = False

    @property
    def point_count(self) -> int:
        return len(self._points)

    def get_points(self) -> list[dict[str, float]]:
        return list(self._points)

    def add_point(
        self,
        position: tuple[float, float],
        in_vec: tuple[float, float] | None = None,
        out_vec: tuple[float, float] | None = None,
        index: int = -1,
    ) -> None:
        pt = {
            "x": float(position[0]),
            "y": float(position[1]),
            "in_x": float(in_vec[0]) if in_vec else 0.0,
            "in_y": float(in_vec[1]) if in_vec else 0.0,
            "out_x": float(out_vec[0]) if out_vec else 0.0,
            "out_y": float(out_vec[1]) if out_vec else 0.0,
        }
        idx = int(index)
        if 0 <= idx < len(self._points):
            self._points.insert(idx, pt)
        else:
            self._points.append(pt)
        self._dirty = True

    def remove_point(self, index: int) -> None:
        if 0 <= index < len(self._points):
            self._points.pop(index)
            self._dirty = True

    def clear_points(self) -> None:
        self._points.clear()
        self._baked_points.clear()
        self._baked_distances.clear()
        self._baked_total_length = 0.0
        self._dirty = False

    def sample(self, idx: int, t: float) -> tuple[float, float]:
        """Cubic Bezier on segment idx at param t (0-1)."""
        n = len(self._points)
        if n == 0:
            return (0.0, 0.0)
        if n == 1:
            p = self._points[0]
            return (p["x"], p["y"])
        idx = max(0, min(idx, n - 2))
        p0 = self._points[idx]
        p1 = self._points[idx + 1]
        cp0x = p0["x"] + p0["out_x"]
        cp0y = p0["y"] + p0["out_y"]
        cp1x = p1["x"] + p1["in_x"]
        cp1y = p1["y"] + p1["in_y"]
        tc = max(0.0, min(1.0, float(t)))
        return _de_casteljau(p0["x"], p0["y"], cp0x, cp0y, cp1x, cp1y, p1["x"], p1["y"], tc)

    def samplef(self, findex: float) -> tuple[float, float]:
        """Float index version: fractional segment + t."""
        n = len(self._points)
        if n == 0:
            return (0.0, 0.0)
        if n == 1:
            p = self._points[0]
            return (p["x"], p["y"])
        seg_count = n - 1
        findex = max(0.0, min(float(seg_count), findex))
        idx = int(findex)
        frac = findex - idx
        if idx >= seg_count:
            idx = seg_count - 1
            frac = 1.0
        return self.sample(idx, frac)

    def _bake(self) -> None:
        if not self._dirty:
            return
        self._baked_points.clear()
        self._baked_distances.clear()
        self._baked_total_length = 0.0

        n = len(self._points)
        if n == 0:
            self._dirty = False
            return
        if n == 1:
            p = self._points[0]
            self._baked_points.append({"x": p["x"], "y": p["y"]})
            self._baked_distances.append(0.0)
            self._dirty = False
            return

        interval = max(0.1, float(self.bake_interval))
        total_est = self._estimate_length()
        if total_est <= 0.0:
            p = self._points[0]
            self._baked_points.append({"x": p["x"], "y": p["y"]})
            self._baked_distances.append(0.0)
            self._dirty = False
            return

        steps = max(2, int(total_est / interval))
        cum = 0.0
        x0, y0 = self._sample_raw(0.0)
        self._baked_points.append({"x": x0, "y": y0})
        self._baked_distances.append(0.0)

        for i in range(1, steps + 1):
            t_scalar = i / steps
            x, y = self._sample_raw(t_scalar)
            seg_len = math.hypot(x - x0, y - y0)
            cum += seg_len
            self._baked_points.append({"x": x, "y": y})
            self._baked_distances.append(cum)
            x0, y0 = x, y

        self._baked_total_length = cum
        self._dirty = False

    def _sample_raw(self, t: float) -> tuple[float, float]:
        """Sample at normalized t [0,1] across all segments."""
        n = len(self._points)
        if n == 0:
            return (0.0, 0.0)
        if n == 1:
            p = self._points[0]
            return (p["x"], p["y"])
        tc = max(0.0, min(1.0, float(t)))
        if tc >= 1.0:
            p = self._points[-1]
            return (p["x"], p["y"])
        if tc <= 0.0:
            p = self._points[0]
            return (p["x"], p["y"])
        segs = n - 1
        seg_float = tc * segs
        seg = int(seg_float)
        local_t = seg_float - seg
        if seg >= segs:
            seg = segs - 1
            local_t = 1.0
        return self.sample(seg, local_t)

    def _estimate_length(self) -> float:
        n = len(self._points)
        if n < 2:
            return 0.0
        total = 0.0
        for i in range(n - 1):
            p0 = self._points[i]
            p1 = self._points[i + 1]
            total += math.hypot(p1["x"] - p0["x"], p1["y"] - p0["y"])
        return total

    def get_baked_points(self) -> list[dict[str, float]]:
        self._bake()
        return list(self._baked_points)

    def get_baked_length(self) -> float:
        self._bake()
        return self._baked_total_length

    def sample_baked(self, offset: float, cubic: bool = False) -> dict[str, float]:
        """Sample along baked points at distance offset. Returns {x, y}."""
        self._bake()
        if not self._baked_points:
            return {"x": 0.0, "y": 0.0}
        if self._baked_total_length <= 1e-9:
            bp = self._baked_points[0]
            return {"x": bp["x"], "y": bp["y"]}

        offset = offset % self._baked_total_length if offset < 0 else offset
        if offset >= self._baked_total_length:
            offset = self._baked_total_length - 1e-9

        for i in range(1, len(self._baked_distances)):
            if self._baked_distances[i] >= offset:
                seg_start = self._baked_distances[i - 1]
                seg_len = self._baked_distances[i] - seg_start
                if seg_len < 1e-9:
                    bp = self._baked_points[i]
                    return {"x": bp["x"], "y": bp["y"]}
                t = (offset - seg_start) / seg_len
                if cubic and len(self._baked_points) >= 4:
                    i0 = max(0, i - 2)
                    i1 = max(0, i - 1)
                    i2 = i
                    i3 = min(len(self._baked_points) - 1, i + 1)
                    x = _catmull_rom(
                        self._baked_points[i0]["x"],
                        self._baked_points[i1]["x"],
                        self._baked_points[i2]["x"],
                        self._baked_points[i3]["x"],
                        t,
                    )
                    y = _catmull_rom(
                        self._baked_points[i0]["y"],
                        self._baked_points[i1]["y"],
                        self._baked_points[i2]["y"],
                        self._baked_points[i3]["y"],
                        t,
                    )
                    return {"x": x, "y": y}
                p0 = self._baked_points[i - 1]
                p1 = self._baked_points[i]
                return {
                    "x": p0["x"] + (p1["x"] - p0["x"]) * t,
                    "y": p0["y"] + (p1["y"] - p0["y"]) * t,
                }

        bp = self._baked_points[-1]
        return {"x": bp["x"], "y": bp["y"]}

    def get_closest_point(self, to_point: tuple[float, float]) -> dict[str, float]:
        self._bake()
        tx, ty = float(to_point[0]), float(to_point[1])
        best = {"x": 0.0, "y": 0.0}
        best_dist = float("inf")
        for bp in self._baked_points:
            d = (bp["x"] - tx) ** 2 + (bp["y"] - ty) ** 2
            if d < best_dist:
                best_dist = d
                best = {"x": bp["x"], "y": bp["y"]}
        if not self._baked_points:
            return {"x": tx, "y": ty}
        return best

    def get_closest_offset(self, to_point: tuple[float, float]) -> float:
        self._bake()
        tx, ty = float(to_point[0]), float(to_point[1])
        best_idx = 0
        best_dist = float("inf")
        for i, bp in enumerate(self._baked_points):
            d = (bp["x"] - tx) ** 2 + (bp["y"] - ty) ** 2
            if d < best_dist:
                best_dist = d
                best_idx = i
        if best_idx < len(self._baked_distances):
            return self._baked_distances[best_idx]
        return 0.0

    def get_forward_vector(self, offset: float) -> dict[str, float]:
        """Get the forward (tangent) vector at a given distance offset. Returns {x, y}."""
        self._bake()
        if len(self._baked_points) < 2:
            return {"x": 1.0, "y": 0.0}
        if self._baked_total_length <= 1e-9:
            return {"x": 1.0, "y": 0.0}

        offset = offset % self._baked_total_length if offset < 0 else offset
        offset = max(0.0, min(self._baked_total_length - 1e-9, offset))

        for i in range(1, len(self._baked_distances)):
            if self._baked_distances[i] >= offset:
                p0 = self._baked_points[i - 1]
                p1 = self._baked_points[i]
                dx = p1["x"] - p0["x"]
                dy = p1["y"] - p0["y"]
                mag = math.hypot(dx, dy)
                if mag < 1e-9:
                    return {"x": 1.0, "y": 0.0}
                return {"x": dx / mag, "y": dy / mag}

        n = len(self._baked_points)
        p0 = self._baked_points[n - 2]
        p1 = self._baked_points[n - 1]
        dx = p1["x"] - p0["x"]
        dy = p1["y"] - p0["y"]
        mag = math.hypot(dx, dy)
        if mag < 1e-9:
            return {"x": 1.0, "y": 0.0}
        return {"x": dx / mag, "y": dy / mag}

    def to_dict(self) -> dict[str, Any]:
        return {
            "points": [dict(p) for p in self._points],
            "bake_interval": self.bake_interval,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Curve2D":
        curve = cls(bake_interval=data.get("bake_interval", 5.0))
        raw = data.get("points", []) or []
        if isinstance(raw, list):
            for pt_data in raw:
                if isinstance(pt_data, dict):
                    curve._points.append({
                        "x": float(pt_data.get("x", 0.0)),
                        "y": float(pt_data.get("y", 0.0)),
                        "in_x": float(pt_data.get("in_x", 0.0)),
                        "in_y": float(pt_data.get("in_y", 0.0)),
                        "out_x": float(pt_data.get("out_x", 0.0)),
                        "out_y": float(pt_data.get("out_y", 0.0)),
                    })
        curve._dirty = True
        return curve

    def __repr__(self) -> str:
        return f"Curve2D(points={self.point_count}, length={self.get_baked_length():.1f})"


def _de_casteljau(
    p0x, p0y, p1x, p1y, p2x, p2y, p3x, p3y, t
) -> tuple[float, float]:
    mt = 1.0 - t
    q0x = mt * p0x + t * p1x
    q0y = mt * p0y + t * p1y
    q1x = mt * p1x + t * p2x
    q1y = mt * p1y + t * p2y
    q2x = mt * p2x + t * p3x
    q2y = mt * p2y + t * p3y
    r0x = mt * q0x + t * q1x
    r0y = mt * q0y + t * q1y
    r1x = mt * q1x + t * q2x
    r1y = mt * q1y + t * q2y
    sx = mt * r0x + t * r1x
    sy = mt * r0y + t * r1y
    return (sx, sy)


def _catmull_rom(p0: float, p1: float, p2: float, p3: float, t: float) -> float:
    t2 = t * t
    t3 = t2 * t
    return 0.5 * (
        (2.0 * p1)
        + (-p0 + p2) * t
        + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * t2
        + (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * t3
    )
