# Auditoria documental

Nota de uso: este documento registra decisiones de reorganizacion y validacion
documental. No es el punto de entrada principal ni reemplaza el contrato
funcional del motor. Para navegar la documentacion usa [README.md](README.md);
para reglas futuras de mantenimiento usa
[documentation_governance.md](documentation_governance.md).

Fecha de reestructuracion inicial: 2026-04-16.
Fecha de cierre post-integracion con `main`: 2026-04-16.

## Alcance auditado

- `README.md`
- `AGENTS.md`
- `CONTRIBUTING.md`
- `COMO_EJECUTAR.md`
- `docs/**/*.md`
- CLI publica `motor`
- `EngineAPI`
- tests de gobernanza, contrato y coherencia de interfaz

## Estado de integracion

La rama `codex/Documentacion` fue actualizada contra `origin/main` mediante un
merge real.

- Base de `main` integrada: `origin/main` en `12b8a53`.
- Commit de merge local: `b8dfdff`.
- Conflictos de Git: ninguno.
- La reorganizacion documental de la rama se conservo: canon en `docs/`,
  material historico bajo `docs/archive/` y `motor` como CLI publica.

Despues del merge, `main` no reintrodujo como canonicos roadmaps, research,
prompts de agentes ni notas historicas en la raiz de `docs/`; permanecen bajo
`docs/archive/`.

## Criterio de autoridad

Si dos fuentes discrepan, manda este orden:

1. Codigo y tests.
2. `EngineAPI` publica.
3. CLI oficial `motor` en `motor/cli.py` y `motor/cli_core.py`.
4. Documentacion canonica enlazada desde [README.md](README.md).
5. Archivo historico en [archive/](archive/) solo como contexto.

No se usan roadmaps, prompts ni research como fuente de producto actual.

## Idioma canonico

La capa canonica del repositorio queda en espanol. Se preservan sin traducir
nombres tecnicos, comandos, metodos, flags, rutas, schemas y valores de contrato
publico, por ejemplo `Scene`, `World`, `SceneManager`, `EngineAPI`,
`legacy_aabb`, `motor`, `schema_version`, `implemented_capabilities` y
`planned_capabilities`.

`AGENTS.md` tambien queda en espanol para no romper la coherencia global de la
capa canonica. Los nombres de ramas, rutas y reglas de perimetro se mantienen
literalmente.

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

- `CONTRIBUTING.md`
- `docs/documentation_governance.md`
- `docs/glossary.md`
- `docs/documentation_audit.md`

### Planificacion operativa para ramas y workspaces

- `docs/roadmap/master-plan.md`
- `docs/roadmap/milestone-template.md`
- `docs/roadmap/rfc-lite-template.md`
- `docs/architecture/branch-strategy.md`
- `docs/architecture/module-boundaries.md`
- `docs/architecture/integration-strategy.md`
- `docs/ai/codex-prompt-guidelines.md`

### Referencia operativa o tooling vigente

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

### Referencias rotas en `AGENTS.md`

Se eliminaron referencias antiguas a:

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

El documento refleja el builder actual y la compatibilidad legacy de `doctor`.

### Material historico mezclado con docs principales

Se movieron roadmaps, research, prompts de agentes, notas de diseno antiguas y
auditorias historicas a `docs/archive/`. Permanecen versionados, pero fuera del
portal canonico.

### Capa nueva para trabajo paralelo

Se introduce una capa operativa nueva para coordinar ramas, workspaces,
milestones, RFCs ligeras e integracion por dominio. Esta capa vive en:

- `docs/roadmap/`
- `docs/architecture/branch-strategy.md`
- `docs/architecture/module-boundaries.md`
- `docs/architecture/integration-strategy.md`
- `docs/ai/codex-prompt-guidelines.md`

Decision aplicada:

- se mantiene fuera del canon funcional del motor
- se enlaza desde `docs/README.md`
- no reemplaza `docs/architecture.md`, `docs/module_taxonomy.md`, `docs/api.md`
  ni `docs/cli.md`
- deja `docs/archive/roadmaps/` como historico y `docs/roadmap/` como
  planificacion operativa vigente

### Rutas absolutas Windows

`docs/rl.md` contenia enlaces Markdown absolutos a una copia local del repo. Se
convirtieron a enlaces relativos del repositorio.

### Ayuda CLI con enlace archivado

`motor --help` seguia apuntando a `docs/CLI_GRAMMAR.md`, movido al archivo como
nota de diseno. Se actualizo el texto de ayuda en `motor/cli.py` para apuntar a
`docs/cli.md`.

### Instrucciones antiguas de ejecucion

`COMO_EJECUTAR.md` contenia comandos antiguos y texto mojibake. Se archivo el
documento original en `docs/archive/demos/COMO_EJECUTAR.md` y se dejo un redirect
breve en root hacia `README.md` y `docs/README.md`.

