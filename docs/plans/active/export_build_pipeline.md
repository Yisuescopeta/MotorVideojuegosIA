# Plan profesional: Export/Build Pipeline nivel Godot para MotorVideojuegosIA

> Documento base para que el agente Reina implemente de forma progresiva, verificable y profesional un sistema de exportación/build de juegos jugables para PC y móviles.
>
> Este documento es contrato de producto y arquitectura. No es una solución rápida. El objetivo es separar claramente editor, runtime, export templates, content bundle, presets, validación, empaquetado, firma y smoke tests.

---

## 0. Principio rector

El build oficial de juegos de MotorVideojuegosIA **no debe empaquetar el editor completo**.

Debe seguir este flujo:

```text
Proyecto editable
  -> validación
  -> grafo de contenido
  -> bundle/pack de contenido
  -> runtime template de plataforma
  -> paquete jugable
  -> smoke test
  -> build report
```

No este:

```text
Editor entero / main.py
  -> PyInstaller
  -> exe
```

La base actual del repo incluye empaquetado Windows del editor/motor con PyInstaller e Inno Setup. Esa base puede reutilizarse como referencia técnica, pero debe evolucionar hacia un sistema separado de exportación de juegos.

---

## 1. Objetivo de producto

Implementar en MotorVideojuegosIA un sistema profesional de exportación de juegos con estas capacidades:

1. Export presets estilo Godot.
2. Exportación por CLI oficial `motor`.
3. Content pack reproducible y verificable.
4. Runtime jugable separado del editor.
5. Exportadores por plataforma.
6. Build reports completos.
7. Smoke tests.
8. Validación de entorno.
9. Integración con `EngineAPI`.
10. Panel de exportación en editor cuando la CLI sea estable.
11. Soporte PC primero.
12. Soporte móvil mediante templates profesionales.
13. Documentación y tests suficientes para que ninguna implementación parcial sea considerada terminada.

---

## 2. Definición objetiva de "nivel Godot" para este motor

La funcionalidad se considera objetivamente "nivel Godot" para el alcance de este proyecto cuando existan y estén verificados todos estos puntos:

### 2.1 Presets

- Existe `export_presets.motor.json`.
- Permite varios presets por proyecto.
- Cada preset define plataforma, arquitectura, modo, entry scene, output, nombre de app, versión y opciones específicas.
- Hay validación de schema.
- Hay migración versionada para presets antiguos.
- Hay comandos CLI para listar, validar, construir y construir todos los presets.

### 2.2 Runtime separado del editor

- El juego exportado arranca con un entrypoint de runtime, no con el editor.
- El runtime exportado no depende de paneles del editor, inspector, herramientas de IA, tests ni tooling dev.
- El runtime carga `runtime_config.json` y un content pack.
- El runtime carga la escena inicial desde el pack.
- El runtime puede ejecutar un smoke test headless o equivalente.

### 2.3 Content pack

- Existe un builder de contenido que parte de escenas, assets, scripts, prefabs y metadatos.
- El pack incluye manifest con hashes, GUIDs, dependencias y entry scene.
- El pack es determinista: mismo input produce mismo manifest lógico.
- Hay verificación de integridad.
- Hay exclusión de archivos editor-only/dev-only.
- Hay tests de grafo de dependencias.

### 2.4 Exportadores

- Existe una interfaz común `PlatformExporter`.
- Existen exportadores separados para Windows, Linux, Android y stubs profesionales para plataformas no verificables en el entorno.
- Windows produce un ejecutable jugable.
- Android genera proyecto/template y APK debug como mínimo.
- Android release soporta AAB/keystore cuando el entorno lo permita.
- iOS queda implementado como exporter condicionado a macOS/Xcode, con validación clara de entorno y tests estructurales cuando no haya macOS.

### 2.5 CLI oficial

- Todo pasa por `py -m motor export ...`.
- No se depende de scripts sueltos como API pública.
- La salida JSON sigue el contrato del resto de la CLI:
  `{ "success": bool, "message": str, "data": object }`.

