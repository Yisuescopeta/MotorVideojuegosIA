# Queen Execution Plan: Nintendo Switch Build

Status: active
Authority: operational-plan
Task ID: queen-20260531-001
Created at: 2026-05-31T22:29:43+02:00
Updated at: 2026-05-31T22:29:43+02:00
Mode: long-task-plan

## Objective

Implementar, en fases posteriores, un build oficial para Nintendo Switch 1 que
permita jugar en devkit a juegos creados con MotorVideojuegosIA.

El resultado buscado es equivalente al modelo de Godot: el usuario edita el
juego en el motor, exporta desde presets, y obtiene un paquete jugable para la
consola. El paquete no incluye editor, inspector, herramientas de authoring,
Queen, agentes IA, tests, docs ni hot reload. Solo incluye lo minimo necesario
para ejecutar el juego exportado con los mismos datos y la misma semantica de
PLAY.

Principio bloqueante: jugar en editor con PLAY y jugar en Switch debe producir
el mismo comportamiento de gameplay para las features soportadas. No se acepta
un runtime Switch que haga reglas distintas, fisica distinta, input semantico
distinto, scene flow distinto o mutaciones de authoring accidentales.

## Context And Constraints

- Target inicial: Nintendo Switch 1.
- Toolchain: SDK oficial de Nintendo, devkit y acceso autorizado mediante
  Nintendo Developer Portal.
- No se versiona SDK privado, headers, librerias, templates propietarios,
  ejemplos bajo NDA, rutas reales de SDK, claves, certificados ni material de
  Nintendo.
- Si falta SDK/devkit, el exporter debe fallar con diagnostico accionable
  `TOOLCHAIN_UNAVAILABLE`, sin generar artefactos falsamente jugables.
- Godot se usa como referencia arquitectonica de export presets, templates y
  separacion editor/runtime. Godot no publica codigo Switch oficial por NDA; el
  plan no debe buscar ni copiar codigo Switch cerrado.
