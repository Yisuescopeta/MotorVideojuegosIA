# Build Artifacts

Artefactos generados por el pipeline de exportacion: manifiestos, content packs,
ejecutables y reports.

## Estructura de salida

```
dist/export/<platform>/<GameName>/
  runtime_config.json       # Configuracion de runtime
  game.manifest.json        # Manifiesto con hashes y GUIDs
  game.pak                  # ZIP determinista (modo packed)
  content/                  # Assets sueltos (modo directory)
    assets/
    levels/
    scripts/
    prefabs/

.motor/build/staging/<preset>/
  game.manifest.json        # Manifiesto staging
  game.pak                  # Content pack staging

.motor/build/export_reports/
  <preset>_<timestamp>.json # Build report por preset
```

## game.manifest.json

Manifiesto determinista generado desde el grafo de contenido:

```json
{
  "schema_version": 1,
  "entry_scene": "levels/main_menu_scene.json",
  "generated_at_utc": "2026-05-19T12:00:00Z",
  "engine_version": "2026.03",
  "project": {
    "name": "My Game",
    "version": "0.1.0"
  },
  "scenes": [
    {
      "path": "levels/main_menu_scene.json",
      "sha256": "abc123...",
      "size_bytes": 4096,
      "guid": "scn_main_menu",
      "dependencies": ["levels/level1_scene.json"]
    }
  ],
  "assets": [
    {
      "guid": "ast_player",
      "path": "assets/player.png",
      "kind": "texture",
      "sha256": "def456...",
      "size_bytes": 1234,
      "dependencies": []
    }
  ],
  "scripts": [
    {
      "path": "scripts/player.py",
      "sha256": "ghi789...",
      "size_bytes": 2048,
      "sandbox": "game_script"
    }
  ]
}
```

### Determinismo

- Mismo input produce mismo manifest logico (orden alfabetico estable).
- `game.pak` usa timestamps fijos (`SOURCE_DATE_EPOCH=0`).
- Hashes SHA-256 de cada archivo.
- GUIDs estables derivados del path relativo.

## game.pak

ZIP determinista que empaqueta todo el contenido:

- Timestamps fijos (epoch 0) para reproducibilidad.
- Orden de entradas alfabetico estable.
- Mismo hash SHA-256 para mismo contenido.
- Se carga via `ContentLoader` usando `zipfile` con verificacion de integridad.

## Content graph

El grafo de contenido recorre la entry scene y sigue referencias estaticas:
- Scene flow links (`next_scene`, `menu_scene`, `target_scene`)
- Prefabs (`prefab_path`)
- Assets (`texture_path`, `asset_path`, `sprite_sheet`, etc.)
- Scripts (`script_path`)
- Materiales (`material_path`, `shader_path`)
- Tilemaps (`tileset_resource_path`)

### Limitaciones

Assets cargados dinamicamente por scripts Python (ej. `load_texture(nombre)`)
no se detectan. Para incluirlos, usar `include_all_assets: true` o
`mode: "debug"` en el preset.

### Exclusiones automaticas

- `.git/`
- `__pycache__/`, `.pytest_cache/`
- `.motor/build/`, `.motor/tmp/`
- `dist/`
- `tests/`
- `docs/`
- `build/`
- `engine/editor/`, `engine/inspector/`
- `tools/` (salvo debug preset)
- Archivos editor-only

## Build reports

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
  "started_at_utc": "2026-05-19T12:00:00Z",
  "finished_at_utc": "2026-05-19T12:00:18Z",
  "duration_seconds": 18.2,
  "artifacts": [
    {
      "path": "dist/export/windows/MyGame/MyGame.exe",
      "kind": "executable",
      "size_bytes": 12345678,
      "sha256": "abc123..."
    },
    {
      "path": "dist/export/windows/MyGame/game.pak",
      "kind": "content_pack",
      "size_bytes": 123456,
      "sha256": "def456..."
    }
  ],
  "warnings": [],
  "errors": [],
  "environment": {
    "python": "3.11",
    "os": "Windows",
    "pyinstaller": "6.x"
  }
}
```

### Sanitizacion

Los reports se sanitizan automaticamente:
- `keystore_path`, `keystore_password`, `key_alias`, `key_password` → `[REDACTED]`.
- Cualquier campo con `password`, `token`, `secret` o `api_key` → `[REDACTED]`.
- Flags de CLI con credenciales → `[REDACTED]`.

Esto previene filtracion accidental de credenciales en CI.

### Lectura de reports

```bash
# El CLI devuelve la ruta del report en data.report
py -m motor export build "Windows Desktop" --project . --json

# Los reports son JSON estandar, se pueden leer directamente
cat .motor/build/export_reports/Windows_Desktop_2026-05-19T120000Z.json
```

## Artefactos por plataforma

### Windows

```
dist/export/windows/MyGame/
  MyGame.exe                # Ejecutable standalone
  runtime_config.json       # Config de runtime
  game.manifest.json        # Manifiesto
  game.pak                  # Content pack
```

### Android

```
dist/export/android/
  MyGame-debug.apk          # APK debug
  MyGame-release.aab        # AAB release (con signing)

.motor/build/staging/Android_Debug/android_project/
  settings.gradle
  build.gradle
  app/src/main/assets/      # Content pack copiado
  app/src/main/AndroidManifest.xml
```

El proyecto Android se genera estructuralmente incluso si el build real falla
por toolchain ausente.