### 2.6 Reports

- Cada build genera un `build_report.json`.
- El report incluye preset, plataforma, modo, artefactos, hashes, warnings, errores, tiempos, versión del motor y entorno.
- Los errores son accionables.

### 2.7 Tests

- Tests unitarios para presets, validación, content graph, manifest, exporters y CLI.
- Smoke test desktop.
- Test estructural Android.
- Tests verdes con `unittest`, `ruff` y `mypy`, salvo exclusiones justificadas ya existentes en el repo.
- No se considera terminado si hay errores conocidos sin issue/documentación.

### 2.8 Documentación

- Documentación de uso para usuarios.
- Documentación de arquitectura para contribuidores.
- Guía de troubleshooting.
- Documentación de requisitos por plataforma.
- ADR de la decisión de arquitectura.

---

## 3. Referencia local Godot

El repo local contiene Godot aquí:

```text
C:\Users\Jesus\Documents\GitHub\MotorVideojuegosIA\godot\godot
```

Usar ese código **solo como referencia arquitectónica y conceptual**, no copiar código.

Áreas de Godot que conviene estudiar:

```text
editor/export/
platform/windows/
platform/linuxbsd/
platform/android/
platform/macos/
```

Conceptos a observar:

```text
ExportPreset
EditorExportPlatform
Export templates
PCK/ZIP pack
Debug vs Release
Signing
Android export
CLI export
Filtros de inclusión/exclusión
Validación por plataforma
```

La implementación debe adaptarse a MotorVideojuegosIA y respetar su arquitectura propia.

---

## 4. Estado inicial detectado en el repo

El repo ya tiene:

```text
build/build_windows.py
build/motorvideojuegos.spec
build/installer.iss
docs/building.md
```

Esta base empaqueta el editor/motor para Windows con PyInstaller e instalador opcional.

También existe base de asset pipeline:

```text
engine/assets/asset_database.py
engine/assets/asset_service.py
tools/asset_pipeline_cli.py
.motor/build/content_bundle.json
.motor/build/bundle_report.json
```

Esto permite reutilizar ideas de:

- catálogo de assets;
- GUIDs;
- hashes;
- artifacts;
- dependencies;
- bundles.

Pero el sistema actual debe convertirse en un export pipeline formal.

---

## 5. Arquitectura objetivo

```text
motor export build "<Preset>"
        |
        v
ExportPresetLoader
        |
        v
ExportValidator
        |
        v
BuildGraph
        |
        v
ContentPackBuilder
        |
        v
PlatformExporter
        |
        +--> WindowsExporter
        +--> LinuxExporter
        +--> MacOSExporter
        +--> AndroidExporter
        +--> IOSExporter
        |
        v
BuildReport
```

Runtime:

```text
ExportedGameRuntime
  -> RuntimeConfig
  -> ContentPack
  -> SceneManager.load_scene(...)
  -> Game.run()
```

---

## 6. Estructura nueva recomendada

Crear:

```text
engine/export/
  __init__.py
  models.py
  preset_loader.py
  preset_schema.py
  preset_migrations.py
  validator.py
  build_context.py
  build_graph.py
  content_collector.py
  content_pack.py
  artifact_writer.py
  exporter_registry.py
  platform_exporter.py
  desktop_exporter.py
  windows_exporter.py
  linux_exporter.py
  macos_exporter.py
  android_exporter.py
  ios_exporter.py
  diagnostics.py
  reports.py

engine/runtime/
  __init__.py
  exported_game.py
  bootstrap.py
  runtime_config.py
  content_loader.py

platforms/
  windows/
    templates/
  linux/
    templates/
  macos/
    templates/
  android/
    template/
  ios/
    template/

docs/
  export_pipeline.md
  export_presets.md
  runtime_templates.md
  build_artifacts.md
  mobile_export.md
  troubleshooting_export.md
  adr/
    0001-export-pipeline.md

tests/
  test_export_presets.py
  test_export_preset_migrations.py
  test_export_content_graph.py
  test_export_content_pack.py
  test_export_cli_contract.py
  test_export_windows_smoke.py
  test_export_android_project_generation.py
  test_export_reports.py
```

