import json
import os
import random
import sys
import unittest
from pathlib import Path

sys.path.append(os.getcwd())

from engine.serialization.schema import validate_scene_data


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = ROOT / ".agents" / "skills" / "turn-based-combat-rpg" / "assets" / "templates" / "battle_minimal_scene.template.json"


def _ordered_actions(payload: dict) -> list[dict]:
    battle = payload["feature_metadata"]["turn_based_battle"]
    combatants = battle["combatants"]
    abilities = battle["abilities"]
    rng = random.Random(int(battle["battle_context"]["rng_seed"]))

    enriched: list[dict] = []
    for action in battle["planned_actions"]:
        actor = combatants[action["actor"]]
        ability = abilities[action["ability"]]
        enriched.append(
            {
                **action,
                "_priority": int(ability["priority"]),
                "_speed": int(actor["speed"]),
                "_tie": rng.random(),
            }
        )

    enriched.sort(key=lambda item: (-item["_priority"], -item["_speed"], item["_tie"]))
    return enriched


def _resolve_turn(payload: dict) -> tuple[list[str], dict]:
    battle = json.loads(json.dumps(payload["feature_metadata"]["turn_based_battle"]))
    combatants = battle["combatants"]
    abilities = battle["abilities"]
    log: list[str] = []

    for action in _ordered_actions(payload):
        actor = combatants[action["actor"]]
        target = combatants[action["target"]]
        if actor["hp"] <= 0 or target["hp"] <= 0:
            continue
        ability = abilities[action["ability"]]
        damage = int(ability["power"])
        target["hp"] = max(0, int(target["hp"]) - damage)
        log.append(f"{action['actor']}->{action['ability']}->{action['target']}:{damage}")

    battle["battle_context"]["log"] = log
    return log, battle


class TurnBasedSkillAssetsTests(unittest.TestCase):
    def test_template_scene_is_valid_under_current_schema(self) -> None:
        payload = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(validate_scene_data(payload), [])

    def test_turn_resolution_uses_priority_order_and_updates_final_state(self) -> None:
        payload = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))

        log, resolved_battle = _resolve_turn(payload)

        self.assertEqual(
            log,
            [
                "slime_a->quick_sting->hero_knight:3",
                "hero_knight->slash->slime_a:7",
            ],
        )
        self.assertEqual(resolved_battle["combatants"]["hero_knight"]["hp"], 17)
        self.assertEqual(resolved_battle["combatants"]["slime_a"]["hp"], 5)


if __name__ == "__main__":
    unittest.main()
