# Prompt F.1

## Titulo
F.1 â€” â€œTilemap como modelo serializable (layers, tileset, metadata)â€

## Instrucciones

```text
Antes de cambiar nada:
1) Verifica si ya existe algo parecido a tilemaps (aunque sea parcial) o si hoy se hace con sprites sueltos.
2) Revisa el Asset DB: cÃ³mo referenciar tilesets/atlases.

Objetivo:
- Definir e implementar un componente Tilemap serializable:
  - grid config (cell size, orientaciÃ³n; iso/hex opcional pero no obligatorio)
  - mÃºltiples layers
  - refs a tileset/tilesource por asset ID
  - metadata por tile (flags, tags, custom int/str)

Restricciones:
- PROHIBIDO que el tilemap exista solo â€œporque el editor lo pintaâ€.
- La API IA debe poder crear/modificar tilemaps sin UI.

ValidaciÃ³n:
- Roundtrip: cargar tilemap, modificar un tile por API, guardar, recargar.
- ValidaciÃ³n de schema y migraciÃ³n cubren tilemaps.
```

