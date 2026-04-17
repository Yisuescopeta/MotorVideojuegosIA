# Contrato de serializacion del core

`engine/serialization/schema.py` es la fuente de verdad tecnica para schemas,
migracion y validacion.

## Version actual

- `scene schema_version = 2`
- `prefab schema_version = 2`

Toda carga migra primero a la version actual y valida despues. Todo guardado de
escena o prefab emite payload canonico `v2`.

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
Los componentes publicos deben estar registrados en
`engine/levels/component_registry.py`.

En UI serializable, el contrato vigente incluye `Canvas`, `RectTransform`,
`UIText`, `UIButton` y `UIImage`. `UIButton` admite visuales opcionales por
sprite (`*_sprite`, `*_slice`, `image_tint`, `preserve_aspect`) sin romper el
payload legacy basado en colores. `UIImage` serializa `sprite`, `slice_name`,
`tint` y `preserve_aspect`.

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

## Migraciones automaticas

### Escenas

La migracion cubre:

- ausencia de `schema_version`
- defaults top-level: `name`, `entities`, `rules`, `feature_metadata`
- defaults de entidad: `active`, `tag`, `layer`, `components`
- canonicalizacion de componentes core legacy
- referencias de asset legacy en campos publicos core: `Sprite.texture`, `Animator.sprite_sheet`, `Tilemap.tileset`, `AudioSource.asset`, `ScriptBehaviour.script`

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

El backend fisico solicitado se mantiene como dato serializable. El runtime
puede usar fallback efectivo sin sobrescribir el valor solicitado.

## Alcance de validacion

La validacion profunda cubre el core serializable. Algunos componentes de
modulos o integraciones siguen con validacion minima de objeto serializable si
su contrato profundo no esta formalizado en el schema.

La UI serializable valida `RGBA`, strings de slice y referencias de asset para
sprites UI cuando esos campos estan presentes.

## Tests relacionados

- `tests/test_schema_validation.py`
- `tests/test_official_contract_contract.py`
- `tests/test_official_contract_regression.py`
- `tests/test_core_regression_matrix.py`
