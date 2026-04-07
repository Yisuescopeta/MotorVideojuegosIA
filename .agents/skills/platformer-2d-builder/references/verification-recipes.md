# Platformer Verification Recipes

Use these recipes after saving the scene that you want to verify. They are designed for `py -3 -m tools.engine_cli ai-verify` and only use assertion kinds that already exist in the repo.

## Split Execution Reminder

Keep these phases separate:

1. Workspace-only request for scene lifecycle changes such as create, open, activate, or save.
2. Transactional request for entity, component, prefab, and scene-flow edits.
3. Validation.
4. Save if verification must observe the changed scene file.
5. Headless verification.

Do not put workspace operations and transactional scene edits in the same execution request.

## Beginner Room Bootstrap

Use this after creating a first room with a player, floor, and platformer camera.

```json
{
  "scenario_id": "platformer-room-bootstrap",
  "project_root": ".",
  "scene_path": "levels/room_01.json",
  "assertions": [
    {
      "assertion_id": "player-exists",
      "kind": "entity_exists",
      "entity_name": "Player"
    },
    {
      "assertion_id": "player-controller-exists",
      "kind": "component_exists",
      "entity_name": "Player",
      "component_name": "PlayerController2D"
    },
    {
      "assertion_id": "camera-exists",
      "kind": "entity_exists",
      "entity_name": "MainCamera"
    },
    {
      "assertion_id": "camera-follows-player",
      "kind": "component_field_equals",
      "entity_name": "MainCamera",
      "component_name": "Camera2D",
      "field_path": "follow_entity",
      "expected_value": "Player"
    },
    {
      "assertion_id": "scene-selected",
      "kind": "selected_scene_is",
      "expected_scene_path": "levels/room_01.json"
    },
    {
      "assertion_id": "status-sane",
      "kind": "engine_status_sanity",
      "expected_state": "EDIT",
      "min_entity_count": 3
    }
  ]
}
```

If the scene uses `CharacterController2D` instead of `PlayerController2D`, swap the controller assertion accordingly.

## Hazard Pit And Respawn Checkpoint

Use this when the scene has:

- a trigger hazard volume
- a checkpoint entity with `SceneEntryPoint`
- a respawn controller entity with `SceneTransitionOnPlayerDeath`
- a `SceneTransitionAction` that targets the same scene and checkpoint entry id

This recipe verifies the saved structure, not the full dynamic checkpoint loop.

```json
{
  "scenario_id": "hazard-checkpoint-structure",
  "project_root": ".",
  "scene_path": "levels/room_01.json",
  "assertions": [
    {
      "assertion_id": "hazard-exists",
      "kind": "entity_exists",
      "entity_name": "HazardPit"
    },
    {
      "assertion_id": "hazard-is-trigger",
      "kind": "component_field_equals",
      "entity_name": "HazardPit",
      "component_name": "Collider",
      "field_path": "is_trigger",
      "expected_value": true
    },
    {
      "assertion_id": "checkpoint-exists",
      "kind": "entity_exists",
      "entity_name": "CheckpointA"
    },
    {
      "assertion_id": "checkpoint-entry-id",
      "kind": "component_field_equals",
      "entity_name": "CheckpointA",
      "component_name": "SceneEntryPoint",
      "field_path": "entry_id",
      "expected_value": "checkpoint_a"
    },
    {
      "assertion_id": "respawn-trigger-present",
      "kind": "component_exists",
      "entity_name": "RespawnController",
      "component_name": "SceneTransitionOnPlayerDeath"
    },
    {
      "assertion_id": "respawn-target-scene",
      "kind": "component_field_equals",
      "entity_name": "RespawnController",
      "component_name": "SceneTransitionAction",
      "field_path": "target_scene_path",
      "expected_value": "levels/room_01.json"
    },
    {
      "assertion_id": "respawn-target-entry",
      "kind": "component_field_equals",
      "entity_name": "RespawnController",
      "component_name": "SceneTransitionAction",
      "field_path": "target_entry_id",
      "expected_value": "checkpoint_a"
    }
  ]
}
```

If you also added a deterministic death repro, add a second verification pass with `play`, `step_frames`, and `recent_event_exists` for `player_death`.

## Goal Door And Next-Scene Transition

Use this when a goal door or goal flag is wired to a saved scene-flow key. This keeps the runtime check aligned with the built-in `scene_flow_target_can_be_loaded` assertion.

```json
{
  "scenario_id": "goal-door-next-scene",
  "project_root": ".",
  "scene_path": "levels/room_01.json",
  "assertions": [
    {
      "assertion_id": "goal-door-exists",
      "kind": "entity_exists",
      "entity_name": "GoalDoor"
    },
    {
      "assertion_id": "goal-door-link-exists",
      "kind": "component_exists",
      "entity_name": "GoalDoor",
      "component_name": "SceneLink"
    },
    {
      "assertion_id": "goal-door-flow-key",
      "kind": "component_field_equals",
      "entity_name": "GoalDoor",
      "component_name": "SceneLink",
      "field_path": "flow_key",
      "expected_value": "next_scene"
    },
    {
      "assertion_id": "goal-door-link-mode",
      "kind": "component_field_equals",
      "entity_name": "GoalDoor",
      "component_name": "SceneLink",
      "field_path": "link_mode",
      "expected_value": "trigger_enter"
    },
    {
      "assertion_id": "next-scene-loads",
      "kind": "scene_flow_target_can_be_loaded",
      "scene_flow_key": "next_scene"
    }
  ]
}
```

If the target scene has a specific arrival point, also verify `SceneLink.target_entry_id`.

## Jump Feel Tuning Pass

Use this after saving a tuning pass for native controller fields. This verifies the serialized values and a basic headless play smoke test.

```json
{
  "scenario_id": "jump-feel-tuning-pass",
  "project_root": ".",
  "scene_path": "levels/room_01.json",
  "play": true,
  "step_frames": 3,
  "assertions": [
    {
      "assertion_id": "player-controller-exists",
      "kind": "component_exists",
      "entity_name": "Player",
      "component_name": "PlayerController2D"
    },
    {
      "assertion_id": "jump-velocity-value",
      "kind": "component_field_equals",
      "entity_name": "Player",
      "component_name": "PlayerController2D",
      "field_path": "jump_velocity",
      "expected_value": -430.0
    },
    {
      "assertion_id": "air-control-value",
      "kind": "component_field_equals",
      "entity_name": "Player",
      "component_name": "PlayerController2D",
      "field_path": "air_control",
      "expected_value": 0.8
    },
    {
      "assertion_id": "play-state-sane",
      "kind": "engine_status_sanity",
      "expected_state": "PLAY",
      "min_frame": 3,
      "min_entity_count": 3
    },
    {
      "assertion_id": "play-event-seen",
      "kind": "recent_event_exists",
      "event_name": "on_play"
    }
  ]
}
```

If the scene uses `CharacterController2D`, switch the field assertions to `jump_velocity`, `gravity`, `max_fall_speed`, or `floor_snap_distance` on that component.

Use a separate focused runtime probe if you need to confirm dynamic input behavior. `ai-verify` does not inject controller input on its own.

## Sample Agent Requests

- `Use $platformer-2d-builder to create a first playable room and give me the workspace request, transactional request, validation command, and verification scenario.`
- `Use $platformer-2d-builder to wire a checkpoint respawn loop using SceneEntryPoint and scene transition components, then verify the saved structure.`
- `Use $platformer-2d-builder to add a goal door that loads the next scene through a saved flow key and verify the target scene can load.`
