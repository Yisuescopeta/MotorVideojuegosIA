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
- Gameplay/fisica: `Collider`, `CollisionShapeSet2D`, `RigidBody`, `CharacterController2D`, `PlayerController2D`, `Joint2D`, `InputMap`, `AudioSource`, `ScriptBehaviour`, `RayCast2D`, `NavigationObstacle2D`.
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
  entidad con deteccion de colisiones y deslizamiento multi-iteracion por
  superficies. El bucle interno usa **`body_test_motion` unificado 2D por
  iteracion**: prueba el vector de movimiento completo contra el mundo, aplica
  el `travel` seguro, y proyecta el remainder deslizando sobre la normal de
  colision (Godot `Vector2.slide` via `_slide_remainder`). Repite hasta
  consumir todo el movimiento o alcanzar `max_slides` iteraciones. Soporta
  configuracion de `floor_max_angle`, `floor_snap_distance`, `up_direction`,
  `wall_min_slide_angle`, `floor_stop_on_slope` (bool, default False) y
  `max_slides` (default 4). Implementado en `LegacyAABBPhysicsBackend` con
  bucle `body_test_motion` + `_slide_remainder`, snap al suelo via
  `body_test_motion`, y clasificacion de colisiones (suelo/pared/techo).
  `slide_count` refleja el numero real de iteraciones de deslizamiento
  (0 si no hubo colision, 1 en colision simple, >1 en esquinas o paredes
  secuenciales).
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
`LegacyAABBPhysicsBackend` usa un **bucle de deslizamiento basado en
`body_test_motion` unificado 2D** (P0-2), proyectando el remainder via
`_slide_remainder` (Godot `Vector2.slide`). El snap al suelo tambien usa
`body_test_motion` en lugar del antiguo `_floor_snap()`. Incluye deteccion de
one-way collision por normal (`_is_one_way_ignorable`), filtrado por
`CollisionFilter2D` y matriz de capas desde
`feature_metadata.physics_2d.layer_matrix`. La clasificacion de colisiones
(suelo/pared/techo) se realiza por angulo respecto a `up_direction`. La
velocidad de retorno se pone a cero por tipo: `vx=0` si `on_wall`, `vy=0` si
`on_floor` o `on_ceiling`.

### Integracion runtime del backend en CharacterControllerSystem

`CharacterControllerSystem` admite inyeccion del backend resuelto via
`set_physics_backend(backend)`. Cuando hay backend, `_move_entity()` delega en
`_move_with_backend()` que consulta `controller.move_mode` para elegir el
metodo del backend:

- `move_and_slide`: llama a `PhysicsBackend.move_and_slide()` con parametros
  completos (velocidad, gravedad, `up_direction`, `floor_max_angle`,
  `floor_snap_distance`, `wall_min_slide_angle`, `floor_stop_on_slope`).
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

### GPUParticlesSystem — Adaptador CPU-backed

`GPUParticlesSystem` (en `engine/systems/gpu_particles_system.py`) ya no es un
placeholder no-op. Actualmente es un **adaptador que delega toda la lógica en
`ParticleSystem` (CPU)**. Expone `update(world, dt)`, `render(world)`,
`reset()`, `active_particle_count` y `total_particle_count` delegando en la
implementación CPU de `ParticleSystem`.

**Limitaciones (anti-humo):**
- No hay aceleración GPU real. El cómputo es puramente CPU fallback.
- El nombre `GPUParticlesSystem` se conserva por compatibilidad con el wiring
  existente en `RuntimeControllerContext` y `Renderer`.
- GPU real no está soportada todavía. Un sistema de partículas GPU real
  reemplazaría este adaptador en el futuro.
- Clasificación: `experimental/tooling` — no es parte del core obligatorio.

### PhysicsMaterial — Recurso de material físico serializable

`PhysicsMaterial` (en `engine/resources/physics_material.py`) es un recurso
data-class que define propiedades de superficie: `friction` (0–1), `bounce`
(0–1), `rough`, `absorbent`. Se serializa como archivo `.json` independiente
y se carga en runtime mediante `load_physics_material(path)`.

```json
{
  "resource_id": "ice_platform",
  "resource_name": "Ice Platform",
  "friction": 0.1,
  "bounce": 0.0,
  "rough": false,
  "absorbent": false,
  "schema_version": 1
}
```

