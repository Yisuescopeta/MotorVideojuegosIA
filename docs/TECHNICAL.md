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
- Gameplay/fisica: `Collider`, `RigidBody`, `CharacterController2D`, `PlayerController2D`, `Joint2D`, `InputMap`, `AudioSource`, `ScriptBehaviour`, `RayCast2D`, `NavigationObstacle2D`.
- Gameplay semantico 2D: `Collectible2D`, `Hazard2D`, `Goal2D`, `RespawnPoint2D`, `MovingPlatform2D`, `EnemyPatrol2D`, `Checkpoint2D`, `KillZone2D`, `LevelBounds2D`. Son componentes serializables. En runtime, `Gameplay2DSemanticSystem` consume contactos fisicos existentes para emitir eventos de coleccionable, hazard, goal, checkpoint y killzone, aplicar respawn runtime y no modificar la escena serializada. Tambien evalua `LevelBounds2D` por frame: emite `level_bounds_exited`, clampa salidas horizontales y respawnea salidas por `bottom` con el respawn de sesion o el primer `RespawnPoint2D` activo. `Checkpoint2D` puede activar un respawn de sesion usando un `RespawnPoint2D` con el mismo id o su propio `Transform`; `KillZone2D` puede devolver al Player a ese respawn o al primer `RespawnPoint2D` activo. `MovingPlatform2D` mueve la entidad por su path, emite eventos de plataforma sin modificar la escena serializada y transporta al Player cuando su `Collider` esta apoyado encima del `Collider` de la plataforma antes del movimiento del frame. Este soporte de riders es minimo, centrado en Player; los eventos `moving_platform_rider_attached`, `moving_platform_rider_moved` y `moving_platform_rider_detached` quedan planned. `EnemyPatrol2D` mueve la entidad entre sus puntos de patrulla en runtime de forma ciclica, emite `enemy_patrol_started` y `enemy_patrol_reached_point`, y al contactar con Player emite `enemy_touched` (o el evento configurado) con daño y respawn usando el respawn de sesion o el primer `RespawnPoint2D` activo; si no hay respawn emite `enemy_respawn_missing`. Si `EnemyPatrol2D` y `Hazard2D` coexisten en la misma entidad, `EnemyPatrol2D` absorbe la interaccion para evitar eventos duplicados. No persiste progreso runtime en la escena.
- Escena, tilemap y UI: `Tilemap`, `SceneLink`, `SceneEntryPoint`, `SceneTransition*`, `Canvas`, `UIText`, `UIButton`, `UIImage`.

No se debe asumir soporte publico para componentes no registrados.

## Runtime y sistemas

El runtime usa `Game` o `HeadlessGame` para coordinar sistemas sobre el mundo
activo. Los sistemas actuales incluyen render, fisica, colisiones, animacion,
input, controladores de personaje/jugador, scripts, audio y UI.

`RenderSystem` conserva el flujo visible actual del render 2D: render graph,
sorting layers, batching base, tilemap chunks, debug geometry y render targets
con fallback seguro cuando no hay backend grafico disponible. `engine/rendering/`
añade una foundation modular con planner/executor tipados para adaptar ese
flujo legacy y preparar fases futuras sin sustituir todavia el sistema actual.
`Animator` mantiene compatibilidad con el flujo actual basado en clips por
nombre (`animations`, `default_state`, `current_state`, `play()` y
`AnimationData.on_complete`) y ahora admite foundation opcional de state
machine de una sola capa:

- `parameters`: definiciones serializables de `bool`, `int`, `float` y `trigger`
- `state_machine`: `entry_state` y nodos por estado con `transitions`
- `transitions`: condiciones declarativas, `has_exit_time`, `exit_time` y
  `force_restart`

Los valores runtime de parametros y triggers no forman parte del payload
serializable del authoring.
`engine/audio/` define la foundation interna del runtime de audio. Expone
contratos runtime (`AudioPlaybackRequest`, `AudioVoiceState`,
`AudioRuntimeEvent`), un `NullAudioBackend` headless-safe y `AudioRuntime`
como nucleo independiente de ECS.

`RenderSystem` mantiene render graph, sorting layers, batching, tilemap chunks,
debug geometry y render targets con fallback seguro cuando no hay backend
grafico disponible.

