# Prompt G.1

## Titulo
G.1 â€” â€œProfiler interno + mÃ©tricas pÃºblicas (API y headless)â€

## Instrucciones

```text
Antes de cambiar nada:
1) Identifica quÃ© mÃ©tricas ya existen (si hay contadores/drawcalls/logs).
2) Analiza el impacto de instrumentaciÃ³n actual.

Objetivo:
- Implementar un profiler interno:
  - tiempos por sistema (ECS systems)
  - render: batches/draw calls
  - fÃ­sica: step time, contactos, islands (si aplica)
  - memoria aproximada (si es posible)
- Exponer mÃ©tricas por API y CLI (export JSON).

Restricciones:
- PROHIBIDO que el profiler sÃ³lo viva en el editor.
- No introducir dependencias pesadas; prioriza simplicidad.

ValidaciÃ³n:
- CLI: `profile_run scene.json --frames 600 --out report.json`.
- Tests: report JSON tiene esquema estable (versionado).
```

