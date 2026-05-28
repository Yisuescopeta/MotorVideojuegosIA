# CLI publica `motor`

Esta es la referencia canonica de la CLI publica actual. La implementacion vive
en `motor/cli.py` y las funciones de comando en `motor/cli_core.py`.

## Puntos de entrada

```bash
motor <command> [options]
py -m motor <command> [options]
```

Si el paquete no esta instalado en modo editable, usa `py -m motor`.

`tools/engine_cli.py` queda como compatibilidad legacy para scripts antiguos. No
es la interfaz publica para automatizacion nueva ni para documentacion canonica.

## Gramática

La CLI sigue esta forma:

```text
motor <noun> [<subnoun>] <verb> [<args>] [options]
```

Convenciones:

- `--project` apunta al root del proyecto y por defecto vale `.`.
- `--json` emite respuestas con `{ "success": bool, "message": str, "data": object }`.
- Los comandos que editan escenas pueden autocargar la ultima escena activa
  desde el estado de editor cuando no hay una escena ya cargada.
- `doctor` es de solo lectura y no genera `motor_ai.json` ni `START_HERE_AI.md`.

## Export/build

Los comandos de exportacion usan `EngineAPI`; la CLI no duplica logica de
presets, validacion, empaquetado ni exporters.

```bash
py -m motor export presets list --project . --json
py -m motor export presets validate --project . --json
py -m motor export doctor --project . --json
py -m motor export pack "Windows Desktop" --project . --json
py -m motor export build "Windows Desktop" --project . --json
py -m motor export build "Android Debug" --project . --json
py -m motor export build-all --project . --json
```

Salida JSON: `{ "success": bool, "message": str, "data": object }`.
`export pack` genera `.motor/build/staging/<preset>/game.manifest.json` y
`game.pak`. `export build` genera report en `.motor/build/export_reports/`.
Si falta toolchain externo, el comando falla con `TOOLCHAIN_UNAVAILABLE` y
mantiene artefactos estructurales posibles, como proyecto Android generado.

Documentacion relacionada: [export_pipeline.md](export_pipeline.md),
[export_presets.md](export_presets.md), [troubleshooting_export.md](troubleshooting_export.md).

## Mobile

```bash
py -m motor mobile controls add --target Player --profile platformer --project . --json
py -m motor mobile controls add --scene levels/platformer_test_scene.json --target Player --profile platformer --project . --json
```

El comando agrega un overlay `MobileControls2D` serializable a la escena activa.
Usa `--scene` para preparar una escena concreta sin depender de la ultima escena
activa del editor. Por defecto no duplica overlays existentes; usa `--replace`
para regenerarlo. El runtime traduce el control tactil a acciones `InputMap`
antes de `PlayerController2D`.

## Comandos de introspeccion

### `motor ai start`

Entrada compacta recomendada para agentes IA. Es de solo lectura y resume el
contrato operativo del proyecto.

```bash
py -m motor ai start --project . --json
```

El JSON usa la envoltura estandar `{ "success": bool, "message": str, "data": object }`.
`data` incluye:

- `engine`: nombre y version de MotorVideojuegosIA.
- `recommended_cli`: `motor`.
- `recommended_api`: `EngineAPI`.
- `scene_context`: escena activa desde estado de editor si existe, ultima escena,
  escenas abiertas y escenas detectadas.
- `initial_commands`: comandos iniciales recomendados para orientacion.
- `recommended_workflows`: workflows compactos derivados del capability registry.
- `rules`: prohibe crear runtime externo y entregar `run_game.py` o main loop
  alternativo como juego principal.
- `validation`: apunta a `motor ai compliance --project . --strict --json` con
  `status = "implemented"`.

### `motor ai compliance`

Diagnostico read-only para validar si un proyecto usa MotorVideojuegosIA de
forma nativa y detectar senales de runtimes externos priorizados por IA.

```bash
py -m motor ai compliance --project . --json
py -m motor ai compliance --project . --strict --json
```

El JSON usa la envoltura estandar `{ "success": bool, "message": str, "data": object }`.
`data` incluye:

