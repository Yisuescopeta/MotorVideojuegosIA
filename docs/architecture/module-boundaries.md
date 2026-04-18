# Limites Practicos De Modulos

Estado: referencia operativa para reparto de trabajo. La clasificacion canonica
de subsistemas sigue en `docs/module_taxonomy.md`.

## Uso de este documento

Este mapa no redefine arquitectura. Sirve para decidir que puede tocar una rama
sin abrir colisiones innecesarias entre agentes o workspaces.

## Touch map por area

| Area | Subsistema principal | Tipo de trabajo esperado | Ramas que deberian tocarla |
|---|---|---|---|
| `docs/` | documentacion canonica y operativa | docs, gobernanza, guias | `docs/*`, `chore/*` documentales |
| `.github/` | gobernanza de revision | plantillas, workflows, issue/PR policy | `docs/*`, `chore/*` de repo |
| `tests/` de gobernanza y contrato | validacion de repo y contrato publico | regresiones documentales, CLI y contrato | `test/*`, `docs/*` si el cambio lo exige |
| `engine/api/` | fachada publica | API publica, automatizacion, authoring publico | `feat/api-*`, `refactor/api-*` |
| `engine/scenes/` | escena, workspace, authoring | save/load, scene flow, dirty state | `feat/scenes-*`, `refactor/scenes-*` |
| `engine/core/` | runtime base | loop, game state, mundo activo | `feat/runtime-*`, `refactor/runtime-*` |
| `engine/app/` | app y control runtime/editor | wiring de app, controladores base | `feat/runtime-*`, `feat/editor-*` |
| `engine/rendering/` | render backend y recursos | pipeline de render, materiales, surfaces | `feat/render-*`, `refactor/render-*` |
| `engine/systems/` | sistemas runtime compartidos | render system, physics system, audio system, UI system | ramas del dominio especifico y con cuidado alto |
| `engine/physics/` | contrato fisico | backends, queries, integracion de fisica | `feat/physics-*`, `test/physics-*` |
| `engine/tilemap/` | tilemaps | datos y helpers especificos de tilemap | `feat/tilemap-*`, `test/tilemap-*` |
| `engine/navigation/` | navegacion | pathing y algoritmos asociados | `feat/navigation-*`, `test/navigation-*` |
| `engine/editor/` | editor visual | paneles, tooling visual, authoring UI | `feat/editor-*`, `refactor/editor-*` |
| `engine/assets/` | pipeline de assets | indexado, slicing, metadata | `feat/assets-*`, `test/assets-*` |
| `engine/rl/` | tooling experimental | wrappers RL y runners | `feat/tooling-*`, `feat/rl-*` |
| `motor/` | CLI publica | parser, comandos oficiales, salida publica | `feat/cli-*`, `docs/*` solo si es ajuste minimo y justificado |

## Archivos criticos congelados por defecto

No tocar salvo tarea explicita y justificada:

- `engine/scenes/scene_manager.py`
- `engine/core/game.py`
- `engine/app/runtime_controller.py`
- `engine/systems/render_system.py`
- `engine/systems/physics_system.py`
- `engine/systems/collision_system.py`
- `engine/components/tilemap.py`
- `engine/levels/component_registry.py`

## Reglas de reparto por subsistema

- una rama debe declarar un area principal del touch map
- si toca otra area, debe ser dependencia inmediata y quedar explicada
- si un cambio requiere `engine/scenes/`, `engine/core/` y `motor/` a la vez,
  el alcance es sospechoso y debe partirse o pasar por RFC lite
- `docs/` y `.github/` pueden tocarse juntos en trabajo de gobernanza
- `tests/` acompana al subsistema tocado, no abre un refactor transversal por si solo

## Ejemplos permitidos

- una rama `docs/repo-branch-guidelines` toca `docs/` y `.github/`
- una rama `feat/render-batching-pass-1` toca `engine/rendering/` y tests de render
- una rama `test/physics-ray-regression` toca tests de fisica y, si hace falta,
  un fix pequeno dentro de `engine/physics/`
- una rama `feat/editor-selection-panel` toca `engine/editor/` y tests del editor

## Ejemplos no permitidos

- una rama `feat/render-batching-pass-1` que ademas reordena `engine/core/`
- una rama `refactor/runtime-cleanup` que tambien cambia CLI y docs de roadmap
- una rama `feat/tilemap-paint` que edita `scene_manager.py` sin tarea explicita
- una rama `docs/master-plan` que cambia `EngineAPI` o parser de `motor`

## Mapa practico para agentes

- si el prompt no lista archivos permitidos, asumir solo el subsistema principal
- si el prompt no excluye archivos criticos, excluirlos por defecto
- si un agente detecta que necesita otro subsistema core, debe detener la
  expansion y registrar el cruce
- si dos ramas quieren el mismo archivo critico, integrar por orden y no en paralelo
