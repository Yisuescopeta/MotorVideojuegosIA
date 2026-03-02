# Motor de Videojuegos 2D - IA First

Motor de videojuegos 2D experimental diseñado para ser **comprendido, modificado y utilizado por una IA** para generar juegos simples.

## 🎯 Objetivos del Proyecto

- **Code-first**: Todo el juego se define por código y datos JSON
- **IA-friendly**: Arquitectura explícita y serializable
- **Sin magia**: Comportamiento predecible y observable
- **Académico**: Proyecto de ~3 meses

## 🚀 Inicio Rápido

```bash
# Instalar dependencias
pip install -r requirements.txt

# Ejecutar
python main.py
```

## 🎮 Controles

| Tecla | Acción |
|-------|--------|
| **ESPACIO** | Play (iniciar juego) |
| **P** | Pause/Resume |
| **ESC** | Stop (volver a edición) |
| **R** | Recargar nivel |
| **TAB** | Mostrar/ocultar inspector |
| **UP/DOWN** | Scroll del inspector |
| **F8** | Hot-Reload scripts |
| **F10** | Step (un frame) |
| **F11** | Fullscreen |
| **Ctrl+S** | Guardar escena |

## 📁 Estructura del Proyecto

```
MotorVideojuegosIA/
├── engine/                 # Motor principal
│   ├── core/              # Game loop, estados, tiempo
│   │   ├── game.py        # Clase principal del motor
│   │   ├── engine_state.py # Estados EDIT/PLAY/PAUSED
│   │   ├── time_manager.py
│   │   └── hot_reload.py  # Sistema de recarga en caliente
│   │
│   ├── ecs/               # Entity-Component-System
│   │   ├── entity.py      # Entidades con ID único
│   │   ├── component.py   # Clase base de componentes
│   │   └── world.py       # Contenedor de entidades
│   │
│   ├── components/        # Componentes de datos
│   │   ├── transform.py   # Posición, rotación, escala
│   │   ├── sprite.py      # Textura y renderizado
│   │   ├── collider.py    # Colisión AABB
│   │   ├── rigidbody.py   # Física básica
│   │   └── animator.py    # Animaciones sprite sheet
│   │
│   ├── systems/           # Sistemas que procesan componentes
│   │   ├── render_system.py
│   │   ├── physics_system.py
│   │   ├── collision_system.py
│   │   └── animation_system.py
│   │
│   ├── events/            # Sistema de eventos
│   │   ├── event_bus.py   # Publish-subscribe
│   │   └── rule_system.py # Reglas declarativas
│   │
│   ├── scenes/            # Gestión de escenas
│   │   ├── scene.py
│   │   └── scene_manager.py
│   │
│   ├── editor/            # Editor visual (paneles)
│   │   ├── console_panel.py  # Consola de errores/logs
│   │   ├── hierarchy_panel.py
│   │   └── editor_layout.py
│   │
│   ├── config.py          # Constantes centralizadas
│   └── resources/
│       └── texture_manager.py
│
├── scripts/               # Scripts recargables en caliente (F8)
│   └── example_script.py
│
├── tools/                 # Herramientas IA
│   ├── create_mechanic.py # Generador de sistemas
│   └── introspect.py      # Reflexión/inspección
│
├── levels/                # Archivos de niveles JSON
├── assets/                # Sprites y recursos
├── tests/                 # Tests y demos
├── .cursorrules           # Reglas globales para IA
├── main.py               # Punto de entrada
└── requirements.txt
```

## 🏗️ Arquitectura

### Entity-Component-System (ECS)

```python
# Crear entidad
player = world.create_entity("Player")

# Añadir componentes
player.add_component(Transform(x=100, y=200))
player.add_component(Collider(width=32, height=32))
player.add_component(RigidBody(gravity_scale=1.0))
```

### Componentes Disponibles

| Componente | Propósito |
|------------|-----------|
| `Transform` | Posición, rotación, escala |
| `Sprite` | Textura para renderizado |
| `Collider` | Área de colisión AABB |
| `RigidBody` | Física (gravedad, velocidad) |
| `Animator` | Animaciones por sprite sheet |

### Estados del Motor

