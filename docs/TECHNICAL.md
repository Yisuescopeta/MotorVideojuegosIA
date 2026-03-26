# Documentación Técnica del Motor 2D

## Índice

1. [Arquitectura General](#arquitectura-general)
2. [Sistema ECS](#sistema-ecs)
3. [Componentes](#componentes)
4. [Sistemas](#sistemas)
5. [Eventos y Reglas](#eventos-y-reglas)
6. [Gestión de Escenas](#gestión-de-escenas)
7. [Inspector Visual](#inspector-visual)
8. [Guia de Uso de API](#guia-de-uso-de-api)
9. [Orquestacion Multiagente](#orquestacion-multiagente)

---

## Arquitectura General

El motor sigue una arquitectura **Entity-Component-System (ECS)** con las siguientes características:

- **Entidades**: Contenedores con ID único y nombre
- **Componentes**: Datos puros sin lógica
- **Sistemas**: Procesan entidades con ciertos componentes
- **World**: Contenedor de todas las entidades

### Diagrama de Flujo

```
main.py
   │
   ▼
Game (game loop)
   │
   ├── SceneManager (gestión de estados)
   │       │
   │       ├── Scene (datos originales)
   │       └── World/RuntimeWorld
   │
   ├── Sistemas
   │       ├── RenderSystem (siempre)
   │       ├── AnimationSystem (PLAY/preview)
   │       ├── PhysicsSystem (solo PLAY)
   │       └── CollisionSystem (solo PLAY)
   │
   ├── EventBus (comunicación)
   │       └── RuleSystem (reglas declarativas)
   │
   └── InspectorSystem (debug visual)
```

---

## Sistema ECS

### Entity

```python
class Entity:
    id: int           # ID único auto-generado
    name: str         # Nombre legible
    
    def add_component(component: Component) -> None
    def get_component(type) -> Component | None
    def has_component(type) -> bool
    def get_all_components() -> list[Component]
```

### Component

```python
class Component:
    """Clase base. Los componentes son datos puros."""
    
    def to_dict() -> dict       # Serialización
    @classmethod
    def from_dict(data) -> Self # Deserialización
```

### World

```python
class World:
    def create_entity(name: str) -> Entity
    def get_entity(id: int) -> Entity | None
    def get_entity_by_name(name: str) -> Entity | None
    def get_entities_with(*types) -> list[Entity]
    def destroy_entity(id: int) -> None
    def clone() -> World  # Copia profunda
    def clear() -> None
```

`World.get_entities_with()` solo devuelve entidades activas cuyos componentes
requeridos estan `enabled`. Los sistemas que usan componentes opcionales deben
respetar tambien su flag `enabled`.

---

## Componentes

### Transform

Posición, rotación y escala de la entidad.

```python
Transform(
    x: float = 0.0,
    y: float = 0.0,
    rotation: float = 0.0,  # grados
    scale_x: float = 1.0,
    scale_y: float = 1.0
)
```

### Sprite

Textura para renderizado.

```python
Sprite(
    texture_path: str,
    width: int = 0,      # 0 = auto
    height: int = 0,
    origin_x: float = 0.5,  # centro
    origin_y: float = 0.5,
    flip_x: bool = False,
    flip_y: bool = False,
    tint: tuple = (255, 255, 255, 255)
)
```

### Collider

Área de colisión AABB.

```python
Collider(
    width: float,
    height: float,
    offset_x: float = 0.0,
    offset_y: float = 0.0,
    is_trigger: bool = False  # True = sin física
)
```

### RigidBody

Física básica.

```python
RigidBody(
    velocity_x: float = 0.0,
    velocity_y: float = 0.0,
    gravity_scale: float = 1.0,
    is_grounded: bool = False
)
```

### Animator

Animaciones por sprite sheet.

```python
Animator(
    sprite_sheet: str,
    frame_width: int,
    frame_height: int,
    animations: dict[str, AnimationData],
    current_state: str = "idle"
)

AnimationData(
    frames: list[int],
    fps: float = 10,
    loop: bool = True,
    on_complete: str | None = None
)
```

### PlayerController2D

Control lateral y salto serializable apoyado en `InputMap` y `RigidBody`.

```python
PlayerController2D(
    move_speed: float = 180.0,
    jump_velocity: float = -320.0,
    air_control: float = 0.75
)
```

### ScriptBehaviour

Script adjunto serializable con hot-reload y hooks simples por modulo.

```python
ScriptBehaviour(
    module_path: str = "",
    run_in_edit_mode: bool = False,
    public_data: dict[str, Any] = {}
)
```

Contrato del modulo:

```python
def on_play(context): ...
def on_update(context, dt): ...
def on_stop(context): ...
```

`public_data` es la unica bolsa de estado persistente del script. El contexto
expone `world`, `entity_name`, `scene_manager` y helpers de log/lectura de
componentes.

---

## Sistemas

### RenderSystem

- **Activo**: Siempre
- **Función**: Dibuja entidades con Sprite o Animator
- **Dependencias**: Transform + (Sprite | Animator)

### PhysicsSystem

- **Activo**: Solo en PLAY
- **Función**: Aplica gravedad y actualiza posiciones
- **Dependencias**: Transform + RigidBody

### CollisionSystem

- **Activo**: Solo en PLAY
- **Función**: Detecta colisiones AABB
- **Eventos**: `on_collision`, `on_trigger_enter`
- **Dependencias**: Transform + Collider

### AnimationSystem

- **Activo**: PLAY (normal) / EDIT (0.25x)
- **Función**: Avanza frames de animación
- **Eventos**: `on_animation_end`
- **Dependencias**: Animator

### PlayerControllerSystem

- **Activo**: PLAY
- **Función**: Convierte `InputMap.last_state` en movimiento lateral y salto
- **Dependencias**: InputMap + RigidBody + PlayerController2D

### ScriptBehaviourSystem

- **Activo**: PLAY y opcionalmente EDIT (`run_in_edit_mode`)
- **FunciÃ³n**: Ejecuta `ScriptBehaviour` con hot-reload sin romper el runtime
- **Dependencias**: ScriptBehaviour

---

## Eventos y Reglas

### EventBus

```python
event_bus = EventBus()

# Suscribirse
event_bus.subscribe("on_collision", callback)

# Emitir
event_bus.emit("on_collision", {
    "entity_a": "Player",
    "entity_b": "Enemy"
})
```

### RuleSystem

Ejecuta reglas declarativas desde JSON.

```json
{
    "event": "on_collision",
    "when": {
        "entity_a": "Player",
        "entity_b": "Enemy"
    },
    "do": [
        {"action": "set_animation", "entity": "Player", "state": "hit"},
        {"action": "log_message", "message": "¡Colisión!"}
    ]
}
```

### Acciones Disponibles

| Acción | Parámetros |
|--------|------------|
| `set_animation` | entity, state |
| `set_position` | entity, x, y |
| `destroy_entity` | entity |
| `emit_event` | event, data |
| `log_message` | message |

---

## Gestión de Escenas

### Scene

Almacena datos originales del nivel (inmutable durante PLAY).

```python
scene = Scene("Demo", level_data)
world = scene.create_world(registry)
```

### SceneManager

Gestiona transiciones entre EDIT y PLAY.

```python
manager = SceneManager(registry)
world = manager.load_scene(level_data)

# PLAY
runtime = manager.enter_play()  # Crea copia

# STOP
world = manager.exit_play()     # Restaura original
```

Durante EDIT, `SceneManager` es la via comun de authoring para API y editor:

- `update_entity_property()` para `active`, `tag` y `layer`
- `apply_edit_to_world()` para props de componentes serializables
- `add_component_to_entity()` y `remove_component_from_entity()`

La UI no debe introducir rutas paralelas con estado exclusivo fuera de `Scene`.

### Flujo de Estados

```
EngineState.EDIT
    │
    │ game.play()
    ▼
EngineState.PLAY ◄──► EngineState.PAUSED
    │                     │
    │ game.stop()         │ game.stop()
    ▼                     ▼
EngineState.EDIT (restaurado)
```

---

## Inspector Visual

Panel lateral que muestra el estado de todas las entidades.

La seleccion activa se conserva entre `EDIT`, `PLAY` y `STOP` mediante
`SceneManager`, de modo que el inspector sigue anclado a la misma entidad
aunque la pestaÃ±a visible sea `Game View`.

`Camera2D` expone follow y framing solo con datos serializables:

- `framing_mode = "platformer"`
- `dead_zone_width` / `dead_zone_height`
- `clamp_left`, `clamp_right`, `clamp_top`, `clamp_bottom`
- `recenter_on_play`

### Controles

| Tecla | Acción |
|-------|--------|
| TAB | Mostrar/ocultar |
| UP/DOWN | Scroll |
| PAGE_UP/DOWN | Scroll rápido |

### Características

- Lista todas las entidades con ID y nombre
- Muestra componentes y propiedades en tiempo real
- Usa introspección (`to_dict()` o reflexión)
- Panel semitransparente a la derecha

---

## Guia de Uso de API

### Crear un Nivel

1. Crear archivo `levels/mi_nivel.json`:

```json
{
    "name": "Mi Nivel",
    "entities": [
        {
            "name": "Player",
            "components": {
                "Transform": {"x": 100, "y": 200},
                "RigidBody": {"gravity_scale": 1.0}
            }
        }
    ],
    "rules": []
}
```

2. Cargar en `main.py`:

```python
level_data = load_level_data("levels/mi_nivel.json")
world = scene_manager.load_scene(level_data)
```

### Modificar Entidad Programáticamente

```python
from engine.api import EngineAPI

api = EngineAPI()
api.load_level("levels/demo_level.json")
api.set_entity_tag("Player", "Hero")
api.set_entity_layer("Player", "Gameplay")
api.set_component_enabled("Ground", "Collider", False)
api.create_camera2d("MainCamera", camera={"follow_entity": "Player"})
filtered = api.list_entities(tag="Hero", layer="Gameplay", active=True)
```

### Añadir Nueva Regla

```json
{
    "event": "on_trigger_enter",
    "when": {"entity_b": "Coin"},
    "do": [
        {"action": "destroy_entity", "entity": "Coin"}
    ]
}
```

### Estados del Motor

```python
# Iniciar juego
game.play()

# Pausar
game.pause()

# Detener y restaurar
game.stop()
```

---

## Notas de Diseno

1. **Todo es serializable**: Componentes tienen `to_dict()`/`from_dict()`
2. **Sin lógica oculta**: Cada acción es explícita
3. **Datos sobre código**: Preferir modificar JSON a código
4. **Estados claros**: EDIT, PLAY, PAUSED son mutuamente excluyentes
5. **Scene es inmutable**: Los cambios en PLAY no afectan la Scene
6. **Config centralizado**: Todas las constantes en `engine/config.py`
7. **Errores no crashean**: Los try/except en el game loop capturan errores y los envían a la consola

---

## Hot-Reload

### HotReloadManager

Monitoriza `scripts/` y recarga módulos modificados con `importlib.reload()`.

```python
from engine.core.hot_reload import HotReloadManager

manager = HotReloadManager("scripts")
manager.scan_directory()         # Descubrir scripts
changed = manager.check_for_changes()  # Detectar y recargar
```

### Crear Scripts Recargables

```python
# scripts/mi_script.py
def on_reload():
    """Se ejecuta al recargar (F8)."""
    print("Recargado!")
```

---

## Herramientas de Desarrollo

### create_mechanic

Genera un nuevo System con boilerplate ECS:

```bash
py -3 tools/create_mechanic.py <nombre> <descripción> <componentes>
```

### introspect

Inspección de estado en tiempo de ejecución:

```python
from tools.introspect import inspect_world, inspect_entity, list_systems

inspect_world(world)           # Resumen del mundo
inspect_entity(world, "Player") # Detalle de entidad
list_systems()                 # Sistemas disponibles
```

---

## Orquestacion Multiagente

El repo incluye una capa inicial para coordinar agentes con foco en `core`,
`API`, `escenas` y `pruebas`.

### Roles base

- `Agente Orquestador`: entrada unica, crea briefs y valida handoffs.
- `Core Architect`: acota diseno tecnico y contratos.
- `Core Implementer`: aplica cambios en el motor.
- `QA & Regression`: valida smoke tests y regresiones.
- `Debugger`: investiga fallos por causa raiz.
- `Docs & Contracts`: mantiene prompts, limites y documentacion operativa.

### Contratos

Los agentes se coordinan con tres artefactos:

- `docs/agent-orchestration/task-brief-template.md`
- `docs/agent-orchestration/result-bundle-template.md`
- `docs/agent-orchestration/definition-of-done.md`

### Utilidad de apoyo

`tools/agent_workflow.py` puede generar un `Task Brief` inicial y sugerir
validaciones segun subsistemas afectados.

La matriz base de paridad para `Unity 2D core` vive en:

- `docs/agent-orchestration/unity-2d-core-matrix.md`

Regla obligatoria:

- ninguna feature puede existir solo en UI
- toda accion editable por el usuario debe existir tambien por API o datos
- la UI actua como traductor del modelo serializable

---

## Configuración Centralizada

`engine/config.py` contiene todas las constantes del motor:

| Constante | Valor | Descripción |
|-----------|-------|-------------|
| `GRAVITY_DEFAULT` | 980.0 | Gravedad en px/s² |
| `GROUND_Y_TEMP` | 550.0 | Suelo temporal |
| `WINDOW_WIDTH` | 800 | Ancho ventana |
| `WINDOW_HEIGHT` | 600 | Alto ventana |
| `TARGET_FPS` | 60 | FPS objetivo |
| `EDIT_ANIMATION_SPEED` | 0.25 | Velocidad preview |
| `SCRIPTS_DIRECTORY` | "scripts" | Dir hot-reload |
