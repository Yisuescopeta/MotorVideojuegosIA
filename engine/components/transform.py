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

    def _global_state(self) -> tuple[tuple[int, float, float, float, float, float], int]:
        parent_state: tuple[int, float, float, float, float, float] | None = None
        parent_revision = -1
        if self.parent is not None:
            parent_state, parent_revision = self.parent._global_state()
        key = (
            id(self.parent) if self.parent is not None else None,
            parent_revision,
            self.local_x,
            self.local_y,
            self.local_rotation,
            self.local_scale_x,
            self.local_scale_y,
        )
        if key != getattr(self, "_global_cache_key", None):
            if parent_state is None:
                state = (
                    0,
                    self.local_x,
                    self.local_y,
                    self.local_rotation,
                    self.local_scale_x,
                    self.local_scale_y,
                )
            else:
                state = (
                    parent_state[0] + 1,
                    parent_state[1] + self.local_x,
                    parent_state[2] + self.local_y,
                    parent_state[3] + self.local_rotation,
                    parent_state[4] * self.local_scale_x,
                    parent_state[5] * self.local_scale_y,
                )
            self._global_cache_key = key
            self._global_cache_state = state
            self._global_cache_revision = getattr(self, "_global_cache_revision", 0) + 1
        return self._global_cache_state, self._global_cache_revision

    @property
    def depth(self) -> int:
        return self._global_state()[0][0]

    @property
    def x(self) -> float:
        return self._global_state()[0][1]

    @x.setter
    def x(self, value: float) -> None:
        if self.parent:
            self.local_x = value - self.parent.x
        else:
            self.local_x = value

    @property
    def y(self) -> float:
        return self._global_state()[0][2]

    @y.setter
    def y(self, value: float) -> None:
        if self.parent:
            self.local_y = value - self.parent.y
        else:
            self.local_y = value

    @property
    def rotation(self) -> float:
        return self._global_state()[0][3]

    @rotation.setter
    def rotation(self, value: float) -> None:
        if self.parent:
            self.local_rotation = value - self.parent.rotation
        else:
            self.local_rotation = value

    @property
    def scale_x(self) -> float:
        return self._global_state()[0][4]

    @scale_x.setter
    def scale_x(self, value: float) -> None:
        if self.parent:
            parent_scale = self.parent.scale_x
            self.local_scale_x = value / parent_scale if parent_scale != 0 else value
        else:
            self.local_scale_x = value

    @property
    def scale_y(self) -> float:
        return self._global_state()[0][5]

    @scale_y.setter
    def scale_y(self, value: float) -> None:
        if self.parent:
            parent_scale = self.parent.scale_y
            self.local_scale_y = value / parent_scale if parent_scale != 0 else value
        else:
            self.local_scale_y = value

    def set_parent(self, parent: Optional["Transform"]) -> None:
        """Asigna un nuevo padre manteniendo la transformaciÃ³n global."""
        global_state, _revision = self._global_state()
        _, global_x, global_y, global_rotation, global_scale_x, global_scale_y = global_state

        if self.parent and self in self.parent.children:
            self.parent.children.remove(self)

        self.parent = parent
        if self.parent is not None and self not in self.parent.children:
            self.parent.children.append(self)

        if parent is None:
            self.local_x = global_x
            self.local_y = global_y
            self.local_rotation = global_rotation
            self.local_scale_x = global_scale_x
            self.local_scale_y = global_scale_y
        else:
            parent_state, _parent_revision = parent._global_state()
            self.local_x = global_x - parent_state[1]
            self.local_y = global_y - parent_state[2]
            self.local_rotation = global_rotation - parent_state[3]
            self.local_scale_x = global_scale_x / parent_state[4] if parent_state[4] != 0 else global_scale_x
            self.local_scale_y = global_scale_y / parent_state[5] if parent_state[5] != 0 else global_scale_y

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
