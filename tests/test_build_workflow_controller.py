import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from engine.app.build_workflow_controller import BuildWorkflowController
from engine.editor.build_settings_modal import BuildSettingsModal
from engine.project.project_service import ProjectService


class BuildWorkflowControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self._temp_dir.name)
        self.global_state_dir = self.workspace / "global_state"
        self.project_root = self.workspace / "project"
        self.project_service = ProjectService(self.project_root, global_state_dir=self.global_state_dir)
        self.modal = BuildSettingsModal()
        self.refresh_project_scene_entries = Mock()
        self.log_info = Mock()
        self.log_err = Mock()
        self.controller = BuildWorkflowController(
            get_project_service=lambda: self.project_service,
            get_build_settings_modal=lambda: self.modal,
            refresh_project_scene_entries=self.refresh_project_scene_entries,
            log_info=self.log_info,
            log_err=self.log_err,
        )

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def test_open_build_settings_loads_settings_scenes_and_last_report(self) -> None:
        last_report_path = self.project_service.get_project_path("build") / "player_build_report.json"
        last_report_path.parent.mkdir(parents=True, exist_ok=True)
        last_report_path.write_text(
            json.dumps({"status": "succeeded", "output_path": "C:/exports/game"}, indent=2),
            encoding="utf-8",
        )

        opened = self.controller.open_build_settings()

        self.assertTrue(opened)
        self.refresh_project_scene_entries.assert_called_once()
        self.assertTrue(self.modal.is_open)
        self.assertEqual(self.modal.startup_scene, "levels/main_scene.json")
        self.assertEqual(self.modal.scenes_in_build, ["levels/main_scene.json"])
        self.assertEqual(self.modal.last_build_report["status"], "succeeded")

    def test_handle_modal_save_persists_build_settings(self) -> None:
        self.controller.open_build_settings()
        self.modal.product_name = "Editor Game"
        self.modal.company_name = "Editor Studio"
        self.modal.output_name = "editor_game"
        self.modal.request_save = True

        self.controller.handle_modal_requests()

        saved = self.project_service.load_build_settings()
        self.assertEqual(saved.product_name, "Editor Game")
        self.assertEqual(saved.company_name, "Editor Studio")
        self.assertEqual(saved.output_name, "editor_game")
        self.log_info.assert_called_with("Build settings updated.")

    def test_handle_modal_build_runs_build_player_and_surfaces_report(self) -> None:
        self.controller.open_build_settings()
        self.modal.request_build = True

        class _FakeReport:
            def __init__(self, payload):
                self.status = payload["status"]
                self.output_path = payload["output_path"]
                self._payload = payload

            def to_dict(self):
                return dict(self._payload)

        class _FakeBuildPlayerService:
            def __init__(self, project_service):
                self.project_service = project_service

            def build_player(self):
                return _FakeReport(
                    {
                        "status": "succeeded",
                        "output_path": "C:/exports/game",
                        "target_platform": "windows_desktop",
                        "startup_scene": "levels/main_scene.json",
                        "warnings": [],
                        "errors": [],
                        "report_path": ".motor/build/player_build_report.json",
                    }
                )

        with patch("engine.project.build_player.BuildPlayerService", _FakeBuildPlayerService):
            self.controller.handle_modal_requests()

        self.assertEqual(self.modal.last_build_report["status"], "succeeded")
        self.assertIn("C:/exports/game", self.modal.status_message)
        self.log_info.assert_called_with("Build Player succeeded: C:/exports/game")

    def test_handle_modal_build_failure_surfaces_error_message(self) -> None:
        self.controller.open_build_settings()
        self.modal.request_build = True

        class _FakeReport:
            def __init__(self, payload):
                self.status = payload["status"]
                self.output_path = payload["output_path"]
                self._payload = payload

            def to_dict(self):
                return dict(self._payload)

        class _FailingBuildPlayerService:
            def __init__(self, project_service):
                self.project_service = project_service

            def build_player(self):
                return _FakeReport(
                    {
                        "status": "failed",
                        "output_path": "",
                        "errors": [{"message": "Startup scene missing."}],
                    }
                )

        with patch("engine.project.build_player.BuildPlayerService", _FailingBuildPlayerService):
            self.controller.handle_modal_requests()

        self.assertEqual(self.modal.last_build_report["status"], "failed")
        self.assertTrue(self.modal.status_is_error)
        self.log_err.assert_called_with("Startup scene missing.")


if __name__ == "__main__":
    unittest.main()
