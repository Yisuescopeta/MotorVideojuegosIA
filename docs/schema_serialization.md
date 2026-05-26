# Contrato de serializacion del core

`engine/serialization/schema.py` es la fuente de verdad tecnica para schemas,
migracion y validacion.

## Version actual

- `scene schema_version = 2`
- `prefab schema_version = 2`
- `export_presets.motor.json schema_version = 1`
- `game.manifest.json schema_version = 1`

Toda carga migra primero a la version actual y valida despues. Todo guardado de
escena o prefab emite payload canonico `v2`.

## Presets y manifest de exportacion

`export_presets.motor.json` vive en la raiz del proyecto. Contiene
`schema_version` y una lista `presets`. Cada preset define `name`, `platform`,
`architecture`, `mode`, `output_path`, `entry_scene`, `display_name`,
`application_id`, version, `bundle_mode`, `include_debug_tools` y opciones de
ventana o movil. Campos desconocidos fallan salvo extras documentados de Android
release (`keystore_path`, `keystore_password`, `key_alias`, `key_password`) y
`include_all_assets`. En Windows, `console: true` es un extra documentado para
forzar consola incluso en release; release normal usa `console=False`.

`game.manifest.json` se genera desde el grafo de contenido. Incluye entry scene,
version de motor, proyecto, escenas, assets y scripts alcanzables, con `sha256`,
`size_bytes`, `guid` estable derivado de path y dependencias. `game.pak` es ZIP
determinista con timestamps fijos y orden estable.

Documentacion relacionada: [export_presets.md](export_presets.md),
[build_artifacts.md](build_artifacts.md), [export_pipeline.md](export_pipeline.md).

## Formatos fisicos de escena

El formato oficial y default sigue siendo un unico archivo `.json` con el
payload canonico de escena.

Existe un backend experimental opt-in interno, `ChunkedSceneStorage`, para
carpetas `.scene/`. En esta fase solo guarda y carga entidades en chunks simples
desde `scene.json` y `entities/chunk_*.json`, y ensambla de vuelta el mismo
payload canonico que consume `Scene`. No esta activado por defecto ni expuesto
como contrato publico de CLI o `EngineAPI`.

Limitaciones actuales de `.scene/`: no hay streaming parcial, dirty chunks,
tilemaps chunked, migracion automatica desde `.json` ni promocion a formato
oficial.

## Politica de compatibilidad

Se aceptan en carga:

- escenas legacy sin `schema_version`
- escenas `schema_version = 1`
- escenas `schema_version = 2`
- prefabs legacy sin `schema_version`
- prefabs `schema_version = 1`
- prefabs `schema_version = 2`

No se aceptan:

- versiones futuras o desconocidas sin migrador explicito
- payloads invalidos despues de migrar
- JSON ajeno al contrato de escena/prefab usado como input de tooling

## Payload minimo de escena

Una escena canonica incluye:

- `name`
- `schema_version`
- `entities`
- `rules`
- `feature_metadata`

Cada entidad define identidad, estado, jerarquia y componentes serializables.
La identidad canonica incluye `id` estable como string no vacio y `name` como
nombre humano compatible. `name` sigue siendo requerido y unico para APIs
existentes; `id` tambien es unico dentro de la escena y se conserva al renombrar.
Opcionalmente puede incluir `groups` como lista de strings no vacios y sin
duplicados para persistir membresias declarativas por entidad.
Los componentes publicos deben estar registrados en
`engine/levels/component_registry.py`.

`rules` contiene reglas declarativas validadas por schema. Las acciones actuales
incluyen `set_animation`, `set_position`, `spawn_entity`, `destroy_entity`,
`emit_event` y `log_message`; `spawn_entity` crea entidades runtime y no cambia
la escena persistente.

