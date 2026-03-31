# Contrato De Serializacion Del Core

## Version actual

- `scene schema_version = 2`
- `prefab schema_version = 2`

`engine/serialization/schema.py` es la fuente de verdad del contrato
serializable. Toda carga migra primero a la version actual y valida despues.
Todo guardado emite payload canónico `v2`.

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
- payloads que siguen siendo invalidos despues de migrar
- JSON ajenos al contrato de escena/prefab usados por error como input del tooling

## Migraciones automaticas

### Escenas

- ausencia de `schema_version`
  - se interpreta como legacy y se promociona por pipeline `v0 -> v1 -> v2`
- defaults top-level y de entidad
  - `name`, `entities`, `rules`, `feature_metadata`
  - `active`, `tag`, `layer`, `components`
- canonicalizacion de componentes core legacy:
  - `Collider`
    - añade `shape_type`, `radius`, `points`, `friction`, `restitution`, `density`
  - `RigidBody`
    - añade `body_type`, `simulated`, `freeze_x`, `freeze_y`,
      `constraints`, `use_full_kinematic_contacts`,
      `collision_detection_mode`
  - referencias de asset legacy en string para campos publicos core
    - `Sprite.texture`
    - `Animator.sprite_sheet`
    - `Tilemap.tileset`
    - `AudioSource.asset`
    - `ScriptBehaviour.script`

### Prefabs

- wrapper de prefab legacy de entidad unica
- normalizacion de `prefab_instance.overrides` legacy tipo mapa a
  `overrides.operations`
- canonicalizacion equivalente de componentes core y asset refs publicos

## Casos que requieren error explicito

La migracion no parchea en silencio payloads ambiguos. Ejemplos:

- `schema_version` no soportado
- `Animator.sprite_sheet` y `sprite_sheet_path` inconsistentes
- `Sprite.texture` y `texture_path` inconsistentes
- `AudioSource.asset` y `asset_path` inconsistentes
- `ScriptBehaviour.script` y `module_path` incompatibles

En estos casos el motor devuelve errores claros del tipo:

- `Unsupported scene schema version: 99`
- `Cannot migrate $.entities[0].components.Animator: inconsistent sprite_sheet and sprite_sheet_path`

## Validacion

Tras migrar, el payload se valida contra `v2`.

La validacion usa errores estables por path, por ejemplo:

- `$.entities[1].parent: unknown parent 'Ghost'`
- `$.entities[0].components.RigidBody.body_type: expected one of ['dynamic', 'kinematic', 'static']`
- `$.feature_metadata.render_2d.sorting_layers[1]: duplicate layer 'Default'`

## Impacto sobre assets antiguos

- los assets legacy siguen cargando si la migracion es no ambigua
- al guardarse, se reescriben en formato canónico `v2`
- en este cierre de prioridad 1, `levels/*.json` del repo principal queda
  normalizado a `v2`

## Alcance actual

El endurecimiento profundo cubre el core serializable del motor. Siguen fuera de
validacion profunda en esta iteracion:

- `CharacterController2D`
- `Joint2D`
- `PlayerController2D`
- `RenderOrder2D`
- `RenderStyle2D`
- `SceneLink`

Estos componentes siguen pasando por validacion minima de objeto serializable.
