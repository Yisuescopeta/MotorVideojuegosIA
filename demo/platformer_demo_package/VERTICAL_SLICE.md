# Platformer Vertical Slice

Mini juego de plataformas 2D implementado como vertical slice del motor `MotorVideojuegosIA`.

## Objetivo

Validar las siguientes capacidades del motor:
- ✅ Tilemap authoring y runtime
- ✅ Animación 2D con estados (idle, run, jump)
- ✅ Audio runtime (SFX)
- ✅ Física/gameplay 2D básica
- ✅ Colisiones con triggers
- ✅ EventBus + Rules para gameplay
- ✅ Serialización de escenas
- ✅ EngineAPI

## Escena

**Archivo:** `levels/platformer_vertical_slice.json`

### Entidades

| Entidad | Propósito | Componentes Clave |
|---------|-----------|-------------------|
| `Player` | Personaje controlable | Transform, Collider, RigidBody, InputMap, PlayerController2D, Animator, AudioSource |
| `MainCamera` | Cámara que sigue al jugador | Transform, Camera2D |
| `LevelTilemap` | Nivel con suelo y plataformas | Transform, Tilemap |
| `Coin` | Coleccionable | Transform, Collider (trigger), Sprite |
| `Spikes` | Peligro | Transform, Collider (trigger), Sprite |
| `Goal` | Meta de victoria | Transform, Collider (trigger), Sprite |
| `AudioManager` | Gestión de audio | Transform, AudioSource |

### Controles

- **A / ←**: Mover izquierda
- **D / →**: Mover derecha
- **SPACE**: Saltar

### Gameplay

1. **Movimiento**: El jugador puede moverse lateralmente y saltar
2. **Coleccionable**: Recoge la moneda (Coin) para puntos
3. **Peligro**: Evita los pinchos (Spikes) o respawneas al inicio
4. **Victoria**: Llega a la meta (Goal) para completar el nivel

### Assets Utilizados

**Sprites:**
- `alienBlue_stand.png` - Jugador idle
- `alienBlue_walk1.png` / `alienBlue_walk2.png` - Jugador corriendo
- `alienBlue_jump.png` - Jugador saltando
- `coinGold.png` - Moneda coleccionable
- `spikes.png` - Peligro/pinchos
- `grassMid.png` - Tiles de suelo y plataformas

**Audio:**
- `jump.wav` - Sonido de salto
- `collect.wav` - Sonido de recolección
- `victory.wav` - Sonido de victoria
- `defeat.wav` - Sonido de daño

## Reglas del EventBus

Las siguientes reglas definen el comportamiento del juego:

1. **Coin Collection**: Cuando Player toca Coin → destruir Coin, log mensaje
2. **Hazard Hit**: Cuando Player toca Spikes → respawn Player al inicio, log mensaje
3. **Victory**: Cuando Player toca Goal → log mensaje, emitir evento "victory"

## Validación

### Tests Disponibles

Ejecutar los tests de validación:

```bash
python demo/platformer_demo_package/test_vertical_slice.py
```

### Tests del Motor

Verificar que no se rompieron tests existentes:

```bash
python -m unittest discover -s tests -v
```

### Cargar la Escena

```python
from engine.api import EngineAPI

api = EngineAPI()
api.load_level("levels/platformer_vertical_slice.json")
api.play()
```

## Arquitectura

### Decisiones Técnicas

1. **PlayerController2D vs CharacterController2D**: Se usó `PlayerController2D` porque está más integrado con el `AnimationSystem` y es más simple para este caso de uso.

2. **Tilemap para nivel**: En lugar de múltiples colliders sueltos, se usó un `Tilemap` con flags "solid" para el suelo y plataformas, demostrando el sistema de tilemaps del motor.

3. **Triggers para gameplay**: Los coleccionables, peligros y meta usan `Collider` con `is_trigger=true`, permitiendo detección sin bloqueo físico.

4. **Rules para lógica**: El gameplay (recolección, daño, victoria) se implementa mediante reglas del EventBus en lugar de scripts, mostrando el sistema declarativo del motor.

5. **Assets relativos**: Todas las rutas de assets usan rutas relativas desde la raíz del proyecto, apuntando a `demo/platformer_demo_package/assets/`.

## Limitaciones Conocidas

1. **Audio**: El motor debe tener el `AudioSystem` inicializado para reproducir sonidos. En modo headless, los AudioSource registran el intento pero no reproducen audio real.

2. **Animaciones**: El Animator usa `slice_names` para referenciar sprites individuales en lugar de una sprite sheet única, adaptándose a los assets disponibles.

3. **Renderizado**: El motor debe tener un backend gráfico configurado para visualizar los sprites y tilemaps.

4. **Física**: Usa el backend `legacy_aabb` por defecto, que es determinístico pero menos preciso que Box2D.

## Extensiones Futuras (Fuera del alcance base)

- Enemigos con patrullaje (usando navegación/pathfinding)
- Múltiples monedas y contador de puntuación
- Sistema de vidas
- Menú de pausa
- Transiciones entre niveles
- Partículas para efectos visuales
- Background scrolling

## Licencias de Assets

Los assets visuales son del **Kenney Platformer Pack** (CC0 - Dominio Público).
Los assets de audio son placeholders generados para el prototipo.

Ver `demo/platformer_demo_package/attribution_and_licenses.md` para detalles completos.
