# RL y datasets

Estado: `experimental/tooling`.

Esta documentacion cubre wrappers y herramientas reales del repo, pero no forman
parte del contrato de `core obligatorio`.

## Gymnasium

El wrapper `Gymnasium` vive en [../engine/rl/gym_env.py](../engine/rl/gym_env.py).

Clase principal:

- `MotorGymEnv`

Contrato:

- `reset(seed=..., options=...) -> (obs, info)`
- `step(action) -> (obs, reward, terminated, truncated, info)`

Funciona en modo headless y usa el runtime real mediante:

- carga de escena por [../engine/api/engine_api.py](../engine/api/engine_api.py)
- entrada inyectada por `InputSystem.inject_state`
- avance de simulacion por `EngineAPI.step()`

Durante `reset()`, el wrapper ejecuta por defecto `settle_frames=1` para
estabilizar escenas cuyo spawn inicial solapa levemente con el suelo.

## Action spec

- version: `1`
- modo: `discrete_6`

Mapa de acciones:

1. `0`: idle
2. `1`: left
3. `2`: right
4. `3`: jump
5. `4`: left_jump
6. `5`: right_jump

## Observation spec

- version: `1`
- campos numericos y serializables

Campos:

- `self_position`
- `self_velocity`
- `goal_delta`
- `on_ground`
- `goal_exists`
- `last_action`

## Reward baseline

La recompensa base actual es deliberadamente simple:

- progreso horizontal: `delta_x * 0.01`
- bonus por objetivo alcanzado: `+1.0`
- penalizacion por caer fuera del umbral: `-1.0`

Sirve como baseline reproducible para entrenamiento y test, no como reward
universal del motor.

## Dataset aleatorio

El runner de rollouts aleatorios vive en
[../tools/random_rollout_dataset.py](../tools/random_rollout_dataset.py).

Se eligio `JSONL` frente a `NPZ` porque cada transicion es inspeccionable,
concatenable y no requiere dependencia pesada.

```bash
py tools/random_rollout_dataset.py levels/platformer_test_scene.json --episodes 10 --max-steps 120 --seed 123 --out artifacts/random_rollouts.jsonl
```

## Multiagente

El wrapper multiagente vive en
[../engine/rl/pettingzoo_env.py](../engine/rl/pettingzoo_env.py) y usa un modelo
`ParallelEnv`.

Se eligio `Parallel` porque el motor procesa acciones de varios actores en el
mismo frame y la fisica se resuelve simultaneamente.

Escena de validacion:

- [../levels/multiagent_toy_scene.json](../levels/multiagent_toy_scene.json)

Dataset multiagente:

```bash
py tools/multiagent_rollout_dataset.py levels/multiagent_toy_scene.json --episodes 5 --max-steps 80 --seed 123 --out artifacts/multiagent_rollouts.jsonl
```

## Scenario generator y replay

El tooling de escenarios y logging versionado vive en
[../tools/scenario_dataset_cli.py](../tools/scenario_dataset_cli.py).

Ejemplos:

```bash
py tools/scenario_dataset_cli.py generate-scenarios levels/multiagent_toy_scene.json --count 100 --seed 123 --out-dir artifacts/generated_scenarios
py tools/scenario_dataset_cli.py run-episodes levels/platformer_test_scene.json --episodes 100 --max-steps 120 --seed 123 --out artifacts/episodes.jsonl --summary-out artifacts/episodes_summary.json
py tools/scenario_dataset_cli.py replay-episode artifacts/episodes.jsonl --episode-id episode_0000 --out artifacts/replay_episode_0000.json
```

Cada step del dataset guarda:

- acciones
- rewards
- infos
- eventos recientes
- fingerprint de mundo

## Runner paralelo

El runner paralelo headless vive en
[../tools/parallel_rollout_runner.py](../tools/parallel_rollout_runner.py).

Usa subprocess por worker para aislar fallos y evitar compartir estado mutable
entre entornos.

```bash
py tools/parallel_rollout_runner.py levels/multiagent_toy_scene.json --workers 8 --episodes 8 --max-steps 1250 --seed 123 --out-dir artifacts/parallel_rollouts
```
