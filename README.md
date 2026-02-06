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

## 📁 Estructura del Proyecto

```
MotorVideojuegosIA/
├── engine/                 # Motor principal
│   ├── core/              # Game loop, estados, tiempo
│   │   ├── game.py        # Clase principal del motor
│   │   ├── engine_state.py # Estados EDIT/PLAY/PAUSED
│   │   └── time_manager.py
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
│   │   ├── scene.py       # Datos originales del nivel
│   │   └── scene_manager.py
│   │
│   ├── levels/            # Carga de niveles
│   │   ├── level_loader.py
│   │   └── component_registry.py
│   │
│   ├── inspector/         # Inspector visual
│   │   └── inspector_system.py
│   │
│   └── resources/         # Gestión de recursos
│       └── texture_manager.py
│
├── levels/                # Archivos de niveles JSON
│   └── demo_level.json
│
├── assets/                # Sprites y recursos
│   └── test_spritesheet.png
│
├── tools/                 # Herramientas auxiliares
│   └── generate_test_spritesheet.py
│
├── main.py               # Punto de entrada
├── requirements.txt
└── README.md
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

## 🔧 Dependencias

- Python 3.10+
- raylib-py

## 📝 Licencia

Proyecto académico - Universidad
