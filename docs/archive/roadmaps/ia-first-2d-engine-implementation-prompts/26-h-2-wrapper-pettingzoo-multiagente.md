# Prompt H.2

## Titulo
H.2 â€” â€œWrapper PettingZoo (ParallelEnv o AEC) para multiagenteâ€

## Instrucciones

```text
Antes de cambiar nada:
1) Revisa el wrapper Gymnasium y la definiciÃ³n de specs.
2) Decide si tu motor necesita acciones simultÃ¡neas (Parallel) o turn-based (AEC); justifica.

Objetivo:
- Implementar un wrapper PettingZoo:
  - API mÃ­nima coherente (reset/step/agents/terminations/truncations/infos)
  - mapping agent_id -> entidad/actor en tu mundo
- Soportar al menos 2 agentes simultÃ¡neos.

Restricciones:
- PROHIBIDO duplicar el mundo por agente; comparten RuntimeWorld (con aislamiento por IDs).
- No dependas de UI.

ValidaciÃ³n:
- Un ejemplo â€œtoyâ€ de 2 agentes (p. ej. empujarse, recoger goals, etc.) que corra headless.
- Dataset de rollouts multiagente generado.
```

