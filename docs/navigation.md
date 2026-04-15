# Navigation / Pathfinding

Estado: `experimental/tooling`.

El modulo de navegacion no pertenece al contrato de `core obligatorio`. Es una
infraestructura de pathfinding standalone que puede integrarse con Tilemap,
fisica o runtime en fases futuras.

Implementacion: [../engine/navigation/](../engine/navigation/)

## Superficie actual

- `Vec2`: coordenada 2D entera e inmutable.
- `NavigationGrid`: grilla 2D con celdas transitables y coste por celda.
- `AStarPathfinder`: A* sobre `NavigationGrid`.
- `NavigationService`: fachada de consultas.

## Ejemplo

```python
from engine.navigation import NavigationGrid, NavigationService

grid = NavigationGrid.from_walkable_matrix([
    [True, True, True, True, True],
    [True, True, True, True, True],
    [True, True, True, True, True],
    [True, True, True, True, True],
    [True, True, True, True, True],
])

service = NavigationService(grid)
result = service.query_path(0, 0, 4, 4)
print(result.success, result.path, result.cost)
```

## `Vec2`

Soporta:

- suma, resta y multiplicacion escalar
- `manhattan_distance`
- `chebyshev_distance`

## `NavigationGrid`

Datos principales:

- `width`
- `height`
- `cell_size`
- `walkable`
- `cost_multiplier`

Conversiones:

- `world_to_grid(x, y)`
- `grid_to_world_center(col, row)`

Vecinos:

- `neighbors_4(pos)`
- `neighbors_8(pos)`

## `AStarPathfinder`

Comportamiento actual:

- movimiento 4 u 8 direcciones
- multiplicadores de coste por celda
- prevencion de corner-cutting diagonal
- line of sight basado en Bresenham
- limite de iteraciones para queries con presupuesto

## `NavigationService`

Metodos principales:

- `query_path(x1, y1, x2, y2, diagonal=True)`
- `query_world_path(wx1, wy1, wx2, wy2)`
- `has_line_of_sight(x1, y1, x2, y2)`
- `get_reachable_positions(x, y, max_cost)`
- `build_navmesh_from_grid()`

## Serializacion

`NavigationGrid` se serializa a dict y JSON:

```python
data = grid.to_dict()
restored = NavigationGrid.from_dict(data)
grid.to_json("path/to/navgrid.json")
restored = NavigationGrid.from_json("path/to/navgrid.json")
```

## No objetivos actuales

- No esta acoplado a Tilemap.
- No esta acoplado a fisica.
- No es un sistema runtime con tick por frame.
- No es un NavMesh 3D.

## Integraciones futuras posibles

Tilemap:

- generar grilla desde propiedades de tiles
- invalidar grilla al cambiar tiles
- referenciar fuentes de tilemap desde metadata

Fisica:

- marcar celdas bloqueadas con bounds de colliders
- actualizar walkability por eventos de colision
- mantener navegacion independiente de cuerpos fisicos si conviene

Runtime:

- exponer consultas desde scripts o sistemas IA
- convertir paths de grilla a waypoints en mundo

Antes de promocionar este modulo fuera de `experimental/tooling`, actualizar
[module_taxonomy.md](module_taxonomy.md), [architecture.md](architecture.md) y
tests de contrato.
