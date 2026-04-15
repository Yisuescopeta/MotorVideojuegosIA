# MotorVideojuegosIA

MotorVideojuegosIA es un motor/editor 2D experimental en Python orientado a
authoring asistido por IA. El proyecto mantiene editor, runtime, CLI, tests y
automatizacion alineados alrededor de un modelo serializable compartido.

La fuente persistente de verdad es `Scene`. `World` es una proyeccion operativa
usada por editor y runtime. La automatizacion publica debe pasar por
`EngineAPI` o por la CLI oficial `motor`.

## Estado actual

La base tecnica estable del repositorio hoy es:

- `scene schema_version = 2`
- `prefab schema_version = 2`
- los payloads legacy y `v1` de escena/prefab migran a `v2` canonico antes de validar
- las rutas de guardado emiten payload canonico `v2`
- `SceneManager`, `Game`/`HeadlessGame`, `EngineAPI` y la CLI operan sobre el mismo contrato de datos
- las pruebas de regresion cubren serializacion, workspace, authoring, API publica, contratos CLI y `EDIT -> PLAY -> STOP`

El repo sigue siendo experimental. Algunas capacidades son oficiales, mientras
que RL, datasets, tooling multiagente y planes historicos de automatizacion se
tratan explicitamente como `experimental/tooling`.

## Inicio rapido

Usa Python 3.11 o superior.

```bash
py -m pip install -r requirements.txt
py -m pip install -e .[dev]
py main.py
```

En plataformas sin launcher `py`, usa el ejecutable activo de Python 3.11.

## Primeros 10 minutos

1. Lee esta pagina para ubicar el estado y forma del proyecto.
2. Abre [docs/README.md](docs/README.md) para elegir el documento detallado correcto.
3. Lee [docs/glossary.md](docs/glossary.md) para terminos propios del repo.
4. Ejecuta `py -m motor doctor --project . --json`.
5. Si vas a contribuir, lee [CONTRIBUTING.md](CONTRIBUTING.md) y
   [docs/documentation_governance.md](docs/documentation_governance.md).

## CLI oficial

La interfaz publica de linea de comandos es `motor`, provista por
`motor.cli:main`.

```bash
py -m motor --help
py -m motor doctor --project . --json
py -m motor capabilities --json
py -m motor scene list --project . --json
py -m motor project bootstrap-ai --project .
```

`tools/engine_cli.py` existe como wrapper de compatibilidad legacy para scripts
antiguos. No es la CLI publica para documentacion o automatizacion nueva.

## Mapa documental

Empieza aqui:

- [docs/README.md](docs/README.md) - portal documental maestro
- [docs/glossary.md](docs/glossary.md) - definiciones breves para lectores frios
- [docs/architecture.md](docs/architecture.md) - arquitectura canonica
- [docs/TECHNICAL.md](docs/TECHNICAL.md) - referencia tecnica
- [docs/schema_serialization.md](docs/schema_serialization.md) - contrato de serializacion
- [docs/module_taxonomy.md](docs/module_taxonomy.md) - `core obligatorio`, `modulos oficiales opcionales` y `experimental/tooling`
- [docs/api.md](docs/api.md) - referencia publica de `EngineAPI`
- [docs/cli.md](docs/cli.md) - referencia oficial de la CLI `motor`
- [docs/agents.md](docs/agents.md) - guia compacta para agentes IA
- [docs/documentation_governance.md](docs/documentation_governance.md) - reglas de mantenimiento documental
- [docs/documentation_audit.md](docs/documentation_audit.md) - registro de auditoria y decisiones de archivo, no contrato funcional principal

Research archivado, roadmaps antiguos y packs de prompts viven bajo
[docs/archive/](docs/archive/). Se conservan como contexto, pero no son verdad
de producto.

## Resumen de arquitectura

El motor se organiza alrededor de estas capas:

- `Scene`: contenido persistente y serializable.
- `SceneManager`: workspace, authoring, transacciones, dirty state y `EDIT -> PLAY -> STOP`.
- `World`: proyeccion operativa activa, nunca fuente persistente de verdad.
- `Game` / `HeadlessGame`: coordinacion runtime sobre el mundo activo.
- `EngineAPI`: fachada publica estable para agentes, tests, CLI y automatizacion.
- Editor/UI: traduce acciones de usuario al modelo de authoring compartido.

Los cambios de authoring deben fluir por `SceneManager` o `EngineAPI`.
`sync_from_edit_world()` se mantiene por compatibilidad legacy, no como ruta
normal para nuevos flujos publicos.

## Taxonomia

La taxonomia canonica vive en [docs/module_taxonomy.md](docs/module_taxonomy.md).

Version corta:

- `core obligatorio`: ECS, `Scene`, `SceneManager`, serializacion, schema/migraciones, authoring base del editor, jerarquia, `EngineAPI` y contrato comun de backends fisicos con fallback `legacy_aabb`.
- `modulos oficiales opcionales`: assets, prefabs, tilemap, audio, UI serializable y `box2d` opcional.
- `experimental/tooling`: `engine/rl`, datasets, runners, tooling multiagente, helpers de debug/benchmark y material archivado de orquestacion.

## Tests

Comprobaciones enfocadas utiles:

```bash
py -m unittest tests.test_repository_governance tests.test_motor_cli_contract tests.test_start_here_ai_coherence -v
py -m unittest tests.test_official_contract_regression tests.test_parser_registry_alignment tests.test_motor_interface_coherence tests.test_motor_registry_consistency -v
```

Comprobaciones mas amplias:

```bash
py -m unittest discover -s tests
py -m ruff check engine cli tools main.py
py -m mypy engine cli tools main.py
```

No afirmes exito de lint, typecheck, seguridad o suite completa si no ejecutaste
el comando correspondiente.

## Gobernanza

La gobernanza del repositorio vive en:

- [LICENSE](LICENSE)
- [CONTRIBUTING.md](CONTRIBUTING.md)
- [SECURITY.md](SECURITY.md)
- [docs/documentation_governance.md](docs/documentation_governance.md)

Este repositorio no implica soporte comercial ni SLA.