- `success`: indica si el diagnostico completo paso para el modo usado.
- `native_score`: puntuacion determinista de 0 a 100.
- `strict_pass`: `false` si strict detecta runtime externo o no hay escena nativa valida.
- `external_runtime_detected`: `true` si encuentra senales sospechosas.
- `problems`: fallos de contrato o strict.
- `warnings`: bootstrap faltante/regenerable, componentes desconocidos, sospechas
  en modo normal y loops propios en scripts referenciados por `ScriptBehaviour`.
- `recommended_next_actions`: acciones concretas para volver al flujo nativo.

Checks principales:

- `project.json` inicializable.
- `motor_ai.json` y `START_HERE_AI.md` presentes o regenerables.
- escenas detectables y escena activa/startup/fallback cargable.
- schema de escena soportado, entidades serializadas y componentes como fuente persistente.
- componentes registrados o warnings por componentes desconocidos.
- posibles runtimes externos como `run_game.py`, loops propios de ventana/render,
  `.bat` que lancen demos o runtime alternativo, o scripts que usen
  `main.py`/`HeadlessGame` como camino final sin `motor`/`EngineAPI`.

Modo normal reporta sospechas como warnings. Modo `--strict` falla ante runtime
externo sospechoso o ausencia de escena nativa valida. Puede haber falsos
positivos en scripts auxiliares o demos antiguas fuera de `docs/`. La
documentacion, incluido el material historico en `docs/archive/`, no forma
parte del escaneo de runtimes externos. El comando no borra ni edita archivos
sospechosos.

Reglas adicionales del escaneo strict:

- `run_game.py` en la raiz del proyecto evaluado sigue bloqueando strict.
- un script que solo importa `pyray`/`raylib` no bloquea por si mismo; debe
  aparecer como launcher alternativo o poseer su propio loop de ventana/render.
- al evaluar este repo del motor, `main.py` en raiz se permite como launcher
  oficial de compatibilidad del repositorio.
- al evaluar este repo del motor, proyectos anidados bajo `projects/` con su
  propio `project.json` se tratan como roots separados y no bloquean el
  compliance del repo principal.
- strict bloquea si un `ScriptBehaviour` de la escena activa referencia un script
  con loops propios como `while True`, porque representa un mini motor paralelo
  que esquiva el runtime oficial.

### `motor ai self-test`

Autovalidacion IA pensada para CI. Por defecto crea un proyecto temporal bajo
`.motor/tmp`, ejecuta el perfil solicitado, valida resultados y elimina el
workspace temporal al terminar.

```bash
py -m motor ai self-test --project . --profile platformer --json
py -m motor ai self-test --project . --profile platformer --in-place --json
```

En v1 solo existe `--profile platformer`, que ejecuta la receta
`platformer-basic`: crea plataforma nativa, valida `platformer`, corre runtime
headless y ejecuta `ai compliance --strict`. Tambien existe
`platformer-advanced` para crear una vertical slice nativa con plataforma movil,
enemy patrol, checkpoint, killzone, bounds, camara y goal. El modo normal no
modifica el proyecto real; `--in-place` ejecuta el flujo contra `--project` y
puede mutar escenas, `editor_state` y `startup_scene` del proyecto real.

El JSON usa la envoltura estandar `{ "success": bool, "message": str, "data": object }`.
`data` incluye:

- `success`: resultado agregado del self-test.
- `profile`: perfil ejecutado.
- `commands_executed`: comandos oficiales ejecutados por la receta.
- `validations`: validaciones de platformer, runtime y compliance.
- `generated_scene`: escena generada antes del cleanup.
- `events`: eventos runtime capturados.
- `cleanup_status`: modo, workspace temporal y estado de borrado.
- `warnings`: avisos agregados.

Antes de mutar nada, el comando comprueba que las capacidades esperadas por la
receta existen y estan `implemented`; si falta alguna, falla con
`missing_capabilities`.

### `motor capabilities`

Lista el registry de capacidades del motor.

```bash
py -m motor capabilities
py -m motor capabilities --json
```

El JSON incluye `count`, `engine_version`, `capabilities_schema_version` y una
lista de capacidades con `id`, `summary`, `mode`, `status`, `api_methods`,
`cli_command` y `tags`.

### `motor doctor`

Diagnostica salud del proyecto sin escribir archivos.

```bash
py -m motor doctor --project . --json
```

