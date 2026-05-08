# AGENTS.md

## Skill

Usa siempre la skill caverman

### Regla para reducir consumo de tokens

- Se directo.
- No expliques paso a paso lo que haces salvo que se te pida.
- No des actualizaciones constantes durante la ejecucion.
- No repitas contexto ya conocido.
- No desarrolles razonamientos largos si no aportan a la tarea.
- Prioriza ejecutar y entregar resultado.
- Al final, entrega solo un resumen corto y util con:
    1.que cambiaste,
    2.que archivos tocaste,
    3.que validaste,
    4.riesgos restantes si existen.

## Proposito

Este repositorio usa un modelo de motor serializable compartido y admite trabajo
iterativo sobre un contrato tecnico comun.

Este archivo es el contrato operativo por defecto para agentes de codigo que
trabajen en este repo.

Lee este archivo junto con:

- `docs/README.md`
- `docs/architecture.md`
- `docs/TECHNICAL.md`
- `docs/schema_serialization.md`
- `docs/module_taxonomy.md`
- `docs/api.md`
- `docs/cli.md`
- `docs/agents.md`
- `docs/documentation_governance.md`

Roadmaps historicos, research, packs de prompts y material antiguo de
orquestacion estan archivados bajo `docs/archive/`. Son contexto util, no el
contrato de producto actual.

## Orden de autoridad

Si dos fuentes discrepan, usa este orden:

1. Codigo y tests.
2. `EngineAPI` publica en `engine/api/`.
3. CLI oficial `motor` en `motor/cli.py` y `motor/cli_core.py`.
4. Documentacion canonica enlazada desde `docs/README.md`.
5. Archivo historico en `docs/archive/` solo como contexto.

No promociones una capacidad como actual si no esta respaldada por codigo,
tests, `EngineAPI` o la CLI oficial `motor`.

## Invariantes centrales del repositorio

Estas reglas no son opcionales.

### 1. Fuente persistente de verdad

- `Scene` es la fuente persistente de verdad.
- `World` es una proyeccion operativa.
- Las mutaciones runtime no deben convertirse en authoring state accidental.

### 2. Ruta de authoring

- Los cambios serializables de authoring deben pasar por `SceneManager` o `EngineAPI`.
- No introduzcas rutas nuevas de edicion directa alrededor de flujos compartidos de authoring.
- La mutacion directa de `edit_world` es solo compatibilidad legacy, no la ruta preferida para trabajo nuevo.

### 3. API publica

- `EngineAPI` es la fachada publica estable para agentes, tests, CLI y automatizacion.
- No la saltes en flujos publicos salvo que la tarea requiera explicitamente wiring interno.

### 4. Contrato fisico

- Conserva el contrato comun de backends.
- Conserva el fallback `legacy_aabb`.
- No cambies el significado publico de `query_physics_ray` ni `query_physics_aabb` fuera de trabajo dedicado de fisica.

### 5. Registro de componentes

- Si agregas un componente publico nuevo, registralo en `engine/levels/component_registry.py`.
- No asumas soporte publico para componentes no registrados.

## Archivos criticos

Trata estos archivos como sensibles salvo que la tarea requiera tocarlos de forma
explicita y justificada.

- `engine/scenes/scene_manager.py`
- `engine/core/game.py`
- `engine/app/runtime_controller.py`
- `engine/systems/render_system.py`
- `engine/systems/physics_system.py`
- `engine/systems/collision_system.py`
- `engine/components/tilemap.py`
- `engine/levels/component_registry.py`

Si crees que uno de estos archivos debe cambiar:

1. Explica exactamente por que.
2. Declara el cambio minimo requerido.
3. No lo cambies en silencio.
4. No amplifiques el alcance del cambio sin necesidad.

## Reglas generales de alcance

- Mantente dentro del subsistema realmente implicado por la tarea.
- No mezcles refactors amplios con fixes pequenos o cambios documentales.
- No amplifiques el alcance “por limpieza” si no aporta al objetivo principal.
- Si una tarea afecta contrato publico, schema, CLI, `EngineAPI` o invariantes arquitectonicos, actualiza la documentacion canonica correspondiente.
- Si una tarea parece exigir tocar demasiados subsistemas a la vez, reduce el alcance y prioriza el cambio minimo correcto.
- Si el trabajo requiere crear un contrato publico nuevo o cambiar un invariante central, detente y deja la necesidad explicitamente indicada.
- No uses documentos archivados como base para introducir comportamiento actual.