En UI serializable, el contrato vigente incluye `Canvas`, `RectTransform`,
`UIText`, `UIButton` y `UIImage`. `UIButton` admite visuales opcionales por
sprite (`*_sprite`, `*_slice`, `image_tint`, `preserve_aspect`) sin romper el
payload legacy basado en colores. `UIImage` serializa `sprite`, `slice_name`,
`tint` y `preserve_aspect`.

Los componentes semanticos minimos de gameplay 2D se serializan como datos.
En runtime, `Gameplay2DSemanticSystem` consume contactos fisicos para emitir
eventos de gameplay (coleccionable, hazard, goal, checkpoint, killzone,
enemy patrol), manejar respawn de sesion, mover plataformas y evaluar bounds
sin modificar la escena serializada (ver [TECHNICAL.md](TECHNICAL.md)).

- `Collectible2D`: `points`, `destroy_on_collect`, `event_name`
- `Hazard2D`: `damage`, `respawn_on_touch`, `event_name`
- `Goal2D`: `complete_on_touch`, `next_scene`, `event_name`
- `RespawnPoint2D`: `spawn_id`, `active`
- `MovingPlatform2D`: `path` como lista de puntos `{x, y}`, `speed`, `loop`,
  `start_active`
- `EnemyPatrol2D`: `waypoints`, `speed`, `damage`, `event_name`, `loop`
- `Checkpoint2D`: `checkpoint_id`, `active`, `set_respawn_on_touch`,
  `event_name`
- `KillZone2D`: `damage`, `respawn_on_touch`, `event_name`
- `LevelBounds2D`: `left`, `right`, `top`, `bottom`
- `NavigationObstacle2D`: `radius`, `affect_avoidance`. Datos para avoidance
  local en `NavigationAgentSystem`. Componente data-only sin runtime behavior
  propio.

`RayCast2D` serializa `enabled`, `cast_to_x`, `cast_to_y`, `collision_mask`,
`collide_with_areas`, `collide_with_bodies`, `exclude_parent`. Los campos
runtime de colisión (`is_colliding`, `collision_point_*`, `collision_normal_*`,
`collider_entity`) no se serializan.

`RigidBody` serializa los nuevos campos de monitoreo de contactos (Godot-like):

- `contact_monitor`: bool (default: `false`). Activa tracking runtime de
  contactos por frame.
- `max_contacts_reported`: int (default: `0`). Máximo de contactos a reportar.
  `0` = deshabilitado (no reporta ninguno).
- `physics_material_override_path`: str (default: `""`). Ruta a un archivo
  `.json` de `PhysicsMaterial` que sobreescribe fricción/rebote del `Collider`.

Estos campos son serializables y roundtripean correctamente. Los contactos
runtime (`_contact_bodies`) y los métodos `get_colliding_bodies()` /
`get_contact_count()` no se serializan.

### TileSet — Recurso serializable independiente

`TileSet` se serializa como archivo `.json` independiente, no como parte del payload
de escena. Define un atlas de tiles con metadata, conjuntos de terreno y peering bits
para autotile conectivo. El contrato serializable incluye:

| Campo | Tipo | Default | Descripción |
|-------|------|---------|-------------|
| `resource_id` | str | `""` | Identificador único del tileset |
| `resource_name` | str | `"default"` | Nombre legible |
| `schema_version` | int | `1` | Versión del formato de serialización |
| `atlas` | dict | `{}` | Fuente de atlas: `texture_path`, `tile_width`, `tile_height`, `columns`, `margin`, `spacing` |
| `tile_metadata` | dict | `{}` | Mapa `tile_id → {tile_id, physics_layers, custom_data, terrain_id}` |
| `terrain_sets` | list | `[]` | Lista de conjuntos de terreno: `{name, color, mode}` donde `mode` ∈ {0=corners_and_sides, 1=corners, 2=sides} |
| `terrain_peering` | dict | `{}` | Mapa `terrain_name → {tile_id → peering_bits}`. peering_bits es entero de 8 bits (bit 0=N, 1=NE, 2=E, 3=SE, 4=S, 5=SW, 6=W, 7=NW) |

