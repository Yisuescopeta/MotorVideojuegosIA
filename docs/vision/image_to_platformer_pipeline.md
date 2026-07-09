# Image to Platformer Pipeline

Estado: `experimental/tooling`.

Este documento describe la Fase 2 del flujo `GameSpec2D -> Scene builder`.
El alcance es solo la construccion de escena desde un `GameSpec2D` ya valido.
No hay CLI todavia, no hay analisis de imagen todavia y no se generan escenas
directamente desde una imagen cruda.

Implementacion: [`../../engine/vision/`](../../engine/vision/)

## Alcance actual

- Entrada: `GameSpec2D`
- Salida: escena persistida via `EngineAPI`
- Representacion actual: `collider_blocks`
- Flujo: validar -> construir -> guardar
- No usa mutacion directa de JSON de escena
- No toca modulos protegidos del core

## Contrato operativo

- El builder usa solo rutas publicas de authoring de `EngineAPI`.
- La escena se crea con `create_scene`, se puebla con `create_entity` y se
  persiste con `save_scene`.
- Si la validacion falla, no se escribe salida parcial.
- Si ocurre un error de authoring, se lanza `GameSpecSceneBuildError`.
- Los nombres de entidades y el orden de salida son deterministas.

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
- No existe CLI de esta fase.
- No hay inferencia CV en este paso.
- El builder solo trabaja con el contrato `GameSpec2D` existente.
- Las entidades generadas usan componentes publicos ya registrados; no hay
  componentes nuevos de escena.

## Validacion de fase

Comandos relevantes:

```bash
py -m unittest tests.test_vision_gamespec2d tests.test_vision_gamespec_to_scene -v
py -m unittest tests.test_component_serialization_contracts tests.test_official_contract_regression -v
py -m motor doctor --project . --json
```

## Rollback

Si esta fase introduce una regresion, revertir en este orden:

1. retirar `docs/vision/image_to_platformer_pipeline.md`
2. revertir `engine/vision/gamespec_to_scene.py`
3. revertir `engine/vision/semantic_prefabs.py`
4. revertir `engine/vision/__init__.py`

Mantener `GameSpec2D` como contrato experimental independiente hasta la Fase 3.

## Siguiente fase

La siguiente fase conecta este builder con la CLI oficial. Hasta entonces, el
pipeline permanece como tooling interno de Python.
