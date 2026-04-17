# Referencia tecnica

Esta referencia resume el estado verificable del codigo. Para el contrato
arquitectonico lee [architecture.md](architecture.md); para la taxonomia lee
[module_taxonomy.md](module_taxonomy.md); para serializacion lee
[schema_serialization.md](schema_serialization.md).

## Contrato base

- `scene schema_version = 2`
- `prefab schema_version = 2`
- migraciones `legacy/v1 -> v2`
- validacion posterior a la migracion
- guardado canonico `v2`

`Scene` es persistente. `World` es una proyeccion operativa.

## Componentes registrados

La fuente de verdad para componentes publicos registrados es
`engine/levels/component_registry.py`.

Familias principales:

- Espacial/render: `Transform`, `RectTransform`, `Sprite`, `Animator`, `Camera2D`, `RenderOrder2D`, `RenderStyle2D`.
- Gameplay/fisica: `Collider`, `RigidBody`, `CharacterController2D`, `PlayerController2D`, `Joint2D`, `InputMap`, `AudioSource`, `ScriptBehaviour`.
- Escena, tilemap y UI: `Tilemap`, `SceneLink`, `SceneEntryPoint`, `SceneTransition*`, `Canvas`, `UIText`, `UIButton`, `UIImage`.

No se debe asumir soporte publico para componentes no registrados.

## Runtime y sistemas

El runtime usa `Game` o `HeadlessGame` para coordinar sistemas sobre el mundo
activo. Los sistemas actuales incluyen render, fisica, colisiones, animacion,
input, controladores de personaje/jugador, scripts, audio y UI.

`RenderSystem` mantiene la fachada publica del render 2D y delega la
planificacion/ejecucion del pipeline a `engine/rendering/`. La planificacion
vive en un planner de frame/passes/comandos y la ejecucion en un executor con
dispatch por tipo de comando y jobs de render target. Se conservan render
graph, sorting layers, batching base, tilemap chunks, debug geometry y render
targets con fallback seguro cuando no hay backend grafico disponible.

`UIRenderSystem` renderiza la UI overlay serializable. `UISystem` conserva
layout e interaccion; `UIRenderSystem` resuelve la capa visual para `UIText`,
`UIButton` por color o sprite, y `UIImage`.

El sistema fisico conserva `legacy_aabb` como fallback obligatorio y registra
`box2d` como backend opcional cuando la dependencia esta disponible.

## Reglas y eventos

`EventBus` y `RuleSystem` permiten gameplay declarativo desde datos de escena.

Acciones de reglas soportadas por contrato:

- `set_animation`
- `set_position`
- `destroy_entity`
- `emit_event`
- `log_message`

## Workspace y authoring

`SceneManager` coordina carga/guardado, workspace multi-escena, escena activa,
dirty state, historial, transacciones, `EDIT -> PLAY -> STOP`, operaciones
estructurales y prefabs.

Las rutas recomendadas para cambios persistentes son `SceneManager` y
`EngineAPI`. `sync_from_edit_world()` queda como compatibilidad legacy.

## EngineAPI publica

`EngineAPI` es la fachada estable para agentes, tests, CLI y automatizacion.
Internamente delega por dominios: authoring, runtime, workspace y scene flow,
assets/proyecto, debug/profiler y UI serializable.

```python
from engine.api import EngineAPI

api = EngineAPI(project_root=".")
api.load_level("levels/platformer_test_scene.json")
api.set_entity_tag("Hero", "Player")
api.play()
api.step(2)
events = api.get_recent_events(count=10)
selection = api.get_physics_backend_selection()
api.shutdown()
```

La referencia agrupada vive en [api.md](api.md).

## CLI oficial

La CLI publica es `motor`, implementada en `motor/cli.py`.

Comandos base:

- `motor capabilities`
- `motor doctor`
- `motor project info`
- `motor project bootstrap-ai`
- `motor scene list/create/load/save`
- `motor entity create`
- `motor component add`
- `motor prefab create/instantiate/unpack/apply/list`
- `motor animator ...`
- `motor asset ...`

La referencia completa vive en [cli.md](cli.md).

## IA, RL y tooling experimental

`engine/rl`, datasets, runners paralelos y workflows AI-assisted existen, pero
pertenecen a `experimental/tooling`, no al `core obligatorio`.

Docs relevantes:

- [rl.md](rl.md)
- [ai_assisted_workflows.md](ai_assisted_workflows.md)
- [navigation.md](navigation.md)

## Tests de contrato

- `tests/test_core_regression_matrix.py`
- `tests/test_schema_validation.py`
- `tests/test_scene_workspace.py`
- `tests/test_engine_api_public_contract.py`
- `tests/test_motor_cli_contract.py`
- `tests/test_official_contract_regression.py`
- `tests/test_repository_governance.py`

Cobertura relevante:

- roundtrip `load -> edit -> save -> load`
- preservacion de `feature_metadata`
- migraciones `legacy/v1 -> v2`
- aislamiento de `PLAY`
- equivalencia funcional de authoring por `EngineAPI`
- fallback fisico y queries publicas
- separacion entre capabilities implementadas y planificadas

## Limites actuales

- No se promete determinismo cross-platform estricto.
- Existen rutas legacy de edicion directa que deben permanecer acotadas.
- `box2d` no es dependencia obligatoria.
- `engine/rl` y datasets son experimentales.
- Material archivado en `docs/archive/` no es contrato vigente.
