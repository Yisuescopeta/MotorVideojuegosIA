# Como ejecutar el Platformer Vertical Slice

Documento historico. Se conserva como referencia de demo antigua.

## Runner legacy archivado

- El runner historico de Windows vive en `docs/archive/legacy_runners/run_platformer_demo.bat`.
- Ese `.bat` ya no es flujo principal recomendado.
- Para uso actual, prefiere comandos manuales o la CLI publica `motor`.

## Linea de comandos manual

### Windows

```cmd
cd C:\Users\usuario\Downloads\MotorVideojuegosIA-main\MotorVideojuegosIA-main
python main.py --level levels/platformer_vertical_slice.json
```

### Linux/Mac

```bash
cd /ruta/al/MotorVideojuegosIA-main
python3 main.py --level levels/platformer_vertical_slice.json
```

## Desde Python interactivo

```python
from engine.api import EngineAPI

api = EngineAPI()
api.load_level("levels/platformer_vertical_slice.json")
api.play()
for _ in range(60):
    api.step(1)
api.stop()
```

## Controles

| Tecla | Accion |
|---|---|
| `A` o `Left` | Mover izquierda |
| `D` o `Right` | Mover derecha |
| `SPACE` | Saltar |
| `TAB` | Abrir Inspector |

## Problemas comunes

### Python no encontrado

Instala Python 3.8+ desde <https://www.python.org/downloads/>.

### Falta `pyray`

```bash
pip install pyray
```

O instala dependencias del proyecto:

```bash
pip install -r requirements.txt
```

### Entorno sin GUI

Para validar logica sin ventana:

```bash
python main.py --level levels/platformer_vertical_slice.json --headless --frames 120
```

## CLI historica

```bash
python -m cli --help
python -m cli run --level levels/platformer_vertical_slice.json
python -m cli run --level levels/platformer_vertical_slice.json --script demo/platformer_demo_package/run_demo.py
```

## Validacion rapida

```bash
python demo/platformer_demo_package/test_vertical_slice.py
```

## Estructura historica

```text
MotorVideojuegosIA-main/
|-- main.py
|-- docs/archive/legacy_runners/run_platformer_demo.bat
|-- levels/
|   `-- platformer_vertical_slice.json
`-- demo/platformer_demo_package/
    |-- assets/
    |-- test_vertical_slice.py
    `-- VERTICAL_SLICE.md
```

## Empaquetado opcional

```bash
pip install pyinstaller
pyinstaller --onefile --add-data "levels;levels" --add-data "demo;demo" main.py
```
