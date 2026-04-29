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
- `warnings`: bootstrap faltante/regenerable, componentes desconocidos y sospechas en modo normal.
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

El JSON devuelve `scene_name`, `scene_path`, `startup_scene`,
`entities_created`, `entity_count` y `scene_file`.

### `motor game platformer add-player`

Crea o actualiza `Player` en la escena de plataformas seleccionada:

```bash
py -m motor game platformer add-player --x 100 --y 300 --project . --json
```

### `motor game platformer add-ground`

Crea o actualiza `Ground` usando celdas de 64 px. `--from-x` es inclusivo y
`--to-x` es exclusivo; `--from-x 0 --to-x 20 --y 8` genera un suelo de
`20 * 64` px centrado en `x=640`, `y=512`.

```bash
py -m motor game platformer add-ground --from-x 0 --to-x 20 --y 8 --project . --json
```

### `motor game platformer add-platform`

Crea o actualiza `Platform` usando celdas de 64 px. `--x` es la celda inicial
izquierda y `--width` mide celdas.

```bash
py -m motor game platformer add-platform --x 5 --y 6 --width 3 --project . --json
```

### `motor game platformer add-coin`

Crea o actualiza `Coin` con `Transform`, `Collider` trigger y `Collectible2D`.

```bash
py -m motor game platformer add-coin --x 320 --y 200 --points 1 --project . --json
```

### `motor game platformer add-hazard`

Crea o actualiza `Hazard` con `Transform`, `Collider` trigger y `Hazard2D`.

```bash
py -m motor game platformer add-hazard --x 640 --y 300 --damage 1 --project . --json
```

### `motor game platformer add-goal`

Crea o actualiza `Goal` con `Transform`, `Collider` trigger y `Goal2D`, sin
referencias a assets concretos.

```bash
py -m motor game platformer add-goal --x 1100 --y 200 --project . --json
```

### `motor game platformer add-respawn`

Crea o actualiza `Respawn_<id>` con `Transform` y `RespawnPoint2D`.

```bash
py -m motor game platformer add-respawn --x 100 --y 300 --id default --project . --json
```

### `motor game platformer validate`

Valida escena, `Player`, suelo/plataforma, `Goal` semantico, carga de escena y
compliance estricto sin runtime externo bloqueante. Si existen `Collectible2D`,
`Hazard2D`, `Goal2D` o `RespawnPoint2D`, los reporta en `semantic_entities`.

```bash
py -m motor game platformer validate --project . --json
```

Los comandos incrementales operan sobre esta regla: escena activa ya cargada,
si existe; si no, `.motor/editor_state.json -> active_scene`; si no,
`settings/project_settings.json -> startup_scene`; si no, primera escena
cargable bajo `levels/` ordenada por ruta. No usan `last_scene`.

Cada comando devuelve el envelope JSON oficial con `success`, `message` y
`data`. En `data` siempre se incluyen `scene_path`, `entities_created` y
`warnings`; `validate` agrega `validation`.

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
```

El JSON incluye `frames_requested`, `status_before`, `status_after_play`,
`status_after_step`, `status_after` y `scene`.

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
```

Opciones:

- `--count`: numero de eventos a recuperar (por defecto: 50).

Si no hay eventos disponibles, devuelve una lista vacia y una advertencia.
El JSON incluye `events` y `count`.

## Entidades

### `motor entity create <name>`

Crea una entidad en la escena activa. Puede recibir componentes iniciales como
JSON.

```bash
py -m motor entity create Player --project . --json
py -m motor entity create Player --components '{"Transform":{"x":100,"y":200}}' --project . --json
```

El comando guarda automaticamente la escena despues de crear la entidad.

## Componentes

### `motor component add <entity> <component>`

Agrega un componente registrado a una entidad existente.

```bash
py -m motor component add Player Transform --data '{"x":100,"y":200}' --project . --json
py -m motor component add Player Animator --data '{"enabled":true,"speed":1.0}' --project . --json
```

El nombre de componente debe estar registrado en
`engine/levels/component_registry.py`.

## Prefabs

### `motor prefab create <entity> <path>`

Guarda una entidad raiz y su subarbol como prefab. Con `--replace-original`
sustituye el subarbol original por una instancia enlazada al prefab nuevo.

