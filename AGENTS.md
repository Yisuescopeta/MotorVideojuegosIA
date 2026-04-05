# AGENTS.md

## Setup

```bash
pip install -r requirements.txt
pip install -e .[dev]
```

Python 3.11+ required.

## Run

- GUI: `python main.py`
- CLI: `py -3 tools/engine_cli.py <subcomando>` (validate, migrate, build-assets, run-headless, profile-run, smoke)
- Headless: `python main.py --headless --level <scene.json> --frames <N>` or `python main.py --frames <N>` (implies headless)

## Test

```bash
python -m unittest discover -s tests
```

Run a single test file: `python -m unittest tests/test_scene_manager_sync.py`

## Lint / Typecheck / Security

```bash
python -m ruff check engine/api engine/project engine/rl engine/serialization engine/events cli tools main.py
python -m mypy engine/api engine/project engine/rl engine/serialization engine/events cli tools main.py
python -m bandit -q -c .bandit -r engine cli tools main.py
python -m pip_audit --skip-editable --ignore-vuln CVE-2026-4539
```

## Architecture Key Facts

- **Source of truth**: Serialized `Scene` JSON (schema v2). UI is a projection, not the authority.
- **EDIT -> PLAY -> STOP**: `Scene` feeds `edit_world` in EDIT; PLAY clones to `runtime_world`; STOP restores from `Scene`. Runtime mutations never contaminate the editable scene.
- **EngineAPI** is the public facade for agents, tests, CLI. It delegates to domain modules but exposes a single, stable surface.
- **Box2D is optional**; core physics falls back to `legacy_aabb`.
- **Modules classified**: `core` (ECS, Scene, serialization, EngineAPI), `official optional` (assets, tilemap, audio, box2d), `experimental/tooling` (RL, datasets, benchmarks).

## Schema / Serialization

- Current: `scene schema_version = 2`, `prefab schema_version = 2`
- Load migrates legacy/v1 -> v2 before validation; save always emits v2.
- `engine/serialization/schema.py` is the canonical contract.

## Editor Controls

SPACE=Play, P=Pause/Resume, ESC=Stop, R=Reload, TAB=Inspector, F8=Hot-reload scripts, F10=Step, F11=Fullscreen, Ctrl+S=Save

## Important Conventions

- **Authoring mutations** must go through `SceneManager.apply_edit_to_world`, `update_entity_property`, `replace_component_data`, etc. Direct `edit_world` mutations are legacy compat only.
- **No parallel truth**: UI state must be reflectable via `EngineAPI` or serialized data.
- **Experimental features** (RL, datasets) are explicitly documented as out of core scope.
- `scripts/` directory holds hot-reloadable user scripts.

## Verification Scripts

Root-level `verify_*.py` scripts test specific subsystems. Use them to check serialization, scene manager, prefabs, inspector, hierarchy, and gizmo logic before declaring a fix complete.
