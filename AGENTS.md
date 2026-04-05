# AGENTS.md

## Setup & Installation

```bash
pip install -r requirements.txt
pip install -e .[dev]
python main.py
```

## Developer Commands

```bash
# Test suite
python -m unittest discover -s tests

# Single test file
python -m unittest tests/test_core_regression_matrix.py

# Lint (ruff targets specific dirs, not whole repo)
python -m ruff check engine/api engine/project engine/rl engine/serialization engine/events cli tools main.py

# Typecheck
python -m mypy engine/api engine/project engine/rl engine/serialization engine/events cli tools main.py

# Security
python -m bandit -q -c .bandit -r engine cli tools main.py
python -m pip_audit --skip-editable --ignore-vuln CVE-2026-4539

# CLI tooling
python -m tools.engine_cli validate --target scene --path levels/demo_level.json
python -m tools.engine_cli smoke --scene levels/demo_level.json --frames 5 --out-dir artifacts/cli_smoke
```

## Core Architecture

- **Source of truth**: Serializable `Scene` data (JSON, schema v2). UI is never the source of truth.
- **Editable world** (`SceneManager.edit_world`) ← derived from `Scene`
- **Runtime world** (`SceneManager.runtime_world`) ← cloned temporary copy for PLAY
- `Game.world` / `HeadlessGame.world` expose `active_world` but don't replace the serializable model.
- **Authoring mutation routes**: Always go through `SceneManager.apply_edit_to_world()`, `update_entity_property()`, `replace_component_data()`, `add_component_to_entity()`, `remove_component_from_entity()`, or `EngineAPI`.
- `sync_from_edit_world()` is legacy; avoid for new authoring code.

## Module Classification

| Category | Contents |
|---|---|
| `core mandatory` | ECS, Scene, SceneManager, serialization/schema, EngineAPI, editor base, hierarchy, physics backend contract + `legacy_aabb` fallback |
| `official optional` | assets, prefabs, tilemap, audio, UI serializable, `box2d` backend |
| `experimental/tooling` | `engine/rl`, datasets, runners, multiagent, debug tooling |

`box2d` is optional and falls back to `legacy_aabb` if unavailable.

## Headless / CLI Mode

```bash
python main.py --headless --level levels/demo_level.json --frames 60
python main.py --headless --script path/to/script.py --frames 5
```

## Key Files

- `main.py` — editor entry point (GUI mode)
- `engine/api/engine_api.py` — public API facade for agents, CLI, tests
- `engine/scenes/scene_manager.py` — coordinates EDIT→PLAY→STOP
- `engine/serialization/` — schema and migration logic (v1→v2, emits v2)
- `docs/architecture.md` / `docs/module_taxonomy.md` — architectural contract
- `docs/TECHNICAL.md`, `docs/schema_serialization.md` — deeper technical docs
- `tests/test_core_regression_matrix.py` — regression tests for core invariants

## Python & Tool Versions

- Python >= 3.11
- `pyproject.toml`: setuptools-based build
- `ruff` (py311 target, line-length 120)
- `mypy` (exclude: tests/, artifacts/, build/, dist/)
- `bandit` config at `.bandit` (skips: B105, B106, B110, B112, B311, B404, B603)

## Editor Controls (when running main.py)

| Key | Action |
|---|---|
| SPACE | Play |
| P | Pause/Resume |
| ESC | Stop |
| R | Reload scene |
| TAB | Toggle inspector |
| F8 | Hot-reload scripts |
| F10 | Step |
| F11 | Fullscreen |
| Ctrl+S | Save scene |
