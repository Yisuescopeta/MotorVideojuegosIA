# Runtime input and 2D picking for scripts

Runtime scripts should read mouse and picking data from `context.input` and `context.picking` or `context.render`. They should not import `pyray` or call raylib mouse functions directly.

## Coordinate spaces

- Screen coordinates: physical window coordinates reported by the platform/window loop.
- Viewport coordinates: coordinates inside the rendered game viewport after editor panels, render textures, scaling, letterboxing, or fullscreen transforms are removed.
- World coordinates: game-space coordinates after the active camera transform is applied. If there is no active camera, viewport coordinates are treated as world coordinates.
- UI coordinates: coordinates used by editor/runtime UI systems. UI may share screen or viewport coordinates depending on the UI layer. Gameplay scripts should not assume UI coordinates are the same as world coordinates.

## Runtime input

Scripts receive a per-frame input snapshot:

```python
def on_update(context):
    mouse_world = context.input.mouse_world
    if context.input.left_pressed:
        entity = context.picking.pick_sprite_at_mouse()
```

Available fields:

- `mouse_screen`
- `mouse_viewport`
- `mouse_world`
- `left_down`
- `left_pressed`
- `left_released`
- `key_pressed(name)`

Existing scripts remain compatible. If a script runs without a runtime input service, `context.input` is a null service with zero mouse coordinates and all buttons/keys false.

## Why scripts must not read pyray

Rendering uses `Transform`, `Sprite`, `Animator`, `Polygon2D`, `RenderOrder2D`, viewport scaling, camera state, and sometimes editor/render-texture transforms. Direct `pyray.get_mouse_position()` only reports screen coordinates. A script that rebuilds viewport, camera, or card bounds by hand will drift when the window is scaled, DPI changes, fullscreen is used, or render textures change.

The engine owns coordinate conversion and visual bounds. Scripts ask the engine.

## Coordinate conversion API

Public helpers live in `engine.utils.viewport`:

- `screen_to_viewport(screen_x, screen_y, viewport_rect=None, viewport_size=None)`
- `viewport_to_world(viewport_x, viewport_y, world=None, viewport_size=None, camera_profile_id=None, camera_entity=None)`
- `screen_to_world(screen_x, screen_y, world=None, viewport_size=None, camera_profile_id=None, viewport_rect=None, camera_entity=None)`

Use these helpers in engine/runtime code. Gameplay scripts should usually use `context.input.mouse_world`.

## Visual bounds

Runtime render queries expose:

- `get_visual_bounds(entity)`
- `get_entity_visual_bounds(entity_name)`

Bounds v1 is an AABB:

- `Sprite`: uses explicit `Sprite.width` and `Sprite.height`; if missing, uses slice/texture size when available. Sprites without a real visual size do not participate in picking.
- `Animator`: uses the current slice, then `frame_width` and `frame_height`.
- `Polygon2D`: uses transformed polygon points.
- Rotation: AABB is conservative; v1 does not do fine rotated-shape picking for sprites.
- Negative scale: bounds are normalized with `min/max`.

## Picking

Runtime picking exposes:

- `pick_sprite_at_world(x, y, layer=None)`
- `pick_sprite_at_mouse(layer=None)`

Picking respects visual order by iterating render order from top to bottom:

- render pass
- sorting layer
- order in layer
- depth
- entity id

Inactive entities, disabled transforms, disabled sprites, and visuals without bounds are ignored.

## Card click example

```python
def on_update(context):
    state = context.state

    hovered = context.picking.pick_sprite_at_mouse()
    state.hovered_card_name = hovered.name if hovered else None

    if context.input.left_pressed:
        clicked = context.picking.pick_sprite_at_mouse()
        if clicked is not None:
            state.selected_card_name = clicked.name
```

Keep hover and selection separate. Hover is the entity under the mouse this frame. Selection changes only on click.
