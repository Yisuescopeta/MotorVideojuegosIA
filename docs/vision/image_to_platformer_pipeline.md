# Image to Platformer Pipeline

Estado: `experimental/tooling` (internal).

Este documento cubre dos pasos experimentales e internos:

- Fase 3: `GameSpec2D -> Scene builder`.
- Fase 4: `imagen simple -> deteccion determinista de grilla -> extraccion de
  tilemap -> GameSpec2D`.

El alcance sigue siendo conservador: no hay ML, no hay CV pesado, no hay red,
no hay soporte obligatorio para Pillow/OpenCV/numpy/supervision y no se
promete soporte arbitrario de formatos de imagen.

Implementacion: [`../../engine/vision/`](../../engine/vision/)

## Fase 4 — simple tile-grid y tilemap extraction without ML

La Fase 4 agrega helpers de vision basados solo en la libreria estandar para
fixturas controladas:

- `PixelImage` inmovil en memoria.
- carga de imagen PPM `P3` y `P6` con `load_image()` / `load_ppm()`.
- reconstruccion determinista de un `GameSpec2D` a partir de una imagen local o
  un `PixelImage` ya creado.

No hay analisis de imagen cruda generalista, no hay OCR, no hay segmentacion
ML/CV y no hay descarga de recursos desde red.

## Alcance actual

- Entrada: `GameSpec2D`
- Entrada CLI: `py -m motor vision spec validate <path> --project . --json`
- Entrada CLI: `py -m motor vision build-scene <gamespec_path> --out <scene_path> --project . --json`
- Salida: validacion estructurada y/o escena persistida via `EngineAPI`
- Representacion actual: `collider_blocks`
- Flujo: validar -> construir -> guardar
- No usa mutacion directa de JSON de escena
- No toca modulos protegidos del core
- No hay analisis de imagen cruda ni generacion desde assets visuales
- La Fase 4 no crea escenas ni expone aun comando CLI de imagen
- La salida de Fase 4 es solo `GameSpec2D`; la escena queda para fases
  posteriores o para el builder existente de Fase 3

## Soporte de imagen controlado

- Formatos soportados: PPM `P3` y `P6`
- Fuente soportada: `PixelImage` o ruta local a archivo PPM
- Formatos no soportados: PNG, JPG, WebP y similares
- Dependencias no obligatorias: Pillow, OpenCV, numpy y supervision
- Dependencias nuevas: no se introducen ni se requiere ADR para esta fase

El loader rechaza datos corruptos o truncados con errores estructurados. El
contrato se mantiene deliberadamente pequeno para fixturas reproducibles.

## Contrato operativo

- La validacion CLI pasa primero por `GameSpec2D.validate()` y devuelve
  resultado estructurado en JSON.
- `build-scene` solo debe ejecutarse despues de una validacion satisfactoria.
- El builder usa solo rutas publicas de authoring de `EngineAPI`.
- La escena se crea con `create_scene`, se puebla con `create_entity` y se
  persiste con `save_scene`.
- Si la validacion falla, no se escribe salida parcial.
- Si la ruta de salida ya existe, la CLI rechaza el overwrite por defecto.
- Si ocurre un error de authoring, se lanza `GameSpecSceneBuildError`.
- Los nombres de entidades y el orden de salida son deterministas.
- La Fase 4 no participa en este flujo de escena: solo produce `GameSpec2D`.

## Deteccion de grilla de tiles

La Fase 4 prueba candidatos de tamano de tile `8`, `16`, `24` y `32` por
defecto.

- El score favorece candidatos que dividen mejor la imagen y que muestran
  consistencia de color en las celdas.
- Si hay empate o la imagen no deja una grilla clara, se elige siempre el
  candidato menor de forma determinista.
- Se emiten advertencias estructuradas como `uniform_image` y
  `no_clear_grid` cuando la inferencia es ambigua o poco confiable.
- El resultado conserva scores por candidato para inspeccion interna.

## Mapeo semantico

El builder traduce semanticas de `GameSpec2D` a componentes ya existentes.
No introduce componentes publicos nuevos.

### Celdas solidas

- `solid_ground` -> entidad con `Transform` + `Collider`
- `platform` -> entidad con `Transform` + `Collider`
- fallback de celda solida: `collider_blocks` si no se usa helper de tilemap

### Entidades

