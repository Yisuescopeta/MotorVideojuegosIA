# Prompt B.1

## Titulo
B.1 â€” â€œEspecificaciÃ³n de schema vNext (escenas/prefabs/assets)â€

## Instrucciones

```text
Antes de cambiar nada:
1) Abre ejemplos reales de escenas JSON y prefabs actuales.
2) Documenta campos, relaciones (jerarquÃ­a), referencias a assets y behaviours serializables.

Objetivo:
- DiseÃ±ar (NO implementar todavÃ­a en profundidad) un schema vNext:
  - Scene, Entity, Component, ResourceRef/AssetRef, Prefab, PrefabInstance + Overrides.
- AÃ±adir un documento /docs/schema_vNext.md que defina:
  - campos obligatorios,
  - versionado (schema_version),
  - reglas de compatibilidad,
  - restricciones (no UI-state),
  - ejemplos JSON concisos.

Restricciones:
- No inventar un â€œestÃ¡ndarâ€ nuevo si ya existe uno Ãºtil: usa JSON convencional y define reglas claras del proyecto.
- Debe ser compatible con la filosofÃ­a: runtime/editor/API consumen el MISMO modelo.

ValidaciÃ³n:
- Incluye al menos 3 ejemplos: escena simple, prefab con overrides, escena con referencias a assets por ID.
```