## Validaciones post-integracion

Estas validaciones se ejecutaron despues de integrar `origin/main` y de cerrar
la edicion documental principal.

### Validado realmente

```bash
py -m unittest tests.test_repository_governance tests.test_motor_cli_contract tests.test_start_here_ai_coherence -v
```

Resultado observado:

- `OK`
- 39 tests
- 2 skips

```bash
py -m unittest tests.test_official_contract_regression tests.test_parser_registry_alignment tests.test_motor_interface_coherence tests.test_motor_registry_consistency -v
```

Resultado observado:

- `OK`
- 50 tests
- 2 skips

```bash
py -m motor --help
```

Resultado observado:

- exit code `0`
- la ayuda se imprime correctamente
- la seccion `Documentation` apunta a `docs/cli.md`

```bash
py -m motor doctor --project . --json
```

Resultado observado:

- exit code `0`
- `success = true`
- `status = "healthy"`
- 3 warnings

Chequeo local de enlaces Markdown internos sobre `README.md`, `AGENTS.md`,
`CONTRIBUTING.md`, `COMO_EJECUTAR.md` y `docs/**/*.md`:

- `OK`
- 88 archivos Markdown verificados
- se ignoraron URLs externas y anclas puras

### Warning/skip esperado

Skips esperados en las dos suites:

- `START_HERE_AI.md no encontrado`
- `START_HERE_AI.md not found`

Motivo: el repo raiz no versiona `START_HERE_AI.md`; ese artefacto se genera por
proyecto con `py -m motor project bootstrap-ai --project .`.

Warnings esperados de `doctor` en el repo raiz:

- `motor_ai.json not found (run project migration)`
- `START_HERE_AI.md not found (run project migration)`
- `Cannot list assets: Project manifest not loaded`

Motivo: el root del repo es funcional como proyecto de desarrollo, pero no tiene
los artefactos AI bootstrap generados en la raiz.

### No ejecutado

No se ejecutaron en este cierre:

- `py -m unittest discover -s tests`
- `py -m ruff check engine cli tools main.py`
- `py -m mypy engine cli tools main.py`
- `py -m bandit -q -c .bandit -r engine cli tools main.py`
- `py -m pip_audit --skip-editable --ignore-vuln CVE-2026-4539`

Motivo: el alcance pedido fue integracion documental y revalidacion enfocada de
gobernanza/contratos/CLI. No se debe inferir exito de estas validaciones.

### Bloqueado por entorno

Ninguna validacion pedida quedo bloqueada por entorno.

## Riesgos residuales

- Los documentos archivados conservan contenido antiguo por diseno. No deben
  usarse como contrato vigente.
- Algunos tests historicos pueden crear fixtures legacy `motor_ai.json` schema
  `1` o `2`; eso prueba compatibilidad, no el contrato actual.
- El registry de capabilities puede listar capacidades `planned`; la CLI publica
  solo debe considerarse disponible si el parser de `motor/cli.py` la expone.

## Cierre tecnico de Fase 0

Fecha: 2026-04-17.
Rama: `chore/repo-workspace-foundation`.

Este cierre deja Fase 0 lista para merge y como base de Fase 1 sin ampliar
alcance a runtime, CLI, schema ni features del motor.

### Sincronizacion con `main`

La rama fue sincronizada con `origin/main` mediante `rebase`.

- Base integrada: `origin/main` en `9b93941`.
- Commit local tras rebase: `27aec3f`.
- Conflictos de Git: ninguno.
- Archivos fuera de Fase 0 tocados por la sincronizacion: ninguno.

### Verificacion de Fase 0

Se confirma que Fase 0 deja:

- convencion clara de ramas
- convencion clara de workspaces
- estrategia de integracion por dominios
- reglas de alcance por rama
- guia practica para futuros prompts a Codex
- enlaces desde `docs/README.md`
- separacion explicita entre planificacion operativa y capacidades implementadas
- cero cambios en runtime critico

### Validado realmente en este cierre

```bash
py -m unittest tests.test_repository_governance tests.test_motor_cli_contract tests.test_start_here_ai_coherence -v
```

Resultado observado:

- `OK`
- 46 tests
- 2 skips

```bash
py -m unittest tests.test_official_contract_regression tests.test_parser_registry_alignment tests.test_motor_interface_coherence tests.test_motor_registry_consistency -v
```

Resultado observado:

- `OK`
- 50 tests
- 2 skips

```bash
py -m motor --help
```

Resultado observado:

- exit code `0`
- la ayuda se imprime correctamente

```bash
py -m motor doctor --project . --json
```

Resultado observado:

- exit code `0`
- `success = true`
- `status = "healthy"`
- 3 warnings esperados del repo raiz
