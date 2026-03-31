# Arquitectura del motor 2D IA-first

## Objetivo

Este documento fija el contrato arquitectonico que el proyecto considera
vigente:

- la UI no es la fuente de verdad
- el modelo serializable manda
- editor, runtime y API operan sobre el mismo contrato de datos

La clasificacion de que cae en `core obligatorio`, `modulos oficiales
opcionales` o `experimental/tooling` vive en
[module_taxonomy.md](./module_taxonomy.md). Esa taxonomia no cambia este
contrato: solo fija prioridades y limites de compatibilidad alrededor del mismo
modelo compartido.

## Fuente de verdad

### Authoring persistente

La fuente de verdad persistente vive en datos serializables:

- escenas JSON con `scene schema_version = 2`
- prefabs con `prefab schema_version = 2`
- migraciones explicitas `legacy/v1 -> v2`
- `feature_metadata` y reglas declarativas serializadas junto a la escena

La carga migra y valida antes de construir runtime. El guardado emite siempre
payload canonico `v2`.

### Representaciones en memoria

Las representaciones en memoria son proyecciones del mismo modelo:

- `Scene` conserva la version editable y persistible del contenido
- `SceneManager.edit_world` es una reconstruccion editable derivada de `Scene`
- `SceneManager.runtime_world` es un clon temporal para `PLAY`
- `Game.world` y `HeadlessGame.world` exponen el `active_world`, pero no
  sustituyen al modelo serializable

## Superficie de mutacion autorizada

La mutacion de contenido debe pasar por rutas compartidas de authoring:

- `SceneManager.apply_edit_to_world()`
- `SceneManager.update_entity_property()`
- `SceneManager.replace_component_data()`
- `SceneManager.add_component_to_entity()`
- `SceneManager.remove_component_from_entity()`
- `SceneManager.create_entity()` y operaciones estructurales relacionadas
- `EngineAPI` como fachada publica para agentes, tooling y tests

`sync_from_edit_world()` sigue existiendo, pero se considera compatibilidad
legacy explicita para rutas antiguas de edicion directa sobre `edit_world`. No
es el flujo normal recomendado para authoring nuevo.

Los previews transitorios de gizmos no deben contaminar dirty state, save ni
autosave.

## Responsabilidades por capa

### Scene

- guarda entidades, componentes, reglas y `feature_metadata`
- resuelve prefabs y crea un `World` desde datos
- aplica actualizaciones serializables por entidad y componente

### SceneManager

- coordina workspaces de escena
- mantiene `Scene`, `edit_world` y `runtime_world`
- controla la transicion `EDIT -> PLAY -> STOP`
- registra dirty state, historial y transacciones

Internamente esta troceado en colaboradores con responsabilidades separadas:

- workspace y lifecycle
- authoring estructural y prefabs
- transacciones e historial

Ese troceado no cambia su fachada publica ni abre rutas nuevas fuera del
contrato comun.

### Game / HeadlessGame

- coordinan estado del motor, tiempo y sistemas
- nunca son la fuente de verdad persistente
- en `PLAY` trabajan sobre un clon temporal
- mantienen una fachada publica estable aunque internamente `Game` este
  dividido en controladores

Los controladores internos no forman parte del contrato publico.

### EngineAPI

- expone authoring, runtime, workspace, assets, debug y UI serializable
- debe ofrecer operaciones funcionales equivalentes a las rutas principales de
  la UI
- no debe depender de internals privados del runtime ni abrir atajos paralelos
  al contrato de `SceneManager`

### UI / editor

- visualiza y traduce operaciones de usuario
- puede mantener estado visual efimero de layout, hover o seleccion
- no puede introducir datos funcionales inaccesibles por API o no
  serializables

## Invariantes testables

1. `load -> edit -> save -> load` conserva entidades, componentes y
   `feature_metadata`.
2. `EDIT -> PLAY -> STOP` no contamina la escena editable con mutaciones de
   runtime.
3. Las rutas principales de authoring disponibles en UI tienen equivalente por
   `EngineAPI` o por datos serializables.
4. Un cambio en `EDIT` termina reflejado en `Scene` y en el `edit_world`
   reconstruido.
5. Prefabs y overrides se guardan como datos, no como copias oportunistas de
   UI.
6. El headless puede ejecutar escenas sin depender de layout ni ventana.
7. La seleccion puede persistir entre `EDIT`, `PLAY`, `STOP` y cambios de
   escena del workspace sin convertirse en estado serializable.
8. La seleccion del backend fisico puede pedir `box2d` y caer en fallback a
   `legacy_aabb` sin mutar el backend solicitado en `feature_metadata`.

## Cobertura de pruebas relevante

- `tests/test_core_regression_matrix.py`
- `tests/test_scene_workspace.py`
- `tests/test_engine_api_public_contract.py`
- `tests/test_schema_validation.py`
- `tests/test_physics_backend.py`

## Limites y riesgos actuales

- siguen existiendo algunas rutas legacy de edicion directa sobre `edit_world`;
  deben quedar acotadas y depender de sincronizacion explicita de compatibilidad
- el determinismo se persigue en la misma maquina y entorno, no como garantia
  cross-platform fuerte
- `box2d` es opcional; el core no lo exige como dependencia obligatoria
- RL, datasets y runners paralelos existen, pero quedan fuera del core
  obligatorio y se documentan como `experimental/tooling`

## Regla de extension

Antes de introducir una feature nueva, hay que responder estas preguntas:

1. Donde se serializa.
2. Como se edita sin depender de UI.
3. Como se valida en headless.
4. Como se restaura tras `STOP` si participa en runtime.
5. Si pertenece al core, a un modulo oficial opcional o a
   `experimental/tooling`.
