# Documentación Técnica del Motor 2D

## Índice

1. [Arquitectura General](#arquitectura-general)
2. [Sistema ECS](#sistema-ecs)
3. [Componentes](#componentes)
4. [Sistemas](#sistemas)
5. [Eventos y Reglas](#eventos-y-reglas)
6. [Gestión de Escenas](#gestión-de-escenas)
7. [Inspector Visual](#inspector-visual)
8. [Guía de Uso para IA](#guía-de-uso-para-ia)

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

## Guía de Uso para IA

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
# Obtener entidad
player = world.get_entity_by_name("Player")

# Modificar componente
transform = player.get_component(Transform)
transform.x = 200
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

## Notas para IA

1. **Todo es serializable**: Componentes tienen `to_dict()`/`from_dict()`
2. **Sin lógica oculta**: Cada acción es explícita
3. **Datos sobre código**: Preferir modificar JSON a código
4. **Estados claros**: EDIT, PLAY, PAUSED son mutuamente excluyentes
5. **Scene es inmutable**: Los cambios en PLAY no afectan la Scene