`UIRenderSystem` renderiza la UI overlay serializable. `UISystem` conserva
layout e interaccion y ahora soporta dos modos de foundation sobre
`RectTransform`:

- `free` para el comportamiento legacy basado en anchors/pivot/anchored offsets
- `vertical_stack` y `horizontal_stack` para distribuir hijos con padding,
  spacing, orden, alineacion y fill/stretch por eje

`UIRenderSystem` sigue resolviendo solo la capa visual para `UIText`,
`UIButton` por color o sprite, y `UIImage`, usando los rects ya calculados por
`UISystem`.

El sistema fisico conserva `legacy_aabb` como fallback obligatorio y registra
`box2d` como backend opcional cuando la dependencia esta disponible.

`PhysicsBackend` (ABC en `engine/physics/backend.py`) define el contrato estable
para backends de fisica 2D. Desde el ciclo 1 de refactorizacion, expone dos nuevos
metodos de movimiento cinematico:

- `move_and_slide(entity, velocity, delta_time, ...)` -> `MoveResult2D`: mueve la
  entidad con deteccion de colisiones y deslizamiento por superficies. Soporta
  configuracion de `floor_max_angle`, `floor_snap_distance`, `up_direction`,
  `wall_min_slide_angle` y `max_slides`. Implementado en
  `LegacyAABBPhysicsBackend` con barrido separado por eje (horizontal/vertical),
  snap al suelo y clasificacion de colisiones (suelo/pared/techo).
- `move_and_collide(entity, velocity, delta_time, max_collisions=1)` -> `MoveResult2D`:
  variante que se detiene en la primera colision (delega en `move_and_slide` con
  `max_slides=1`).

`MoveResult2D` es el dataclass canonico de resultado:

```
@dataclass
class MoveResult2D:
    position_x: float = 0.0
    position_y: float = 0.0
    velocity_x: float = 0.0
    velocity_y: float = 0.0
    on_floor: bool = False
    on_wall: bool = False
    on_ceiling: bool = False
    collision_normal_x: float = 0.0
    collision_normal_y: float = 0.0
    contacts: list = field(default_factory=list)  # list[PhysicsContact]
    slide_count: int = 0
    floor_angle: float = 0.0
```

Actualmente estos metodos son contratos del backend (nivel `PhysicsBackend`) y
no estan expuestos directamente en `EngineAPI`. La implementacion en
`LegacyAABBPhysicsBackend` usa barrido AABB con `_sweep_axis()`, snap al suelo
con `_floor_snap()`, filtrado por `CollisionFilter2D` y matriz de capas desde
`feature_metadata.physics_2d.layer_matrix`. La clasificacion de colisiones
(suelo/pared/techo) se realiza por angulo respecto a `up_direction`.

### Integracion runtime del backend en CharacterControllerSystem

`CharacterControllerSystem` admite inyeccion del backend resuelto via
`set_physics_backend(backend)`. Cuando hay backend, `_move_entity()` delega en
`_move_with_backend()` que consulta `controller.move_mode` para elegir el
metodo del backend:

- `move_and_slide`: llama a `PhysicsBackend.move_and_slide()` con parametros
  completos (velocidad, gravedad, `up_direction`, `floor_max_angle`,
  `floor_snap_distance`, `wall_min_slide_angle`).
- `move_and_collide`: llama a `PhysicsBackend.move_and_collide()` con solo
  velocidad y delta, deteniendose en la primera colision.

En ambos modos copia el `MoveResult2D` resultante al Transform y al componente
(velocidad, flags `on_floor`/`on_wall`/`on_ceiling`, normales de colision). Los
contactos del resultado se emiten como eventos `on_collision` en el EventBus,
con la misma deduplicacion por par que el codigo legacy.

`RuntimeController.update_gameplay()` es quien inyecta el backend cada frame:
resuelve `PhysicsBackendRegistry.resolve(world)` y, si hay backend disponible,
lo pasa a `CharacterControllerSystem.set_physics_backend()` antes de llamar a
`update()`. Esto mantiene el `legacy_aabb` como fallback: si el registry
devuelve `None`, el sistema sigue usando sus barridos AABB manuales
(`_sweep_horizontal`/`_sweep_vertical`/`_floor_snap`) sin cambios.

