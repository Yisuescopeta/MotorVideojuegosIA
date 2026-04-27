# Optimization 5.5 validation

Fecha: 2026-04-27
Rama revisada: `Fix/optimización5.5`
Base solicitada no encontrada localmente: `fix/optimizacion5.5-estabilizacion`

## Checks ejecutados

| Comando | Resultado |
| --- | --- |
| `python -m unittest discover -s tests` | OK: 1595 tests, 9 skipped, 685.921 s |
| `python -m tools.benchmark_suite --quick --out artifacts/benchmarks/performance_suite.json` | OK: suite `passed`, 4/4 escenarios, 0 warnings, 0 failures |
| `python -m ruff check engine cli tools main.py` | FAIL: 275 errores globales |
| `python -m mypy engine cli tools main.py` | FAIL: 168 errores globales en 26 archivos |

Validacion enfocada adicional sobre los archivos tocados por la rama:

- `python -m ruff check engine/assets/asset_database.py engine/ecs/world.py engine/systems/render_system.py engine/systems/script_behaviour_system.py engine/systems/physics_system.py tests/test_debug_tools_controller.py tests/test_editor_tools.py tests/test_benchmark_run.py tests/test_inspector_core.py`: OK.
- `python -m mypy engine/assets/asset_database.py engine/ecs/world.py engine/systems/render_system.py engine/systems/script_behaviour_system.py engine/systems/physics_system.py`: OK.

## Benchmarks quick

Suite:

- Status: `passed`
- Duracion total: 53016.15 ms
- Total: 4
- Passed: 4
- Warnings: 0
- Failed: 0

Escenarios:

| Escenario | Status | Duracion ms | Metricas clave |
| --- | --- | ---: | --- |
| `transform_edit_stress_10k` | passed | 14040.82 | load_level 4693.72; transform_edit 0.28; render_preparation 168.67; frame_max 0.22 |
| `play_mode_clone_stress_10k` | passed | 31130.36 | load_level 9933.54; edit_to_play 1130.51; play_to_edit 1849.64; render_preparation 186.73; frame_max 28.33 |
| `many_static_colliders` | passed | 2841.55 | load_level 427.00; edit_to_play 54.60; play_to_edit 100.54; frame_max 156.74 |
| `many_sprite_entities_headless` | passed | 5002.88 | load_level 1342.79; edit_to_play 267.65; play_to_edit 294.87; render_preparation 58.63; frame_max 5.33 |

## Revision manual

- Asset index: `AssetDatabase` mantiene lectura por indice SQLite solo cuando el schema es valido; `has_current_index()` queda documentado como validacion cara y no se usa en rutas calientes.
- World/versiones granulares: los sistemas revisados usan `render_version`, `transform_version`, `structure_version` o `ui_layout_version` donde corresponde. Se elimino el uso residual de `world.version` en la cache runtime de scripts.
- Render: la cache de ordenado incluye `transform_version`, necesario porque `Transform.depth` afecta el sort. El indice espacial se reconstruye desde la lista ordenada cacheada y el culling reduce entidades visibles en los benchmarks.
- Tilemap: la lista de chunks runtime se cachea e invalida al reconstruir chunks o al crear/vaciar chunks. La seleccion visible evita recorrer todos los chunks cuando la camara permite acotar candidatos.
- UI: layout cacheado por `ui_layout_version` y viewport; la interaccion reutiliza la lista de botones visibles.
- Transform/RectTransform: los tests actualizados validan edicion in-place y preservacion de estado de fold, sin exigir rebuild de entidad.
- IDs serializados: no se detectaron ids enteros persistidos en los archivos revisados. El fallback `runtime_{self.id}` sigue siendo string y no debe tratarse como identidad persistente estable.

## Riesgos restantes

- `ruff` global sigue fallando. Ejemplos: imports sin ordenar y imports no usados en `engine/agent/*`, `engine/app/runtime_controller.py`, `engine/systems/selection_system.py`, `engine/systems/ui_system.py`, entre otros.
- `mypy` global sigue fallando. Ejemplos: `engine/app/runtime_controller.py` referencia `Entity` sin definir; `engine/core/game.py` tiene tipos no resueltos para sistemas runtime; `engine/editor/editor_layout.py` expone atributos dinamicos no tipados; `engine/inspector/inspector_system.py` tiene multiples lambdas sin inferencia.
- Los fallos globales parecen deuda previa o fuera del alcance inmediato de estabilizacion 5.5; no se hizo refactor masivo.
- `artifacts/benchmarks/performance_suite.json` fue regenerado por el comando exacto solicitado.

## Recomendacion

No mergear todavia con criterio estricto, porque dos checks requeridos (`ruff` y `mypy` globales) fallan.

Mergear solo si el equipo acepta explicitamente esa deuda global como no bloqueante para esta rama. Si se exige gate verde completo, hay que corregir la deuda global de `ruff` y `mypy` antes del merge.
