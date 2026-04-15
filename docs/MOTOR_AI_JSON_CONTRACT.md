# Contrato `motor_ai.json`

`motor_ai.json` es el artefacto legible por maquinas que permite a una IA
descubrir un proyecto creado con MotorVideojuegosIA. No es documentacion del repositorio:
se genera dentro de cada proyecto con la CLI oficial.

Generador canonico:

- `engine/ai/registry_builder.py`
- `engine/project/project_service.py`
- `motor project bootstrap-ai --project .`

## Estado actual

- Formato actual: `schema_version = 3`
- Registry interno de capabilities: `capabilities_schema_version = 1`
- CLI oficial: `motor`
- Compatibilidad legacy de `doctor`: schemas `1` y `2` con `capabilities.capabilities`

`doctor` puede leer schemas antiguos para diagnostico, pero el bootstrap actual
debe generar siempre schema `3`.

## Principios

1. Las rutas de proyecto deben ser relativas al root del proyecto.
2. El archivo no debe contener rutas absolutas de Windows, Unix ni red.
3. La lista de capabilities separa lo implementado de lo planificado.
4. Los comandos CLI documentados deben usar `motor`, no `tools.engine_cli`.
5. `capability_counts` debe coincidir con las listas del archivo.

## Estructura v3

```json
{
  "schema_version": 3,
  "engine": {
    "name": "MotorVideojuegosIA",
    "version": "2026.03",
    "api_version": "1",
    "capabilities_schema_version": 1
  },
  "implemented_capabilities": [
    {
      "id": "scene:create",
      "summary": "Create a new scene with a unique file path",
      "mode": "both",
      "status": "implemented",
      "api_methods": ["SceneWorkspaceAPI.create_scene"],
      "cli_command": "motor scene create <name>",
      "example": {
        "description": "Create a new scene called 'Level 1'",
        "api_calls": [
          {
            "method": "create_scene",
            "args": {
              "name": "Level 1"
            }
          }
        ],
        "expected_outcome": "A new scene file is created and becomes active"
      },
      "notes": "Scene name is sanitized for the filename.",
      "tags": ["scene", "authoring", "workspace"]
    }
  ],
  "planned_capabilities": [
    {
      "id": "runtime:step",
      "summary": "Advance runtime simulation by a number of frames",
      "mode": "play",
      "status": "planned",
      "api_methods": ["RuntimeAPI.step"],
      "cli_command": "motor step <frames>",
      "example": {
        "description": "Advance simulation",
        "api_calls": [
          {
            "method": "step",
            "args": {
              "frames": 1
            }
          }
        ],
        "expected_outcome": "Simulation advances one frame"
      },
      "notes": "Listed as planned when no public CLI parser exists.",
      "tags": ["runtime"]
    }
  ],
  "capability_counts": {
    "implemented": 1,
    "planned": 1,
    "total": 2
  },
  "project": {
    "name": "MyGame",
    "root": ".",
    "engine_version": "2026.03",
    "template": "empty",
    "paths": {
      "assets": "assets",
      "levels": "levels",
      "prefabs": "prefabs",
      "scripts": "scripts",
      "settings": "settings",
      "meta": ".motor/meta",
      "build": ".motor/build"
    }
  },
  "entrypoints": {
    "manifest": "project.json",
    "settings": "settings/project_settings.json",
    "startup_scene": "levels/main_scene.json",
    "scripts_dir": "scripts",
    "assets_dir": "assets",
    "levels_dir": "levels",
    "prefabs_dir": "prefabs"
  }
}
```

Las secciones `project` y `entrypoints` aparecen cuando el bootstrap recibe datos
de proyecto. Los tests de portabilidad verifican que esas rutas sean relativas.

## Campos principales

### `schema_version`

Version del contrato del archivo. El valor actual generado por el codigo es `3`.

### `engine`

Metadatos del motor:

- `name`
- `version`
- `api_version`
- `capabilities_schema_version`

### `implemented_capabilities`

Lista de capacidades disponibles ahora. Cada entrada debe tener
`status = "implemented"` y, si declara `cli_command`, debe usar la CLI oficial
`motor`.

### `planned_capabilities`

Lista de capacidades no disponibles como interfaz publica completa. Se conserva
para orientacion de agentes, pero no autoriza a invocar comandos inexistentes.

### `capability_counts`

Resumen derivado:

- `implemented = implemented_capabilities.length`
- `planned = planned_capabilities.length`
- `total = implemented + planned`

### `project`

Metadatos portables del proyecto. `root` debe ser `"."`; `paths` debe contener
rutas relativas.

### `entrypoints`

Archivos y carpetas que una IA puede usar para orientarse dentro del proyecto.
Todos los valores son relativos.

## Compatibilidad legacy

Schemas `1` y `2` usaban una forma anidada:

```json
{
  "schema_version": 2,
  "capabilities": {
    "capabilities": []
  }
}
```

`motor doctor` conserva lectura de esa forma para proyectos antiguos y reporta
los conteos como implementados. Esa estructura no debe usarse en bootstrap nuevo.

## Uso desde CLI

```bash
py -m motor project bootstrap-ai --project . --json
py -m motor doctor --project . --json
py -m motor capabilities --json
```

`doctor` no crea archivos. `project bootstrap-ai` es el comando que escribe
`motor_ai.json` y `START_HERE_AI.md`.

## Validaciones relevantes

- `tests/test_bootstrap_portability.py`
- `tests/test_doctor_bootstrap_flow.py`
- `tests/test_motor_cli_contract.py`
- `tests/test_official_contract_regression.py`
- `tests/test_motor_interface_coherence.py`
- `tests/test_motor_registry_consistency.py`
- `tests/test_project_service.py`

Estas suites cubren portabilidad de rutas, schema v3, separacion
implemented/planned, conteos, uso de `motor` y comportamiento read-only de
`doctor`.
