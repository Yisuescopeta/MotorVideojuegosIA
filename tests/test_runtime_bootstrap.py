import json
import tempfile
import unittest
from pathlib import Path

from engine.project.build_settings import BuildSettings, BuildTargetPlatform, build_manifest_from_settings
from engine.runtime import (
    PackagedContentResolver,
    RuntimeBootstrapError,
    RuntimeManifest,
    StandaloneRuntimeBootstrap,
    runtime_manifest_from_build_manifest,
)


class StandaloneRuntimeBootstrapTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.build_root = Path(self._temp_dir.name) / "ExportedGame"
        self.bootstrap = StandaloneRuntimeBootstrap()

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def _scene_payload(self, name: str = "Main Scene") -> dict:
        return {
            "name": name,
            "entities": [],
            "rules": [],
            "feature_metadata": {},
        }

    def _build_manifest(self):
        settings = BuildSettings(
            product_name="Packaged Game",
            company_name="Runtime Tests",
            startup_scene="levels/main_scene.json",
            scenes_in_build=("levels/main_scene.json",),
            target_platform=BuildTargetPlatform.WINDOWS_DESKTOP,
            development_build=False,
            include_logs=False,
            include_profiler=False,
            output_name="packaged_game",
        )
        return build_manifest_from_settings(
            settings,
            ".motor/build",
            generated_at_utc="2026-04-03T20:00:00+00:00",
        )

    def _write_json(self, relative_path: str, payload: dict) -> Path:
        path = self.build_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=4), encoding="utf-8")
        return path

    def _create_packaged_build(
        self,
        *,
        create_runtime_manifest: bool = True,
        create_build_manifest: bool = True,
        create_startup_scene: bool = True,
        runtime_manifest_payload: dict | None = None,
    ) -> tuple[RuntimeManifest, Path | None]:
        build_manifest = self._build_manifest()
        runtime_manifest = runtime_manifest_from_build_manifest(
            build_manifest,
            generated_at_utc="2026-04-03T20:30:00+00:00",
            startup_scene="levels/main_scene.json",
            selected_content_summary={
                "scenes": 1,
                "prefabs": 0,
                "scripts": 0,
                "assets": 0,
                "metadata": 1,
            },
        )
        scene_path = None
        if create_runtime_manifest:
            payload = runtime_manifest.to_dict() if runtime_manifest_payload is None else runtime_manifest_payload
            self._write_json("runtime/runtime_manifest.json", payload)
        if create_build_manifest:
            self._write_json("runtime/metadata/build_manifest.json", build_manifest.to_dict())
        (self.build_root / "runtime" / "content").mkdir(parents=True, exist_ok=True)
        if create_startup_scene:
            scene_path = self._write_json("runtime/content/levels/main_scene.json", self._scene_payload())
        return runtime_manifest, scene_path

    def test_bootstrap_launches_valid_packaged_startup_scene(self) -> None:
        runtime_manifest, scene_path = self._create_packaged_build()

        bootstrapped = self.bootstrap.bootstrap(self.build_root, headless=True)

        self.assertTrue(bootstrapped.game.is_play_mode)
        self.assertIsNone(bootstrapped.game.project_service)
        self.assertEqual(bootstrapped.runtime_manifest.to_dict(), runtime_manifest.to_dict())
        self.assertEqual(bootstrapped.startup_scene_path, scene_path.as_posix())
        self.assertEqual(bootstrapped.scene_manager.current_scene.source_path, scene_path.as_posix())
        self.assertEqual(bootstrapped.content_resolver.content_root, self.build_root / "runtime" / "content")

    def test_bootstrap_fails_when_startup_scene_is_missing(self) -> None:
        self._create_packaged_build(create_startup_scene=False)

        with self.assertRaises(RuntimeBootstrapError) as context:
            self.bootstrap.bootstrap(self.build_root, headless=True)

        self.assertEqual(context.exception.diagnostics[0].code, "packaged_content.startup_scene_missing")

    def test_bootstrap_fails_when_runtime_manifest_is_missing(self) -> None:
        self._create_packaged_build(create_runtime_manifest=False)

        with self.assertRaises(RuntimeBootstrapError) as context:
            self.bootstrap.bootstrap(self.build_root, headless=True)

        self.assertEqual(context.exception.diagnostics[0].code, "runtime_manifest.missing")

    def test_bootstrap_fails_when_build_manifest_is_missing(self) -> None:
        self._create_packaged_build(create_build_manifest=False)

        with self.assertRaises(RuntimeBootstrapError) as context:
            self.bootstrap.bootstrap(self.build_root, headless=True)

        self.assertEqual(context.exception.diagnostics[0].code, "build_manifest.missing")

    def test_runtime_manifest_rejects_paths_outside_packaged_content(self) -> None:
        self._create_packaged_build(
            runtime_manifest_payload={
                "schema": RuntimeManifest.SCHEMA_NAME,
                "schema_version": RuntimeManifest.SCHEMA_VERSION,
                "generated_at_utc": "2026-04-03T20:30:00+00:00",
                "target_platform": "windows_desktop",
                "startup_scene": "../levels/main_scene.json",
                "content_root": "runtime/content",
                "metadata_root": "runtime/metadata",
                "build_manifest_path": "runtime/metadata/build_manifest.json",
                "selected_content_summary": {"scenes": 1},
            }
        )

        with self.assertRaises(RuntimeBootstrapError) as context:
            self.bootstrap.bootstrap(self.build_root, headless=True)

        self.assertEqual(context.exception.diagnostics[0].code, "runtime_manifest.invalid")

    def test_packaged_content_resolver_stays_within_packaged_roots(self) -> None:
        runtime_manifest, _ = self._create_packaged_build()
        resolver = PackagedContentResolver(self.build_root, runtime_manifest)

        with self.assertRaises(ValueError):
            resolver.resolve_content_path("../escape.json")

        with self.assertRaises(ValueError):
            resolver.resolve_metadata_path("../runtime_manifest.json")

    def test_runtime_manifest_serialization_is_deterministic(self) -> None:
        runtime_manifest, _ = self._create_packaged_build()

        first = json.dumps(runtime_manifest.to_dict(), sort_keys=True)
        second = json.dumps(runtime_manifest.to_dict(), sort_keys=True)

        self.assertEqual(first, second)

    def test_bootstrap_contract_is_deterministic_for_same_packaged_build(self) -> None:
        self._create_packaged_build()

        first = self.bootstrap.bootstrap(self.build_root, headless=True)
        second = self.bootstrap.bootstrap(self.build_root, headless=True)

        self.assertEqual(
            json.dumps(first.runtime_manifest.to_dict(), sort_keys=True),
            json.dumps(second.runtime_manifest.to_dict(), sort_keys=True),
        )
        self.assertEqual(first.startup_scene_path, second.startup_scene_path)


if __name__ == "__main__":
    unittest.main()
