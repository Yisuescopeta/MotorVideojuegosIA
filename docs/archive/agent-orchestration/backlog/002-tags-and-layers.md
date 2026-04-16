# Task Brief

## Metadata

- `task_id`: unity-core-002
- `created_by`: Agente Orquestador
- `priority`: unity-2d-core-gap
- `execution_mode`: sequential
- `requested_agents`: Agente Orquestador, Feature Scout, Core Architect, Core Implementer, QA & Regression, Docs & Contracts
- `status`: ready

## Objective

Completar el soporte de `tag` y `layer` como metadatos de primera clase en
scene, API y editor, y usarlos en filtros simples de seleccion y reglas.

## Scope

- In scope: visibilidad, edicion y serializacion de tags/layers
- Out of scope: matrices complejas de colision por capas
- Affected subsystems: scenes, api, editor, events
- Candidate files: engine/scenes/scene.py, engine/api/engine_api.py, engine/inspector/inspector_system.py

## Constraints

- IA-first rule: la fuente de verdad debe vivir en codigo y datos serializables; la UI solo traduce ese modelo y toda accion del usuario debe existir tambien por API o datos accesibles por IA.
- No inventar una base de datos aparte de tags.
- Mantener el modelo simple y entendible.

## Acceptance Criteria

- [ ] La entidad expone `tag` y `layer` por API.
- [ ] La escena los serializa y restaura correctamente.
- [ ] La UI muestra y permite editar esos metadatos usando la misma via de authoring.
- [ ] Existe al menos un uso funcional sencillo en runtime o tooling.

## Validation Plan

- `py -3 -m unittest tests.test_unity_core_authoring`
- `py -3 tests/test_api_usage.py`

## Handoff Notes

- Dependencies: `001-entity-activation.md`
- Known risks: UI mostrando datos desactualizados tras rebuild
- Recommended next agent: Core Architect
