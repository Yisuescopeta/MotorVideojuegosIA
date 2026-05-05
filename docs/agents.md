# Guia para agentes IA

Esta guia resume como orientarse sin mezclar material historico con contratos
vigentes. Para reglas operativas completas, lee [../AGENTS.md](../AGENTS.md).

## Primeros 5 minutos

1. Ejecuta `py -m motor ai start --project . --json` para cargar el contrato
   compacto del proyecto.
2. Ejecuta `py -m motor ai compliance --project . --json` para detectar si el
   proyecto sigue el flujo nativo o tiene senales de runtime externo.
3. Lee [README.md](README.md) para ubicar canon, referencia, tooling y archivo.
4. Lee [../AGENTS.md](../AGENTS.md) antes de tocar archivos o elegir perimetro.
5. Usa [api.md](api.md) o [cli.md](cli.md) para flujos publicos.
6. Revisa [documentation_governance.md](documentation_governance.md) si el cambio
   crea, mueve o actualiza documentacion.

## Fuentes de verdad

Orden de autoridad:

1. Codigo y tests.
2. `EngineAPI` publica en `engine/api/`.
3. CLI oficial `motor` en `motor/cli.py`.
4. Docs canonicos en [README.md](README.md), [architecture.md](architecture.md),
   [TECHNICAL.md](TECHNICAL.md), [schema_serialization.md](schema_serialization.md),
   [module_taxonomy.md](module_taxonomy.md), [api.md](api.md) y [cli.md](cli.md).
5. Archivo historico en [archive/](archive/) solo como contexto.

No uses roadmaps, prompts antiguos, research ni capabilities `planned` como
prueba de funcionalidad actual.

## Invariantes que no debes romper

- `Scene` es la fuente persistente de verdad.
- `World` es una proyeccion operativa.
- Las mutaciones runtime no deben convertirse en authoring state por accidente.
- Cambios serializables compartidos deben pasar por `SceneManager` o `EngineAPI`.
- `EngineAPI` es la fachada publica para agentes, tests, CLI y automatizacion.
- `legacy_aabb` debe seguir funcionando como fallback fisico.
- Componentes publicos nuevos deben registrarse en `engine/levels/component_registry.py`.

## Como hacer cambios de authoring

Ruta recomendada:

```python
from engine.api import EngineAPI

api = EngineAPI(project_root=".")
try:
    api.load_scene("levels/main_scene.json")
    api.create_entity("Player", components={"Transform": {"x": 0, "y": 0}})
    api.add_component("Player", "Sprite", {"asset_path": "assets/player.png"})
    api.save_scene()
finally:
    api.shutdown()
```

## Agente nativo experimental

El repo incluye una base clean-room en `engine/agent/` para un agente de
asistencia integrado. Usalo como `experimental/tooling`, no como contrato core.
La v2 usa un runtime de turnos suspendibles: el provider puede pedir tools, cada
tool devuelve un `tool_result` emparejado y el runtime continua hasta respuesta
final, aprobacion pendiente, cancelacion o limite de iteraciones.

- Crea sesiones con `EngineAPI.create_agent_session`.
- Envia mensajes con `EngineAPI.send_agent_message`.
- Aprueba acciones pendientes con `EngineAPI.approve_agent_action`.
- Trata los `session_id` como opacos: el runtime solo acepta ids validados y
  no deben construirse como rutas.
- Una aprobacion o rechazo reanuda el mismo turno logico y vuelve al provider
  con el resultado de tool.
- Las mutaciones de escenas deben pasar por herramientas que usan `EngineAPI` o
  `AuthoringExecutionService`.
- No incluyas la carpeta local `Claude Code/` o `claude code/` como contexto
  del agente.
- El provider por defecto `fake` es determinista, offline y `test_only`; no debe
  presentarse como inteligencia real. `ReplayLLMProvider` cubre contratos
  multi-turn en tests. `OpenAIProvider` es el primer provider online real de V3a
  y acepta `OPENAI_API_KEY`, secreto local del agente o bridge desde auth
  gestionada por Codex/OpenAI. El estado `runtime_ready` indica si ese login
  gestionado expone una credencial reutilizable para el runtime actual; no hay
  fallback silencioso a fake.
