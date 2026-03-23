# Arquitectura Del Motor 2D IA-First

## Objetivo

Este documento fija el contrato de arquitectura del proyecto para que nuevas
features no rompan la regla principal del repositorio:

- la UI no es la fuente de verdad
- el modelo serializable manda
- editor, runtime y API deben operar sobre el mismo contrato de datos

## Fuente De Verdad

### Authoring persistente

La fuente de verdad persistente vive en datos serializables:

- escenas JSON cargadas y guardadas por `engine/scenes/scene.py`
- prefabs y overrides serializables gestionados por `engine/scenes/scene.py`
  y `engine/scenes/scene_manager.py`
- metadatos de proyecto y editor gestionados por
  `engine/project/project_service.py`
- `feature_metadata` y reglas declarativas serializadas junto a la escena

### Representaciones en memoria

Las representaciones en memoria son proyecciones del modelo serializable:

- `Scene` contiene la version editable y persistible del contenido
- `SceneManager.edit_world` es una reconstruccion editable derivada de `Scene`
- `SceneManager.runtime_world` es un clon temporal para `PLAY`
- `Game.world` expone el `active_world`, pero no sustituye al modelo serializable

### Superficie de mutacion autorizada

La mutacion de contenido debe pasar por rutas compartidas:

- `SceneManager.apply_edit_to_world()`
- `SceneManager.update_entity_property()`
- `SceneManager.replace_component_data()`
- `SceneManager.add_component_to_entity()`
- `SceneManager.remove_component_from_entity()`
- `SceneManager.create_entity()` y variantes
- `EngineAPI` como fachada publica para agentes y tooling

La UI solo debe emitir cambios que acaben en esas rutas. No debe crear estado
funcional exclusivo de interfaz.

## Responsabilidades Por Capa

### Scene

- guarda entidades, componentes, reglas y `feature_metadata`
- resuelve prefabs y crea un `World` desde datos
- permite actualizaciones de datos serializables por entidad y componente

### SceneManager

- coordina workspaces de escena
- mantiene `Scene`, `edit_world` y `runtime_world`
- controla la transicion `EDIT -> PLAY -> STOP`
- reconstuye `edit_world` desde `Scene`
- registra historial de cambios y dirty state

### Game / HeadlessGame

- coordina estado del motor, tiempo y sistemas
- nunca es la fuente de verdad persistente del contenido
- en `PLAY` trabaja sobre un clon temporal
- en `EDIT` sincroniza cambios del mundo editable de vuelta a `SceneManager`

### EngineAPI

- expone authoring y runtime a agentes, scripts y tests
- debe ofrecer las mismas operaciones funcionales que la UI
- no debe abrir rutas alternativas que esquiven el contrato de `SceneManager`

### UI / Editor

- visualiza y traduce operaciones de usuario
- puede mantener estado visual efimero de layout o seleccion
- no puede introducir datos funcionales que no sean serializables o accesibles
  por API

## Invariantes Testables

1. `load -> edit -> save -> load` conserva entidades, componentes y
   `feature_metadata`.
2. `EDIT -> PLAY -> STOP` no contamina la escena editable con cambios runtime.
3. Toda operacion de authoring relevante disponible en UI tiene equivalente por
   `EngineAPI` o por datos serializables.
4. Un cambio de componente en `EDIT` termina reflejado en `Scene` y en el
   `edit_world` reconstruido.
5. Prefabs y overrides se guardan como datos, no como copias completas forzadas
   por conveniencia de UI.
6. El headless puede ejecutar escenas sin depender de ventana o layout.
7. Los hashes/huellas de estado deben derivarse de datos del mundo, no de
   estructuras de UI.

## Puntos De Integracion Para Fases Siguientes

### Serializacion y schema

- `engine/scenes/scene.py`
- `engine/scenes/scene_manager.py`
- `engine/ecs/world.py`

### Runtime reproducible

- `cli/headless_game.py`
- `engine/core/time_manager.py`
- `engine/debug/`

### API y authoring compartido

- `engine/api/engine_api.py`
- `engine/scenes/scene_manager.py`

### Tooling CLI

- `main.py`
- `cli/runner.py`
- `cli/script_executor.py`

## Riesgos Actuales

- existen rutas de mutacion directa sobre `edit_world` en herramientas de editor;
  dependen de `sync_from_edit_world()` para volver al modelo
- hay duplicidades y restos de iteracion en `main.py` y `engine/core/game.py`
- el headless existia, pero no tenia una salida canonica para golden runs ni una
  huella estable de estado

## Matriz De Pruebas Recomendada

| Area | Que validar | Tipo |
|---|---|---|
| Scene/serializacion | roundtrip de escenas y prefabs | unit/integration |
| SceneManager | `EDIT -> PLAY -> STOP`, dirty state, seleccion | integration |
| EngineAPI | authoring no visual, bloqueo de edicion en `PLAY` | integration |
| Headless harness | mismos inputs -> misma huella de estado | integration |
| Fingerprint | mismo contenido con distinto orden de construccion -> mismo hash | unit |
| CLI | ejecucion headless con salida JSON reproducible | smoke |

## Regla De Extension

Antes de introducir una feature nueva, hay que responder estas preguntas:

1. Donde se serializa.
2. Como se edita sin UI.
3. Como se valida en headless.
4. Como se restaura tras `STOP` si participa en runtime.
5. Como se representa en hashes o golden runs si afecta al estado observable.
