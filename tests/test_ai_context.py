import json
import os
import sys
import unittest

sys.path.append(os.getcwd())

from engine.api import EngineAPI


class AIContextTests(unittest.TestCase):
    def setUp(self) -> None:
        self.api = EngineAPI()
        self.api.load_level("levels/demo_level.json")

    def tearDown(self) -> None:
        self.api.shutdown()

    def test_minimal_context_is_small_and_stable(self) -> None:
        context_a = self.api.build_ai_context(level="minimal")
        context_b = self.api.build_ai_context(level="minimal")

        self.assertEqual(context_a, context_b)
        self.assertEqual(context_a["schema"], "ai_context/v1")
        self.assertEqual(context_a["mode"], "EDIT")
        self.assertEqual(context_a["world_source"], "edit_world")
        self.assertEqual(context_a["scene"]["name"], "Demo Level (con Reglas)")
        self.assertLessEqual(len(context_a["relevant_entities"]), 5)

        payload_size = len(json.dumps(context_a, ensure_ascii=False))
        self.assertLess(payload_size, 1200)

    def test_selection_and_component_summary_are_exposed(self) -> None:
        assert self.api.game is not None
        assert self.api.game.world is not None
        self.api.game.world.selected_entity_name = "Player"

        context = self.api.build_ai_context(level="editor_focus")

        self.assertEqual(context["selection"]["entity"]["name"], "Player")
        self.assertTrue(context["selection"]["exists_in_world"])
        self.assertGreaterEqual(context["selection"]["components_count"], 1)
        self.assertLessEqual(len(context["selection"]["main_components"]), 5)
        self.assertEqual(context["relevant_entities"][0]["reason"], "selected")
        self.assertIn("viewport", context)
        self.assertIn("available", context["viewport"])

    def test_runtime_levels_follow_state_transitions(self) -> None:
        assert self.api.game is not None
        assert self.api.game.world is not None
        self.api.game.world.selected_entity_name = "Player"

        self.api.play()
        play_context = self.api.build_ai_context(level="runtime_focus")
        self.assertEqual(play_context["mode"], "PLAY")
        self.assertEqual(play_context["world_source"], "runtime_world")
        self.assertTrue(play_context["play_state"]["is_playing"])
        self.assertFalse(play_context["play_state"]["is_paused"])

        self.api.game.pause()
        paused_context = self.api.build_ai_context(level="runtime_focus")
        self.assertEqual(paused_context["mode"], "PAUSED")
        self.assertEqual(paused_context["world_source"], "runtime_world")
        self.assertTrue(paused_context["play_state"]["is_paused"])

        self.api.stop()
        stopped_context = self.api.build_ai_context(level="minimal")
        self.assertEqual(stopped_context["mode"], "EDIT")
        self.assertEqual(stopped_context["world_source"], "edit_world")

        self.api.play()
        self.api.game.pause()
        self.api.game.step()
        stepping_context = self.api.build_ai_context(level="runtime_focus")
        self.assertEqual(stepping_context["mode"], "STEPPING")
        self.assertTrue(stepping_context["play_state"]["is_stepping"])
        self.assertEqual(stepping_context["world_source"], "runtime_world")

    def test_duplicate_names_are_marked(self) -> None:
        assert self.api.game is not None
        assert self.api.game.world is not None

        duplicate = self.api.game.world.create_entity("Player")
        self.assertIsNotNone(duplicate)
        self.api.game.world.selected_entity_name = "Player"

        context = self.api.build_ai_context(level="minimal")
        self.assertTrue(context["selection"]["entity"]["duplicate_name"])

    def test_chat_message_and_examples_are_available(self) -> None:
        message = self.api.build_ai_context_message(level="minimal")
        self.assertTrue(message.startswith("AI_CONTEXT\n"))

        payload = json.loads(message.split("\n", 1)[1])
        self.assertEqual(payload["schema"], "ai_context/v1")

        examples = self.api.get_ai_context_examples()
        self.assertIn("minimal", examples)
        self.assertIn("runtime_focus", examples)


if __name__ == "__main__":
    unittest.main()
