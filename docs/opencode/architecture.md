# OpenCode Integrado En El Motor

## Objetivo

Este documento define que significa integrar OpenCode dentro del motor sin
romper la arquitectura actual:

- servicio + API + CLI primero
- UI despues y solo como cliente opcional
- escenas, prefabs, scripts y proyecto siguen usando JSON y rutas ya existentes
- `artifacts/` y `.motor/` mantienen sus responsabilidades actuales

No se propone rehacer la CLI unificada ni sustituir el pipeline actual de
artefactos. OpenCode debe acoplarse a ellos.

## Linea Base Del Repo

### Fuente de verdad actual

Segun [docs/architecture.md](/C:/Users/usuario/Downloads/MotorVideojuegosIA-main/MotorVideojuegosIA-main/docs/architecture.md),
la fuente de verdad persistente vive en datos serializables del proyecto:

- escenas JSON en `levels/`
- prefabs serializables en `prefabs/`
- scripts y assets del proyecto
- metadatos de proyecto resueltos por `project.json`

La UI no es fuente de verdad. OpenCode tampoco debe serlo.

### Rutas de proyecto ya soportadas

`project.json` y [engine/project/project_service.py](/C:/Users/usuario/Downloads/MotorVideojuegosIA-main/MotorVideojuegosIA-main/engine/project/project_service.py)
declaran estas rutas estables:

- `assets/`
- `levels/`
- `prefabs/`
- `scripts/`
- `settings/`
- `.motor/meta/`
- `.motor/build/`

### Politica actual de `artifacts/` y `.motor/`

La separacion observable hoy es:

- `.motor/meta/`: estado local y metadatos del proyecto o de herramientas
  internas. Ejemplos reales: `asset_catalog.json`,
  `ai_project_memory.json`, `ai_sessions/*.json`, `ai_snapshots/*.json`.
- `.motor/build/`: salidas derivadas del pipeline interno del proyecto.
  Ejemplos reales: `asset_build_report.json`, `bundle_report.json`,
  `content_bundle.json`.
- `artifacts/`: salidas reproducibles de CLI, smoke, datasets, replay,
  benchmarks e inspeccion operativa. Ejemplos reales:
  `artifacts/cli_smoke_manual/`, `artifacts/generated_scenarios_100/`,
  `artifacts/replay_episode_0000.json`,
  `artifacts/parallel_rollouts_8x1250/`.

Regla de contrato:

- `artifacts/` contiene outputs exportados y evidencia operativa.
- `.motor/` contiene estado local de proyecto, cache, metadata y build interno.
- Ninguno de los dos sustituye a `levels/`, `prefabs/`, `scripts/` o
  `assets/` como fuente de verdad funcional.

## Que Significa "OpenCode Integrado"

OpenCode integrado en el motor significa lo siguiente:

1. Un servicio OpenCode se ejecuta fuera de la UI y puede ser gestionado por
   procesos del motor.
2. El motor habla con ese servicio via API o bridge local.
3. La superficie operativa publica es CLI primero, usando los comandos reales
   ya existentes del repo.
4. La UI, si aparece despues, solo consume ese bridge y nunca introduce una
   ruta alternativa de mutacion.

Esto se alinea con el contrato ya fijado en
[docs/architecture.md](/C:/Users/usuario/Downloads/MotorVideojuegosIA-main/MotorVideojuegosIA-main/docs/architecture.md):
editor, runtime, API y tooling deben operar sobre el mismo modelo serializable.

## Superficie Operativa Real Ya Disponible

### CLI unificada actual

El punto de entrada existente es
[tools/engine_cli.py](/C:/Users/usuario/Downloads/MotorVideojuegosIA-main/MotorVideojuegosIA-main/tools/engine_cli.py).

Subcomandos reales hoy:

- `validate`
- `migrate`
- `build-assets`
- `run-headless`
- `profile-run`
- `smoke`

La documentacion actual esta en
[docs/cli.md](/C:/Users/usuario/Downloads/MotorVideojuegosIA-main/MotorVideojuegosIA-main/docs/cli.md)
y los tests en
[tests/test_engine_cli.py](/C:/Users/usuario/Downloads/MotorVideojuegosIA-main/MotorVideojuegosIA-main/tests/test_engine_cli.py).

### Tooling real adicional que OpenCode debe reutilizar

No forma parte aun del CLI unificado, pero ya existe y es la base correcta para
tools tipadas:

- datasets RL single-agent:
  [tools/random_rollout_dataset.py](/C:/Users/usuario/Downloads/MotorVideojuegosIA-main/MotorVideojuegosIA-main/tools/random_rollout_dataset.py)
- datasets RL multiagent:
  [tools/multiagent_rollout_dataset.py](/C:/Users/usuario/Downloads/MotorVideojuegosIA-main/MotorVideojuegosIA-main/tools/multiagent_rollout_dataset.py)
- escenarios, episode logging y replay:
  [tools/scenario_dataset_cli.py](/C:/Users/usuario/Downloads/MotorVideojuegosIA-main/MotorVideojuegosIA-main/tools/scenario_dataset_cli.py)
- runner paralelo por subprocess:
  [tools/parallel_rollout_runner.py](/C:/Users/usuario/Downloads/MotorVideojuegosIA-main/MotorVideojuegosIA-main/tools/parallel_rollout_runner.py)
- harness headless y golden runs:
  [cli/runner.py](/C:/Users/usuario/Downloads/MotorVideojuegosIA-main/MotorVideojuegosIA-main/cli/runner.py)

### Comandos concretos que ya existen

Casos reales que OpenCode puede envolver sin inventar una CLI nueva:

```bash
py -3 tools/engine_cli.py smoke --scene levels/demo_level.json --frames 5 --seed 123 --out-dir artifacts/cli_smoke
py -3 tools/scenario_dataset_cli.py generate-scenarios levels/multiagent_toy_scene.json --count 100 --seed 123 --out-dir artifacts/generated_scenarios
py -3 tools/scenario_dataset_cli.py run-episodes levels/platformer_test_scene.json --episodes 100 --max-steps 120 --seed 123 --out artifacts/episodes.jsonl --summary-out artifacts/episodes_summary.json
py -3 tools/scenario_dataset_cli.py replay-episode artifacts/episodes.jsonl --episode-id episode_0000 --out artifacts/replay_episode_0000.json
py -3 tools/parallel_rollout_runner.py levels/multiagent_toy_scene.json --workers 8 --episodes 8 --max-steps 1250 --seed 123 --out-dir artifacts/parallel_rollouts
python -m pytest tests/test_engine_cli.py tests/test_scenario_dataset.py
```

## Arquitectura Recomendada

### Capas

#### 1. Servicio OpenCode

- proceso gestionado fuera de la UI
- health-check
- sesiones
- mensajes
- permisos/aprobaciones

#### 2. Bridge del motor

- adapta OpenCode al contrato del repo
- resuelve rutas relativas al proyecto
- aplica politicas de seguridad
- solo expone operaciones engine-aware

#### 3. CLI del motor

- sigue siendo la superficie publica principal
- puede añadir subcomandos `opencode` en el futuro
- no debe duplicar logica que ya existe en `tools/engine_cli.py` o en los
  CLIs de datasets

#### 4. UI opcional

- cliente de sesiones, streaming, diff y approvals
- sin privilegios especiales
- sin acceso directo a mutaciones fuera del bridge

## Modelo De Artefactos OpenCode

## Principio

OpenCode no introduce un almacen nuevo. Usa JSON y el sistema actual:

- estado local o reusable de proyecto en `.motor/meta/`
- evidencias exportadas y bundles de ejecucion en `artifacts/`

## Tipos de artefacto

### Estado local

Propuesta sin romper el repo:

- `.motor/meta/opencode/active_session.json`
- `.motor/meta/opencode/session_index.json`

Uso:

- punteros a sesiones activas
- configuracion local y resoluciones operativas
- nunca fuente de verdad de escenas o cambios de codigo

### Bundle exportado por ejecucion

Propuesta:

- `artifacts/opencode/<run_id>/transcript.json`
- `artifacts/opencode/<run_id>/diffs.json`
- `artifacts/opencode/<run_id>/logs.jsonl`
- `artifacts/opencode/<run_id>/approvals.json`
- `artifacts/opencode/<run_id>/manifest.json`

Uso:

- evidencia auditable
- replay humano y debugging
- trazabilidad de que pidio el agente, que intento cambiar y que se aprobo

## Semantica de cada archivo

### `transcript.json`

- transcript normalizado de la sesion
- compatible con la idea ya existente de `.motor/meta/ai_sessions/*.json`
- debe incluir mensajes, timestamps, session id, prompt inicial y resumen

### `diffs.json`

- lista JSON de archivos afectados
- estado por archivo: `planned`, `applied`, `rejected`, `skipped`
- puede incluir hashes antes/despues y resumen textual del cambio
- evita introducir un formato custom distinto del stack actual

### `logs.jsonl`

- eventos operativos append-only
- ejemplo de eventos: `service_started`, `tool_called`, `approval_requested`,
  `approval_resolved`, `artifact_exported`, `session_failed`

### `approvals.json`

- decisiones de permiso y aprobacion humana
- accion solicitada
- alcance
- decision
- razon
- timestamp

### `manifest.json`

- indice del bundle exportado
- version
- session id
- run id
- rutas relativas de artefactos
- estado final

## Esquema De Carpetas Propuesto

Este esquema extiende el repo sin romper la estructura actual:

```text
docs/
  opencode/
    architecture.md
    security.md

.motor/
  meta/
    opencode/
      active_session.json
      session_index.json

artifacts/
  opencode/
    <run_id>/
      manifest.json
      transcript.json
      diffs.json
      logs.jsonl
      approvals.json
```

Reglas:

- `docs/opencode/` documenta el contrato
- `.motor/meta/opencode/` guarda estado local no canonico
- `artifacts/opencode/` exporta bundles de evidencia
- no se crean rutas nuevas para fuente de verdad de contenido

## Relacion Con Agent Skills

El repo ya trabaja con skills bajo `.agents/skills/` y documentos tipo
`SKILL.md`. OpenCode debe consumir esa ruta como fuente compartida de
instrucciones especializadas, no duplicarla dentro de una UI.

Regla:

- skill compartida en `.agents/skills/`
- OpenCode la referencia y ejecuta dentro del contrato del motor
- la skill no puede saltarse el bridge ni abrir una ruta de mutacion paralela

## Checklist De Aceptacion

- [ ] Queda explicito que OpenCode integrado significa servicio + API + CLI
      primero, sin dependencia de UI.
- [ ] Queda explicito que la UI, si existe, llega despues como cliente del
      bridge.
- [ ] Se referencia el CLI unificado actual y los scripts reales de datasets,
      replay y runner paralelo.
- [ ] Se mantiene la politica actual: `artifacts/` como outputs/evidencia y
      `.motor/` como metadata/build local.
- [ ] El modelo de artefactos usa JSON y rutas compatibles con el repo.
- [ ] No se redefine la fuente de verdad del motor.
- [ ] El esquema de carpetas propuesto puede anadirse sin mover ni romper
      rutas existentes.
