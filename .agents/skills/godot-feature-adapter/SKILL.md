---
name: godot-feature-adapter
description: Research and adapt Godot features for this IA-first 2D engine. Use whenever the prompt contains the word "Godot", even if the request is brief or ambiguous. Also use when a prompt asks to add a Godot feature, characteristic, mechanic, component, system, API, workflow, or behavior, including prompts in Spanish such as "caracteristica de Godot", "mecanica de Godot", "componente de Godot", "nodo de Godot", or "hazlo como en Godot". Also trigger on terms such as Node, SceneTree, AnimationPlayer, CharacterBody2D, Area2D, RigidBody2D, TileMap, TileSet, Sprite2D, AnimatedSprite, Resource, Signal, @export, _process, _physics_process, or "make it work like Godot". Research Godot source code and/or docs before implementing, understand how the Godot feature behaves, and translate it into explicit, serializable, AI-friendly engine structures instead of copying Godot's hidden magic.
---

# Godot Feature Adapter

Research the referenced Godot feature first, then implement the same gameplay intent using this engine's explicit ECS, JSON, event, and API patterns.

## Workflow

1. Identify the Godot feature being requested.
2. Search Godot docs (`docs.godotengine.org`) and source code before coding.
3. Prefer Godot Manual (Class Reference) and official tutorials as primary sources.
4. Extract the feature contract:
   - What the feature does for gameplay.
   - What data it stores (properties, resources).
   - What lifecycle or events drive it (`_process`, `_physics_process`, signals).
   - What editor-facing configuration users expect (`@export` vars).
   - What runtime side effects or edge cases matter.
5. Restate that contract in engine terms before changing code.
6. Map it onto the engine using explicit data and systems:
   - `engine/components/` for serializable state.
   - `engine/systems/` for frame processing.
   - `engine/events/` for event-driven behavior (signals → EventBus).
   - `engine/scenes/`, `levels/*.json`, and API surface for authoring.
   - `ScriptBehaviour` only when a reusable engine primitive is not justified.
7. Implement the smallest engine change that preserves the Godot-facing behavior.
8. Add or update tests when behavior becomes part of the engine contract.

## Translation Rules

- Preserve behavior, not Godot class names.
- Prefer one explicit component plus one system over reflection-heavy or callback-heavy designs.
- Prefer serializable JSON fields over hidden runtime state.
- Prefer deterministic update order over implicit magic methods (`_process`, `_physics_process`).
- Prefer engine events, EventBus, and declarative config over ad hoc hardcoded branches.
- Expose authoring through level JSON, inspector-visible fields, or engine API when relevant.
- Keep features composable so an AI can combine them without reverse-engineering hidden coupling.

## Engine Mapping

Translate Godot requests into the closest engine primitives:

- `Node` → entity in `World` or scene JSON entity entry.
- `Node2D` → Entity + `Transform` component.
- `CharacterBody2D` → Entity + `CharacterBody` component + character movement system.
- `Area2D` → Entity + `Area` (trigger) component + trigger system.
- `StaticBody2D` → Entity + `StaticBody` component.
- `RigidBody2D` → Entity + `Rigidbody2D` component + rigidbody system.
- `Sprite2D` → Entity + `Sprite` component + sprite render system.
- `AnimatedSprite2D` → Entity + `AnimatedSprite` component (extends Sprite) + animation system.
- `CollisionShape2D` → `shape` field in existing collider component.
- `TileMap` → `engine/components/tilemap.py` (already exists, partial).
- `TileSet` → reusable tile data resource.
- `Camera2D` → Entity + `Camera2D` component + camera system.
- `Timer` → Entity + `Timer` component (already exists).
- `Marker2D` → Entity + `Marker2D` component (already exists).
- `AnimationPlayer` → `animation_player` system + `AnimationClip` resources.
- `Path2D/PathFollow2D` → Entity + `PathFollower` component + path system.
- `ParallaxBackground/Parallax2D` → `ParallaxLayer` component + parallax system.
- `CanvasLayer` → Render layer system.
- `Resource` subclasses → serializable data in `engine/resources/`.
- Godot signals → EventBus events in `engine/events/`.
- Godot `@export var` → serializable component field.
- Godot `_process(delta)` → explicit system with update phase registration.
- Godot `_physics_process(delta)` → explicit system with physics phase registration.
- Godot `SceneTree` groups → `engine/ecs/group_operations.py` (already exists).
- Godot `Input` singleton → `engine/input/` input manager.
- Godot `InputEvent` subclasses → events on EventBus.

If a Godot feature does not map cleanly, introduce a minimal engine-native abstraction and explain why it is better for this IA-first architecture.

## Output Shape

When using this skill, structure the work in this order:

1. Name the Godot feature being adapted.
2. Summarize the researched behavior in plain language.
3. Explain the engine-native design.
4. List the files or subsystems to change.
5. Implement the code.
6. Verify with tests, a focused repro, or both.

## AI-Friendly Constraints

- Do not reproduce Godot editor magic, `@tool` scripts, or undocumented side effects unless they are essential to gameplay.
- Do not hide data in transient Python objects when it should survive save/load, play/stop, or hot reload.
- Do not create broad abstractions "for future Godot parity" without a concrete use in the current request.
- Prefer names and schemas that are easy for another AI to infer from code search.

## Reference

Read [references/godot-mappings.md](references/godot-mappings.md) for the complete Godot-to-Motor mapping table.
Read [references/godot-ai-friendly-rules.md](references/godot-ai-friendly-rules.md) for the decision filter and deliverable template.
