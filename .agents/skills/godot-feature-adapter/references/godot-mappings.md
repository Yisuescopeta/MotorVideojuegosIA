# Godot → Motor Mapping Table

Complete mapping from Godot Engine concepts to MotorVideojuegosIA equivalents.

## Source Priority

1. Godot source code (C++ headers for API, `.cpp` for implementation)
2. Godot Manual (`docs.godotengine.org/en/stable/classes/`)
3. Godot Scripting API reference
4. Official Godot tutorials
5. High-quality community explanations (only to clarify gaps)

---

## Core Concepts

| Godot Concept | Motor Concept | Notes |
|---------------|---------------|-------|
| `Node` (base class) | Entity in `World` | No inheritance tree needed — components handle specialization |
| `Node.name` | Entity name in scene JSON | |
| `Node.owner` | Scene root reference | |
| `Node.get_parent()` | `SceneManager.get_entity_parent(entity_id)` | |
| `Node.get_children()` | `SceneManager.get_entity_children(entity_id)` | |
| `Node.add_child(node)` | `SceneManager.add_entity_to_scene()` | |
| `Node.remove_child(node)` | `SceneManager.remove_entity_from_scene()` | |
| `Node.queue_free()` | `SceneManager.remove_entity(entity_id)` | |
| `Node.is_inside_tree()` | Entity exists in active World | |
| Scene (`.tscn` file) | Scene JSON in `engine/scenes/` | Schema v2 |
| PackedScene (`.tscn` resource) | Reusable scene pattern/template | |
| `SceneTree` | `engine/ecs/group_operations.py` | Already exists |
| `SceneTree.paused` | `Game.paused` | |
| `SceneTree.create_timer()` | Create entity with `Timer` component | |
| `Engine.get_process_delta_time()` | `Time.delta_time` | |

---

## 2D Nodes

| Godot Class | Motor | Status |
|------------|-------|--------|
| `Node2D` | `Transform` component | ✅ exists |
| `Sprite2D` | `Sprite` component + `sprite_render_system` | ❌ missing |
| `AnimatedSprite2D` | `AnimatedSprite` component (extends Sprite) | ❌ missing |
| `CharacterBody2D` | `CharacterBody` component + `character_movement_system` | ❌ missing |
| `Area2D` | `Area` component (trigger mode in collider) | ❌ missing |
| `StaticBody2D` | `StaticBody` component | ❌ missing |
| `RigidBody2D` | `Rigidbody2D` component + `rigidbody_system` | ❌ missing |
| `AnimatableBody2D` | `AnimatableBody` component | ❌ missing |
| `CollisionShape2D` | `shape` field in Collider component | 🔶 partial |
| `CollisionPolygon2D` | `polygon_points` field in Collider | 🔶 partial |
| `TileMapLayer` | Extension of `engine/components/tilemap.py` | 🔶 partial |
| `Camera2D` | `Camera2D` component | ❌ missing |
| `Path2D` | `Path` component | ❌ missing |
| `PathFollow2D` | `PathFollower` component + `path_follow_system` | ❌ missing |
| `Parallax2D` | `ParallaxLayer` component + `parallax_system` | ❌ missing |
| `ParallaxBackground` | `ParallaxBackground` component (container) | ❌ missing |
| `Marker2D` | `Marker2D` component | ✅ exists |
| `RemoteTransform2D` | `TransformBinding` component | ❌ missing |
| `BackBufferCopy` | Render-to-texture system | ❌ missing |
| `CanvasModulate` | `CanvasModulate` component | ❌ missing |
| `Light2D` | `Light2D` component | ❌ missing |
| `PointLight2D` | Extends `Light2D` | ❌ missing |
| `DirectionalLight2D` | Extends `Light2D` | ❌ missing |
| `LightOccluder2D` | `LightOccluder` component | ❌ missing |
| `AudioStreamPlayer2D` | `AudioSource` component (2D positional) | ❌ missing |
| `AudioListener2D` | `AudioListener` component | ❌ missing |
| `Line2D` | `Line2D` component | ❌ missing |
| `Polygon2D` | `Polygon2D` component | ❌ missing |
| `NavigationAgent2D` | `engine/navigation/` navigation system | ❌ missing |
| `NavigationRegion2D` | `NavigationRegion` component | ❌ missing |
| `NavigationObstacle2D` | `NavigationObstacle` component | ❌ missing |
| `CPUParticles2D` | `Particles2D` component | ❌ missing |
| `GPUParticles2D` | Same but GPU-accelerated | ❌ missing |
| `RayCast2D` | `query_physics_ray` in EngineAPI | ✅ exists |
| `ShapeCast2D` | `query_physics_shape_cast` (if added) | 🔶 partial |
| `Joint2D` subclasses | `Joint` components + joint system | ❌ missing |
| `PinJoint2D` | `PinJoint` component | ❌ missing |
| `GrooveJoint2D` | `GrooveJoint` component | ❌ missing |
| `DampedSpringJoint2D` | `SpringJoint` component | ❌ missing |
| `VisibleOnScreenNotifier2D` | `ViewportNotifier` component | ❌ missing |
| `VisibleOnScreenEnabler2D` | Extends ViewportNotifier | ❌ missing |
| `TouchScreenButton` | `TouchButton` component (mobile) | ❌ missing |