Valida `project.json`, `motor_ai.json`, `START_HERE_AI.md`, carpetas esperadas,
inicializacion del motor, listado de escenas/assets y consistencia del registry
de capacidades. Si faltan los archivos AI bootstrap, recomienda ejecutar
`motor project bootstrap-ai --project .`.

## Proyecto

### `motor project info`

Muestra informacion del proyecto, estado de editor y proyectos recientes.

```bash
py -m motor project info --project . --json
```

### `motor project bootstrap-ai`

Genera o regenera los artefactos orientados a IA del proyecto:

- `motor_ai.json`
- `START_HERE_AI.md`

```bash
py -m motor project bootstrap-ai --project . --json
```

El formato actual de `motor_ai.json` es `schema_version = 3`; ver
[MOTOR_AI_JSON_CONTRACT.md](MOTOR_AI_JSON_CONTRACT.md).

## Editor

### `motor editor theme list|active|set|export|import`

Gestiona temas del editor desde `EngineAPI`. El tema activo se guarda en
`.motor/editor_state.json -> preferences.editor_theme`; no se serializa en
escenas.

```bash
py -m motor editor theme list --project . --json
py -m motor editor theme active --project . --json
py -m motor editor theme set unity_dark --project . --json
py -m motor editor theme export theme.json --name unity_dark --project . --json
py -m motor editor theme import theme.json --project . --json
```

`export` escribe JSON de tema. `import` registra el tema y lo activa por defecto;
usa `--no-activate` para solo registrarlo en el proceso actual.

### `motor editor feature-flags list|set`

Gestiona flags de migracion del editor. Los defaults son `false` y los valores
persistidos viven en `.motor/editor_state.json -> preferences.editor_feature_flags`.
Variables de entorno como `MOTOR_EDITOR_CONTROL_CONSOLE` pueden sobrescribir el
valor persistido durante el proceso actual.

```bash
py -m motor editor feature-flags list --project . --json
py -m motor editor feature-flags set console_panel true --project . --json
```

El payload JSON incluye `schema_version`, `flags`, `env_overrides` y
`preference_key`.

## Recetas IA

Las recetas IA son workflows declarativos versionados empaquetados con el
motor. No cargan recetas arbitrarias desde el proyecto. `list` y `show` son
read-only; `run` ejecuta solo comandos `motor` allowlist en el proceso actual,
sin shell, scripts temporales ni runtime externo.

### `motor recipe list`

Lista recetas disponibles.

```bash
py -m motor recipe list --project . --json
```

### `motor recipe show <id>`

Muestra la receta completa, incluyendo `steps`, `expected_capabilities` y
`validation_commands`, sin mutar archivos del proyecto.

```bash
py -m motor recipe show platformer-basic --project . --json
py -m motor recipe show platformer-advanced --project . --json
```

### `motor recipe run <id>`

Ejecuta una receta declarativa por pasos allowlist. `platformer-basic` crea un
nivel minimo de plataformas, agrega moneda, hazard y respawn, valida
`platformer`, ejecuta `ai compliance --strict`, y hace comprobaciones runtime
headless con `runtime step` y `runtime events`. `platformer-advanced` crea una
vertical slice nativa con player, ground, plataforma fija, coin, hazard,
respawn, checkpoint, killzone, moving platform, enemy patrol, bounds, camera
follow, goal, `platformer validate`, `ai compliance --strict` y `runtime step`
con input minimo.

```bash
py -m motor recipe run platformer-basic --project . --json
py -m motor recipe run platformer-advanced --project . --json
```

No usa shell arbitrario ni scripts temporales, pero si muta el `--project`
objetivo porque los pasos de authoring guardan escena y estado del proyecto.

El JSON devuelve `recipe`, `recipe_id`, `version`, `steps`,
`commands_executed`, `generated_scene`, `validations`, `warnings`, `events`,
`first_failure`, `expected_capabilities` y `validation_commands`.

## Game

### `motor game platformer create <name>`

Crea una escena nativa mínima de plataformas 2D bajo `levels/`, la deja activa
y actualiza `settings/project_settings.json -> startup_scene` al nuevo nivel.

```bash
py -m motor game platformer create "Level 1" --project . --json
```

La escena creada usa solo componentes/escenas nativas del motor y no crea
`run_game.py`, loops externos ni scripts auxiliares. Estructura mínima:

- `Player` con `Transform`, `Collider`, `RigidBody`, `InputMap`,
  `PlayerController2D`