**API pública del módulo:**
- `load_physics_material(path: str) -> PhysicsMaterial | None`: Carga desde
  archivo JSON relativo o absoluto. Retorna `None` si el archivo no existe,
  el JSON es inválido o el path está vacío. Los resultados se cachean por
  ruta resuelta.
- `clear_physics_material_cache()`: Limpia el caché de materiales (útil en
  tests).
- `PhysicsMaterial.from_dict(data)`: Construye desde dict.
- `PhysicsMaterial.get_effective_bounce()` / `get_effective_friction()`:
  Retorna los valores efectivos de rebote y fricción.

**Integración en PhysicsSystem:**
`PhysicsSystem` lee `physics_material_override_path` de `RigidBody` y
`StaticBody2D` durante la resolución de colisiones. Si el path es válido y el
material se carga correctamente, el `bounce` y `friction` del material
reemplazan los valores del `Collider`. El rebote final usa `max()` entre ambos
cuerpos; la fricción usa promedio. Si el material no se puede cargar, se usa el
fallback del `Collider` (`restitution` / `friction`).

Campos serializables del recurso:
- `resource_id`: str, identificador único del material.
- `resource_name`: str, nombre legible (default: `"default"`).
- `friction`: float (0–1), coeficiente de fricción (0 = deslizamiento sin pérdida).
- `bounce`: float (0–1), coeficiente de restitución / rebote.
- `rough`: bool, si la superficie es rugosa (fricción efectiva infinita).
- `absorbent`: bool, si la superficie absorbe impacto (bounce efectivo 0).
- `schema_version`: int, versión del formato de serialización (1 = actual).
  Desde `from_dict()`, legacy payloads sin este campo se cargan con default 1.

### TileSet — Recurso de atlas, terrenos y autotile conectivo

`TileSet` (en `engine/resources/tileset.py`) es un recurso serializable que define
un atlas de tiles con metadata por tile, conjuntos de terreno y peering bits para
autotile conectivo (adaptado de Godot TileSet). Se serializa como archivo `.json`
independiente.

```json
{
  "resource_id": "grass_tileset",
  "resource_name": "Grass Tileset",
  "schema_version": 1,
  "atlas": { "texture_path": "assets/tiles/grass.png", "tile_width": 32, "tile_height": 32, "columns": 8 },
  "tile_metadata": {},
  "terrain_sets": [{"name": "grass", "color": "#00ff00", "mode": 0}],
  "terrain_peering": {"grass": {"tile_0": 0, "tile_1": 255}}
}
```

**API pública del módulo:**
- `load_tileset(path: str) -> TileSet | None`: Carga desde archivo JSON. Retorna
  `None` si el archivo no existe, el JSON es inválido o el path está vacío.
  Resultados cacheados por ruta resuelta.
- `clear_tileset_cache()`: Limpia el caché global (útil en tests).
- `TileSet.from_dict(data)`: Construye desde dict.
- `TileSet.to_dict()`: Serializa a dict.

**Estructura:**
- `TileAtlasSource`: Define la textura del atlas, dimensiones de tile, columnas,
  márgenes y espaciado. Método `get_tile_region(tile_index)` → `(sx, sy, sw, sh)`.
- `TileMetadata`: Metadata por tile con `tile_id`, `physics_layers` (shapes box/circle),
  `custom_data` y `terrain_id` (índice en `terrain_sets`).
- `TerrainSet`: Conjunto de terreno con `name`, `color` y `mode` (0=corners_and_sides,
  1=corners, 2=sides).
- `terrain_peering`: Mapa `terrain_name → {tile_id → peering_bits}` donde
  peering_bits es entero de 8 bits (bit 0=N, 1=NE, 2=E, 3=SE, 4=S, 5=SW, 6=W, 7=NW).

**Autotile conectivo:**
- `compute_terrain_mask(layer_tiles, x, y, terrain_name) → int`: Computa máscara
  de 8 bits para celda `(x, y)` según vecinos que comparten el terreno.
- `get_autotile_tile(terrain_name, neighbor_mask) → str | None`: Busca tile con
  peering bits exacto para `terrain_name`. Si no hay match exacto, busca el tile
  con más bits coincidentes como fallback ponderado.
- `set_cells_terrain_connect(cells, terrain_name, get_tile_at, set_tile_at) → int`:
  Para cada celda en `cells` (lista de dicts `{x, y}`), computa máscara, busca
  tile de autotile y lo coloca vía `set_tile_at`. Retorna número de celdas modificadas.

