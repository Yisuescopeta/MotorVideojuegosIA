# Prompt H.4

## Titulo
H.4 â€” â€œRunner paralelo headless (vectorizaciÃ³n simple) + lÃ­mites de recursosâ€

## Instrucciones

```text
Antes de cambiar nada:
1) Revisa CLI y headless run.
2) Decide estrategia: subprocess por entorno vs mÃºltiples mundos en un proceso (justifica).

Objetivo:
- Implementar un runner paralelo:
  - ejecuta N entornos en paralelo para generar experiencia rÃ¡pidamente.
  - controla CPU/memoria y timeouts.
- AÃ±adir modos:
  - â€œfast simâ€ sin render
  - â€œrender occasionallyâ€ (si aplica) para debugging.

Restricciones:
- PROHIBIDO que el runner requiera GPU o UI.
- Debe integrarse con el dataset logging de H.3.

ValidaciÃ³n:
- Benchmark: N=8 entornos durante 10k steps y reporte de throughput.
- Manejo de fallos: si un worker crashea, el runner reporta y continÃºa (o aborta) segÃºn configuraciÃ³n.
```

