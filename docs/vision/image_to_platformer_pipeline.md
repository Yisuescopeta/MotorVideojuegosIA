# Image to Platformer Pipeline

Estado: `experimental/tooling` (internal).

Este documento cubre la Fase 5: una imagen PPM controlada se convierte en un
`GameSpec2D` sidecar y luego en una escena de plataformas mediante el builder
publico. La Fase 7 añade un overlay PPM de diagnostico para inspeccionar la
proyeccion sin tocar render, editor, runtime ni `EngineAPI`.

Implementacion: [`../../engine/vision/`](../../engine/vision/)

## Fase 5 — PPM -> GameSpec2D sidecar -> scene builder

La pipeline publica sigue este orden determinista:

1. cargar imagen PPM `P3` o `P6`;
2. reconstruir un `GameSpec2D` con tilemap determinista;
3. validar el `GameSpec2D`;
4. escribir el sidecar `.gamespec.json`;
5. construir y guardar la escena mediante el builder publico.

El flujo existe para fixtures controladas y no usa ML, CV pesado, OCR ni
object detection. Tampoco promete soporte para PNG, JPG, WebP, screenshots
comerciales o assets arbitrarios.
La automatizacion publica de esta fase es la CLI; no hay wrapper publico de
`EngineAPI` todavia. La helper Python interna sigue siendo experimental y
persiste usando rutas publicas de authoring.

## Adapter de supervision (interno y opcional)

Esta fase admite como contrato de entrada dicts normalizados o DTOs
`DetectionResult` ya construidos por tooling externo. El adapter solo traduce
esas detecciones a `GameSpec2D`.

- `supervision` no es una dependencia requerida de OpenGame.
- No hay instalacion obligatoria, API key, descarga de modelos ni red.
- No hay inferencia ML, entrenamiento ni analisis de imagen en este adapter.
- Etiquetas desconocidas se degradan por defecto a `decorative_prop` con
  warnings; una politica de rechazo estricto es opcional para callers que lo
  necesiten.
- La salida se valida como `GameSpec2D`; no se emite `Scene` de forma directa
  desde el adapter.

## Entrada y salida

- Entrada soportada: PPM `P3`/`P6` local.
- Entrada no soportada: PNG, JPG, WebP y similares.
- Salida intermedia: `GameSpec2D` serializable.
- Salida final: escena persistida y reporte estructurado.
- Sidecar por defecto: `<scene_path>.gamespec.json`.

La CLI asociada es `py -m motor vision build-platformer <image_path> --out <scene_path> --project . --json`.
Puede usar `--gamespec-out` para fijar el sidecar.

## Contrato operativo

- Si la escena o el sidecar ya existen, el comando rechaza overwrite.
- Si la reconstruccion o validacion falla, no se deja salida parcial.
- Si el builder de escena falla, el cleanup elimina los archivos creados en esa
  ejecucion.
- No se modifican modulos protegidos del core.
- El Scene JSON no se edita a mano para este flujo.

## Fase 7 — Debug overlay PPM

La fase de debug overlay genera un PPM determinista y solo diagnostico a partir
de la imagen fuente y el `GameSpec2D` ya validado.

- Implementacion stdlib-only.
- Sin integracion con render, editor, runtime ni `EngineAPI`.
- Sin texto renderizado; solo grid, celdas y marcadores de entidad.
- Entrada soportada: PPM `P3`/`P6` de prueba.
- Salida: PPM `P3`.
- El comando `motor vision annotate <image_path> --gamespec <gamespec_path> --out <overlay_path> --project . --json` rechaza overwrite y falla sin dejar salida parcial.

Salida estructurada minima:

- `overlay_path`
- `source`
- `gamespec`
- `dimensions`
- `annotation_counts`
- `warning_count`
- `format`

`annotation_counts` agrupa `grid_lines`, `solid_cells`, `decorative_cells` y
`entities`. `warning_count` refleja las warnings del `GameSpec2D` cargado.

## Salida estructurada

El JSON del comando expone, como minimo, estos campos top-level:

En exito:

- `image_path`
- `gamespec_path`
- `scene_path`
- `warnings`
- `confidence`
- `unsupported_features`
- `schema_version`
- `game_type`
- `entity_count`
- `representation`
- `report`

`report` resume el build de escena con `scene_path`, `scene_name`,
`representation`, `entity_names` y `semantic_mapping`.

En fallo, los mismos campos se conservan cuando ya se pudieron inferir; cuando
no, se devuelven con defaults o vacios y el error sigue siendo estructurado en
`success=false` con `message` y `data`.

Para la fase de overlay, el JSON expone `overlay_path`, `source`, `gamespec`,
`dimensions`, `annotation_counts`, `warning_count` y `format`.

## Fase 8A.1 — Geometria semantica determinista

Las escenas generadas conservan sus componentes `Sprite` y añaden un
`Polygon2D` rectangular, centrado respecto al `Transform`, para cada tipo
semantico soportado. Las celdas solidas creadas directamente desde el tilemap
tambien incluyen este fallback visible.

- La paleta RGBA es explicita y estable por tipo semantico.
- La geometria depende solo del ancho y alto del elemento.
- No usa texturas, assets binarios, red ni dependencias nuevas.
- `Polygon2D` se serializa y recarga mediante la ruta publica existente.
- La representacion del reporte sigue siendo `collider_blocks`.

Esta geometria sirve para inspeccion estructural y smoke visual. No reproduce
el arte de la imagen fuente. La captura real del render y cualquier validacion
visual automatica pertenecen a fases posteriores y no quedan demostradas por
este fallback.

## Limitaciones

- Solo PPM controlado; no screenshots ni soportes de assets visuales generales.
- Sin ML/CV ni dependencias de vision obligatorias.
- Sin red, Roboflow, keys, descargas de modelos ni entrenamiento.
- El resultado depende del contrato existente de `GameSpec2D`.
- La salida debe inspeccionarse via JSON; `success=false` es un fallo
  estructurado.

## Rollback

Si esta fase introduce una regresion, revertir en este orden:

1. retirar solo los payloads `Polygon2D` semanticos de
   `engine/vision/semantic_prefabs.py` y `engine/vision/gamespec_to_scene.py`;
2. mantener `Sprite`, `Collider`, `GameSpec2D` y `representation="collider_blocks"`;
3. para un rollback mas amplio de la pipeline, retirar
   `engine/vision/image_to_platformer.py`, los hooks de CLI y la capability en
   ese orden.

Mantener el comportamiento experimental desactivado o retirarlo antes que
romper el flujo `GameSpec2D -> Scene` existente.

## Validacion de fase

Comandos relevantes:

```bash
py -m unittest tests.test_vision_cli_contract -v
py -m unittest tests.test_vision_build_platformer_cli -v
py -m unittest tests.test_vision_cli_contract tests.test_vision_tilemap_reconstructor tests.test_vision_gamespec2d tests.test_vision_gamespec_to_scene -v
py -m motor vision annotate tests/fixtures/vision/simple_platformer.ppm --gamespec examples/vision/simple_platformer.gamespec.json --out <temp> --project . --json
py -m motor vision build-platformer tests/fixtures/vision/simple_platformer.ppm --out <temp> --project . --json
py -m motor doctor --project . --json
```
