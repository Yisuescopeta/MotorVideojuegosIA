# Task Brief

## Metadata

- `task_id`: unity-core-003
- `created_by`: Agente Orquestador
- `priority`: unity-2d-core-gap
- `execution_mode`: sequential
- `requested_agents`: Agente Orquestador, Feature Scout, Core Architect, Core Implementer, QA & Regression, Docs & Contracts
- `status`: ready

## Objective

Consolidar `Camera2D` como capacidad de juego de primera clase para `Game View`,
con componente serializable, control por API y soporte minimo visible en editor.

## Scope

- In scope: camara primaria, offset, zoom, seguimiento simple por nombre
- Out of scope: blending, camaras multiples avanzadas, postprocesado
- Affected subsystems: components, systems, core, api
- Candidate files: engine/components/camera2d.py, engine/systems/render_system.py, engine/api/engine_api.py

## Constraints

- IA-first rule: la fuente de verdad debe vivir en codigo y datos serializables; la UI solo traduce ese modelo y toda accion del usuario debe existir tambien por API o datos accesibles por IA.
- No mezclar la camara del editor con la camara del juego.
- La `Scene View` sigue usando camara de editor; la `Game View` usa `Camera2D`.

## Acceptance Criteria

- [ ] La `Game View` usa la `Camera2D` primaria cuando exista.
- [ ] La API puede crear, leer y editar la camara.
- [ ] La escena serializa y restaura la configuracion.
- [ ] El editor refleja ese estado sin convertirse en fuente de verdad.

## Validation Plan

- `py -3 tests/test_api_usage.py`
- `py -3 -m unittest tests.test_unity_core_authoring`
- smoke visual opcional en `Game View`

## Handoff Notes

- Dependencies: `002-tags-and-layers.md`
- Known risks: doble aplicacion de camara en render
- Recommended next agent: Core Architect
