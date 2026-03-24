import json
import os
import sys
import unittest
from pathlib import Path

sys.path.append(os.getcwd())

from engine.serialization.schema import validate_scene_data


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = ROOT / ".agents" / "skills" / "visual-novel-engine" / "assets" / "templates" / "vn_minimal_scene.template.json"


def _conditions_pass(conditions: list[dict], flags: dict[str, object]) -> bool:
    for condition in conditions:
        key = str(condition.get("flag", ""))
        if "equals" in condition and flags.get(key) != condition["equals"]:
            return False
        if "not_equals" in condition and flags.get(key) == condition["not_equals"]:
            return False
        if "exists" in condition and bool(key in flags) != bool(condition["exists"]):
            return False
    return True


def _run_branch(scene_payload: dict, choice_id: str) -> tuple[list[str], dict[str, object]]:
    runtime = scene_payload["feature_metadata"]["vn_runtime"]
    nodes = runtime["dialogue_graph"]["nodes"]
    flags = dict(runtime["flag_store"])
    current = runtime["entry_node"]
    transcript: list[str] = []

    while True:
        node = nodes[current]
        conditions = node.get("conditions", [])
        if conditions:
            assert _conditions_pass(conditions, flags), f"conditions failed for node {current}"

        node_type = node["type"]
        transcript.append(current)

        if node_type == "line":
            next_node = node.get("next")
            if not next_node:
                break
            current = next_node
            continue

        if node_type == "choice":
            selected = None
            for choice in node.get("choices", []):
                if choice.get("id") == choice_id:
                    selected = choice
                    break
            assert selected is not None, f"choice not found: {choice_id}"
            flags.update(selected.get("set_flags", {}))
            current = selected["next"]
            continue

        if node_type == "end":
            break

        raise AssertionError(f"unexpected node type: {node_type}")

    return transcript, flags


class VisualNovelSkillAssetsTests(unittest.TestCase):
    def test_template_scene_is_valid_under_current_scene_schema(self) -> None:
        payload = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(validate_scene_data(payload), [])

    def test_template_graph_walks_both_branches_and_updates_flags(self) -> None:
        payload = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))

        library_transcript, library_flags = _run_branch(payload, "library")
        rooftop_transcript, rooftop_flags = _run_branch(payload, "rooftop")

        self.assertEqual(library_transcript, ["intro", "choice_route", "library_scene", "end"])
        self.assertEqual(rooftop_transcript, ["intro", "choice_route", "rooftop_scene", "end"])
        self.assertEqual(library_flags["route"], "library")
        self.assertEqual(rooftop_flags["route"], "rooftop")
        self.assertTrue(library_flags["met.alex"])
        self.assertTrue(rooftop_flags["met.alex"])


if __name__ == "__main__":
    unittest.main()
