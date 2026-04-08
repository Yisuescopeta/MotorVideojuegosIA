# Motor de Videojuegos 2D - IA First

Motor/editor 2D experimental en Python orientado a trabajar con un modelo
serializable comun para editor, runtime y API. El proyecto no intenta ocultar
estado en la UI: la fuente de verdad vive en escenas, prefabs y metadatos
serializables.

## Estado actual

La base tecnica mas estable del repositorio hoy es:

- `scene schema_version = 2`
- `prefab schema_version = 2`
- la carga migra payloads legacy y `v1` a `v2` antes de validar
- el guardado emite payload canonico `v2`
- `SceneManager`, `Game`/`HeadlessGame` y `EngineAPI` operan sobre el mismo
  contrato de datos
- existe una matriz de regresion del core que protege invariantes de
  serializacion, workspace, authoring, `EDIT -> PLAY -> STOP` y API publica

El proyecto sigue siendo experimental. Hay capacidades reales de authoring,
runtime, headless y tooling, pero no se documenta como motor cerrado ni como
producto listo para produccion.

## Inicio rapido

```bash
pip install -r requirements.txt
pip install -e .[dev]
python main.py
```

## Testing y CLI

```bash
python -m unittest discover -s tests

python -m motor doctor --project . --json
python -m motor capabilities --json

python -m ruff check engine/api engine/project engine/rl engine/serialization engine/events cli tools main.py
python -m mypy engine/api engine/project engine/rl engine/serialization engine/events cli tools main.py
python -m bandit -q -c .bandit -r engine cli tools main.py
python -m pip_audit --skip-editable --ignore-vuln CVE-2026-4539
```

## Taxonomia del motor

La referencia canonica de clasificacion vive en
[docs/module_taxonomy.md](docs/module_taxonomy.md). El resumen operativo es:

### Core obligatorio

- ECS, `Scene`, `SceneManager`, serializacion y schema/migraciones
- editor base y jerarquia como parte del authoring compartido
- `EngineAPI` y contrato fisico base con fallback `legacy_aabb`
- pruebas de regresion que protegen ese nucleo

### Modulos oficiales opcionales

- assets y prefabs
- tilemap, audio y UI serializable
- `box2d` y otras capacidades oficiales no necesarias para el contrato minimo

### Experimental/tooling

- `engine/rl`
- datasets, runners, multiagente y debug avanzado
- tooling de investigacion y benchmarking fuera del contrato base

## Contrato de datos

La escena serializable es la fuente de verdad. `Scene` contiene el payload
editable y persistible; `SceneManager.edit_world` es una proyeccion editable de
ese payload; `SceneManager.runtime_world` es un clon temporal para `PLAY`.
`Game.world` y `HeadlessGame.world` exponen el `active_world`, pero no
sustituyen al modelo serializable.

El payload canonico de escena contiene como minimo:

- `name`
- `schema_version`
- `entities`
- `rules`
- `feature_metadata`

`feature_metadata` concentra configuracion transversal soportada por el core,
como `render_2d`, `physics_2d` y `scene_flow`, siempre validada desde schema.

## Capas principales

- `Scene`: guarda datos serializables, resuelve prefabs y reconstruye `World`
  desde datos.
- `SceneManager`: coordina workspace, authoring estructural, transacciones,
  historial, dirty state y la transicion `EDIT -> PLAY -> STOP`.
- `Game` / `HeadlessGame`: coordinan estado del motor, tiempo y sistemas sobre
  el mundo activo.
- `EngineAPI`: fachada publica para agentes, tests, CLI y scripts. Internamente
  esta delegada por dominios, pero la fachada publica sigue siendo unica.
- UI/editor: traduce interacciones de usuario al mismo contrato compartido. No
  debe crear fuente de verdad paralela.

## EngineAPI actual

`EngineAPI` expone dominios publicos de trabajo sin depender de internals
privados del runtime:

- authoring de entidades, componentes y `feature_metadata`
- runtime (`play`, `stop`, `step`, eventos e input inyectado)
- workspace y scene flow
- assets y proyecto
- debug/profiler
- UI serializable

La documentacion tecnica completa esta en:

- [docs/architecture.md](docs/architecture.md)
- [docs/TECHNICAL.md](docs/TECHNICAL.md)
- [docs/schema_serialization.md](docs/schema_serialization.md)

## Controles del editor

| Tecla | Accion |
|---|---|
| `SPACE` | Play |
| `P` | Pause / Resume |
| `ESC` | Stop |
| `R` | Recargar escena |
| `TAB` | Mostrar u ocultar inspector |
| `UP` / `DOWN` | Scroll del inspector |
| `F8` | Hot-reload de scripts |
| `F10` | Step |
| `F11` | Fullscreen |
| `Ctrl+S` | Guardar escena |

## Contribucion y seguridad

El repositorio mantiene documentacion minima de gobernanza:

- [CONTRIBUTING.md](CONTRIBUTING.md)
- [SECURITY.md](SECURITY.md)
- [LICENSE](LICENSE)

No se promete soporte comercial ni SLA.
