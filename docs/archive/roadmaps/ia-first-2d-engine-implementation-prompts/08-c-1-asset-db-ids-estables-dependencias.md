# Prompt C.1

## Titulo
C.1 â€” â€œAsset DB con IDs estables y dependenciasâ€

## Instrucciones

```text
Antes de cambiar nada:
1) Analiza cÃ³mo se referencian assets hoy (paths, handles, etc.).
2) Identifica hot-reload actual y cÃ³mo invalida/carga recursos.

Objetivo:
- Crear un Asset Database:
  - asigna IDs estables a cada asset (GUID o content-hash; decide y justifica).
  - guarda metadatos: tipo, hash, dependencias, import_settings (versionados).
  - expone API: resolve(id) -> runtime asset, get_meta(id).

Restricciones:
- PROHIBIDO depender de rutas absolutas.
- Debe funcionar en headless/CLI.
- No romper el sistema actual: crea una capa de compatibilidad si es necesario.

ValidaciÃ³n:
- Test: mover/renombrar un fichero de asset no rompe la referencia si el ID es estable (si el diseÃ±o lo permite).
- Reporte: listar assets y dependencias.
```