---

## Resources

| Godot Resource | Motor | Notes |
|---------------|-------|-------|
| `Resource` (base) | Serializable dataclass | |
| `Texture2D` | `engine/resources/texture.py` | Image resource |
| `CompressedTexture2D` | Same with compression flag | |
| `AtlasTexture` | `TextureAtlas` resource | Region within atlas |
| `TileSet` | TileSet resource + TileMap component | 🔶 partial |
| `TileSetSource` | Source definition in TileSet | |
| `TileData` | Individual tile data | |
| `Animation` | `AnimationClip` resource | Keyframe list |
| `AnimationLibrary` | `AnimationLibrary` resource | Named clip collection |
| `SpriteFrames` | `SpriteSheet` resource | Frames + timings |
| `Curve2D` | `Curve` resource | Points + interpolation |
| `Curve` (1D) | `Curve1D` resource | |
| `Gradient` | `Gradient` resource | |
| `PackedScene` | Scene JSON template | |
| `Shader` | `engine/shaders/` | |
| `ShaderMaterial` | `Material` component referencing shader | |
| `PhysicsMaterial` | `PhysicsMaterial` resource | friction, bounce, absorb |
| `AudioStream` subclasses | `AudioClip` resource | |
| `AudioStreamWAV` | WAV clip resource | |
| `AudioStreamMP3` | MP3 clip resource | |
| `AudioStreamOggVorbis` | OGG clip resource | |
| `Font` | `engine/resources/font.py` | |
| `FontFile` | TTF/OTF font file | |
| `DynamicFont` | Rendered font resource | |
| `StyleBox` subclasses | `StyleBox` resource (UI) | |
| `InputEvent` subclasses | Events on EventBus | Not resources per se |
| `InputEventAction` | `InputAction` event | |
| `InputEventKey` | `KeyEvent` with key field | |
| `InputEventMouseButton` | `MouseButtonEvent` | |
| `InputEventMouseMotion` | `MouseMotionEvent` | |
| `InputEventJoypadButton` | `JoypadButtonEvent` | |
| `InputEventJoypadMotion` | `JoypadMotionEvent` | |
| `NavigationMesh` | `engine/navigation/navmesh.py` | |
| `NavigationPolygon` | 2D navmesh | |
| `OccluderPolygon2D` | `OccluderShape` resource | |
| `Theme` | `Theme` resource (UI styling) | |

---

## Signals → EventBus Events

| Godot Signal (source class) | Motor Event | Parameters |
|---------------------------|-------------|------------|
| `body_entered(body: Node2D)` (Area2D) | `PHYSICS_BODY_ENTERED` | `entity_id`, `other_entity_id` |
| `body_exited(body: Node2D)` (Area2D) | `PHYSICS_BODY_EXITED` | `entity_id`, `other_entity_id` |
| `area_entered(area: Area2D)` | `PHYSICS_AREA_ENTERED` | `entity_id`, `other_entity_id` |
| `area_exited(area: Area2D)` | `PHYSICS_AREA_EXITED` | `entity_id`, `other_entity_id` |
| `body_shape_entered(...)` | `PHYSICS_BODY_SHAPE_ENTERED` | `entity_id`, `shape_index`, `other_entity_id`, `other_shape_index` |
| `body_shape_exited(...)` | `PHYSICS_BODY_SHAPE_EXITED` | same |
| `area_shape_entered(...)` | `PHYSICS_AREA_SHAPE_ENTERED` | same |
| `area_shape_exited(...)` | `PHYSICS_AREA_SHAPE_EXITED` | same |
| `timeout()` (Timer) | `TIMER_TIMEOUT` | `entity_id` | ✅ exists |
| `started()` (Timer) | `TIMER_STARTED` | `entity_id` | ✅ exists |
| `stopped()` (Timer) | `TIMER_STOPPED` | `entity_id` | ✅ exists |
| `animation_started(name)` (AnimationPlayer) | `ANIMATION_STARTED` | `entity_id`, `clip_name` |
| `animation_finished(name)` (AnimationPlayer) | `ANIMATION_FINISHED` | `entity_id`, `clip_name` |
| `animation_changed(name, name)` (AnimationPlayer) | `ANIMATION_CHANGED` | `entity_id`, `old_clip`, `new_clip` |
| `animation_libraries_updated()` | `ANIMATION_LIBRARIES_UPDATED` | |
| `finished()` (Tween) | `TWEEN_FINISHED` | `tween_id` |
| `loop_finished()` (Tween) | `TWEEN_LOOP_FINISHED` | `tween_id` |
| `step_finished(idx)` (Tween) | `TWEEN_STEP_FINISHED` | `tween_id`, `step_index` |
| `pressed()` (BaseButton) | `UI_BUTTON_PRESSED` | `entity_id` |
| `toggled(state)` (BaseButton) | `UI_BUTTON_TOGGLED` | `entity_id`, `state` |
| `button_down()` / `button_up()` | `UI_BUTTON_DOWN` / `UI_BUTTON_UP` | `entity_id` |
| `mouse_entered()` (Control) | `UI_MOUSE_ENTERED` | `entity_id` |
| `mouse_exited()` (Control) | `UI_MOUSE_EXITED` | `entity_id` |
| `focus_entered()` (Control) | `UI_FOCUS_ENTERED` | `entity_id` |
| `focus_exited()` (Control) | `UI_FOCUS_EXITED` | `entity_id` |
| `visibility_changed()` (CanvasItem) | `VISIBILITY_CHANGED` | `entity_id`, `visible` |
| `item_rect_changed()` (CanvasItem) | `CANVAS_ITEM_RECT_CHANGED` | `entity_id`, `rect` |
| `draw()` (CanvasItem) | Not an event — handled by render system | |
| `tree_entered()` (Node) | `ENTITY_ADDED_TO_SCENE` | `entity_id` |
| `tree_exiting()` (Node) | `ENTITY_REMOVING_FROM_SCENE` | `entity_id` |
| `tree_exited()` (Node) | `ENTITY_REMOVED_FROM_SCENE` | `entity_id` |
| `ready()` (Node) | `ENTITY_READY` | `entity_id` |
| `renamed()` (Node) | `ENTITY_RENAMED` | `entity_id`, `old_name`, `new_name` |
| `child_entered_tree(node)` | `CHILD_ADDED_TO_SCENE` | `parent_entity_id`, `child_entity_id` |
| `child_exiting_tree(node)` | `CHILD_REMOVING_FROM_SCENE` | `parent_entity_id`, `child_entity_id` |

