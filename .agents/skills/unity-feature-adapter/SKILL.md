---
name: unity-feature-adapter
description: Research and adapt Unity features for this IA-first 2D engine. Use whenever the prompt contains the word "Unity", even if the request is brief or ambiguous. Also use when a prompt asks to add a Unity feature, characteristic, mechanic, component, system, API, workflow, or behavior, including prompts in Spanish such as "caracteristica de Unity", "mecanica de Unity", "componente de Unity", or "hazlo como en Unity". Also trigger on terms such as GameObject, MonoBehaviour, prefab, scene, animation state machine, collider, rigidbody, trigger, camera, input, tilemap, ScriptableObject, or "make it work like Unity". Search the web before implementing, understand how the Unity feature behaves, and translate it into explicit, serializable, AI-friendly engine structures instead of copying Unity's hidden magic.
---

# Unity Feature Adapter

Research the referenced Unity feature first, then implement the same gameplay intent using this engine's explicit ECS, JSON, event, and API patterns.

## Workflow

1. Identify the Unity feature being requested.
2. Search the web before coding.
3. Prefer Unity Manual, Unity Scripting API, and official Unity learn material as primary sources.
4. Extract the feature contract:
   - What the feature does for gameplay.
   - What data it stores.
   - What lifecycle or events drive it.
   - What editor-facing configuration users expect.
   - What runtime side effects or edge cases matter.
5. Restate that contract in engine terms before changing code.
6. Map it onto the engine using explicit data and systems:
   - `engine/components/` for serializable state.
   - `engine/systems/` for frame processing.
   - `engine/events/` or rules for event-driven behavior.
   - `engine/scenes/`, `levels/*.json`, and API surface for authoring.
   - `ScriptBehaviour` only when a reusable engine primitive is not justified.
7. Implement the smallest engine change that preserves the Unity-facing behavior.
8. Add or update tests when behavior becomes part of the engine contract.

## Translation Rules

- Preserve behavior, not Unity class names.
- Prefer one explicit component plus one system over reflection-heavy or callback-heavy designs.
- Prefer serializable JSON fields over hidden runtime state.
- Prefer deterministic update order over implicit magic methods.
- Prefer engine events, rules, and declarative config over ad hoc hardcoded branches.
- Expose authoring through level JSON, inspector-visible fields, or engine API when relevant.
- Keep features composable so an AI can combine them without reverse-engineering hidden coupling.

## Engine Mapping

Translate Unity requests into the closest engine primitives:

- `GameObject` -> entity in `World` or scene JSON entity entry.
- `Transform` -> `Transform` component.
- `MonoBehaviour` -> `ScriptBehaviour` or a new explicit engine system when the behavior is core.
- `Prefab` -> reusable serialized scene/entity pattern, not opaque runtime cloning magic.
- `Scene` -> `engine/scenes/` plus level JSON.
- `Collider` / `Trigger` / `Rigidbody` -> collider, collision, and rigidbody components/systems.
- Unity events/callbacks -> event bus, rule actions, or explicit lifecycle hooks.
- Inspector fields -> serializable component fields or `public_data`.

If a Unity feature does not map cleanly, introduce a minimal engine-native abstraction and explain why it is better for this IA-first architecture.

## Output Shape

When using this skill, structure the work in this order:

1. Name the Unity feature being adapted.
2. Summarize the researched behavior in plain language.
3. Explain the engine-native design.
4. List the files or subsystems to change.
5. Implement the code.
6. Verify with tests, a focused repro, or both.

## AI-Friendly Constraints

- Do not reproduce Unity editor magic, reflection, or undocumented side effects unless they are essential to gameplay.
- Do not hide data in transient Python objects when it should survive save/load, play/stop, or hot reload.
- Do not create broad abstractions "for future Unity parity" without a concrete use in the current request.
- Prefer names and schemas that are easy for another AI to infer from code search.

## Reference

Read [references/unity-ai-friendly-rules.md](references/unity-ai-friendly-rules.md) when the requested Unity feature is large, ambiguous, or could be implemented in several ways.
