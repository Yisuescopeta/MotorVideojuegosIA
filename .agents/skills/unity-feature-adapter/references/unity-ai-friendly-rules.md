# Unity AI-Friendly Rules

Use this reference when a Unity feature could be copied literally but should instead be adapted to this engine's architecture.

## Decision Filter

For each requested Unity feature, answer these questions before coding:

1. What gameplay problem does the Unity feature solve?
2. Which parts are essential behavior and which parts are Unity-specific ergonomics?
3. What is the smallest serializable representation that preserves the behavior?
4. Should this live as data, a system, an event contract, or a `ScriptBehaviour`?
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

1. Unity Manual
2. Unity Scripting API
3. Official Unity tutorials or package docs
4. High-quality community explanations only to clarify gaps

## Deliverable Template

When explaining or implementing the feature, keep this shape:

- Unity behavior summary
- Engine-native mapping
- Serialization/API/editor impact
- Runtime/system impact
- Test or verification plan