Modificar:

```text
motor/cli.py
motor/cli_core.py
engine/api/engine_api.py
docs/cli.md
docs/module_taxonomy.md
project.json schema/migration si aplica
```

Mantener como legacy o reconvertir:

```text
build/build_windows.py
build/motorvideojuegos.spec
docs/building.md
```

---

## 7. Formato de presets

Crear en la raíz del proyecto:

```text
export_presets.motor.json
```

Ejemplo inicial:

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
      "application_id": "com.yisuescopeta.mygame",
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
    },
    {
      "name": "Android Debug",
      "platform": "android",
      "architecture": "arm64-v8a",
      "mode": "debug",
      "output_path": "dist/export/android/MyGame-debug.apk",
      "entry_scene": "levels/main_menu_scene.json",
      "display_name": "My Game",
      "application_id": "com.yisuescopeta.mygame",
      "version_name": "0.1.0",
      "version_code": 1,
      "min_sdk": 23,
      "target_sdk": 35,
      "orientation": "landscape",
      "bundle_mode": "packed",
      "include_debug_tools": true
    }
  ]
}
```

Reglas:

- `name` único.
- `platform` enum.
- `mode` enum: `debug`, `release`.
- `entry_scene` obligatorio.
- `output_path` obligatorio.
- `application_id` obligatorio para mobile.
- `version_code` obligatorio para Android release.
- `schema_version` obligatorio.
- No aceptar campos desconocidos silenciosamente si pueden indicar error de usuario.

---

## 8. CLI objetivo

Añadir comandos:

```bash
py -m motor export presets list --project . --json
py -m motor export presets validate --project . --json
py -m motor export doctor --project . --json
py -m motor export pack "Windows Desktop" --project . --json
py -m motor export build "Windows Desktop" --project . --json
py -m motor export build "Android Debug" --project . --json
py -m motor export build-all --project . --json
```

Contrato JSON:

```json
{
  "success": true,
  "message": "Export completed",
  "data": {
    "preset": "Windows Desktop",
    "platform": "windows",
    "mode": "release",
    "artifacts": [
      "dist/export/windows/MyGame/MyGame.exe",
      "dist/export/windows/MyGame/game.pak"
    ],
    "report": ".motor/build/export_reports/windows-release-latest.json"
  }
}
```

Los errores deben ser accionables:

```json
{
  "success": false,
  "message": "Export preset validation failed",
  "data": {
    "errors": [
      {
        "code": "ENTRY_SCENE_NOT_FOUND",
        "path": "levels/main_menu_scene.json",
        "hint": "Create the scene or update export_presets.motor.json"
      }
    ]
  }
}
```

---

## 9. `EngineAPI`

Añadir métodos públicos:

```python
class EngineAPI:
    def list_export_presets(self) -> list[dict]: ...
    def validate_export_preset(self, name: str | None = None) -> dict: ...
    def export_pack(self, name: str) -> dict: ...
    def build_export(self, name: str) -> dict: ...
    def build_all_exports(self) -> dict: ...
    def export_doctor(self) -> dict: ...
```

Regla:

- CLI, editor, tests y agentes deben usar esta ruta o servicios compartidos.
- No duplicar lógica entre CLI y UI.

---

## 10. Runtime exportado

Crear entrypoint de juego exportado:

```text
engine/runtime/exported_game.py
```

Debe:

1. Leer `runtime_config.json`.
2. Leer `game.manifest.json` o `game.pak`.
3. Inicializar solo sistemas necesarios para juego.
4. Cargar `entry_scene`.
5. Ejecutar juego.
6. Permitir modo smoke/headless.

No debe importar de forma obligatoria:

```text
engine.editor.*
engine.inspector.*
tools.*
tests.*
docs.*
```

Debe soportar flags mínimos:

```bash
MyGame.exe --smoke-test
MyGame.exe --headless --frames 3
MyGame.exe --print-runtime-info
```

---

## 11. Content pack

Crear `ContentPackBuilder`.

Salidas iniciales:

```text
dist/export/<platform>/<game>/
  runtime_config.json
  game.manifest.json
  content/
    assets/
    levels/
    scripts/
    prefabs/
