# Prompt H.1

## Titulo
H.1 â€” â€œWrapper Gymnasium: Env(reset/step) sobre tu runtime headlessâ€

## Instrucciones

```text
Antes de cambiar nada:
1) Revisa tu API programÃ¡tica para IA y el loop de simulaciÃ³n.
2) Identifica cÃ³mo se hace reset de mundo/escena y cÃ³mo se avanza un step.

Objetivo:
- Implementar una clase que siga el contrato Gymnasium:
  - reset(seed=..., options=...) -> (obs, info)
  - step(action) -> (obs, reward, terminated, truncated, info)
- Definir â€œaction specâ€ y â€œobservation specâ€ versionados (documento + cÃ³digo).
- Soportar modo headless por defecto.

Restricciones:
- PROHIBIDO que obs/action dependan de UI o de assets cargados solo en editor.
- No asumas un Ãºnico agente: diseÃ±a para extender a multiagente (sin implementarlo aÃºn).

ValidaciÃ³n:
- Un script de prueba que haga random rollouts 10 episodios y guarde un dataset JSONL/NPZ (elige, justifica).
- Reproducibilidad: misma seed -> mismos resultados (segÃºn alcance definido en Fase A).
```