---

## Lifecycle Methods → System Registration

| Godot Method | Motor Equivalent |
|-------------|-----------------|
| `_init()` | Component dataclass default values |
| `_enter_tree()` | `SceneManager` lifecycle hook |
| `_ready()` | `SceneManager` lifecycle hook + `ENTITY_READY` event |
| `_process(delta)` | System registered in `update` phase |
| `_physics_process(delta)` | System registered in `physics` phase |
| `_input(event)` | System registered as `InputSystem` |
| `_draw()` | Handled by `RenderSystem` |
| `_exit_tree()` | `SceneManager` lifecycle hook |
| `_notification(what)` | Specific events on EventBus |

---

## Editor/Authoring Concepts → Motor Authoring

| Godot Concept | Motor Equivalent |
|---------------|-----------------|
| `@export var` | Serializable field in component dataclass |
| `@export_group("name")` | Group metadata on component |
| `@export_range(min, max)` | Field metadata `range: [min, max]` |
| `@export_enum(...)` | Field metadata `enum: [...]` |
| `@export_file("*.png")` | Field metadata `file_filter: "*.png"` |
| `@export_dir` | Field metadata `type: "directory"` |
| `@export_multiline` | Field metadata `multiline: true` |
| `@export_color_no_alpha` | Color field without alpha |
| `@export_flags(...)` | Bit flag field |
| `@export_node_path` | Entity reference field |
| Inspector plugin | EngineAPI + CLI authoring tools |
| Tool script (`@tool`) | `ScriptBehaviour` or CLI automation |
| Editor plugin | No equivalent (editor is separate concern) |

---

## Physics Server → Physics Backend

| Godot Concept | Motor Equivalent |
|---------------|-----------------|
| `PhysicsServer2D` | `physics_backend` (legacy_aabb or box2d) |
| `PhysicsDirectSpaceState2D` | `query_physics_ray` / `query_physics_aabb` |
| `PhysicsShapeQueryParameters2D` | Query parameters dict |
| `move_and_collide()` | `character_movement_system` |
| `move_and_slide()` | `character_movement_system` |
| `test_move()` | `query_physics_cast` |
| Collision layers/masks | `collision_layer`/`collision_mask` on components |
| `WorldBoundaryShape2D` | Line/wall shape |
| `SeparationRayShape2D` | Ray shape |
| `CircleShape2D` | Circle shape |
| `RectangleShape2D` | Rectangle/AABB shape |
| `CapsuleShape2D` | Capsule shape |
| `ConvexPolygonShape2D` | Convex polygon shape |
| `ConcavePolygonShape2D` | Concave polygon shape |
| `SegmentShape2D` | Segment shape |

---

## Already Implemented (No Gap)

| Godot Feature | Motor File | Status |
|---------------|-----------|--------|
| `Timer` | `engine/components/timer.py` | ✅ complete |
| `Marker2D` | `engine/components/marker2d.py` | ✅ complete |
| SceneTree groups | `engine/ecs/group_operations.py` | ✅ complete |
| `Transform2D` / position | `engine/components/transform.py` | ✅ complete |
| `query_physics_ray` | `EngineAPI.query_physics_ray` | ✅ complete |
| `query_physics_aabb` | `EngineAPI.query_physics_aabb` | ✅ complete |
| `legacy_aabb` physics | Fallback physics backend | ✅ complete |
| Scene serialization (`.tscn`) | Scene schema v2 + `SceneManager` | ✅ complete |
| `TileMap` | `engine/components/tilemap.py` | 🔶 partial |
