# Image to Platformer Pipeline

Estado: `experimental/tooling` (internal).

Este documento cubre la Fase 5: una imagen PPM controlada se convierte en un
`GameSpec2D` sidecar y luego en una escena de plataformas mediante el builder
publico.

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

## Limitaciones

- Solo PPM controlado; no screenshots ni soportes de assets visuales generales.
- Sin ML/CV ni dependencias de vision obligatorias.
- Sin red, Roboflow, keys, descargas de modelos ni entrenamiento.
- El resultado depende del contrato existente de `GameSpec2D`.
- La salida debe inspeccionarse via JSON; `success=false` es un fallo
  estructurado.

## Rollback

Si esta fase introduce una regresion, revertir en este orden:

1. `engine/vision/image_to_platformer.py`
2. hooks de CLI en `motor/cli_core.py` y `motor/cli.py`
3. registro de capacidad en `engine/ai/registry_builder.py`
4. luego, si hace falta, la reconstruccion determinista de tilemap

Mantener el comportamiento experimental desactivado o retirarlo antes que
romper el flujo `GameSpec2D -> Scene` existente.

## Validacion de fase

Comandos relevantes:

```bash
py -m unittest tests.test_vision_build_platformer_cli -v
py -m unittest tests.test_vision_cli_contract tests.test_vision_tilemap_reconstructor tests.test_vision_gamespec2d tests.test_vision_gamespec_to_scene -v
py -m motor vision build-platformer tests/fixtures/vision/simple_platformer.ppm --out <temp> --project . --json
py -m motor doctor --project . --json
```
