# 🎮 Cómo Ejecutar el Platformer Vertical Slice

## Opción 1: Ejecutar con el script .bat (Windows)

1. **Doble clic** en `run_platformer_demo.bat`
2. El script verificará Python y dependencias automáticamente
3. El juego se iniciará con la escena del vertical slice

## Opción 2: Línea de comandos manual

### Windows

```cmd
# Navegar al directorio
cd C:\Users\usuario\Downloads\MotorVideojuegosIA-main\MotorVideojuegosIA-main

# Ejecutar con la escena del vertical slice
python main.py --level levels/platformer_vertical_slice.json
```

### Linux/Mac

```bash
# Navegar al directorio
cd /ruta/al/MotorVideojuegosIA-main

# Ejecutar
python3 main.py --level levels/platformer_vertical_slice.json
```

## Opción 3: Desde Python interactivo

```python
# En Python REPL o script
from engine.api import EngineAPI

# Crear instancia del API
api = EngineAPI()

# Cargar la escena
api.load_level("levels/platformer_vertical_slice.json")

# Iniciar gameplay
api.play()

# Avanzar frames (en modo headless)
for i in range(60):
    api.step(1)

# Detener
api.stop()
```

## Controles del Juego

| Tecla | Acción |
|-------|--------|
| **A** o **←** | Mover izquierda |
| **D** o **→** | Mover derecha |
| **SPACE** | Saltar |
| **TAB** | Abrir Inspector (debug) |

## Objetivo

1. **Recoge** la moneda dorada
2. **Evita** los pinchos rojos
3. **Llega** a la meta verde para ganar

## Si hay problemas...

### "Python no encontrado"

Instala Python 3.8+ desde: https://www.python.org/downloads/

**IMPORTANTE**: Marca la opción "Add Python to PATH" durante la instalación.

### "ModuleNotFoundError: No module named 'pyray'"

Instala las dependencias:

```bash
pip install pyray
```

O instala todas las dependencias del proyecto:

```bash
pip install -r requirements.txt
```

### Error de display/ventana

El motor usa Raylib que requiere un entorno gráfico. Si estás en:
- **Windows**: Funciona directamente
- **Linux con X11**: Funciona directamente  
- **WSL**: Necesitas configurar X11 forwarding o ejecutar nativo en Windows
- **Servidor sin GUI**: Ejecuta en modo headless (ver abajo)

## Modo Headless (sin ventana)

Para probar la lógica sin interfaz gráfica:

```bash
python main.py --level levels/platformer_vertical_slice.json --headless --frames 120
```

Esto ejecutará 120 frames de simulación sin abrir ventana.

## Usando el CLI

El motor tiene un CLI integrado:

```bash
# Ver ayuda
python -m cli --help

# Ejecutar escena
python -m cli run --level levels/platformer_vertical_slice.json

# Ejecutar con script de automatización
python -m cli run --level levels/platformer_vertical_slice.json --script demo/platformer_demo_package/run_demo.py
```

## Validación rápida

Para verificar que todo está bien sin ejecutar el juego completo:

```bash
python demo/platformer_demo_package/test_vertical_slice.py
```

## Estructura del demo

```
MotorVideojuegosIA-main/
├── main.py                           # Punto de entrada del motor
├── run_platformer_demo.bat           # Script de lanzamiento (Windows)
├── levels/
│   └── platformer_vertical_slice.json    # ← Escena del juego
└── demo/platformer_demo_package/
    ├── assets/
    │   ├── sprites/                  # Gráficos del personaje y objetos
    │   ├── tilesets/                 # Tiles del nivel
    │   └── audio/                    # Sonidos
    ├── test_vertical_slice.py        # Tests de validación
    └── VERTICAL_SLICE.md             # Documentación técnica
```

## Compilar a ejecutable (opcional)

Si quieres distribuir el juego como .exe:

```bash
pip install pyinstaller
pyinstaller --onefile --add-data "levels;levels" --add-data "demo;demo" main.py
```

El ejecutable estará en `dist/main.exe`.

---

¿Problemas? Revisa:
1. Que Python 3.8+ esté instalado y en el PATH
2. Que pyray esté instalado: `pip install pyray`
3. Que los archivos de assets existan en `demo/platformer_demo_package/assets/`