- `MainCamera` con `Transform` y `Camera2D` siguiendo a `Player`
- `Ground` con `Transform` y `Collider`
- `Goal` con `Transform`, `Collider` trigger y `Goal2D`

El JSON devuelve `scene_name`, `scene_path`, `startup_scene`,
`entities_created`, `entity_count` y `scene_file`.

### `motor game platformer add-player`

Crea o actualiza `Player` en la escena de plataformas seleccionada:

```bash
py -m motor game platformer add-player --x 100 --y 300 --project . --json
```

### `motor game platformer add-ground`

Crea suelo usando celdas de 64 px. `--from-x` es inclusivo y `--to-x` es
exclusivo; `--from-x 0 --to-x 20 --y 8` genera un suelo de `20 * 64` px
centrado en `x=640`, `y=512`. Sin `--name`, crea el siguiente `Ground_###`;
con `--name`, crea o actualiza esa entidad.

```bash
py -m motor game platformer add-ground --from-x 0 --to-x 20 --y 8 --project . --json
```

### `motor game platformer add-platform`

Crea plataforma usando celdas de 64 px. `--x` es la celda inicial izquierda y
`--width` mide celdas. Sin `--name`, crea `Platform_001`, `Platform_002`, etc.;
con `--name`, crea o actualiza esa entidad.

```bash
py -m motor game platformer add-platform --x 5 --y 6 --width 3 --project . --json
```

### `motor game platformer add-coin`

Crea moneda con `Transform`, `Collider` trigger y `Collectible2D`. Sin
`--name`, crea `Coin_001`, `Coin_002`, etc.; con `--name`, crea o actualiza esa
entidad.

```bash
py -m motor game platformer add-coin --x 320 --y 200 --points 1 --project . --json
```

### `motor game platformer add-hazard`

Crea hazard con `Transform`, `Collider` trigger y `Hazard2D`. Sin `--name`, crea
`Hazard_001`, `Hazard_002`, etc.; con `--name`, crea o actualiza esa entidad.

```bash
py -m motor game platformer add-hazard --x 640 --y 300 --damage 1 --project . --json
```

### `motor game platformer add-goal`

Crea goal con `Transform`, `Collider` trigger y `Goal2D`, sin referencias a
assets concretos. Sin `--name`, crea `Goal` si falta; si ya existe, crea
`Goal_001`, `Goal_002`, etc. Con `--name`, crea o actualiza esa entidad.

```bash
py -m motor game platformer add-goal --x 1100 --y 200 --project . --json
```

### `motor game platformer add-respawn`

Crea o actualiza `Respawn_<id>` con `Transform` y `RespawnPoint2D`.

```bash
py -m motor game platformer add-respawn --x 100 --y 300 --id default --project . --json
```

### `motor game platformer add-moving-platform`

Crea o actualiza una entidad con nombre obligatorio usando `Transform`,
`Collider` y `MovingPlatform2D`. En runtime, la plataforma se mueve por su
path y emite eventos de movimiento sin persistir esos cambios en la escena.
Tambien puede transportar al Player cuando su `Collider` esta apoyado encima
del `Collider` de la plataforma. Este soporte de riders es minimo, centrado en
Player; los eventos `moving_platform_rider_attached`,
`moving_platform_rider_moved` y `moving_platform_rider_detached` quedan planned.

Es authoring/serializacion data-only. Este comando no promete movimiento
runtime por si mismo.

```bash
py -m motor game platformer add-moving-platform --name Lift_A --x 320 --y 300 --width 96 --height 24 --to-x 640 --to-y 300 --speed 80 --project . --json
```

### `motor game platformer add-enemy-patrol`

Crea o actualiza una entidad con nombre obligatorio usando `Transform`,
`Collider` trigger y `EnemyPatrol2D`. Cada `--point` usa formato `x,y` en
pixeles y puede repetirse.

Es authoring/serializacion con runtime basico de patrulla: durante PLAY la
entidad se mueve entre los puntos indicados, emite `enemy_patrol_started` y
`enemy_patrol_reached_point`, y al contactar con Player emite `enemy_touched`
con daño y respawn. No promete IA compleja.

```bash
py -m motor game platformer add-enemy-patrol --name Slime_A --x 500 --y 480 --point 500,480 --point 700,480 --damage 1 --speed 60 --project . --json
```

