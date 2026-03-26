# Prompt D.3

## Titulo
D.3 â€” â€œRender targets y composiciÃ³nâ€

## Instrucciones

```text
Antes de cambiar nada:
1) Verifica si hay soporte de render-to-texture o framebuffer en el backend actual.
2) Identifica cÃ³mo se renderiza el viewport del editor.

Objetivo:
- Implementar RenderTarget API:
  - crear, set, clear, draw-to-target, luego componer al back buffer.
- AÃ±adir al menos 2 usos:
  1) minimap (o preview) simple
  2) selecciÃ³n/highlight (mask / outline) o debug overlay compositado

Restricciones:
- PROHIBIDO acoplarlo a UI: la UI solo muestra el resultado.
- Debe funcionar en runtime y, si hay backend, en editor viewport.

ValidaciÃ³n:
- Tests de â€œno-crashâ€ + ejemplo reproducible.
- MÃ©tricas: coste del pass adicional reportado.
```

