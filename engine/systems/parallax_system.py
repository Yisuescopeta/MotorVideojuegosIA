"""
engine/systems/parallax_system.py - Sistema de desplazamiento parallax.

Aplica movimiento relativo a la camara para entidades con ParallaxLayer.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from engine.components.camera2d import Camera2D
from engine.components.parallax_layer import ParallaxLayer
from engine.components.transform import Transform

if TYPE_CHECKING:
    from engine.ecs.entity import Entity
    from engine.ecs.world import World


class ParallaxSystem:
    """Sistema que aplica desplazamiento parallax a entidades con ParallaxLayer."""

    def __init__(self) -> None:
        self._camera_origin_x: float = 0.0
        self._camera_origin_y: float = 0.0
        self._origin_captured: bool = False

    def on_play(self, world: Optional["World"]) -> None:
        """Captura posiciones de descanso al iniciar el juego."""
        if world is None:
            return
        self._capture_camera_origin(world)
        for entity in self._iter_parallax_entities(world):
            transform = entity.get_component(Transform)
            parallax = entity.get_component(ParallaxLayer)
            if transform is None or parallax is None:
                continue
            parallax._rest_x = transform.x
            parallax._rest_y = transform.y
            parallax._autoscroll_accum_x = 0.0
            parallax._autoscroll_accum_y = 0.0
            parallax._rest_captured = True

    def _capture_camera_origin(self, world: "World") -> None:
        """Registra la posicion inicial de la camara primaria."""
        self._camera_origin_x = 0.0
        self._camera_origin_y = 0.0
        self._origin_captured = False
        for entity in world.get_entities_with(Transform, Camera2D):
            camera = entity.get_component(Camera2D)
            if camera is not None and camera.enabled and camera.is_primary:
                transform = entity.get_component(Transform)
                if transform is not None:
                    self._camera_origin_x = transform.x
                    self._camera_origin_y = transform.y
                    self._origin_captured = True
                break

    def on_stop(self, world: Optional["World"]) -> None:
        """Restaura posiciones de descanso y limpia estado interno."""
        if world is not None:
            for entity in self._iter_parallax_entities(world):
                parallax = entity.get_component(ParallaxLayer)
                transform = entity.get_component(Transform)
                if parallax is not None and transform is not None and parallax._rest_captured:
                    transform.x = parallax._rest_x
                    transform.y = parallax._rest_y
                    parallax._rest_captured = False
        self._camera_origin_x = 0.0
        self._camera_origin_y = 0.0
        self._origin_captured = False

    def update(self, world: Optional["World"], dt: float) -> None:
        """Aplica desplazamiento parallax cada frame."""
        if world is None or not self._origin_captured:
            return

        camera_x, camera_y = self._get_primary_camera_position(world)
        if camera_x is None or camera_y is None:
            return

        camera_delta_x = camera_x - self._camera_origin_x
        camera_delta_y = camera_y - self._camera_origin_y

        entities = []
        for entity in self._iter_parallax_entities(world):
            transform = entity.get_component(Transform)
            parallax = entity.get_component(ParallaxLayer)
            if transform is not None and parallax is not None:
                entities.append((transform.depth, entity.id, entity, transform, parallax))
        entities.sort(key=lambda x: x[0])

        for _, _, _entity, transform, parallax in entities:
            if not parallax._rest_captured:
                parallax._rest_x = transform.x
                parallax._rest_y = transform.y
                parallax._autoscroll_accum_x = 0.0
                parallax._autoscroll_accum_y = 0.0
                parallax._rest_captured = True

            if not parallax.enabled:
                transform.x = parallax._rest_x
                transform.y = parallax._rest_y
                continue

            if not parallax.follow_viewport:
                transform.x = parallax._rest_x
                transform.y = parallax._rest_y
                continue

            parallax._autoscroll_accum_x += parallax.autoscroll_x * dt
            parallax._autoscroll_accum_y += parallax.autoscroll_y * dt

            new_x = (
                parallax._rest_x
                + camera_delta_x * parallax.motion_scale_x
                + parallax.scroll_offset_x
                + parallax._autoscroll_accum_x
            )
            new_y = (
                parallax._rest_y
                + camera_delta_y * parallax.motion_scale_y
                + parallax.scroll_offset_y
                + parallax._autoscroll_accum_y
            )

            if parallax.mirror_x > 0:
                offset_x = new_x - parallax._rest_x
                wrapped_offset_x = self._wrap_mirror(offset_x, parallax.mirror_x)
                new_x = parallax._rest_x + wrapped_offset_x
            if parallax.mirror_y > 0:
                offset_y = new_y - parallax._rest_y
                wrapped_offset_y = self._wrap_mirror(offset_y, parallax.mirror_y)
                new_y = parallax._rest_y + wrapped_offset_y

            transform.x = new_x
            transform.y = new_y

    @staticmethod
    def _iter_parallax_entities(world: "World") -> list["Entity"]:
        """Itera entidades con Transform + ParallaxLayer incluyendo deshabilitadas."""
        result: list["Entity"] = []
        for entity in world.get_entities_with(Transform):
            if entity.has_component(ParallaxLayer):
                result.append(entity)
        return result

    def _get_primary_camera_position(self, world: "World") -> tuple[Optional[float], Optional[float]]:
        for entity in world.get_entities_with(Transform, Camera2D):
            camera = entity.get_component(Camera2D)
            if camera is not None and camera.enabled and camera.is_primary:
                transform = entity.get_component(Transform)
                if transform is not None:
                    return transform.x, transform.y
        return None, None

    @staticmethod
    def _wrap_mirror(value: float, mirror: float) -> float:
        if mirror <= 0:
            return value
        return value % mirror
