# Politica De Permisos OpenCode

## Objetivo

Este repo usa `permission` en
[opencode.jsonc](/C:/Users/usuario/Downloads/MotorVideojuegosIA-main/MotorVideojuegosIA-main/opencode.jsonc)
para mantener OpenCode util sin abrir shell o edicion peligrosa por defecto.

La politica esta basada en la documentacion oficial de OpenCode sobre
permissions y object syntax:

- [Permissions](https://open-code.ai/docs/en/permissions)
- [Config](https://open-code.ai/en/docs/config)

## Regla Base

Se usa:

```jsonc
"permission": {
  "*": "ask"
}
```

Justificacion:

- `ask` mantiene la experiencia util para tareas legitimas no previstas.
- `deny` global volveria OpenCode demasiado rigido para iteraciones reales del
  motor.
- Los riesgos altos quedan bloqueados con reglas especificas.

## Bash

`bash` usa object syntax con la regla "ultima coincidencia gana".

Se permite sin aprobacion solo lo que ya usa de verdad el pipeline del repo:

- `git status`
- `git diff`
- `git rev-parse *`
- `python -m unittest discover *`
- `py -3 -m unittest discover *`
- `python -m pytest *`
- `py -3 -m pytest *`
- `tools/engine_cli.py`
- `tools/scenario_dataset_cli.py`
- `tools/parallel_rollout_runner.py`
- `tools/random_rollout_dataset.py`
- `tools/multiagent_rollout_dataset.py`

Se bloquea de forma explicita:

- `git push`
- `rm`
- `rmdir`
- `del`
- `Remove-Item`

Todo lo demas queda en `ask`.

### Ejemplos permitidos

```bash
git status --short
git diff -- tests/test_engine_cli.py
py -3 tools/engine_cli.py smoke --scene levels/demo_level.json --frames 5 --seed 123 --out-dir artifacts/cli_smoke
py -3 tools/scenario_dataset_cli.py replay-episode artifacts/episodes.jsonl --episode-id episode_0000 --out artifacts/replay_episode_0000.json
py -3 tools/parallel_rollout_runner.py levels/multiagent_toy_scene.json --workers 2 --episodes 4 --max-steps 12 --seed 10 --out-dir artifacts/parallel_rollouts
py -3 -m unittest discover -s tests -p "test_*.py"
```

### Ejemplos bloqueados

```bash
git push origin main
rm -rf artifacts
Remove-Item -Recurse -Force .motor
```

## Edit

`edit` queda en deny por defecto y abre solo las rutas necesarias:

- `docs/**`: `allow`
- codigo, tests, tooling, assets y datos del proyecto: `ask`
- cualquier otra ruta: `deny`

Justificacion:

- documentacion es la zona menos riesgosa para iterar sin friccion
- cambios a codigo o datos del proyecto deben seguir pidiendo confirmacion

### Ejemplos

- editar `docs/opencode/security.md`: `allow`
- editar `engine/api/engine_api.py`: `ask`
- editar `tests/test_engine_cli.py`: `ask`
- editar una ruta no prevista fuera del repo: `deny`

## Read

`read` mantiene el comportamiento util por defecto, pero protege secretos:

```jsonc
"read": {
  "*": "allow",
  "*.env": "deny",
  "*.env.*": "deny",
  "*.env.example": "allow"
}
```

## External Directory

Se usa:

```jsonc
"external_directory": "deny"
```

Justificacion:

- este repo no necesita tocar rutas fuera del workspace para su pipeline
- reduce el riesgo de leer o editar archivos del usuario por accidente

## Doom Loop

Se usa:

```jsonc
"doom_loop": "ask"
```

Justificacion:

- permite inspeccionar un patron repetitivo antes de cortar una tarea legitima
- evita repetir tres veces la misma llamada sin control

## Comandos Del Motor Cubiertos

Estos son los comandos reales identificados en docs y tests del repo:

- [tools/engine_cli.py](/C:/Users/usuario/Downloads/MotorVideojuegosIA-main/MotorVideojuegosIA-main/tools/engine_cli.py)
- [tools/scenario_dataset_cli.py](/C:/Users/usuario/Downloads/MotorVideojuegosIA-main/MotorVideojuegosIA-main/tools/scenario_dataset_cli.py)
- [tools/parallel_rollout_runner.py](/C:/Users/usuario/Downloads/MotorVideojuegosIA-main/MotorVideojuegosIA-main/tools/parallel_rollout_runner.py)
- [tools/random_rollout_dataset.py](/C:/Users/usuario/Downloads/MotorVideojuegosIA-main/MotorVideojuegosIA-main/tools/random_rollout_dataset.py)
- [tools/multiagent_rollout_dataset.py](/C:/Users/usuario/Downloads/MotorVideojuegosIA-main/MotorVideojuegosIA-main/tools/multiagent_rollout_dataset.py)

Cobertura de referencia en el repo:

- [docs/cli.md](/C:/Users/usuario/Downloads/MotorVideojuegosIA-main/MotorVideojuegosIA-main/docs/cli.md)
- [docs/rl.md](/C:/Users/usuario/Downloads/MotorVideojuegosIA-main/MotorVideojuegosIA-main/docs/rl.md)
- [tests/test_engine_cli.py](/C:/Users/usuario/Downloads/MotorVideojuegosIA-main/MotorVideojuegosIA-main/tests/test_engine_cli.py)
- [tests/test_scenario_dataset.py](/C:/Users/usuario/Downloads/MotorVideojuegosIA-main/MotorVideojuegosIA-main/tests/test_scenario_dataset.py)
