# RL Wrapper

El wrapper `Gymnasium` del motor vive en [engine/rl/gym_env.py](/C:/Users/usuario/Downloads/MotorVideojuegosIA-main/MotorVideojuegosIA-main/engine/rl/gym_env.py).

## Contrato

La clase principal es `MotorGymEnv` y sigue el contrato:

- `reset(seed=..., options=...) -> (obs, info)`
- `step(action) -> (obs, reward, terminated, truncated, info)`

Funciona en modo headless por defecto y se apoya en el runtime real del motor mediante:

- carga de escena por [engine/api/engine_api.py](/C:/Users/usuario/Downloads/MotorVideojuegosIA-main/MotorVideojuegosIA-main/engine/api/engine_api.py)
- entrada inyectada por `InputSystem.inject_state`
- avance de simulacion por `step()`

Durante `reset()` el wrapper ejecuta por defecto `1` frame neutro de asentamiento (`settle_frames=1`) para estabilizar escenas cuyo spawn inicial entra levemente solapado con el suelo.

## Action Spec

- version: `1`
- modo: `discrete_6`

Mapa de acciones:

1. `0`: idle
2. `1`: left
3. `2`: right
4. `3`: jump
5. `4`: left_jump
6. `5`: right_jump

La codificacion esta pensada para ampliarse a multiagente mas adelante sin acoplarse a UI.

## Observation Spec

- version: `1`
- campos numericos y serializables

Campos:

- `self_position`
- `self_velocity`
- `goal_delta`
- `on_ground`
- `goal_exists`
- `last_action`

## Reward Baseline

La recompensa base actual es deliberadamente simple y transparente:

- progreso horizontal: `delta_x * 0.01`
- bonus por objetivo alcanzado: `+1.0`
- penalizacion por caer fuera del umbral: `-1.0`

Esto sirve como baseline reproducible para entrenamiento y test, no como reward universal del motor.

## Dataset

El runner de rollouts aleatorios vive en [random_rollout_dataset.py](/C:/Users/usuario/Downloads/MotorVideojuegosIA-main/MotorVideojuegosIA-main/tools/random_rollout_dataset.py).

Se eligio `JSONL` frente a `NPZ` por tres motivos:

- no añade dependencia pesada
- cada transicion es inspeccionable a simple vista
- es facil de concatenar, filtrar y versionar

Ejemplo:

```bash
py -3 tools/random_rollout_dataset.py levels/platformer_test_scene.json --episodes 10 --max-steps 120 --seed 123 --out artifacts/random_rollouts.jsonl
```

## Multiagente

El wrapper multiagente vive en [pettingzoo_env.py](/C:/Users/usuario/Downloads/MotorVideojuegosIA-main/MotorVideojuegosIA-main/engine/rl/pettingzoo_env.py) y usa un modelo `ParallelEnv`.

Se eligio `Parallel` y no `AEC` porque:

- el motor ya procesa acciones de varios actores en el mismo frame
- la fisica y colisiones son simultaneas, no por turnos
- evita introducir una semantica artificial distinta del runtime real

Escena de validacion:

- [multiagent_toy_scene.json](/C:/Users/usuario/Downloads/MotorVideojuegosIA-main/MotorVideojuegosIA-main/levels/multiagent_toy_scene.json)

Dataset multiagente:

```bash
py -3 tools/multiagent_rollout_dataset.py levels/multiagent_toy_scene.json --episodes 5 --max-steps 80 --seed 123 --out artifacts/multiagent_rollouts.jsonl
```

## Scenario Generator y Replay

El tooling de escenarios y logging versionado vive en [scenario_dataset_cli.py](/C:/Users/usuario/Downloads/MotorVideojuegosIA-main/MotorVideojuegosIA-main/tools/scenario_dataset_cli.py).

Ejemplos:

```bash
py -3 tools/scenario_dataset_cli.py generate-scenarios levels/multiagent_toy_scene.json --count 100 --seed 123 --out-dir artifacts/generated_scenarios
py -3 tools/scenario_dataset_cli.py run-episodes levels/platformer_test_scene.json --episodes 100 --max-steps 120 --seed 123 --out artifacts/episodes.jsonl --summary-out artifacts/episodes_summary.json
py -3 tools/scenario_dataset_cli.py replay-episode artifacts/episodes.jsonl --episode-id episode_0000 --out artifacts/replay_episode_0000.json
```

Cada step del dataset guarda:

- acciones
- rewards
- infos
- eventos recientes
- fingerprint de mundo

## Runner Paralelo

El runner paralelo headless vive en [parallel_rollout_runner.py](/C:/Users/usuario/Downloads/MotorVideojuegosIA-main/MotorVideojuegosIA-main/tools/parallel_rollout_runner.py).

Usa subprocess por worker para:

- aislar fallos
- limitar mejor CPU por `max_workers`
- evitar compartir estado mutable entre entornos

Ejemplo:

```bash
py -3 tools/parallel_rollout_runner.py levels/multiagent_toy_scene.json --workers 8 --episodes 8 --max-steps 1250 --seed 123 --out-dir artifacts/parallel_rollouts
```
