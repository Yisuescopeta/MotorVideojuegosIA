# Prompt B.4

## Titulo
B.4 â€” â€œContrato â€˜UI traduce modeloâ€™: API de ediciÃ³n transaccionalâ€

## Instrucciones

```text
Antes de cambiar nada:
1) Localiza cÃ³mo el editor modifica el modelo: inspector, drag&drop, jerarquÃ­a, etc.
2) Identifica si existe ya un sistema de comandos/undo/redo o timeline.

Objetivo:
- Implementar una API de ediciÃ³n transaccional (editor agnÃ³stica):
  - begin_transaction()
  - apply_change(change)
  - commit() / rollback()
- DiseÃ±ar `Change` como dato serializable (para undo/redo, timeline y para IA).
- La UI solo emite `Change`; el modelo aplica.

Restricciones:
- PROHIBIDO que la UI mutile directamente el estado runtime sin pasar por Change.
- Debe funcionar tanto en editor como por API IA.

ValidaciÃ³n:
- Demo mÃ­nima: cambiar un valor desde UI y desde API IA genera el mismo Change serializado.
- Undo/redo funciona sin UI (por CLI/test).
```

