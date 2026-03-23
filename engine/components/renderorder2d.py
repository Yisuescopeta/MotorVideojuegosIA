from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


class RenderOrder2D(Component):
    """Orden de renderizado 2D desacoplado de gameplay layers."""

    MIN_ORDER_IN_LAYER: int = -32768
    MAX_ORDER_IN_LAYER: int = 32767
    DEFAULT_RENDER_PASS: str = "World"
    ALLOWED_RENDER_PASSES: tuple[str, ...] = ("World", "Overlay", "Debug")

    def __init__(self, sorting_layer: str = "Default", order_in_layer: int = 0, render_pass: str = DEFAULT_RENDER_PASS) -> None:
        self.enabled: bool = True
        self.sorting_layer: str = sorting_layer
        self.order_in_layer: int = self._clamp_order(order_in_layer)
        self.render_pass: str = self._normalize_render_pass(render_pass)

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "sorting_layer": self.sorting_layer,
            "order_in_layer": self.order_in_layer,
            "render_pass": self.render_pass,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RenderOrder2D":
        component = cls(
            sorting_layer=data.get("sorting_layer", "Default"),
            order_in_layer=cls._clamp_order(int(data.get("order_in_layer", 0))),
            render_pass=data.get("render_pass", cls.DEFAULT_RENDER_PASS),
        )
        component.enabled = data.get("enabled", True)
        return component

    @classmethod
    def _clamp_order(cls, value: int) -> int:
        return max(cls.MIN_ORDER_IN_LAYER, min(cls.MAX_ORDER_IN_LAYER, int(value)))

    @classmethod
    def _normalize_render_pass(cls, value: str) -> str:
        candidate = str(value or cls.DEFAULT_RENDER_PASS).strip() or cls.DEFAULT_RENDER_PASS
        if candidate not in cls.ALLOWED_RENDER_PASSES:
            return cls.DEFAULT_RENDER_PASS
        return candidate
