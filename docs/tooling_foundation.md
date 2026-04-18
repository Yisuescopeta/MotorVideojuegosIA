# Tooling Foundation

Status: `experimental/tooling`.

## Scope

Esta capa agrupa tooling local y no publico para soporte a desarrollo del repo.
No forma parte de la interfaz estable del motor y no amplifica el contrato de
`EngineAPI` ni de la CLI oficial `motor`.

Los comandos actuales viven bajo `tools/`:

- `python -m tools.dev_checks`
- `python -m tools.capability_registry_audit`
- `python -m tools.dev_worktree`

## Non-goals

Esta foundation no:

- cambia `motor` ni agrega comandos publicos
- toca runtime central ni rutas de authoring del motor
- crea o modifica worktrees automaticamente
- reemplaza checks de CI o contratos publicos

## Commands

### `python -m tools.dev_checks`

Runner local para checks enfocados por suite nombrada.

Suites actuales:

- `tooling-foundation`: gobernanza y regresiones del tooling tocado en esta fase
- `repo-contracts`: checks de coherencia contractual del repo
- `doctor`: ejecuta `motor doctor --project <repo>`
- `registry-audit`: ejecuta el audit del capability registry

Flags utiles:

- `--suite <name>` para elegir una o varias suites
- `--list-suites` para listar suites disponibles
- `--dry-run` para ver los comandos sin ejecutarlos
- `--json` para salida maquina-legible

### `python -m tools.capability_registry_audit`

Audit local del capability registry para detectar drift entre:

- referencias `api_methods`
- comandos `cli_command`
- ejemplos de componentes
- contrato basico del registry

Existe `scripts/audit_registry.py` como wrapper legacy hacia este modulo. No es
una interfaz nueva de producto; solo mantiene compatibilidad operativa.

### `python -m tools.dev_worktree`

Helper read-only para soporte a trabajo paralelo con git worktrees.

Subcomandos:

- `status`: repo root, branch actual, detached HEAD y dirty state
- `list`: parsea `git worktree list --porcelain`
- `validate`: valida branch esperada, detached permitido y limpieza opcional
- `plan`: propone un `git worktree add ...` sin ejecutarlo

`plan` solo genera una recomendacion. No crea ramas ni worktrees en esta fase.

## Usage Notes

- Todo este tooling es repo-local y experimental.
- La salida `--json` esta pensada para automatizacion interna del repo, no como
  contrato externo estable.
- Si una capacidad de esta capa evoluciona hacia contrato publico, debe pasar
  por la documentacion canonica correspondiente en lugar de quedarse solo aqui.
