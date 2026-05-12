"""Design tokens for Frostline Qt editor theme."""

from __future__ import annotations


class FrostlineDark:
    BG_APP = "#04111c"
    BG_SHELL = "#071827"
    PANEL = "#0b2032"
    PANEL_ALT = "#102b42"
    PANEL_GLASS = "rgba(9, 30, 48, 0.82)"
    PANEL_RAISED = "#112c44"
    BORDER_SOFT = "#1d405d"
    BORDER_STRONG = "#2c6b96"
    TEXT = "#d9ecff"
    TEXT_SOFT = "#a8c1d8"
    TEXT_MUTED = "#6f8fa8"
    ACCENT = "#32c7ff"
    ACCENT_2 = "#2f8cff"
    ACCENT_DEEP = "#0c6cb3"
    ACCENT_SOFT = "rgba(50, 199, 255, 0.16)"
    SELECTION = "#0e4f7c"
    WARNING = "#ffb84d"
    DANGER = "#ff667d"
    SUCCESS = "#4ed6a3"
    SHADOW = "rgba(0, 0, 0, 0.45)"
    VIEWPORT_CHROME = "rgba(5, 20, 34, 0.78)"


class FrostlineLight:
    BG_APP = "#d8ecfb"
    BG_SHELL = "#eaf6ff"
    PANEL = "#f3faff"
    PANEL_ALT = "#e6f3fd"
    PANEL_GLASS = "rgba(244, 251, 255, 0.78)"
    PANEL_RAISED = "#ffffff"
    BORDER_SOFT = "#c8e0f2"
    BORDER_STRONG = "#9dc8e9"
    TEXT = "#17314d"
    TEXT_SOFT = "#486581"
    TEXT_MUTED = "#7a97ae"
    ACCENT = "#35bdf6"
    ACCENT_2 = "#2f8cff"
    ACCENT_DEEP = "#176fb7"
    ACCENT_SOFT = "#d8f2ff"
    SELECTION = "#bce8ff"
    WARNING = "#f7a928"
    DANGER = "#ef5b73"
    SUCCESS = "#3dbf8f"
    SHADOW = "rgba(38, 94, 145, 0.18)"
    VIEWPORT_CHROME = "rgba(67, 137, 194, 0.42)"


class Spacing:
    XS = 4
    SM = 8
    MD = 12
    LG = 16
    XL = 24


class Typography:
    FONT_FAMILY = "Segoe UI, Inter, Arial, sans-serif"
    FONT_SIZE = 12
    FONT_SIZE_SMALL = 11
    FONT_SIZE_TITLE = 13
