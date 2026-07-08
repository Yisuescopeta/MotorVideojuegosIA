# ADR-0002 - Runtime input and 2D picking API for scripts

## Estado

Aceptado

## Contexto

Runtime scripts were reading `pyray` mouse state directly and reconstructing visual bounds by hand. That is not stable because render uses engine-owned viewport conversion, camera state, `Transform`, `Sprite`, `Animator`, `Polygon2D`, and `RenderOrder2D`.

## Decision

Add engine-owned runtime services exposed through `ScriptBehaviourContext`:

- `context.input` for mouse screen/viewport/world, left button state, and minimal key presses.
- `context.render` and `context.picking` for visual bounds and topmost 2D picking.

Coordinate conversion lives in `engine.utils.viewport`. Visual bounds and render-order picking live in the render/query path, not in game scripts.

## Consequences

- Scripts no longer need to import `pyray` for gameplay input.
- Picking follows the same visual order as rendering.
- Existing scripts remain compatible through null services.
- Bounds v1 is AABB-based; sprite rotation does not get exact shape picking yet.

## Alternatives considered

- Patch solitaire hitboxes only: rejected because it keeps the architecture bug.
- Duplicate camera and viewport math in scripts: rejected because it creates drift between input and render.
- Full collision-based picking: deferred because the immediate problem is visual picking for runtime scripts, not physics queries.
