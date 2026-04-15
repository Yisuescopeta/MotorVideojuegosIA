# Prompt E.2

## Titulo
E.2 â€” â€œIntegraciÃ³n Box2D opcional (scope mÃ­nimo)â€

## Instrucciones

```text
Antes de cambiar nada:
1) EvalÃºa dependencias viables en Python (bindings) y cÃ³mo se distribuirÃ­an en bundling.
2) Revisa la interfaz PhysicsBackend definida en E.1 y ajusta sÃ³lo si es imprescindible.

Objetivo:
- AÃ±adir un backend Box2D con alcance mÃ­nimo:
  - dynamic/static bodies
  - shapes bÃ¡sicas (box/circle/polygon simple)
  - fricciÃ³n/restituciÃ³n y gravedad
  - step fijo y contact callbacks -> eventos del motor

Restricciones:
- PROHIBIDO exigir Box2D como dependencia obligatoria del motor.
- Debe existir una ruta â€œsin Box2Dâ€ (legacy backend).
- No depender de UI.

ValidaciÃ³n:
- Escena canÃ³nica: stack de cajas y una bola -> resultados reproducibles (misma mÃ¡quina).
- Benchmark: coste por step reportado.
```

