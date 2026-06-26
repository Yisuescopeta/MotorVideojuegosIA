# Export Pipeline

Sistema profesional de exportacion/build de juegos para OpenGame.

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
  -> ContentLoader
  -> SharedGameRuntime
      -> Game(editor_enabled=False, hot_reload_enabled=False)
      -> RuntimeController.load_scene_from_data(...)
      -> mismos sistemas y orden de PLAY del editor
```

El juego exportado usa `engine/runtime/exported_game.py` como entrypoint.
No monta paneles, inspector, herramientas de editor ni hot-reload, pero ejecuta
la escena mediante el mismo `Game` + `RuntimeController` usado por PLAY en el
editor. No importa `engine.editor`, ni `engine.inspector`, ni `tools`, ni
`tests`, ni `docs`, ni `main`.

`engine/runtime/export_runtime.py` queda como shim deprecated: conserva imports
legacy de `ExportRuntime`, pero delega en `SharedGameRuntime`.

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

Cuando un asset alcanzable tiene sidecar `*.meta.json`, el sidecar tambien se
incluye en el content pack. Esto conserva metadata de slices para `Sprite` y
`Animator` en exports PC/Android.

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
- Dependencias de scripts alcanzables: `*.py.meta.json.dependencies` y literales
  Python simples que sean rutas de proyecto (`assets/...`, `scripts/...`, etc.)

Exclusiones: `.git`, `__pycache__`, `.motor`, `dist`, `tests`, `docs`, `build`.

Assets construidos dinamicamente por scripts (por ejemplo concatenando strings)
no se detectan. Para incluirlos, declararlos en el `.py.meta.json`, usar
`include_all_assets` o usar `mode: debug` en el preset.

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
- Requiere `ANDROID_HOME`, Build-Tools 34.0.0+, JDK 17+ y Gradle 8.7+
- El template fija Android Gradle Plugin 8.6.1 y wrapper Gradle 8.7 para API 35
- Genera proyecto Android desde template `platforms/android/template/`
- Debug: `assembleDebug` -> APK
- Release: `assembleRelease` -> APK firmado, `bundleRelease` -> AAB
- El APK esperado es obligatorio; nunca se seleccionan variantes `unsigned`
- Keystore configurable via `preset.extra.keystore_path`
- Errores de keystore con codigos accionables: `ANDROID_KEYSTORE_MISSING`, `ANDROID_KEYSTORE_NOT_FOUND`
- Si `output_path` termina en `.apk` o `.aab`, el artefacto se copia a ese nombre exacto
- `android_python_runtime: true` activa Chaquopy 17.0.0, requiere `min_sdk >= 24`
  y copia `engine/`, `pyray/`, `sitecustomize.py` y scripts alcanzables a
  `app/src/main/python/`
- `runtime_config.json` incluye `android_runtime_cache_key`, derivado de
  `game.manifest.json` y del runtime/template Android relevante; el shell
  Android lo usa para cachear en `filesDir` solo los assets runtime necesarios
  y nunca copia `chaquopy/`
- Si el runtime compartido falla al crear escena o frame, Android muestra una
  pantalla de error visible y registra el detalle en Logcat (`MotorGame`)
- Escenas Android jugables (`InputMap` + `PlayerController2D`) requieren
  `android_python_runtime: true` para mantener paridad con PLAY del editor

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
| Android platforms | `platforms/android-{compile_sdk}` para todos los presets Android | Falla con `ANDROID_PLATFORM_MISSING` |
| Android build-tools | Version mas alta bajo `build-tools/` | Requiere 34.0.0+ |
| Java/JDK | Ruta, version, major y compatibilidad | Requiere JDK 17+ |
| Gradle | Ruta, version y compatibilidad del wrapper/global | Requiere Gradle 8.7+ |

El resultado incluye `healthy: bool`. Cuando PyInstaller o pip faltan, `healthy`
es `false` y `doctor` retorna `success: false` con lista de issues y warnings.

## Requisitos por plataforma

| Plataforma | Toolchain | SO requerido |
|-----------|-----------|-------------|
| Windows | PyInstaller | Windows |
| Linux | PyInstaller | Linux |
| macOS | PyInstaller, Xcode | macOS |
| Android | Android SDK, Build-Tools 34.0.0+, JDK 17+, Gradle 8.7+ | Cualquiera |
| iOS | Xcode, Apple Developer | macOS |

## Limitaciones reales

### Windowed runtime condicionado a pyray/raylib

El modo windowed del runtime exportado requiere que `pyray` (o `raylib`) esté
disponible. Sin esta dependencia, el entrypoint retorna
`TOOLCHAIN/RUNTIME_UNAVAILABLE` con código 2. El modo headless (`--smoke-test`,
`--headless --frames N`) funciona sin dependencias gráficas.

### Smoke test no equivale a jugabilidad completa

`--smoke-test` valida carga headless + 60 frames de simulacion usando
`SharedGameRuntime`, `Game` y `RuntimeController`. Es el mismo orden runtime de
PLAY del editor, con herramientas de editor desactivadas y sin carga GPU de
texturas cuando no existe ventana raylib.
Sin embargo, **no verifica**:
- Render de sprites/texturas reales (el smoke test es headless, no abre ventana)
- Input de teclado/mouse real (solo inyectado via `inject_input`)
- Interaccion UI (mouse real + UISystem + cambio de escena por click en boton)
- ScriptBehaviour con eventos runtime reales

Para validar jugabilidad real (escena con UI, click en boton que carga otra
escena, input que mueve Player, colisiones con gravedad), usa los tests de
`tests/test_export_runtime_playability.py`:

```bash
py -m unittest tests.test_export_runtime_playability -v
```

Estos tests verifican el shim `ExportRuntime` y el runtime compartido sin
PyInstaller ni builds completos. Cubren: carga de escenas, ejecucion de frames,
movimiento del Player por input inyectado (izquierda, derecha, salto),
gravedad, click en UIButton con cambio de escena, scripts desde `.pak`,
coleccionables semanticos y pickup scriptado que aplica score antes de destruir
la entidad.

### Content graph: assets cargados dinamicamente

El grafo de contenido detecta assets por referencias estáticas en campos JSON
conocidos (`texture_path`, `asset_path`, `sprite_sheet`, `prefab_path`, etc.).
Assets construidos dinamicamente por scripts Python (ej. `load_texture(prefijo + nombre)`)
no se detectan. Para cubrirlos, declararlos en `script.py.meta.json`, activar
`include_all_assets` en el preset o usar `mode: debug`.

### Toolchains externas

Los builds reales de Windows/Linux requieren PyInstaller, Android requiere
Android SDK + JDK + Gradle o wrapper, macOS/iOS requieren macOS + Xcode. Sin ellos,
el pipeline genera content pack, proyecto Android estructural y build report
con `TOOLCHAIN_UNAVAILABLE`, pero no el ejecutable final.

El proyecto Android generado empaqueta el content pack en assets. Con
`android_python_runtime: true`, el shell Kotlin extrae a `filesDir` solo
`runtime_config.json`, `game.manifest.json`, `levels/`, `assets/` y `scripts/`,
excluye `chaquopy/`, cachea la copia con `android_runtime_cache_key`, arranca
Chaquopy y ejecuta `SharedGameRuntime`, la misma ruta `Game` +
`RuntimeController` que usa PLAY del editor. Kotlin no decide gameplay en ese
modo: solo traduce touch, mantiene `SurfaceView` y renderiza el snapshot
serializado usando metadata de slices para `Sprite.source_slice` y
`Animator.slice_names`. Sin ese flag, el fallback Kotlin nativo v1 queda limitado
a escenas simples; escenas jugables fallan con `ANDROID_RUNTIME_REQUIRES_SHARED_RUNTIME`
y animaciones avanzadas fallan con `ANDROID_RUNTIME_UNSUPPORTED_ANIMATOR_ADVANCED`.

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
