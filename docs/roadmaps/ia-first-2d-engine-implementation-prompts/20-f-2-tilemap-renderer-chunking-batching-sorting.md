# Prompt F.2

## Titulo
F.2 â€” â€œTilemap renderer: chunking + batching + sortingâ€

## Instrucciones

```text
Antes de cambiar nada:
1) Inspecciona el RenderGraph/passes y el batching implementado.
2) Decide la estrategia de chunking (tamaÃ±o de chunk, invalidaciÃ³n parcial).

Objetivo:
- Implementar rendering eficiente de tilemaps:
  - reconstrucciÃ³n incremental al cambiar tiles
  - batches por atlas/material y por chunk
  - sorting por layer/order

Restricciones:
- PROHIBIDO recomponer todo el mapa por cada cambio pequeÃ±o.
- No uses UI como cachÃ©: el runtime debe recomponer chunks por datos.

ValidaciÃ³n:
- Escena de stress: tilemap grande (p. ej. 256x256) con 3 layers.
- MÃ©tricas muestran batches y coste de rebuild incremental.
```

