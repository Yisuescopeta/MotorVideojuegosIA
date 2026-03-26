# Prompt B.2

## Titulo
B.2 â€” â€œValidaciÃ³n offline y migraciones (N-1 â†’ N)â€

## Instrucciones

```text
Antes de cambiar nada:
1) Identifica dÃ³nde se parsean/cargan escenas/prefabs.
2) Identifica cÃ³mo se reportan errores (exceptions/logs).

Objetivo:
- Implementar un validador de escenas/prefabs:
  - Ejecutable por CLI: `validate_scene <path>` y `validate_all`.
  - Debe fallar con errores accionables (ruta del campo, expected vs actual).
- Implementar un sistema de migraciones:
  - Cada cambio de schema_version debe tener un migrator `migrate_vX_to_vY(data)` determinista y testeado.

Restricciones:
- PROHIBIDO introducir migraciones que dependan de la UI.
- No romper compatibilidad: si un archivo viejo se abre, debe migrarse y/o avisar claramente.

ValidaciÃ³n:
- Tests unitarios: (a) un JSON vOld migra a vNew y pasa validaciÃ³n, (b) un JSON invÃ¡lido produce error con path.
```