```bash
py -m motor prefab create EnemyTemplate prefabs/enemy.prefab --project . --json
py -m motor prefab create EnemyTemplate prefabs/enemy.prefab --replace-original --instance-name EnemyA --project . --json
```

### `motor prefab instantiate <path>`

Crea una instancia enlazada desde un prefab existente.

```bash
py -m motor prefab instantiate prefabs/enemy.prefab --name EnemyA --project . --json
py -m motor prefab instantiate prefabs/enemy.prefab --name EnemyA --parent Spawner --project . --json
```

### `motor prefab unpack <entity>`

Convierte una instancia de prefab en entidades explicitas editables.

```bash
py -m motor prefab unpack EnemyA --project . --json
```

### `motor prefab apply <entity>`

Aplica los overrides acumulados de una instancia al archivo prefab origen.

```bash
py -m motor prefab apply EnemyA --project . --json
```

### `motor prefab list`

Lista los prefabs detectados en el proyecto.

```bash
py -m motor prefab list --project . --json
```

## Animator

### `motor animator info <entity>`

Muestra configuracion de `Animator` para una entidad.

```bash
py -m motor animator info Player --project . --json
```

### `motor animator ensure <entity>`

Crea `Animator` si falta o actualiza su sprite sheet si se pasa `--sheet`.

```bash
py -m motor animator ensure Player --sheet assets/player.png --project . --json
```

### `motor animator set-sheet <entity> <asset>`

Actualiza el sprite sheet del `Animator`.

```bash
py -m motor animator set-sheet Player assets/player.png --project . --json
```

### `motor animator state create <entity> <state>`

Crea o actualiza un estado de animacion.

```bash
py -m motor animator state create Player idle --slices idle_0,idle_1,idle_2 --fps 8 --loop --set-default --project . --json
py -m motor animator state create Player attack --slices atk_0,atk_1 --fps 12 --no-loop --project . --json
```

Opciones:

- `--slices` es obligatorio.
- `--fps` por defecto vale `8.0`.
- `--loop` y `--no-loop` controlan repeticion; si no se indica, el comando usa loop.
- `--set-default` marca el estado como default.
- `--auto-create` crea `Animator` si falta.

### `motor animator state remove <entity> <state>`

Elimina un estado de animacion.

```bash
py -m motor animator state remove Player idle --project . --json
```

Existen aliases legacy ocultos para compatibilidad temporal, pero no forman
parte de la interfaz oficial ni se documentan como comandos disponibles. Usa
siempre la gramatica `animator state create/remove`.

## Assets

### `motor asset list`

Lista assets del proyecto, con filtro opcional.

```bash
py -m motor asset list --project . --json
py -m motor asset list --search player --project . --json
```

### `motor asset slice list <asset>`

Lista slices definidos para un asset.

```bash
py -m motor asset slice list assets/player.png --project . --json
```

### `motor asset slice grid <asset>`

Genera slices por grilla.

```bash
py -m motor asset slice grid assets/tiles.png --cell-width 32 --cell-height 32 --project . --json
```

Opciones adicionales:

- `--margin`
- `--spacing`
- `--pivot-x`
- `--pivot-y`
- `--naming-prefix`

### `motor asset slice auto <asset>`

Detecta slices por alpha. Con `--preview` no guarda cambios.

```bash
py -m motor asset slice auto assets/player.png --alpha-threshold 1 --preview --project . --json
py -m motor asset slice auto assets/player.png --project . --json
```

### `motor asset slice manual <asset>`

Guarda slices definidos manualmente como JSON inline o ruta a archivo JSON.

```bash
py -m motor asset slice manual assets/player.png --slices '[{"name":"idle_0","x":0,"y":0,"width":32,"height":32}]' --project . --json
```

## Agente experimental

Estos comandos exponen el agente clean-room nativo del motor como herramienta
experimental. Las sesiones se guardan en estado local del proyecto bajo
`.motor/agent_state/`.

### `motor agent providers list`

Lista providers configurados y su metadata.

```bash
py -m motor agent providers list --project . --json
```

`fake` y `replay` son providers offline de prueba. `openai` es online, requiere
una credencial usable y no se usa como fallback silencioso. Esa credencial puede
venir de `OPENAI_API_KEY`, del secreto local del agente o de login gestionado
por Codex/OpenAI cuando el bridge expone una API key reutilizable.

### `motor agent providers login <provider>`

Configura credenciales de provider.