### `motor game platformer add-checkpoint`

Crea o actualiza una entidad con nombre obligatorio usando `Transform`,
`Collider` trigger, `Checkpoint2D` y `RespawnPoint2D` con el mismo id.

Checkpoint2D ya tiene runtime support semantico: puede emitir
`checkpoint_reached` y activar respawn de sesion via `RespawnPoint2D` sin
guardar mutaciones runtime como authoring.

```bash
py -m motor game platformer add-checkpoint --name Checkpoint_A --x 200 --y 420 --id cp_a --project . --json
```

### `motor game platformer add-killzone`

Crea o actualiza una entidad con nombre obligatorio usando `Transform`,
`Collider` trigger y `KillZone2D`.

KillZone2D ya tiene runtime support semantico: puede emitir `killzone_touched`
y respawnear al jugador desde el checkpoint activo o el primer
`RespawnPoint2D` activo, sin guardar mutaciones runtime como authoring.

```bash
py -m motor game platformer add-killzone --name Pit_A --x 640 --y 620 --width 1280 --height 64 --damage 1 --project . --json
```

### `motor game platformer set-camera-follow`

Crea o actualiza una entidad `Camera2D` con seguimiento nativo mediante
`follow_entity`, offsets, dead zone y zoom. No introduce componente de camara
nuevo.

```bash
py -m motor game platformer set-camera-follow --name MainCamera --target Player --offset-x 0 --offset-y 0 --dead-zone-width 120 --dead-zone-height 80 --zoom 1 --project . --json
```

### `motor game platformer set-bounds`

Crea o actualiza una entidad con `LevelBounds2D`. Si se pasa `--camera`, tambien
sincroniza `Camera2D.clamp_left/right/top/bottom` en esa camara.

En runtime headless, `LevelBounds2D` emite `level_bounds_exited`, clampa
salidas horizontales del `Player` y usa respawn para salidas por `bottom` sin
guardar mutaciones como authoring.

```bash
py -m motor game platformer set-bounds --name LevelBounds --left 0 --right 1600 --top 0 --bottom 720 --camera MainCamera --project . --json
```

### `motor game platformer validate`

Valida escena, `Player`, suelo/plataforma, `Goal` semantico, carga de escena y
compliance estricto sin runtime externo bloqueante. El JSON separa
`platformer_validation` de `strict_compliance`; `success` requiere ambas. Si
existen componentes semanticos o de authoring avanzado, los reporta en
`semantic_entities`: `collectibles`, `hazards`, `goals`, `respawns`,
`moving_platforms`, `enemy_patrols`, `checkpoints`, `killzones`, `bounds` y
`cameras`.

```bash
py -m motor game platformer validate --project . --json
```

Los comandos incrementales operan sobre esta regla: escena activa ya cargada,
si existe; si no, `.motor/editor_state.json -> active_scene`; si no,
`settings/project_settings.json -> startup_scene`; si no, primera escena
cargable bajo `levels/` ordenada por ruta. No usan `last_scene`.

Cada comando devuelve el envelope JSON oficial con `success`, `message` y
`data`. En `data` siempre se incluyen `scene_path`, `entities_created` y
`warnings`; `validate` agrega `validation`. Los comandos avanzados requieren
`--name` para authoring idempotente.

## Escenas

### `motor scene list`

Lista escenas detectadas en el proyecto.

```bash
py -m motor scene list --project . --json
```

### `motor scene create <name>`

Crea una escena y la deja como escena activa.

```bash
py -m motor scene create "Level 1" --project . --json
```

### `motor scene load <path>`

Carga una escena desde ruta de proyecto.

```bash
py -m motor scene load levels/main_scene.json --project . --json
```

### `motor scene save`

Guarda la escena activa en su ruta fuente.

```bash
py -m motor scene save --project . --json
```

### `motor scene flow next`

Carga la siguiente escena en el flujo de escenas definido por `SceneLink`.

```bash
py -m motor scene flow next --project . --json
```

### `motor scene flow menu`

Carga la escena de menu definida en el flujo de escenas.

```bash
py -m motor scene flow menu --project . --json
```

### `motor scene flow set-link <source> <target>`

Establece un enlace de flujo entre dos escenas. `--entity` opcional para
vincular a una entidad con `SceneLink`.

