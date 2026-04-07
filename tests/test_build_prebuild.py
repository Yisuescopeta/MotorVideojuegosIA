import json
import tempfile
import unittest
from pathlib import Path

from engine.assets.asset_service import AssetService
from engine.project import BuildPrebuildService, ProjectService
from engine.serialization.schema import migrate_prefab_data, migrate_scene_data


MINIMAL_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\rIDATx\x9cc```\xf8\x0f\x00\x01\x04\x01\x00"
    b"\x18\xdd\x8d\xb1"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _transform() -> dict[str, float | bool]:
    return {
        "enabled": True,
        "x": 0.0,
        "y": 0.0,
        "rotation": 0.0,
        "scale_x": 1.0,
        "scale_y": 1.0,
    }


def _entity(
    name: str,
    *,
    components: dict[str, object] | None = None,
    prefab_instance: dict[str, object] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": name,
        "active": True,
        "tag": "Untagged",
        "layer": "Default",
        "components": components or {"Transform": _transform()},
    }
    if prefab_instance is not None:
        payload["prefab_instance"] = prefab_instance
    return payload


def _scene_payload(
    name: str,
    entities: list[dict[str, object]],
    *,
    feature_metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "name": name,
        "entities": entities,
        "rules": [],
        "feature_metadata": feature_metadata or {},
    }


class BuildPrebuildServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self._temp_dir.name)
        self.global_state_dir = self.workspace / "global_state"
        self.project_root = self.workspace / "project"
        self.project_service = ProjectService(self.project_root, global_state_dir=self.global_state_dir)
        self.asset_service = AssetService(self.project_service)
        self.prebuild_service = BuildPrebuildService(self.project_service, self.asset_service)

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def _write_scene(self, relative_path: str, payload: dict[str, object]) -> Path:
        path = self.project_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(migrate_scene_data(payload), indent=2), encoding="utf-8")
        return path

    def _write_prefab(self, relative_path: str, payload: dict[str, object]) -> Path:
        path = self.project_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(migrate_prefab_data(payload), indent=2), encoding="utf-8")
        return path

    def _write_script(self, relative_path: str, contents: str = "def on_play(context):\n    return None\n") -> Path:
        path = self.project_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")
        return path

    def _write_png(self, relative_path: str) -> Path:
        path = self.project_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(MINIMAL_PNG_BYTES)
        return path

    def test_default_project_with_one_startup_scene_selects_only_default_scene(self) -> None:
        report = self.prebuild_service.generate_report(generated_at_utc="2026-04-03T21:00:00+00:00")
        report_path = self.prebuild_service.save_report(report)

        self.assertTrue(report.valid)
        self.assertEqual(report.startup_scene, "levels/main_scene.json")
        self.assertEqual(report.scene_order, ("levels/main_scene.json",))
        self.assertEqual(report.selected_content.scenes, ("levels/main_scene.json",))
        self.assertEqual(report.selected_content.prefabs, ())
        self.assertEqual(report.selected_content.scripts, ())
        self.assertEqual(report.selected_content.assets, ())
        self.assertEqual(
            report.selected_content.metadata,
            (
                "project.json",
                "settings/build_settings.json",
                ".motor/build/windows_desktop/project/build_manifest.json",
            ),
        )
        self.assertEqual(report.omitted_content.scenes, ())
        self.assertEqual(report.report_path, ".motor/build/prebuild_content_report.json")
        self.assertTrue(report_path.exists())

    def test_multiple_scenes_in_build_drive_dependency_selection_and_omissions(self) -> None:
        self._write_png("assets/player.png")
        self._write_png("assets/unused.png")
        self._write_script("scripts/brain.py")
        self._write_script("scripts/unused.py")
        self._write_prefab(
            "prefabs/enemy.prefab",
            {
                "root_name": "Enemy",
                "entities": [
                    {"name": "Enemy", "components": {"Transform": _transform()}},
                ],
            },
        )
        self._write_prefab(
            "prefabs/unused.prefab",
            {
                "root_name": "Unused",
                "entities": [
                    {"name": "Unused", "components": {"Transform": _transform()}},
                ],
            },
        )
        self._write_scene(
            "levels/alpha.json",
            _scene_payload(
                "Alpha",
                [
                    _entity(
                        "Player",
                        components={
                            "Transform": _transform(),
                            "Sprite": {"enabled": True, "texture_path": "assets/player.png"},
                            "ScriptBehaviour": {
                                "enabled": True,
                                "module_path": "brain",
                                "script": {"path": "scripts/brain.py", "guid": ""},
                                "public_data": {},
                            },
                        },
                    )
                ],
            ),
        )
        self._write_scene(
            "levels/beta.json",
            _scene_payload(
                "Beta",
                [
                    _entity(
                        "Spawner",
                        prefab_instance={
                            "prefab_path": "prefabs/enemy.prefab",
                            "root_name": "Enemy",
                            "overrides": {},
                        },
                    )
                ],
            ),
        )
        self._write_scene("levels/extra.json", _scene_payload("Extra", [_entity("Extra")]))
        self.project_service.save_build_settings(
            {
                "product_name": "Project",
                "company_name": "Studio",
                "startup_scene": "levels/beta.json",
                "scenes_in_build": ["levels/beta.json", "levels/alpha.json"],
                "target_platform": "windows_desktop",
                "development_build": False,
                "include_logs": False,
                "include_profiler": False,
                "output_name": "Project",
            }
        )

        report = self.prebuild_service.generate_report(generated_at_utc="2026-04-03T21:05:00+00:00")

        self.assertTrue(report.valid)
        self.assertEqual(report.scene_order, ("levels/beta.json", "levels/alpha.json"))
        self.assertEqual(report.selected_content.scenes, ("levels/beta.json", "levels/alpha.json"))
        self.assertEqual(report.selected_content.prefabs, ("prefabs/enemy.prefab",))
        self.assertEqual(report.selected_content.scripts, ("scripts/brain.py",))
        self.assertEqual(report.selected_content.assets, ("assets/player.png",))
        self.assertIn("levels/extra.json", report.omitted_content.scenes)
        self.assertIn("levels/main_scene.json", report.omitted_content.scenes)
        self.assertEqual(report.omitted_content.prefabs, ("prefabs/unused.prefab",))
        self.assertEqual(report.omitted_content.scripts, ("scripts/unused.py",))
        self.assertEqual(report.omitted_content.assets, ("assets/unused.png",))

    def test_missing_startup_scene_is_reported_as_blocking(self) -> None:
        startup_scene_path = self.project_root / "levels" / "main_scene.json"
        startup_scene_path.unlink()

        report = self.prebuild_service.generate_report(generated_at_utc="2026-04-03T21:10:00+00:00")

        self.assertFalse(report.valid)
        self.assertTrue(any(item.code == "build_settings.startup_scene_missing" for item in report.blocking_errors))

    def test_included_scene_with_missing_dependency_reports_blocker(self) -> None:
        self._write_scene(
            "levels/main_scene.json",
            _scene_payload(
                "Main Scene",
                [
                    _entity(
                        "Player",
                        components={
                            "Transform": _transform(),
                            "Sprite": {"enabled": True, "texture_path": "assets/missing.png"},
                        },
                    )
                ],
            ),
        )

        report = self.prebuild_service.generate_report(generated_at_utc="2026-04-03T21:15:00+00:00")

        self.assertFalse(report.valid)
        self.assertTrue(any(item.code == "dependency.missing" for item in report.blocking_errors))
        self.assertTrue(any(item.path == "assets/missing.png" for item in report.blocking_errors))

    def test_dependency_driven_content_selection_is_deterministic(self) -> None:
        self._write_png("assets/player.png")
        self._write_script("scripts/brain.py")
        self._write_prefab(
            "prefabs/enemy.prefab",
            {
                "root_name": "Enemy",
                "entities": [
                    {"name": "Enemy", "components": {"Transform": _transform()}},
                ],
            },
        )
        self._write_scene(
            "levels/alpha.json",
            _scene_payload(
                "Alpha",
                [
                    _entity(
                        "Player",
                        components={
                            "Transform": _transform(),
                            "Sprite": {"enabled": True, "texture_path": "assets/player.png"},
                            "ScriptBehaviour": {
                                "enabled": True,
                                "module_path": "brain",
                                "script": {"path": "scripts/brain.py", "guid": ""},
                                "public_data": {},
                            },
                        },
                    )
                ],
            ),
        )
        self._write_scene(
            "levels/beta.json",
            _scene_payload(
                "Beta",
                [
                    _entity(
                        "Spawner",
                        prefab_instance={
                            "prefab_path": "prefabs/enemy.prefab",
                            "root_name": "Enemy",
                            "overrides": {},
                        },
                    )
                ],
            ),
        )
        self.project_service.save_build_settings(
            {
                "product_name": "Project",
                "company_name": "Studio",
                "startup_scene": "levels/alpha.json",
                "scenes_in_build": ["levels/alpha.json", "levels/beta.json"],
                "target_platform": "windows_desktop",
                "development_build": False,
                "include_logs": False,
                "include_profiler": False,
                "output_name": "Project",
            }
        )

        first = self.prebuild_service.generate_report(generated_at_utc="2026-04-03T21:20:00+00:00")
        second = self.prebuild_service.generate_report(generated_at_utc="2026-04-03T21:20:00+00:00")

        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(json.dumps(first.to_dict(), sort_keys=True), json.dumps(second.to_dict(), sort_keys=True))

    def test_scene_reference_outside_scenes_in_build_blocks_prebuild(self) -> None:
        self._write_scene(
            "levels/main_scene.json",
            _scene_payload(
                "Main Scene",
                [
                    _entity(
                        "Portal",
                        components={
                            "Transform": _transform(),
                            "SceneTransitionAction": {
                                "enabled": True,
                                "target_scene_path": "levels/secret.json",
                                "target_entry_id": "",
                            },
                        },
                    )
                ],
            ),
        )
        self._write_scene("levels/secret.json", _scene_payload("Secret", [_entity("Secret")]))

        report = self.prebuild_service.generate_report(generated_at_utc="2026-04-03T21:25:00+00:00")

        self.assertFalse(report.valid)
        self.assertTrue(any(item.code == "scene_dependency.outside_build" for item in report.blocking_errors))
        self.assertIn("levels/secret.json", report.dependency_graph.unresolved_dependencies)


if __name__ == "__main__":
    unittest.main()
