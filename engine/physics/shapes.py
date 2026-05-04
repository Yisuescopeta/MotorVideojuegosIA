"""
engine/physics/shapes.py — ShapeInstance y ShapeFactory para narrow-phase de colisiones.

Factoría de shapes geométricos que reemplaza el uso directo de collider.get_bounds()
en narrow-phase. Cada shape sabe calcular su AABB y testear intersección contra otras shapes.

Shapes:
    ShapeInstance (ABC)    — clase base abstracta
    AABBShape              — rectángulo alineado a ejes (box)
    CircleShape            — círculo
    CapsuleShape           — cápsula vertical (segmento + radio)
    PolygonShape           — polígono convexo (SAT)

Fábrica:
    ShapeFactory.build(collider, x, y) → ShapeInstance
"""

from __future__ import annotations

from abc import ABC, abstractmethod

AABB = tuple[float, float, float, float]


class ShapeInstance(ABC):
    """Forma geométrica para narrow-phase de colisiones."""

    @abstractmethod
    def get_aabb(self) -> AABB:
        """Devuelve (left, top, right, bottom)."""
        ...

    @abstractmethod
    def intersects_shape(self, other: ShapeInstance) -> bool:
        """True si esta shape intersecta con other."""
        ...


class AABBShape(ShapeInstance):
    """Rectángulo alineado a ejes."""

    def __init__(self, cx: float, cy: float, half_w: float, half_h: float):
        self.cx = cx
        self.cy = cy
        self.half_w = half_w
        self.half_h = half_h

    def get_aabb(self) -> AABB:
        return (
            self.cx - self.half_w,
            self.cy - self.half_h,
            self.cx + self.half_w,
            self.cy + self.half_h,
        )

    def intersects_shape(self, other: ShapeInstance) -> bool:
        if isinstance(other, AABBShape):
            return self._intersects_aabb(other)
        return other.intersects_shape(self)

    def _intersects_aabb(self, other: AABBShape) -> bool:
        return (
            abs(self.cx - other.cx) < self.half_w + other.half_w
            and abs(self.cy - other.cy) < self.half_h + other.half_h
        )


class CircleShape(ShapeInstance):
    """Círculo."""

    def __init__(self, cx: float, cy: float, radius: float):
        self.cx = cx
        self.cy = cy
        self.radius = radius

    def get_aabb(self) -> AABB:
        return (
            self.cx - self.radius,
            self.cy - self.radius,
            self.cx + self.radius,
            self.cy + self.radius,
        )

    def intersects_shape(self, other: ShapeInstance) -> bool:
        if isinstance(other, CircleShape):
            return self._intersects_circle(other)
        if isinstance(other, AABBShape):
            return self._intersects_aabb(other)
        if isinstance(other, CapsuleShape):
            return other.intersects_shape(self)
        return other.intersects_shape(self)

    def _intersects_circle(self, other: CircleShape) -> bool:
        dx = self.cx - other.cx
        dy = self.cy - other.cy
        r = self.radius + other.radius
        return dx * dx + dy * dy <= r * r

    def _intersects_aabb(self, aabb: AABBShape) -> bool:
        closest_x = max(aabb.cx - aabb.half_w, min(self.cx, aabb.cx + aabb.half_w))
        closest_y = max(aabb.cy - aabb.half_h, min(self.cy, aabb.cy + aabb.half_h))
        dx = self.cx - closest_x
        dy = self.cy - closest_y
        return dx * dx + dy * dy <= self.radius * self.radius


