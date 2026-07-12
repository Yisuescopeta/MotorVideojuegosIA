# Arquitectura canonica

Este documento fija el contrato arquitectonico vigente del repo. La referencia
de clasificacion por subsistema esta en [module_taxonomy.md](module_taxonomy.md).

## Principio central

El motor no debe esconder estado funcional en la UI. La fuente de verdad
persistente vive en datos serializables.

- `Scene` es la fuente de verdad persistente.
- `World` es una proyeccion operativa.
- `SceneManager` coordina el workspace editable y el ciclo `EDIT -> PLAY -> STOP`.
- `EngineAPI` es la fachada publica para agentes, tests, CLI y automatizacion.

El contrato base vigente usa:

- `scene schema_version = 2`
- `prefab schema_version = 2`
- migracion explicita de payloads legacy y `v1` a `v2`
- guardado canonico en `v2`

## Representaciones

### Scene

`Scene` conserva el contenido editable y persistible: entidades, componentes
serializables, reglas, `feature_metadata` y referencias de prefab. Un cambio de
authoring que deba persistir tiene que terminar en `Scene`.

### World

`World` contiene entidades activas para editor y runtime. No es un formato de
persistencia ni sustituye a `Scene`.

`SceneManager.edit_world` es una reconstruccion editable desde la escena.
`SceneManager.runtime_world` es un clon temporal usado en `PLAY`.
`Game.world` y `HeadlessGame.world` exponen el mundo activo para sistemas, pero
no son la fuente de verdad persistente.

`World` conserva la autoridad sobre entidades, seleccion, callbacks,
notificaciones y versionado. La separacion interna de sus servicios queda asi:

- `engine.ecs.group_registry.GroupRegistry` es la autoridad del indice de
  grupos. `world.group_registry` sigue siendo la superficie estable y el
  registro mantiene su dependencia de `World` para resolver entidades.
- `engine.ecs.world_serialization.serialize_world()` es la autoridad de
  serializacion; `World.serialize()` permanece como fachada compatible.
- `engine.ecs.world_clone.clone_world()` es la autoridad de clonacion;
  `World.clone()` permanece como fachada compatible y pasa la factory exacta
  `World`.

Esta separacion no cambia Scene v2, el schema ni el payload serializado, la
superficie publica de `EngineAPI` o el ciclo `EDIT -> PLAY -> STOP`.

## Ciclo EDIT -> PLAY -> STOP

```text
Scene serializable
  -> edit_world para authoring
  -> runtime_world temporal para PLAY
  -> vuelta a edit_world sin contaminar authoring
```

Invariantes:

1. Las mutaciones de runtime no se guardan como authoring por accidente.
2. La seleccion puede sobrevivir a cambios de modo sin volverse dato serializable de escena.
3. Previews transitorios de gizmos no deben marcar dirty state ni autosave.
4. Un save/load roundtrip conserva entidades, componentes, jerarquia y `feature_metadata`.

## Superficie de mutacion autorizada

Las rutas compartidas de authoring son:

- `SceneManager.apply_edit_to_world()`
- `SceneManager.update_entity_property()`
- `SceneManager.replace_component_data()`
- `SceneManager.add_component_to_entity()`
- `SceneManager.remove_component_from_entity()`
- operaciones estructurales de `SceneManager`
- metodos publicos equivalentes en `EngineAPI`

`sync_from_edit_world()` existe para compatibilidad legacy explicita. No es la
ruta normal para nuevas superficies publicas de authoring.

## Responsabilidades por capa

### Export pipeline

El build oficial de juegos separa editor y runtime:

```text
Proyecto editable -> validacion -> grafo de contenido -> content pack ->
runtime template de plataforma -> artefacto jugable -> smoke/report
```

`Scene` sigue siendo fuente persistente de verdad. `World` no se serializa como
authoring durante export. La automatizacion publica entra por `EngineAPI` o
`py -m motor export ...`. El runtime exportado usa `engine/runtime/exported_game.py`
y carga `runtime_config.json`, `game.manifest.json`, `game.pak` o `content/` sin
arrancar paneles de editor.

Documentacion relacionada: [export_pipeline.md](export_pipeline.md),
[export_presets.md](export_presets.md), [runtime_templates.md](runtime_templates.md),
[build_artifacts.md](build_artifacts.md), [mobile_export.md](mobile_export.md),
[troubleshooting_export.md](troubleshooting_export.md).

### SceneManager

Responsable de workspace, escenas abiertas, escena activa, dirty state,
transacciones, historial, operaciones estructurales y transicion entre modos.

La persistencia tecnica queda separada por responsabilidades:

- `ScenePersistenceService` es la autoridad de resolucion de rutas, storage
  default o custom, escritura temporal y reemplazo del storage default,
  readback, migracion, validacion, recuento de entidades y lectura de mtime.
