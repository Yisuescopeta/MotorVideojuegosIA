# Export Pipeline

Sistema profesional de exportacion/build de juegos para MotorVideojuegosIA.

## Arquitectura

```text
motor export build "<Preset>"
        |
        v
ExportPresetLoader (export_presets.motor.json)
        |
        v
ExportValidator
        |
        v
BuildGraph (grafo de dependencias desde entry_scene)
        |
        v
ContentPackBuilder (game.manifest.json + content/)
        |
        v
PlatformExporter
        |
        +--> WindowsExporter  (PyInstaller -> .exe)
        +--> LinuxExporter    (PyInstaller -> binario)
        +--> MacOSExporter    (PyInstaller -> .app/binario, requiere macOS)
        +--> AndroidExporter  (Gradle -> APK/AAB, requiere Android SDK)
        +--> IOSExporter      (Xcode -> .ipa, requiere macOS + Xcode)
        |
        v
BuildReport (.motor/build/export_reports/)
```

## Runtime exportado

```text
ExportedGameRuntime
  -> RuntimeConfig (runtime_config.json)
  -> ContentPack (game.manifest.json + game.pak o content/)
  -> SceneManager.load_scene(...)
  -> Game.run()
```

El juego exportado usa `engine/runtime/exported_game.py` como entrypoint, separado del editor. No importa `engine.editor`, ni `engine.inspector`, ni `tools`, ni `tests`, ni `docs`, ni `main`.

El binario exportado soporta flags de runtime:

```bash
MyGame.exe                              # Normal (windowed, requiere pyray/raylib)
MyGame.exe --smoke-test                 # Headless smoke test (60 frames)
MyGame.exe --headless --frames 3        # Headless con N frames
MyGame.exe --print-runtime-info         # Informacion de runtime y salida
```

Windowed requiere `pyray` o `raylib`. Sin ellos, retorna
`TOOLCHAIN/RUNTIME_UNAVAILABLE` con código 2. El modo headless carga la escena,
ejecuta fisica/colision N frames y emite eventos — operativo incluso sin
toolchain de ventanas.

## Presets

Archivo: `export_presets.motor.json` en la raiz del proyecto.

Ejemplo:
```json
{
  "schema_version": 1,
  "presets": [
    {
      "name": "Windows Desktop",
      "platform": "windows",
      "architecture": "x86_64",
      "mode": "release",
      "output_path": "dist/export/windows/MyGame",
      "entry_scene": "levels/main_menu_scene.json",
      "display_name": "My Game",
      "application_id": "com.example.mygame",
      "version_name": "0.1.0",
      "version_code": 1,
      "bundle_mode": "packed",
      "include_debug_tools": false,
      "window": {
        "width": 1280,
        "height": 720,
        "resizable": true,
        "fullscreen": false
      }
    }
  ]
}
```

Campos obligatorios: `name`, `platform`, `entry_scene`, `output_path`.
Campos obligatorios para mobile: `application_id`.

Plataformas validas: `windows`, `linux`, `macos`, `android`, `ios`.
Modos validos: `debug`, `release`.
Arquitecturas validas: `x86_64`, `x86`, `arm64-v8a`, `armeabi-v7a`, `universal`.

## CLI

```bash
# Listar presets
py -m motor export presets list --project . --json

# Validar presets (todos o uno especifico)
py -m motor export presets validate --project . --json
py -m motor export presets validate --project . --name "Windows Desktop" --json

# Doctor (diagnostico de toolchain)
# Retorna "healthy": bool. Si es false, el build fallara con TOOLCHAIN_UNAVAILABLE.
py -m motor export doctor --project . --json

# Empaquetar contenido (sin build)
py -m motor export pack "Windows Desktop" --project . --json

# Build completo
py -m motor export build "Windows Desktop" --project . --json

# Build de todos los presets
py -m motor export build-all --project . --json
```

Formato JSON de respuesta:
```json
{
  "success": true,
  "message": "Export completed",
  "data": {
    "preset": "Windows Desktop",
    "platform": "windows",
    "mode": "release",
    "artifacts": ["dist/export/windows/MyGame/MyGame.exe"],
    "report": ".motor/build/export_reports/windows-release-latest.json"
  }
}
```

