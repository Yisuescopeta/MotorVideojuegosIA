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

### SceneManager

Responsable de workspace, escenas abiertas, escena activa, dirty state,
transacciones, historial, operaciones estructurales y transicion entre modos.

### Game y HeadlessGame

Coordinan tiempo, estado del motor y sistemas sobre el mundo activo. No deben
convertirse en una ruta paralela de persistencia.

### EngineAPI

`EngineAPI` expone authoring, runtime, workspace, scene flow, assets, proyecto,
debug y UI serializable. Wrappers RL, CLI, tests y automatizacion deben usar
esta fachada en vez de internals privados.

### Editor/UI

La UI visualiza y traduce acciones de usuario. Puede mantener estado efimero de
layout, hover o seleccion visual. No debe introducir comportamiento funcional
inaccesible por `EngineAPI` o por datos serializables.

## Contrato fisico

El core conserva un contrato comun de backends fisicos:

- `legacy_aabb` esta siempre disponible
- `box2d` es opcional
- si `box2d` no puede activarse, el runtime cae a `legacy_aabb`
- el backend solicitado en `feature_metadata.physics_2d.backend` no debe sobrescribirse por el fallback efectivo
- `query_physics_ray` y `query_physics_aabb` mantienen su significado publico

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