- `SceneManager` conserva instalacion de payloads, rekey del workspace, dirty y
  pending state, tracking de mtime y callbacks de guardado.
- `SceneWorkspace` conserva solo estado y ciclo de vida en memoria; no realiza
  I/O.

La separacion mantiene las firmas publicas, Scene v2 y su schema. Tambien
preserva la atomicidad vigente: temporal mas reemplazo para storage default y
la semantica provista por cada storage custom.

### Game y HeadlessGame

Coordinan tiempo, estado del motor y sistemas sobre el mundo activo. No deben
convertirse en una ruta paralela de persistencia.

### EngineAPI

`EngineAPI` expone authoring, runtime, workspace, scene flow, assets, proyecto,
debug y UI serializable. Wrappers RL, CLI, tests y automatizacion deben usar
esta fachada en vez de internals privados.

## Contratos internos base

La base tecnica compartida de Fase 1 hace explicitos tres puertos internos de
escena y un contexto de runtime:

- `SceneRuntimePort`: ciclo `EDIT -> PLAY -> STOP` y acceso al mundo activo.
- `SceneAuthoringPort`: mutaciones serializables y operaciones estructurales.
- `SceneWorkspacePort`: workspace multi-escena, guardado y scene flow.
- `RuntimeControllerContext`: wiring explicito entre runtime, escena y sistemas.

`SceneManager` sigue siendo la implementacion concreta y `EngineAPI` mantiene la
misma superficie publica. El cambio solo formaliza limites internos para que
fases posteriores extiendan runtime, render, fisica, tilemaps, animacion, UI,
audio, navegacion, editor y tooling sin introducir nuevos accesos cruzados.

### Editor/UI

La UI visualiza y traduce acciones de usuario. Puede mantener estado efimero de
layout, hover o seleccion visual. No debe introducir comportamiento funcional
inaccesible por `EngineAPI` o por datos serializables.

Sincronizacion escena-editor: `Scene` es la fuente de verdad. `World` se refresca
como proyeccion operativa cuando la escena se recarga. Un guardado exitoso de
escena puede notificar al editor para refrescar vistas. La recarga segura de
archivo stale evita descartar estado de authoring sucio no guardado.

## Contrato fisico

El core conserva un contrato comun de backends fisicos:

- `legacy_aabb` esta siempre disponible
- `box2d` es opcional
- si `box2d` no puede activarse, el runtime cae a `legacy_aabb`
- el backend solicitado en `feature_metadata.physics_2d.backend` no debe sobrescribirse por el fallback efectivo
- `query_physics_ray` y `query_physics_aabb` mantienen su significado publico
- `body_test_motion` añade un sweep-test no-mutante (barrido de colisión sin modificar el mundo), bloque fundamental del que depende `move_and_slide`
- **PGS Impulse Solver (dos fases):** tras integrar fuerzas, el sistema construye constraints de contacto y joints bilaterales (fixed, distance, pin) entre cuerpos, agrupa en islas via BFS, y ejecuta:
  1. **PGS velocity solve** (8 iteraciones): impulsos normales con clamp no-negativo y friccion Coulomb
  2. **PGS position solve** (3 iteraciones): correccion mass-weighted sobre transforms con age-based damping
  Los joints bilaterales usan `is_bilateral=True` para permitir impulso negativo.
- **Broadphase unificado**: `SpatialHash2D` compartido y reutilizado entre
  `PhysicsSystem`, `CollisionSystem` y queries espaciales. El tamano de celda se
  selecciona de forma determinista desde el tamano mediano de los colliders,
  limitado a `32..256px`; AABB gigantes usan un registro conservativo separado.
- **Cache geometrica runtime**: AABB y `ShapeInstance` se reutilizan entre
  frames mientras no cambien transform, estado enabled ni geometria del
  collider. La cache no es authoring state ni se serializa.
- **Joint stiffness**: `Joint2D.joint_stiffness` (default 0.2) controla bias en constraints PGS bilaterales.

## Taxonomia arquitectonica

Los documentos principales usan tres categorias:

- `core obligatorio`
- `modulos oficiales opcionales`
- `experimental/tooling`

La clasificacion completa vive en [module_taxonomy.md](module_taxonomy.md).

## Cobertura relevante

- `tests/test_core_regression_matrix.py`
- `tests/test_scene_workspace.py`
- `tests/test_engine_api_public_contract.py`
- `tests/test_schema_validation.py`
- `tests/test_physics_backend.py`
- `tests/test_repository_governance.py`

## Regla de extension

Antes de introducir una feature nueva, definir:

1. Donde se serializa.
2. Como se edita sin depender de UI.
3. Como se valida en headless.
4. Como vuelve a estado editable tras `STOP` si participa en runtime.
5. Si pertenece a `core obligatorio`, `modulos oficiales opcionales` o `experimental/tooling`.
