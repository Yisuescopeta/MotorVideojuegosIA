# ADR 0001: Export Pipeline — Separación Editor/Runtime

- **Estado:** Implementado (2026-05-19)
- **Contexto:** Necesidad de exportar juegos jugables sin empaquetar el editor completo
- **Decisión:** Pipeline con presets, content pack, runtime separado, exporters por plataforma
- **Consecuencias:** Ver secciones abajo

## Contexto

Hasta 2026-05, el único mecanismo para distribuir juegos era empaquetar el editor/motor
completo vía `build/build_windows.py` con PyInstaller. Esto producía un ejecutable que
contenía paneles de editor, inspector, tooling IA, tests y documentación — inaceptable
para un juego final.

Objetivos:
1. Separar editor de runtime exportado.
2. Sistema de presets estilo Godot.
3. CLI oficial `motor export` como única interfaz pública.
4. Content pack reproducible con integridad verificable.
5. Build reports con errores accionables.
6. Exportadores por plataforma (Windows, Linux, macOS, Android, iOS).
7. No depender de toolchains externos para validación estructural.

## Decisión

### Arquitectura

```text
Proyecto editable
  -> validacion de presets
  -> grafo de contenido desde entry_scene
  -> content pack (game.manifest.json + game.pak)
  -> runtime template de plataforma
  -> artefacto jugable
  -> smoke test
  -> build report
```

El editor **no** es el entrypoint del juego exportado.

### Principios

1. `Scene` sigue siendo fuente persistente de verdad. `World` no se serializa como
   authoring durante export.
2. `EngineAPI` es la fachada pública para automatización de export. CLI, editor, tests
   y agentes pasan por ella.
3. `engine/runtime/exported_game.py` es el entrypoint del juego exportado. No importa
   `engine.editor`, `engine.inspector`, `tools`, `tests`, `docs`, `main`.
4. `export_presets.motor.json` es el único contrato de configuración de export.
5. Content pack determinista: mismo input produce mismo manifest lógico. Timestamp
   fijo (`SOURCE_DATE_EPOCH`), orden alfabético estable.
6. Integridad SHA-256: cada asset, scene y script en el manifest tiene hash SHA-256.
7. Reports sanitizados: keystore paths, passwords, tokens y API keys se redactan
   automáticamente.
8. `TOOLCHAIN_UNAVAILABLE` es un estado válido y documentado. El pipeline genera
   artefactos estructurales incluso cuando el build real falla por toolchain ausente.
9. `doctor` expone `healthy: bool`. Cuando PyInstaller o pip faltan, devuelve
   `success: false` con lista de issues/warnings.
10. Exportadores implementan `PlatformExporter` con `validate_environment()` y
    `export(ctx)`.

### Formato de presets

`export_presets.motor.json` en raíz del proyecto:

```json
{
  "schema_version": 1,
  "presets": [{...}]
}
```

Campos clave: `name`, `platform`, `mode`, `output_path`, `entry_scene`,
`display_name`, `application_id`, `bundle_mode`, `window`, `extra`.

Campos desconocidos fallan validación, salvo extras documentados como
`keystore_path`, `keystore_password`, `key_alias`, `key_password`, `include_all_assets`.

### CLI

```bash
py -m motor export presets list [--project .] [--json]
py -m motor export presets validate [--project .] [--name <preset>] [--json]
py -m motor export doctor [--project .] [--json]
py -m motor export pack <preset> [--project .] [--json]
py -m motor export build <preset> [--project .] [--json]
py -m motor export build-all [--project .] [--json]
```

### Content pack

Salida en `.motor/build/staging/<preset>/`:
- `game.manifest.json`: manifiesto con hashes SHA-256, GUIDs, entry scene, assets,
  scenes, scripts con dependencias.
- `game.pak`: ZIP determinista (timestamps fijos, orden estable).
- `content/`: assets, escenas, scripts alcanzables (modo `directory`).

El grafo de contenido recorre la entry_scene y sigue referencias estáticas por
campos JSON conocidos. Assets cargados dinámicamente por scripts requieren
`include_all_assets`.

### Build reports

En `.motor/build/export_reports/<preset>_<timestamp>.json`:

```json
{
  "schema_version": 1,
  "success": bool,
  "preset": "...",
  "platform": "...",
  "mode": "...",
  "engine_version": "...",
  "artifacts": [...],
  "warnings": [...],
  "errors": [...],
  "environment": {"python": "...", "os": "...", "pyinstaller": "..."}
}
```

Los reports se sanitizan automáticamente: keystore paths, passwords, API keys
se redactan con `[REDACTED]`.

### Exportadores

Cada plataforma tiene un exporter que implementa `PlatformExporter`:

| Plataforma | Clase | Toolchain requerida |
|---|---|---|
| Windows | `WindowsExporter` | PyInstaller |
| Linux | `LinuxExporter` | PyInstaller |
| macOS | `MacOSExporter` | macOS + PyInstaller + Xcode |
| Android | `AndroidExporter` | Android SDK, Build-Tools 34.0.0+, JDK 17+, Gradle 8.7+ |
| iOS | `IOSExporter` | macOS + Xcode |

Sin toolchain: `validate_environment()` falla, `export()` retorna `false`, se
genera build report con `TOOLCHAIN_UNAVAILABLE`. Los artefactos estructurales
(proyecto Android generado, content pack) se conservan.

### Runtime exportado

`engine/runtime/exported_game.py` soporta flags:

```bash
MyGame.exe                          # Normal (windowed, requiere pyray)
MyGame.exe --smoke-test             # Headless smoke test (60 frames)
MyGame.exe --headless --frames 3    # Headless con N frames
MyGame.exe --print-runtime-info     # Info de runtime y salida
```

Windowed requiere `pyray` o `raylib`; sin ellos, retorna `TOOLCHAIN_UNAVAILABLE`
con código 2. El modo headless carga la escena, ejecuta física/colisión N frames
y emite eventos.

## Consecuencias

### Positivas

- El juego exportado no contiene editor, inspector, tooling IA ni tests.
- Pipeline verificable: content pack → build report → exit code determinista.
- Validación temprana: `doctor` detecta toolchains faltantes antes de build.
- Separación clara de responsabilidades: `EngineAPI` para automatización,
  CLI para usuarios, UI futura sobre la misma API.

### Negativas

- Windowed runtime real requiere PyInstaller + pyray; sin ellas solo hay headless.
- Content graph no detecta assets cargados dinámicamente por scripts Python
  (requiere `include_all_assets` para cubrirlos).
- Android/iOS builds reales bloqueados por toolchains externas ausentes en el
  entorno de desarrollo actual.
- No hay panel de editor UI todavía; la interacción es solo CLI/API.

### Riesgos

- Si `export_presets.motor.json` se edita manualmente, errores de schema se
  detectan en validación pero no previenen el commit.
- Keystores de Android release no se copian al build report (solo referencia),
  pero el path se redacta en sanitización.

## Referencias

- `docs/export_pipeline.md` — documentación de uso y troubleshooting
- `docs/export_implementation_report.md` — reporte operativo de implementación
- `engine/api/_export_api.py` — ExportAPI delegate
- `engine/export/` — pipeline completo
- `engine/runtime/exported_game.py` — entrypoint de juego exportado
- `export_presets.motor.json` — presets del proyecto
- Plan: `docs/plans/active/export_build_pipeline.md`
