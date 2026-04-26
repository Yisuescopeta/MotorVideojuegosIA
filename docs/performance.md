# Performance y benchmarks

Benchmarks sinteticos para medir rendimiento antes de optimizar. Viven en
tooling experimental y usan el runtime headless real mediante
`engine.debug.benchmark_runner`.

## Ejecutar

Comando base:

```bash
py -m tools.benchmark_run --scenario many_transform_entities --mode play --frames 120 --entity-count 10000 --out reports/bench_10k.json
```

Suite pequena para CI con umbrales suaves:

```bash
py -m tools.benchmark_suite --quick --out artifacts/benchmarks/performance_suite.json
```

La suite ejecuta `transform_edit_stress` 10k, `play_mode_clone_stress` 10k,
`many_static_colliders` y `many_sprite_entities` en headless. `--quick` reduce
los escenarios no 10k para mantener el coste de CI acotado. Sin `--quick`, esos
escenarios usan cargas locales algo mayores para comparacion manual.

Por defecto, la suite solo devuelve codigo distinto de cero ante regresiones
enormes o comportamiento roto: crash del benchmark, operaciones obligatorias
ausentes, conteos inesperados o umbrales duros superados. Los umbrales suaves
quedan registrados como warnings en el JSON y no fallan CI salvo que se use
`--fail-on-warning`.

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

## Guardado compacto de escenas grandes

`SceneManager.save_scene_to_file` mantiene por defecto el JSON legible con
`indent=4` para escenas pequenas. Cuando una escena supera
`COMPACT_SCENE_SAVE_ENTITY_THRESHOLD` entidades, el guardado automatico usa JSON
compacto con `separators=(",", ":")` para reducir tamano y tiempo de escritura.

El parametro `compact_save` permite forzar el modo: `True` guarda compacto y
`False` conserva el formato legible aunque la escena supere el umbral. Este
cambio solo afecta espacios y saltos de linea; el payload serializable y
`load_scene_from_file` siguen usando el mismo contrato.

## Escenarios

- `many_transform_entities`: muchas entidades con `Transform`.
- `many_sprite_entities`: muchas entidades renderizables con `Sprite`.
- `many_ui_buttons`: canvas y muchos botones UI.
- `huge_tilemap`: un tilemap denso configurable.
- `transform_edit_stress`: escena grande para medir una edicion serializable.
- `play_mode_clone_stress`: escena grande para medir entrada y salida de PLAY.
- Escenarios existentes de fisica: `many_static_colliders`,
  `one_dynamic_many_static`, `many_dynamic_and_static`.

Los benchmarks individuales no fallan por umbral. La suite
`tools.benchmark_suite` agrega warnings suaves y puertas duras amplias para CI,
pensadas para detectar regresiones grandes sin depender de pequenas variaciones
de hardware.

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

## Validacion rama Fix/optimizacion5.5 - 2026-04-26

Estado tomado sobre la rama local `Fix/optimizacion5.5`, alineada con
`origin/Fix/optimizacion5.5` en el momento de la validacion. El comando
`python -m ...` no pudo ejecutarse por configuracion local: `python` apunta al
alias de Microsoft Store. Las validaciones reales se ejecutaron con `py -m ...`.

Comandos ejecutados:

- `python -m unittest discover -s tests`: no ejecuta por el alias local de
  Microsoft Store.
- `py -m unittest discover -s tests`: falla tras 1565 tests, con 3 failures y
  3 errors.
- `py -m tools.benchmark_suite --quick --out artifacts/benchmarks/performance_suite.json`:
  pasa con 4/4 escenarios, 0 warnings y 0 failures. Duracion aproximada:
  29.34 s. El JSON generado queda en
  `artifacts/benchmarks/performance_suite.json`.
- `py -m ruff check engine cli tools main.py`: falla con 277 errores.
- `py -m mypy engine cli tools main.py`: falla con 196 errores en 31 archivos.

Fallos principales de `unittest`:

- `engine/app/debug_tools_controller.py`: `_FakePerfWorld` no tiene
  `iter_all_entities`.
- `engine/core/game.py`: `_resolve_default_ui_parent` intenta iterar un `Mock`.
- `tests/test_agent_service.py`: `opencode-go` aparece como `configured` en vez
  de `missing`; parece dependiente del entorno local de credenciales.
- `tests/test_inspector_core.py`: el test esperaba rebuild con cambio de
  `entity.id`, pero el id no cambia.
- `tests/test_performance_infra.py`: la cache de layout no se invalida como
  espera el test.

Resumen de analisis estatico:

- Ruff reporta principalmente whitespace, imports sin ordenar, imports no
  usados, nombres indefinidos y sentencias multiples en una linea.
- Mypy reporta principalmente problemas de tipos en ECS/world, render, editor,
  scene manager, agent provider y sistemas runtime.

Clasificacion de riesgo:

- Varios archivos implicados en los fallos estan modificados frente a
  `origin/main`, asi que algunos fallos podrian haber sido introducidos por
  esta rama, especialmente los de performance/debug/ui cache.
- No se puede afirmar preexistencia definitiva sin ejecutar las mismas
  validaciones en `origin/main`.
- El fallo de disponibilidad de `python` es de entorno local, no de la rama.
