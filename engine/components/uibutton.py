"""
engine/components/uibutton.py - Boton UI serializable con accion declarativa.
"""

from __future__ import annotations

import copy
from typing import Any

from engine.assets.asset_reference import clone_asset_reference, normalize_asset_reference, reference_has_identity
from engine.ecs.component import Component


def _color_tuple(value: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    r, g, b, a = value
    return (int(r), int(g), int(b), int(a))


class UIButton(Component):
    """Boton UI con accion declarativa ejecutada al soltar dentro del control."""

    def __init__(
        self,
        enabled: bool = True,
        interactable: bool = True,
        label: str = "Button",
        normal_color: tuple[int, int, int, int] = (72, 72, 72, 255),
        hover_color: tuple[int, int, int, int] = (92, 92, 92, 255),
        pressed_color: tuple[int, int, int, int] = (56, 56, 56, 255),
        disabled_color: tuple[int, int, int, int] = (48, 48, 48, 200),
        transition_scale_pressed: float = 0.96,
        on_click: dict[str, Any] | None = None,
        normal_sprite: Any = None,
        hover_sprite: Any = None,
        pressed_sprite: Any = None,
        disabled_sprite: Any = None,
        normal_slice: str = "",
        hover_slice: str = "",
        pressed_slice: str = "",
        disabled_slice: str = "",
        image_tint: tuple[int, int, int, int] = (255, 255, 255, 255),
        preserve_aspect: bool = True,
    ) -> None:
        self.enabled = enabled
        self.interactable = bool(interactable)
        self.label = str(label)
        self.normal_color = _color_tuple(normal_color)
        self.hover_color = _color_tuple(hover_color)
        self.pressed_color = _color_tuple(pressed_color)
        self.disabled_color = _color_tuple(disabled_color)
        self.transition_scale_pressed = float(transition_scale_pressed)
        self.on_click = copy.deepcopy(on_click or {})
        self.normal_sprite = normalize_asset_reference(normal_sprite)
        self.hover_sprite = normalize_asset_reference(hover_sprite)
        self.pressed_sprite = normalize_asset_reference(pressed_sprite)
        self.disabled_sprite = normalize_asset_reference(disabled_sprite)
        self.normal_slice = str(normal_slice or "")
        self.hover_slice = str(hover_slice or "")
        self.pressed_slice = str(pressed_slice or "")
        self.disabled_slice = str(disabled_slice or "")
        self.image_tint = _color_tuple(image_tint)
        self.preserve_aspect = bool(preserve_aspect)

    def has_sprite_visuals(self) -> bool:
        return any(
            reference_has_identity(ref)
            for ref in (
                self.normal_sprite,
                self.hover_sprite,
                self.pressed_sprite,
                self.disabled_sprite,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "interactable": self.interactable,
            "label": self.label,
            "normal_color": list(self.normal_color),
            "hover_color": list(self.hover_color),
            "pressed_color": list(self.pressed_color),
            "disabled_color": list(self.disabled_color),
            "transition_scale_pressed": self.transition_scale_pressed,
            "on_click": copy.deepcopy(self.on_click),
            "normal_sprite": clone_asset_reference(self.normal_sprite),
            "hover_sprite": clone_asset_reference(self.hover_sprite),
            "pressed_sprite": clone_asset_reference(self.pressed_sprite),
            "disabled_sprite": clone_asset_reference(self.disabled_sprite),
            "normal_slice": self.normal_slice,
            "hover_slice": self.hover_slice,
            "pressed_slice": self.pressed_slice,
            "disabled_slice": self.disabled_slice,
            "image_tint": list(self.image_tint),
            "preserve_aspect": self.preserve_aspect,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UIButton":
        return cls(
            enabled=data.get("enabled", True),
            interactable=data.get("interactable", True),
            label=data.get("label", "Button"),
            normal_color=tuple(data.get("normal_color", [72, 72, 72, 255])),  # type: ignore[arg-type]
            hover_color=tuple(data.get("hover_color", [92, 92, 92, 255])),  # type: ignore[arg-type]
            pressed_color=tuple(data.get("pressed_color", [56, 56, 56, 255])),  # type: ignore[arg-type]
            disabled_color=tuple(data.get("disabled_color", [48, 48, 48, 200])),  # type: ignore[arg-type]
            transition_scale_pressed=data.get("transition_scale_pressed", 0.96),
            on_click=copy.deepcopy(data.get("on_click", {})),
            normal_sprite=data.get("normal_sprite"),
            hover_sprite=data.get("hover_sprite"),
            pressed_sprite=data.get("pressed_sprite"),
            disabled_sprite=data.get("disabled_sprite"),
            normal_slice=data.get("normal_slice", ""),
            hover_slice=data.get("hover_slice", ""),
            pressed_slice=data.get("pressed_slice", ""),
            disabled_slice=data.get("disabled_slice", ""),
            image_tint=tuple(data.get("image_tint", [255, 255, 255, 255])),  # type: ignore[arg-type]
            preserve_aspect=data.get("preserve_aspect", True),
        )
