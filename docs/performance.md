# Performance y benchmarks

Benchmarks sinteticos para medir rendimiento antes de optimizar. Viven en
tooling experimental y usan el runtime headless real mediante
`engine.debug.benchmark_runner`.

## Ejecutar

Comando base:

```bash
py -m tools.benchmark_run --scenario many_transform_entities --mode play --frames 120 --entity-count 10000 --out reports/bench_10k.json
```

Escenas grandes con `Transform`:

```bash
py -m tools.benchmark_run --scenario many_transform_entities --mode play --frames 120 --entity-count 10000 --columns 100 --out reports/transforms_10k.json
py -m tools.benchmark_run --scenario many_transform_entities --mode play --frames 120 --entity-count 50000 --columns 250 --out reports/transforms_50k.json
py -m tools.benchmark_run --scenario many_transform_entities --mode play --frames 120 --entity-count 100000 --columns 400 --out reports/transforms_100k.json
```

Sprites y preparacion de render headless:

```bash
py -m tools.benchmark_run --scenario many_sprite_entities --mode play --frames 120 --entity-count 10000 --columns 100 --out reports/sprites_10k.json
```

Edicion de `Transform.x` en escena grande:

```bash
py -m tools.benchmark_run --scenario transform_edit_stress --mode edit --frames 1 --entity-count 10000 --columns 100 --out reports/transform_edit_10k.json
```

Transiciones EDIT -> PLAY y PLAY -> EDIT:

```bash
py -m tools.benchmark_run --scenario play_mode_clone_stress --mode play --frames 1 --entity-count 10000 --columns 100 --out reports/play_clone_10k.json
```

UI y tilemap:

```bash
py -m tools.benchmark_run --scenario many_ui_buttons --mode edit --frames 1 --entity-count 5000 --columns 20 --out reports/ui_buttons_5k.json
py -m tools.benchmark_run --scenario huge_tilemap --mode edit --frames 1 --tilemap-width 256 --tilemap-height 256 --out reports/tilemap_256.json
```

Fisica con colliders estaticos y dinamicos:

```bash
py -m tools.benchmark_run --scenario many_dynamic_and_static --mode play --frames 120 --backend legacy_aabb --static-count 10000 --dynamic-count 100 --columns 200 --spacing 24 --out reports/physics_legacy.json
py -m tools.benchmark_run --scenario many_dynamic_and_static --mode play --frames 120 --backend box2d --static-count 10000 --dynamic-count 100 --columns 200 --spacing 24 --out reports/physics_box2d.json
```

## JSON

El reporte conserva `summary`, `profiler_report` y `last_sample`. Las mediciones
puntuales viven en `operations`:

```json
{
  "operations": {
    "load_level": {"ms": 0.0},
    "transform_edit": {
      "ms": 0.0,
      "success": true,
      "target_entity": "Entity_9999",
      "field": "Transform.x"
    },
    "edit_to_play": {"ms": 0.0},
    "play_to_edit": {"ms": 0.0},
    "render_preparation": {
      "ms": 0.0,
      "stats": {"render_entities": 0, "draw_calls": 0}
    }
  }
}
```

Las claves no aplicables se omiten. Por ejemplo, `transform_edit` solo aparece en
`transform_edit_stress`.

## Escenarios

- `many_transform_entities`: muchas entidades con `Transform`.
- `many_sprite_entities`: muchas entidades renderizables con `Sprite`.
- `many_ui_buttons`: canvas y muchos botones UI.
- `huge_tilemap`: un tilemap denso configurable.
- `transform_edit_stress`: escena grande para medir una edicion serializable.
- `play_mode_clone_stress`: escena grande para medir entrada y salida de PLAY.
- Escenarios existentes de fisica: `many_static_colliders`,
  `one_dynamic_many_static`, `many_dynamic_and_static`.

Estos benchmarks no definen umbrales de exito. Su objetivo es generar mediciones
comparables antes de cambios de optimizacion.

## Asset index incremental

`engine.assets.asset_database.AssetDatabase` mantiene un indice SQLite basico en
`.motor/asset_index.sqlite`. El indice guarda `guid`, ruta relativa, ruta
absoluta, extension, tipo, `mtime`, tamano y nombre visible de assets bajo
`assets/`, `scripts/`, `prefabs/` y `levels/`.

`rebuild()` recrea el indice completo. `update_changed()` compara `mtime` y
tamano para insertar nuevos archivos, actualizar modificados y borrar entradas
de archivos eliminados. `list_assets()`, `get_by_path()` y `get_by_guid()` leen
desde SQLite y crean el indice si falta.

Este indice todavia no reemplaza `ProjectService.list_assets`; esa ruta legacy
sigue vigente hasta una integracion publica dedicada.
