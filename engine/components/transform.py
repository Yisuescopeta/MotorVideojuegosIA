"""
engine/components/transform.py - Componente de posicion y transformacion
"""

from __future__ import annotations

from typing import Any, Optional

from engine.ecs.component import Component


class _TransformChildren(list["Transform"]):
    """Lista de hijos sin duplicados para mantener la jerarquia consistente."""

    def append(self, item: "Transform") -> None:
        if item not in self:
            super().append(item)

    def extend(self, items: list["Transform"]) -> None:
        for item in items:
            self.append(item)

    def insert(self, index: int, item: "Transform") -> None:
        if item not in self:
            super().insert(index, item)


class Transform(Component):
    """Componente que define la transformacion 2D local/global."""

    def __init__(
        self,
        x: float = 0.0,
        y: float = 0.0,
        rotation: float = 0.0,
        scale_x: float = 1.0,
        scale_y: float = 1.0,
    ) -> None:
        object.__setattr__(self, "enabled", True)
        object.__setattr__(self, "_local_x", x)
        object.__setattr__(self, "_local_y", y)
        object.__setattr__(self, "_local_rotation", rotation)
        object.__setattr__(self, "_local_scale_x", scale_x)
        object.__setattr__(self, "_local_scale_y", scale_y)
        object.__setattr__(self, "_parent", None)
        object.__setattr__(self, "children", _TransformChildren())
        object.__setattr__(self, "_global_cache_state", (0, x, y, rotation, scale_x, scale_y))
        object.__setattr__(self, "_global_cache_revision", 0)
        object.__setattr__(self, "_global_dirty", True)

    @property
    def local_x(self) -> float:
        return self._local_x

    @local_x.setter
    def local_x(self, value: float) -> None:
        self._set_local_attr("_local_x", value)

    @property
    def local_y(self) -> float:
        return self._local_y

    @local_y.setter
    def local_y(self, value: float) -> None:
        self._set_local_attr("_local_y", value)

    @property
    def local_rotation(self) -> float:
        return self._local_rotation

    @local_rotation.setter
    def local_rotation(self, value: float) -> None:
        self._set_local_attr("_local_rotation", value)

    @property
    def local_scale_x(self) -> float:
        return self._local_scale_x

    @local_scale_x.setter
    def local_scale_x(self, value: float) -> None:
        self._set_local_attr("_local_scale_x", value)

    @property
    def local_scale_y(self) -> float:
        return self._local_scale_y

    @local_scale_y.setter
    def local_scale_y(self, value: float) -> None:
        self._set_local_attr("_local_scale_y", value)

    @property
    def parent(self) -> Optional["Transform"]:
        return self._parent

    @parent.setter
    def parent(self, value: Optional["Transform"]) -> None:
        self._set_parent_reference(value)

    def _set_local_attr(self, attr_name: str, value: float) -> None:
        if getattr(self, attr_name) == value:
            return
        object.__setattr__(self, attr_name, value)
        self._mark_subtree_dirty()

    def _set_local_values(
        self,
        *,
        x: float,
        y: float,
        rotation: float,
        scale_x: float,
        scale_y: float,
    ) -> None:
        next_values = (x, y, rotation, scale_x, scale_y)
        current_values = (
            self._local_x,
            self._local_y,
            self._local_rotation,
            self._local_scale_x,
            self._local_scale_y,
        )
        if current_values == next_values:
            return
        object.__setattr__(self, "_local_x", x)
        object.__setattr__(self, "_local_y", y)
        object.__setattr__(self, "_local_rotation", rotation)
        object.__setattr__(self, "_local_scale_x", scale_x)
        object.__setattr__(self, "_local_scale_y", scale_y)
        self._mark_subtree_dirty()

    def _would_create_cycle(self, parent: Optional["Transform"]) -> bool:
        current = parent
        while current is not None:
            if current is self:
                return True
            current = current._parent
        return False

    def _set_parent_reference(self, parent: Optional["Transform"]) -> None:
        if parent is self or self._would_create_cycle(parent):
            raise ValueError("Transform hierarchy cannot contain cycles")
        if self._parent is parent:
            return
        previous_parent = self._parent
        if previous_parent is not None and self in previous_parent.children:
            previous_parent.children.remove(self)
        object.__setattr__(self, "_parent", parent)
        if parent is not None:
            parent.children.append(self)
        self._mark_subtree_dirty()

    def _mark_subtree_dirty(self) -> None:
        object.__setattr__(self, "_global_dirty", True)
        for child in self.children:
            child._mark_subtree_dirty()

    def _global_state(self) -> tuple[tuple[int, float, float, float, float, float], int]:
        if not self._global_dirty:
            return self._global_cache_state, self._global_cache_revision

        parent_state: tuple[int, float, float, float, float, float] | None = None
        if self._parent is not None:
            parent_state, _parent_revision = self._parent._global_state()

        if parent_state is None:
            state = (
                0,
                self._local_x,
                self._local_y,
                self._local_rotation,
                self._local_scale_x,
                self._local_scale_y,
            )
        else:
            state = (
                parent_state[0] + 1,
                parent_state[1] + self._local_x,
                parent_state[2] + self._local_y,
                parent_state[3] + self._local_rotation,
                parent_state[4] * self._local_scale_x,
                parent_state[5] * self._local_scale_y,
            )
        object.__setattr__(self, "_global_cache_state", state)
        object.__setattr__(self, "_global_cache_revision", self._global_cache_revision + 1)
        object.__setattr__(self, "_global_dirty", False)
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
        """Asigna un nuevo padre manteniendo la transformacion global."""
        global_state, _revision = self._global_state()
        _, global_x, global_y, global_rotation, global_scale_x, global_scale_y = global_state

        self.parent = parent

        if parent is None:
            self._set_local_values(
                x=global_x,
                y=global_y,
                rotation=global_rotation,
                scale_x=global_scale_x,
                scale_y=global_scale_y,
            )
        else:
            parent_state, _parent_revision = parent._global_state()
            self._set_local_values(
                x=global_x - parent_state[1],
                y=global_y - parent_state[2],
                rotation=global_rotation - parent_state[3],
                scale_x=global_scale_x / parent_state[4] if parent_state[4] != 0 else global_scale_x,
                scale_y=global_scale_y / parent_state[5] if parent_state[5] != 0 else global_scale_y,
            )

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