### RayCast2DSystem — Raycast por componente

`RayCast2DSystem` se ejecuta cada frame en `RuntimeController.update_gameplay()`:
para cada entidad con `RayCast2D` y `Transform`, lanza un rayo mediante
`query_physics_ray` desde la posición de la entidad hacia `cast_to` y puebla
los campos de resultado (`is_colliding`, `collision_point_*`,
`collision_normal_*`, `collider_entity`).

**Filtrado de resultados:** El sistema aplica `_filter_hits()` sobre los hits
crudos de `query_physics_ray` antes de poblar el componente:

1. `exclude_parent`: si `true`, descarta hits cuya entidad coincida con la
   entidad origen o su `parent_name`.
2. `collide_with_areas`: si `false`, descarta hits con `is_trigger=True`.
3. `collide_with_bodies`: si `false`, descarta hits con `is_trigger=False`.
4. `collision_mask`: descarta hits cuya entidad golpeada tenga un
   `CollisionFilter2D.layer` que no esté en la máscara. Si la entidad no
   tiene `CollisionFilter2D`, se asume capa `1`.

El primer hit filtrado (más cercano al origen) se usa como resultado final.
Si no hay hits tras filtrar, todos los campos runtime quedan en cero/vacío.

El componente `RayCast2D` se registra en `engine/levels/component_registry.py`
y sus campos serializables son `enabled`, `cast_to_x`, `cast_to_y`,
`collision_mask`, `collide_with_areas`, `collide_with_bodies`,
`exclude_parent`. Los campos runtime de colisión no se serializan.

El wiring ocurre en `Game.set_raycast_2d_system()`, que inyecta
`query_physics_ray` como función de consulta. `RuntimeController` obtiene el
sistema desde el contexto y lo actualiza tras `backend.step()`.

Desde `RuntimeAPI`, el método `get_raycast_result(entity_name)` permite leer
los campos runtime de un `RayCast2D` como dict plano sin acceder al componente
directamente. Retorna `{}` si la entidad no existe, no tiene `RayCast2D` o el
runtime no está activo.

### GPUParticlesSystem — Placeholder no-op

`GPUParticlesSystem` (en `engine/systems/gpu_particles_system.py`) es un
**marcador de posición (placeholder) que no realiza cómputo real de partículas
en GPU**. Expone `update(world, dt)`, `render(world)` y `reset()` como no-ops exclusivamente
para satisfacer el contrato de `RuntimeControllerContext` y `Renderer` sin romper el wiring
existente.

**No es una feature implementada.** Cuando se desarrolle un sistema real de
partículas GPU en el futuro, este placeholder será reemplazado por la
implementación completa.

### ShapeFactory y narrow-phase multi-shape

`engine/physics/shapes.py` introduce `ShapeFactory` y `ShapeInstance` para
unificar la logica de interseccion en narrow-phase. Reemplaza las funciones
dispersas de interseccion (capsule-vs-AABB, capsule-vs-capsule) por un modelo
polimorfico: cada `ShapeInstance` conoce su propia interseccion contra las
demas mediante `intersects_shape(other)`.

**Shapes concretas:**

| Shape | Constructor | Intersecciones implementadas |
|---|---|---|
| `AABBShape(cx, cy, half_w, half_h)` | centro + semi-dimensiones | AABB‑AABB |
| `CircleShape(cx, cy, radius)` | centro + radio | Circle‑Circle, Circle‑AABB, Circle‑Capsule |
| `CapsuleShape(cx, cy, radius, height)` | centro + radio + altura total del segmento | Capsule‑AABB, Capsule‑Circle, Capsule‑Capsule |
| `PolygonShape(vertices)` | vertices en world space (SAT) | Polygon‑AABB (SAT), Polygon‑Circle (delega en Circle), resto por AABB overlap |

**Factory:**

```python
ShapeFactory.build(collider, x, y) -> ShapeInstance
```

Lee `collider.shape_type` y construye la shape correspondiente:

- `"circle"` → `CircleShape` con `collider.radius`
- `"capsule"` → `CapsuleShape` con `collider.radius` y `collider.capsule_height`
- `"polygon"` → `PolygonShape` con `collider.points` transformados a world space
- `"box"` o cualquier otro → `AABBShape` con `collider.width` y `collider.height`

**Integracion en CollisionSystem:**

`CollisionSystem._narrow_phase_check(entry_a, entry_b)` reemplaza a la antigua
`_narrow_phase_capsule()` y sus helpers `_capsule_vs_aabb()` /
`_capsule_vs_capsule()`. Si ambas shapes son `"box"`, la interseccion ya fue
validada por el broad-phase AABB y retorna `True` sin construir shapes. En caso
contrario construye ambas shapes via `ShapeFactory.build()` (o crea una
`AABBShape` desde los bounds si no hay Collider) y llama a
`shape_a.intersects_shape(shape_b)`. El codigo legacy de capsule queda
comentado como referencia.

**Integracion en LegacyAABBPhysicsBackend:**

En `_sweep_axis()`, cuando el collider entrante o el otro collider tienen
`shape_type != "box"`, se construyen ambas shapes en el punto de colision
candidato y se verifica `intersects_shape()` antes de aceptar la colision.
Esto evita falsos positivos del barrido AABB para circulos, capsulas y
poligonos.

**Tests:** 12 tests en `tests/test_shape_factory.py` que cubren intersecciones
AABB‑AABB, Circle‑Circle, Circle‑AABB, Circle‑Capsule, Capsule‑AABB,
Capsule‑Capsule, Polygon‑AABB, la factoria desde Collider, y la integracion en
`_sweep_axis` del backend legacy.

### Limitaciones actuales

- **`legacy_aabb` es el backend default estable.** `box2d` es opt-in via
  `feature_metadata.physics_2d.backend`.
- **Box2D NO soporta `move_and_slide` ni `move_and_collide`.** Su
  `supports_kinematic_move()` retorna `False`. El `PhysicsKinematicMoveService`
  usa el fallback legacy AABB solver automaticamente.
- **`CapsuleShape.collide_shape()` tiene manifold aproximado.** El punto de
  contacto y la normal son estimados; no hay resolucion SAT completa para
  capsulas.
- **`PolygonShape` asume poligonos convexos.** No hay deteccion de concavidad.
  El SAT implementado es correcto para convexos pero no tiene manifold completo
  (depth/normal aproximados desde AABB de los vertices).
- **`query_shape_cast` legacy usa barrido por pasos discretos** (20 steps).
  No es un cast continuo real. Adecuado para depuracion y queries gruesas.
- **`ShapeFactory.collide_shape()` devuelve `ContactManifold2D` con normal y
  depth**, pero no todos los pares de shapes tienen precision fisica completa
  (ver tabla abajo).

| Par de shapes | Manifold | Precision |
|--------------|----------|-----------|
| AABB x AABB | Completo | Normal y depth exactas |
| Circle x Circle | Completo | Normal y depth exactas |
| Circle x AABB | Completo | Normal y depth exactas |
| Capsule x AABB | Aproximado | Punto de contacto estimado |
| Capsule x Circle | Aproximado | Punto de contacto estimado |
| Capsule x Capsule | Aproximado | Solo deteccion booleana |
| Polygon x AABB | Aproximado | SAT implementado, manifold basico |
| Polygon x Polygon | Aproximado | SAT implementado, manifold basico |
| Polygon x Circle | Aproximado | Distancia a aristas, normal estimada |

### Trabajo futuro

- Box2D `move_and_slide` real con shape casts nativos
- Manifold completo para CapsuleShape (capsula vs todos)
- Manifold completo para PolygonShape (SAT con depth y normal real)
- Unificacion de contactos por frame (evitar duplicacion entre CharacterController y CollisionSystem)
- CI matrix con Box2D instalado y sin Box2D
- `query_shape_cast` continuo (no discreto) en backends

`AudioSystem` sigue siendo la superficie ECS/runtime compatible y delega en la
foundation interna de `engine/audio/`. El backend real de audio, buses/mixer,
spatial audio completo y la integracion con el `EventBus` global quedan
preparados pero no implementados como contrato actual.

### Secuencia runtime foundation