Cada `TileAtlasSource` (`atlas`) serializa:

| Campo | Tipo | Default | Descripción |
|-------|------|---------|-------------|
| `texture_path` | str | `""` | Ruta a la textura del atlas |
| `tile_width` | int | `16` | Ancho de cada tile en píxeles |
| `tile_height` | int | `16` | Alto de cada tile en píxeles |
| `columns` | int | `0` | Número de columnas en el atlas (0 = una sola celda) |
| `margin` | int | `0` | Margen exterior en píxeles |
| `spacing` | int | `0` | Espacio entre tiles en píxeles |

Cada `TileMetadata` serializa:

| Campo | Tipo | Default | Descripción |
|-------|------|---------|-------------|
| `tile_id` | str | `""` | Identificador del tile |
| `physics_layers` | list | `[]` | Lista de `{shape_type, points}` (box o circle con puntos locales) |
| `custom_data` | dict | `{}` | Datos arbitrarios por tile |
| `terrain_id` | int | `-1` | Índice del terreno en `terrain_sets` (-1 = sin terreno) |

Ejemplo de archivo `tilesets/grass.json`:
```json
{
  "resource_id": "grass_tileset",
  "resource_name": "Grass Tileset",
  "schema_version": 1,
  "atlas": {
    "texture_path": "assets/tiles/grass.png",
    "tile_width": 32,
    "tile_height": 32,
    "columns": 8,
    "margin": 1,
    "spacing": 2
  },
  "tile_metadata": {
    "grass_0_0": {
      "tile_id": "grass_0_0",
      "physics_layers": [{"shape_type": "box", "points": [[0.0, 0.0], [32.0, 32.0]]}],
      "custom_data": {"weight": 1},
      "terrain_id": 0
    }
  },
  "terrain_sets": [
    {"name": "grass", "color": "#00ff00", "mode": 0},
    {"name": "dirt", "color": "#8b4513", "mode": 0}
  ],
  "terrain_peering": {
    "grass": {
      "grass_0_0": 0,
      "grass_1_0": 15,
      "grass_2_0": 240,
      "grass_3_0": 255
    }
  }
}
```

**Compatibilidad legacy:**
- Payloads sin `schema_version` se cargan con default `1`.
- Payloads sin `resource_id` o `resource_name` se cargan con defaults vacíos.
- `terrain_sets` vacío o ausente no produce terrenos.
- `terrain_peering` vacío o ausente desactiva autotile conectivo.
- `tile_metadata` vacío o ausente no asigna metadata a tiles.

**Uso desde escena:**
`Tilemap` referencia un TileSet mediante el campo `tileset_resource_path` (ruta
relativa al proyecto a un archivo `.json`). En runtime, `Tilemap.get_tileset_resource()`
carga y cachea el recurso.

### PhysicsMaterial — Recurso serializable independiente

`PhysicsMaterial` se serializa como archivo `.json` independiente, no como parte del
payload de escena. El contrato serializable incluye:

| Campo | Tipo | Default | Descripción |
|-------|------|---------|-------------|
| `resource_id` | str | `""` | Identificador único del material |
| `resource_name` | str | `"default"` | Nombre legible |
| `friction` | float | `1.0` | Coeficiente de fricción (0 = deslizante, 1 = normal) |
| `bounce` | float | `0.0` | Coeficiente de restitución (0 = sin rebote, 1 = rebote perfecto) |
| `rough` | bool | `False` | Fricción efectiva infinita (sobrescribe `friction`) |
| `absorbent` | bool | `False` | Bounce efectivo 0 (sobrescribe `bounce`) |
| `schema_version` | int | `1` | Versión del formato de serialización |

Ejemplo de archivo `materials/ice.json`:
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

