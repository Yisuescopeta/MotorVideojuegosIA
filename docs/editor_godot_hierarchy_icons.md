# Editor Godot Hierarchy Icons

Guia operativa del pack Godot especializado para iconos semanticos de
Hierarchy. Lucide sigue siendo el sistema principal para acciones generales de
UI.

## Fuente

- Repositorio upstream: <https://github.com/godotengine/godot/tree/master/editor/icons>
- Commit importado: `72cc0fc9a75bf041e84b9d37e7e31e17cb114a9e`
- Guia oficial de iconos Godot: <https://docs.godotengine.org/en/stable/engine_details/editor/creating_icons.html>

## Recursos locales

- SVG vendoreados: `engine/editor/resources/icons/godot/svg/`
- Manifest: `engine/editor/resources/icons/godot/godot_hierarchy_manifest.json`
- Atlas runtime: `engine/editor/resources/icons/godot/godot_hierarchy_atlas.png`
- Metadata runtime: `engine/editor/resources/icons/godot/godot_hierarchy_atlas.json`
- Licencia: `docs/third_party/godot_editor_icons_LICENSE.txt`

## Iconos importados

- `entity` -> `Node.svg`
- `node2d` -> `Node2D.svg`
- `sprite` -> `Sprite2D.svg`
- `camera` -> `Camera2D.svg`
- `tilemap` -> `TileMap.svg`
- `collider` -> `CollisionShape2D.svg`
- `rigidbody` -> `RigidBody2D.svg`
- `audio` -> `AudioStreamPlayer2D.svg`
- `animation` -> `AnimationPlayer.svg`
- `canvas` -> `CanvasLayer.svg`
- `ui_button` -> `Button.svg`
- `light` -> `DirectionalLight2D.svg`
- `particles` -> `CPUParticles2D.svg`

## Sustituciones documentadas

- `light` pide semantica `Light2D`, pero el snapshot importado usa
  `DirectionalLight2D.svg`. La sustitucion queda trazada en
  `godot_hierarchy_manifest.json` via `substitution_from`.

## Regenerar el atlas

Instala dependencias de build si faltan:

```bash
py -m pip install Pillow CairoSVG resvg-py
```

Luego ejecuta:

```bash
py scripts/build_godot_hierarchy_icon_atlas.py
```

Notas:

- El runtime del editor no carga SVG.
- El runtime solo consume `PNG + JSON`.
- `CairoSVG` es preferido; `resvg-py` queda como fallback de build.
- El atlas conserva color original de Godot. No se blanquea ni se recolorea en
  el pipeline.

## Anadir iconos nuevos

1. Vendorea el SVG desde `godotengine/godot/editor/icons`.
2. Anade o ajusta la entrada en `godot_hierarchy_manifest.json`.
3. Regenera el atlas con `py scripts/build_godot_hierarchy_icon_atlas.py`.
4. Si el alias pasa a contrato publico, agrega la constante correspondiente en
   `engine/editor/ui_core/icon_names.py` y reexportala desde `engine/editor/ui/`.

## Fallback runtime

Resolucion en `draw_icon()`:

1. Para aliases semanticos de Hierarchy, intenta Godot.
2. Si Godot no resuelve, intenta Lucide.
3. Si Lucide tampoco resuelve, usa el fallback primitivo actual.
4. Si no existe ninguna ruta, sale sin crash.

Esto mantiene Lucide para `play`, `pause`, `stop`, `search`, `settings`,
`trash`, `plus` y el resto de acciones generales del editor.
