"""Editor theme model and Raygui mapping."""

from __future__ import annotations

from dataclasses import dataclass

from engine.editor.ui.colors import rgba_to_int
from engine.editor.ui.tokens import (
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
    FONT_SIZE_SM,
    RGBA,
)


@dataclass(frozen=True)
class EditorTheme:
    """Serializable RGBA palette used by editor chrome and Raygui style mapping."""

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


UNITY_DARK = EditorTheme()

# Raygui numeric constants. Duplicated here to keep this module pure and avoid
# importing pyray or the compatibility wrapper.
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


def theme_to_raygui_map(theme: EditorTheme = UNITY_DARK) -> dict[tuple[int, int], int]:
    """Return pure Raygui style map: (control, property) -> packed RGBA int."""
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
        (DEFAULT, TEXT_SIZE): FONT_SIZE_SM,
        (DEFAULT, TEXT_SPACING): 1,
        (DEFAULT, LINE_COLOR): border,
        (DEFAULT, BACKGROUND_COLOR): rgba_to_int(theme.panel),
        (DEFAULT, BORDER_WIDTH): BUTTON_RADIUS,
        (DEFAULT, TEXT_PADDING): CONTROL_PADDING_X,
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
