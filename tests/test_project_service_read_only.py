"""
tests/test_project_service_read_only.py - Unit tests for ProjectService read_only mode

Verifies that read_only=True provides ACTIVE protection against all mutating operations,
not just a convention. Every public mutating method must raise PermissionError.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from engine.project.project_service import ProjectService


class ProjectServiceReadOnlyUnitTests(unittest.TestCase):
    """Direct unit tests: every mutating method raises PermissionError in read_only mode."""

    @classmethod
    def setUpClass(cls):
        cls.workspace = Path(tempfile.mkdtemp(prefix="motor_ps_readonly_"))

    def setUp(self):
        self.project = self.workspace / "Project"
        self.project.mkdir(exist_ok=True)
        (self.project / "project.json").write_text(
            json.dumps({
                "name": "TestProject",
                "version": 2,
                "engine_version": "2026.03",
                "template": "empty",
                "paths": {
                    "assets": "assets", "levels": "levels",
                    "prefabs": "prefabs", "scripts": "scripts",
                    "settings": "settings", "meta": ".motor/meta",
                    "build": ".motor/build",
                },
            }),
            encoding="utf-8",
        )
        self.ro = ProjectService(self.project, auto_ensure=False, read_only=True)
        self.rw = ProjectService(self.project, auto_ensure=False, read_only=False)
        manifest_path = self.project / "project.json"
        self.rw._manifest = self.rw._load_manifest(manifest_path)

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.workspace, ignore_errors=True)

    def _guard_test(self, method_name: str, call_ro, call_rw, *args, **kwargs) -> None:
        """Verify method raises PermissionError in read_only mode, works in writable mode."""
        with self.subTest(method=method_name, mode="read_only"):
            err = self._expect_PermissionError(call_ro, *args, **kwargs)
            self.assertIsNotNone(
                err,
                f"{method_name} must raise PermissionError in read_only mode, "
                f"got: {type(err).__name__ if err else 'no error'}"
            )
        with self.subTest(method=method_name, mode="writable"):
            try:
                call_rw(*args, **kwargs)
            except PermissionError:
                self.fail(f"{method_name} raised PermissionError in writable mode")

    def _expect_PermissionError(self, fn, *args, **kwargs) -> BaseException | None:
        try:
            fn(*args, **kwargs)
            return None
        except PermissionError:
            return PermissionError

    def test_ensure_project_read_only(self) -> None:
        alt = self.workspace / "AltProject"
        alt.mkdir()
        (alt / "project.json").write_text(json.dumps({
            "name": "Alt", "version": 2, "engine_version": "2026.03",
            "paths": {"assets": "assets", "levels": "levels", "prefabs": "prefabs",
                     "scripts": "scripts", "settings": "settings", "meta": ".motor/meta",
                     "build": ".motor/build"},
        }), encoding="utf-8")
        self._guard_test("ensure_project", self.ro.ensure_project, self.rw.ensure_project, alt)

    def test_create_project_read_only(self) -> None:
        new_proj = self.workspace / "NewProject"
        self._guard_test("create_project", self.ro.create_project, self.rw.create_project, new_proj)

    def test_register_project_read_only(self) -> None:
        self._guard_test("register_project", self.ro.register_project, self.rw.register_project, self.project)

    def test_remove_registered_project_read_only(self) -> None:
        self._guard_test("remove_registered_project", self.ro.remove_registered_project,
                        self.rw.remove_registered_project, self.project)

    def test_save_project_settings_read_only(self) -> None:
        self.ro._manifest = self.ro._load_manifest(self.project / "project.json")
        self._guard_test("save_project_settings", self.ro.save_project_settings,
                        self.rw.save_project_settings, {"startup_scene": "levels/main.json"})

    def test_save_editor_state_read_only(self) -> None:
        self._guard_test("save_editor_state", self.ro.save_editor_state,
                        self.rw.save_editor_state, {"last_scene": "", "open_scenes": [], "recent_assets": {}, "preferences": {}})

    def test_set_last_scene_read_only(self) -> None:
        self._guard_test("set_last_scene", self.ro.set_last_scene, self.rw.set_last_scene, "levels/test.json")

    def test_set_preference_read_only(self) -> None:
        self._guard_test("set_preference", self.ro.set_preference, self.rw.set_preference, "key", "value")

    def test_push_recent_asset_read_only(self) -> None:
        self._guard_test("push_recent_asset", self.ro.push_recent_asset,
                        self.rw.push_recent_asset, "sprite", "assets/player.png")

    def test_record_recent_project_read_only(self) -> None:
        self._guard_test("record_recent_project", self.ro.record_recent_project, self.rw.record_recent_project)

    def test_clear_recent_projects_read_only(self) -> None:
        self._guard_test("clear_recent_projects", self.ro.clear_recent_projects, self.rw.clear_recent_projects)

    def test_generate_ai_bootstrap_read_only(self) -> None:
        self.ro._manifest = self.ro._load_manifest(self.project / "project.json")
        self._guard_test("generate_ai_bootstrap", self.ro.generate_ai_bootstrap, self.rw.generate_ai_bootstrap)

    def test_migrate_project_bootstrap_read_only(self) -> None:
        self.ro._manifest = self.ro._load_manifest(self.project / "project.json")
        self._guard_test("migrate_project_bootstrap", self.ro.migrate_project_bootstrap,
                        self.rw.migrate_project_bootstrap)

    def test_read_only_methods_still_work(self) -> None:
        """Read-only methods must NOT raise in read_only mode."""
        self.ro._manifest = self.ro._load_manifest(self.project / "project.json")
        self.ro.has_project
        self.ro.project_root
        self.ro.project_name
        self.ro.list_project_scenes()
        self.ro.list_assets()
        self.ro.load_editor_state()
        self.ro.load_project_settings()
        self.ro.get_last_scene()
        self.ro.get_preference("x")

    def test_permission_error_message_mentions_operation(self) -> None:
        """PermissionError message must name the blocked operation."""
        try:
            self.ro.generate_ai_bootstrap()
            self.fail("Should have raised PermissionError")
        except PermissionError as e:
            msg = str(e)
            self.assertIn("generate_ai_bootstrap", msg)
            self.assertIn("read-only", msg.lower())

    def test_different_instances_independent(self) -> None:
        """A read_only=False instance can write even when a read_only=True instance exists."""
        ro = ProjectService(self.project, auto_ensure=False, read_only=True)
        rw = ProjectService(self.project, auto_ensure=False, read_only=False)

        with self.assertRaises(PermissionError):
            ro.save_editor_state({"last_scene": "", "open_scenes": [], "recent_assets": {}, "preferences": {}})

        rw.save_editor_state({"last_scene": "", "open_scenes": [], "recent_assets": {}, "preferences": {}})


if __name__ == "__main__":
    unittest.main()
