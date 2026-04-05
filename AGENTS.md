# AGENTS.md

## Setup

```bash
pip install -r requirements.txt
pip install -e .[dev]
```

## Running

- GUI editor: `python main.py`
- Headless: `python main.py --headless`
- Single level smoke test: `python -m tools.engine_cli smoke --scene levels/demo_level.json --frames 5`
- Run N frames: `python main.py --headless --level levels/demo_level.json --frames 60`

## Testing

```bash
python -m unittest discover -s tests
```

Run a single test file: `python -m unittest tests/test_schema_validation.py`

## Validation commands (run in order)

```bash
python -m ruff check engine/api engine/project engine/rl engine/serialization engine/events cli tools main.py
python -m mypy engine/api engine/project engine/rl engine/serialization engine/events cli tools main.py
python -m bandit -q -c .bandit -r engine cli tools main.py
python -m pip_audit --skip-editable --ignore-vuln CVE-2026-4539
```

## Architecture: Source of truth rule

**The UI is never the source of truth.** The serializable `Scene` JSON (schema v2) is the authoritative data. `Scene` contains entities, components, rules, and `feature_metadata`. `SceneManager.edit_world` and `SceneManager.runtime_world` are projections of that data.

Data flow: `Scene` (serializable) → `edit_world` (editable projection) → `runtime_world` (cloned for PLAY) → restored to `edit_world` on STOP.

Mutation must go through `SceneManager` authoring methods or `EngineAPI`. Direct `edit_world` mutation is legacy-only.

## Schema versions

- Scene and prefab `schema_version = 2` is canonical
- Save always emits v2
- Load migrates legacy and v1 → v2 automatically
- Source of truth: `engine/serialization/schema.py`

## Key imports

```python
from engine.api import EngineAPI           # public facade for agents, CLI, tests
from engine import Scene, SceneManager     # core data/model layer
from engine import Game, HeadlessGame     # runtime coordinators
```

## EngineAPI usage pattern

```python
api = EngineAPI(project_root=".")
api.load_level("levels/demo_level.json")
api.play()
api.step(10)
events = api.get_recent_events(count=10)
api.shutdown()
```

## Component registry

Components are registered in `engine/levels/component_registry.py`. Only registered components are valid.

## Physics backends

Default: `legacy_aabb`. Optional: `box2d` (loaded if available). Fallback to `legacy_aabb` if `box2d` unavailable. Backend selection is in `feature_metadata.physics_2d.backend`.

## Version info

Version is set in `engine/config.py` (`ENGINE_VERSION`), not in pyproject.toml. This is the single source of truth for the engine version.

## Editor controls (GUI mode)

| Key | Action |
|-----|--------|
| SPACE | Play |
| P | Pause/Resume |
| ESC | Stop |
| R | Reload scene |
| TAB | Toggle inspector |
| F8 | Hot-reload scripts |
| F10 | Step |
| F11 | Fullscreen |
| Ctrl+S | Save scene |

## Module taxonomy (from `docs/module_taxonomy.md`)

- **Core mandatory**: ECS, Scene, SceneManager, serialization, EngineAPI, editor base, hierarchy, physics backend contract + legacy_aabb fallback
- **Official optional**: assets, prefabs, tilemap, audio, UI, box2d
- **Experimental/tooling**: engine/rl, datasets, multiagent runners, benchmarking, AI workflows

## Important file locations

- `engine/scenes/scene.py` — Scene data model
- `engine/scenes/scene_manager.py` — coordinates workspace, authoring, EDIT→PLAY→STOP
- `engine/api/engine_api.py` — public EngineAPI facade
- `engine/levels/component_registry.py` — registered components
- `engine/serialization/schema.py` — schema versions and migration
- `cli/runner.py` — headless CLI execution
- `main.py` — GUI entry point
