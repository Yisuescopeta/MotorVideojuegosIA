# Optimization 5.5 validation

Fecha: 2026-04-27
Rama revisada: `Fix/optimización5.5`
Base solicitada no encontrada localmente: `fix/optimizacion5.5-estabilizacion`

## Checks ejecutados

| Comando | Resultado |
| --- | --- |
| `python -m unittest discover -s tests` | OK: 1595 tests, 9 skipped, 629.120 s |
| `python -m tools.benchmark_suite --quick --out artifacts/benchmarks/performance_suite.json` | OK: suite `passed`, 4/4 escenarios, 0 warnings, 0 failures |
| `python -m ruff check engine/assets/asset_database.py engine/project/project_service.py engine/ecs/world.py engine/ecs/entity.py engine/systems/render_system.py engine/rendering/render_spatial_index.py engine/systems/script_behaviour_system.py engine/components/tilemap.py engine/systems/physics_system.py engine/systems/ui_system.py tests/test_asset_database.py tests/test_project_service.py tests/test_render_graph.py tests/test_render_spatial_index.py tests/test_script_behaviour_system.py tests/test_tilemap_api.py tests/test_physics_system.py tests/test_serialized_id_runtime.py tests/test_world_versions.py` | FAIL: 8 errores (imports no ordenados en `ui_system.py` y tests; variables no usadas en tests; nombres ambiguos en `test_tilemap_api.py`) |
| `python -m mypy engine/assets/asset_database.py engine/project/project_service.py engine/ecs/world.py engine/ecs/entity.py engine/systems/render_system.py engine/rendering/render_spatial_index.py engine/systems/script_behaviour_system.py engine/components/tilemap.py engine/systems/physics_system.py engine/systems/ui_system.py` | OK: no issues found in 10 source files |
| `python -m ruff check engine cli tools main.py` | FAIL: 275 errores globales |
| `python -m mypy engine cli tools main.py` | FAIL: 168 errores globales en 26 archivos |

Validacion enfocada adicional (script manual `tmp_validation_script.py`):

- `ProjectService.list_assets()` usa SQLite cuando el indice existe: **PASS**.
- `ProjectService.list_project_scenes()` usa SQLite cuando el indice existe: **PASS**.
- `Entity.to_dict()["id"]` siempre es `str`: **PASS**.
- `World.get_entity_by_serialized_id()` funciona tras rename y remove: **PASS**.
- `RenderSpatialIndex.bounds_for_entity()` devuelve bounds para entidad con solo `Transform`: **PASS**.
- `RenderSystem` invalida render graph al cambiar `world.transform_version`: **PASS**.
- `PhysicsSystem` incrementa `transform_version` al mover una entidad: **PASS**.
- `ScriptBehaviourSystem` deja de ejecutar hooks tras eliminar `ScriptBehaviour`: **PASS**.
- `Tilemap.iter_visible_runtime_chunks()` acota candidatos por camera_bounds: **PASS**.

## Benchmarks quick

Suite:

- Status: `passed`
- Duracion total: 28080.21 ms
- Total: 4
- Passed: 4
- Warnings: 0
- Failed: 0

Escenarios:

| Escenario | Status | Duracion ms | Metricas clave |
| --- | --- | ---: | --- |
| `transform_edit_stress_10k` | passed | 8323.17 | load_level 4107.23; transform_edit **0.21**; render_preparation 94.60; frame_max 0.09 |
| `play_mode_clone_stress_10k` | passed | 15491.97 | load_level 5084.74; edit_to_play 663.03; play_to_edit 1215.14; render_preparation 112.76; frame_max 18.02 |
| `many_static_colliders` | passed | 1638.46 | load_level 281.32; edit_to_play 46.41; play_to_edit 70.83; frame_max 71.67 |
| `many_sprite_entities_headless` | passed | 2626.38 | load_level 680.79; edit_to_play 114.25; play_to_edit 161.48; render_preparation **25.04**; frame_max 3.32 |

Confirmaciones de metricas clave:

- `transform_edit_stress_10k`: `transform_edit` se mantiene en ~0.21 ms (muy bajo, dentro del umbral de 50 ms soft / 500 ms hard).
- `many_sprite_entities_headless`: `render_preparation` se mantiene en ~25.04 ms (razonable, dentro del umbral de 4000 ms soft / 20000 ms hard).
- No existe escenario `huge_tilemap` en la suite quick; no se evaluo en esta corrida.

## Revision manual

- Asset index: `AssetDatabase` mantiene lectura por indice SQLite cuando el schema es valido; `list_assets()` y `list_project_scenes()` recurren al indice sin escaneo completo si `_asset_index_is_usable` devuelve `True`.
- IDs serializados: `Entity.to_dict()["id"]` siempre es `str`; el fallback `runtime_{self.id}` es string y no entero.
- World/versiones granulares: los sistemas revisados usan `render_version`, `transform_version`, `structure_version` o `ui_layout_version` donde corresponde.
- Render: la cache de ordenado incluye `transform_version`, necesario porque `Transform.depth` afecta el sort. El indice espacial se reconstruye desde la lista ordenada cacheada y el culling reduce entidades visibles.
- Tilemap: `iter_visible_runtime_chunks()` filtra candidatos por bounds de camara y no recorre todos los chunks cuando la camara permite acotar.
- Scripts: `ScriptBehaviourSystem` limpia hooks compilados cuando el componente desaparece.
- Physics: `PhysicsSystem` incrementa `world.transform_version` al aplicar velocidad/posicion.

## Riesgos restantes

- `ruff` global sigue fallando con **275 errores**. Ejemplos: imports sin ordenar (I001), lineas en blanco con espacios (W293), imports no usados (F401), variables no usadas (F841), nombres ambiguos (E741), multiples sentencias en una linea (E701). Afecta a `engine/editor/*`, `engine/systems/selection_system.py`, `engine/levels/*`, `engine/agent/*`, `engine/workflows/*`, entre otros.
- `mypy` global sigue fallando con **168 errores en 26 archivos**. Ejemplos: tipos no resueltos en `engine/core/game.py`, `engine/app/runtime_controller.py`, `engine/editor/editor_layout.py`, `engine/inspector/inspector_system.py`, `engine/scenes/scene_manager.py`, `engine/agent/provider.py`.
- Los fallos globales parecen deuda previa o fuera del alcance inmediato de estabilizacion 5.5; no se hizo refactor masivo.
- `artifacts/benchmarks/performance_suite.json` fue regenerado por el comando exacto solicitado. Se agrego `artifacts/benchmarks/*.json` a `.gitignore` para evitar commitear baselines locales no versionados.

## Recomendacion

**No mergear todavia.**

Con criterio estricto, la rama **no esta lista para merge** porque `ruff` y `mypy` globales siguen fallando. Los tests unitarios, benchmarks y verificaciones manuales especificas de optimizacion 5.5 pasan, pero el gate de calidad global (lint + typecheck) no es verde.

Mergear solo si el equipo acepta explicitamente la deuda global de lint/type como no bloqueante para esta rama. Si se exige gate verde completo, hay que corregir la deuda global de `ruff` y `mypy` antes del merge.