**Compatibilidad legacy:**
- Payloads sin `schema_version` se cargan con default `1` (no hay cambios de schema entre v1 actual).
- Payloads sin `resource_id` o `resource_name` se cargan con defaults vacíos.
- El campo `rough=True` fuerza fricción efectiva infinita, ignorando `friction`.
- El campo `absorbent=True` fuerza bounce efectivo 0, ignorando `bounce`.

**Uso desde escena:**
`RigidBody` y `StaticBody2D` referencian un PhysicsMaterial mediante el campo
`physics_material_override_path` (ruta relativa al proyecto).

### CollisionShapeSet2D — Multiple collision shapes por entidad

`CollisionShapeSet2D` es un componente registrado que permite definir múltiples
shapes de colisión sobre una misma entidad. Cada shape se define como un
`CollisionShape2DDef` (data-only, no es un Component) con su propio tipo,
offset, trigger flag y propiedades físicas.

Payload JSON serializado en escena:

```json
{
  "shapes": [
    {
      "shape_type": "box",
      "offset_x": 0.0,
      "offset_y": 0.0,
      "disabled": false,
      "is_trigger": false,
      "one_way_collision": false,
      "one_way_collision_direction_y": -1.0,
      "friction": 0.2,
      "restitution": 0.0,
      "width": 32.0,
      "height": 32.0,
      "radius": 16.0,
      "points": [],
      "capsule_height": 0.0
    }
  ]
}
```

Campos de `CollisionShape2DDef`:

| Campo | Tipo | Default | Descripción |
|-------|------|---------|-------------|
| `shape_type` | string | `"box"` | Tipo de shape: `"box"`, `"circle"`, `"capsule"`, `"polygon"` |
| `offset_x` | float | `0.0` | Offset local X desde el transform de la entidad |
| `offset_y` | float | `0.0` | Offset local Y desde el transform de la entidad |
| `disabled` | bool | `false` | Si es `true`, esta shape se ignora en colisiones |
| `is_trigger` | bool | `false` | Si es `true`, solo evento trigger sin bloqueo físico |
| `one_way_collision` | bool | `false` | Colisión unilateral (solo desde arriba) |
| `one_way_collision_direction_y` | float | `-1.0` | Dirección de la colisión unilateral |
| `friction` | float | `0.2` | Coeficiente de fricción de esta shape |
| `restitution` | float | `0.0` | Coeficiente de restitución (rebote) de esta shape |
| `width` | float | `32.0` | Ancho (para shapes `"box"`) |
| `height` | float | `32.0` | Alto (para shapes `"box"`) |
| `radius` | float | `16.0` | Radio (para shapes `"circle"` y `"capsule"`) |
| `points` | list[list[float]] | `[]` | Vértices locales (para shapes `"polygon"`) |
| `capsule_height` | float | `0.0` | Altura del segmento central (para shapes `"capsule"`) |

**Compatibilidad legacy:** Si una entidad no tiene `CollisionShapeSet2D`, el
sistema usa el `Collider` legacy como única shape envuelta en un
`CollisionShape2DDef` sintético, manteniendo compatibilidad total con escenas
existentes.

**Default:** Si el payload tiene `shapes: []` (lista vacía), se crea una shape
por defecto tipo `"box"` con valores predeterminados.

En `Animator`, el payload vigente sigue usando `animations`, `default_state`,
`current_state`, `sprite_sheet` y `sprite_sheet_path`. Como foundation opcional
de Fase 6 puede incluir tambien:

- `parameters`: mapa `name -> {type, default}` con tipos `bool`, `int`, `float`
  y `trigger`
- `state_machine`: `entry_state` y `states`
- `states.<name>.transitions`: lista con `to`, `conditions`, `has_exit_time`,
  `exit_time`, `force_restart` y `name` opcional
- `conditions`: `parameter`, `operator`, `value`

Los valores runtime de parametros y triggers no se serializan; solo se
serializa su configuracion declarativa.
`RectTransform` conserva anclas, pivote, offsets y tamano del payload legacy,
y ahora puede serializar foundation adicional de layout:

