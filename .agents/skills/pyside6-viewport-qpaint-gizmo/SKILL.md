---
name: pyside6-viewport-qpaint-gizmo
description: Use this skill when editing the Qt-native viewport, QPainter rendering, camera pan/zoom, viewport overlays, drag/drop asset placement, entity selection, transform gizmos, or scene preview drawing in MotorVideojuegosIA.
---

# PySide6 viewport, QPainter and gizmo skill

## Mission

Keep the viewport responsive, clear and architecturally clean.

The viewport is a Qt-native authoring preview. It is not the game runtime and
must not call raylib, `Game.run()`, or runtime mutation paths directly.

## Current route

`QtSceneViewportPanel` should:

- receive snapshots through `set_snapshot(...)`
- normalize entity viewmodels
- paint with `QPainter`
- manage camera pan/zoom as UI state
- emit selection and transform signals
- emit asset drop signals
- never call `EditorEngineFacade` or `EngineAPI`

## Coordinate system

Keep camera math in exactly named helpers:

```python
def _screen_to_world(self, screen_pos: QPointF) -> tuple[float, float]:
    ...

def _world_to_screen(self, world_x: float, world_y: float) -> tuple[float, float]:
    ...
```

Do not duplicate these formulas. Camera bugs are goblins: feed one and now the
whole viewport smells weird.

## paintEvent structure

Recommended paint order:

```python
def paintEvent(self, event) -> None:
    painter = QPainter(self)
    painter.fillRect(self.rect(), QColor(...))

    painter.save()
    self._apply_camera_transform(painter)
    self._draw_grid(painter)
    self._draw_entities(painter)
    self._draw_gizmo(painter)
    painter.restore()

    self._draw_viewport_overlay(painter)
```

Use `save()` / `restore()` around camera and object transforms.

## QPainter rules

- Create `QPainter` inside `paintEvent`.
- Do not keep a painter as instance state.
- Use `QPen` widths adjusted for zoom where world-space lines must remain readable.
- Cache expensive pixmaps.
- Avoid loading files during every paint.
- Avoid facade/API calls inside paint.
- Avoid `update()` loops unless state changes.
- Draw screen-space overlays after restoring camera transform.

## Pixmap cache

Recommended:

```python
self._pixmap_cache: dict[str, QPixmap] = {}
```

Rules:

- resolve relative asset paths against project root
- cache failed/null pixmaps too, or throttle repeated loads
- clear cache on asset refresh
- draw fallback rect when image is missing
- consider visible-rect culling for many entities

## Entity viewmodels

Normalize before drawing:

```python
{
    "name": "...",
    "x": 0.0,
    "y": 0.0,
    "width": 48.0,
    "height": 48.0,
    "sprite": "assets/player.png",
    "active": True,
}
```

Keep normalization out of paint loops when possible.

## Selection

Viewport emits:

```python
entity_selected = Signal(str)
```

`MainWindow` then refreshes inspector, animator and status.

Viewport may keep `_selected_entity` for drawing selection outline, but it does
not become source of truth.

## Transform drag

Drag has two phases:

1. preview while dragging
2. commit once on mouse release

Signals:

```python
entity_moved = Signal(str, str, str, float, float)
entity_rotated = Signal(str, str, str, float)
entity_scaled = Signal(str, str, str, float, float)
```

`MainWindow` commits through facade.

Do not commit every mouse move unless a transaction/edit-session API exists.

## Gizmo isolation

Keep gizmo math in `editor_qt/gizmo/`.

Viewport may:

- set gizmo mode
- perform hit-test
- call start/update/end drag
- draw gizmo

Gizmo should return `before_state` and `after_state`.

## Frostline viewport chrome

Match the supplied mockup:

- scene image/canvas fills the central area
- overlay controls are rounded pills
- active mode uses cyan
- camera gizmo sits top-right
- small status label shows view mode
- use translucent dark/light chrome over viewport
- controls should not obscure the scene

Draw overlay either with child widgets or QPainter. If using child widgets, keep
them independent from scene data.

## Drag/drop assets

Viewport emits:

```python
asset_dropped = Signal(str, float, float)
```

MainWindow decides:

- prefab -> `facade.instantiate_prefab(...)`
- image -> create entity + Transform + Sprite + Collider
- unsupported -> console warning

Do not mutate the project from the viewport.

## Performance thresholds

If entity count grows:

- cull to visible world bounds
- skip labels under low zoom
- cache static grid layers if needed
- debounce expensive updates
- use simplified drawing while panning/zooming
- avoid per-entity widget children in viewport

## Professional viewport UX ideas

Safe improvements:

- selected entity outline
- hover entity outline
- ghost preview for dragged asset
- reset camera button
- frame selected entity
- zoom percentage dropdown
- grid density changes by zoom
- snap indicator when Ctrl is held
- axis constraint hint when Shift is held
- small warning overlay when scene has no camera/player/etc.

Do not add runtime play behavior into this viewport unless the architecture
explicitly changes.
