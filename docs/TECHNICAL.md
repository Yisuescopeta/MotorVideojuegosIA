# Documentacion tecnica del motor 2D

## Resumen tecnico

El motor se organiza alrededor de un modelo ECS y de un contrato serializable de
escena/prefab. El punto importante no es solo que exista editor, runtime o CLI,
sino que las tres capas operan sobre el mismo modelo de datos.

Contrato base vigente:

- `scene schema_version = 2`
- `prefab schema_version = 2`
- migraciones explicitas de payloads legacy y `v1`
- guardado siempre en payload canonico `v2`

La fuente de verdad persistente es `Scene`. `World` es una proyeccion operativa
del mismo contenido.

## Modelo de datos

### Scene

`Scene` encapsula el payload editable y persistible:

- `name`
- `schema_version`
- `entities`
- `rules`
- `feature_metadata`

Ademas:

- resuelve prefabs al reconstruir `World`
- preserva `feature_metadata`
- permite actualizar entidad, componente y metadata serializable sin depender de
  UI

### World

`World` es el contenedor de entidades activas utilizado por editor y runtime.
No es la fuente de verdad persistente.

Propiedades relevantes del contrato operativo:

- entidades con nombre unico
- filtrado por componentes via `get_entities_with(...)`
- `feature_metadata` accesible desde el mundo activo
- seleccion activa (`selected_entity_name`) como estado de workspace/runtime,
  no como dato persistente de escena

### SceneManager

`SceneManager` coordina la vida de la escena editable:

- `load_scene(...)` y `load_scene_from_file(...)`
- workspace multi-escena
- `enter_play()` y `exit_play()`
- dirty state por escena
- historial y transacciones
- seleccion persistente entre `EDIT`, `PLAY`, `STOP` y cambios de pestaña

Internamente esta separado por responsabilidades:

- `workspace_lifecycle.py`
- `structural_authoring.py`
- `change_history.py`

La fachada publica sigue centralizada en `SceneManager`.

## Componentes registrados hoy

La fuente de verdad sobre componentes registrados es
`engine/levels/component_registry.py`. Las familias activas hoy son:

### Espacial y render

- `Transform`
- `RectTransform`
- `Sprite`
- `Animator`
- `Camera2D`
- `RenderOrder2D`
- `RenderStyle2D`

### Gameplay y fisica

- `Collider`
- `RigidBody`
- `CharacterController2D`
- `PlayerController2D`
- `Joint2D`
- `InputMap`
- `AudioSource`
- `ScriptBehaviour`

### Escena, tilemap y UI serializable

- `Tilemap`
- `SceneLink`
- `Canvas`
- `UIText`
- `UIButton`

No se debe asumir soporte publico para componentes fuera de ese registry.

## Sistemas y runtime

### RenderSystem

`RenderSystem` no solo dibuja sprites. Hoy tambien:

- construye un render graph publico con passes `World`, `Overlay` y `Debug`
- ordena por sorting layer y `order_in_layer`
- agrupa entidades contiguas por material, atlas y capa
- soporta `Tilemap` por chunks con cache y rebuild incremental
- puede emitir debug geometry dump y metricas de profiling
- usa render targets con fallback seguro cuando no hay backend grafico

### Physics y collision

El runtime fisico opera contra un contrato comun de backend:

- backend efectivo por defecto `legacy_aabb`
- `box2d` opcional cuando la dependencia esta disponible
- fallback explicito a `legacy_aabb` si `box2d` no puede activarse
- la fachada publica expone `query_physics_ray` y `query_physics_aabb`
- `query_shape` permanece como parte del contrato interno de backend, no como
  API publica del motor

El backend solicitado se expresa en `feature_metadata.physics_2d.backend`. El
fallback no debe sobrescribir ese valor pedido; solo cambia la seleccion
efectiva en runtime.

### Animation, input, scripts y UI

Tambien forman parte del runtime actual:

- `AnimationSystem`
- `InputSystem`
- `CharacterControllerSystem`
- `PlayerControllerSystem`
- `ScriptBehaviourSystem`
- `AudioSystem`
- `UISystem`
- `UIRenderSystem`