- `layout_mode = free | vertical_stack | horizontal_stack`
- `layout_order = 0` por defecto
- `layout_ignore = false` por defecto
- `size_mode_x = fixed | stretch`
- `size_mode_y = fixed | stretch`
- `layout_align = start | center | end | stretch`
- `padding_left`, `padding_top`, `padding_right`, `padding_bottom`, `spacing`
  con default `0.0`

Estos campos son aditivos y mantienen compatibilidad con escenas UI existentes:
si no estan presentes, `RectTransform` sigue resolviendose como layout libre
basado en anchors/pivot/anchored offsets.

## Migraciones automaticas

### Escenas

La migracion cubre:

- ausencia de `schema_version`
- defaults top-level: `name`, `entities`, `rules`, `feature_metadata`
- defaults de entidad: `active`, `tag`, `layer`, `components`
- `id` estable de entidad cuando falta o esta vacio, generado de forma
  determinista desde la escena, posicion y nombre legacy
- canonicalizacion de componentes core legacy
- referencias de asset legacy en campos publicos core: `Sprite.texture`, `Animator.sprite_sheet`, `Tilemap.tileset`, `Tilemap.tileset_resource_path`, `AudioSource.asset`, `ScriptBehaviour.script`

### Prefabs

La migracion cubre:

- wrapper de prefab legacy de entidad unica
- normalizacion de `prefab_instance.overrides`
- canonicalizacion equivalente de componentes core
- asset refs publicos equivalentes a escenas

## Errores explicitos

La migracion no parchea payloads ambiguos en silencio. Deben fallar casos como:

- `schema_version` no soportado
- `Animator.sprite_sheet` y `sprite_sheet_path` inconsistentes
- `Sprite.texture` y `texture_path` inconsistentes
- `AudioSource.asset` y `asset_path` inconsistentes
- `ScriptBehaviour.script` y `module_path` incompatibles

Ejemplos de errores esperados:

- `Unsupported scene schema version: 99`
- `Cannot migrate $.entities[0].components.Animator: inconsistent sprite_sheet and sprite_sheet_path`

## Validacion

Tras migrar, el payload se valida contra `v2`.

Los errores usan paths estables, por ejemplo:

- `$.entities[1].parent: unknown parent 'Ghost'`
- `$.entities[0].components.RigidBody.body_type: expected one of [...]`
- `$.feature_metadata.render_2d.sorting_layers[1]: duplicate layer 'Default'`

## Feature metadata

`feature_metadata` concentra configuracion transversal del core y modulos
oficiales. Ejemplos actuales:

- `render_2d`
- `physics_2d`
- `scene_flow`
- `signals`

 El backend fisico solicitado se mantiene como dato serializable. El runtime
 puede usar fallback efectivo sin sobrescribir el valor solicitado.

`signals` serializa conexiones persistentes bajo `feature_metadata.signals.connections`.
Cada conexion define `source.id`, `source.signal`, un `target` soportado
(`entity` o `event_bus`), una referencia `callable`, y opcionalmente `flags`,
`binds`, `enabled`, `description` e `id` estable.
Para `target.kind == "entity"`, `target.id` es la identidad estable preferida
cuando existe; `target.name` se mantiene como compatibilidad y fallback.

## Alcance de validacion

La validacion profunda cubre el core serializable. Algunos componentes de
modulos o integraciones siguen con validacion minima de objeto serializable si
su contrato profundo no esta formalizado en el schema.

La UI serializable valida `RGBA`, strings de slice y referencias de asset para
sprites UI cuando esos campos estan presentes. En esta fase, la foundation
aditiva de layout en `RectTransform` se serializa y roundtripea como contrato
de compatibilidad, pero no introduce aun una matriz nueva de validacion estricta
en `engine/serialization/schema.py`.

## Tests relacionados

- `tests/test_schema_validation.py`
- `tests/test_official_contract_contract.py`
- `tests/test_official_contract_regression.py`
- `tests/test_core_regression_matrix.py`
