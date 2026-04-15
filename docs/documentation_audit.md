# Auditoria documental

Nota de uso: este documento es un registro de auditoria y decisiones de
reorganizacion. No es el punto de entrada principal ni reemplaza el contrato
funcional del motor. Para navegar la documentacion usa [README.md](README.md);
para reglas futuras de mantenimiento usa
[documentation_governance.md](documentation_governance.md).

Fecha de reestructuracion: 2026-04-16.

Alcance auditado:

- `README.md`
- `AGENTS.md`
- `CONTRIBUTING.md`
- `COMO_EJECUTAR.md`
- `docs/**/*.md`
- CLI publica `motor`
- `EngineAPI`
- tests de gobernanza, contrato y coherencia de interfaz

## Criterio de autoridad

La fuente de verdad es el codigo, los tests, `EngineAPI`, `motor/cli.py`,
`motor/cli_core.py`, `engine/ai/registry_builder.py` y los schemas reales.

No se usaron roadmaps, prompts ni research como fuente de producto actual.

## Clasificacion resultante

### Canon del motor

- `README.md`
- `AGENTS.md`
- `docs/README.md`
- `docs/architecture.md`
- `docs/TECHNICAL.md`
- `docs/schema_serialization.md`
- `docs/module_taxonomy.md`
- `docs/api.md`
- `docs/cli.md`
- `docs/MOTOR_AI_JSON_CONTRACT.md`
- `docs/agents.md`

### Gobernanza y soporte de lectura

- `docs/documentation_governance.md`
- `docs/glossary.md`
- `docs/documentation_audit.md`

### Referencia tecnica o tooling vigente

- `docs/building.md`
- `docs/navigation.md`
- `docs/rl.md`
- `docs/ai_assisted_workflows.md`

`navigation.md`, `rl.md` y `ai_assisted_workflows.md` se tratan como
`experimental/tooling`.

### Historico, research o no canonico

Archivado bajo `docs/archive/`:

- `docs/archive/roadmaps/**`
- `docs/archive/research/**`
- `docs/archive/agent-orchestration/**`
- `docs/archive/design-notes/**`
- `docs/archive/audits/ANALISIS_PROYECTO_ACTUAL.md`
- `docs/archive/demos/COMO_EJECUTAR.md`

## Inconsistencias corregidas

### Skill inexistente

El prompt inicial referenciaba `.agents/skills/doc-coauthoring/SKILL.md`, pero
ese archivo no existe en el repo. La reestructuracion siguio el contrato del
prompt del usuario.

### Referencias rotas en `AGENTS.md`

Se eliminaron referencias a:

- `docs/parallel_execution_plan.md`
- `docs/parallel_prompts_index.md`

Se sustituyeron por documentos existentes y canonicos:

- `docs/README.md`
- `docs/architecture.md`
- `docs/TECHNICAL.md`
- `docs/schema_serialization.md`
- `docs/module_taxonomy.md`
- `docs/agents.md`

### CLI obsoleta

`docs/cli.md` documentaba `py -3 tools/engine_cli.py` como interfaz principal.
Se reemplazo por la CLI publica real:

- `motor`
- `py -m motor`
- entrypoint `motor.cli:main`

`tools/engine_cli.py` queda documentado solo como compatibilidad legacy.

### Contrato `motor_ai.json` obsoleto

`docs/MOTOR_AI_JSON_CONTRACT.md` documentaba `schema_version = 2` y
`capabilities.capabilities`. El codigo actual genera:

- `schema_version = 3`
- `implemented_capabilities`
- `planned_capabilities`
- `capability_counts`

El documento fue reescrito para reflejar el builder actual y la compatibilidad
legacy de `doctor`.

### Material historico mezclado con docs principales

Se movieron roadmaps, research, prompts de agentes, notas de diseno antiguas y
auditorias historicas a `docs/archive/`. Permanecen versionados, pero fuera del
portal canonico.

### Rutas absolutas Windows

`docs/rl.md` contenia enlaces Markdown absolutos a una copia local del repo. Se
convirtio a enlaces relativos del repositorio.

### Ayuda CLI con enlace archivado

`motor --help` seguia apuntando a `docs/CLI_GRAMMAR.md`, movido al archivo como
nota de diseno. Se actualizo el texto de ayuda en `motor/cli.py` para apuntar a
`docs/cli.md`.

