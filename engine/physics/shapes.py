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
from typing import Optional

from engine.physics.contact_data import ContactManifold2D, ContactPoint2D

AABB = tuple[float, float, float, float]


class ShapeInstance(ABC):
    """Forma geométrica para narrow-phase de colisiones."""

    @abstractmethod
    def get_aabb(self) -> AABB:
        """Devuelve (left, top, right, bottom)."""
        ...

    @abstractmethod
    def collide_shape(self, other: ShapeInstance) -> Optional[ContactManifold2D]:
        """Calcula manifold de contacto. None si no hay colisión."""
        ...

    def intersects_shape(self, other: ShapeInstance) -> bool:
        """True si esta shape intersecta con other. Wrapper de collide_shape."""
        return self.collide_shape(other) is not None


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

    def collide_shape(self, other: ShapeInstance) -> Optional[ContactManifold2D]:
        if isinstance(other, AABBShape):
            return self._collide_aabb(other)
        return other.collide_shape(self)

    def _collide_aabb(self, other: AABBShape) -> Optional[ContactManifold2D]:
        overlap_left = (self.cx + self.half_w) - (other.cx - other.half_w)
        overlap_right = (other.cx + other.half_w) - (self.cx - self.half_w)
        overlap_top = (self.cy + self.half_h) - (other.cy - other.half_h)
        overlap_bottom = (other.cy + other.half_h) - (self.cy - self.half_h)

        if overlap_left <= 0 or overlap_right <= 0 or overlap_top <= 0 or overlap_bottom <= 0:
            return None

        overlap_x = min(overlap_left, overlap_right)
        overlap_y = min(overlap_top, overlap_bottom)

        if overlap_x < overlap_y:
            nx = -1.0 if self.cx < other.cx else 1.0
            ny = 0.0
            depth = overlap_x
        else:
            nx = 0.0
            ny = -1.0 if self.cy < other.cy else 1.0
            depth = overlap_y

        contact_x = (max(self.cx - self.half_w, other.cx - other.half_w)
                     + min(self.cx + self.half_w, other.cx + other.half_w)) / 2
        contact_y = (max(self.cy - self.half_h, other.cy - other.half_h)
                     + min(self.cy + self.half_h, other.cy + other.half_h)) / 2

        cp = ContactPoint2D(point_x=contact_x, point_y=contact_y, normal_x=nx, normal_y=ny, depth=depth)
        return ContactManifold2D(
            entity_a_id=0, entity_b_id=0, entity_a_name="", entity_b_name="",
            normal_x=nx, normal_y=ny, depth=depth,
            relative_velocity_x=0.0, relative_velocity_y=0.0,
            contact_count=1, contacts=[cp], is_trigger=False,
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

    def collide_shape(self, other: ShapeInstance) -> Optional[ContactManifold2D]:
        if isinstance(other, CircleShape):
            return self._collide_circle(other)
        if isinstance(other, AABBShape):
            return self._collide_aabb(other)
        if isinstance(other, PolygonShape):
            return self._collide_polygon(other)
        if isinstance(other, CapsuleShape):
            return other.collide_shape(self)
        return other.collide_shape(self)

    def _collide_circle(self, other: CircleShape) -> Optional[ContactManifold2D]:
        dx = other.cx - self.cx
        dy = other.cy - self.cy
        dist_sq = dx * dx + dy * dy
        min_dist = self.radius + other.radius
        if dist_sq > min_dist * min_dist:
            return None
        dist = dist_sq ** 0.5
        depth = min_dist - dist
        if dist < 0.0001:
            nx, ny = 0.0, -1.0
        else:
            nx, ny = dx / dist, dy / dist
        contact_x = self.cx + nx * (self.radius - depth / 2)
        contact_y = self.cy + ny * (self.radius - depth / 2)
        cp = ContactPoint2D(point_x=contact_x, point_y=contact_y, normal_x=nx, normal_y=ny, depth=depth)
        return ContactManifold2D(
            entity_a_id=0, entity_b_id=0, entity_a_name="", entity_b_name="",
            normal_x=nx, normal_y=ny, depth=depth,
            relative_velocity_x=0.0, relative_velocity_y=0.0,
            contact_count=1, contacts=[cp], is_trigger=False,
        )

    def _collide_aabb(self, aabb: AABBShape) -> Optional[ContactManifold2D]:
        closest_x = max(aabb.cx - aabb.half_w, min(self.cx, aabb.cx + aabb.half_w))
        closest_y = max(aabb.cy - aabb.half_h, min(self.cy, aabb.cy + aabb.half_h))
        dx = self.cx - closest_x
        dy = self.cy - closest_y
        dist_sq = dx * dx + dy * dy
        if dist_sq > self.radius * self.radius:
            return None
        dist = dist_sq ** 0.5
        depth = self.radius - dist
        if dist < 0.0001:
            nx, ny = 0.0, -1.0
        else:
            nx, ny = dx / dist, dy / dist
        contact_x = self.cx - nx * (self.radius - depth / 2)
        contact_y = self.cy - ny * (self.radius - depth / 2)
        cp = ContactPoint2D(point_x=contact_x, point_y=contact_y, normal_x=nx, normal_y=ny, depth=depth)
        return ContactManifold2D(
            entity_a_id=0, entity_b_id=0, entity_a_name="", entity_b_name="",
            normal_x=nx, normal_y=ny, depth=depth,
            relative_velocity_x=0.0, relative_velocity_y=0.0,
            contact_count=1, contacts=[cp], is_trigger=False,
        )

    def _collide_polygon(self, poly: PolygonShape) -> Optional[ContactManifold2D]:
        """Circle vs Polygon: punto más cercano en polígono al centro del círculo."""
        if poly._point_inside(self.cx, self.cy):
            cp = ContactPoint2D(point_x=self.cx, point_y=self.cy, normal_x=0.0, normal_y=-1.0, depth=self.radius)
            return ContactManifold2D(
                entity_a_id=0, entity_b_id=0, entity_a_name="", entity_b_name="",
                normal_x=0.0, normal_y=-1.0, depth=self.radius,
                relative_velocity_x=0.0, relative_velocity_y=0.0,
                contact_count=1, contacts=[cp], is_trigger=False,
            )
        # Punto más cercano en aristas del polígono
        closest_dist_sq = float("inf")
        closest_px = 0.0
        closest_py = 0.0
        n = len(poly.vertices)
        for i in range(n):
            v1 = poly.vertices[i]
            v2 = poly.vertices[(i + 1) % n]
            ex = v2[0] - v1[0]
            ey = v2[1] - v1[1]
            if abs(ex) < 1e-6 and abs(ey) < 1e-6:
                d_sq = (self.cx - v1[0]) ** 2 + (self.cy - v1[1]) ** 2
                px, py = v1[0], v1[1]
            else:
                t = ((self.cx - v1[0]) * ex + (self.cy - v1[1]) * ey) / (ex * ex + ey * ey)
                t = max(0.0, min(1.0, t))
                px = v1[0] + t * ex
                py = v1[1] + t * ey
                d_sq = (self.cx - px) ** 2 + (self.cy - py) ** 2
            if d_sq < closest_dist_sq:
                closest_dist_sq = d_sq
                closest_px = px
                closest_py = py
        if closest_dist_sq > self.radius * self.radius:
            return None
        dist = closest_dist_sq ** 0.5
        depth = self.radius - dist
        if dist < 0.0001:
            nx, ny = 0.0, -1.0
        else:
            nx = (self.cx - closest_px) / dist
            ny = (self.cy - closest_py) / dist
        cp = ContactPoint2D(point_x=closest_px, point_y=closest_py, normal_x=nx, normal_y=ny, depth=depth)
        return ContactManifold2D(
            entity_a_id=0, entity_b_id=0, entity_a_name="", entity_b_name="",
            normal_x=nx, normal_y=ny, depth=depth,
            relative_velocity_x=0.0, relative_velocity_y=0.0,
            contact_count=1, contacts=[cp], is_trigger=False,
        )


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

    def collide_shape(self, other: ShapeInstance) -> Optional[ContactManifold2D]:
        # TODO: implementar manifold real para capsule
        if self.intersects_shape(other):
            cp = ContactPoint2D(point_x=self.cx, point_y=self.cy, normal_x=0.0, normal_y=-1.0, depth=self.radius)
            return ContactManifold2D(
                entity_a_id=0, entity_b_id=0, entity_a_name="", entity_b_name="",
                normal_x=0.0, normal_y=-1.0, depth=self.radius,
                relative_velocity_x=0.0, relative_velocity_y=0.0,
                contact_count=1, contacts=[cp], is_trigger=False,
            )
        return None

    def intersects_shape(self, other: ShapeInstance) -> bool:
        if isinstance(other, AABBShape):
            return self._intersects_aabb(other)
        if isinstance(other, CircleShape):
            return self._intersects_circle(other)
        if isinstance(other, CapsuleShape):
            return self._intersects_capsule(other)
        if isinstance(other, PolygonShape):
            return self._intersects_polygon(other)
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

    def _intersects_polygon(self, poly: PolygonShape) -> bool:
        """Capsule vs Polygon: extremos como círculos + muestreo del segmento."""
        from engine.physics.shapes import CircleShape  # noqa: PLC0415

        top_y, bottom_y = self._segment_ends()
        top_circle = CircleShape(self.cx, top_y, self.radius)
        if top_circle._intersects_polygon(poly):
            return True
        bot_circle = CircleShape(self.cx, bottom_y, self.radius)
        if bot_circle._intersects_polygon(poly):
            return True
        steps = 4
        for i in range(steps + 1):
            t = i / steps
            py = top_y + t * (bottom_y - top_y)
            if poly._point_inside(self.cx, py):
                return True
        return False


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

    def collide_shape(self, other: ShapeInstance) -> Optional[ContactManifold2D]:
        # TODO: implementar manifold real para polygon
        if isinstance(other, AABBShape):
            if self._sat_intersects_aabb(other):
                cp = ContactPoint2D(point_x=self._centroid_x(), point_y=self._centroid_y(), normal_x=0.0, normal_y=-1.0, depth=1.0)
                return ContactManifold2D(
                    entity_a_id=0, entity_b_id=0, entity_a_name="", entity_b_name="",
                    normal_x=0.0, normal_y=-1.0, depth=1.0,
                    relative_velocity_x=0.0, relative_velocity_y=0.0,
                    contact_count=1, contacts=[cp], is_trigger=False,
                )
            return None
        if isinstance(other, CircleShape):
            return other.collide_shape(self)
        if isinstance(other, PolygonShape):
            if self._sat_intersects_polygon(other):
                cp = ContactPoint2D(point_x=self._centroid_x(), point_y=self._centroid_y(), normal_x=0.0, normal_y=-1.0, depth=1.0)
                return ContactManifold2D(
                    entity_a_id=0, entity_b_id=0, entity_a_name="", entity_b_name="",
                    normal_x=0.0, normal_y=-1.0, depth=1.0,
                    relative_velocity_x=0.0, relative_velocity_y=0.0,
                    contact_count=1, contacts=[cp], is_trigger=False,
                )
            return None
        if isinstance(other, CapsuleShape):
            return other.collide_shape(self)
        # Fallback: AABB overlap test
        if self._aabb_overlap_fallback(self.get_aabb(), other.get_aabb()):
            cp = ContactPoint2D(point_x=self._centroid_x(), point_y=self._centroid_y(), normal_x=0.0, normal_y=-1.0, depth=1.0)
            return ContactManifold2D(
                entity_a_id=0, entity_b_id=0, entity_a_name="", entity_b_name="",
                normal_x=0.0, normal_y=-1.0, depth=1.0,
                relative_velocity_x=0.0, relative_velocity_y=0.0,
                contact_count=1, contacts=[cp], is_trigger=False,
            )
        return None

    def intersects_shape(self, other: ShapeInstance) -> bool:
        if isinstance(other, AABBShape):
            return self._sat_intersects_aabb(other)
        if isinstance(other, CircleShape):
            return other.intersects_shape(self)
        if isinstance(other, PolygonShape):
            return self._sat_intersects_polygon(other)
        if isinstance(other, CapsuleShape):
            return other.intersects_shape(self)
        return self._aabb_overlap_fallback(self.get_aabb(), other.get_aabb())

    def _centroid_x(self) -> float:
        if not self.vertices:
            return 0.0
        return sum(v[0] for v in self.vertices) / len(self.vertices)

    def _centroid_y(self) -> float:
        if not self.vertices:
            return 0.0
        return sum(v[1] for v in self.vertices) / len(self.vertices)

    def _sat_intersects_aabb(self, aabb: AABBShape) -> bool:
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

    def _sat_intersects_polygon(self, other: PolygonShape) -> bool:
        """SAT entre dos polígonos convexos."""
        return self._sat_test(self.vertices, other.vertices)

    @staticmethod
    def _sat_test(verts_a: list, verts_b: list) -> bool:
        """Separating Axis Theorem generalizado."""
        n = len(verts_a)
        m = len(verts_b)
        axes: list[tuple[float, float]] = []
        for i in range(n):
            v1 = verts_a[i]
            v2 = verts_a[(i + 1) % n]
            edge = (v2[0] - v1[0], v2[1] - v1[1])
            normal = (-edge[1], edge[0])
            length = (normal[0] ** 2 + normal[1] ** 2) ** 0.5
            if length > 1e-6:
                axes.append((normal[0] / length, normal[1] / length))
        for i in range(m):
            v1 = verts_b[i]
            v2 = verts_b[(i + 1) % m]
            edge = (v2[0] - v1[0], v2[1] - v1[1])
            normal = (-edge[1], edge[0])
            length = (normal[0] ** 2 + normal[1] ** 2) ** 0.5
            if length > 1e-6:
                axes.append((normal[0] / length, normal[1] / length))

        for ax, ay in axes:
            min_a = float("inf")
            max_a = float("-inf")
            for v in verts_a:
                proj = v[0] * ax + v[1] * ay
                min_a = min(min_a, proj)
                max_a = max(max_a, proj)
            min_b = float("inf")
            max_b = float("-inf")
            for v in verts_b:
                proj = v[0] * ax + v[1] * ay
                min_b = min(min_b, proj)
                max_b = max(max_b, proj)
            if max_a < min_b or max_b < min_a:
                return False
        return True

    def _point_inside(self, px: float, py: float) -> bool:
        """Ray casting: punto dentro de polígono."""
        n = len(self.vertices)
        inside = False
        j = n - 1
        for i in range(n):
            vi = self.vertices[i]
            vj = self.vertices[j]
            if ((vi[1] > py) != (vj[1] > py)) and (
                px < (vj[0] - vi[0]) * (py - vi[1]) / (vj[1] - vi[1]) + vi[0]
            ):
                inside = not inside
            j = i
        return inside

    @staticmethod
    def _aabb_overlap(a: AABB, b: AABB) -> bool:
        return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]

    @staticmethod
    def _aabb_overlap_fallback(a: AABB, b: AABB) -> bool:
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
