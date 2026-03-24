# Platformer Patterns

Use this file for implementation notes and pseudocode. Keep `SKILL.md` as the operational checklist.

## Controller Selection

Prefer `CharacterController2D` when you need:

- explicit floor snap
- slide or collide semantics
- collision normals
- later extension toward platformer feel tuning

Prefer `PlayerController2D` when you only need:

- basic run and jump
- `RigidBody` velocity control
- simple animation state switching already covered by `engine/systems/player_controller_system.py`

## Vertical Slice Skeleton

Recommended entity set:

- `Player`
- `MainCamera`
- `Ground`
- one or more platforms or a `Tilemap`
- `HazardZone`
- `Checkpoint_A`
- `GoalFlag`

Recommended scene payload fields:

- `entities`
- `rules`
- `feature_metadata`

## Checkpoint Pattern

There is no built-in checkpoint component. Use one of these patterns:

1. Stateless respawn to a fixed start position with `RuleSystem`.
2. Stateful checkpoint memory with `ScriptBehaviour.public_data`.

Pseudocode:

```python
def on_trigger_enter_checkpoint(context, checkpoint_name: str, x: float, y: float) -> None:
    data = context.public_data
    data["checkpoint_name"] = checkpoint_name
    data["respawn_x"] = x
    data["respawn_y"] = y


def on_player_death(context) -> None:
    transform = context.get_component("Transform")
    if transform is None:
        return
    transform.x = float(context.public_data.get("respawn_x", 120.0))
    transform.y = float(context.public_data.get("respawn_y", 518.0))
```

If the request needs reusable checkpoint authoring across many scenes, propose a dedicated engine task.

## Hazard Pattern

Use trigger colliders plus declarative rules first.

Example shape:

```json
{
  "event": "on_trigger_enter",
  "when": {"entity_a": "Player", "entity_b": "HazardZone"},
  "do": [
    {"action": "log_message", "message": "Hazard hit"},
    {"action": "set_position", "entity": "Player", "x": 120.0, "y": 518.0}
  ]
}
```

Mirror the reverse entity ordering as well when necessary because the collision pair order may vary.

## Camera Pattern

`engine/systems/render_system.py` already resolves a platformer framing mode:

- `follow_entity`
- `framing_mode = "platformer"`
- `dead_zone_width`
- `dead_zone_height`
- `clamp_left/right/top/bottom`
- `recenter_on_play`

Use those fields before inventing custom camera scripts.

## Tilemap Collision Pattern

`engine/tilemap/collision_builder.py` treats a tile as solid when:

- `flags` contains `solid`
- `tags` contains `solid`
- `custom.collision` is true
- `custom.collision_shape` is `grid`, `box`, or `solid`

When authoring tilemaps, keep collision intent in tile data, not in editor-only overlays.

## Game Feel Extensions

These mechanics are not present as first-class fields in `CharacterController2D` today:

- coyote time
- jump buffering
- variable jump cutoff
- halved gravity near apex
- corner correction
- momentum transfer

Use this decision rule:

1. If the user only asked for content, do not invent these as hidden hacks.
2. If the user explicitly asked for engine movement feel work, extend `CharacterController2D` and `engine/systems/character_controller_system.py` with explicit serialized tunables.
3. If the task scope does not allow engine work, call out the gap and propose a separate task.

Possible serialized tuning fields for a future engine task:

```text
coyote_time_ms
jump_buffer_ms
jump_cut_gravity_multiplier
apex_gravity_multiplier
corner_correction_pixels
inherit_platform_velocity
```

## Validation Pattern

Preferred order:

1. targeted unit tests
2. headless harness
3. unified CLI smoke

Commands:

```bash
py -3 -m unittest tests.test_character_controller tests.test_tilemap_collision tests.test_headless_harness
py -3 tools/engine_cli.py smoke --scene levels/platformer_test_scene.json --frames 5 --seed 123 --out-dir artifacts/platformer_smoke
```