class CapsuleShape(ShapeInstance):
    """Cápsula vertical: segmento central + radio en extremos."""

    def __init__(self, cx: float, cy: float, radius: float, height: float):
        self.cx = cx
        self.cy = cy
        self.radius = radius
        self.height = height

    def get_aabb(self) -> AABB:
        half_total = self.radius + self.height / 2
        return (
            self.cx - self.radius,
            self.cy - half_total,
            self.cx + self.radius,
            self.cy + half_total,
        )

    def intersects_shape(self, other: ShapeInstance) -> bool:
        if isinstance(other, AABBShape):
            return self._intersects_aabb(other)
        if isinstance(other, CircleShape):
            return self._intersects_circle(other)
        if isinstance(other, CapsuleShape):
            return self._intersects_capsule(other)
        return other.intersects_shape(self)

    def _segment_ends(self) -> tuple[float, float]:
        """Devuelve (top_y, bottom_y) del segmento central."""
        half_h = self.height / 2
        return (self.cy - half_h, self.cy + half_h)

    def _closest_point_on_segment(self, px: float, py: float) -> tuple[float, float]:
        """Punto más cercano en el segmento a (px, py)."""
        top_y, bottom_y = self._segment_ends()
        closest_y = max(top_y, min(py, bottom_y))
        return (self.cx, closest_y)

    def _intersects_aabb(self, aabb: AABBShape) -> bool:
        closest_cx, closest_cy = self._closest_point_on_segment(aabb.cx, aabb.cy)
        closest_ax = max(aabb.cx - aabb.half_w, min(closest_cx, aabb.cx + aabb.half_w))
        closest_ay = max(aabb.cy - aabb.half_h, min(closest_cy, aabb.cy + aabb.half_h))
        dx = closest_cx - closest_ax
        dy = closest_cy - closest_ay
        return dx * dx + dy * dy <= self.radius * self.radius

    def _intersects_circle(self, circle: CircleShape) -> bool:
        cx, cy = self._closest_point_on_segment(circle.cx, circle.cy)
        dx = cx - circle.cx
        dy = cy - circle.cy
        r = self.radius + circle.radius
        return dx * dx + dy * dy <= r * r

    def _intersects_capsule(self, other: CapsuleShape) -> bool:
        a_top, a_bot = self._segment_ends()
        b_top, b_bot = other._segment_ends()
        r = self.radius + other.radius
        dx = self.cx - other.cx

        overlap_top = max(a_top, b_top)
        overlap_bot = min(a_bot, b_bot)
        if overlap_top <= overlap_bot:
            return abs(dx) <= r

        d1_sq = dx * dx + (a_top - b_bot) * (a_top - b_bot)
        d2_sq = dx * dx + (a_bot - b_top) * (a_bot - b_top)
        return min(d1_sq, d2_sq) <= r * r


class PolygonShape(ShapeInstance):
    """Polígono convexo."""

    def __init__(self, vertices: list[tuple[float, float]]):
        self.vertices = vertices

    def get_aabb(self) -> AABB:
        if not self.vertices:
            return (0.0, 0.0, 0.0, 0.0)
        xs = [v[0] for v in self.vertices]
        ys = [v[1] for v in self.vertices]
        return (min(xs), min(ys), max(xs), max(ys))

    def intersects_shape(self, other: ShapeInstance) -> bool:
        if isinstance(other, AABBShape):
            return self._intersects_aabb(other)
        if isinstance(other, CircleShape):
            return other.intersects_shape(self)
        return self._aabb_overlap(self.get_aabb(), other.get_aabb())

    def _intersects_aabb(self, aabb: AABBShape) -> bool:
        return self._sat_intersects(aabb)

    def _sat_intersects(self, aabb: AABBShape) -> bool:
        """Separating Axis Theorem entre polígono y AABB."""
        aabb_verts = [
            (aabb.cx - aabb.half_w, aabb.cy - aabb.half_h),
            (aabb.cx + aabb.half_w, aabb.cy - aabb.half_h),
            (aabb.cx + aabb.half_w, aabb.cy + aabb.half_h),
            (aabb.cx - aabb.half_w, aabb.cy + aabb.half_h),
        ]

        n = len(self.vertices)
        axes: list[tuple[float, float]] = []
        for i in range(n):
            v1 = self.vertices[i]
            v2 = self.vertices[(i + 1) % n]
            edge = (v2[0] - v1[0], v2[1] - v1[1])
            normal = (-edge[1], edge[0])
            length = (normal[0] ** 2 + normal[1] ** 2) ** 0.5
            if length > 1e-6:
                axes.append((normal[0] / length, normal[1] / length))

        axes.extend([(1.0, 0.0), (0.0, 1.0)])

        for axis in axes:
            ax, ay = axis
            poly_min = float("inf")
            poly_max = float("-inf")
            for v in self.vertices:
                proj = v[0] * ax + v[1] * ay
                poly_min = min(poly_min, proj)
                poly_max = max(poly_max, proj)

            aabb_min = float("inf")
            aabb_max = float("-inf")
            for v in aabb_verts:
                proj = v[0] * ax + v[1] * ay
                aabb_min = min(aabb_min, proj)
                aabb_max = max(aabb_max, proj)

            if poly_max < aabb_min or aabb_max < poly_min:
                return False

        return True

    @staticmethod
    def _aabb_overlap(a: AABB, b: AABB) -> bool:
        return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]


class ShapeFactory:
    """Crea ShapeInstance a partir de un Collider."""

    @staticmethod
    def build(collider, x: float, y: float) -> ShapeInstance:
        """Construye una ShapeInstance desde un Collider en (x, y)."""
        from engine.components.collider import Collider  # noqa: PLC0415

        cx = x + collider.offset_x
        cy = y + collider.offset_y

        shape_type = str(collider.shape_type or "box")

        if shape_type == "circle":
            return CircleShape(cx, cy, collider.radius)
        if shape_type == "capsule":
            return CapsuleShape(cx, cy, collider.radius, collider.capsule_height)
        if shape_type == "polygon" and collider.points:
            world_verts = [(cx + p[0], cy + p[1]) for p in collider.points]
            return PolygonShape(world_verts)
        return AABBShape(cx, cy, collider.width / 2, collider.height / 2)
