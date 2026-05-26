# Reporte de Implementacion: Export/Build Pipeline

Fecha: 2026-05-19
Plan base: `docs/plans/active/export_build_pipeline.md`
Estado: `partial` por toolchains externos ausentes y una regresion no relacionada en full discover.

## Resumen

Sistema de export/build implementado sobre `EngineAPI` y CLI oficial `motor`. El flujo separa editor y runtime, valida presets, genera grafo de contenido, `game.manifest.json`, `game.pak`, runtime config, exporters por plataforma y build reports en `.motor/build/export_reports/`.

## Fases completadas

| Fase | Estado |
|---|---|
| 1 Presets/contratos | Completada |
| 2 CLI base | Completada |
| 3 Build graph/content pack | Completada y endurecida |
| 4 Runtime exportado | Completada; carga `content/` o `game.pak` |
| 5 Windows exporter | Implementado; build real bloqueado por PyInstaller ausente |
| 6 Linux/macOS | Implementado estructural; macOS condicionado a host/Xcode |
| 7 Android template | Implementado |
| 8 Android debug | Implementado; APK bloqueado por `ANDROID_HOME`/Gradle ausentes |
| 9 Android release | Implementado con config de keystore cuando toolchain exista |
| 10 iOS estructural | Implementado; bloqueado fuera de macOS/Xcode |
| 11 Editor UI | No implementado; plan lo deja posterior a CLI estable |
| 12 Hardening | Parcial: export tests y ruff pasan; mypy/full discover tienen deuda externa indicada abajo |

## Documentacion completada

| Documento | Estado |
|---|---|
| `docs/export_pipeline.md` | Creado — arquitectura, CLI, content pack, exporters, troubleshooting |
| `docs/export_presets.md` | Creado — formato, schema, validacion, migraciones, CLI, EngineAPI |
| `docs/runtime_templates.md` | Creado — entrypoint, flags, runtime config, plataformas, smoke test |
| `docs/build_artifacts.md` | Creado — manifiesto, game.pak, content graph, reports, determinismo |
| `docs/mobile_export.md` | Creado — Android/iOS requisitos, templates, builds, keystore, doctor |
| `docs/troubleshooting_export.md` | Creado — errores comunes, TOOLCHAIN_UNAVAILABLE, diagnostico paso a paso |
| `docs/adr/0001-export-pipeline.md` | Creado — ADR con decisiones de arquitectura |
| `docs/export_implementation_report.md` | Este documento |
| `docs/README.md` | Actualizado — index de nuevos docs en canon y referencia |
| `docs/architecture.md` | Actualizado — export section con links a docs nuevos |
| `docs/TECHNICAL.md` | Actualizado — export section con links a docs nuevos |
| `docs/schema_serialization.md` | Actualizado — presets/manifest con links a docs nuevos |
| `docs/cli.md` | Actualizado — export section con links a docs nuevos |
| `docs/api.md` | Actualizado — export section con links a docs nuevos |

## Archivos creados

- `engine/export/*` pipeline modular de exportacion.
- `engine/runtime/*` runtime separado del editor.
- `platforms/android/template/*` template Gradle Android.
- `platforms/ios/template/*` template estructural iOS.
- `tests/test_export_presets.py`
- `tests/test_export_preset_migrations.py`
- `tests/test_export_content_graph.py`
- `tests/test_export_content_pack.py`
- `tests/test_export_cli_contract.py`
- `tests/test_export_reports.py`
- `tests/test_export_windows_smoke.py`
- `tests/test_export_android_project_generation.py`
- `docs/export_pipeline.md`
- `docs/export_presets.md`
- `docs/runtime_templates.md`
- `docs/build_artifacts.md`
- `docs/mobile_export.md`
- `docs/troubleshooting_export.md`
- `docs/export_implementation_report.md`
- `docs/adr/0001-export-pipeline.md`

## Archivos modificados

- `engine/api/_export_api.py`: metodos publicos export, validacion por nombre, export_doctor con healthy flag, artifacts en respuesta con SHA-256.
- `engine/api/engine_api.py`: wrappers explicitos para ExportAPI + editor API requeridos por auditoria de registry.
- `engine/ai/registry_builder.py`: registro de 6 capabilities de export en motor_ai.json.
- `engine/export/build_context.py`: hashes SHA-256 de artefactos, add_artifact con hash automatico.
- `engine/export/build_graph.py`: bloqueo de rutas absolutas/traversal.
- `engine/export/content_collector.py`: GUID estable, copia segura, `game.pak` determinista.
- `engine/export/content_pack.py`: timestamp reproducible (`SOURCE_DATE_EPOCH`) y soporte `include_all_assets`.
- `engine/export/diagnostics.py`: run_export_doctor con checks de PyInstaller, pip, ANDROID_HOME, Java, Gradle y flag `healthy`.
- `engine/export/preset_schema.py`: campos desconocidos, `console` Windows, application id y version_code Android.
- `engine/export/reports.py`: build reports sanitizados (keystore/password/token redacted), artifact hashes.
- `engine/export/validator.py`: validacion segura de entry scene/output.
- `engine/export/windows_exporter.py`: runtime config/manifest/pak en salida, spec con datas absolutas, `console=False` en release, imports/binarios raylib y smoke test post-build.
- `engine/export/android_exporter.py`: genera proyecto Android antes de bloquear por SDK externo.
- `engine/runtime/content_loader.py`: carga manifest desde `game.pak`.
- `engine/runtime/exported_game.py`: runtime headless usa `content/` como root del juego exportado. Soporta flags --smoke-test, --headless, --print-runtime-info. Windowed requiere pyray/raylib; sin ellos retorna TOOLCHAIN_UNAVAILABLE y si raylib no crea ventana retorna codigo 2 con error claro.
- `engine/runtime/runtime_config.py`: conserva base path del runtime.
- `tests/test_export_cli_contract.py`: contrato JSON, validate con --name, doctor healthy, pack/build error toolchain.
- `docs/README.md`, `docs/api.md`, `docs/cli.md`, `docs/schema_serialization.md`, `docs/architecture.md`, `docs/TECHNICAL.md`, `docs/agents.md`, `docs/module_taxonomy.md`.
- `docs/export_pipeline.md`: documentacion de uso, arquitectura y troubleshooting.
- `docs/export_presets.md`: formato, schema, validacion, CLI y EngineAPI de presets.
- `docs/runtime_templates.md`: entrypoint, flags, plataformas y smoke test.
- `docs/build_artifacts.md`: manifiesto, game.pak, content graph, reports y determinismo.
- `docs/mobile_export.md`: requisitos, templates y builds Android/iOS.
- `docs/troubleshooting_export.md`: diagnostico de errores comunes.
- `docs/adr/0001-export-pipeline.md`: ADR con decisiones de arquitectura (separacion editor/runtime, content pack determinista, SHA-256, reports sanitizados, TOOLCHAIN_UNAVAILABLE).