```bash
py -m motor agent providers login opencode-go --api-key-stdin --project .
py -m motor agent providers login openai --codex-chatgpt --project .
py -m motor agent providers login openai --device-auth --project .
```

Modos soportados:

- `--api-key-stdin`: guarda un secreto local del agente sin dejarlo en el historial.
- `--codex-chatgpt`: delega el login real al CLI oficial `codex login`.
- `--device-auth`: usa el flujo oficial device-code de Codex para entornos sin navegador local.

### `motor agent providers logout <provider>`

Elimina credenciales locales de provider sin revelar secretos.

```bash
py -m motor agent providers logout openai --project . --json
```

No elimina variables de entorno ni sesiones externas gestionadas por otras
herramientas.

### `motor agent providers status [provider]`

Inspecciona estado de auth sin revelar secretos.

```bash
py -m motor agent providers status openai --project . --json
```

Campos relevantes:

- `credential_source`: `env`, `user_local`, `codex_chatgpt`, `codex_api_key`, `codex_keyring` o `none`.
- `auth_method`: metodo observable (`api_key` o `chatgpt`) cuando el origen lo permite.
- `runtime_ready`: indica si el runtime actual puede reutilizar la credencial detectada.

### `motor agent session create`

Crea una sesion de agente. Por defecto usa proveedor fake determinista.

```bash
py -m motor agent session create --project . --permission-mode confirm_actions --json
py -m motor agent session create --project . --permission-mode full_access --title "Sesion local" --json
py -m motor agent session create --project . --provider-id openai --model gpt-5 --stream --json
```

Modos de permisos:

- `confirm_actions` permite lecturas seguras y deja ediciones, shell y Git como acciones pendientes.
- `full_access` autoejecuta acciones permitidas, manteniendo limites de ruta, auditoria y bloqueo de secretos evidentes.

Opciones de provider:

- `--provider-id`: `fake` por defecto; `openai` requiere una credencial usable (`OPENAI_API_KEY`, secreto local o bridge gestionado por Codex/OpenAI).
- `--model`: modelo del provider.
- `--temperature`, `--max-tokens`: limites opcionales del provider.
- `--stream`: activa streaming si el provider lo soporta.

### `motor agent session compact <session_id>`

Compacta el transcript en memoria local sanitizada.

```bash
py -m motor agent session compact agent-session-id --project . --json
```

No compacta acciones pendientes sin conservar referencia; excluye rutas
protegidas y secretos evidentes.

### `motor agent session inspect <session_id>`

Inspecciona una sesion sin mutarla.

```bash
py -m motor agent session inspect agent-session-id --project . --json
```

### `motor agent message send <session_id> <message>`

Envia texto a una sesion. El proveedor fake puede ejecutar herramientas simples
como `read README.md`, `list .`, `search pattern in path`, `write path :: text`,
`edit path :: old => new`, `run <command>`, `git status` y `git diff`.

```bash
py -m motor agent message send agent-session-id "read README.md" --project . --json
```

### `motor agent action approve <session_id> <action_id>`

Aprueba o rechaza una accion pendiente generada en modo `confirm_actions`.

```bash
py -m motor agent action approve agent-session-id agent-action-id --project . --json
py -m motor agent action approve agent-session-id agent-action-id --reject --project . --json
```

### `motor agent usage <session_id>`

Muestra usage registrado por providers. El coste queda `unknown` si faltan
tokens o tabla de precios.

```bash
py -m motor agent usage agent-session-id --project . --json
```

## Comandos del registry que aun no estan en la CLI

`motor capabilities --json` puede listar capacidades con `status = "planned"`.
Esas capacidades documentan intencion de API o roadmap interno, pero no deben
tratarse como comandos CLI disponibles si `motor/cli.py` no las expone.

Ejemplos actuales de capacidades planificadas sin parser publico incluyen:

- `entity delete/list/parent`
- `component edit/remove`
- runtime `play/stop/step/undo/redo`
- queries de fisica desde CLI
- scene flow desde CLI

Para esas operaciones, usa `EngineAPI` programaticamente solo si el metodo esta
implementado y el flujo esta cubierto por tests.

## Validacion recomendada

```bash
py -m motor --help
py -m motor doctor --project . --json
py -m unittest tests.test_motor_cli_contract tests.test_motor_interface_coherence tests.test_motor_registry_consistency -v
```