### Instrucciones antiguas de ejecucion

`COMO_EJECUTAR.md` contenia comandos antiguos y texto mojibake. Se archivo el
documento original en `docs/archive/demos/COMO_EJECUTAR.md` y se dejo un redirect
breve en root hacia `README.md` y `docs/README.md`.

## Decisiones de arquitectura documental

1. `README.md` queda como entrada ejecutiva.
2. `docs/README.md` queda como portal maestro.
3. `docs/architecture.md` define el contrato conceptual.
4. `docs/TECHNICAL.md` resume comportamiento verificable y enlaza a fuentes.
5. `docs/schema_serialization.md` es la unica fuente documental para escenas y prefabs.
6. `docs/module_taxonomy.md` es la unica fuente documental de clasificacion.
7. `docs/api.md` documenta `EngineAPI` por dominios reales.
8. `docs/cli.md` documenta solo la CLI publica `motor`.
9. `docs/agents.md` da orientacion breve y evita que agentes lean archivo historico como contrato.
10. `docs/archive/` conserva contexto no canonico sin contaminar la navegacion principal.

## Documentos movidos al archivo

Diseno/notas historicas:

- `docs/CLI_ARCHITECTURE.md`
- `docs/CLI_GRAMMAR.md`
- `docs/DOCTOR_BOOTSTRAP_FLOW.md`
- `docs/DOCTOR_READ_ONLY_DESIGN.md`
- `docs/CAPABILITY_STATUS_DESIGN.md`
- `docs/MIGRATION_TO_MOTOR_INTERFACE.md`
- `docs/PARSER_REGISTRY_ALIGNMENT.md`
- `docs/REGISTRY_AUDIT_REPORT.md`
- `docs/REGRESSION_GUARANTEES.md`
- `docs/ANIMATOR_HEADLESS_FLOW.md`
- `docs/ai_workflow_cli.md`

Auditoria historica:

- `docs/ANALISIS_PROYECTO_ACTUAL.md`

Demos antiguas:

- `COMO_EJECUTAR.md` original

Directorios completos:

- `docs/roadmaps/`
- `docs/research/`
- `docs/agent-orchestration/`

## Validaciones ejecutadas durante la auditoria inicial

```bash
py -m unittest tests.test_repository_governance tests.test_motor_cli_contract tests.test_start_here_ai_coherence -v
```

Resultado observado antes de la reestructuracion completa:

- `OK`
- 39 tests
- 2 skips esperados por ausencia de `START_HERE_AI.md` en root

## Validaciones ejecutadas tras la reestructuracion

```bash
py -m unittest tests.test_repository_governance tests.test_motor_cli_contract tests.test_start_here_ai_coherence -v
py -m unittest tests.test_official_contract_regression tests.test_parser_registry_alignment tests.test_motor_interface_coherence tests.test_motor_registry_consistency -v
py -m motor --help
py -m motor doctor --project . --json
```

Resultados:

- primera suite: `OK`, 39 tests, 2 skips esperados por ausencia de `START_HERE_AI.md` en root
- segunda suite: `OK`, 50 tests, 2 skips esperados por ausencia de `START_HERE_AI.md` en root
- `py -m motor --help`: `OK`, ayuda apunta a `docs/cli.md`
- `py -m motor doctor --project . --json`: `success = true`, proyecto `healthy`, 3 warnings esperados
- chequeo de enlaces Markdown internos sobre `README.md`, `AGENTS.md`, `CONTRIBUTING.md`, `COMO_EJECUTAR.md` y `docs/**/*.md`: `OK`

Warnings esperados de `doctor` en el repo raiz:

- `motor_ai.json not found (run project migration)`
- `START_HERE_AI.md not found (run project migration)`
- `Cannot list assets: Project manifest not loaded`

## Riesgos residuales

- Algunos documentos archivados conservan contenido antiguo por diseno. No deben
  usarse como contrato vigente.
- Algunos tests historicos pueden crear fixtures legacy `motor_ai.json`
  schema `1` o `2`; eso prueba compatibilidad, no el contrato actual.
- El registry de capabilities puede listar capacidades `planned`; la CLI publica
  solo debe considerarse disponible si el parser de `motor/cli.py` la expone.
