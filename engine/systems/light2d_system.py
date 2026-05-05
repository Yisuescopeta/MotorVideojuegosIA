"""
engine/systems/light2d_system.py - Renderiza luces 2D puntuales con blend modes
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pyray as rl
from engine.components.camera2d import Camera2D
from engine.components.light2d import Light2D
from engine.components.transform import Transform
from engine.ecs.entity import Entity

if TYPE_CHECKING:
    from engine.ecs.world import World


class Light2DSystem:
    """Renderiza entidades Light2D como circulos concentricos con falloff."""

    CIRCLE_STEPS: int = 8

    def render(self, world: World, camera: rl.Camera2D | None = None) -> None:
        backend_ready = bool(hasattr(rl, "is_window_ready") and rl.is_window_ready())
        if not backend_ready:
            return

        if camera is None:
            camera = self._build_camera_from_world(world)

        entities = world.get_entities_with(Transform, Light2D)
        lights: list[tuple[int, Entity, Light2D, Transform]] = []
        for entity in entities:
            light = entity.get_component(Light2D)
            transform = entity.get_component(Transform)
            if light is None or transform is None or not light.enabled or not transform.enabled:
                continue
            lights.append((light.z_index, entity, light, transform))

        lights.sort(key=lambda item: item[0])

        for _, _entity, light, transform in lights:
            self._render_light(light, transform, camera)

    def _render_light(self, light: Light2D, transform: Transform, camera: rl.Camera2D | None) -> None:
        if camera is not None:
            rl.begin_mode_2d(camera)

        blend = rl.BLEND_ADDITIVE
        if light.blend_mode == Light2D.BLEND_MULTIPLIED and hasattr(rl, "BLEND_MULTIPLIED"):
            blend = rl.BLEND_MULTIPLIED
        rl.begin_blend_mode(blend)

        base_alpha = min(255, max(0, int(light.color_a * light.energy)))
        r_val = light.color_r
        g_val = light.color_g
        b_val = light.color_b

        for step in range(self.CIRCLE_STEPS, 0, -1):
            ratio = step / self.CIRCLE_STEPS
            step_radius = light.radius * ratio

            if light.falloff_type == Light2D.FALLOFF_CONSTANT:
                alpha_ratio = 1.0
            elif light.falloff_type == Light2D.FALLOFF_LINEAR:
                alpha_ratio = ratio
            else:  # quadratic
                alpha_ratio = ratio * ratio

            alpha = max(1, int(base_alpha * alpha_ratio))
            color = rl.Color(r_val, g_val, b_val, alpha)
            rl.draw_circle(
                int(transform.x),
                int(transform.y),
                step_radius,
                color,
            )

        rl.end_blend_mode()
        if camera is not None:
            rl.end_mode_2d()

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
