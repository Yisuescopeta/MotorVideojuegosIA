import json
import tempfile
import unittest
from pathlib import Path

from cli.script_executor import ScriptExecutor
from engine.api import (
    ComponentNotFoundError,
    EngineAPI,
    EntityNotFoundError,
    InvalidOperationError,
    LevelLoadError,
)
from engine.ecs.entity import Entity


class ScriptExecutorTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self._temp_dir.name)
        self.project_root = self.workspace / "project"
        self.project_root.mkdir(parents=True, exist_ok=True)
        self.global_state_dir = self.workspace / "global_state"
        self.outside_root = self.workspace / "outside"
        self.outside_root.mkdir(parents=True, exist_ok=True)
        self.api = EngineAPI(
            project_root=self.project_root.as_posix(),
            global_state_dir=self.global_state_dir.as_posix(),
        )

    def tearDown(self) -> None:
        self.api.shutdown()
        self._temp_dir.cleanup()

    def _write_scene(self, base: Path, relative_path: str, name: str) -> Path:
        path = base / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "name": name,
                    "entities": [],
                    "rules": [],
                    "feature_metadata": {},
                },
                indent=4,
            ),
            encoding="utf-8",
        )
        return path

    def test_load_scene_accepts_relative_project_path(self) -> None:
        self._write_scene(self.project_root, "levels/inside.json", "Inside Scene")
        executor = ScriptExecutor(self.api.game)
        executor.commands = [{"action": "LOAD_SCENE", "args": {"path": "levels/inside.json"}}]

        success = executor.run_all()

        self.assertTrue(success)
        self.assertEqual(self.api.scene_manager.scene_name, "Inside Scene")
        self.assertTrue(self.api.scene_manager.current_scene.source_path.endswith("levels/inside.json"))

    def test_load_scene_blocks_path_outside_project_root(self) -> None:
        outside_scene = self._write_scene(self.outside_root, "external.json", "Outside Scene")
        executor = ScriptExecutor(self.api.game)
        executor.commands = [{"action": "LOAD_SCENE", "args": {"path": outside_scene.as_posix()}}]

        success = executor.run_all()

        self.assertFalse(success)
        self.assertTrue(executor.failed)
        self.assertTrue(executor.finished)
        self.assertIsInstance(executor.last_error, LevelLoadError)

    def test_unknown_command_marks_execution_as_failed(self) -> None:
        executor = ScriptExecutor(self.api.game)
        executor.commands = [{"action": "NOT_A_REAL_COMMAND", "args": {}}]

        success = executor.run_all()

        self.assertFalse(success)
        self.assertTrue(executor.failed)
        self.assertIsInstance(executor.last_error, ValueError)

    def test_run_all_returns_false_when_command_execution_fails(self) -> None:
        executor = ScriptExecutor(self.api.game)
        executor.commands = [{"action": "DELETE_ENTITY", "args": {"name": "Ghost"}}]

        success = executor.run_all()

        self.assertFalse(success)
        self.assertTrue(executor.failed)
        self.assertIsInstance(executor.last_error, EntityNotFoundError)

    def test_assert_pos_missing_entity_records_entity_not_found(self) -> None:
        world = self.api.scene_manager.create_new_scene("Assert Pos Missing Entity")
        self.api.game.set_world(world)
        executor = ScriptExecutor(self.api.game)
        executor.commands = [{"action": "ASSERT_POS", "args": {"entity": "Ghost", "x": 0, "y": 0}}]

        success = executor.run_all()

        self.assertFalse(success)
        self.assertIsInstance(executor.last_error, EntityNotFoundError)

    def test_assert_pos_missing_transform_records_component_not_found(self) -> None:
        world = self.api.scene_manager.create_new_scene("Assert Pos Missing Transform")
        world.add_entity(Entity("NoTransform"))
        self.api.game.set_world(world)
        executor = ScriptExecutor(self.api.game)
        executor.commands = [{"action": "ASSERT_POS", "args": {"entity": "NoTransform", "x": 0, "y": 0}}]

        success = executor.run_all()

        self.assertFalse(success)
        self.assertIsInstance(executor.last_error, ComponentNotFoundError)

    def test_inject_input_without_input_system_records_invalid_operation(self) -> None:
        self.api.game._input_system = None
        executor = ScriptExecutor(self.api.game)
        executor.commands = [{"action": "INJECT_INPUT", "args": {"entity": "Player", "state": {"jump": True}, "frames": 1}}]

        success = executor.run_all()

        self.assertFalse(success)
        self.assertIsInstance(executor.last_error, InvalidOperationError)


if __name__ == "__main__":
    unittest.main()
