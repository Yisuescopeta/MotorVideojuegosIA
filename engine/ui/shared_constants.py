"""Shared design tokens for Runtime UI and Editor UI.

These constants are independent of editor theme system, pyray, and engine
internals. Safe to import from any UI layer.
"""

from __future__ import annotations

RGBA = tuple[int, int, int, int]

# --- Font sizes ---

FONT_SIZE_XS = 8
FONT_SIZE_SM = 10
FONT_SIZE_MD = 12
FONT_SIZE_LG = 16
FONT_SIZE_XL = 20
FONT_SIZE_TITLE = 24
FONT_SIZE_HEADING = 32

# --- Spacing and layout ---

SPACING_XS = 2
SPACING_SM = 4
SPACING_MD = 8
SPACING_LG = 12
SPACING_XL = 16
PADDING_XS = 2
PADDING_SM = 4
PADDING_MD = 8
PADDING_LG = 16

# --- Sizes ---

ROW_HEIGHT_SM = 18
ROW_HEIGHT_MD = 24
ROW_HEIGHT_LG = 32
ICON_SIZE_SM = 16
ICON_SIZE_MD = 24
ICON_SIZE_LG = 32
BUTTON_HEIGHT = 28
INPUT_HEIGHT = 26
SCROLLBAR_WIDTH = 10

# --- Keyboard shortcuts ---

KEY_SHORTCUT_SAVE = ("ctrl", "s")
KEY_SHORTCUT_SAVE_AS = ("ctrl", "shift", "s")
KEY_SHORTCUT_UNDO = ("ctrl", "z")
KEY_SHORTCUT_REDO = ("ctrl", "shift", "z")
KEY_SHORTCUT_CUT = ("ctrl", "x")
KEY_SHORTCUT_COPY = ("ctrl", "c")
KEY_SHORTCUT_PASTE = ("ctrl", "v")
KEY_SHORTCUT_SELECT_ALL = ("ctrl", "a")
KEY_SHORTCUT_FIND = ("ctrl", "f")
KEY_SHORTCUT_DELETE = ("delete",)
KEY_SHORTCUT_RENAME = ("f2",)
KEY_SHORTCUT_PLAY = ("f5",)
KEY_SHORTCUT_PAUSE = ("f6",)
KEY_SHORTCUT_STOP = ("f7",)

# --- Minimal color palette (independent of editor themes) ---

COLOR_TRANSPARENT: RGBA = (0, 0, 0, 0)
COLOR_BLACK: RGBA = (0, 0, 0, 255)
COLOR_WHITE: RGBA = (255, 255, 255, 255)
COLOR_RED: RGBA = (255, 60, 60, 255)
COLOR_GREEN: RGBA = (60, 200, 80, 255)
COLOR_BLUE: RGBA = (60, 120, 255, 255)
COLOR_YELLOW: RGBA = (240, 220, 60, 255)
COLOR_ORANGE: RGBA = (255, 160, 40, 255)
COLOR_PURPLE: RGBA = (160, 80, 255, 255)
COLOR_CYAN: RGBA = (60, 200, 220, 255)
COLOR_GRAY: RGBA = (128, 128, 128, 255)
COLOR_LIGHT_GRAY: RGBA = (200, 200, 200, 255)
COLOR_DARK_GRAY: RGBA = (60, 60, 60, 255)