- `player_spawn` -> `RespawnPoint2D` + `Sprite`
- `solid_ground` -> `Collider` + `Sprite`
- `platform` -> `Collider` + `MovingPlatform2D` + `Sprite`
- `coin` -> `Collider` + `Collectible2D` + `Sprite`
- `enemy_patrol` -> `Collider` + `EnemyPatrol2D` + `Sprite`
- `hazard` -> `Collider` + `Hazard2D` + `Sprite`
- `goal` -> `Collider` + `Goal2D` + `Sprite`
- `checkpoint` -> `Collider` + `Checkpoint2D` + `Sprite`
- `killzone` -> `Collider` + `KillZone2D` + `Sprite`
- `decorative_prop` -> `Sprite` y etiquetado/layer decorativo

## Nombre y orden deterministas

- Las celdas se ordenan por fila, columna, etiqueta y semantica.
- Las entidades usan sufijos estables como `coin_001`, `coin_002`.
- Las celdas solidas usan nombres estables como `solid_ground_cell_001_000`.
- `SceneBuildReport.entity_names` conserva el orden de creacion.
- `SceneBuildReport.semantic_mapping` agrupa por semantica y se ordena por clave.

## Validacion

Antes de crear nada, `GameSpec2D.validate()` debe pasar.
Si el spec es invalido:

- no se crea una escena utilizable;
- no se sobreescribe una salida previa;
- no se publica un resultado parcial.

Para Fase 4, la salida valida sigue siendo un `GameSpec2D` serializable.

## Extraccion de celdas solidas

La extraccion de tilemap en Fase 4 asume fixturas simples y controladas:

- clasificacion por color del centro de la celda
- color de fondo por defecto tomado del pixel `(0, 0)` cuando no se pasa uno
- `solid_predicate` opcional para sobreescribir la regla por color
- celdas solidas emitidas en orden fila-major

Si la imagen no produce celdas solidas, se registra `no_solid_tiles`.
La advertencia no invalida el spec por si sola; solo informa que el tilemap
extraido quedo vacio.

## Dependencias

No hay dependencias CV opcionales obligatorias.
Este builder no importa `cv2`, `PIL`, `numpy` ni `supervision`.

## Uso minimo

```python
from pathlib import Path

from engine.vision import GameSpec2D, build_scene_from_gamespec2d

spec = GameSpec2D.from_dict({...})
report = build_scene_from_gamespec2d(spec, Path("levels/generated.scene"), project_root=".")

print(report.scene_path)
print(report.entity_names)
print(report.semantic_mapping)
```

## Limitaciones conocidas

- No lee imagenes crudas.
- No existe CLI para analisis de imagen o inferencia visual.
- No existe aun comando CLI oficial para image-to-gamespec.
- La CLI solo cubre `vision spec validate` y `vision build-scene`.
- No hay inferencia CV en este paso.
- El builder solo trabaja con el contrato `GameSpec2D` existente.
- Las entidades generadas usan componentes publicos ya registrados; no hay
  componentes nuevos de escena.
- Si el entorno o dependencias nativas imprimen ruido de arranque en stderr, el
  contrato relevante sigue siendo el JSON parseable de stdout.
- Esta fase no cubre texturas arbitrarias, atlas ni deteccion visual general.

## Validacion de fase

Comandos relevantes:

```bash
py -m unittest tests.test_vision_tile_grid_detector tests.test_vision_tilemap_reconstructor -v
py -m unittest tests.test_vision_gamespec2d tests.test_vision_gamespec_to_scene -v
py -m unittest tests.test_vision_cli_contract -v
py -m motor doctor --project . --json
```

## Rollback

Si esta fase introduce una regresion, revertir en este orden:

1. retirar `docs/vision/image_to_platformer_pipeline.md`
2. revertir `engine/vision/tilemap_reconstructor.py`
3. revertir `engine/vision/tile_extractor.py`
4. revertir `engine/vision/tile_grid_detector.py`
5. revertir `engine/vision/image_loader.py`
6. revertir el builder de Fase 3 si la regresion toca el flujo GameSpec2D -> Scene

Mantener `GameSpec2D` y la pipeline de imagen como contrato experimental
independiente del core.

La regresion documental se considera resuelta si el doc vuelve a reflejar solo
el alcance realmente implementado.

## Siguiente fase

La siguiente fase puede exponer o ampliar el flujo de image-to-gamespec, pero
solo cuando exista una decision explicita sobre CLI y formato de entrada.
Hasta entonces, el pipeline permanece como tooling interno de Python.