| Estado | Física | Reglas | Animación |
|--------|--------|--------|-----------|
| **EDIT** | ❌ | ❌ | Preview (lento) |
| **PLAY** | ✔️ | ✔️ | Normal |
| **PAUSED** | ❌ | ❌ | ❌ |

## 📄 Formato de Nivel (JSON)

```json
{
    "name": "Mi Nivel",
    "entities": [
        {
            "name": "Player",
            "components": {
                "Transform": {"x": 100, "y": 200},
                "Collider": {"width": 32, "height": 32},
                "RigidBody": {"gravity_scale": 1.0}
            }
        }
    ],
    "rules": [
        {
            "event": "on_collision",
            "when": {"entity_a": "Player", "entity_b": "Enemy"},
            "do": [
                {"action": "set_animation", "entity": "Player", "state": "hit"}
            ]
        }
    ]
}
```

## 📡 Sistema de Eventos

### Eventos Emitidos

| Evento | Origen | Datos |
|--------|--------|-------|
| `on_collision` | CollisionSystem | entity_a, entity_b |
| `on_trigger_enter` | CollisionSystem | entity_a, entity_b |
| `on_animation_end` | AnimationSystem | entity, animation |
| `on_level_loaded` | Game | level_name |
| `on_play` | Game | - |

### Acciones de Reglas

| Acción | Efecto |
|--------|--------|
| `set_animation` | Cambia estado de animación |
| `set_position` | Mueve entidad |
| `destroy_entity` | Elimina entidad |
| `emit_event` | Dispara otro evento |
| `log_message` | Imprime en consola |

## 🔄 Gestión de Escenas

```
[EDIT] Scene → World (editable)
         ↓ SPACE (play)
[PLAY] World.clone() → RuntimeWorld (temporal)
         ↓ ESC (stop)
[EDIT] Scene → World (restaurado)
```

Al presionar **ESC**, el mundo vuelve exactamente al estado original.

## 🛠️ API para IA

```python
from engine import Game, World, Transform, Collider

# Crear mundo
world = World()

# Crear entidad programáticamente
enemy = world.create_entity("Enemy")
enemy.add_component(Transform(x=200, y=100))
enemy.add_component(Collider(width=32, height=32))

# Control del motor
game.play()   # EDIT → PLAY
game.pause()  # PLAY ↔ PAUSED
game.stop()   # → EDIT + restaurar
```

## 📊 Fases Completadas

| Fase | Descripción | Estado |
|------|-------------|--------|
| 1 | Entorno y setup | ✅ |
| 3 | ECS, Física, Colisiones | ✅ |
| 4 | Animaciones | ✅ |
| 5 | Inspector Visual | ✅ |
| 6 | Niveles JSON | ✅ |
| 7 | Eventos y Reglas | ✅ |
| 8 | Estados del Motor | ✅ |
| 12 | Gestión de Escenas | ✅ |

## 📋 Próximas Fases

- **Fase 9**: Controles de ejecución avanzados
- **Fase 10**: Inspector editable
- **Fase 11**: Sistema CLI
- **Fase 13**: API completa para IA

## 🔥 Hot-Reload (Recarga en Caliente)

Modifica scripts mientras el motor está corriendo:

1. Coloca scripts `.py` en la carpeta `scripts/`
2. Presiona **F8** para recargar los scripts modificados
3. Los errores aparecen en la consola del editor, sin crashear

```python
# scripts/mi_script.py
def on_reload():
    """Se ejecuta al recargar el módulo."""
    print("Script recargado!")
```

## ⚙️ Configuración Centralizada

Todas las constantes modificables están en `engine/config.py`:

```python
from engine.config import GRAVITY_DEFAULT, WINDOW_WIDTH, TARGET_FPS
```

## 🤖 Herramientas IA

### Crear Mecánica
```bash
py -3 tools/create_mechanic.py double_jump "Doble salto" Transform,RigidBody
```

### Inspeccionar Mundo
```python
from tools.introspect import inspect_world, inspect_entity
print(inspect_world(world))      # Resumen completo
print(inspect_entity(world, "Player"))  # Entidad específica
```

## 🔧 Dependencias

- Python 3.10+
- raylib-py

## 📝 Licencia

Proyecto académico - Universidad