**Integración en Tilemap:**
`Tilemap` componente expone `tileset_resource_path` (str, campo serializable) y
`get_tileset_resource() → TileSet | None` que carga lazy con caché interno por
instancia. Desde `EngineAPI`, `set_cells_terrain_connect()` permite aplicar
autotile conectivo sobre una capa tilemap.

**Tests:** `tests/test_tileset.py` (355+ líneas) cubre roundtrip, atlas regions,
terrain peering, autotile exacto y fallback, compute_terrain_mask, loader con
cache, estados vacíos y modos de TerrainSet.

### RigidBody contact_monitor — Monitoreo de contactos runtime

`RigidBody` ahora incluye monitoreo de contactos estilo Godot, activado
mediante dos nuevos campos serializables:

| Campo | Tipo | Default | Descripción |
|-------|------|---------|-------------|
| `contact_monitor` | bool | `false` | Activa el tracking de contactos este frame |
| `max_contacts_reported` | int | `0` | Máx. contactos a reportar. `0` = deshabilitado |

**Métodos públicos runtime (no serializables):**
- `get_colliding_bodies() -> list[int]`: IDs de entidades en contacto este frame.
- `get_contact_count() -> int`: Número de contactos activos.

**Comportamiento:**
- `contact_monitor=false` o `max_contacts_reported=0`: sin tracking.
- `contact_monitor=true` y `max_contacts_reported>0`: registra hasta N
  colisiones reales (no triggers) por frame.
- `CollisionSystem` limpia los contactos al inicio de cada paso y registra
  nuevas colisiones durante la resolución.
- Los contactos solo se registran para colisiones no-trigger (consistente con
  Godot `body_entered`). Triggers no producen contactos en este sistema.
- `get_colliding_bodies()` retorna IDs de entidad (enteros), no nombres.
- Los contactos son estado runtime volátil: se borran cada frame y no se
  serializan.

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

**Factory from params:**

```python
ShapeFactory.build_from_params(shape_type, cx, cy, **params) -> ShapeInstance
```

Construye una shape desde parametros explicitos sin requerir un `Collider`. Soporta:

- `box`: `width`, `height`
- `circle`: `radius`
- `capsule`: `radius`, `height`
- `polygon`: `vertices` (lista de `(x, y)` locales)

Usado internamente por `swept_collision` para construir la shape de barrido en cada punto de la busqueda binaria.

**Factory from CollisionShape2DDef:**

```python
ShapeFactory.build_from_def(def_: CollisionShape2DDef, cx: float, cy: float) -> ShapeInstance
```

Construye una `ShapeInstance` desde un `CollisionShape2DDef`, aplicando `offset_x`
y `offset_y` al centro `(cx, cy)`. Soporta los mismos tipos que `build()`:
`"box"`, `"circle"`, `"capsule"`, `"polygon"`. Usado internamente por
`CollisionSystem` y `PhysicsSystem` para construir shapes desde las definiciones
de `CollisionShapeSet2D`.

**Integracion en CollisionSystem:**

`CollisionSystem` soporta dos modos de entrada de shapes: legacy (`Collider`,
`CollisionShape2D`, `CollisionPolygon2D`) y el nuevo `CollisionShapeSet2D`.
Cuando una entidad tiene `CollisionShapeSet2D`, se usa su lista de
`CollisionShape2DDef` tanto para bounds compuestos (broad-phase) como para
intersección por pares (narrow-phase).

El broad-phase construye el AABB compuesto desde
`CollisionShapeSet2D.get_composite_bounds()` que encierra todas las shapes
habilitadas no-trigger.

La narrow-phase itera sobre todos los pares de shapes entre dos entidades,
construyendo cada `ShapeInstance` via `ShapeFactory.build_from_def()` y
verificando `intersects_shape()`. Se usa el manifold de mayor profundidad
como resultado de contacto. Si ambas shapes son `"box"`, la intersección ya fue
validada por el broad-phase y retorna `True` sin construir shapes.

Cuando una entidad usa `Collider` legacy (sin `CollisionShapeSet2D`), el sistema
convierte el `Collider` a un `CollisionShape2DDef` sintético mediante
`_collider_to_shape_def()` para unificar el flujo de narrow-phase.

La detección de trigger (`_any_shape_is_trigger()`) verifica si alguna shape
de cualquiera de las dos entidades tiene `is_trigger=True`, reemplazando la
antigua verificación por collider único.

