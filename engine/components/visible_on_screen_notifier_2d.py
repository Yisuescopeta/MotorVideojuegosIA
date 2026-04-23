"""
engine/components/visible_on_screen_notifier_2d.py - Deteccion de visibilidad en pantalla.

Emite senales: screen_entered, screen_exited.
"""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


class VisibleOnScreenNotifier2D(Component):
    """Detecta si la entidad entra o sale del viewport de la camara."""

    def __init__(
        self,
        rect_x: float = 0.0,
        rect_y: float = 0.0,
        rect_width: float = 32.0,
        rect_height: float = 32.0,
        show_rect: bool = False,
    ) -> None:
        self.enabled: bool = True
        self.rect_x: float = float(rect_x)
        self.rect_y: float = float(rect_y)
        self.rect_width: float = float(rect_width)
        self.rect_height: float = float(rect_height)
        self.show_rect: bool = bool(show_rect)

        # Estado de runtime (no serializable)
        self._is_on_screen: bool = False

    @property
    def is_on_screen(self) -> bool:
        return self._is_on_screen

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "rect_x": self.rect_x,
            "rect_y": self.rect_y,
            "rect_width": self.rect_width,
            "rect_height": self.rect_height,
            "show_rect": self.show_rect,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VisibleOnScreenNotifier2D":
        component = cls(
            rect_x=data.get("rect_x", 0.0),
            rect_y=data.get("rect_y", 0.0),
            rect_width=data.get("rect_width", 32.0),
            rect_height=data.get("rect_height", 32.0),
            show_rect=data.get("show_rect", False),
        )
        component.enabled = data.get("enabled", True)
        return component


class VisibleOnScreenEnabler2D(VisibleOnScreenNotifier2D):
    """Hereda del Notifier y activa/desactiva automaticamente una entidad objetivo."""

    def __init__(
        self,
        rect_x: float = 0.0,
        rect_y: float = 0.0,
        rect_width: float = 32.0,
        rect_height: float = 32.0,
        show_rect: bool = False,
        enable_mode: str = "inherit",
        enable_node_path: str = "",
    ) -> None:
        super().__init__(rect_x, rect_y, rect_width, rect_height, show_rect)
        self.enable_mode: str = str(enable_mode or "inherit").strip().lower()
        self.enable_node_path: str = str(enable_node_path or "").strip()

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["enable_mode"] = self.enable_mode
        data["enable_node_path"] = self.enable_node_path
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VisibleOnScreenEnabler2D":
        component = cls(
            rect_x=data.get("rect_x", 0.0),
            rect_y=data.get("rect_y", 0.0),
            rect_width=data.get("rect_width", 32.0),
            rect_height=data.get("rect_height", 32.0),
            show_rect=data.get("show_rect", False),
            enable_mode=data.get("enable_mode", "inherit"),
            enable_node_path=data.get("enable_node_path", ""),
        )
        component.enabled = data.get("enabled", True)
        return component
