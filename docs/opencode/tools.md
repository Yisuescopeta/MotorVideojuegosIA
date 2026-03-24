# Custom Tools OpenCode

## Objetivo

Este repo envuelve tooling Python ya existente del motor mediante Custom Tools
de OpenCode en `.opencode/tools/`.

No se reimplementan scripts del motor. Los wrappers solo:

- validan argumentos con `tool.schema`
- construyen comandos de forma estricta
- ejecutan los scripts Python existentes
- devuelven salida estructurada con JSON y un resumen humano

## Tools Incluidas

- `engine_unittest`
- `engine_smoke`
- `dataset_generate_scenarios`
- `dataset_run_episodes`
- `dataset_replay_episode`
- `runner_parallel_rollout`

## Scripts Reales Envueltos

- [tools/engine_cli.py](/C:/Users/usuario/Downloads/MotorVideojuegosIA-main/MotorVideojuegosIA-main/tools/engine_cli.py)
- [tools/scenario_dataset_cli.py](/C:/Users/usuario/Downloads/MotorVideojuegosIA-main/MotorVideojuegosIA-main/tools/scenario_dataset_cli.py)
- [tools/parallel_rollout_runner.py](/C:/Users/usuario/Downloads/MotorVideojuegosIA-main/MotorVideojuegosIA-main/tools/parallel_rollout_runner.py)

## Reglas De Seguridad

- no se expone `bash` raw dentro del tool
- los comandos se construyen como arrays cerrados
- las rutas de salida se restringen a `artifacts/` o `.motor/`
- no hay dependencia de UI

## Contrato De Retorno

Cada tool devuelve un objeto con este esquema general:

```json
{
  "ok": true,
  "summary": "engine_smoke completed: artifacts/opencode/manual_smoke",
  "command": ["py", "-3", "tools/engine_cli.py", "smoke", "..."],
  "cwd": "C:/.../MotorVideojuegosIA-main",
  "exitCode": 0,
  "stdout": "...",
  "stderr": "",
  "outputDir": "artifacts/opencode/manual_smoke",
  "data": {}
}
```

## Smoke Test Manual

### 1. Cargar el repo con OpenCode

Abre OpenCode desde la raiz del proyecto.

### 2. Probar `engine_unittest`

Pide a OpenCode algo como:

```text
Run the custom tool engine_unittest and summarize the result.
```

Resultado esperado:

- ejecuta `unittest discover`
- devuelve `ok: true` si la suite pasa

### 3. Probar `engine_smoke`

```text
Run engine_smoke with scene=levels/demo_level.json frames=5 seed=123 out_dir=artifacts/opencode/manual_smoke
```

Resultado esperado:

- crea `artifacts/opencode/manual_smoke/`
- genera smoke artifacts del motor
- devuelve referencias estructuradas a `smoke_profile.json`,
  `smoke_debug_dump.json` y `smoke_migrated_scene.json`

### 4. Probar `dataset_generate_scenarios`

```text
Run dataset_generate_scenarios with scene=levels/multiagent_toy_scene.json count=5 seed=123 out_dir=artifacts/opencode/generated_scenarios_smoke
```

Resultado esperado:

- crea `manifest.json`
- devuelve el manifest parseado si existe

### 5. Probar `dataset_run_episodes`

```text
Run dataset_run_episodes with scene=levels/platformer_test_scene.json episodes=4 max_steps=20 seed=123 out=artifacts/opencode/episodes_smoke/episodes.jsonl summary_out=artifacts/opencode/episodes_smoke/summary.json
```

Resultado esperado:

- genera `episodes.jsonl`
- genera `summary.json`
- devuelve el summary parseado

### 6. Probar `dataset_replay_episode`

```text
Run dataset_replay_episode with episodes_jsonl=artifacts/opencode/episodes_smoke/episodes.jsonl episode_id=episode_0000 out=artifacts/opencode/episodes_smoke/replay_episode_0000.json
```

Resultado esperado:

- genera el replay report
- devuelve el JSON parseado del replay

### 7. Probar `runner_parallel_rollout`

```text
Run runner_parallel_rollout with scene=levels/multiagent_toy_scene.json workers=2 episodes=4 max_steps=20 seed=123 out_dir=artifacts/opencode/parallel_smoke
```

Resultado esperado:

- genera `parallel_report.json`
- devuelve el report parseado

## Notas

- El nombre de cada tool coincide con el nombre del archivo en
  `.opencode/tools/`.
- La implementacion usa la API oficial de Custom Tools de OpenCode:
  [Custom Tools](https://open-code.ai/en/docs/custom-tools).
