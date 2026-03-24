# Slash Commands OpenCode

## Objetivo

Este repo define comandos reutilizables en `.opencode/commands/` para flujos
repetibles del motor.

Los comandos:

- usan el sistema de Markdown commands de OpenCode
- pasan argumentos con placeholders como `$1`, `$2` y `$ARGUMENTS`
- delegan en las Custom Tools ya existentes
- no duplican la logica de los scripts Python del repo

Referencia oficial:

- [OpenCode Commands](https://opencode.ai/docs/commands/)

## Comandos Incluidos

- `/engine-test`
- `/engine-smoke <scene> [frames] [seed]`
- `/dataset-generate <scene> [count] [seed]`
- `/episodes-run <scene> [episodes] [max_steps] [seed]`
- `/episodes-replay <episodes_jsonl> <episode_id>`
- `/parallel-rollout <scene> [workers] [episodes] [max_steps] [seed]`

## Que Hace Cada Uno

### `/engine-test`

Valida:

- `unittest discover` sobre `tests/`

Artifacts:

- no requiere bundle nuevo por defecto

Ejemplo:

```text
/engine-test
```

### `/engine-smoke <scene> [frames] [seed]`

Valida:

- scene validation
- asset validation
- migrate
- build-assets
- headless run corto
- profile run corto

Artifacts:

- `artifacts/opencode/engine_smoke/`

Ejemplo:

```text
/engine-smoke levels/demo_level.json
/engine-smoke levels/demo_level.json 8 321
```

### `/dataset-generate <scene> [count] [seed]`

Valida:

- generacion de escenarios
- manifest reproducible

Artifacts:

- `artifacts/opencode/generated_scenarios/`

Ejemplo:

```text
/dataset-generate levels/multiagent_toy_scene.json
/dataset-generate levels/multiagent_toy_scene.json 20 123
```

### `/episodes-run <scene> [episodes] [max_steps] [seed]`

Valida:

- ejecucion reproducible de episodios
- dataset JSONL
- summary JSON

Artifacts:

- `artifacts/opencode/episodes/episodes.jsonl`
- `artifacts/opencode/episodes/summary.json`

Ejemplo:

```text
/episodes-run levels/platformer_test_scene.json
/episodes-run levels/platformer_test_scene.json 8 30 77
```

### `/episodes-replay <episodes_jsonl> <episode_id>`

Valida:

- replay de un episodio concreto
- generacion del replay report

Artifacts:

- `artifacts/opencode/episodes/replay_<episode_id>.json`

Ejemplo:

```text
/episodes-replay artifacts/opencode/episodes/episodes.jsonl episode_0000
```

### `/parallel-rollout <scene> [workers] [episodes] [max_steps] [seed]`

Valida:

- rollout paralelo por subprocess
- throughput y fallos por shard

Artifacts:

- `artifacts/opencode/parallel_rollout/`

Ejemplo:

```text
/parallel-rollout levels/multiagent_toy_scene.json
/parallel-rollout levels/multiagent_toy_scene.json 2 4 20 123
```

## Notas De Uso

- Los comandos no deben escribir fuera de `artifacts/` o `.motor/` sin
  confirmacion.
- Si faltan argumentos obligatorios como `scene` o `episode_id`, el agente debe
  pedirlos antes de continuar.
- La ejecucion efectiva debe pasar por las tools custom ya creadas, no por
  bash raw.