```

Salidas avanzadas:

```text
dist/export/<platform>/<game>/
  runtime_config.json
  game.manifest.json
  game.pak
```

Manifest:

```json
{
  "schema_version": 1,
  "entry_scene": "levels/main_menu_scene.json",
  "generated_at_utc": "...",
  "engine_version": "2026.03",
  "project": {
    "name": "My Game",
    "version": "0.1.0"
  },
  "assets": [
    {
      "guid": "ast_xxx",
      "path": "assets/player.png",
      "kind": "texture",
      "sha256": "...",
      "size_bytes": 1234,
      "dependencies": []
    }
  ],
  "scripts": [
    {
      "path": "scripts/player.py",
      "sha256": "...",
      "sandbox": "game_script"
    }
  ]
}
```

Requisitos:

- Hash SHA-256 de cada archivo.
- Manifest ordenado de forma estable.
- Copia segura sin salir del root del proyecto.
- Rechazar rutas absolutas peligrosas o traversal `../`.
- Incluir solo assets alcanzables desde la entry scene salvo opción explícita `include_all_assets`.
- Soportar exclusiones:
  - tests;
  - docs;
  - `.git`;
  - `.pytest_cache`;
  - build temp;
  - editor-only;
  - tooling IA, salvo debug/dev preset.

---

## 12. BuildGraph

Construir dependencias desde:

```text
entry_scene
  -> scene flow links
  -> prefabs
  -> sprite assets
  -> audio assets
  -> scripts
  -> materials
  -> tilemaps
  -> UI assets
```

El sistema actual ya detecta muchas dependencias por campos como:

```text
texture_path
asset_path
sprite_sheet
prefab_path
target_path
script_path
material_path
shader_path
```

Ampliar y testear esto para export.

El grafo debe producir:

```python
BuildGraphResult(
    entry_scene="levels/main_menu_scene.json",
    reachable_assets=[...],
    missing_assets=[...],
    warnings=[...],
)
```

No permitir build release si hay assets obligatorios faltantes.

---

## 13. Exportador Windows

Implementar:

```text
engine/export/windows_exporter.py
```

Debe:

1. Validar Python y PyInstaller/Nuitka.
2. Preparar staging dir.
3. Generar content pack.
4. Generar runtime config.
5. Generar spec temporal específico para juego.
6. Ejecutar build.
7. Copiar content pack.
8. Ejecutar smoke test.
9. Generar report.

Salida:

```text
dist/export/windows/MyGame/
  MyGame.exe
  runtime_config.json
  game.manifest.json
  game.pak o content/
  licenses/
```

No usar `main.py` como entrypoint.

Usar `engine/runtime/exported_game.py`.

---

## 14. Exportador Linux

Implementar después de Windows, con misma interfaz.

Salida inicial:

```text
dist/export/linux/MyGame/
  MyGame
  runtime_config.json
  game.manifest.json
  game.pak
```

Preparar para AppImage en fase posterior, pero no bloquear MVP.

---

## 15. Exportador macOS

Implementar estructura profesional:

```text
dist/export/macos/MyGame.app
```

Si el entorno no es macOS:

- no fallar tests generales;
- reportar `TOOLCHAIN_UNAVAILABLE`;
- mantener tests estructurales;
- documentar requisitos.

---

## 16. Exportador Android

Crear template:

```text
platforms/android/template/
  settings.gradle
  build.gradle
  app/
    build.gradle
    src/main/AndroidManifest.xml
    src/main/assets/
    src/main/res/
    src/main/java/
    src/main/cpp/ si aplica
