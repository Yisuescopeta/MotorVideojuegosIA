# Prompt D.1

## Titulo
D.1 â€” â€œRender layers + render passes (render graph mÃ­nimo)â€

## Instrucciones

```text
Antes de cambiar nada:
1) Inspecciona el renderer 2D actual: cÃ³mo dibuja sprites, cÃ³mo ordena, cÃ³mo maneja cÃ¡mara.
2) Identifica si existe ya nociÃ³n de layers/sorting.

Objetivo:
- DiseÃ±ar e implementar un RenderGraph mÃ­nimo:
  - define passes: World, Overlay, Debug.
  - define RenderLayer/SortKey en el modelo serializable.
- El runtime ejecuta el RenderGraph; el editor viewport lo reutiliza.

Restricciones:
- PROHIBIDO introducir ordenaciÃ³n dentro de UI; debe ser modelo.
- MantÃ©n compatibilidad con lo existente (puede haber defaults).

ValidaciÃ³n:
- Escena con 3 layers y solapes: orden correcto y reproducible.
- MÃ©tricas: batches/draw calls expuestas al profiler/monitor.
```

