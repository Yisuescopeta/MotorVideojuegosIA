"""
scripts/example_script.py - Script de ejemplo para hot-reload

PROPÓSITO:
    Demuestra cómo crear un script recargable en caliente.
    Modifica este archivo mientras el motor está corriendo y
    presiona F8 para ver los cambios aplicados.

EJEMPLO:
    Cambia el mensaje de abajo y presiona F8 en el motor.
"""


def on_reload() -> None:
    """
    Se ejecuta automáticamente cuando el módulo es recargado.
    Úsalo para aplicar cambios al motor en tiempo real.
    """
    print("[SCRIPT] example_script recargado exitosamente!")
    print("[SCRIPT] Modifica este archivo y presiona F8 para probar hot-reload")


def get_description() -> str:
    """Retorna una descripción del script."""
    return "Script de ejemplo para demostrar hot-reload"


# Este código se ejecuta al cargar el módulo por primera vez
print("[SCRIPT] example_script cargado")
