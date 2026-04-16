# Task Brief

## Metadata

- `task_id`: unity-core-005
- `created_by`: Agente Orquestador
- `priority`: unity-2d-core-gap
- `execution_mode`: sequential
- `requested_agents`: Agente Orquestador, Feature Scout, Core Architect, Core Implementer, QA & Regression, Docs & Contracts
- `status`: ready

## Objective

Cerrar `AudioSource` como capacidad basica serializable con authoring por API,
estado consultable y comandos equivalentes en automatizacion para reproducir y
detener audio sin rutas exclusivas de UI.

## Scope

- In scope: helpers API, consultas de estado, comandos de script, validacion
- Out of scope: mezcla avanzada, spatial audio real, formatos complejos
- Affected subsystems: api, systems, cli, tests
- Candidate files: engine/api/engine_api.py, engine/systems/audio_system.py, cli/script_executor.py, tests/test_unity_core_authoring.py

## Constraints

- IA-first rule: la fuente de verdad debe vivir en codigo y datos serializables; la UI solo traduce ese modelo y toda accion del usuario debe existir tambien por API o datos accesibles por IA.
- No introducir estados de reproduccion exclusivos del editor.
- Mantener el modelo visible y entendible por IA.

## Acceptance Criteria

- [ ] La API puede crear, leer y editar `AudioSource`.
- [ ] La reproduccion/paro queda reflejada en estado consultable no visual.
- [ ] Scripts de automatizacion tienen comandos equivalentes.
- [ ] Existe prueba reproducible sin ventana visual.

## Validation Plan

- `py -3 tests/test_api_usage.py`
- `py -3 -m unittest tests.test_unity_core_authoring`

## Handoff Notes

- Dependencies: `001-entity-activation.md`
- Known risks: confusion entre estado serializado de authoring y estado runtime
- Recommended next agent: Core Architect
