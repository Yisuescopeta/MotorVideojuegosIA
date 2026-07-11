# Branch audit

Date: 2026-07-01

## Remote main detection

Commands executed:

```bash
git fetch --all --prune
git remote show origin
git branch -r --sort=-committerdate
```

Detected main branch: `origin/main`

Base commit used:

```text
b18fb1894552ef50ea3966a88276051054286585
```

`origin/main` matched the expected base commit after fetch, so work continued.

## Work branch

Created branch:

```text
codex/queen-safe-continuation
```

The branch was created from `origin/main` while preserving existing working-tree changes.

## Working-tree state at start

Modified:

- `AGENTS.md`
- `engine/ecs/world.py`
- `tests/test_ecs_indices.py`

Untracked:

- `docs/archive/agent-orchestration/agents/opengame-agents.md`
- `docs/plans/active/queen-20260630-001-ajuste-plan-especializado-ejecucion.md`

## Risk

`AGENTS.md` was already modified and full-suite governance tests fail against that file. This was documented as baseline risk and not reverted.

## Runtime input/picking phase update - 2026-07-02

Commands executed again before implementation:

```bash
git remote show origin
git fetch --all --prune
git branch -r --sort=-committerdate
```

Detected main branch: `origin/main`.

Base commit:

```text
b18fb1894552ef50ea3966a88276051054286585
```

Work branch:

```text
codex/runtime-input-picking
```

Pre-existing dirty worktree was preserved. Notable modified or untracked files already included `.gitignore`, `AGENTS.md`, `engine/ecs/world.py`, `tests/test_ecs_indices.py`, `tests/test_spatial_hash.py`, `docs/refactor/`, `projects/Opengame cartas/`, `tests/test_solitario_espanol.py`, and `tools/spatial_hash_benchmark.py`.

## Codex Queen migration audit - 2026-07-10

- Remote: `origin https://github.com/Yisuescopeta/OpenGame.git`.
- Branch: `fix/ciclosReina`; approved base:
  `99fa3896f661298208bcacde2821c2fab1a9dae6`.
- Migration scope excludes `engine/`, `cli/`, `main.py`, `START_HERE_AI.md`,
  `docs/archive/`, `.opencode/` and `opencode.json`.
- Initial task artifacts were untracked active plan and `.superpowers/` brief.
