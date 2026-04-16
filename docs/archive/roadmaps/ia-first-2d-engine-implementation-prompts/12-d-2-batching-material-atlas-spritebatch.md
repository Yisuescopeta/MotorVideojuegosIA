# Prompt D.2

## Titulo
D.2 â€” â€œBatching por material/atlas y disciplina tipo SpriteBatchâ€

## Instrucciones

```text
Antes de cambiar nada:
1) Identifica dÃ³nde se producen â€œdraw callsâ€ o equivalentes.
2) Identifica cambios de textura/material.

Objetivo:
- Introducir un sistema de batching:
  - agrupa por (atlas_id, material_id, shader_id, blend_mode, layer).
  - minimiza cambios de estado.
- Si existe ya batching, endurecerlo: aÃ±ade mÃ©tricas y tests de regresiÃ³n.

Restricciones:
- PROHIBIDO hacer â€œsort cada frameâ€ si no es imprescindible; documenta la estrategia.
- No introducir dependencias UI.

ValidaciÃ³n:
- Benchmark headless de una escena con 5k sprites: reporta batches/draws.
- Golden de mÃ©tricas (dentro de tolerancias) para evitar regresiones.
```

