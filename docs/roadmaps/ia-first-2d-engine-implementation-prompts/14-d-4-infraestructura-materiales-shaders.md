# Prompt D.4

## Titulo
D.4 â€” â€œInfraestructura de materiales/shaders (sin construir un editor de shaders aÃºn)â€

## Instrucciones

```text
Antes de cambiar nada:
1) Analiza cÃ³mo se definen hoy materiales/efectos (si existen).
2) Identifica si hay un concepto anÃ¡logo a tags/predicates.

Objetivo:
- Crear un modelo serializable Material:
  - referencias a shader/programa, parÃ¡metros, blend mode, tags.
- Runtime: aplicar materiales en batching sin romper compatibilidad.

Restricciones:
- PROHIBIDO hacer que el material exista solo como â€œconfig UIâ€.
- No intentes un editor visual de shaders en esta fase.

ValidaciÃ³n:
- 2 materiales distintos en una escena (p. ej. normal vs additive) se renderizan correctamente.
- SerializaciÃ³n: material se guarda/carga sin perder parÃ¡metros.
```