- `run_command` no es una shell generica: acepta solo perfiles allowlist con
  `shell=False`. `full_access` autoaprueba acciones permitidas, pero no desactiva
  la policy de comandos ni los guards de `Claude Code/`, `.git`, `.motor`,
  rutas externas y secretos evidentes.
- `run_command` se ejecuta mediante `AgentCommandRunner`, con cwd confinado,
  entorno minimo, timeout, limite de output y auditoria.
- Streaming V3a se refleja como eventos `assistant_delta` y mensaje final
  persistido; si el provider no soporta streaming, se conserva el flujo no
  streaming.
- La memoria/compactacion guarda resumen local sanitizado y el coste queda
  `unknown` si no existen datos fiables de usage/precios.
- Las sesiones legacy se migran explicitamente con backup `.legacy-v1.bak` y
  evento `session_migrated`; una sesion corrupta se conserva sin sobrescribir.

Para CLI:

```bash
py -m motor ai start --project . --json
py -m motor ai compliance --project . --json
py -m motor ai self-test --project . --profile platformer --json
py -m motor doctor --project . --json
py -m motor recipe list --project . --json
py -m motor recipe show platformer-basic --project . --json
py -m motor recipe show platformer-advanced --project . --json
py -m motor recipe run platformer-basic --project . --json
py -m motor recipe run platformer-advanced --project . --json
py -m motor runtime step --project . --frames 300 --input "right,jump" --json
py -m motor game platformer create "Level 1" --project . --json
py -m motor game platformer add-player --x 100 --y 300 --project . --json
py -m motor game platformer add-ground --from-x 0 --to-x 20 --y 8 --project . --json
py -m motor game platformer add-platform --x 5 --y 6 --width 3 --project . --json
py -m motor game platformer add-coin --x 320 --y 200 --points 1 --project . --json
py -m motor game platformer add-hazard --x 640 --y 300 --damage 1 --project . --json
py -m motor game platformer add-goal --x 1100 --y 200 --project . --json
py -m motor game platformer add-respawn --x 100 --y 300 --id default --project . --json
py -m motor game platformer add-moving-platform --name Lift_A --x 320 --y 300 --width 96 --height 24 --to-x 640 --to-y 300 --speed 80 --project . --json
py -m motor game platformer add-enemy-patrol --name Slime_A --x 500 --y 480 --point 500,480 --point 700,480 --damage 1 --speed 60 --project . --json
py -m motor game platformer add-checkpoint --name Checkpoint_A --x 200 --y 420 --id cp_a --project . --json
py -m motor game platformer add-killzone --name Pit_A --x 640 --y 620 --width 1280 --height 64 --damage 1 --project . --json
py -m motor game platformer set-camera-follow --name MainCamera --target Player --project . --json
py -m motor game platformer set-bounds --name LevelBounds --left 0 --right 1600 --top 0 --bottom 720 --camera MainCamera --project . --json
py -m motor game platformer validate --project . --json
py -m motor scene create "Level 1" --project . --json
py -m motor entity create Player --project . --json
py -m motor entity list --project . --json
py -m motor entity delete Enemy_A --project . --json
py -m motor component add Player Transform --data '{"x":0,"y":0}' --project . --json
py -m motor component edit Player Transform x 200 --project . --json
py -m motor component remove Player Sprite --project . --json
```

Para construir plataformas sin tocar JSON, usa `motor game platformer create`
y luego los comandos incrementales `add-player`, `add-ground`, `add-platform`,
`add-coin`, `add-hazard`, `add-goal`, `add-respawn`, los comandos avanzados
`add-moving-platform`, `add-enemy-patrol`, `add-checkpoint`, `add-killzone`,
`set-camera-follow`, `set-bounds` y `validate`. Estos comandos
guardan la escena serializada y eligen escena por esta regla: activa cargada,
`editor_state.active_scene`, `startup_scene`, o primera escena cargable en
`levels/`; no usan `last_scene`.

`platformer create` ya deja una escena minima validable con `Player`, `Ground`,
`Goal` y `MainCamera`. En `add-ground`, `add-platform`, `add-coin`,
`add-hazard` y `add-goal`, `--name` hace idempotente la entidad indicada; sin
`--name`, se genera el siguiente nombre `*_###` disponible (`Goal` usa primero
`Goal` si falta). En los comandos avanzados, `--name` es obligatorio.

