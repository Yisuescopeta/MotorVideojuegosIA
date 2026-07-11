# GameSpec2D

Estado: `experimental/tooling`.

GameSpec2D es el contrato interno experimental de `engine/vision` para
interpretar una imagen 2D como un spec intermedio de juego de plataformas. El
paquete expone solo contratos de datos: no depende de `Scene`, `EngineAPI`,
`SceneManager`, la serializacion core, ni del render. En Fase 1 no genera
escenas.

Implementacion: [`../engine/vision/`](../engine/vision/)

## Alcance

- `STATUS` del paquete: `internal-experimental`
- `schema_version` soportado: `gamespec2d.v1`
- `game_type` soportado: `platformer`
- objetivo: normalizar, validar y transportar hallazgos de vision en un
  contrato JSON-compatible

## Modelo de datos

| Campo | Tipo | Uso |
|---|---|---|
| `source` | `SourceImageMetadata` | Metadatos de la imagen de entrada. |
| `camera` | `CameraSpec` | Encadre/crop sugerido para la camara. |
| `grid` | `GridSpec` | Dimensiones de la grilla base y tamano de tile. |
| `tilemap` | `TileMapSpec` | Celdas solidas y decorativas detectadas. |
| `entities` | lista de `EntitySpec` | Entidades semanticas detectadas. |
| `warnings` | lista de `WarningSpec` | Advertencias del analisis o del sintetizador. |
| `confidence` | float opcional | Confianza global del spec. |
| `metadata` | dict | Metadatos arbitrarios serializables. |

### `SourceImageMetadata`

- `width`
- `height`
- `path`
- `metadata`

### `CameraSpec`

- `x`
- `y`
- `width`
- `height`
- `confidence`
- `metadata`

### `GridSpec`

- `width`
- `height`
- `tile_size`
- `origin_x`
- `origin_y`
- `confidence`
- `metadata`

### `TileMapSpec`

- `solid_cells`
- `decorative_cells`
- `confidence`
- `metadata`

### `TileCell`

- `x`
- `y`
- `semantics`
- `label`
- `confidence`
- `metadata`

### `EntitySpec`

- `type`
- `x`
- `y`
- `semantics`
- `label`
- `confidence`
- `metadata`

### `WarningSpec`

- `code`
- `message`
- `confidence`
- `metadata`

## Tipos de entidad permitidos

`EntitySpec.type` solo admite:

- `player_spawn`
- `solid_ground`
- `platform`
- `coin`
- `enemy_patrol`
- `hazard`
- `goal`
- `checkpoint`
- `killzone`
- `decorative_prop`

Regla de semantica:

- para entidades normales, `semantics` y `label` deben ser uno de los tipos
  permitidos si se especifican
- `decorative_prop` es la unica excepcion: puede transportar etiquetas o
  semanticas libres
- la misma excepcion aplica a celdas decorativas con `label == decorative_prop`

## Validacion

`GameSpec2D.validate()` aplica estas reglas:

- `schema_version` debe ser exactamente `gamespec2d.v1`
- `game_type` debe ser exactamente `platformer`
- `grid.width` y `grid.height` deben ser enteros positivos
- `grid.tile_size` debe ser un numero finito positivo
- `grid.origin_x` y `grid.origin_y` deben ser finitos
- `camera.x` y `camera.y` deben ser finitos
- `camera.width` y `camera.height`, si existen, deben ser finitos y positivos
- cada celda de `solid_cells` y `decorative_cells` debe caer dentro de la grilla
- cada `EntitySpec.type` debe pertenecer al conjunto permitido
- `EntitySpec.x` y `EntitySpec.y` deben ser finitos
- cada `confidence` explicita debe estar entre `0.0` y `1.0`, inclusive
- los campos `confidence` anidados dentro de `metadata` tambien se validan de
  forma recursiva cuando aparecen como clave literal `confidence`

## Serializacion

- `from_dict()` acepta mappings JSON-like
- `to_dict()` devuelve solo dicts/listas/escalares JSON-compatible
- el roundtrip `GameSpec2D.from_dict(spec.to_dict())` debe preservar el payload
  y seguir validando
- los campos faltantes se normalizan con defaults seguros (`{}` o listas vacias)

## Politica de dependencias

Este contrato no tiene dependencia obligatoria de:

- OpenCV (`cv2`)
- Pillow (`PIL`)
- numpy
- supervision

El modulo debe seguir siendo util aun cuando esas librerias no esten
instaladas. Cualquier integracion con tooling CV externo es opcional y no forma
parte de este contrato.

## No objetivos

- no crea `Scene`
- no modifica `EngineAPI`
- no coordina `SceneManager`
- no sustituye la serializacion core
- no define pipeline de inferencia concreto
- no convierte automaticamente el spec en escenas durante Fase 1

## Rollback

Si este contrato experimental se retira, revertir en este orden:

1. eliminar `docs/vision/gamespec2d.md`
2. quitar la clasificacion de `engine/vision` en `docs/module_taxonomy.md`
3. retirar el paquete `engine/vision/` y sus tests solo si la funcionalidad se
   descarta por completo

Mientras siga activo, mantenerlo etiquetado como `experimental/tooling` e
independiente del contrato core.
