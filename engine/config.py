"""
engine/config.py - Configuración centralizada del motor

PROPÓSITO:
    Contiene TODAS las constantes y valores configurables del motor.
    La IA y los usuarios deben modificar valores aquí, nunca usar
    números mágicos directamente en el código.

REGLAS:
    - Toda constante modificable va aquí
    - Los nombres son UPPER_SNAKE_CASE
    - Agrupados por categoría con comentarios

EJEMPLO DE USO:
    from engine.config import GRAVITY_DEFAULT, WINDOW_WIDTH

    physics = PhysicsSystem(gravity=GRAVITY_DEFAULT)
"""

# === VENTANA ===
WINDOW_TITLE: str = "Motor 2D - AI First Engine"
WINDOW_WIDTH: int = 800
WINDOW_HEIGHT: int = 600
TARGET_FPS: int = 60

# === FÍSICA ===
GRAVITY_DEFAULT: float = 980.0
"""Gravedad por defecto en píxeles/segundo²."""

GROUND_Y_TEMP: float = 550.0
"""Posición Y del suelo temporal (se eliminará cuando CollisionSystem lo gestione)."""

# === ANIMACIÓN ===
EDIT_ANIMATION_SPEED: float = 0.25
"""Velocidad de preview de animación en modo EDIT (multiplicador de dt)."""

# === EDITOR ===
INSPECTOR_WIDTH: int = 300
"""Ancho del panel inspector en píxeles."""

# === DEBUG ===
TIMELINE_CAPACITY: int = 1000
"""Número máximo de snapshots en el timeline de debug."""

# === HOT-RELOAD ===
SCRIPTS_DIRECTORY: str = "scripts"
"""Directorio de scripts recargables en caliente."""

HOT_RELOAD_CHECK_INTERVAL: float = 1.0
"""Intervalo en segundos entre chequeos de archivos modificados."""

# === COLORES DEL MOTOR (RGBA tuples) ===
COLOR_BG: tuple[int, int, int, int] = (40, 40, 40, 255)
"""Color de fondo del editor."""

COLOR_GRID: tuple[int, int, int, int] = (60, 60, 60, 255)

# === AUTOSAVE ===
AUTOSAVE_INTERVAL: float = 60.0
"""Intervalo de auto-guardado en segundos."""