`MovingPlatform2D` debe tratarse como authoring/serializacion data-only con
runtime support minimo: mueve la entidad por su path y emite eventos durante
PLAY, y puede transportar al Player cuando esta apoyado encima mediante
Collider/AABB runtime. Los eventos de rider attach/move/detach quedan planned.
`EnemyPatrol2D` tiene runtime support semantico via `Gameplay2DSemanticSystem`: patrulla ciclica entre puntos,
emite `enemy_patrol_started`, `enemy_patrol_reached_point` y al contacto con
Player emite `enemy_touched` con daño y respawn (o `enemy_respawn_missing` si
no hay respawn). Si coexiste con `Hazard2D` en la misma entidad,
`EnemyPatrol2D` absorbe la interaccion para evitar duplicados. `Checkpoint2D`,
`KillZone2D` y `LevelBounds2D` tienen runtime support semantico via
`Gameplay2DSemanticSystem`: `Checkpoint2D` puede activar compatibilidad de
respawn de sesion con `RespawnPoint2D`, `KillZone2D` puede respawnear al
jugador desde el checkpoint activo o el primer `RespawnPoint2D` activo, y
`LevelBounds2D` puede emitir `level_bounds_exited`, clamp horizontal y
`level_bounds_respawn_missing`.

Para workflows comunes, usa recetas IA declarativas con `motor recipe`.
`platformer-basic` empaqueta el flujo minimo nativo de plataformas.
`platformer-advanced` crea una vertical slice con plataforma movil,
`EnemyPatrol2D`, `Checkpoint2D`, `KillZone2D`, `LevelBounds2D`, camara, goal,
validacion `platformer`, compliance estricto y `runtime step`. `recipe list` y
`recipe show` son read-only; `recipe run` ejecuta solo comandos oficiales
allowlist, sin shell, scripts temporales ni runtime externo, pero si muta el
`--project` objetivo porque los pasos de authoring guardan escena y estado.

Para autovalidacion completa de CI, usa
`py -m motor ai self-test --project . --profile platformer --json`. Por defecto
crea un proyecto temporal bajo `.motor/tmp`, ejecuta `platformer-basic`, reporta
comandos, validaciones, escena generada, eventos, cleanup y warnings, y elimina
el workspace temporal. Solo usa `--in-place` si quieres mutar el proyecto real.

Para verificacion runtime headless, usa `motor runtime play/step/stop`. Estos
comandos son stateless: inicializan `EngineAPI`, cargan una escena mediante
superficies publicas, ejecutan el control runtime y salen sin guardar mutaciones
runtime como authoring state. `motor runtime step --input "right,jump"` es la
via oficial para simular acciones `InputMap` (`left`, `right`, `up`, `down`,
`jump`, `action_1`, `action_2`) y leer `player_before`, `player_after` y
eventos runtime desde JSON. Los eventos semanticos 2D visibles incluyen
`collectible_collected`, `hazard_touched`, `goal_reached`,
`checkpoint_reached`, `killzone_touched`, `killzone_respawn_missing`,
`level_bounds_exited` y `level_bounds_respawn_missing`; respawns activados por
checkpoint y correcciones de bounds son estado runtime de sesion y no se
guardan en la escena serializada.

Con implementacion actual, `Gameplay2DSemanticSystem` deduplica `hazard` y
`goal` por par jugador/objetivo durante la misma sesion `PLAY`, asi que esos
eventos no re-emiten tras contactos repetidos hasta la siguiente invocacion.

`MovingPlatform2D` tiene soporte runtime minimo: durante PLAY mueve la entidad
por su path, emite `moving_platform_started`,
`moving_platform_reached_point` y `moving_platform_completed`, y no persiste
progreso runtime en la escena. Tambien transporta al Player cuando su
`Collider` esta apoyado encima del `Collider` de la plataforma antes del
movimiento del frame. Este soporte de riders es minimo, centrado en Player y
no define todavia eventos publicos `moving_platform_rider_attached`,
`moving_platform_rider_moved` ni `moving_platform_rider_detached`.

Para UI serializable usa los helpers publicos de `EngineAPI` como
`create_canvas`, `create_ui_text`, `create_ui_button` y `create_ui_image`.

## Recetas manuales seguras por genero