`CollisionSystem.resolve_contacts()` también itera por pares de shapes,
seleccionando el manifold con mayor profundidad entre todas las combinaciones
de shapes de ambas entidades.

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

**Integracion en PhysicsSystem con CollisionShapeSet2D:**

`PhysicsSystem` soporta `CollisionShapeSet2D` en todas las rutas de colisión:

- `_get_entity_shape_aabbs()` retorna una lista de pares `(AABB, CollisionShape2DDef | None)` para cada shape habilitada no-trigger de la entidad. Si la entidad usa `CollisionShapeSet2D`, itera sobre sus shapes; si no, retorna el AABB del `Collider` legacy.
- `_get_solid_composite_aabb()` retorna el AABB compuesto para inserción en el spatial hash. Usa `get_composite_bounds()` si hay `CollisionShapeSet2D`.
- `_resolve_horizontal()` y `_resolve_vertical()` iteran sobre los AABBs de todas las shapes de la entidad contraria, resolviendo colisión y aplicando materiales por shape (`restitution`/`friction` desde `CollisionShape2DDef` cuando está disponible).
- `_sweep_horizontal()`, `_sweep_vertical()` y `_has_proximity()` iteran sobre shapes para detección de barrido y proximidad respectivamente.

La resolución de materiales prioriza `physics_material_override_path` del
`RigidBody` antes que `CollisionShape2DDef.friction`/`restitution`, y estos a
su vez antes que los valores del `Collider` legacy.

**Tests:** 12 tests en `tests/test_shape_factory.py` que cubren intersecciones
AABB‑AABB, Circle‑Circle, Circle‑AABB, Circle‑Capsule, Capsule‑AABB,
Capsule‑Capsule, Polygon‑AABB, la factoria desde Collider, y la integracion en
`_sweep_axis` del backend legacy.

Tests adicionales en `tests/test_collision_shape_set_2d.py` cubren
`CollisionShape2DDef` (bounds con/sin offset, circle, capsule, to_dict roundtrip,
flags) y `CollisionShapeSet2D` (shape por defecto, composite bounds, exclusión de
disabled/trigger, to_dict roundtrip, empty shapes default).

### Swept collision (barrido continuo)

`engine/physics/swept_collision.py` implementa el algoritmo de **swept collision
con busqueda binaria TOI** (Time of Impact). Reemplaza el antiguo barrido
discreto de 20 pasos por un metodo continuo que encuentra con precision el
primer impacto entre una shape en movimiento y una shape objetivo.

**Entrada:** `swept_shape_toi(shape_type, shape_params, origin, direction,
max_distance, target_shape, target_info, epsilon=0.001, max_iter=64)`

**Algoritmo:**
1. Normaliza la direccion de barrido.
2. Verifica overlap en origen — si hay solapamiento inicial, retorna `fraction=0.0`.
3. Verifica overlap en el extremo del cast — si no hay, intenta deteccion con
   `_scan_and_refine()` (linear scan de 20 pasos + busqueda binaria entre el
   ultimo punto claro y el primer hit).
4. Si hay overlap en el extremo, ejecuta busqueda binaria entre `[0, max_distance]`
   para encontrar el TOI exacto (epsilon configurable, 64 iteraciones max).
5. La normal se computa desde `ShapeInstance.collide_shape()` en el punto del TOI
   y se orienta contra la direccion de barrido.

**Broad-phase AABB:** Antes de la busqueda binaria por entidad,
`LegacyAABBPhysicsBackend.query_shape_cast()` construye el AABB union del
barrido (origen + extremo) y filtra entidades candidatas, reduciendo el numero
de shapes objetivo para la fase estrecha.

**Uso en `LegacyAABBPhysicsBackend`:**
- `query_shape_cast()` delega el TOI por entidad en `_swept_toi()`, que llama a
  `swept_shape_toi()`.
- Las shapes de barrido se construyen via `ShapeFactory.build_from_params()`
  con los `shape_params` recibidos (o derivados de `shape_size` legacy).

**Tests:** 12 tests en `tests/test_swept_collision.py` que cubren caja vs caja
(precision TOI, overlap en origen, sin colision, epsilon convergence, grazing
edge, datos de entidad, direccion cero) y barrido con shape circle/capsule.

### Pipeline de fisica

El pipeline completo de fisica por frame se ejecuta en este orden dentro de
`PhysicsSystem.update()`:

