"""
tools/generate_test_spritesheet.py - Genera un sprite sheet de prueba

PROPÓSITO:
    Crea una imagen PNG con múltiples frames para probar el sistema de animaciones.
    Cada frame es un rectángulo de color diferente para visualizar los cambios.

EJECUCIÓN:
    python tools/generate_test_spritesheet.py

RESULTADO:
    assets/test_spritesheet.png - Sprite sheet de 8 frames (4 columnas x 2 filas)
"""

import os

# Intentar usar Raylib para generar la imagen
try:
    import pyray as rl
    HAS_RAYLIB = True
except ImportError:
    HAS_RAYLIB = False


def generate_spritesheet_raylib() -> None:
    """Genera el sprite sheet usando Raylib."""
    frame_width = 32
    frame_height = 32
    columns = 4
    rows = 2

    total_width = frame_width * columns
    total_height = frame_height * rows

    # Colores para cada frame (8 frames)
    colors = [
        rl.RED,
        rl.ORANGE,
        rl.YELLOW,
        rl.GREEN,
        rl.SKYBLUE,
        rl.BLUE,
        rl.PURPLE,
        rl.PINK
    ]

    # Crear directorio de assets si no existe
    os.makedirs("assets", exist_ok=True)

    # Inicializar ventana oculta
    rl.set_config_flags(getattr(rl, "FLAG_WINDOW_HIDDEN", 0))
    rl.init_window(1, 1, "Generator")

    # Crear render texture
    target = rl.load_render_texture(total_width, total_height)

    # Dibujar frames en la textura
    rl.begin_texture_mode(target)
    rl.clear_background(rl.BLANK)

    for i, color in enumerate(colors):
        col = i % columns
        row = i // columns

        x = col * frame_width
        y = row * frame_height

        # Dibujar rectángulo de color
        rl.draw_rectangle(x + 2, y + 2, frame_width - 4, frame_height - 4, color)

        # Dibujar borde
        rl.draw_rectangle_lines(x, y, frame_width, frame_height, rl.WHITE)

        # Dibujar número de frame
        rl.draw_text(str(i), x + 12, y + 10, 14, rl.WHITE)

    rl.end_texture_mode()

    # Guardar imagen
    image = rl.load_image_from_texture(target.texture)
    rl.image_flip_vertical(image)  # Raylib invierte Y
    rl.export_image(image, "assets/test_spritesheet.png")

    # Limpiar
    rl.unload_image(image)
    rl.unload_render_texture(target)
    rl.close_window()

    print("✅ Generado: assets/test_spritesheet.png")
    print(f"   Tamaño: {total_width}x{total_height}")
    print(f"   Frames: {len(colors)} ({columns} columnas x {rows} filas)")
    print(f"   Frame size: {frame_width}x{frame_height}")


def generate_placeholder_info() -> None:
    """Información sobre cómo crear el sprite sheet manualmente."""
    print("=" * 50)
    print("SPRITE SHEET DE PRUEBA")
    print("=" * 50)
    print()
    print("Para probar las animaciones, necesitas un sprite sheet.")
    print("Puedes crear uno manualmente con estas especificaciones:")
    print()
    print("  Archivo: assets/test_spritesheet.png")
    print("  Tamaño: 128x64 píxeles")
    print("  Frames: 8 (4 columnas x 2 filas)")
    print("  Tamaño de frame: 32x32 píxeles")
    print()
    print("Distribución de frames:")
    print("  [0][1][2][3]  <- Fila 1 (idle: 0-3)")
    print("  [4][5][6][7]  <- Fila 2 (run: 4-7)")
    print()


if __name__ == "__main__":
    if HAS_RAYLIB:
        generate_spritesheet_raylib()
    else:
        generate_placeholder_info()