Cuando el genero pedido no tenga comando dedicado, compone con superficies ya
implementadas. No promociones estos flujos como recetas `motor recipe` nuevas:
son pasos manuales seguros para agentes.

- Top-down: crea escena con `motor scene create`, entidades con
  `motor entity create`, componentes con `motor component add` y ajustes con
  `motor component edit`. Verifica con `motor runtime play`,
  `motor runtime step` y `motor ai compliance`.
- Puzzle: modela piezas, puertas, interruptores y objetivos como entidades con
  componentes serializables. Usa `rules` y `RuleSystem` solo con acciones
  soportadas como `emit_event`, `set_position` y `spawn_entity`; no asumas
  solver, grid engine ni sistema de inventario si no existen en codigo.
- Main menu: usa `EngineAPI.create_canvas`, `EngineAPI.create_ui_text` y
  `EngineAPI.create_ui_button`. No existe CLI dedicada de menu principal; si
  necesitas authoring desde CLI, usa entidades/componentes basicos.

Anti-alucinacion: no uses `motor game topdown`, `motor game puzzle`,
`motor game shmup` ni `motor recipe run topdown`; esos comandos no son
contrato actual. No crees `run_game.py`. Si falta un helper especifico,
compone con `EngineAPI` o la CLI basica oficial.

Para gameplay runtime usa la fachada publica de `EngineAPI` en lugar de tocar
`Game`, `RuntimeController` o utilidades internas:

- señales runtime: `connect_signal`, `emit_signal`, `disconnect_signal`, `list_signal_connections`
- señales declarativas (persistencia): `add_signal_connection`, `remove_signal_connection`, `list_signal_connections_declarative`
- grupos: `get_entities_in_group`, `get_entity_groups`, `add_entity_to_group`, `remove_entity_from_group`, `call_group`, `emit_group`
- servicios globales: `get_service`, `has_service`, `register_service_runtime`, `register_service_builtin`

Cuando el motor esta en `EDIT`, los cambios persistentes de grupos deben entrar
por la ruta de authoring expuesta por `EngineAPI`; en `PLAY`, esos cambios solo
afectan al runtime activo.

## Física avanzada (P0)

La API de física expone fuerzas, impulsos, torque, capas de colisión y
monitoreo de overlaps vía Area2D. Todos los métodos usan la fachada pública
`EngineAPI`.

- `apply_force(entity, fx, fy)`: Aplica fuerza continua. Acelera el RigidBody cada frame.
- `apply_impulse(entity, ix, iy)`: Aplica impulso instantáneo. Cambio de velocidad inmediato.
- `apply_torque(entity, torque)`: Aplica torque angular al RigidBody.
- `set_collision_filter(entity, layer, mask)`: Configura capas de colisión con máscaras de bits (uint32). La regla de colisión es `(A.mask & B.layer) != 0 AND (B.mask & A.layer) != 0`.
- **Area2D**: monitorea overlaps con eventos `body_entered`/`body_exited`/`area_entered`/`area_exited`. Requiere un Collider. El payload de eventos incluye `entity_id`, `other_entity_id`, `entity_name` y `other_entity_name`.
- `CollisionFilter2D.should_collide(entity_a, entity_b)`: Verifica si dos entidades colisionan según sus filtros de capa/máscara.

### Ejemplo mínimo de física

```python
from engine.api import EngineAPI

api = EngineAPI(project_root=".")
api.load_scene("levels/main_scene.json")

# RigidBody dinámico con fuerzas
api.create_entity("player", components=["RigidBody", "Collider", "Transform"])
api.set_rigidbody_property("player", "body_type", "dynamic")
api.set_rigidbody_property("player", "mass", 2.0)
api.apply_force("player", 500.0, 0.0)
api.apply_impulse("player", 0.0, -300.0)

# Capas de colisión
api.set_collision_filter("player", layer=1, mask=1)

# Area2D para monitoreo
api.create_entity("damage_zone", components=["Area2D", "Collider", "Transform"])
api.set_collider_rect("damage_zone", 100, 100)
api.set_collider_trigger("damage_zone", True)

api.save_scene()
api.shutdown()
```

### Inyección automática de backend en CharacterControllerSystem

