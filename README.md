# MotorVideojuegosIA

MotorVideojuegosIA is an experimental 2D engine/editor in Python designed around
AI-assisted authoring. The project keeps editor, runtime, CLI, tests, and
automation aligned around a shared serializable model.

The persistent source of truth is `Scene`. `World` is an operational projection
used by editor and runtime. Public automation should go through `EngineAPI` or
the official `motor` CLI.

## Current Status

The stable technical base today is:

- `scene schema_version = 2`
- `prefab schema_version = 2`
- legacy and `v1` scene/prefab payloads are migrated to canonical `v2` before validation
- save paths emit canonical `v2`
- `SceneManager`, `Game`/`HeadlessGame`, `EngineAPI`, and the CLI operate on the same data contract
- regression tests cover serialization, workspace behavior, authoring, public API, CLI contracts, and `EDIT -> PLAY -> STOP`

The repo remains experimental. Some modules are official, while RL, datasets,
multi-agent tooling, and historical automation plans are explicitly
`experimental/tooling`.

## Quick Start

Use Python 3.11 or newer.

```bash
py -m pip install -r requirements.txt
py -m pip install -e .[dev]
py main.py
```

On platforms where `py` is not available, use the active Python 3.11 executable.

## Official CLI

The public command-line interface is `motor`, provided by `motor.cli:main`.

```bash
py -m motor --help
py -m motor doctor --project . --json
py -m motor capabilities --json
py -m motor scene list --project . --json
py -m motor project bootstrap-ai --project .
```

`tools/engine_cli.py` still exists as a deprecated compatibility wrapper for
legacy scripts. It is not the public CLI for new documentation or automation.

## Documentation Map

Start here:

- [docs/README.md](docs/README.md) - master documentation portal
- [docs/architecture.md](docs/architecture.md) - canonical architecture
- [docs/TECHNICAL.md](docs/TECHNICAL.md) - technical reference
- [docs/schema_serialization.md](docs/schema_serialization.md) - serialization contract
- [docs/module_taxonomy.md](docs/module_taxonomy.md) - `core obligatorio`, `modulos oficiales opcionales`, and `experimental/tooling`
- [docs/api.md](docs/api.md) - public `EngineAPI` reference
- [docs/cli.md](docs/cli.md) - official `motor` CLI reference
- [docs/agents.md](docs/agents.md) - compact guide for AI agents
- [docs/documentation_audit.md](docs/documentation_audit.md) - audit and archive decisions

Archived research, old roadmaps, and prompt packs live under
[docs/archive/](docs/archive/). They are preserved for context, but they are not
product truth.

## Architecture Summary

The engine is built around these layers:

- `Scene`: persistent, serializable content.
- `SceneManager`: workspace, authoring state, transactions, dirty state, and `EDIT -> PLAY -> STOP`.
- `World`: active operational projection, never the persistent source of truth.
- `Game` / `HeadlessGame`: runtime coordination over the active world.
- `EngineAPI`: stable public facade for agents, tests, CLI, and automation.
- Editor/UI: translates user actions into the shared authoring model.

Authoring changes should flow through `SceneManager` or `EngineAPI`.
`sync_from_edit_world()` is retained for legacy compatibility, not as the normal
route for new public workflows.

## Taxonomy

The canonical taxonomy is maintained in [docs/module_taxonomy.md](docs/module_taxonomy.md).

Short version:

- `core obligatorio`: ECS, `Scene`, `SceneManager`, serialization, schema/migrations, base editor authoring, hierarchy, `EngineAPI`, and the common physics backend contract with `legacy_aabb` fallback.
- `modulos oficiales opcionales`: assets, prefabs, tilemap, audio, UI serializable, and optional `box2d`.
- `experimental/tooling`: `engine/rl`, datasets, runners, multi-agent tooling, debug/benchmark helpers, and archived orchestration material.

## Tests

Useful focused checks:

```bash
py -m unittest tests.test_repository_governance tests.test_motor_cli_contract tests.test_start_here_ai_coherence -v
py -m unittest tests.test_official_contract_regression tests.test_parser_registry_alignment tests.test_motor_interface_coherence tests.test_motor_registry_consistency -v
```

Broader checks:

```bash
py -m unittest discover -s tests
py -m ruff check engine cli tools main.py
py -m mypy engine cli tools main.py
```

Do not claim lint, typecheck, security, or full test success unless the command
was actually run.

## Governance

Repository governance lives in:

- [LICENSE](LICENSE)
- [CONTRIBUTING.md](CONTRIBUTING.md)
- [SECURITY.md](SECURITY.md)

There is no commercial support or SLA implied by this repository.