```text
1. Force integration (gravedad, fuerzas aplicadas, fuerzas constantes de StaticBody2D)
2. Construir constraints de contacto (pares overlap de broadphase)
3. Construir constraints bilaterales de joints (fixed, distance, pin)
4. Construir islas fisicas (BFS sobre contactos + joint pairs)
5. Por cada isla:
   a. PGS velocity solve (8 iteraciones) — normal + friccion Coulomb
   b. PGS position solve (3 iteraciones) — correccion mass-weighted sobre transforms
6. Per-body CCD (swept collision continua con busqueda binaria TOI)
7. Push-out safety net (factor 0.05, overlap minimo 0.005)
8. Joint legacy pass (groove, damped_spring, angular limits/motor)
```

### PGS Impulse Solver

El motor incluye un solver de impulsos por Proyeccion Gauss-Seidel (PGS) para
resolucion de contactos y joints bilaterales entre cuerpos rigidos 2D.

**Archivos:**
- `engine/physics/contact_solver.py` — `ContactConstraint2D` y `ImpulseSolver2D`
- `engine/physics/island_manager.py` — `Island2D` y `IslandBuilder2D`
- `engine/systems/physics_system.py` — integracion con `PhysicsSystem.update()`

#### Parametros de contacto

| Parametro | Default | Descripcion |
|-----------|---------|-------------|
| `solver_iterations` | 8 | Iteraciones PGS de velocidad por frame |
| `BAUMGARTE_FACTOR` | 0.2 | Factor de estabilizacion Baumgarte (velocity solve) |
| `SLOP` | 0.01 | Tolerancia de penetracion (velocity solve) |
| `MAX_BIAS` | 10.0 | Velocidad maxima de correccion posicional |

#### Parametros de correccion posicional (solve_positions)

| Parametro | Default | Descripcion |
|-----------|---------|-------------|
| `POSITION_ITERATIONS` | 3 | Iteraciones PGS posicionales por frame |
| `POSITION_CORRECTION_FACTOR` | 0.2 | Fraccion de correccion por iteracion |
| `POSITION_SLOP` | 0.005 | Penetracion permitida antes de corregir |
| `position_correction_ratio` | 0.05 | Safety net push-out (push-out post-PGS) |
| `PUSH_OUT_MIN_OVERLAP` | 0.005 | Overlap minimo para push-out |

**Pipeline de resolucion por isla:**
1. **Velocity solve** (`ImpulseSolver2D.solve()`): aplica impulsos normales y de
   friccion (Coulomb) sobre las velocidades de los cuerpos. Los contactos usan
   clamp no-negativo (non-penetration); los joints bilaterales (`is_bilateral=True`)
   permiten impulso negativo (atraccion).
2. **Position solve** (`ImpulseSolver2D.solve_positions()`): corrige posiciones
   directamente sobre los `Transform` con distribucion mass-weighted. Para contactos
   usa correccion proporcional a `(depth - slop) * factor`; para joints bilaterales
   usa direccion desde `bias` escalada por `stiffness * dt * factor`.

**Metricas expuestas via `get_solver_metrics()`:**
- `warm_start_cache_size`: pares de contacto activos en cache
- `iterations`: iteraciones de velocidad configuradas
- `island_count`: total de islas este frame
- `sleeping_islands`: islas dormidas este frame

**Caracteristicas del solver:**
- Impulso normal con clamp no-negativo para contactos (`is_bilateral=False`)
- Impulso normal sin clamp para joints bilaterales (`is_bilateral=True`)
- Friccion Coulomb (tangente clamp a friction * normal_impulse, desactivada para bilaterales)
- Warm starting entre frames via cache por par de entidades con **contact age tracking**:
  el cache ahora almacena `(normal_impulse, tangent_impulse, contact_age)`. La edad
  de contacto se incrementa cada frame que el par persiste y se usa en
  `solve_positions()` para reducir la correccion posicional en contactos estables
  via `age_factor = 1.0 / (1.0 + age * 0.1)`, eliminando jitter.
- Baumgarte stabilization para correccion posicional suave en velocity solve
- Soporte para cuerpos dinamicos, kinematic y estaticos
- `validate_contacts()` eliminado (codigo muerto; la cache de warm-start ya filtra
  contactos por clave de posicion via `CONTACT_RECYCLE_RADIUS`)

#### Islas fisicas (Constraint Islands)

