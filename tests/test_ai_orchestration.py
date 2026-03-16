import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(os.getcwd())

from engine.api import EngineAPI


class AIOrchestrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self._temp_dir.name)
        self.global_state_dir = self.workspace / "global_state"
        self.project_root = self.workspace / "AIProject"
        self.api = EngineAPI(project_root=self.project_root.as_posix(), global_state_dir=self.global_state_dir.as_posix())
        self._write_level("bootstrap.json", "Bootstrap")
        self.api.load_level("levels/bootstrap.json")

    def tearDown(self) -> None:
        self.api.shutdown()
        self._temp_dir.cleanup()

    def _write_level(self, filename: str, scene_name: str) -> Path:
        level_path = self.project_root / "levels" / filename
        level_path.parent.mkdir(parents=True, exist_ok=True)
        level_path.write_text(json.dumps({"name": scene_name, "entities": [], "rules": []}, indent=4), encoding="utf-8")
        return level_path

    def test_provider_selection_follows_project_policy(self) -> None:
        self.api.update_ai_project_memory({"provider_policy": {"mode": "cloud"}})

        response = self.api.handle_ai_request("Haz un plan general", mode="plan")

        self.assertEqual(response["provider"], "stub_cloud")

    def test_context_includes_skills_capabilities_and_memory(self) -> None:
        self.api.update_ai_project_memory({"conventions": {"enemy_prefix": "Enemy_"}})

        context = self.api.get_ai_context("Crear un juego de plataformas")

        skill_ids = {item["id"] for item in context["skills"]}
        self.assertIn("genre_platformer_planner", skill_ids)
        self.assertTrue(len(context["capabilities"]) > 0)
        self.assertEqual(context["memory"]["conventions"]["enemy_prefix"], "Enemy_")

    def test_platformer_plan_asks_questions_before_execution(self) -> None:
        response = self.api.handle_ai_request("Crea un juego de plataformas", mode="plan")

        self.assertEqual(response["status"], "needs_input")
        question_ids = [item["id"] for item in response["plan"]["questions"]]
        self.assertEqual(question_ids, ["enemies", "obstacles", "asset_strategy", "camera_style", "hud"])
        self.assertEqual(response["plan"]["questions"][0]["choices"], ["none", "single_melee_enemy", "two_basic_enemies"])
        self.assertLessEqual(len(response["plan"]["questions"][0]["choices"]), 3)

    def test_gap_detection_prevents_invented_support(self) -> None:
        response = self.api.handle_ai_request("Crea un plataformas con tilemap y pathfinding", mode="plan")

        gap_ids = {gap["id"] for gap in response["gaps"]}
        self.assertIn("tilemap_support", gap_ids)
        self.assertIn("pathfinding_support", gap_ids)
        self.assertEqual(response["plan"]["session_type"], "gap_analysis")

    def test_execution_stays_in_proposal_until_confirmed(self) -> None:
        response = self.api.handle_ai_request(
            "Crea un juego de plataformas",
            answers={
                "enemies": "none",
                "obstacles": "none",
                "asset_strategy": "placeholders",
                "camera_style": "follow_platformer",
                "hud": "none",
            },
        )

        self.assertEqual(response["status"], "proposal_ready")
        entity_names = {entity["name"] for entity in self.api.list_entities()}
        self.assertNotIn("Player", entity_names)

    def test_platformer_execution_applies_after_confirmation_and_validates(self) -> None:
        response = self.api.handle_ai_request(
            "Crea un juego de plataformas",
            answers={
                "enemies": "slime",
                "obstacles": "pinchos",
                "asset_strategy": "placeholders",
                "camera_style": "follow_platformer",
                "hud": "basic_hud",
            },
            confirmed=True,
        )

        self.assertEqual(response["status"], "applied")
        self.assertTrue(response["validation"]["success"])
        entity_names = {entity["name"] for entity in self.api.list_entities()}
        self.assertTrue({"Player", "Ground", "MainCamera", "Enemy_01", "Obstacle_01", "HUDCanvas", "HUDLabel"}.issubset(entity_names))

    def test_general_plan_stops_asking_when_required_answers_are_present(self) -> None:
        response = self.api.handle_ai_request(
            "Anademe un script con el movimiento del Player",
            mode="plan",
            answers={
                "goal": "prototipo_jugable",
                "scope": "escena_existente",
            },
        )

        self.assertEqual(response["status"], "planned")
        self.assertEqual(response["plan"]["questions"], [])

    def test_direct_mode_skips_question_gate_and_returns_proposal(self) -> None:
        response = self.api.handle_ai_request(
            "Anademe un script con el movimiento del Player",
            mode="direct",
        )

        self.assertEqual(response["status"], "proposal_ready")
        action_ids = [action["id"] for action in response["proposal"]["actions"]]
        self.assertIn("attach_player_script_behaviour", action_ids)
        self.assertIn("player_script_scaffold", action_ids)

    def test_direct_mode_detects_spanish_prompt_for_jugador(self) -> None:
        response = self.api.handle_ai_request(
            "anademe movimiento al jugador",
            mode="direct",
        )

        self.assertEqual(response["status"], "proposal_ready")
        self.assertEqual(response["plan"]["execution_intent"], "attach_player_movement_script")

    def test_direct_apply_writes_player_script_scaffold(self) -> None:
        self.api.create_entity(
            "Player",
            components={
                "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0}
            },
        )

        response = self.api.handle_ai_request(
            "anademe movimiento al jugador",
            mode="direct",
            confirmed=True,
            allow_python=True,
        )

        self.assertEqual(response["status"], "applied")
        script_path = self.project_root / "scripts" / "player_movement_generated.py"
        self.assertTrue(script_path.exists())
        player = self.api.get_entity("Player")
        self.assertIn("ScriptBehaviour", player["components"])
        self.assertIn("InputMap", player["components"])
        self.assertIn("RigidBody", player["components"])

    def test_python_changes_require_explicit_opt_in(self) -> None:
        response = self.api.handle_ai_request(
            "Crea un juego de plataformas con script python personalizado",
            answers={
                "enemies": "none",
                "obstacles": "none",
                "asset_strategy": "placeholders",
                "camera_style": "follow_platformer",
                "hud": "none",
            },
            confirmed=True,
        )

        self.assertEqual(response["status"], "blocked")
        self.assertTrue(any("Python change blocked" in error for error in response["context_summary"]["errors"]))

    def test_project_memory_persists_between_sessions(self) -> None:
        self.api.update_ai_project_memory({"notes": ["usar placeholders hasta tener sprites finales"]})
        self.api.shutdown()

        second_api = EngineAPI(project_root=self.project_root.as_posix(), global_state_dir=self.global_state_dir.as_posix())
        try:
            memory = second_api.get_ai_project_memory()
            self.assertEqual(memory["notes"], ["usar placeholders hasta tener sprites finales"])
        finally:
            second_api.shutdown()

    def test_skill_manifests_are_loaded_with_versioned_contract(self) -> None:
        skills = self.api.list_ai_skills()

        self.assertGreaterEqual(len(skills), 4)
        self.assertTrue(all(skill["version"] >= 1 for skill in skills))
        self.assertEqual(len({skill["id"] for skill in skills}), len(skills))

    def test_provider_diagnostics_do_not_crash_without_active_project_manifest(self) -> None:
        bootstrap_root = self.workspace / "BootstrapOnly"
        bootstrap_root.mkdir(parents=True, exist_ok=True)
        no_project_api = EngineAPI(project_root=bootstrap_root.as_posix(), global_state_dir=self.global_state_dir.as_posix())
        try:
            no_project_api.project_service.clear_active_project()
            diagnostics = no_project_api.get_ai_provider_diagnostics()
            self.assertIn("selected_provider", diagnostics)
            self.assertIn("policy", diagnostics)
        finally:
            no_project_api.shutdown()


if __name__ == "__main__":
    unittest.main()