## Comandos ejecutados

| Comando | Resultado |
|---|---|
| `py -m unittest tests.test_export_presets tests.test_export_preset_migrations tests.test_export_content_graph tests.test_export_content_pack tests.test_export_cli_contract tests.test_export_reports tests.test_export_windows_smoke tests.test_export_android_project_generation -v` | OK, 71 tests |
| `py -m motor export presets list --project . --json` | OK, 2 presets |
| `py -m motor export presets validate --project . --json` | OK |
| `py -m motor export presets validate --project . --name "Windows Desktop" --json` | OK, preset especifico |
| `py -m motor export doctor --project . --json` | OK; `healthy` depende de toolchains instalados en el entorno local |
| `py -m motor export doctor --project . --json \| python -c "import sys,json; d=json.load(sys.stdin); print(d['data']['healthy'])"` | healthy flag verificada |
| `py -m motor export pack "Windows Desktop" --project . --json` | OK; genero manifest y `game.pak` |
| `py -m motor export build "Windows Desktop" --project . --json` | OK cuando PyInstaller esta instalado; genera `My_Game.exe`, runtime config, manifest y `game.pak` |
| `py -m motor export build "Android Debug" --project . --json` | Falla accionable: `ANDROID_HOME` ausente; proyecto Android staging generado |
| `py -m ruff check engine cli tools main.py` | OK |
| `py -m mypy engine/export engine/runtime engine/api/_export_api.py` | OK |
| `py -m mypy engine cli tools main.py` | Falla por errores existentes en editor UI/theme/asset_browser, fuera de export |
| `py -m unittest tests.test_capability_registry_audit -v` | OK |
| `py -m motor capabilities --project . --json \| python -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('capabilities',[])))"` | 6 nuevas capabilities export en registry |
| `py -m motor doctor --project . --json` | Export doctor integrado OK |
| `py -m unittest discover -s tests -v -f` | Falla en `tests.test_character_controller.CharacterControllerTests.test_floor_snap_every_frame`, fuera de export |

## Artefactos generados

- `.motor/build/staging/Windows_Desktop/game.manifest.json`
- `.motor/build/staging/Windows_Desktop/game.pak`
- `.motor/build/staging/Windows_Desktop/content/`
- `.motor/build/staging/Android_Debug/android_project/`
- `.motor/build/export_reports/Windows_Desktop_*.json`
- `.motor/build/export_reports/Android_Debug_*.json`

## Plataformas verificadas

- Windows: validacion, pack, build, report y smoke test del ejecutable verificados cuando PyInstaller esta instalado.
- Android: template/proyecto generado y bloqueo SDK verificado. APK no verificado por `ANDROID_HOME` ausente.
- Linux/macOS/iOS: estructura/imports/tests de exporter verificados; builds reales dependen de host/toolchain.

## Registry y motor_ai.json

- `engine/ai/registry_builder.py` registra 6 capabilities de export:
  `export:presets:list`, `export:presets:validate`, `export:doctor`,
  `export:pack`, `export:build`, `export:build-all`.
- `motor_ai.json` incremento de 112 a 118 capabilities implementadas (+6 export).
- `py -m motor ai start --project . --json` incluye las nuevas capabilities.

## Plataformas bloqueadas por entorno

- Windows/Linux desktop real: requiere PyInstaller instalado en el interprete activo.
- Android APK/AAB: falta `ANDROID_HOME`; Gradle no esta en PATH.
- macOS/iOS: requiere macOS y Xcode.

## Limitaciones reales

- Windows release genera PyInstaller `console=False`; debug, `include_debug_tools` o `console: true` generan `console=True`.
- Runtime windowed intenta pyray/raylib; si no estan disponibles, retorna `TOOLCHAIN/RUNTIME_UNAVAILABLE` con codigo 2. Si raylib no crea ventana, retorna codigo 2 con `ERROR: raylib window was not created`. Smoke/headless funcionan sin dependencias graficas y no validan ventana real, render, input real ni UI interactiva.
- Build reports se sanitizan automaticamente: keystore paths, passwords, tokens y API keys se redactan.
- Doctor expone `healthy: bool`. Con PyInstaller ausente, healthy=false y API retorna success=false.
- Content graph detecta referencias estaticas por campos JSON conocidos; assets cargados dinamicamente por scripts requieren `include_all_assets`.
- `py -m unittest discover -s tests` no queda verde por fallo de `CharacterController2D` no relacionado con export.
- `py -m mypy engine cli tools main.py` no queda verde por deuda de tipado en editor UI/theme/asset_browser no relacionada con export.
