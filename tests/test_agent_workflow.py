import unittest

from tools.agent_workflow import (
    IA_FIRST_RULE,
    UNITY_2D_CORE_MATRIX,
    build_task_brief,
    infer_execution_mode,
    recommend_agents,
    recommend_validations,
)


class AgentWorkflowTests(unittest.TestCase):
    def test_recommend_agents_for_core_change(self) -> None:
        agents = recommend_agents(["core", "api"])
        self.assertIn("Agente Orquestador", agents)
        self.assertIn("Feature Scout", agents)
        self.assertIn("Core Architect", agents)
        self.assertIn("Core Implementer", agents)
        self.assertIn("QA & Regression", agents)
        self.assertIn("Docs & Contracts", agents)

    def test_recommend_agents_adds_debugger_when_failure_present(self) -> None:
        agents = recommend_agents(["scenes"], has_failure=True)
        self.assertIn("Debugger", agents)

    def test_recommend_validations_deduplicates_commands(self) -> None:
        commands = recommend_validations(["api", "tests", "api"])
        self.assertEqual(commands, ["python tests/test_api_usage.py"])

    def test_infer_execution_mode_prefers_sequential_for_runtime_critical(self) -> None:
        self.assertEqual(infer_execution_mode(["editor"]), "parallel")
        self.assertEqual(infer_execution_mode(["core", "editor"]), "sequential")

    def test_build_task_brief_contains_expected_sections(self) -> None:
        brief = build_task_brief(
            title="Corregir flujo de escenas",
            goal="Asegurar la restauracion correcta al salir de PLAY",
            subsystems=["scenes", "api"],
            files=["engine/scenes/scene_manager.py"],
            priority="core-stability",
        )
        self.assertIn("# Task Brief", brief)
        self.assertIn("engine/scenes/scene_manager.py", brief)
        self.assertIn("python verify_scene_manager.py", brief)
        self.assertIn("python tests/test_api_usage.py", brief)
        self.assertIn(IA_FIRST_RULE, brief)

    def test_unity_matrix_contains_expected_features(self) -> None:
        feature_names = {item["feature"] for item in UNITY_2D_CORE_MATRIX}
        self.assertIn("camera-2d", feature_names)
        self.assertIn("input-actions", feature_names)


if __name__ == "__main__":
    unittest.main()
