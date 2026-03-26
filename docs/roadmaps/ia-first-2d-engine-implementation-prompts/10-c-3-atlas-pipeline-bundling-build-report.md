# Prompt C.3

## Titulo
C.3 â€” â€œAtlas pipeline y bundling reproducible con build reportâ€

## Instrucciones

```text
Antes de cambiar nada:
1) Busca si ya existe atlas/packing o batching por textura.
2) Identifica cÃ³mo se empaqueta/distribuye hoy (si existe algo).

Objetivo:
- AÃ±adir un pipeline de atlas:
  - agrupa sprites por â€œgrupo de usoâ€ y genera atlas pages.
  - produce metadatos de UVs y rects por sprite.
- Implementar bundling:
  - empaqueta artifacts + scenes/prefabs en un formato de bundle del motor.
  - genera un build report (tamaÃ±o por asset + totales).

Restricciones:
- PROHIBIDO que el editor sea el Ãºnico modo de generar un build.
- El build report debe ser reproducible en headless.

ValidaciÃ³n:
- Comparar un escenario antes/despuÃ©s: nÃºmero de binds/draw-batches disminuye o se monitoriza.
- Build report existe y lista top-N assets por tamaÃ±o.
```