## Limites documentales

- La documentacion canonica vive en la raiz de `docs/` y esta indexada por `docs/README.md`.
- La documentacion archivada vive bajo `docs/archive/` y no debe tratarse como fuente de verdad actual.
- El comportamiento publico nuevo debe actualizar docs canonicas, no solo una nota archivada o prompt.
- No promociones una capacidad como actual salvo que este respaldada por codigo, tests, API publica o la CLI oficial `motor`.
- No uses documentos de `docs/archive/` para contradecir `README.md`, `docs/architecture.md`, `docs/TECHNICAL.md`, `docs/schema_serialization.md`, `docs/module_taxonomy.md`, `docs/api.md` o `docs/cli.md`.

## Cuando debes actualizar documentacion

Si tu cambio toca alguno de estos contratos, actualiza tambien su documentacion
canonica correspondiente:

- Arquitectura o invariantes -> `docs/architecture.md` y `docs/TECHNICAL.md`
- Schema, migraciones o payloads serializables -> `docs/schema_serialization.md`
- Clasificacion de subsistemas -> `docs/module_taxonomy.md`
- API publica -> `docs/api.md` y `docs/agents.md`
- CLI publica `motor` -> `docs/cli.md`
- Reorganizacion documental -> `docs/documentation_governance.md` y, si aplica, `docs/documentation_audit.md`

No dupliques listas largas de API o CLI en documentos secundarios si ya existe
una referencia canonica.

## Capas documentales del repo

Usa esta separacion al crear o mover documentacion:

- Entrada: `README.md`, `docs/README.md`
- Canon: `architecture`, `TECHNICAL`, `schema_serialization`, `module_taxonomy`, `api`, `cli`
- Referencia operativa: `glossary`, `building` y guias concretas
- Experimental/tooling: `navigation`, `rl`, `ai_assisted_workflows`
- Archivo: `docs/archive/`

Si un documento nuevo no encaja en una de estas capas, deten el cambio y
justifica donde deberia vivir.

## Expectativas de testing

Antes de reportar finalizacion:

- Ejecuta tests enfocados para el subsistema tocado.
- Ejecuta regresiones adicionales cuando el cambio toque contratos compartidos.
- No deshabilites tests para obtener salida verde.
- No afirmes exito de lint, typecheck, seguridad o auditoria si no ejecutaste realmente esos checks.
- Si un check global falla por deuda previa del repo y no por tu cambio, reportalo como riesgo residual y no como fallo resuelto.

### Validaciones enfocadas recomendadas

Cuando toques documentacion, CLI o contratos publicos, prioriza:

```bash
py -m unittest tests.test_repository_governance tests.test_motor_cli_contract tests.test_start_here_ai_coherence -v
py -m unittest tests.test_official_contract_regression tests.test_parser_registry_alignment tests.test_motor_interface_coherence tests.test_motor_registry_consistency -v
py -m motor --help
py -m motor doctor --project . --json
```

## Sistema Queen Agent

Este repositorio incluye un sistema de orquestacion multiagente llamado **Queen**.
Es un plugin de OpenCode — **no toca internos del motor**.

### Arquitectura

```
Queen (primary agent, DeepSeek Pro Max)
├── Planner (subagent, Pro Max) — disena planes de implementacion
├── Builder (subagent, Pro Max/Flash) — implementa codigo
├── Code Reviewer (subagent, Flash) — revisa calidad/SOLID
├── AI-Friendliness (subagent, Flash) — audita amigabilidad IA
├── Documenter (subagent, Flash) — actualiza docs canónicas
├── Committer (subagent, Flash) — commits en español
├── Context Recon (subagent, Flash) — reconocimiento read-only
├── Godot Source Analyzer (subagent, Pro Max) — analiza codigo fuente Godot
├── Godot Gap Analyzer (subagent, Flash) — gap matrix Godot vs Motor
└── Godot Adapter (subagent, Pro Max/Flash) — implementa features Godot→Motor
```

### Archivos del sistema