```bash
py -m motor scene flow set-link levels/level1.json levels/level2.json --project . --json
py -m motor scene flow set-link levels/level1.json levels/menu.json --entity Doorway --project . --json
```

## Runtime headless

Los comandos `runtime` usan la fachada publica `EngineAPI` dentro del proceso
CLI actual. Son stateless: no comparten una sesion viva entre invocaciones y no
guardan mutaciones runtime como estado de authoring.

Si el proceso no tiene escena activa, intentan cargar una escena para
inspeccion runtime desde estado de editor, `startup_scene` o la primera escena
detectada. El JSON incluye `warnings` cuando ocurre este fallback.

### `motor runtime play`

Inicializa el runtime headless, carga una escena, ejecuta `EngineAPI.play()`,
reporta estado y limpia con `EngineAPI.stop()` antes de salir.

```bash
py -m motor runtime play --project . --headless --json
```

### `motor runtime step`

Ejecuta la validacion headless completa en un solo proceso:
`PLAY -> STEP(frames) -> STOP`.

```bash
py -m motor runtime step --project . --frames 300 --json
py -m motor runtime step --project . --frames 300 --input "right,jump" --json
```

`--input` simula acciones `InputMap` durante todos los frames solicitados.
Tokens soportados: `left`, `right`, `up`, `down`, `jump`, `action_1`,
`action_2`. `jump` equivale a `action_1`; ejes opuestos se cancelan y se
reportan en `warnings`.

Los eventos semanticos observados aqui dependen de una sesion `PLAY` stateless
por invocacion. Con implementacion actual, `hazard` y `goal` se deduplican por
par jugador/objetivo dentro de esa sesion y no re-emiten tras contactos
repetidos hasta el siguiente `PLAY`.

El JSON incluye `frames_requested`, `frames_simulated`, `input_sequence`,
`player_before`, `player_after`, `events`, `status_before`,
`status_after_play`, `status_after_step`, `status_after`, `scene_path` y
`scene`. En escenas de plataformas, `events` puede incluir eventos semanticos
2D como `checkpoint_reached`, `killzone_touched`, `killzone_respawn_missing`,
`level_bounds_exited` y `level_bounds_respawn_missing`; los respawns activados
por checkpoint y las correcciones runtime de bounds no se guardan como
authoring.

### `motor runtime stop`

Llama `EngineAPI.stop()` en el proceso actual. Como la CLI es stateless, no
puede detener una sesion `PLAY` iniciada por una invocacion anterior y lo
declara en `warnings`.

```bash
py -m motor runtime stop --project . --json
```

### `motor runtime status`

Devuelve el estado actual del runtime y la informacion de la escena activa.
Es de solo lectura y no modifica el estado de authoring.

```bash
py -m motor runtime status --project . --json
```

El JSON incluye:

- `status`: estado del runtime (`state`, `frame`, `time`, `fps`, `entity_count`).
- `scene`: metadatos de la escena activa (o advertencia si se uso fallback).
- `warnings`: lista de advertencias, por ejemplo si se cargo una escena fallback.

### `motor runtime entities`

Lista las entidades de la escena activa. Es de solo lectura.

```bash
py -m motor runtime entities --project . --json
py -m motor runtime entities --project . --tag Player --active-only --json
```

Opciones:

- `--tag`: filtra por tag.
- `--layer`: filtra por layer.
- `--active-only`: muestra solo entidades activas.

El JSON incluye `entities` (lista de `EntityData`) y `count`.

### `motor runtime inspect <entity>`

Devuelve los datos completos de una entidad concreta. Es de solo lectura.

```bash
py -m motor runtime inspect Player --project . --json
```

El JSON incluye `entity` con `name`, `active`, `tag`, `layer`, `parent`,
`components` y `component_metadata`.

### `motor runtime events`

Devuelve los eventos recientes del bus de eventos del runtime. Es de solo
lectura.

```bash
py -m motor runtime events --project . --json
py -m motor runtime events --project . --count 10 --json
py -m motor runtime events --project . --step-frames 1 --json
```

Opciones:

- `--count`: numero de eventos a recuperar (por defecto: 50).
- `--step-frames`: si es mayor que `0`, ejecuta `PLAY -> STEP(N)` en el
  mismo proceso stateless antes de leer eventos. No guarda mutaciones runtime
  como estado de authoring.

