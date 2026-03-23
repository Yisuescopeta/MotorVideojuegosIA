# Prompt F.3

## Titulo
F.3 â€” â€œColisiones por tile + composiciÃ³n/merge de shapesâ€

## Instrucciones

```text
Antes de cambiar nada:
1) Revisa el backend de fÃ­sica y si soporta mÃºltiples shapes por body.
2) Decide cÃ³mo se mapearÃ¡ tile metadata -> collider.

Objetivo:
- Generar colliders desde tilemap:
  - por tile (simple) y/o por regiones mergeadas (optimizaciÃ³n).
- Mantener datos serializables: el tile dice â€œcolisionaâ€ + tipo de forma (grid/sprite shape).
- Integrar con eventos/reglas declarativas actuales.

Restricciones:
- PROHIBIDO dependencia del editor para generar colliders: debe pasar en runtime y en CLI build-assets.
- MantÃ©n un modo determinista y testeable.

ValidaciÃ³n:
- Test: un personaje colisiona con paredes en tilemap.
- Benchmark: coste de generar colliders por mapa.
```

