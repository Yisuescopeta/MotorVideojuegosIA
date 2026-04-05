# AGENTS.md

## Setup

```bash
pip install -r requirements.txt
pip install -e .[dev]
python main.py
```

## Commands

### Run tests
```bash
python -m unittest discover -s tests
```

### Lint and typecheck (CI order: lint -> typecheck -> test)
```bash
python -m ruff check engine/api engine/project engine/rl engine/serialization engine/events cli tools main.py
python -m mypy engine/api engine/project engine/rl engine/serialization engine/events cli tools main.py
```

### CLI tooling
```bash
python -m tools.engine_cli validate --target scene --path levels/demo_level.json
python -m tools.engine_cli smoke --scene levels/demo_level.json --frames 5 --out-dir artifacts/cli_smoke
```

## Architecture

- Serializable scene (`levels/*.json`) is the source of truth.
- `SceneManager` drives EDIT -> PLAY -> STOP and owns dirty state / authoring transactions.
- `Game` / `HeadlessGame` operate on the active world, but don't replace the serializable model.
- `EngineAPI` is the public facade for agents, CLI, tests, and scripts.
- Core modules: ECS, Scene, SceneManager, serialization/schema migrations, editor base, hierarchy, EngineAPI, physics contract with `legacy_aabb` fallback.
- `box2d` is optional — registered at startup if available, falls back silently.
- `engine/rl` is experimental/tooling, not part of the core contract.

See `docs/module_taxonomy.md` for full classification.

## Schema

- Scene/prefab schema_version = 2.
- Loading migrates legacy and v1 payloads to v2 before validation.
- Saving emits canonico v2.
- Migration path: `tools/schema_cli.py` or `python -m tools.engine_cli migrate`.

## Editor controls

| Key | Action |
|---|---|
| SPACE | Play |
| P | Pause/Resume |
| ESC | Stop |
| R | Recargar escena |
| TAB | Mostrar/ocultar inspector |
| F8 | Hot-reload de scripts |
| F10 | Step |
| F11 | Fullscreen |
| Ctrl+S | Guardar escena |

## Verification rule

Per `.cursorrules`: always create a verification script for critical logic fixes before notifying the user. When modifying core systems (Game Loop, Inspector, etc.), verify changes with a script or automated test.

## Project layout

- `engine/` — core engine (api, ecs, scenes, physics, etc.)
- `cli/` — CLI runner and script executor
- `tools/` — standalone tooling (engine_cli, benchmarks, dataset runners)
- `levels/` — scene JSON files
- `assets/` — sprites, fonts, textures
- `scripts/` — user-authored Python scripts attached to entities
- `settings/` — project settings JSON
- `tests/` — test suite (also contains `visual_*.json` fixture files)

## Dependencies

- `raylib-py>=5.0.0.0` — graphics/physics (native library required)
- `box2d` — optional physics backend
- Dev: `ruff`, `mypy`, `bandit`, `pip-audit`, `Pillow`

## Known constraints

- Headless mode requires raylib native bindings; falls back gracefully if unavailable.
- `pip-audit` ignores CVE-2026-4539 (Pygments, no fix published yet).
- Mypy and ruff exclude `tests/`, `artifacts/`, `build/`, `dist/` (per pyproject.toml).