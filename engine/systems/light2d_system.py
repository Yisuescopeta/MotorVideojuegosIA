"""
engine/systems/light2d_system.py - Renderiza luces 2D puntuales con blend modes y sombras
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pyray as rl
from engine.components.camera2d import Camera2D
from engine.components.light2d import Light2D
from engine.components.light_occluder_2d import LightOccluder2D
from engine.components.point_light_2d import PointLight2D
from engine.components.transform import Transform

if TYPE_CHECKING:
    from engine.ecs.world import World


class Light2DSystem:
    """Renderiza entidades Light2D y PointLight2D como circulos concentricos con falloff."""

    CIRCLE_STEPS: int = 8

    def render(self, world: World, camera: rl.Camera2D | None = None) -> None:
        backend_ready = bool(hasattr(rl, "is_window_ready") and rl.is_window_ready())
        if not backend_ready:
            return

        if camera is None:
            camera = self._build_camera_from_world(world)

        lights: list[tuple[int, object]] = []

        for entity in world.get_entities_with(Transform, Light2D):
            light = entity.get_component(Light2D)
            transform = entity.get_component(Transform)
            if light is None or transform is None or not light.enabled or not transform.enabled:
                continue
            lights.append((light.z_index, (entity, light, transform)))

        for entity in world.get_entities_with(Transform, PointLight2D):
            light = entity.get_component(PointLight2D)
            transform = entity.get_component(Transform)
            if light is None or transform is None or not light.enabled or not transform.enabled:
                continue
            lights.append((0, (entity, light, transform)))

        lights.sort(key=lambda item: item[0])

        occluders: list[tuple[LightOccluder2D, Transform]] = []
        for entity in world.get_entities_with(Transform, LightOccluder2D):
            occluder = entity.get_component(LightOccluder2D)
            obj_transform = entity.get_component(Transform)
            if occluder and occluder.enabled and obj_transform:
                occluders.append((occluder, obj_transform))

        for _, (entity, light, transform) in lights:
            self._render_light(light, transform, camera, occluders)

    def _render_light(
        self,
        light: Light2D | PointLight2D,
        transform: Transform,
        camera: rl.Camera2D,
        occluders: list[tuple[LightOccluder2D, Transform]],
    ) -> None:
        if camera is not None:
            rl.begin_mode_2d(camera)

        # Extract light params
        if isinstance(light, PointLight2D):
            r_val, g_val, b_val, a_val = light.color
            radius = light.radius
            energy = light.energy
            shadow_enabled = light.shadow_enabled
            shadow_color = light.shadow_color
            # PointLight2D uses blend_mode as string, default "add"
            blend = rl.BLEND_ADDITIVE
            falloff_type = "quadratic"
        else:
            r_val = light.color_r
            g_val = light.color_g
            b_val = light.color_b
            a_val = light.color_a
            radius = light.radius
            energy = light.energy
            shadow_enabled = False
            shadow_color = (0, 0, 0, 100)
            blend = rl.BLEND_ADDITIVE
            if light.blend_mode == Light2D.BLEND_MULTIPLIED and hasattr(rl, "BLEND_MULTIPLIED"):
                blend = rl.BLEND_MULTIPLIED
            falloff_type = light.falloff_type

        light_x = int(transform.x)
        light_y = int(transform.y)

        # Render shadows first
        if shadow_enabled and occluders:
            self._render_shadows(
                float(light_x), float(light_y), radius, shadow_color, occluders
            )

        if self._is_point_occluded(float(light_x), float(light_y), occluders):
            if camera is not None:
                rl.end_mode_2d()
            return

        rl.begin_blend_mode(blend)

        base_alpha = min(255, max(0, int(a_val * energy)))

        for step in range(self.CIRCLE_STEPS, 0, -1):
            ratio = step / self.CIRCLE_STEPS
            step_radius = radius * ratio

            if falloff_type == Light2D.FALLOFF_CONSTANT:
                alpha_ratio = 1.0
            elif falloff_type == Light2D.FALLOFF_LINEAR:
                alpha_ratio = ratio
            else:  # quadratic
                alpha_ratio = ratio * ratio

            alpha = max(1, int(base_alpha * alpha_ratio))
            color = rl.Color(r_val, g_val, b_val, alpha)
            rl.draw_circle(
                light_x,
                light_y,
                step_radius,
                color,
            )

        rl.end_blend_mode()
        if camera is not None:
            rl.end_mode_2d()

    def _render_shadows(
        self,
        light_x: float,
        light_y: float,
        radius: float,
        shadow_color: tuple[int, int, int, int],
        occluders: list[tuple[LightOccluder2D, Transform]],
    ) -> None:
        sr, sg, sb, sa = shadow_color
        if sa <= 0:
            return
        shadow_col = rl.Color(sr, sg, sb, sa)

        for occluder, obj_transform in occluders:
            bounds = occluder.get_bounds(obj_transform.x, obj_transform.y)
            ox1, oy1, ox2, oy2 = bounds

            volume = self._compute_shadow_volume(
                light_x, light_y, (ox1, oy1, ox2, oy2), radius
            )
            if not volume:
                continue

            # Draw shadow volume as triangle fan
            for i in range(len(volume) - 2):
                rl.draw_triangle(volume[0], volume[i + 1], volume[i + 2], shadow_col)

    @staticmethod
    def _compute_shadow_volume(
        light_x: float,
        light_y: float,
        occluder_aabb: tuple[float, float, float, float],
        radius: float,
    ) -> list[rl.Vector2]:
        """Compute shadow polygon vertices for a box occluder.

        Returns a list of Vector2 that forms a triangle fan from the near edge
        to the projected far points.
        """
        ox1, oy1, ox2, oy2 = occluder_aabb

        # 4 corners
        corners = [
            (ox1, oy1),
            (ox2, oy1),
            (ox2, oy2),
            (ox1, oy2),
        ]

        # Find which edges face the light
        # Simple approach: project each corner away from light by radius
        projected: list[rl.Vector2] = []
        for cx, cy in corners:
            dx = cx - light_x
            dy = cy - light_y
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < 0.001:
                continue
            ndx = dx / dist
            ndy = dy / dist
            projected.append(rl.Vector2(cx + ndx * radius, cy + ndy * radius))

        if len(projected) < 2:
            return []

        # Build triangle fan: start from first near corner, alternate
        # Actually we return the polygon vertices forming the shadow wedge
        # The caller draws triangle fan from volume[0]
        result: list[rl.Vector2] = []
        # Near edge (facing light): the two corners closest to light -> not needed for fan
        # Instead just return projected points as a fan from one base corner
        # For box occluder, use the two visible edges

        # Simpler approach: project all 4 corners, use them as a fan
        # Start with first corner, then all projected points
        first_corner = rl.Vector2(corners[0][0], corners[0][1])
        result.append(first_corner)
        result.extend(projected)

        return result

    @staticmethod
    def _is_point_occluded(
        px: float,
        py: float,
        occluders: list[tuple[LightOccluder2D, Transform]],
    ) -> bool:
        for occluder, obj_transform in occluders:
            bounds = occluder.get_bounds(obj_transform.x, obj_transform.y)
            if bounds[0] <= px <= bounds[2] and bounds[1] <= py <= bounds[3]:
                return True
        return False

    @staticmethod
    def _build_camera_from_world(world: World) -> rl.Camera2D | None:
        primary_entity = None
        for entity in world.get_entities_with(Transform, Camera2D):
            camera_component = entity.get_component(Camera2D)
            if camera_component is not None and camera_component.enabled and camera_component.is_primary:
                primary_entity = entity
                break
        if primary_entity is None:
            return None

        transform = primary_entity.get_component(Transform)
        camera_component = primary_entity.get_component(Camera2D)
        if transform is None or camera_component is None:
            return None

        camera = rl.Camera2D()
        camera.target = rl.Vector2(transform.x, transform.y)
        camera.offset = rl.Vector2(camera_component.offset_x, camera_component.offset_y)
        camera.rotation = camera_component.rotation
        camera.zoom = camera_component.zoom
        return camera