`Game` y `HeadlessGame` comparten una secuencia interna explicita por frame:

`HeadlessGame` queda tocado solo como adaptador minimo porque `EngineAPI`
inicializa ese runtime y `step()` publica entra por `step_frame()`. Mantener la
misma secuencia evita que el foundation diverja entre runtime grafico y runtime
publico headless.

1. `FIXED_UPDATE`: simulacion runtime con `fixed_dt = 1/60` y acumulador con
   limite de pasos por frame.
2. `UPDATE`: animacion normal o preview y trabajo variable que no entra todavia
   en fixed-step.
3. `POST_UPDATE`: UI runtime/render-like, bookkeeping y transicion
   `STEPPING -> PAUSED`.
4. `RENDER`: solo en el loop grafico; el foundation no cambia `RenderSystem`.

El lifecycle minimo queda asi:

- `EDIT -> PLAY`: clona `runtime_world`, resetea el estado del loop y dispara
  hooks runtime existentes (`on_play`).
- `PLAY/PAUSED -> STEPPING`: fuerza exactamente un `FIXED_UPDATE`.
- `PLAY/PAUSED/STEPPING -> EDIT`: limpia el estado transitorio del loop,
  ejecuta `on_stop` y restaura `edit_world`.

Esto prepara fases posteriores de render/fisica sin abrir callbacks publicos
nuevos ni alterar `EngineAPI`, CLI o schema serializable.

## Reglas y eventos

`EventBus` y `RuleSystem` permiten gameplay declarativo desde datos de escena.

Acciones de reglas soportadas por contrato:

- `set_animation`
- `set_position`
- `spawn_entity`
- `destroy_entity`
- `emit_event`
- `log_message`

## Workspace y authoring

`SceneManager` coordina carga/guardado, workspace multi-escena, escena activa,
dirty state, historial, transacciones, `EDIT -> PLAY -> STOP`, operaciones
estructurales y prefabs.

Las rutas recomendadas para cambios persistentes son `SceneManager` y
`EngineAPI`. `sync_from_edit_world()` queda como compatibilidad legacy.

## Foundation del editor

La foundation visual del editor vive en `engine/editor/` y se organiza alrededor
de `EditorShell`, `EditorShellState`, `EditorPanelSlots` y
`EditorSelectionState`.

- `EditorShell` compone layout, jerarquia y paneles montables.
- `EditorLayout` sigue siendo la superficie visual compatible, pero ya no crea
  por si mismo todos los paneles del shell.
- `EditorSelectionState` es estado efimero compartido entre shell, jerarquia e
  interaccion; no reemplaza a `SceneManager`, `World` ni a la ruta canonica de
  authoring.
- El runtime sigue orquestado por `Game`; la costura editor/runtime solo monta
  la foundation del editor y no redefine contratos del motor.
### Foundation incremental de tilemap

`Tilemap` conserva su payload serializable actual y su superficie publica para
compatibilidad con escenas, `EngineAPI`, inspector y runtime existente.

La foundation del dominio vive en `engine/tilemap/model.py`. Esa capa mantiene:

- orden estable de capas por lista
- almacenamiento interno por coordenada tipada
- emision canonica de tiles como lista serializable
- metadata existente de mapa, layer y tile-instance sin introducir schema nuevo

`engine/components/tilemap.py` sigue siendo el componente serializable estable;
usa esa foundation para parseo y serializacion canonica, sin convertirse en un
espejo complejo del dominio ni en una integracion fuerte con editor/runtime. En
runtime mantiene tiles por coordenada `tuple[int, int]` y chunks efimeros con
`version`/`dirty`; ese cache alimenta el render sin cambiar el payload de
escena ni serializar estado runtime.

Esta foundation prepara evolucion futura de metadata por tile, layers y reglas
sin mezclar aun editor visual nuevo ni cambios amplios en runtime/render.
Base tecnica interna compartida:

- `engine/scenes/contracts.py` separa `SceneRuntimePort`,
  `SceneAuthoringPort` y `SceneWorkspacePort` como puertos internos sobre
  `SceneManager`.
- `engine/core/runtime_contracts.py` encapsula el wiring requerido por
  `RuntimeController` en `RuntimeControllerContext`.
