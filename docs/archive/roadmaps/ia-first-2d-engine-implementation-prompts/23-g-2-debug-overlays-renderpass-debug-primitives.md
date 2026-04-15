# Prompt G.2

## Titulo
G.2 â€” â€œDebug overlays como RenderPass y â€˜debug primitivesâ€™â€

## Instrucciones

```text
Antes de cambiar nada:
1) Revisa el RenderGraph y dÃ³nde insertar un Debug pass.
2) Identifica quÃ© datos quieres dibujar: AABB, colliders, joints, tile chunks, cÃ¡mara, selecciÃ³n.

Objetivo:
- Un sistema de debug draw:
  - primitives (line/rect/circle) data-driven
  - un RenderPass â€œDebugOverlayâ€
- Debe poder activarse por CLI/flag y por API IA.

Restricciones:
- PROHIBIDO dibujar debug desde la UI directamente.
- No mezclar gameplay logic con debug.

ValidaciÃ³n:
- Escena canÃ³nica muestra overlays correctos.
- Headless puede emitir â€œdebug dumpâ€ (p. ej. SVG/PNG opcional) o al menos logs de geometrÃ­a.
```

