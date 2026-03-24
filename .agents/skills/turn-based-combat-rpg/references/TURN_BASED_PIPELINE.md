# Turn Based Pipeline

Use the standard scene JSON envelope from `engine/serialization/schema.py` and place battle data under `feature_metadata.turn_based_battle`.

## Recommended Shape

```json
{
  "schema_version": 1,
  "name": "BattleVerticalSlice",
  "entities": [],
  "rules": [],
  "feature_metadata": {
    "turn_based_battle": {}
  }
}
```

```json
{
  "version": 1,
  "battle_context": {
    "phase": "StartTurn",
    "turn_index": 1,
    "rng_seed": 123,
    "log": []
  },
  "parties": {
    "heroes": ["hero_knight"],
    "enemies": ["slime_a"]
  },
  "combatants": {
    "hero_knight": {
      "party": "heroes",
      "hp": 20,
      "max_hp": 20,
      "speed": 5,
      "status_effects": []
    },
    "slime_a": {
      "party": "enemies",
      "hp": 12,
      "max_hp": 12,
      "speed": 2,
      "status_effects": []
    }
  },
  "abilities": {
    "slash": {
      "priority": 0,
      "power": 7,
      "targeting": "single_enemy"
    },
    "quick_sting": {
      "priority": 1,
      "power": 3,
      "targeting": "single_enemy"
    }
  }
}
```

## State Machine Diagram

```text
StartTurn
  -> refresh per-turn flags, decrement or trigger start-of-turn effects
  -> SelectActions

SelectActions
  -> gather one action per alive combatant
  -> OrderActions

OrderActions
  -> sort by priority desc
  -> sort by speed desc
  -> break full ties with seeded RNG
  -> Resolve

Resolve
  -> for each ordered action:
       apply pre-action status triggers
       validate target is still legal
       apply damage/heal/buff/debuff
       emit combat events and append log entries
       apply post-action status triggers
  -> EndTurn

EndTurn
  -> apply end-of-turn effects
  -> evaluate win/lose/escape
  -> if battle continues: StartTurn
```

## Damage And Effect Pipeline

```text
input action
  -> validate actor alive
  -> validate target(s)
  -> run on_before_action effects
  -> compute deterministic result
  -> mutate HP/status
  -> emit battle.action_resolved
  -> append combat log entry
  -> run on_after_action effects
```

## Status Effect Model

Recommended fields:

- `id`
- `kind`
- `duration`
- `stacks`
- `magnitude`
- `triggers`

Example:

```json
{
  "id": "poison_1",
  "kind": "poison",
  "duration": 3,
  "stacks": 1,
  "magnitude": 2,
  "triggers": ["on_turn_end"]
}
```

## Ordering Pseudocode

```text
ordered_actions = sort(actions,
  key = (
    -ability.priority,
    -combatant.speed,
    seeded_roll_for_exact_ties
  )
)
```

Keep the seeded tie-break deterministic by using the encounter seed from `battle_context.rng_seed` or the engine seed from `Game.set_seed()`.

## Replay Guidance

- Persist `rng_seed`, chosen actions, ordered action ids, and combat logs.
- For headless checks, write transcript JSON to `artifacts/`.
- Use `engine/debug/golden_run.py` style capture when the encounter also mutates world state outside the combat model.