- `IslandBuilder2D` agrupa cuerpos rigidos en islas independientes usando BFS
  sobre conectividad de contactos y joints (pares de cuerpos unidos por joint,
  incluyendo joints registrados via `_collect_joint_pairs()`).
- Cada isla agrupa cuerpos que interactuan via restricciones directas o
  indirectas; cuerpos en islas distintas no interactuan y se resuelven por
  separado en su propio pase PGS.
- `Island2D` almacena `body_ids`, `constraints`, flag `sleeping` y `sleep_timer`.
  Expone propiedades `size` (numero de cuerpos) y `constraint_count`.
- **Island-level sleeping**: si todos los cuerpos de una isla estaban en la
  misma isla dormida el frame anterior y sus velocidades estan por debajo de
  los umbrales (`sleep_linear_threshold`, `sleep_angular_threshold`), la isla
  completa se marca como dormida, se salta la resolucion PGS completa (velocity
  solve + position solve) y las velocidades se ponen a cero. El temporizador
  `sleep_timer` se acumula hasta superar `time_to_sleep` (default 0.5s) antes
  de dormir. Cualquier movimiento reactiva la isla.
- **Metricas** via `get_step_metrics()`: `ccd_bodies`, `swept_checks`,
  `candidate_solids`, `island_count` (total de islas) y `sleeping_islands`
  (islas dormidas este frame).
- `_body_id_to_island` persiste el mapeo entre frames para transferir estado
  de sueño entre islas que mantienen la misma composicion.

#### Joints como constraints PGS bilaterales

Los tipos de joint `fixed`, `distance` y `pin` se construyen como constraints
PGS bilaterales con `is_bilateral=True` en `_build_joint_constraints()`. Esto
permite que el PGS resuelva la velocidad de los joints integrada con los
contactos dentro de la misma isla:

- **Fixed joint**: 2 constraints (x, y) que bloquean posicion relativa.
  La rotacion relativa se bloquea en el legacy pass posterior.
- **Distance joint**: 1 constraint en la direccion del vector A→B, con `error
  = dist - rest_length`. Bias usa `joint_stiffness`.
- **Pin joint**: 2 constraints (x, y) que anclan ambos cuerpos al mismo punto.
  `softness > 0` suaviza la correccion via factor `1.0 / (1.0 + softness * 10.0)`.

Los joints legacy (`groove`, `damped_spring`) y la correccion angular de
`fixed`, los angular limits/motor de `pin` se resuelven en el **legacy pass**
(`_resolve_joints()`) despues del PGS posicional, CCD y push-out.

**Joint stiffness:** `Joint2D.joint_stiffness` (default 0.2, rango 0–1) controla
el factor de bias en las constraints PGS bilaterales. Se serializa y expone via
`from_dict`/`to_dict`. A mayor valor, correccion mas agresiva del error de
posicion.

La busqueda de entidades con joints paso de `world.iter_entities()` a
`world.get_entities_with(Joint2D)` en `_collect_joint_pairs()` y
`_resolve_joints()`, reduciendo el escaneo a solo entidades con Joint2D.

### Broadphase unificado

El motor mantiene un unico `SpatialHash2D` (celda 128px) compartido entre
`PhysicsSystem`, `CollisionSystem` y las queries de `LegacyAABBPhysicsBackend`:

1. `LegacyAABBPhysicsBackend.step()` construye el grid de todos los colliders
   del mundo al inicio del frame (shared_grid).
2. Pasa `shared_grid=grid` a `PhysicsSystem.update()`: PhysicsSystem lo usa
   como broadphase en lugar de construir su propio `SpatialHash2D`.
3. Despues de la simulacion, repuebla el grid con posiciones post-fisica y lo
   pasa a `CollisionSystem.update(shared_grid=grid)`, que lo reusa en lugar de
   construir su propio grid.
4. `query_physics_ray()`, `query_physics_aabb()` y `query_shape_cast()` usan
   el grid compartido (`self._shared_grid`) para obtener candidatos iniciales
   en vez de iterar todas las entidades del mundo.

Benefits: ~1 SpatialHash2D construido por frame (vs ~3 antes de la
unificacion). El grid se almacena como `PhysicsSystem.spatial_grid` (propiedad
de solo lectura) y en `LegacyAABBPhysicsBackend._shared_grid`.

**Nuevo metodo en SpatialHash2D:**
- `query_ray_candidates(ox, oy, dx, dy, max_distance)`: retorna IDs de entidad
  en celdas intersecadas por el barrido AABB del segmento de rayo (DDA
  conservativo via swept AABB). Usado por `query_physics_ray` para reducir
  candidatos.