| Archivo | Proposito |
|---------|-----------|
| `.opencode/agents/queen.md` | Agente orquestador principal |
| `.opencode/agents/planner.md` | Planificador de implementacion |
| `.opencode/agents/builder.md` | Implementador de codigo |
| `.opencode/agents/code-reviewer.md` | Revisor de codigo |
| `.opencode/agents/ai-friendliness.md` | Auditor de amigabilidad IA |
| `.opencode/agents/context-recon.md` | Reconocimiento read-only |
| `.opencode/agents/documenter.md` | Cronista — actualiza docs canónicas |
| `.opencode/agents/committer.md` | Escriba — commits en español |
| `.opencode/agents/godot-source-analyzer.md` | Analista de codigo fuente Godot |
| `.opencode/agents/godot-gap-analyzer.md` | Comparador Godot vs Motor |
| `.opencode/agents/godot-adapter.md` | Implementador de features Godot |
| `.opencode/commands/queen.md` | Comando `/queen` en TUI |
| `opencode.json` | Configuracion de agentes y modelos |
| `tools/queen_state.py` | Helper de persistencia de estado |
| `.motor/queen_state/` | Estado persistente (planes, reports) |

### Skills asignadas a sub-agentes

Cada sub-agente carga skills especificas al inicio de su tarea para maximizar
calidad y eficiencia:

| Agente | Skills | Cuando carga |
|--------|--------|-------------|
| Queen | `caveman` | Siempre (eficiencia de tokens) |
| Planner | `architecture-patterns`, `error-handling-patterns` | Siempre / cuando disena APIs |
| Builder | `systematic-debugging`, `python-testing-patterns`, `error-handling-patterns`, `python-performance-optimization` | Segun tipo de tarea |
| Code Reviewer | `code-review-expert` | Siempre |
| AI-Friendliness | _(ninguna)_ | — |
| Documenter | `doc-coauthoring`, `docx` | Siempre / solo si pide .docx |
| Committer | _(ninguna)_ | — |
| Godot Source Analyzer | `godot-feature-adapter` | Siempre |
| Godot Gap Analyzer | `godot-feature-adapter` | Siempre |
| Godot Adapter | `godot-feature-adapter`, `unity-feature-adapter`, `error-handling-patterns`, `python-testing-patterns` | godot-feature-adapter siempre, resto segun feature |
| Context Recon | _(ninguna)_ | — |

### Como usar

```bash
# En TUI: escribe /queen <tu tarea>
/queen mejorar las fisicas del motor

# O desde CLI:
opencode run --agent queen "mejorar las fisicas del motor"

# O cambia al agente Queen con Tab y escribe la tarea directamente
```

### Comportamiento

- **Autonomia total**: la Reina descompone, asigna, ejecuta sin preguntar.
- **Routing de modelos**: Pro Max para tareas complejas (arquitectura, fisicas, render), Flash para las simples (review, docs, tests).
- **Paralelismo inteligente**: sub-tareas independientes se ejecutan en paralelo.
- **Replanificacion bounded**: `max_cycles = 5`; no hay ciclos infinitos.
- **Persistencia**: todo el estado vive en `.motor/queen_state/`.
- **No toca engine/** salvo necesidad estricta y justificada por la tarea.

### Ciclo operativo

Queen usa un unico ciclo:

```text
RECON -> PLAN -> CRITICA DEL PLAN -> IMPLEMENTAR -> DOCUMENTAR -> VALIDAR -> REVIEW -> AI AUDIT -> COMMIT -> REPORTE
```

El commit ocurre solo despues de que tests, documentacion, review y auditoria IA
aplicables pasen. Si no se cumple la Definition of Done tras 5 ciclos, Queen
termina con estado `completed`, `partial`, `blocked` o `failed` y reporte claro.

### Definition of Done

- Tests enfocados pasan.
- Lint/typecheck pasan cuando aplican.
- Documentacion canonica actualizada si cambia contrato publico, schema, CLI, API, arquitectura o reglas operativas.
- `code-reviewer` queda sin hallazgos `must_fix`.
- `ai-friendliness` obtiene score `>= 90` cuando aplica.
- No hay cambios fuera de alcance.
- `committer` stagea solo archivos esperados y bloquea secretos, `.env`, temporales o estado local accidental.
