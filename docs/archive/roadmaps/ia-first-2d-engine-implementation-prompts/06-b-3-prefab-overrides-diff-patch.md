# Prompt B.3

## Titulo
B.3 â€” â€œPrefab overrides como diff/patch (aplicaciÃ³n al cargar)â€

## Instrucciones

```text
Antes de cambiar nada:
1) Identifica cÃ³mo funcionan hoy los prefabs y cÃ³mo se instancian en escena/runtime.
2) Comprueba si ya existe algÃºn concepto de â€œoverrideâ€ o â€œmodificacionesâ€.

Objetivo:
- Definir e implementar un formato de overrides tipo patch:
  - add/remove component
  - set field value (incluyendo nested)
  - reorder children (si existe jerarquÃ­a)
- Aplicar overrides al cargar/bakear la escena (no cada frame).

Restricciones:
- PROHIBIDO duplicar toda la data del prefab en cada instancia.
- PROHIBIDO hacer que el editor guarde â€œcopias completasâ€ por comodidad.
- Debe ser serializable y aplicable por API IA sin editor.

ValidaciÃ³n:
- Caso de test: prefab base + 2 instancias con overrides distintos â†’ runtime produce entidades distintas.
- Roundtrip: save/load conserva override semantics.
```

