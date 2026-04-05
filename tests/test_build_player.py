import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from engine.project import BuildPlayerOptions, BuildPlayerService, ProjectService
from engine.project.build_player import _PackagingRequest, _PyInstallerPackager


MINIMAL_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\rIDATx\x9cc```\xf8\x0f\x00\x01\x04\x01\x00"
    b"\x18\xdd\x8d\xb1"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


class _FakePackager:
    def __init__(self) -> None:
        self.requests = []

    def package(self, request):
        self.requests.append(request)
        output_root = Path(request.output_root)
        output_root.mkdir(parents=True, exist_ok=True)
        executable_path = output_root / f"{request.executable_name}.exe"
        executable_path.write_bytes(b"fake-player-executable")
        return SimpleNamespace(executable_path=executable_path.as_posix())


def _timer_factory(values: list[float]):
    iterator = iter(values)
    return lambda: next(iterator)


class BuildPlayerServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self._temp_dir.name)
        self.global_state_dir = self.workspace / "global_state"
        self.project_root = self.workspace / "project"
        self.project_service = ProjectService(self.project_root, global_state_dir=self.global_state_dir)
        self.repo_root = Path(__file__).resolve().parents[1]

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def _write_png(self, relative_path: str) -> Path:
        path = self.project_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(MINIMAL_PNG_BYTES)
        return path

    def _build_service(self, *, packager: _FakePackager, timer_values: list[float]) -> BuildPlayerService:
        return BuildPlayerService(
            self.project_service,
            packager=packager,
            timer=_timer_factory(timer_values),
            repo_root=self.repo_root,
        )

    def test_successful_build_generates_folder_export_and_report(self) -> None:
        packager = _FakePackager()
        self._write_png("assets/unused.png")
        export_root = self.workspace / "exports" / "Project"

        report = self._build_service(packager=packager, timer_values=[10.0, 12.5]).build_player(
            BuildPlayerOptions(
                output_root=export_root.as_posix(),
                generated_at_utc="2026-04-03T22:00:00+00:00",
            )
        )

        self.assertEqual(report.status, "succeeded")
        self.assertEqual(report.startup_scene, "levels/main_scene.json")
        self.assertEqual(report.included_scenes, ("levels/main_scene.json",))
        self.assertEqual(report.included_asset_counts["scenes"], 1)
        self.assertEqual(report.included_asset_counts["metadata"], 3)
        self.assertEqual(len(packager.requests), 1)
        self.assertEqual(Path(packager.requests[0].output_root), export_root)

        executable_path = export_root / "project.exe"
        runtime_manifest_path = export_root / "runtime" / "runtime_manifest.json"
        build_manifest_path = export_root / "runtime" / "metadata" / "build_manifest.json"
        build_report_path = export_root / "runtime" / "metadata" / "build_report.json"
        packaged_scene_path = export_root / "runtime" / "content" / "levels" / "main_scene.json"
        packaged_project_manifest = export_root / "runtime" / "content" / "project.json"
        packaged_build_settings = export_root / "runtime" / "content" / "settings" / "build_settings.json"

        self.assertTrue(executable_path.exists())
        self.assertTrue(runtime_manifest_path.exists())
        self.assertTrue(build_manifest_path.exists())
        self.assertTrue(build_report_path.exists())
        self.assertTrue(packaged_scene_path.exists())
        self.assertTrue(packaged_project_manifest.exists())
        self.assertTrue(packaged_build_settings.exists())
        self.assertFalse((export_root / "runtime" / "content" / "assets" / "unused.png").exists())

        runtime_manifest = json.loads(runtime_manifest_path.read_text(encoding="utf-8"))
        content_bundle = json.loads((export_root / "runtime" / "metadata" / "content_bundle.json").read_text(encoding="utf-8"))
        persisted_report = json.loads(build_report_path.read_text(encoding="utf-8"))

        self.assertEqual(runtime_manifest["startup_scene"], "levels/main_scene.json")
        self.assertEqual(content_bundle["asset_count"], 1)
        self.assertEqual([item["path"] for item in content_bundle["assets"]], ["levels/main_scene.json"])
        self.assertEqual(persisted_report, report.to_dict())
        self.assertEqual(report.references["runtime_manifest"], "runtime/runtime_manifest.json")
        self.assertEqual(report.references["build_manifest"], "runtime/metadata/build_manifest.json")

    def test_missing_startup_scene_fails_before_packaging(self) -> None:
        packager = _FakePackager()
        (self.project_root / "levels" / "main_scene.json").unlink()

        report = self._build_service(packager=packager, timer_values=[20.0, 20.5]).build_player(
            BuildPlayerOptions(generated_at_utc="2026-04-03T22:05:00+00:00")
        )

        self.assertEqual(report.status, "failed")
        self.assertTrue(any(item.code == "build_settings.startup_scene_missing" for item in report.errors))
        self.assertEqual(packager.requests, [])

    def test_development_build_adds_runtime_dev_extras(self) -> None:
        prod_packager = _FakePackager()
        dev_packager = _FakePackager()
        prod_root = self.workspace / "exports" / "prod"
        dev_root = self.workspace / "exports" / "dev"

        prod_report = self._build_service(packager=prod_packager, timer_values=[30.0, 31.0]).build_player(
            BuildPlayerOptions(
                output_root=prod_root.as_posix(),
                generated_at_utc="2026-04-03T22:10:00+00:00",
            )
        )

        self.project_service.save_build_settings(
            {
                "product_name": "Project",
                "company_name": "DefaultCompany",
                "startup_scene": "levels/main_scene.json",
                "scenes_in_build": ["levels/main_scene.json"],
                "target_platform": "windows_desktop",
                "development_build": True,
                "include_logs": True,
                "include_profiler": True,
                "output_name": "project",
            }
        )

        dev_report = self._build_service(packager=dev_packager, timer_values=[40.0, 41.25]).build_player(
            BuildPlayerOptions(
                output_root=dev_root.as_posix(),
                generated_at_utc="2026-04-03T22:15:00+00:00",
            )
        )

        self.assertEqual(prod_report.status, "succeeded")
        self.assertFalse(prod_report.development_build)
        self.assertEqual(prod_report.development_extras, ())
        self.assertFalse((prod_root / "runtime" / "dev").exists())

        self.assertEqual(dev_report.status, "succeeded")
        self.assertTrue(dev_report.development_build)
        self.assertIn("runtime/dev/development_options.json", dev_report.development_extras)
        self.assertIn("runtime/dev/logs/README.txt", dev_report.development_extras)
        self.assertTrue((dev_root / "runtime" / "dev" / "development_options.json").exists())
        self.assertTrue((dev_root / "runtime" / "dev" / "logs" / "README.txt").exists())

    def test_build_report_is_deterministic_with_fixed_timestamp_and_timer(self) -> None:
        first_packager = _FakePackager()
        second_packager = _FakePackager()
        export_root = self.workspace / "exports" / "deterministic"
        options = BuildPlayerOptions(
            output_root=export_root.as_posix(),
            generated_at_utc="2026-04-03T22:20:00+00:00",
        )

        first = self._build_service(packager=first_packager, timer_values=[50.0, 51.5]).build_player(options)
        second = self._build_service(packager=second_packager, timer_values=[50.0, 51.5]).build_player(options)

        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(json.dumps(first.to_dict(), sort_keys=True), json.dumps(second.to_dict(), sort_keys=True))
        self.assertEqual(first.output_summary, second.output_summary)
        self.assertEqual(first.top_assets_by_size, second.top_assets_by_size)


    def test_spec_file_has_valid_python_syntax(self) -> None:
        """Generated spec must be syntactically valid Python (no indentation error from joiner mismatch)."""
        packager = _PyInstallerPackager()
        request = _PackagingRequest(
            project_root=(self.workspace / "proj").as_posix(),
            repo_root=self.repo_root.as_posix(),
            output_root=(self.workspace / "out" / "game_build").as_posix(),
            executable_name="game_build",
            development_build=False,
            include_logs=False,
        )
        spec = packager._build_spec(request)
        try:
            compile(spec, "player_runtime.spec", "exec")
        except SyntaxError as exc:
            self.fail(
                f"Generated spec file has a Python syntax error: {exc}\n"
                f"First 10 lines:\n" + "\n".join(spec.splitlines()[:10])
            )

    def test_packaging_failure_surfaces_stderr_in_report(self) -> None:
        """A CalledProcessError raised by the packager must include stderr in the build report."""

        class _FailingPackager:
            def package(self, request):
                # CalledProcessError(returncode, cmd, output, stderr) — note: stdout is the 'output' param
                raise subprocess.CalledProcessError(
                    1,
                    ["pyinstaller", "spec"],
                    "INFO: PyInstaller starting\n",
                    "ERROR: cannot import name 'HeadlessGame'\nTraceback ...\nIndentationError: unexpected indent",
                )

        report = BuildPlayerService(
            self.project_service,
            packager=_FailingPackager(),
            timer=_timer_factory([0.0, 0.1]),
            repo_root=self.repo_root,
        ).build_player()

        self.assertEqual(report.status, "failed")
        error_codes = [e.code for e in report.errors]
        self.assertIn("build_player.packaging_failed", error_codes)
        error = next(e for e in report.errors if e.code == "build_player.packaging_failed")
        self.assertIn("exit code 1", error.message)
        self.assertIn("IndentationError", error.message)
        self.assertEqual(error.stage, "packaging")


if __name__ == "__main__":
    unittest.main()
