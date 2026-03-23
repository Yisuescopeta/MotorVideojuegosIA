# Prompt A.2

## Titulo
A.2 â€” â€œHarness de pruebas headless + golden runs de simulaciÃ³nâ€

## Instrucciones

```text
Antes de cambiar nada:
1) Localiza cÃ³mo se ejecuta el motor en modo CLI/headless y cÃ³mo se carga/ejecuta una escena.
2) Localiza el loop de simulaciÃ³n (EDIT/PLAY/PAUSED/STEPPING) y cÃ³mo se avanza el tiempo.

Objetivo:
- AÃ±adir un â€œharnessâ€ de pruebas que ejecute escenas en headless durante N frames y produzca:
  a) mÃ©tricas (fps/tiempo por frame/contadores),
  b) un hash del estado serializable (o un resumen determinista),
  c) logs estructurados por frame (mÃ­nimo: frame index, dt, eventos crÃ­ticos).

Alcance:
- No cambiar gameplay; solo instrumentaciÃ³n y test harness.
- AÃ±adir al menos 2 escenas/escenarios canÃ³nicos de test (pueden ser JSON ya existentes o copias mÃ­nimas).

Restricciones:
- PROHIBIDO depender de UI o de input humano.
- Si ya existe timeline/snapshots, reutilÃ­zalo; no lo reescribas.
- Si existe un sistema de serializaciÃ³n, Ãºsalo para el estado/hashes.

ValidaciÃ³n:
- Un comando (script) o test automatizado que:
  1) corre la escena canÃ³nica 200 frames,
  2) genera un reporte,
  3) falla si el resultado cambia sin actualizar el â€œgoldenâ€.
- Incluye documentaciÃ³n de cÃ³mo regenerar golden de forma explÃ­cita.
```

