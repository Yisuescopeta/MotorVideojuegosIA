# Task Brief

## Metadata

- `task_id`: unity-core-001
- `created_by`: Agente Orquestador
- `priority`: unity-2d-core-gap
- `execution_mode`: sequential
- `requested_agents`: Agente Orquestador, Feature Scout, Core Architect, Core Implementer, QA & Regression, Docs & Contracts
- `status`: ready

## Objective

Completar la activacion de entidades y la habilitacion de componentes en todo el
runtime para que render, seleccion, fisica, colisiones y animacion respeten el
estado serializable del modelo.

## Scope

- In scope: completar la propagacion de `active` y `enabled` en sistemas y UI
- Out of scope: sistema de permisos complejo o jerarquias de activacion avanzadas
- Affected subsystems: core, ecs, systems, api, editor
- Candidate files: engine/ecs/world.py, engine/systems/*.py, engine/inspector/inspector_system.py

## Constraints

- IA-first rule: la fuente de verdad debe vivir en codigo y datos serializables; la UI solo traduce ese modelo y toda accion del usuario debe existir tambien por API o datos accesibles por IA.
- No introducir flags solo visuales.
- Cualquier toggle hecho en UI debe terminar persistiendo en la escena serializable.

## Acceptance Criteria

- [ ] Entidades inactivas no participan en runtime ni seleccion.
- [ ] Componentes deshabilitados no participan en sistemas.
- [ ] API y UI pueden activar o desactivar el mismo estado.
- [ ] La escena serializada conserva esos valores.

## Validation Plan

- `py -3 tests/test_api_usage.py`
- `py -3 -m unittest tests.test_unity_core_authoring`

## Handoff Notes

- Dependencies: ninguna
- Known risks: divergencia entre scene y edit_world
- Recommended next agent: Core Architect
