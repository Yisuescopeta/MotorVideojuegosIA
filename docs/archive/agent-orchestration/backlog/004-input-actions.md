# Task Brief

## Metadata

- `task_id`: unity-core-004
- `created_by`: Agente Orquestador
- `priority`: unity-2d-core-gap
- `execution_mode`: sequential
- `requested_agents`: Agente Orquestador, Feature Scout, Core Architect, Core Implementer, QA & Regression, Docs & Contracts
- `status`: ready

## Objective

Consolidar `InputMap` como authoring declarativo de primera clase con lectura por
API y comandos equivalentes en automatizacion para que IA y usuario puedan
editar y consultar bindings sin depender de input visual.

## Scope

- In scope: helpers API, lectura de estado serializable, comandos de automatizacion
- Out of scope: remapeo avanzado por dispositivo o rebinding visual complejo
- Affected subsystems: api, systems, cli, tests
- Candidate files: engine/api/engine_api.py, engine/systems/input_system.py, cli/script_executor.py, tests/test_unity_core_authoring.py

## Constraints

- IA-first rule: la fuente de verdad debe vivir en codigo y datos serializables; la UI solo traduce ese modelo y toda accion del usuario debe existir tambien por API o datos accesibles por IA.
- No introducir capas opacas de input dependientes de UI.
- Mantener el modelo de bindings simple, visible y serializable.

## Acceptance Criteria

- [ ] La API puede crear, leer y editar `InputMap`.
- [ ] Existe acceso no visual al ultimo estado calculado de input.
- [ ] Scripts de automatizacion pueden manipular bindings por comandos equivalentes.
- [ ] Hay prueba reproducible sin ventana visual.

## Validation Plan

- `py -3 tests/test_api_usage.py`
- `py -3 -m unittest tests.test_unity_core_authoring`

## Handoff Notes

- Dependencies: `001-entity-activation.md`
- Known risks: divergencia entre bindings serializados y estado runtime
- Recommended next agent: Core Architect