`ScriptBehaviour.public_data` sigue siendo la unica bolsa persistente del
script. El resto del estado de modulo es runtime.

## Reglas y eventos

`EventBus` y `RuleSystem` permiten gameplay declarativo desde datos de escena.

Acciones soportadas por contrato:

- `set_animation`
- `set_position`
- `destroy_entity`
- `emit_event`
- `log_message`

`RuleSystem` admite binding por fases:

- se construye con `event_bus`
- enlaza el `World` activo despues mediante `set_world(world)`

Las acciones que requieren entidad se omiten con warning si aun no hay `world`.

## Flujo de escenas y workspace

### Ciclo `EDIT -> PLAY -> STOP`

El flujo correcto hoy es:

```text
Scene (serializable)
  -> edit_world (editable)
  -> runtime_world (clon temporal para PLAY)
  -> reconstruccion de edit_world al volver a STOP
```

Invariantes operativos:

- las mutaciones runtime no deben contaminar `Scene`
- la seleccion puede sobrevivir al cambio de modo
- dirty/save/autosave no deben contaminarse con previews transitorios de gizmos

### Rutas de authoring recomendadas

Las rutas compartidas de authoring siguen siendo:

- `SceneManager.apply_edit_to_world()`
- `SceneManager.update_entity_property()`
- `SceneManager.replace_component_data()`
- `SceneManager.add_component_to_entity()`
- `SceneManager.remove_component_from_entity()`
- operaciones estructurales como crear entidad, duplicar subarbol o reparentar
- `EngineAPI` como fachada publica equivalente

`sync_from_edit_world()` queda como compatibilidad legacy explicita, no como via
principal para authoring nuevo.

## EngineAPI publica

`EngineAPI` es la fachada publica que el repositorio considera estable.
Internamente delega por dominios, pero el punto de entrada publico sigue siendo
uno.

Dominios actuales:

- authoring
- runtime
- workspace y scene flow
- assets y proyecto
- debug/profiler
- UI serializable

Ejemplos de superficie publica ya fijada por tests:

```python
from engine.api import EngineAPI

api = EngineAPI(project_root=".")
api.load_level("levels/platformer_test_scene.json")
api.set_entity_tag("Hero", "Player")
api.play()
api.step(2)
events = api.get_recent_events(count=10)
selection = api.get_physics_backend_selection()
```

Regla importante:

- wrappers RL, CLI y automatizacion deben usar `EngineAPI`
- no deben tocar hooks privados del runtime

## Invariantes realmente cubiertos por tests

La documentacion principal debe leerse junto con estas suites:

- `tests/test_core_regression_matrix.py`
- `tests/test_schema_validation.py`
- `tests/test_scene_workspace.py`
- `tests/test_engine_api_public_contract.py`
- `tests/test_physics_backend.py`

Cobertura relevante hoy:

- roundtrip `load -> edit -> save -> load`
- preservacion de `feature_metadata`
- compatibilidad de migracion `legacy/v1 -> v2`
- aislamiento de `PLAY` respecto a la escena editable
- seleccion persistente por workspace
- equivalencia funcional entre authoring directo y authoring via `EngineAPI`
- fallback fisico y contrato publico comparable entre backends

## Clasificacion tecnica del repo

La referencia canonica por subsistema vive en
[module_taxonomy.md](./module_taxonomy.md). El resumen tecnico es:

### Core obligatorio

- ECS, `Scene`, `SceneManager`, serializacion y schema/migraciones
- editor base, jerarquia y `EngineAPI`
- contrato comun de physics backends con fallback `legacy_aabb`

### Modulos oficiales opcionales

- assets y prefabs
- tilemap, audio y UI serializable
- `box2d` y otras capacidades oficiales no necesarias para el contrato minimo

### Experimental/tooling

- `engine/rl`
- datasets, runners y multiagente
- debug avanzado, benchmarking y tooling de investigacion

## Limites actuales

- el determinismo no se promete como garantia cross-platform estricta
- existen rutas legacy de edicion directa sobre `edit_world` que deben seguir
  acotadas
- RL y datasets existen, pero no forman parte del core obligatorio
- el proyecto sigue siendo experimental aunque varias bases del core ya esten
  cubiertas por tests
