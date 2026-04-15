# Prompt E.3

## Titulo
E.3 â€” â€œCCD y fast movers: polÃ­tica explÃ­cita + testsâ€

## Instrucciones

```text
Antes de cambiar nada:
1) Identifica el timestep del motor y cÃ³mo se calcula dt.
2) Determina si hay objetos rÃ¡pidos (â€œbulletsâ€) y cÃ³mo colisionan hoy.

Objetivo:
- Definir una polÃ­tica de CCD:
  - quÃ© componentes la activan,
  - quÃ© coste/perf implica (documentado),
  - fallback si el backend no soporta CCD real.
- AÃ±adir test de â€œno tunnelingâ€ (escenario bala vs pared).

Restricciones:
- No hacer promesas falsas: si no hay CCD real, documenta lÃ­mites.
- PROHIBIDO que la soluciÃ³n sea â€œsubir fps en UIâ€: debe ser runtime + datos.

ValidaciÃ³n:
- Test automatizado donde un objeto rÃ¡pido no atraviesa un collider.
- MÃ©tricas del coste adicional visibles.
```