- Fuentes publicas:
  - [Godot console support](https://docs.godotengine.org/en/4.0/tutorials/platform/consoles.html)
  - [Nintendo Developer Portal](https://developer.nintendo.com/register)

## Non-Goals

- No implementar homebrew, emuladores, bypasses, exploits ni flujos no
  oficiales.
- No convertir la Switch en entorno para crear juegos dentro del motor.
- No empaquetar `main.py`, editor, inspector, herramientas IA, tests, docs ni
  tooling de desarrollo.
- No crear un mini motor paralelo con comportamiento distinto al PLAY del
  editor.
- No cambiar `Scene` como fuente persistente de verdad ni serializar `World`
  runtime como authoring.
- No tocar fisica publica fuera de una fase dedicada y justificada.
- No prometer publicamente soporte Switch hasta que haya codigo, tests,
  toolchain validada y docs canonicas actualizadas.

## Technical Direction

El trabajo futuro debe extender el pipeline actual:

```text
motor export build "<Nintendo Switch Preset>"
  -> ExportPresetLoader
  -> ExportValidator
  -> BuildGraph
  -> ContentPackBuilder
  -> NintendoSwitchExporter
  -> Switch template/player
  -> paquete jugable para devkit
  -> parity report + build report
```

La base a reutilizar:

- `ExportPreset` para declarar `platform: "nintendo_switch"`.
- `PlatformExporter` para el futuro `NintendoSwitchExporter`.
- `ContentPackBuilder` para `game.manifest.json`, `game.pak` y contenido
  determinista.
- `BuildReport` para artefactos, hashes, warnings, errores y entorno.
- `SharedGameRuntime` como contrato de comportamiento PLAY/export, salvo que
  una fase de research demuestre que el SDK exige un player nativo equivalente.

El template/player Switch puede ser nativo o hibrido, pero debe pasar por una
capa de paridad: mismos datos de escena, mismo orden de sistemas, misma
semantica de input, misma resolucion de scene flow y mismos eventos observables.

## Public Interfaces To Add Later

- `export_presets.motor.json`
  - `platform: "nintendo_switch"`
  - `architecture`: valor final dependiente del SDK oficial.
  - `output_path`: ruta relativa bajo `dist/export/switch/...`.
  - `entry_scene`, `display_name`, `application_id`, `version_name`,
    `version_code`, `bundle_mode`, `include_debug_tools`.
  - `extra`: solo campos no secretos o referencias a variables de entorno.

- `NintendoSwitchExporter`
  - Registrado en `ExporterRegistry`.
  - Implementa `validate_environment()` y `export(ctx)`.
  - Nunca importa SDK privado si el entorno no esta configurado.
  - Nunca escribe secrets en reports.

- Toolchain local
  - Variables abstractas previstas: `NINTENDO_SDK_ROOT`,
    `NINTENDO_SWITCH_DEVKIT_ID`, `MOTOR_SWITCH_TEMPLATE_ROOT`.
  - Nombres finales se decidiran solo tras leer la documentacion oficial bajo
    acceso autorizado.

- CLI
  - Se reutiliza `py -m motor export presets validate --project . --json`.
  - Se reutiliza `py -m motor export doctor --project . --json`.
  - Se reutiliza `py -m motor export build "<preset>" --project . --json`.
  - No crear CLI paralela.

## Phases

### Phase 1 - Legal, SDK And Toolchain Contract

Status: pending

Goal: definir el contrato real de toolchain sin versionar material privado.

Work:
- Confirmar requisitos oficiales: SDK, devkit, host soportado, compilador,
  packaging, firma debug/devkit, limites de distribucion y salida generada.
- Definir variables de entorno y rutas locales permitidas.
- Crear matriz de bloqueo: sin SDK, sin devkit, sin credenciales, host no
  soportado, template privado ausente.
- Decidir si el player Switch sera nativo completo, wrapper sobre runtime
  compartido, o template hibrido. La decision debe basarse en SDK oficial y en
  paridad con PLAY.

Acceptance:
- Documento interno de decision sin secretos.
- Lista de diagnosticos `TOOLCHAIN_UNAVAILABLE` esperados.
- Cero SDK privado en git.
- Cero promesa de soporte publico antes de implementacion.

### Phase 2 - Preset Nintendo Switch And Validation

Status: pending

Goal: aceptar `platform: "nintendo_switch"` en presets sin ejecutar builds aun.

Work:
- Extender enums/schema de export presets.
- Validar `application_id`, `entry_scene`, `output_path`, `mode`,
  `bundle_mode` y campos Switch permitidos.
- Rechazar campos desconocidos.
- Mantener migraciones de preset versionadas si cambia schema.

Acceptance:
- `validate_export_preset` reconoce Switch.
- Presets invalidos fallan con codigos accionables.
- Tests de schema, migracion y CLI cubren el nuevo target.
- Docs canonicas de presets actualizadas solo cuando el soporte exista en
  codigo.

### Phase 3 - Switch Content Pack Without Gameplay Forks

Status: pending

Goal: producir staging Switch con el mismo `game.pak`/manifest y sin contenido
editor-only.

Work:
- Reutilizar content graph actual para escenas, assets, scripts y prefabs.
- Anadir exclusiones especificas de Switch solo si la plataforma lo requiere.
- Verificar hashes SHA-256 y paths seguros.
- Preparar `runtime_config.json` con campos Switch no secretos.

Acceptance:
- Mismo proyecto produce pack determinista.
- El pack no incluye editor, inspector, tests, docs, `.motor/tmp` ni SDK.
- Assets dinamicos siguen la politica actual: metadata, `include_all_assets` o
  debug mode.

### Phase 4 - Switch Template/Player Without Editor

Status: pending

Goal: crear template/player que arranque en devkit y cargue `game.pak`.

Work:
- Crear estructura `platforms/nintendo_switch/template/` solo con placeholders
  publicos o archivos propios del motor.
- Integrar SDK privado mediante rutas externas al repo.
- Arrancar desde `runtime_config.json`, manifest y content pack.
- Exponer errores visibles/logueables si falta contenido o falla la escena.
- Mantener `Scene` como verdad persistente y `World` como proyeccion runtime.

Acceptance:
- No importa ni empaqueta editor/inspector/tooling.
- No hay rutas absolutas ni SDK privado en outputs versionados.
- El template falla cerrado si falta toolchain.

### Phase 5 - Platform Adapters: Input, Render, Audio, Storage

Status: pending

Goal: mapear APIs de consola a contratos existentes sin cambiar gameplay.

Work:
- Input: mapear Joy-Con/Pro Controller a acciones `InputMap` existentes.
- Render: adaptar backend grafico a `RenderSystem` o a un snapshot equivalente
  probado por paridad.
- Audio: conectar `AudioSystem` a backend Switch o declarar bloqueante si falta.
- Storage: lectura de `game.pak`, saves/config runtime y logs sin tocar
  authoring.
- Window/display: usar resolucion/perfil Switch sin alterar coordenadas de
  gameplay.

Acceptance:
- Input produce los mismos estados logicos que PLAY.
- Scene flow, UI, scripts, animacion, fisica y eventos mantienen semantica.
- No hay mutacion persistente accidental durante runtime.

### Phase 6 - Official Toolchain Build And Devkit Artifact

Status: pending

Goal: generar artefacto jugable para devkit con SDK oficial.

Work:
- Implementar `NintendoSwitchExporter.export(ctx)`.
- Invocar toolchain sin shell insegura cuando sea posible.
- Copiar artefactos al `output_path`.
- Registrar hashes y tamanos en build report.
- Separar debug/release segun SDK oficial.

Acceptance:
- Build con SDK/devkit configurado genera artefacto instalable/ejecutable en
  devkit.
- Build sin SDK falla con `TOOLCHAIN_UNAVAILABLE` y report claro.
- Extension exacta del artefacto queda definida por SDK oficial, no inventada.

### Phase 7 - PLAY vs Switch Parity Harness

Status: pending

Goal: bloquear divergencias entre editor PLAY y Switch.

Work:
- Crear trazas de referencia desde PLAY/headless: seed, input timeline, frames,
  eventos, transforms clave, escena activa, hashes de estado logico.
- Ejecutar la misma escena/input en Switch o en runner oficial permitido.
- Comparar tolerancias numericas explicitas para fisica/render-independent
  state.
- Fallar build si una feature usada por el juego no tiene soporte equivalente.

Acceptance:
- Parity report por build.
- Diferencias en gameplay son errores, no warnings.
- Si una feature no puede validarse en host local, queda marcada como bloqueante
  hasta prueba en devkit.

### Phase 8 - Doctor, Reports And Actionable Errors

Status: pending

Goal: diagnosticos claros para usuarios y agentes.

Work:
- Extender `export_doctor` con checks Switch no secretos.
- Sanitizar paths, variables y secretos en reports.
- Agregar codigos de error: SDK ausente, devkit ausente, template privado
  ausente, host incompatible, signing/devkit config incompleta, parity failed.
- Mantener formato `{ "success": bool, "message": str, "data": object }`.

Acceptance:
- Reports no filtran SDK paths sensibles, tokens, certificados ni claves.
- Errores indican accion concreta.
- Tests cubren sanitizacion.

### Phase 9 - Canonical Docs And Final Acceptance

Status: pending

Goal: promocionar soporte Switch solo cuando sea verificable.

Work:
- Actualizar docs canonicas correspondientes:
  - `docs/export_pipeline.md`
  - `docs/export_presets.md`
  - `docs/runtime_templates.md`
  - `docs/build_artifacts.md`
  - `docs/cli.md`
  - `docs/api.md`
  - `docs/TECHNICAL.md`
  - `docs/documentation_governance.md` si cambia gobernanza documental.
- Documentar limitaciones reales: SDK privado, devkit requerido, no soporte
  sin autorizacion Nintendo.
- Anadir troubleshooting Switch sin secretos.

Acceptance:
- Docs no presentan Switch como disponible antes de que los tests/builds lo
  respalden.
- Tests enfocados pasan.
- Review sin hallazgos must-fix.
- AI-friendliness score >= 90 si aplica.

## Suggested Validation Commands For Future Implementation

```bash
py -m unittest tests.test_export_presets tests.test_export_cli_contract -v
py -m unittest tests.test_export_content_graph tests.test_export_content_pack -v
py -m unittest tests.test_export_reports tests.test_repository_governance -v
py -m motor export presets validate --project . --json
py -m motor export doctor --project . --json
```

Cuando exista SDK/devkit configurado:

```bash
py -m motor export build "Nintendo Switch Debug" --project . --json
```

## Definition Of Done

- `platform: "nintendo_switch"` soportado por schema, API y CLI.
- `NintendoSwitchExporter` registrado y probado.
- Build sin SDK falla con diagnostico correcto.
- Build con SDK oficial genera artefacto jugable en devkit.
- El paquete no incluye editor, inspector, tests, docs, Queen ni tooling IA.
- Parity harness demuestra comportamiento equivalente a PLAY para el juego
  exportado.
- Build report incluye artefactos, hashes, warnings, errores y parity report.
- Docs canonicas actualizadas solo cuando el soporte sea real.
- No hay SDK privado ni secretos en git.

## Open Risks

- El SDK oficial puede imponer arquitectura, empaquetado, firma o host que no
  puede conocerse desde fuentes publicas.
- `SharedGameRuntime` puede no ser portable tal cual; si ocurre, el player
  nativo debe replicar el contrato de sistemas sin cambiar gameplay.
- Scripts Python pueden requerir estrategia dedicada si el entorno Switch no
  permite embebido equivalente.
- Render/audio/input pueden exigir backends nativos nuevos; cada backend debe
  pasar por parity harness antes de marcarse soportado.
- Cualquier restriccion NDA debe mantenerse fuera de este repo publico/local
  versionado.

