# Export Presets

Configuracion de exportacion estilo Godot para MotorVideojuegosIA. Un archivo
`export_presets.motor.json` en la raiz del proyecto define todos los presets.

## Formato

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
      "include_all_assets": false,
      "console": false,
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

## Campos por preset

| Campo | Tipo | Obligatorio | Descripcion |
|---|---|---|---|
| `name` | string | Si | Identificador unico del preset. |
| `platform` | enum | Si | `windows`, `linux`, `macos`, `android`, `ios`. |
| `architecture` | enum | No | `x86_64`, `x86`, `arm64-v8a`, `armeabi-v7a`, `universal`. |
| `mode` | enum | No | `debug` o `release` (default: `release`). |
| `output_path` | string | Si | Ruta relativa de salida. |
| `entry_scene` | string | Si | Ruta a escena inicial (ej. `levels/main_menu_scene.json`). |
| `display_name` | string | No | Nombre visible del juego. |
| `application_id` | string | Si (mobile) | ID unico estilo `com.empresa.juego`. |
| `version_name` | string | No | Version legible (ej. `0.1.0`). |
| `version_code` | int | No | Codigo entero incremental (obligatorio en Android release). |
| `bundle_mode` | enum | No | `packed` (ZIP) o `directory` (archivos sueltos). Default: `packed`. |
| `include_debug_tools` | bool | No | Incluir tooling IA y debug en el export. Default: `false`. |
| `include_all_assets` | bool | No | Incluir todos los assets, no solo los alcanzables por grafo. |
| `console` | bool | No | Windows: forzar consola. Release normal usa `false`; debug o `include_debug_tools` usan consola. |
| `window` | object | No | Configuracion de ventana (solo desktop). |
| `min_sdk` | int | No | API level minimo Android. Default: `23`. |
| `target_sdk` | int | No | API level objetivo Android. Default: `35`. |
| `orientation` | string | No | `landscape`, `portrait`, `auto`. Default: `landscape`. |
| `extra` | object | No | Opciones especificas de plataforma (keystore, etc.). |

### Extra: Android release

```json
{
  "extra": {
    "keystore_path": "android/keystore.jks",
    "keystore_password": "storepass",
    "key_alias": "gamekey",
    "key_password": "keypass"
  }
}
```

Estos campos se redactan automaticamente (`[REDACTED]`) en build reports.

### Extra: Windows console

Windows release genera spec PyInstaller con `console=False` por defecto. Usa
`mode: "debug"`, `include_debug_tools: true` o `console: true` para generar
`console=True` y ver stdout/stderr en una terminal.

## Validacion

El schema valida automaticamente:

- Campos obligatorios por plataforma.
- Plataformas y modos validos.
- Entry scene existente.
- Output path sin traversal (`../`).
- Campos desconocidos rechazados (salvo extras documentados).
- `application_id` obligatorio en mobile.
- `version_code` obligatorio en Android release.

Errores accionables:

```json
{
  "code": "ENTRY_SCENE_NOT_FOUND",
  "path": "levels/main_menu_scene.json",
  "hint": "Create the scene or update export_presets.motor.json"
}
```

## Migraciones

`schema_version` en el archivo permite migraciones automaticas. Actualmente
solo existe `schema_version = 1`. La migracion se ejecuta al cargar presets;
si la version es desconocida, falla con diagnostico claro.

## CLI

```bash
# Listar todos los presets
py -m motor export presets list --project . --json

# Validar todos los presets
py -m motor export presets validate --project . --json

# Validar un preset especifico
py -m motor export presets validate --project . --name "Windows Desktop" --json
```

## EngineAPI

```python
from engine.api import EngineAPI

api = EngineAPI(project_root=".")
presets = api.list_export_presets()
result = api.validate_export_preset("Windows Desktop")
# result = {"success": True, "message": "...", "data": {...}}
api.shutdown()
```

## Multiples presets

Un archivo puede contener varios presets para distintas plataformas o modos:

```json
{
  "schema_version": 1,
  "presets": [
    {"name": "Windows Release", "platform": "windows", "mode": "release", ...},
    {"name": "Windows Debug",   "platform": "windows", "mode": "debug", ...},
    {"name": "Android Debug",   "platform": "android", "mode": "debug", ...}
  ]
}
```

Cada uno genera sus propios artefactos en `dist/export/` y su propio report en
`.motor/build/export_reports/`.

## Build con preset

```bash
# Empaquetar contenido sin build de plataforma
py -m motor export pack "Windows Desktop" --project . --json

# Build completo (content + plataforma)
py -m motor export build "Windows Desktop" --project . --json

# Build de todos los presets
py -m motor export build-all --project . --json
```
