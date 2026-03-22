from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


class RenderOrder2D(Component):
    """Orden de renderizado 2D desacoplado de gameplay layers."""

    MIN_ORDER_IN_LAYER: int = -32768
    MAX_ORDER_IN_LAYER: int = 32767

    def __init__(self, sorting_layer: str = "Default", order_in_layer: int = 0) -> None:
        self.enabled: bool = True
        self.sorting_layer: str = sorting_layer
        self.order_in_layer: int = self._clamp_order(order_in_layer)

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "sorting_layer": self.sorting_layer,
            "order_in_layer": self.order_in_layer,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RenderOrder2D":
        component = cls(
            sorting_layer=data.get("sorting_layer", "Default"),
            order_in_layer=cls._clamp_order(int(data.get("order_in_layer", 0))),
        )
        component.enabled = data.get("enabled", True)
        return component

    @classmethod
    def _clamp_order(cls, value: int) -> int:
        return max(cls.MIN_ORDER_IN_LAYER, min(cls.MAX_ORDER_IN_LAYER, int(value)))