El `CharacterControllerSystem` recibe automáticamente el `PhysicsBackend` resuelto
cada frame desde `RuntimeController`. No es necesario que el agente configure nada:

- Con backend: usa `PhysicsBackend.move_and_slide()` (Box2D o legacy)
- Sin backend: fallback a código legacy AABB interno

El componente `CharacterController2D` determina el modo (`move_and_slide` vs
`move_and_collide`) y el backend lo respeta.

### RayCast2D — Raycast por componente

`RayCast2D` es un componente que lanza un rayo cada frame desde la entidad
usando internamente `query_physics_ray`. El sistema `RayCast2DSystem` está
wired en `EngineAPI` y `RuntimeController`, y se ejecuta automáticamente
durante `PLAY`.

Uso desde authoring:
```python
api.add_component("player", "RayCast2D", {"cast_to_y": 100})
```

Campos runtime actualizados cada frame: `is_colliding`, `collision_point_*`,
`collision_normal_*`, `collider_entity`.

### NavigationObstacle2D — Obstáculo estático para avoidance

Componente data-only que marca una entidad como obstáculo para
`NavigationAgentSystem`. Campos: `radius` (default: `0.0`),
`affect_avoidance` (default: `true`). No requiere configuración runtime.

```python
api.add_component("wall", "NavigationObstacle2D", {"radius": 16.0})
```

### Limitaciones de física para agentes IA

- `box2d` es backend opt-in. No usar a menos que esté explicitamente configurado.
- `supports_kinematic_move()` indica si el backend implementa movimiento kinematic real.
- `PhysicsKinematicMoveService` maneja el fallback automatico: si el backend no
  soporta kinematic move, usa el solver AABB legacy.
- Las shapes no-AABB (circle, capsule, polygon) tienen narrow-phase pero con
  precision variable en el manifold de contacto. Para fisica precisa, usar
  `box2d` como backend (requiere Box2D instalado).

## Que evitar

- No editar `SceneManager.edit_world` directamente para flujos publicos nuevos.
- No crear un runtime externo ni entregar `run_game.py` o un main loop alternativo
  como juego principal.
- Un import directo de `pyray`/`raylib` en scripts de comportamiento o helpers
  no implica por si solo runtime externo; strict bloquea launchers alternativos
  y loops propios fuera del flujo publico.
- Usa `py -m motor ai compliance --project . --strict --json` antes de entregar
  cuando el cambio pueda haber creado scripts ejecutables o flujo de juego.
- No asumir soporte de componentes no registrados.
- No documentar capacidades planificadas como implementadas.
- No ejecutar comandos listados como `planned` en `motor_ai.json` o
  `motor capabilities --json` si no existen en `motor/cli.py`.
- No reemplazar `motor` por `tools/engine_cli.py` en docs nuevas.
- No mover material desde `docs/archive/` a docs canonicas sin verificar codigo y tests.
- No tocar archivos congelados de [../AGENTS.md](../AGENTS.md) sin justificarlo.

## Documentos por necesidad

- Quiero entender el sistema: [architecture.md](architecture.md).
- Quiero entender terminos del repo: [glossary.md](glossary.md).
- Quiero entender la clasificación de subsistemas (qué es core y qué es experimental): [module_taxonomy.md](module_taxonomy.md).
- Quiero cambiar escenas/prefabs: [schema_serialization.md](schema_serialization.md).
- Quiero automatizar por Python: [api.md](api.md).
- Quiero automatizar por CLI: [cli.md](cli.md).
- Quiero entender `motor_ai.json`: [MOTOR_AI_JSON_CONTRACT.md](MOTOR_AI_JSON_CONTRACT.md).
- Quiero cambiar documentacion: [documentation_governance.md](documentation_governance.md).
- Quiero contexto historico: [archive/](archive/).

## Checks minimos antes de entregar docs o contratos

```bash
py -m unittest tests.test_repository_governance tests.test_motor_cli_contract tests.test_start_here_ai_coherence -v
py -m unittest tests.test_official_contract_regression tests.test_parser_registry_alignment tests.test_motor_interface_coherence tests.test_motor_registry_consistency -v
py -m motor --help
py -m motor ai start --project . --json
py -m motor ai compliance --project . --json
py -m motor doctor --project . --json
```

Declara solo los comandos que hayas ejecutado realmente.
