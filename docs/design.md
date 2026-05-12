# Frostline Design System for MotorVideojuegosIA Qt Editor

Target visual para el editor `editor_qt` (PySide6). Basado en los bocetos
Frostline Engine: glaciar, profesional, con acentos cyan/azules, modo claro
helado y modo oscuro azul profundo.

## Layout de zonas

```
+------------------------------------------------------------------+
|  Top bar: logo | project | scene | tools | play | build | undo   |
+------+-----------------------------+-----------------------------+
| Left |  Hierarchy (izquierda)      |  Inspector (derecha)        |
| Rail |  - search                   |  - Entity / Component tabs  |
|      |  - tree con vis icons       |  - Transform group          |
| icons|  - selected: cyan           |  - Mesh/Material/Light      |
|      |                             |  - Add Component            |
+------+-----------------------------+-----------------------------+
|  Viewport central (Scene / Game tabs)                            |
|  + floating controls: zoom, reset, frame selected               |
+------------------------------------------------------------------+
|  Project browser (asset cards)  |  Console (pill filters)        |
+------------------------------------------------------------------+
```

### 1. Top bar
Logo + engine name izquierda, combos rounded project/scene, tool group
select/move/rotate/scale, play/pause/stop, build/launch, undo/redo/theme/account.
Shell actual Qt usa grupos visuales separados estilo mockup dentro de la barra
superior, con icon buttons compactos y botones placeholder deshabilitados donde
el backend aun no existe.

### 2. Left rail
Narrow vertical panel con iconos: Hierarchy, Scenes, World, Lighting,
Scripting, Audio, Settings. Active item: cyan glow.

### 3. Hierarchy panel
Search field, tree con visibility icons, selected row cyan highlight.

### 4. Viewport
Scene/Game tabs arriba, floating viewport controls (zoom, reset camera,
frame selected), camera gizmo top-right, grid visible.

### 5. Inspector
Entity/Component segmented tabs, Transform group, secciones plegables para
Sprite/Mesh, Materials, Light, Scripts. Add Component button.
Header actual tambien muestra nombre de entidad, tag/layer y toggle Static
read-only como estado visual del shell.

### 6. Project browser + Console
Asset cards con thumbnails, Add Scene dashed card, grid/list toggle.
Console con pill filters: All, Log, Warning, Error.
Console actual muestra resumen de errores/warnings/logs en cabecera.

## Paletas

### Frostline Dark
| Token | Color |
|---|---|
| `bg_app` | `#04111c` |
| `bg_shell` | `#071827` |
| `panel` | `#0b2032` |
| `panel_glass` | `rgba(9, 30, 48, 0.82)` |
| `border_soft` | `#1d405d` |
| `text` | `#d9ecff` |
| `text_muted` | `#6f8fa8` |
| `accent` | `#32c7ff` |
| `selection` | `#0e4f7c` |
| `danger` | `#ff667d` |
| `success` | `#4ed6a3` |

### Frostline Light
| Token | Color |
|---|---|
| `bg_app` | `#d8ecfb` |
| `bg_shell` | `#eaf6ff` |
| `panel` | `#f3faff` |
| `panel_glass` | `rgba(244, 251, 255, 0.78)` |
| `border_soft` | `#c8e0f2` |
| `text` | `#17314d` |
| `text_muted` | `#7a97ae` |
| `accent` | `#35bdf6` |
| `selection` | `#bce8ff` |
| `danger` | `#ef5b73` |
| `success` | `#3dbf8f` |

## Estados de componentes requeridos

- normal
- hover
- pressed
- checked
- disabled (con tooltip explicativo)
- focus (visible outline)

## Arquitectura

```
Panel -> Signal -> MainWindow slot -> EditorEngineFacade -> EngineAPI
```

Los paneles Qt NO importan `EngineAPI`. Solo ven metodos tipados del facade.
UI-only state (seleccion, hover, tabs, splitter sizes, search text) no se
guarda como datos de escena.

## Archivos de tema

- `editor_qt/theme/frost_dark.qss` — tema oscuro
- `editor_qt/theme/frost_light.qss` — tema claro
- `editor_qt/theme/tokens.py` — tokens Python para runtime switching

## Fases de rediseno

Ver `motorvideojuegosia/ui-redesign-checklist.md` en el pack de skills para
detalle completo:

1. **Theme foundation** — QSS, theme loader, object names, hover/focus/disabled
2. **Layout polish** — top bar groups, left rail, margins, splitter persistence
3. **Hierarchy + Inspector** — search, cyan selection, visibility icons, inspector sections
4. **Project browser** — asset cards, thumbnails, Add Scene card, grid/list toggle
5. **Console** — pill filters, warning/error colors, timestamps, command input
6. **Viewport** — floating controls, zoom, frame selected, entity outline, grid
7. **Professionalization** — model/view, QSignalSpy tests, offscreen tests, fake facade
