"""
engine/components/transform.py - Componente de posiciÃ³n y transformaciÃ³n
"""

from __future__ import annotations

from typing import Any, Optional

from engine.ecs.component import Component


class Transform(Component):
    """Componente que define la transformaciÃ³n 2D local/global."""

    def __init__(
        self,
        x: float = 0.0,
        y: float = 0.0,
        rotation: float = 0.0,
        scale_x: float = 1.0,
        scale_y: float = 1.0,
    ) -> None:
        self.enabled: bool = True
        self.local_x: float = x
        self.local_y: float = y
        self.local_rotation: float = rotation
        self.local_scale_x: float = scale_x
        self.local_scale_y: float = scale_y
        self.parent: Optional["Transform"] = None
        self.children: list["Transform"] = []

    @property
    def depth(self) -> int:
        depth = 0
        current = self.parent
        while current is not None:
            depth += 1
            current = current.parent
        return depth

    @property
    def x(self) -> float:
        if self.parent:
            return self.parent.x + self.local_x
        return self.local_x

    @x.setter
    def x(self, value: float) -> None:
        if self.parent:
            self.local_x = value - self.parent.x
        else:
            self.local_x = value

    @property
    def y(self) -> float:
        if self.parent:
            return self.parent.y + self.local_y
        return self.local_y

    @y.setter
    def y(self, value: float) -> None:
        if self.parent:
            self.local_y = value - self.parent.y
        else:
            self.local_y = value

    @property
    def rotation(self) -> float:
        if self.parent:
            return self.parent.rotation + self.local_rotation
        return self.local_rotation

    @rotation.setter
    def rotation(self, value: float) -> None:
        if self.parent:
            self.local_rotation = value - self.parent.rotation
        else:
            self.local_rotation = value

    @property
    def scale_x(self) -> float:
        if self.parent:
            return self.parent.scale_x * self.local_scale_x
        return self.local_scale_x

    @scale_x.setter
    def scale_x(self, value: float) -> None:
        if self.parent:
            parent_scale = self.parent.scale_x
            self.local_scale_x = value / parent_scale if parent_scale != 0 else value
        else:
            self.local_scale_x = value

    @property
    def scale_y(self) -> float:
        if self.parent:
            return self.parent.scale_y * self.local_scale_y
        return self.local_scale_y

    @scale_y.setter
    def scale_y(self, value: float) -> None:
        if self.parent:
            parent_scale = self.parent.scale_y
            self.local_scale_y = value / parent_scale if parent_scale != 0 else value
        else:
            self.local_scale_y = value

    def set_parent(self, parent: Optional["Transform"]) -> None:
        """Asigna un nuevo padre manteniendo la transformaciÃ³n global."""
        global_x, global_y = self.x, self.y
        global_rotation = self.rotation
        global_scale_x = self.scale_x
        global_scale_y = self.scale_y

        if self.parent and self in self.parent.children:
            self.parent.children.remove(self)

        self.parent = parent
        if self.parent is not None and self not in self.parent.children:
            self.parent.children.append(self)

        self.x = global_x
        self.y = global_y
        self.rotation = global_rotation
        self.scale_x = global_scale_x
        self.scale_y = global_scale_y

    def add_child(self, child: "Transform") -> None:
        child.set_parent(self)

    def set_position(self, x: float, y: float) -> None:
        self.x = x
        self.y = y

    def translate(self, dx: float, dy: float) -> None:
        self.x += dx
        self.y += dy

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "x": self.local_x,
            "y": self.local_y,
            "rotation": self.local_rotation,
            "scale_x": self.local_scale_x,
            "scale_y": self.local_scale_y,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Transform":
        component = cls(
            x=data.get("x", 0.0),
            y=data.get("y", 0.0),
            rotation=data.get("rotation", 0.0),
            scale_x=data.get("scale_x", 1.0),
            scale_y=data.get("scale_y", 1.0),
        )
        component.enabled = data.get("enabled", True)
        return component
