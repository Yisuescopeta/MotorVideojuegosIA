"""
engine/editor/raygui_theme.py - Tema Unity Dark para Raygui

PROPÓSITO:
    Configura el estilo visual de Raygui para que se parezca a Unity.
    Incluye colores oscuros profesionales y estilos de widgets.
"""

import pyray as rl
from engine.editor.ui.colors import rgba_to_int
from engine.editor.ui.theme import UNITY_DARK as EDITOR_UNITY_DARK
from engine.editor.ui.theme import get_active_theme, theme_to_raygui_map
from engine.editor.ui.tokens import BG_RAYGUI_DARK

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
    return rgba_to_int((r, g, b, a))

# Paleta Unity
UNITY_BG = rgba_to_int(EDITOR_UNITY_DARK.bg)                    # #383838 - Fondo principal
UNITY_PANEL = rgba_to_int(EDITOR_UNITY_DARK.panel)              # #2D2D2D - Paneles
UNITY_DARK = rgba_to_int(BG_RAYGUI_DARK)                        # #202020 - Más oscuro
UNITY_BORDER = rgba_to_int(EDITOR_UNITY_DARK.border)            # #1E1E1E - Bordes
UNITY_TEXT = rgba_to_int(EDITOR_UNITY_DARK.text)                # Texto claro
UNITY_TEXT_DIM = rgba_to_int(EDITOR_UNITY_DARK.text_muted)      # Texto apagado
UNITY_BLUE = rgba_to_int(EDITOR_UNITY_DARK.accent)              # Selección/Focus
UNITY_BLUE_HOVER = rgba_to_int(EDITOR_UNITY_DARK.accent_hover)  # Hover
UNITY_BUTTON = rgba_to_int(EDITOR_UNITY_DARK.button)            # Botones
UNITY_BUTTON_HOVER = rgba_to_int(EDITOR_UNITY_DARK.button_hover) # Botón hover

def apply_unity_dark_theme() -> None:
    """
    Aplica el tema oscuro estilo Unity a todos los widgets de Raygui.
    Llamar DESPUÉS de init_window() y ANTES del game loop.
    """
    # Cargar estilo por defecto primero
    rl.gui_load_style_default()

    active_theme = get_active_theme()
    for (control, property_id), value in theme_to_raygui_map(active_theme).items():
        rl.gui_set_style(control, property_id, value)

    print(f"[THEME] {active_theme.name} Theme aplicado a Raygui")
