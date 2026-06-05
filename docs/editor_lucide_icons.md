# Editor Lucide Icons

Esta guia describe el contrato operativo del sistema de iconos Lucide del editor.

## Recursos

- SVG vendoreados: `engine/editor/resources/icons/vendor/lucide/icons/`
- Licencia upstream vendoreada: `engine/editor/resources/icons/vendor/lucide/LICENSE`
- Copia documental de licencia: `docs/third_party/lucide_LICENSE.txt`
- Manifest interno: `engine/editor/resources/icons/lucide_manifest.json`
- Atlas runtime: `engine/editor/resources/icons/lucide_atlas.png`
- Metadata runtime: `engine/editor/resources/icons/lucide_atlas.json`

## Regenerar el atlas

Instala dependencias de build:

```bash
py -m pip install CairoSVG Pillow resvg-py
```

Luego ejecuta:

```bash
py scripts/build_lucide_icon_atlas.py
```

El script recorre todos los SVG vendoreados, valida que cada alias del manifest apunte a un icono Lucide real y regenera `lucide_atlas.png` + `lucide_atlas.json`.

Notas:

- El runtime del editor no usa SVG.
- El runtime solo carga `PNG + JSON`.
- `CairoSVG` es la ruta preferida de rasterizacion; `resvg-py` queda como fallback de build cuando Cairo no esta disponible en el entorno.

## Anadir o cambiar iconos

1. Vendorea o actualiza el snapshot Lucide bajo `engine/editor/resources/icons/vendor/lucide/`.
2. Si quieres exponer un alias interno nuevo, añade el par `alias -> nombre-lucide` en `lucide_manifest.json`.
3. Regenera el atlas con `py scripts/build_lucide_icon_atlas.py`.
4. Si el alias se convierte en contrato publico del editor, añade la constante correspondiente en `engine/editor/ui_core/icon_names.py` y reexportala desde `engine/editor/ui/icons.py`.

## Alias internos

- Los alias publicos del editor usan `snake_case`.
- Los nombres upstream de Lucide usan `kebab-case`.
- `lucide_manifest.json` es la tabla canonica de traduccion entre ambos.

Ejemplo:

```json
{
  "gear": "settings",
  "tilemap": "grid-3x3",
  "unknown": "circle-question-mark"
}
```

`unknown` usa `circle-question-mark` porque el snapshot upstream vendoreado no incluye `circle-help`.

## Licencia

- Lucide se redistribuye con su texto de licencia intacto.
- Si actualizas el vendor, actualiza tambien `docs/third_party/lucide_LICENSE.txt`.
- No elimines `engine/editor/resources/icons/vendor/lucide/LICENSE` del paquete: forma parte de la redistribucion del snapshot vendoreado.
