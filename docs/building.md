# Build y distribucion Windows

Estado: referencia tecnica vigente para empaquetado local.

El script de build vive en [../build/build_windows.py](../build/build_windows.py).

## Requisitos

- Python 3.11+
- PyInstaller
- Inno Setup 6 solo si se genera instalador

Instalacion minima:

```bash
py -m pip install pyinstaller
```

Inno Setup: https://jrsoftware.org/isinfo.php

## Generar ejecutable

```bash
py build/build_windows.py
```

Salida esperada:

```text
dist/MotorVideojuegosIA/MotorVideojuegosIA.exe
```

## Generar ejecutable e instalador

```bash
py build/build_windows.py --installer
```

Salida esperada:

```text
dist/MotorVideojuegosIA-{version}-Setup.exe
```

El instalador requiere `ISCC.exe` en el `PATH` o en una ruta estandar de Inno
Setup 6.

## Version

La version del motor se lee desde `ENGINE_VERSION` en
[../engine/config.py](../engine/config.py). Ese valor alimenta el build, el
instalador y las referencias de version del motor.

Ejemplo:

```python
ENGINE_VERSION: str = "2026.03"
```

No dupliques la version en documentacion ni scripts si puede leerse desde
`engine/config.py`.

## Archivos de build

```text
build/
  build_windows.py
  installer.iss
  motorvideojuegos.spec
```

## Publicacion manual

1. Actualiza `ENGINE_VERSION` en `engine/config.py`.
2. Ejecuta `py build/build_windows.py --installer`.
3. Crea una GitHub Release con tag `v{version}`.
4. Sube `dist/MotorVideojuegosIA-{version}-Setup.exe` como asset.

## Notas

- El ejecutable empaquetado incluye Python y dependencias necesarias.
- Windows SmartScreen puede advertir si el instalador no esta firmado.
- El working directory del acceso directo debe apuntar a la carpeta de
  instalacion para conservar compatibilidad con proyectos que usan `os.getcwd()`.
