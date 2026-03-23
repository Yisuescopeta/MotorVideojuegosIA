# Prompt C.2

## Titulo
C.2 â€” â€œImporters + cache determinista + invalidaciÃ³nâ€

## Instrucciones

```text
Antes de cambiar nada:
1) Identifica formatos soportados hoy (imÃ¡genes, audio).
2) Revisa si hay caching o conversiÃ³n previa.

Objetivo:
- Implementar importers (mÃ­nimo: sprites e audio) con cache determinista:
  - input file + import_settings -> artifact (cache key)
  - invalidaciÃ³n por hash
- Definir artifacts como datos (p. ej. atlas pages, decoded audio, etc.) listos para runtime.

Restricciones:
- PROHIBIDO hacer que el runtime haga trabajo pesado que puede hacerse offline.
- MantÃ©n el pipeline extensible (aÃ±adir tile sources/tilemaps despuÃ©s).

ValidaciÃ³n:
- Test: cambiar un import_setting re-genera artifact; no cambiar input no reimporta.
- CLI: `build-assets` genera artifacts sin editor.
```