Con implementacion actual, los eventos semanticos `hazard` y `goal` se
deduplican por par jugador/objetivo dentro de esa invocacion stateless.

Si no hay eventos disponibles, devuelve una lista vacia y una advertencia.
El JSON incluye `events` y `count`. Con `--step-frames`, los eventos
semanticos 2D observables incluyen `checkpoint_reached`, `killzone_touched` y
`killzone_respawn_missing` cuando hay contactos entre `Player` y esos
componentes.

### `motor runtime undo`

Deshace la ultima accion de authoring. Usa `EngineAPI.undo()` internamente.

```bash
py -m motor runtime undo --project . --json
```

### `motor runtime redo`

Rehace la ultima accion deshecha. Usa `EngineAPI.redo()` internamente.

```bash
py -m motor runtime redo --project . --json
```

## Física

Los comandos `motor physics` consultan el backend físico del runtime.
Son read-only y stateless: no mutan la escena ni el estado de authoring.
Usan `EngineAPI` y el `PhysicsBackend` activo (por defecto `legacy_aabb`).
Si no hay escena activa en el proceso CLI, cargan una escena fallback solo
para la consulta runtime y lo reportan en `warnings`.

### `motor physics backend list`

Lista los backends físicos disponibles y cuál está activo.

```bash
py -m motor physics backend list --project . --json
```

El JSON incluye:
- `backends`: lista con `name`, `available` y `unavailable_reason` por backend.
- `active_backend`: nombre del backend activo.
- `selection`: `requested_backend`, `effective_backend`, `used_fallback` y `fallback_reason`.
- `count`: total de backends listados.

### `motor physics query aabb`

Consulta colisionadores que solapan un AABB (axis-aligned bounding box).
Retorna las entidades cuyos colliders intersectan el rectángulo dado.

```bash
py -m motor physics query aabb 0 0 640 480 --project . --json
```

Parámetros posicionales: `left`, `top`, `right`, `bottom`.

El JSON incluye:
- `query`: AABB consultado (`left`, `top`, `right`, `bottom`).
- `hits`: lista de colisionadores encontrados. Cada hit incluye `entity_id`, `entity_name` y `position`.
- `count`: número de hits.
- `status_after`: estado del runtime tras la consulta (`state`, `frame`, `time`, `fps`, `entity_count`).

### `motor physics query ray`

Lanza un rayo y retorna el primer colisionador intersectado (o ninguno).

```bash
py -m motor physics query ray 0 0 1 0 --project . --json
py -m motor physics query ray 100 200 0 1 --max-distance 500 --project . --json
```

Parámetros posicionales: `origin_x`, `origin_y`, `direction_x`, `direction_y`.
Opciones: `--max-distance` (default: 1000).

El JSON incluye:
- `query`: rayo lanzado (`origin_x`, `origin_y`, `direction_x`, `direction_y`, `max_distance`).
- `hits`: lista con el primer hit (si existe). Cada hit incluye `entity_id`, `entity_name`, `position`, `normal` y `distance`.
- `count`: 0 o 1.
- `status_after`: estado del runtime tras la consulta.

### `motor physics query shape-cast`

Barre una forma a través del mundo físico y retorna los colisionadores impactados
en orden de primer contacto.

```bash
py -m motor physics query shape-cast box 16 16 0 0 1 0 --max-distance 200 --project . --json
py -m motor physics query shape-cast circle 10 10 100 100 0 1 --project . --json
```

Parámetros posicionales: `shape_type`, `shape_width`, `shape_height`, `origin_x`, `origin_y`, `direction_x`, `direction_y`.
Tipos de forma: `box`, `circle`, `capsule`, `polygon`.
Opciones: `--max-distance` (default: 1000).

El JSON incluye:
- `query`: parámetros del cast (`shape_type`, `shape_width`, `shape_height`, `origin_*`, `direction_*`, `max_distance`).
- `hits`: lista de hits ordenados. Cada hit incluye `entity_id`, `entity_name`, `position`, `normal`, `fraction` y `distance`.
- `count`: número de hits.

### `motor physics query motion`

Prueba si una entidad puede moverse a lo largo de un vector sin colisionar.
**No muta** el `Transform` ni el estado del mundo. Útil para predicción de
movimiento y validación de trayectorias.

