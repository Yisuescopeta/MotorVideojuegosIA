# Godot AI-Friendly Rules

Use this reference when a Godot feature could be copied literally but should instead be adapted to this engine's architecture.

## Decision Filter

For each requested Godot feature, answer these questions before coding:

1. What gameplay problem does the Godot feature solve?
2. Which parts are essential behavior and which parts are Godot-specific ergonomics (Node tree, `@export`, editor integration)?
3. What is the smallest serializable representation that preserves the behavior?
4. Should this live as data (component), a system, an event contract (EventBus), or a `ScriptBehaviour`?
5. How will another AI discover and reuse this feature from code or JSON alone?

## Preferred Implementation Order

1. Reuse an existing component or system if the current engine already expresses the behavior.
2. Extend an existing component schema if the new behavior is a natural fit.
3. Add a new component plus system when the feature becomes part of the engine contract.
4. Fall back to `ScriptBehaviour` only for narrow gameplay logic that should remain project-specific.

## What "AI-Friendly" Means Here

- The feature is discoverable from filenames, class names, and JSON fields.
- The runtime behavior follows obvious update paths.
- The data model is explicit enough for save/load and editor inspection.
- The feature can be configured without reading hidden global state.
- The implementation avoids surprising coupling between unrelated systems.

## Source Priority

Use sources in this order when browsing:

1. Godot Manual (class reference at `docs.godotengine.org/en/stable/classes/`)
2. Godot source code (C++ headers for API, `.cpp` for implementation details)
3. Official Godot tutorials or step-by-step guides
4. High-quality community explanations only to clarify gaps

## Deliverable Template

When explaining or implementing the feature, keep this shape:

- Godot behavior summary (what it does, not how Godot implements it)
- Engine-native mapping (component + system + resource + event)
- Serialization impact (what goes in scene JSON)
- API impact (what EngineAPI methods are needed)
- Runtime/system impact (which phase: update/physics/render)
- Test or verification plan

## Godot-Specific Considerations

### Node Tree vs ECS
- Godot uses inheritance: `Node` → `Node2D` → `Sprite2D`
- Motor uses composition: Entity + `Sprite` component + `Transform` component
- **DO NOT** replicate Godot's class hierarchy. A `Sprite2D` is not a subclass of `Node2D` — it's an entity that happens to have both a `Sprite` and `Transform` component.

### Signals vs EventBus
- Godot signals are per-object: `my_sprite.body_entered.connect(callback)`
- Motor uses EventBus: subscribe to `PHYSICS_BODY_ENTERED` and filter by `entity_id`
- **DO NOT** implement per-entity signal connections. Use global EventBus + entity_id filtering.

### Resources vs JSON Data
- Godot Resources (`.tres`, `.res`) are self-contained serializable assets
- Motor resources are JSON-serializable dataclasses
- **DO** make resources explicit, versioned, and JSON-serializable

### Scenes vs Scene JSON
- Godot `.tscn` files contain entire node hierarchies with properties
- Motor scene JSON v2 contains entities with component data
- **DO** follow the existing scene JSON schema when adding new entity types

### Editor Integration
- Godot's `@tool` scripts and editor plugins are out of scope
- Motor uses CLI (`motor`) and EngineAPI for authoring
- **DO** expose authoring through EngineAPI or CLI, not editor-specific paths