### Box2D: CollisionFilter2D soportado

El backend Box2D (opt-in, requiere Box2D 2.3.10) ahora soporta
`CollisionFilter2D`: cuando una entidad tiene este componente, sus valores
`layer` y `mask` (uint32) se mapean a `b2Filter.categoryBits` y
`b2Filter.maskBits` en cada fixture del body Box2D. La entrada
`"CollisionFilter2D"` fue eliminada de la lista de componentes no-soportados
del backend.

### Limitaciones actuales

- **`legacy_aabb` es el backend default estable.** `box2d` es opt-in via
  `feature_metadata.physics_2d.backend`.
- **Box2D NO soporta `move_and_slide` ni `move_and_collide`.** Su
  `supports_kinematic_move()` retorna `False`. El `PhysicsKinematicMoveService`
  usa el fallback legacy AABB solver automaticamente.
- **`CapsuleShape.collide_shape()` produce manifold completo.** Depth, normal y
  punto de contacto reales para colisiones con AABB, Circle, Capsule y Polygon.
- **`PolygonShape` asume poligonos convexos.** No hay deteccion de concavidad.
  El SAT con clipping de aristas produce manifold completo (depth, normal y
  puntos de contacto reales) para pares Polygon-Polygon y Polygon-AABB.
- **`query_shape_cast` usa swept collision real con busqueda binaria TOI.**
  La implementacion en `LegacyAABBPhysicsBackend` ya no usa 20 pasos discretos.
  Emplea `swept_collision.swept_shape_toi()` con broad-phase AABB, linear scan
  de 20 pasos para deteccion inicial y busqueda binaria (64 iteraciones max,
  epsilon 0.001) para precision TOI. La normal se obtiene del manifold de
  `collide_shape()`. No obstante, la precision del manifold depende del par de
  shapes (ver tabla).
- **`ShapeFactory.collide_shape()` devuelve `ContactManifold2D` con normal y
  depth reales** para la mayoria de los pares de shapes (ver tabla abajo).

| Par de shapes | Manifold | Precision |
|--------------|----------|-----------|
| AABB x AABB | Completo | Normal y depth exactas |
| Circle x Circle | Completo | Normal y depth exactas |
| Circle x AABB | Completo | Normal y depth exactas |
| Capsule x AABB | Completo | Normal, depth y punto de contacto reales |
| Capsule x Circle | Completo | Normal, depth y punto de contacto reales |
| Capsule x Capsule | Completo | Segment overlap + capsulas extremas |
| Polygon x AABB | Completo | SAT con clipping, depth y normal reales |
| Polygon x Polygon | Completo | SAT con clipping, depth y normal reales |
| Polygon x Circle | Aproximado | Distancia a aristas, normal estimada |

### Trabajo futuro

- Box2D `move_and_slide` real con shape casts nativos
- Unificacion de contactos por frame (evitar duplicacion entre CharacterController y CollisionSystem)
- CI matrix con Box2D instalado y sin Box2D
- `query_shape_cast` continuo nativo en backend Box2D

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
espejo complejo del dominio ni en una integracion fuerte con editor/runtime.
Serializa el nuevo campo `tileset_resource_path` (ruta a archivo `.json` de
TileSet) y expone `get_tileset_resource()` para carga lazy con cache interno.
En runtime mantiene tiles por coordenada `tuple[int, int]` y chunks efimeros con
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

**Métodos públicos de tilemap en EngineAPI (autoría):**
- `set_tilemap_tile(entity, layer, x, y, tile_id, ...)`: Coloca un tile individual.
- `bulk_set_tilemap_tiles(entity, layer, tiles)`: Coloca múltiples tiles.
- `set_cells_terrain_connect(entity, layer, cells, terrain_name)`: Aplica autotile
  conectivo sobre celdas específicas usando el TileSet cargado. Cada celda es
  `{"x": int, "y": int}`. El `terrain_name` debe coincidir con un `TerrainSet`
  definido en el TileSet. Internamente computa máscara de vecinos (8 bits),
  busca tile de autotile vía peering, y lo coloca en la capa. Retorna
  `ActionResult` con `count` de celdas modificadas.
- `resize_tilemap(entity, cell_width, cell_height, *, offset_x, offset_y)`: Cambia
  dimensiones de la rejilla del tilemap.

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
