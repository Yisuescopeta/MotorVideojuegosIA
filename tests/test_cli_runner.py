import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from cli.runner import CLIRunner
from engine.api.errors import InvalidOperationError


class CLIRunnerTests(unittest.TestCase):
    def _build_args(self) -> SimpleNamespace:
        return SimpleNamespace(
            level="",
            script="script.json",
            frames=0,
            seed=None,
            debug_colliders=False,
            debug_labels=False,
            debug_tile_chunks=False,
            debug_camera=False,
            golden_output="",
            golden_compare="",
            capture_every=1,
            debug_dump="",
        )

    @patch("cli.runner.traceback.print_exc")
    @patch("builtins.print")
    @patch("cli.runner.ScriptExecutor")
    @patch("cli.runner.HeadlessGame")
    def test_typed_script_error_exits_without_traceback(
        self,
        headless_game_mock,
        script_executor_mock,
        print_mock,
        traceback_mock,
    ) -> None:
        game = Mock()
        headless_game_mock.return_value = game
        executor = script_executor_mock.return_value
        executor.run_all.return_value = False
        executor.last_error = InvalidOperationError("script failed")

        with self.assertRaises(SystemExit) as context:
            CLIRunner().run(self._build_args())

        self.assertEqual(context.exception.code, 1)
        traceback_mock.assert_not_called()
        print_mock.assert_any_call("[ERROR] Error ejecutando script: script failed")

    @patch("cli.runner.traceback.print_exc")
    @patch("builtins.print")
    @patch("cli.runner.ScriptExecutor")
    @patch("cli.runner.HeadlessGame")
    def test_unexpected_script_error_keeps_traceback(
        self,
        headless_game_mock,
        script_executor_mock,
        print_mock,
        traceback_mock,
    ) -> None:
        game = Mock()
        headless_game_mock.return_value = game
        executor = script_executor_mock.return_value
        executor.run_all.return_value = False
        executor.last_error = RuntimeError("boom")

        with self.assertRaises(SystemExit) as context:
            CLIRunner().run(self._build_args())

        self.assertEqual(context.exception.code, 1)
        traceback_mock.assert_called_once()
        print_mock.assert_any_call("[ERROR] Error ejecutando script: boom")


if __name__ == "__main__":
    unittest.main()
