# Prompt H.3

## Titulo
H.3 â€” â€œScenario generator + dataset logging (replays + metadatos)â€

## Instrucciones

```text
Antes de cambiar nada:
1) Identifica cÃ³mo hoy se crean escenas por API y cÃ³mo se guardan.
2) Identifica timeline/snapshots actuales.

Objetivo:
- Implementar un generador de escenarios data-driven:
  - toma una plantilla (prefab/scene) y aplica randomizaciones controladas por seed.
  - guarda: escena generada + seed + specs + mÃ©tricas.
- Implementar logging de episodios:
  - acciones, observaciones (o referencias), rewards, eventos, fingerprint por step.

Restricciones:
- PROHIBIDO â€œrandomâ€ sin seed.
- Dataset debe ser reproducible y versionado.

ValidaciÃ³n:
- Generar 100 escenarios y correr 100 episodios headless, con reporte agregado.
- Poder re-ejecutar un episodio por ID y reproducir sus resultados.
```

