"""
engine/editor/raygui_theme.py - Tema Unity Dark para Raygui

PROPÓSITO:
    Configura el estilo visual de Raygui para que se parezca a Unity.
    Incluye colores oscuros profesionales y estilos de widgets.
"""

import pyray as rl

# ============================================================================
# Constantes de Estilo Raygui
# ============================================================================

# Control types (from raygui.h)
DEFAULT = 0
LABEL = 1
BUTTON = 2
TOGGLE = 3
SLIDER = 4
PROGRESSBAR = 5
CHECKBOX = 6
COMBOBOX = 7
DROPDOWNBOX = 8
TEXTBOX = 9
VALUEBOX = 10
SPINNER = 11
LISTVIEW = 12
COLORPICKER = 13
SCROLLBAR = 14
STATUSBAR = 15

# Properties (from raygui.h)
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
TEXT_ALIGNMENT = 14

# Default properties
TEXT_SIZE = 16
TEXT_SPACING = 17
LINE_COLOR = 18
BACKGROUND_COLOR = 19

# ============================================================================
# Unity Dark Theme Colors
# ============================================================================

def color_to_int(r: int, g: int, b: int, a: int = 255) -> int:
    """Convierte RGBA a entero para gui_set_style."""
    return (r << 24) | (g << 16) | (b << 8) | a

# Paleta Unity
UNITY_BG = color_to_int(56, 56, 56)           # #383838 - Fondo principal
UNITY_PANEL = color_to_int(45, 45, 45)        # #2D2D2D - Paneles
UNITY_DARK = color_to_int(32, 32, 32)         # #202020 - Más oscuro
UNITY_BORDER = color_to_int(30, 30, 30)       # #1E1E1E - Bordes
UNITY_TEXT = color_to_int(200, 200, 200)      # Texto claro
UNITY_TEXT_DIM = color_to_int(140, 140, 140)  # Texto apagado
UNITY_BLUE = color_to_int(44, 93, 135)        # Selección/Focus
UNITY_BLUE_HOVER = color_to_int(60, 110, 160) # Hover
UNITY_BUTTON = color_to_int(65, 65, 65)       # Botones
UNITY_BUTTON_HOVER = color_to_int(80, 80, 80) # Botón hover

def apply_unity_dark_theme() -> None:
    """
    Aplica el tema oscuro estilo Unity a todos los widgets de Raygui.
    Llamar DESPUÉS de init_window() y ANTES del game loop.
    """
    # Cargar estilo por defecto primero
    rl.gui_load_style_default()

    # ========================================
    # DEFAULT (afecta a todos los controles)
    # ========================================
    rl.gui_set_style(DEFAULT, BORDER_COLOR_NORMAL, UNITY_BORDER)
    rl.gui_set_style(DEFAULT, BASE_COLOR_NORMAL, UNITY_BG)
    rl.gui_set_style(DEFAULT, TEXT_COLOR_NORMAL, UNITY_TEXT)

    rl.gui_set_style(DEFAULT, BORDER_COLOR_FOCUSED, UNITY_BLUE)
    rl.gui_set_style(DEFAULT, BASE_COLOR_FOCUSED, UNITY_BUTTON_HOVER)
    rl.gui_set_style(DEFAULT, TEXT_COLOR_FOCUSED, UNITY_TEXT)

    rl.gui_set_style(DEFAULT, BORDER_COLOR_PRESSED, UNITY_BLUE)
    rl.gui_set_style(DEFAULT, BASE_COLOR_PRESSED, UNITY_BLUE)
    rl.gui_set_style(DEFAULT, TEXT_COLOR_PRESSED, UNITY_TEXT)

    rl.gui_set_style(DEFAULT, BORDER_COLOR_DISABLED, UNITY_DARK)
    rl.gui_set_style(DEFAULT, BASE_COLOR_DISABLED, UNITY_DARK)
    rl.gui_set_style(DEFAULT, TEXT_COLOR_DISABLED, UNITY_TEXT_DIM)

    rl.gui_set_style(DEFAULT, TEXT_SIZE, 10)
    rl.gui_set_style(DEFAULT, TEXT_SPACING, 1)
    rl.gui_set_style(DEFAULT, LINE_COLOR, UNITY_BORDER)
    rl.gui_set_style(DEFAULT, BACKGROUND_COLOR, UNITY_PANEL)

    # ========================================
    # BUTTON
    # ========================================
    rl.gui_set_style(BUTTON, BASE_COLOR_NORMAL, UNITY_BUTTON)
    rl.gui_set_style(BUTTON, BORDER_COLOR_NORMAL, UNITY_BORDER)
    rl.gui_set_style(BUTTON, BASE_COLOR_FOCUSED, UNITY_BUTTON_HOVER)
    rl.gui_set_style(BUTTON, BASE_COLOR_PRESSED, UNITY_BLUE)

    # ========================================
    # TOGGLE (para tabs)
    # ========================================
    rl.gui_set_style(TOGGLE, BASE_COLOR_NORMAL, UNITY_PANEL)
    rl.gui_set_style(TOGGLE, BASE_COLOR_PRESSED, UNITY_BG)  # Activo = más claro

    # ========================================
    # SLIDER
    # ========================================
    rl.gui_set_style(SLIDER, BASE_COLOR_NORMAL, UNITY_DARK)
    rl.gui_set_style(SLIDER, BASE_COLOR_PRESSED, UNITY_BLUE)

    # ========================================
    # CHECKBOX
    # ========================================
    rl.gui_set_style(CHECKBOX, BASE_COLOR_NORMAL, UNITY_DARK)
    rl.gui_set_style(CHECKBOX, BASE_COLOR_PRESSED, UNITY_BLUE)

    # ========================================
    # TEXTBOX
    # ========================================
    rl.gui_set_style(TEXTBOX, BASE_COLOR_NORMAL, UNITY_DARK)
    rl.gui_set_style(TEXTBOX, BORDER_COLOR_FOCUSED, UNITY_BLUE)

    # ========================================
    # LISTVIEW
    # ========================================
    rl.gui_set_style(LISTVIEW, BASE_COLOR_NORMAL, UNITY_PANEL)
    rl.gui_set_style(LISTVIEW, BASE_COLOR_FOCUSED, UNITY_BLUE)

    # ========================================
    # SCROLLBAR
    # ========================================
    rl.gui_set_style(SCROLLBAR, BASE_COLOR_NORMAL, UNITY_DARK)
    rl.gui_set_style(SCROLLBAR, BASE_COLOR_PRESSED, UNITY_BUTTON)

    print("[THEME] Unity Dark Theme aplicado a Raygui")