- `engine/api/_contracts.py` tipa el bundle interno que `EngineAPI` expone a
  sus colaboradores privados.

## EngineAPI publica

`EngineAPI` es la fachada estable para agentes, tests, CLI y automatizacion.
Internamente delega por dominios: authoring, runtime, workspace y scene flow,
assets/proyecto, debug/profiler y UI serializable.

Desde Fase 1, esos colaboradores privados consumen puertos tipados de escena y
runtime en vez de depender de `Game` o `SceneManager` completos cuando no hace
falta. La semantica publica no cambia.

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
- `motor runtime play/step/stop`
- `motor entity create`
- `motor component add`
- `motor prefab create/instantiate/unpack/apply/list`
- `motor animator ...`
- `motor asset ...`

La referencia completa vive en [cli.md](cli.md).

Los comandos `motor runtime play/step/stop` son verificacion headless stateless:
cada invocacion inicializa `EngineAPI`, carga una escena mediante la fachada
publica, ejecuta `play`, `step` o `stop` y termina sin persistir mutaciones
runtime como estado de authoring.

## IA, RL y tooling experimental

`engine/rl`, datasets, runners paralelos y workflows AI-assisted existen, pero
pertenecen a `experimental/tooling`, no al `core obligatorio`.

`engine/recipes/` contiene recetas IA declarativas versionadas para workflows
comunes. `platformer-basic` empaqueta comandos oficiales `motor` allowlist para
crear, validar y comprobar un nivel minimo de plataformas. `platformer-advanced`
crea una vertical slice nativa con componentes runtime semanticos ya soportados
(`MovingPlatform2D`, `EnemyPatrol2D`, `Checkpoint2D`, `KillZone2D` y
`LevelBounds2D`) sin shell, scripts temporales ni runtime externo.

`engine/navigation` mantiene una foundation `grid-first` experimental con
`NavigationGrid`, `NeighborMode`, `PathRequest`, `PathResult` y una API
canonica `NavigationService.request_path(...)`; `query_path(...)` y
`query_world_path(...)` permanecen como wrappers de compatibilidad.

`engine/agent/` implementa una base clean-room para sesiones tipo agente dentro
del motor. Es `experimental/tooling`: no cambia `Scene`, `World`,
`SceneManager` ni el contrato de runtime.

- `AgentSessionService` es la fachada compatible; delega en `AgentRuntime`, que
  ejecuta turnos iterativos `provider -> tool_use -> tool_result -> provider`.
- Las aprobaciones suspenden un turno y `approve_agent_action(...)` lo reanuda
  con un `tool_result` de ejecucion o rechazo.
- Las herramientas pasan por pipeline de validacion, preview, permiso,
  ejecucion y mapeo de resultado.
- `run_command` esta endurecida por `AgentCommandPolicy` y `AgentCommandRunner`:
  no usa shell, ejecuta `argv` con `shell=False`, confina cwd al proyecto, limita
  entorno/output/timeout y conserva la misma policy en `confirm_actions` y
  `full_access`.
- `FakeLLMProvider` y `ReplayLLMProvider` son providers offline de prueba con
  metadata explicita (`provider_kind=test`, `test_only=True`); `OpenAIProvider`
  es el primer adapter online real y exige credenciales por entorno.
- El runtime soporta eventos de streaming (`assistant_delta` y lifecycle de
  provider) y persiste el mensaje final reconstruido.
- `AgentMemoryStore` y `AgentCompactionService` guardan resumen local sanitizado;
  `AgentUsageRecord` conserva usage de provider con coste `unknown` si no hay
  precios configurados.
- Las herramientas de authoring del motor usan un puerto de engine: `EngineAPI`
  en API/CLI y un adaptador vivo del editor para el panel visual.
- La construccion `EngineAPI` ligada a runtime vivo vive en tooling interno del
  editor; no se promociona como constructor core estable.
- Los modos de permiso iniciales son `confirm_actions` y `full_access`.
- El estado versionado y la auditoria local viven bajo `.motor/agent_state`; las
  sesiones legacy se migran con backup, validacion y evento `session_migrated`.
- `AgentPanel` monta una interfaz simple en el panel inferior del editor, junto
  a `Terminal`.

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
