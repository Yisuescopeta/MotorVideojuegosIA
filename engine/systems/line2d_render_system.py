"""
engine/systems/line2d_render_system.py - Sistema de renderizado para lineas 2D.

Renderiza entidades con Transform + Line2D usando pyray. Soporta grosor,
joint modes (sharp/round), lineas cerradas y cap_mode round.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pyray as rl
from engine.components.line2d import Line2D
from engine.components.transform import Transform

if TYPE_CHECKING:
    from engine.ecs.world import World


class Line2DRenderSystem:
    """Renderiza entidades con componente Line2D."""

    def render(self, world: "World") -> None:
        for entity in world.get_entities_with(Transform, Line2D):
            transform = entity.get_component(Transform)
            line = entity.get_component(Line2D)
            if transform is None or line is None or not line.enabled:
                continue
            if line.point_count < 2:
                continue

            self._draw_line2d(transform, line)

    def _draw_line2d(self, transform: Transform, line: Line2D) -> None:
        color = rl.Color(*line.color)
        world_points = self._transform_points(line.points, transform)

        if line.point_count < 2:
            return

        pairs = self._build_pairs(world_points, line.closed)

        if line.width <= 1.0:
            self._draw_thin_line(world_points, color, line.closed)
        else:
            self._draw_thick_line(pairs, world_points, line.width, color, line.joint_mode, line.closed, line.cap_mode)

    @staticmethod
    def _transform_points(
        points: list[list[float]], transform: Transform
    ) -> list[tuple[float, float]]:
        cos_r = math.cos(transform.rotation)
        sin_r = math.sin(transform.rotation)
        sx = transform.scale_x
        sy = transform.scale_y

        result: list[tuple[float, float]] = []
        for pt in points:
            wx = pt[0] * sx
            wy = pt[1] * sy
            rx = wx * cos_r - wy * sin_r
            ry = wx * sin_r + wy * cos_r
            result.append((transform.x + rx, transform.y + ry))
        return result

    @staticmethod
    def _build_pairs(
        points: list[tuple[float, float]], closed: bool
    ) -> list[tuple[tuple[float, float], tuple[float, float]]]:
        pairs: list[tuple[tuple[float, float], tuple[float, float]]] = []
        for i in range(len(points) - 1):
            pairs.append((points[i], points[i + 1]))
        if closed and len(points) >= 2:
            pairs.append((points[-1], points[0]))
        return pairs

    def _draw_thin_line(
        self, points: list[tuple[float, float]], color: rl.Color, closed: bool
    ) -> None:
        for i in range(len(points) - 1):
            p0, p1 = points[i], points[i + 1]
            rl.draw_line(int(p0[0]), int(p0[1]), int(p1[0]), int(p1[1]), color)
        if closed and len(points) >= 2:
            p0, p1 = points[-1], points[0]
            rl.draw_line(int(p0[0]), int(p0[1]), int(p1[0]), int(p1[1]), color)

    def _draw_thick_line(
        self,
        pairs: list[tuple[tuple[float, float], tuple[float, float]]],
        points: list[tuple[float, float]],
        width: float,
        color: rl.Color,
        joint_mode: str,
        closed: bool,
        cap_mode: str,
    ) -> None:
        half_w = width * 0.5

        for a, b in pairs:
            self._draw_thick_segment(a, b, half_w, color)

        if joint_mode == "round":
            for pt in points:
                rl.draw_circle(int(pt[0]), int(pt[1]), half_w, color)
        elif joint_mode == "sharp":
            self._draw_sharp_joints(pairs, points, half_w, color, closed)

        if cap_mode == "round" and not closed:
            if len(points) >= 1:
                rl.draw_circle(int(points[0][0]), int(points[0][1]), half_w, color)
                rl.draw_circle(int(points[-1][0]), int(points[-1][1]), half_w, color)

    @staticmethod
    def _draw_thick_segment(
        a: tuple[float, float],
        b: tuple[float, float],
        half_w: float,
        color: rl.Color,
    ) -> None:
        dx = b[0] - a[0]
        dy = b[1] - a[1]
        length = math.sqrt(dx * dx + dy * dy)
        if length < 0.001:
            rl.draw_circle(int(a[0]), int(a[1]), half_w, color)
            return

        nx = -dy / length * half_w
        ny = dx / length * half_w

        rl.draw_triangle(
            rl.Vector2(a[0] + nx, a[1] + ny),
            rl.Vector2(b[0] + nx, b[1] + ny),
            rl.Vector2(a[0] - nx, a[1] - ny),
            color,
        )
        rl.draw_triangle(
            rl.Vector2(b[0] + nx, b[1] + ny),
            rl.Vector2(b[0] - nx, b[1] - ny),
            rl.Vector2(a[0] - nx, a[1] - ny),
            color,
        )

    @staticmethod
    def _draw_sharp_joints(
        pairs: list[tuple[tuple[float, float], tuple[float, float]]],
        points: list[tuple[float, float]],
        half_w: float,
        color: rl.Color,
        closed: bool,
    ) -> None:
        n = len(points)
        for i, pt in enumerate(points):
            if not closed and (i == 0 or i == n - 1):
                continue
            prev_i = i - 1 if i > 0 else n - 1
            next_i = i + 1 if i < n - 1 else 0

            pa = points[prev_i]
            pb = pt
            pc = points[next_i]

            d1x = pb[0] - pa[0]
            d1y = pb[1] - pa[1]
            len1 = math.sqrt(d1x * d1x + d1y * d1y)
            if len1 < 0.001:
                continue
            n1x = -d1y / len1 * half_w
            n1y = d1x / len1 * half_w

            d2x = pc[0] - pb[0]
            d2y = pc[1] - pb[1]
            len2 = math.sqrt(d2x * d2x + d2y * d2y)
            if len2 < 0.001:
                continue
            n2x = -d2y / len2 * half_w
            n2y = d2x / len2 * half_w

            corner1 = (pb[0] + n1x, pb[1] + n1y)
            corner2 = (pb[0] + n2x, pb[1] + n2y)
            corner3 = (pb[0] - n1x, pb[1] - n1y)
            corner4 = (pb[0] - n2x, pb[1] - n2y)

            rl.draw_triangle(
                rl.Vector2(pb[0], pb[1]),
                rl.Vector2(corner1[0], corner1[1]),
                rl.Vector2(corner2[0], corner2[1]),
                color,
            )
            rl.draw_triangle(
                rl.Vector2(pb[0], pb[1]),
                rl.Vector2(corner3[0], corner3[1]),
                rl.Vector2(corner4[0], corner4[1]),
                color,
            )
