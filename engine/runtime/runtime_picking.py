"""Runtime render queries and 2D picking for scripts."""

from __future__ import annotations

from typing import Any, Callable

from engine.runtime.runtime_input import NULL_RUNTIME_INPUT


class NullRuntimeRenderQueryService:
    def get_visual_bounds(self, entity: Any) -> dict[str, float] | None:
        return None

    def get_entity_visual_bounds(self, entity_name: str) -> dict[str, float] | None:
        return None

    def pick_sprite_at_world(self, x: float, y: float, layer: str | None = None) -> Any | None:
        return None

    def pick_sprite_at_mouse(self, layer: str | None = None) -> Any | None:
        return None


class RuntimeRenderQueryService:
    """Delegates visual bounds and picking to the active RenderSystem."""

    def __init__(
        self,
        *,
        get_world: Callable[[], Any | None],
        get_render_system: Callable[[], Any | None],
        input_service: Any = NULL_RUNTIME_INPUT,
    ) -> None:
        self._get_world = get_world
        self._get_render_system = get_render_system
        self._input_service = input_service

    def get_visual_bounds(self, entity: Any) -> dict[str, float] | None:
        render_system = self._get_render_system()
        if render_system is None or not hasattr(render_system, "get_visual_bounds"):
            return None
        return render_system.get_visual_bounds(entity)

    def get_entity_visual_bounds(self, entity_name: str) -> dict[str, float] | None:
        world = self._get_world()
        if world is None or not hasattr(world, "get_entity_by_name"):
            return None
        entity = world.get_entity_by_name(str(entity_name))
        if entity is None:
            return None
        return self.get_visual_bounds(entity)

    def pick_sprite_at_world(self, x: float, y: float, layer: str | None = None) -> Any | None:
        world = self._get_world()
        render_system = self._get_render_system()
        if world is None or render_system is None or not hasattr(render_system, "pick_sprite_at_world"):
            return None
        return render_system.pick_sprite_at_world(world, x, y, layer=layer)

    def pick_sprite_at_mouse(self, layer: str | None = None) -> Any | None:
        mouse_world = getattr(self._input_service, "mouse_world", (0.0, 0.0))
        return self.pick_sprite_at_world(float(mouse_world[0]), float(mouse_world[1]), layer=layer)


NULL_RUNTIME_RENDER_QUERIES = NullRuntimeRenderQueryService()
