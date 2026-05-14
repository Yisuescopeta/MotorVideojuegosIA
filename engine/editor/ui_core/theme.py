"""Editor theme model, named registry and Raygui mapping."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from engine.editor.ui_core.colors import rgba_to_int
from engine.editor.ui_core.tokens import (
    BG_RAYGUI_DARK,
    BUTTON_RADIUS,
    CONTROL_PADDING_X,
    EDITOR_ACCENT,
    EDITOR_ACCENT_HOVER,
    EDITOR_BG,
    EDITOR_BORDER,
    EDITOR_BORDER_HOVER,
    EDITOR_DANGER,
    EDITOR_PANEL,
    EDITOR_PANEL_ALT,
    EDITOR_PANEL_HEADER,
    EDITOR_SUCCESS,
    EDITOR_TEXT,
    EDITOR_TEXT_DISABLED,
    EDITOR_TEXT_MUTED,
    EDITOR_WARNING,
    FONT_SIZE_LG,
    FONT_SIZE_MD,
    FONT_SIZE_SM,
    PANEL_RADIUS,
    RGBA,
)


@dataclass(frozen=True)
class EditorTheme:
    """Serializable editor theme used by editor chrome and Raygui style mapping."""

    name: str = "unity_dark"
    bg: RGBA = EDITOR_BG
    panel: RGBA = EDITOR_PANEL
    panel_alt: RGBA = EDITOR_PANEL_ALT
    panel_header: RGBA = EDITOR_PANEL_HEADER
    border: RGBA = EDITOR_BORDER
    border_hover: RGBA = EDITOR_BORDER_HOVER
    text: RGBA = EDITOR_TEXT
    text_muted: RGBA = EDITOR_TEXT_MUTED
    text_disabled: RGBA = EDITOR_TEXT_DISABLED
    accent: RGBA = EDITOR_ACCENT
    accent_hover: RGBA = EDITOR_ACCENT_HOVER
    danger: RGBA = EDITOR_DANGER
    warning: RGBA = EDITOR_WARNING
    success: RGBA = EDITOR_SUCCESS
    raygui_dark: RGBA = BG_RAYGUI_DARK
    button: RGBA = (65, 65, 65, 255)
    button_hover: RGBA = (80, 80, 80, 255)
    font_size_sm: int = FONT_SIZE_SM
    font_size_md: int = FONT_SIZE_MD
    font_size_lg: int = FONT_SIZE_LG
    panel_radius: int = PANEL_RADIUS
    button_radius: int = BUTTON_RADIUS
    control_padding_x: int = CONTROL_PADDING_X

    @property
    def colors(self) -> dict[str, RGBA]:
        return {key: getattr(self, key) for key in _COLOR_FIELDS}

    @property
    def fonts(self) -> dict[str, int]:
        return {
            "font_size_sm": self.font_size_sm,
            "font_size_md": self.font_size_md,
            "font_size_lg": self.font_size_lg,
        }

    @property
    def metrics(self) -> dict[str, int]:
        return {
            "panel_radius": self.panel_radius,
            "button_radius": self.button_radius,
            "control_padding_x": self.control_padding_x,
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "colors": {key: list(value) for key, value in self.colors.items()},
            "fonts": self.fonts,
            "metrics": self.metrics,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "EditorTheme":
        payload: dict[str, Any] = {"name": str(data.get("name", "custom"))}
        colors = data.get("colors", {})
        if isinstance(colors, dict):
            for key in _COLOR_FIELDS:
                if key in colors:
                    payload[key] = _rgba_from_payload(colors[key])
        for group_name, fields in (("fonts", _FONT_FIELDS), ("metrics", _METRIC_FIELDS)):
            group = data.get(group_name, {})
            if isinstance(group, dict):
                for key in fields:
                    if key in group:
                        payload[key] = _int_from_payload(group[key])
        for key in (*_COLOR_FIELDS, *_FONT_FIELDS, *_METRIC_FIELDS):
            if key in data:
                payload[key] = _rgba_from_payload(data[key]) if key in _COLOR_FIELDS else _int_from_payload(data[key])
        return cls(**payload)


_COLOR_FIELDS = (
    "bg",
    "panel",
    "panel_alt",
    "panel_header",
    "border",
    "border_hover",
    "text",
    "text_muted",
    "text_disabled",
    "accent",
    "accent_hover",
    "danger",
    "warning",
    "success",
    "raygui_dark",
    "button",
    "button_hover",
)
_FONT_FIELDS = ("font_size_sm", "font_size_md", "font_size_lg")
_METRIC_FIELDS = ("panel_radius", "button_radius", "control_padding_x")


def _rgba_from_payload(value: object) -> RGBA:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError(f"Expected RGBA list/tuple, got {value!r}")
    return (int(value[0]), int(value[1]), int(value[2]), int(value[3]))


def _int_from_payload(value: object) -> int:
    if isinstance(value, bool):
        raise ValueError(f"Expected int-compatible value, got {value!r}")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        raise ValueError(f"Expected int-compatible value, got {value!r}")
    if isinstance(value, str):
        return int(value)
    raise ValueError(f"Expected int-compatible value, got {value!r}")


class ThemeRegistry:
    """In-memory named theme registry. Pure; no file IO here."""

    def __init__(self, themes: list[EditorTheme] | None = None, active_name: str = "unity_dark") -> None:
        self._themes: dict[str, EditorTheme] = {}
        for theme in themes or []:
            self.register(theme)
        self._active_name = active_name

    @property
    def active_name(self) -> str:
        return self._active_name

    def names(self) -> tuple[str, ...]:
        return tuple(self._themes.keys())

    def register(self, theme: EditorTheme) -> None:
        if not theme.name:
            raise ValueError("Theme name cannot be empty")
        self._themes[theme.name] = theme

    def get(self, name: str) -> EditorTheme:
        try:
            return self._themes[name]
        except KeyError as exc:
            raise KeyError(f"Unknown editor theme: {name}") from exc

    def set_active(self, name: str) -> EditorTheme:
        theme = self.get(name)
        self._active_name = name
        return theme

    def active(self) -> EditorTheme:
        return self.get(self._active_name)

    def to_dict(self) -> dict[str, object]:
        return {"active": self._active_name, "themes": [theme.to_dict() for theme in self._themes.values()]}


UNITY_DARK = EditorTheme()
UNITY_LIGHT = EditorTheme(
    name="unity_light",
    bg=(194, 194, 194, 255),
    panel=(220, 220, 220, 255),
    panel_alt=(205, 205, 205, 255),
    panel_header=(210, 210, 210, 255),
    border=(130, 130, 130, 255),
    border_hover=(100, 100, 100, 255),
    text=(35, 35, 35, 255),
    text_muted=(90, 90, 90, 255),
    text_disabled=(140, 140, 140, 255),
    accent=(58, 120, 180, 255),
    accent_hover=(75, 140, 205, 255),
    raygui_dark=(180, 180, 180, 255),
    button=(200, 200, 200, 255),
    button_hover=(185, 205, 225, 255),
)
THEME_REGISTRY = ThemeRegistry([UNITY_DARK, UNITY_LIGHT])


def get_active_theme() -> EditorTheme:
    return THEME_REGISTRY.active()


def set_active_theme(name: str) -> EditorTheme:
    return THEME_REGISTRY.set_active(name)


def resolve_theme(theme: EditorTheme | None = None) -> EditorTheme:
    return THEME_REGISTRY.active() if theme is None else theme

DEFAULT = 0
BUTTON = 2
TOGGLE = 3
SLIDER = 4
CHECKBOX = 6
TEXTBOX = 9
LISTVIEW = 12
SCROLLBAR = 14

BORDER_COLOR_NORMAL = 0
BASE_COLOR_NORMAL = 1
TEXT_COLOR_NORMAL = 2
BORDER_COLOR_FOCUSED = 3
BASE_COLOR_FOCUSED = 4
TEXT_COLOR_FOCUSED = 5
BORDER_COLOR_PRESSED = 6
BASE_COLOR_PRESSED = 7
TEXT_COLOR_PRESSED = 8
BORDER_COLOR_DISABLED = 9
BASE_COLOR_DISABLED = 10
TEXT_COLOR_DISABLED = 11
BORDER_WIDTH = 12
TEXT_PADDING = 13
TEXT_SIZE = 16
TEXT_SPACING = 17
LINE_COLOR = 18
BACKGROUND_COLOR = 19


def theme_to_raygui_map(theme: EditorTheme | None = UNITY_DARK) -> dict[tuple[int, int], int]:
    """Return pure Raygui style map: (control, property) -> packed RGBA int."""
    theme = resolve_theme(theme)
    border = rgba_to_int(theme.border)
    text = rgba_to_int(theme.text)
    accent = rgba_to_int(theme.accent)
    dark = rgba_to_int(theme.raygui_dark)
    return {
        (DEFAULT, BORDER_COLOR_NORMAL): border,
        (DEFAULT, BASE_COLOR_NORMAL): rgba_to_int(theme.bg),
        (DEFAULT, TEXT_COLOR_NORMAL): text,
        (DEFAULT, BORDER_COLOR_FOCUSED): accent,
        (DEFAULT, BASE_COLOR_FOCUSED): rgba_to_int(theme.button_hover),
        (DEFAULT, TEXT_COLOR_FOCUSED): text,
        (DEFAULT, BORDER_COLOR_PRESSED): accent,
        (DEFAULT, BASE_COLOR_PRESSED): accent,
        (DEFAULT, TEXT_COLOR_PRESSED): text,
        (DEFAULT, BORDER_COLOR_DISABLED): dark,
        (DEFAULT, BASE_COLOR_DISABLED): dark,
        (DEFAULT, TEXT_COLOR_DISABLED): rgba_to_int(theme.text_muted),
        (DEFAULT, TEXT_SIZE): theme.font_size_sm,
        (DEFAULT, TEXT_SPACING): 1,
        (DEFAULT, LINE_COLOR): border,
        (DEFAULT, BACKGROUND_COLOR): rgba_to_int(theme.panel),
        (DEFAULT, BORDER_WIDTH): theme.button_radius,
        (DEFAULT, TEXT_PADDING): theme.control_padding_x,
        (BUTTON, BASE_COLOR_NORMAL): rgba_to_int(theme.button),
        (BUTTON, BORDER_COLOR_NORMAL): border,
        (BUTTON, BASE_COLOR_FOCUSED): rgba_to_int(theme.button_hover),
        (BUTTON, BASE_COLOR_PRESSED): accent,
        (TOGGLE, BASE_COLOR_NORMAL): rgba_to_int(theme.panel),
        (TOGGLE, BASE_COLOR_PRESSED): rgba_to_int(theme.bg),
        (SLIDER, BASE_COLOR_NORMAL): dark,
        (SLIDER, BASE_COLOR_PRESSED): accent,
        (CHECKBOX, BASE_COLOR_NORMAL): dark,
        (CHECKBOX, BASE_COLOR_PRESSED): accent,
        (TEXTBOX, BASE_COLOR_NORMAL): dark,
        (TEXTBOX, BORDER_COLOR_FOCUSED): accent,
        (LISTVIEW, BASE_COLOR_NORMAL): rgba_to_int(theme.panel),
        (LISTVIEW, BASE_COLOR_FOCUSED): accent,
        (SCROLLBAR, BASE_COLOR_NORMAL): dark,
        (SCROLLBAR, BASE_COLOR_PRESSED): rgba_to_int(theme.button),
    }
