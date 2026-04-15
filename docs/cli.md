# CLI publica `motor`

Esta es la referencia canonica de la CLI publica actual. La implementacion vive
en `motor/cli.py` y las funciones de comando en `motor/cli_core.py`.

## Entrypoints

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

Genera o regenera los artefactos AI-facing del proyecto:

- `motor_ai.json`
- `START_HERE_AI.md`

```bash
py -m motor project bootstrap-ai --project . --json
```

El formato actual de `motor_ai.json` es `schema_version = 3`; ver
[MOTOR_AI_JSON_CONTRACT.md](MOTOR_AI_JSON_CONTRACT.md).

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

Alias legacy no documentados en `--help`:

- `motor animator upsert-state`
- `motor animator remove-state`

Se mantienen solo por compatibilidad temporal.

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

## Comandos del registry que aun no estan en la CLI

`motor capabilities --json` puede listar capacidades con `status = "planned"`.
Esas capacidades documentan intencion de API o roadmap interno, pero no deben
tratarse como comandos CLI disponibles si `motor/cli.py` no las expone.

Ejemplos actuales de capacidades planificadas sin parser publico incluyen:

- `entity delete/list/parent`
- `component edit/remove`
- operaciones de prefab
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
