# Build y Distribución - MotorVideojuegosIA (Windows)

## Requisitos

- Python 3.11+
- PyInstaller: `pip install pyinstaller`
- Inno Setup 6 (solo para generar instalador): https://jrsoftware.org/isinfo.php

## Generar ejecutable

```bash
python build/build_windows.py
```

Genera `dist/MotorVideojuegosIA/MotorVideojuegosIA.exe` (carpeta con todo incluido).

## Generar ejecutable + instalador

```bash
python build/build_windows.py --installer
```

Genera `dist/MotorVideojuegosIA-{version}-Setup.exe`.

Requiere Inno Setup 6 instalado (ISCC.exe en el PATH o en su ubicación estándar).

## Publicar una nueva versión

1. **Editar la versión** en `engine/config.py`:
   ```python
   ENGINE_VERSION: str = "2026.04"  # <- cambiar aquí
   ```
   Esta es la **única fuente de verdad**. pyproject.toml, el instalador, la UI y el update checker la leen de aquí.

2. **Generar build e instalador**:
   ```bash
   python build/build_windows.py --installer
   ```

3. **Crear GitHub Release**:
   - Tag: `v2026.04` (o la versión que corresponda)
   - Subir `dist/MotorVideojuegosIA-2026.04-Setup.exe` como asset
   - Marcar como "Latest release"

4. Los usuarios existentes verán el botón verde "Update vX.Y" en la barra de menú del editor.

## Cómo funciona la comprobación de actualizaciones

- Al arrancar, el motor lanza un thread que consulta la GitHub Releases API
- Si hay una release más nueva que `ENGINE_VERSION`, muestra un botón verde en la barra de menú
- Al hacer click, abre el navegador con el enlace de descarga del instalador
- Si no hay conexión o la API falla, no pasa nada: el motor funciona normalmente
- No hay actualización automática, ni servicio en background, ni reemplazo de binarios

## Estructura de archivos de build

```
build/
  motorvideojuegos.spec   # Configuración de PyInstaller
  installer.iss           # Script de Inno Setup
  build_windows.py        # Script principal de build
```

## Notas

- Windows SmartScreen puede advertir al ejecutar el instalador (no está firmado digitalmente). El usuario debe hacer "Ejecutar de todas formas".
- El ejecutable empaquetado pesa ~30-50MB (Python + raylib embebido).
- El working directory del acceso directo apunta a la carpeta de instalación, lo cual es necesario para que `os.getcwd()` funcione correctamente con los proyectos.