## Content Pack

El content pack incluye:
- `game.manifest.json`: manifiesto con hashes SHA-256, GUIDs, dependencias
- `content/`: assets, escenas, scripts alcanzables desde entry_scene
- `game.pak`: ZIP determinista (timestamps fijos, orden estable, mismo input
  produce mismo hash)
- `runtime_config.json`: configuracion de runtime (entry scene, window, etc.)

Cada asset, escena y script en el manifest incluye `sha256` y `size_bytes`.
Los GUIDs son estables: derivados del path y dependencias.

### Verificacion de integridad
- `verify_pak()` valida cada entrada del manifest dentro de `game.pak` por SHA-256.
- Se ejecuta automaticamente despues de `write_pak()` durante `build_content_pack()`.
- Si detecta archivos corruptos/tampered, el build falla con `RuntimeError`.
- En runtime, `--smoke-test` ejecuta `ContentLoader.verify_integrity()` (codigo 3 si invalido).

El grafo de contenido recorre la entry scene y sigue:
- Scene flow links (`next_scene`, `menu_scene`, `target_scene`)
- Prefabs referenciados (`prefab_path`)
- Assets referenciados (`texture_path`, `asset_path`, `sprite_sheet`, etc.)

Exclusiones: `.git`, `__pycache__`, `.motor`, `dist`, `tests`, `docs`, `build`.

Assets cargados dinamicamente por scripts no se detectan. Para incluirlos,
usar `include_all_assets` o `mode: debug` en el preset.

## Exportadores

### Windows
- Requiere PyInstaller (`pip install pyinstaller`)
- Genera `.exe` standalone
- `console=True` para debug
- El spec no empaqueta el directorio completo `engine/` — solo runtime_config, manifest y pak
- Post-build: copia runtime files al directorio del ejecutable y ejecuta smoke test

### Linux
- Requiere PyInstaller
- Genera binario sin extension
- Sin `console=True`
- Post-build y smoke test analogos a Windows

### macOS
- Requiere macOS + PyInstaller + Xcode (opcional)
- Si no es macOS: `TOOLCHAIN_UNAVAILABLE`
- Si es macOS: genera `.app` o binario con `--windowed`
- Post-build: runtime files a `Contents/Resources/` para .app, al dir del binario en otro caso
- Smoke test via `open --args --smoke-test` para .app

### Android
- Requiere `ANDROID_HOME`, JDK 11+, Gradle
- Genera proyecto Android desde template `platforms/android/template/`
- Debug: `assembleDebug` -> APK
- Release: `assembleRelease` -> APK firmado, `bundleRelease` -> AAB
- Keystore configurable via `preset.extra.keystore_path`
- Errores de keystore con codigos accionables: `ANDROID_KEYSTORE_MISSING`, `ANDROID_KEYSTORE_NOT_FOUND`
- Si `output_path` termina en `.apk` o `.aab`, el artefacto se copia a ese nombre exacto

### iOS
- Requiere macOS + Xcode
- Si no es macOS: `TOOLCHAIN_UNAVAILABLE` con instrucciones claras
- Si es macOS: genera proyecto Xcode desde template `platforms/ios/template/`
- NO compila automaticamente (requiere Apple Developer account)

## Build Reports

Cada build genera un report en `.motor/build/export_reports/`:

```json
{
  "schema_version": 1,
  "success": true,
  "preset": "Windows Desktop",
  "platform": "windows",
  "mode": "release",
  "engine_version": "2026.03",
  "project_name": "My Game",
  "entry_scene": "levels/main_menu_scene.json",
  "started_at_utc": "...",
  "finished_at_utc": "...",
  "duration_seconds": 18.2,
  "artifacts": [
    {
      "path": "dist/export/windows/MyGame/MyGame.exe",
      "kind": "executable",
      "size_bytes": 12345678,
      "sha256": "abcdef..."
    }
  ],
  "warnings": [],
  "errors": [],
  "environment": { "python": "3.11", "os": "Windows", "pyinstaller": "" }
}
```

### Sanitizacion de reports

Los build reports se sanitizan automaticamente antes de escribirse:

- `keystore_path`, `keystore_password`, `key_alias`, `key_password` se redactan
  como `[REDACTED]`.
- Cualquier campo que contenga `password`, `token`, `secret` o `api_key` se
  redacta.
- Flags de CLI como `--password <valor>` se redactan.
- Los artifacts paths y environment variables tambien se sanitizan.

Esto previene filtrado accidental de credenciales de signing en reports de CI.

## EngineAPI

```python
from engine.api import EngineAPI

api = EngineAPI(project_root=".")
api.list_export_presets()
api.validate_export_preset()                     # todos los presets
api.validate_export_preset("Windows Desktop")    # uno especifico
api.export_doctor()
api.export_pack("Windows Desktop")
api.build_export("Windows Desktop")
api.build_all_exports()
api.shutdown()
```

Todas devuelven `{ "success": bool, "message": str, "data": object }`.
`export_pack` genera staging en `.motor/build/staging/<preset>/`.
`export build` escribe report en `.motor/build/export_reports/`.

## Doctor: diagnosticos de toolchain

`motor export doctor` ejecuta estos checks:

| Check | Que detecta | Impacto si falla |
|---|---|---|
| PyInstaller | `shutil.which("pyinstaller")` | Desktop builds fallan con `TOOLCHAIN_UNAVAILABLE` |
| pip | Import `pip` | Reporte de entorno incompleto |
| ANDROID_HOME | Variable de entorno `ANDROID_HOME`/`ANDROID_SDK_ROOT` | Android exports fallan |
| Java/JDK | `shutil.which("java")` | Android builds requieren JDK |
| Gradle | `shutil.which("gradle")` | Android compilacion requiere Gradle |

El resultado incluye `healthy: bool`. Cuando PyInstaller o pip faltan, `healthy`
es `false` y `doctor` retorna `success: false` con lista de issues y warnings.

## Requisitos por plataforma

| Plataforma | Toolchain | SO requerido |
|-----------|-----------|-------------|
| Windows | PyInstaller | Windows |
| Linux | PyInstaller | Linux |
| macOS | PyInstaller, Xcode | macOS |
| Android | Android SDK, JDK 11+, Gradle | Cualquiera |
| iOS | Xcode, Apple Developer | macOS |

## Limitaciones reales

### Windowed runtime condicionado a pyray/raylib

El modo windowed del runtime exportado requiere que `pyray` (o `raylib`) esté
disponible. Sin esta dependencia, el entrypoint retorna
`TOOLCHAIN/RUNTIME_UNAVAILABLE` con código 2. El modo headless (`--smoke-test`,
`--headless --frames N`) funciona sin dependencias gráficas.

### Content graph: assets cargados dinamicamente

El grafo de contenido detecta assets por referencias estáticas en campos JSON
conocidos (`texture_path`, `asset_path`, `sprite_sheet`, `prefab_path`, etc.).
Assets cargados dinámicamente por scripts Python (ej. `load_texture(nombre)`)
no se detectan. Para cubrirlos, activar `include_all_assets` en el preset o
usar `mode: debug`.

### Toolchains externas

Los builds reales de Windows/Linux requieren PyInstaller, Android requiere
Android SDK + JDK + Gradle, macOS/iOS requieren macOS + Xcode. Sin ellos,
el pipeline genera content pack, proyecto Android estructural y build report
con `TOOLCHAIN_UNAVAILABLE`, pero no el ejecutable final.

## Troubleshooting

### `TOOLCHAIN_UNAVAILABLE: PyInstaller not found`
```bash
pip install pyinstaller
```

### `TOOLCHAIN_UNAVAILABLE: ANDROID_HOME not set`
```bash
# Windows
set ANDROID_HOME=C:\Users\<user>\AppData\Local\Android\Sdk

# Linux/macOS
export ANDROID_HOME=~/Android/Sdk
```

### `TOOLCHAIN_UNAVAILABLE: macOS export requires a macOS host`
Exporta macOS desde una Mac o usa CI con runners macOS (GitHub Actions `macos-latest`).

### `ENTRY_SCENE_NOT_FOUND`
Verifica que `entry_scene` en `export_presets.motor.json` apunte a una escena existente en `levels/`.