```

El exporter debe:

1. Validar `ANDROID_HOME`.
2. Validar Java/JDK.
3. Validar Gradle.
4. Validar SDK.
5. Validar build-tools.
6. Validar NDK si se usa runtime nativo.
7. Generar proyecto temporal.
8. Copiar content pack a `app/src/main/assets/`.
9. Generar manifest Android.
10. Generar recursos básicos.
11. Ejecutar `assembleDebug`.
12. Copiar APK a `dist/export/android/`.
13. Generar report.

Release:

1. Validar keystore.
2. Generar AAB si se configura.
3. Firmar.
4. Reportar hashes.

Si el entorno no tiene Android SDK:

- los tests unitarios deben seguir pasando;
- los tests de Gradle real pueden saltarse con razón explícita;
- `motor export doctor` debe reportar qué falta;
- no marcar Android como completamente verificado.

---

## 17. Exportador iOS

iOS requiere macOS/Xcode.

Implementar:

```text
engine/export/ios_exporter.py
platforms/ios/template/
```

Si no hay macOS/Xcode:

- generar error accionable;
- mantener tests estructurales;
- documentar requisitos;
- no declarar iOS como verificado.

Runtime móvil profesional:

- Si Python/raylib-py no permite móvil sólido, documentar el bloqueo.
- Preparar diseño para runtime nativo progresivo.
- No resolver móvil con un hack frágil.

---

## 18. Panel de editor

Cuando CLI esté estable, crear:

```text
engine/editor/export_panel.py
```

Funciones:

- listar presets;
- crear preset;
- duplicar preset;
- validar preset;
- build preset;
- abrir carpeta de salida;
- ver último build report.

Regla:

- La UI solo llama a `EngineAPI`.
- No duplicar lógica en UI.
- No hacer que la UI sea requisito para automatización.

---

## 19. Build reports

Generar reports en:

```text
.motor/build/export_reports/
```

Ejemplo:

```json
{
  "schema_version": 1,
  "success": true,
  "preset": "Windows Desktop",
  "platform": "windows",
  "mode": "release",
  "engine_version": "2026.03",
  "project_name": "MyGame",
  "entry_scene": "levels/main_menu_scene.json",
  "started_at_utc": "...",
  "finished_at_utc": "...",
  "duration_seconds": 18.2,
  "artifacts": [
    {
      "path": "dist/export/windows/MyGame/MyGame.exe",
      "kind": "executable",
      "size_bytes": 12345678,
      "sha256": "..."
    },
    {
      "path": "dist/export/windows/MyGame/game.pak",
      "kind": "content_pack",
      "size_bytes": 123456,
      "sha256": "..."
    }
  ],
  "warnings": [],
  "errors": [],
  "environment": {
    "python": "3.11",
    "os": "Windows",
    "pyinstaller": "x.y.z"
  }
}
```

---

## 20. Seguridad y robustez

Validar:

- rutas relativas;
- no traversal;
- no symlink peligroso fuera del proyecto;
- no escritura fuera de `dist/` o `.motor/build/` salvo configuración explícita;
- scripts incluidos conscientemente;
- no meter secretos en reports;
- keystores referenciados, no copiados al build report;
- permisos móviles mínimos.

---

## 21. Tests obligatorios

Crear y mantener:

```text
tests/test_export_presets.py
tests/test_export_preset_migrations.py
tests/test_export_content_graph.py
tests/test_export_content_pack.py
tests/test_export_cli_contract.py
tests/test_export_reports.py
tests/test_export_windows_smoke.py
tests/test_export_android_project_generation.py
```

Comandos mínimos antes de considerar terminada una fase:

```bash
py -m unittest tests.test_export_presets -v
py -m unittest tests.test_export_content_graph -v
py -m unittest tests.test_export_content_pack -v
py -m unittest tests.test_export_cli_contract -v
py -m unittest tests.test_export_reports -v
py -m unittest discover -s tests
py -m ruff check engine cli tools main.py
py -m mypy engine cli tools main.py
```

Además:

```bash
py -m motor export doctor --project . --json
py -m motor export presets validate --project . --json
py -m motor export pack "Windows Desktop" --project . --json
py -m motor export build "Windows Desktop" --project . --json
```

Si el entorno tiene Android SDK:

```bash
py -m motor export build "Android Debug" --project . --json
```

---

## 22. Fases de implementación

### Fase 1 — Diseño y contratos

Entregables:

- ADR.
- Docs base.
- Modelos de presets.
- Loader y validator.
- Tests de presets.

No construir todavía.

### Fase 2 — CLI base

Entregables:

- `motor export presets list`.
- `motor export presets validate`.
- `motor export doctor`.
- Salida JSON estable.
- Tests CLI.

### Fase 3 — Build graph y content pack

Entregables:

- `BuildGraph`.
- `ContentPackBuilder`.
- `game.manifest.json`.
- `content/` staging.
- Tests de dependencias.
- Tests de manifest determinista.

### Fase 4 — Runtime exportado

Entregables:

- `engine/runtime/exported_game.py`.
- `runtime_config.json`.
- modo smoke/headless.
- carga de entry scene.
- tests básicos.

### Fase 5 — Windows exporter

Entregables:

- `WindowsExporter`.
- PyInstaller spec temporal para runtime.
- build jugable.
- smoke test.
- build report.

### Fase 6 — Desktop común

Entregables:

- `DesktopExporter`.
- Linux exporter inicial.
- macOS exporter estructural.
- reports por plataforma.

### Fase 7 — Android template

Entregables:

- template Gradle.
- generación de proyecto Android.
- assets en `src/main/assets`.
- AndroidManifest generado.
- tests estructurales.

### Fase 8 — Android debug real

Entregables:

- `assembleDebug`.
- APK.
- report.
- smoke básico si hay emulador/dispositivo.

### Fase 9 — Android release

Entregables:

- keystore config.
- signing.
- AAB.
- docs de publicación.
- validaciones.

### Fase 10 — iOS estructural

Entregables:

- exporter iOS.
- template Xcode o generador.
- validación macOS/Xcode.
- docs.
- tests estructurales.

### Fase 11 — Editor UI

Entregables:

- panel de export.
- uso de `EngineAPI`.
- docs de usuario.

### Fase 12 — Hardening final

Entregables:

- suite completa verde.
- ruff verde.
- mypy verde o exclusiones justificadas.
- docs actualizadas.
- build reports.
- troubleshooting.
- revisión de arquitectura.
- limpieza de legacy.

---

## 23. Política de no finalización prematura

El agente no debe declarar la tarea terminada hasta que:

1. Todas las fases aplicables estén implementadas.
2. Todos los comandos de test requeridos se hayan ejecutado.
3. Los errores detectados estén corregidos.
4. Las plataformas no verificables por falta de toolchain estén documentadas como bloqueador externo, con tests estructurales pasando.
5. Exista un reporte final en markdown con:
   - fases completadas;
   - archivos modificados;
   - comandos ejecutados;
   - resultados;
   - limitaciones reales;
   - siguientes pasos si dependen de SDKs, firmas o hardware externo.

No usar frases como "debería funcionar" sin test asociado.

---

## 24. Criterios de aceptación finales

La funcionalidad queda aceptada cuando:

- `py -m motor export presets list --project . --json` funciona.
- `py -m motor export presets validate --project . --json` funciona.
- `py -m motor export doctor --project . --json` funciona.
- `py -m motor export pack "Windows Desktop" --project . --json` genera manifest y pack.
- `py -m motor export build "Windows Desktop" --project . --json` genera juego ejecutable.
- El ejecutable exportado arranca sin editor.
- El ejecutable exportado carga la escena inicial.
- El smoke test pasa.
- El build report incluye artefactos y hashes.
- Android genera proyecto/template.
- Android genera APK debug cuando el SDK está disponible.
- Android release genera AAB cuando signing y SDK están disponibles.
- iOS reporta correctamente requisitos si no hay macOS/Xcode.
- La documentación explica cómo usar todo.
- La arquitectura no duplica lógica entre CLI y UI.
- No hay tests rotos.
- No hay lint/typecheck roto sin justificación explícita.