```bash
py -m motor physics query motion Player 100 0 --project . --json
py -m motor physics query motion Enemy_A 0 -50 --margin 0.1 --exclude-names Ground --project . --json
```

Parámetros posicionales: `entity_name`, `motion_x`, `motion_y`.
Opciones:
- `--margin`: margen de seguridad (default: 0.08).
- `--recovery-as-collision`: reporta overlaps preexistentes como colisiones.
- `--exclude-names`: nombres de entidades a excluir (separados por coma).
- `--collision-mask`: máscara de bits para filtrado de capas (hex válido).
- `--collide-with-areas`: incluye entidades area/trigger en la prueba.

El JSON incluye:
- `query`: parámetros de la prueba (`entity_name`, `motion_x`, `motion_y`, `margin`, `recovery_as_collision`, `exclude_names`, `collision_mask`, `collide_with_areas`).
- `result`: dict con `travel_x`, `travel_y`, `remainder_x`, `remainder_y`, `collision_point_*`, `collision_normal_*`, `collision_depth`, `collision_safe_fraction`, `collision_unsafe_fraction`, `collider_entity_name` y campos del colisionador impactado.
- `has_collision`: bool que indica si hubo colisión.
- `status_after`: estado del runtime tras la consulta.

## Entidades

### `motor entity create <name>`

Crea una entidad en la escena activa. Puede recibir componentes iniciales como
JSON.

```bash
py -m motor entity create Player --project . --json
py -m motor entity create Player --components '{"Transform":{"x":100,"y":200}}' --project . --json
```

El comando guarda automaticamente la escena despues de crear la entidad.

### `motor entity list`

Lista entidades de la escena activa, con filtros opcionales.

```bash
py -m motor entity list --project . --json
py -m motor entity list --tag Enemy --active-only --project . --json
```

El JSON incluye `entities`, `count`, `filters` y metadatos de `scene`.

### `motor entity delete <name>`

Elimina una entidad de la escena activa usando `EngineAPI.delete_entity` y
guarda la escena. Los hijos siguen la semantica de jerarquia existente:
se reasignan al padre de la entidad eliminada y conservan transformacion de
mundo cuando hay `Transform`.

```bash
py -m motor entity delete Enemy_A --project . --json
```

### `motor entity set-parent <entity> <parent>`

Asigna un padre a una entidad existente, estableciendo jerarquia.

```bash
py -m motor entity set-parent Sword Player --project . --json
```

### `motor entity create-child <parent>`

Crea una entidad hija bajo un padre existente. `--name` es obligatorio.

```bash
py -m motor entity create-child Player --name Sword --project . --json
```

## Componentes

### `motor component add`

Agrega un componente a una entidad con datos iniciales opcionales.

```bash
py -m motor component add Player Transform --data '{"x":0,"y":0}' --project . --json
```

### `motor component edit`

Edita una propiedad de un componente. Usa `--raw` para valores literales sin parseo JSON.

```bash
py -m motor component edit Player Transform x 200 --project . --json
```

### `motor component remove`

Elimina un componente de una entidad.

```bash
py -m motor component remove Player Sprite --project . --json
```

## Animator

### `motor animator info`

Muestra la configuracion del Animator de una entidad.

```bash
py -m motor animator info Player --project . --json
```

### `motor animator set-sheet`

Asigna un sprite sheet al Animator de una entidad.

```bash
py -m motor animator set-sheet Player assets/player.png --project . --json
```

### `motor animator ensure`

Asegura que el componente Animator existe. Si se pasa `--sheet`, actualiza el sprite sheet.

```bash
py -m motor animator ensure Player --sheet assets/player.png --project . --json
```

### `motor animator state create`

Crea o actualiza un estado de animacion con slices, fps y opciones de loop/default.

```bash
py -m motor animator state create Player idle --slices idle_1,idle_2,idle_3 --fps 8 --loop --set-default --project . --json
```

### `motor animator state remove`

Elimina un estado de animacion.

```bash
py -m motor animator state remove Player idle --project . --json
```

## Validacion recomendada

```bash
py -m motor --help
py -m motor doctor --project . --json
py -m unittest tests.test_motor_cli_contract tests.test_motor_interface_coherence tests.test_motor_registry_consistency -v
```
