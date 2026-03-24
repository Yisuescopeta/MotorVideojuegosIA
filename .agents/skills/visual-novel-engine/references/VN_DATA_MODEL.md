# VN Data Model

Use the existing scene JSON envelope from `engine/serialization/schema.py` and place VN-specific data under `feature_metadata.vn_runtime`. Do not invent a parallel DSL when JSON already fits.

## Recommended Placement

```json
{
  "schema_version": 1,
  "name": "VNVerticalSlice",
  "entities": [],
  "rules": [],
  "feature_metadata": {
    "vn_runtime": {}
  }
}
```

## Recommended Runtime Shape

```json
{
  "version": 1,
  "entry_node": "intro",
  "current_node": "intro",
  "flag_store": {
    "met.alex": true,
    "route": null
  },
  "save_slots": {
    "slot_1": {
      "scene_id": "vn_vertical_slice",
      "current_node": "intro",
      "flags": {
        "met.alex": true,
        "route": null
      }
    }
  },
  "dialogue_graph": {
    "nodes": {
      "intro": {
        "type": "line",
        "speaker": "Alex",
        "text": "The train is late again.",
        "portrait": "alex_neutral",
        "audio": {
          "bgm_entity": "BgmSource",
          "voice_entity": "VoiceSource"
        },
        "next": "choice_route"
      },
      "choice_route": {
        "type": "choice",
        "prompt": "Where do we go after class?",
        "choices": [
          {
            "id": "library",
            "text": "Go to the library",
            "next": "library_scene",
            "set_flags": {
              "route": "library"
            }
          },
          {
            "id": "rooftop",
            "text": "Go to the rooftop",
            "next": "rooftop_scene",
            "set_flags": {
              "route": "rooftop"
            }
          }
        ]
      },
      "library_scene": {
        "type": "line",
        "speaker": "Alex",
        "text": "Library route selected.",
        "conditions": [
          {
            "flag": "route",
            "equals": "library"
          }
        ],
        "next": "end"
      },
      "rooftop_scene": {
        "type": "line",
        "speaker": "Alex",
        "text": "Rooftop route selected.",
        "conditions": [
          {
            "flag": "route",
            "equals": "rooftop"
          }
        ],
        "next": "end"
      },
      "end": {
        "type": "end"
      }
    }
  }
}
```

## Condition Model

Keep conditions explicit and easy to test. Start small.

```json
[
  { "flag": "route", "equals": "library" },
  { "flag": "met.alex", "equals": true },
  { "flag": "seen.prologue", "not_equals": true }
]
```

Recommended first-pass operators:

- `equals`
- `not_equals`
- `exists`

If richer boolean logic is needed, define it as an explicit follow-up data contract instead of embedding hidden Python rules across many scripts.

## Save Slot Guidance

- `SaveSlot` is a JSON payload, not a built-in runtime service in the current engine.
- Store:
  - scene id or scene path
  - current node id
  - flags snapshot
  - optional replay transcript ids
- Keep save/load code separate from UI rendering.

## Presentation Mapping

- `UIText.text` renders dialogue or choice labels.
- `UIButton.on_click` should emit an explicit action or call a narrow script handler with the chosen choice id.
- Portraits should remain serializable entity data. If portrait rendering needs a custom component not yet present, create a separate engine task instead of overloading text widgets.

## Pseudocode

```text
load vn_runtime from feature_metadata
node = nodes[current_node]
assert node conditions pass

if node.type == "line":
  render speaker/text/portrait
  on advance -> current_node = node.next

if node.type == "choice":
  render choices filtered by conditions
  on select(choice):
    apply choice.set_flags into flag_store
    current_node = choice.next
```
