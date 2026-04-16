# Prompt A.3

## Titulo
A.3 â€” â€œDeterminismo mÃ­nimo: seed, orden y â€˜state hashâ€™â€

## Instrucciones

```text
Antes de cambiar nada:
1) Busca cualquier uso de aleatoriedad (random, time, uuid, etc.) y cualquier ID generado en runtime.
2) Identifica si el orden de iteraciÃ³n de entidades/componentes puede variar (p. ej. uso de dict no ordenado, sets, etc.).

Objetivo:
- Introducir un â€œDeterminism Layerâ€ mÃ­nimo que:
  - permita fijar una seed global para runs headless,
  - evite que IDs no deterministas contaminen el estado serializable,
  - provea una funciÃ³n estÃ¡ndar: compute_state_fingerprint(world) -> str,
    que sea estable en la misma mÃ¡quina/versiÃ³n.

Restricciones:
- No prometas determinismo cross-platform si el motor usa floats no controlados; documenta el alcance real.
- PROHIBIDO modificar UI para â€œarreglar determinismoâ€; debe ser runtime+data.

ValidaciÃ³n:
- Extiende el harness (A.2) para ejecutar 2 runs con misma seed y verificar fingerprint idÃ©ntico.
- AÃ±ade 1 run con seed distinta y demuestra fingerprint distinto (si aplica).
```

