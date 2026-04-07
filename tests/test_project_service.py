import json
import tempfile
import unittest
from pathlib import Path

from cli.script_executor import ScriptExecutor
from engine.api import EngineAPI
from engine.project.project_service import ProjectService


REPO_ROOT = Path(__file__).resolve().parents[1]


class ProjectServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self._temp_dir.name)
        self.global_state_dir = self.workspace / "global_state"

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def _make_project(self, name: str) -> tuple[Path, ProjectService]:
        root = self.workspace / name
        service = ProjectService(root, global_state_dir=self.global_state_dir)
        return root, service

    def _write_level(self, project_root: Path, filename: str, scene_name: str) -> Path:
        level_path = project_root / "levels" / filename
        level_path.parent.mkdir(parents=True, exist_ok=True)
        level_path.write_text(
            json.dumps(
                {
                    "name": scene_name,
                    "entities": [],
                    "rules": [],
                },
                indent=4,
            ),
            encoding="utf-8",
        )
        return level_path

    def test_ensure_project_creates_manifest_and_editor_state_layout(self) -> None:
        project_root, service = self._make_project("ProjectAlpha")

        self.assertTrue((project_root / "project.json").exists())
        self.assertTrue((project_root / ".motor" / "editor_state.json").exists())
        self.assertTrue(service.get_project_path("assets").exists())
        self.assertTrue(service.get_project_path("levels").exists())
        self.assertTrue(service.get_project_path("prefabs").exists())
        self.assertTrue(service.get_project_path("scripts").exists())
        self.assertTrue(service.get_project_path("settings").exists())
        self.assertTrue(service.get_project_path("meta").exists())
        self.assertEqual(service.manifest.name, "ProjectAlpha")
        self.assertEqual(service.manifest.version, 2)
        self.assertEqual(service.manifest.template, "empty")
        self.assertEqual(service.manifest.engine_version, "2026.03")
        self.assertTrue((project_root / "levels" / "main_scene.json").exists())
        self.assertEqual(
            service.load_project_settings(),
            {
                "startup_scene": "levels/main_scene.json",
                "template": "empty",
                "terminal": {
                    "execution_policy": "inherit",
                },
                "api": {
                    "path_sandbox": False,
                },
            },
        )
        self.assertEqual(
            service.load_editor_state(),
            {
                "recent_assets": {},
                "last_scene": "",
                "open_scenes": [],
                "active_scene": "",
                "scene_view_states": {},
                "preferences": {},
            },
        )

    def test_recent_projects_are_global_sorted_and_filter_invalid_entries(self) -> None:
        _, first_service = self._make_project("ProjectOne")
        _, second_service = self._make_project("ProjectTwo")

        recents_path = second_service.get_recent_projects_path()
        data = json.loads(recents_path.read_text(encoding="utf-8"))
        data["projects"].append({"name": "Ghost", "path": (self.workspace / "Ghost").as_posix()})
        recents_path.write_text(json.dumps(data, indent=4), encoding="utf-8")

        recents = second_service.list_recent_projects()

        self.assertEqual(recents[0]["name"], "ProjectTwo")
        self.assertEqual(recents[1]["name"], "ProjectOne")
        self.assertTrue(all(item["path"] != (self.workspace / "Ghost").as_posix() for item in recents))
        self.assertTrue(recents[0]["manifest_path"].endswith("project.json"))
        self.assertTrue(bool(recents[0]["last_opened_utc"]))
        self.assertEqual(first_service.global_state_dir, self.global_state_dir.resolve())

    def test_launcher_lists_internal_and_invalid_registered_projects(self) -> None:
        bootstrap = ProjectService(self.workspace, global_state_dir=self.global_state_dir, auto_ensure=False)
        internal_root = bootstrap.build_internal_project_path("InternalProject")
        bootstrap.create_project(internal_root, name="InternalProject")
        missing_path = (self.workspace / "GhostProject").resolve()
        registry_path = bootstrap.get_recent_projects_path()
        registry_path.write_text(
            json.dumps(
                {
                    "projects": [
                        {
                            "name": "GhostProject",
                            "path": missing_path.as_posix(),
                            "manifest_path": (missing_path / "project.json").as_posix(),
                            "last_opened_utc": "2026-03-20T12:00:00+00:00",
                            "engine_version": "2026.03",
                        }
                    ]
                },
                indent=4,
            ),
            encoding="utf-8",
        )

        launcher_projects = bootstrap.list_launcher_projects()

        self.assertEqual(launcher_projects[0]["name"], "InternalProject")
        self.assertEqual(launcher_projects[0]["status"], "valid")
        self.assertEqual(launcher_projects[1]["name"], "GhostProject")
        self.assertEqual(launcher_projects[1]["status"], "missing")

    def test_editor_state_round_trip_tracks_scene_recent_assets_and_preferences(self) -> None:
        project_root, service = self._make_project("ProjectState")
        asset_path = project_root / "assets" / "hero.png"
        asset_path.write_bytes(b"")
        self._write_level(project_root, "intro.json", "Intro")

        service.set_last_scene("levels/intro.json")
        service.push_recent_asset("sprite", "assets/hero.png")
        service.set_preference("active_tab", "GAME")

        state = service.load_editor_state()

        self.assertEqual(state["last_scene"], "levels/intro.json")
        self.assertEqual(state["open_scenes"], [])
        self.assertEqual(state["active_scene"], "")
        self.assertEqual(state["scene_view_states"], {})
        self.assertEqual(state["recent_assets"]["sprite"], ["assets/hero.png"])
        self.assertEqual(state["preferences"]["active_tab"], "GAME")

        service.set_last_scene("")
        self.assertEqual(service.get_last_scene(), "")

    def test_project_settings_round_trip_normalizes_security_defaults(self) -> None:
        _, service = self._make_project("ProjectSecurity")

        service.save_project_settings(
            {
                "startup_scene": "levels/custom_scene.json",
                "template": "empty",
                "terminal": {"execution_policy": "RemoteSigned"},
                "api": {"path_sandbox": True},
            }
        )

        self.assertEqual(
            service.load_project_settings(),
            {
                "startup_scene": "levels/custom_scene.json",
                "template": "empty",
                "terminal": {
                    "execution_policy": "RemoteSigned",
                },
                "api": {
                    "path_sandbox": True,
                },
            },
        )

    def test_validate_project_rejects_missing_or_invalid_manifest(self) -> None:
        missing_root = self.workspace / "MissingProject"
        missing_root.mkdir(parents=True, exist_ok=True)
        invalid_root = self.workspace / "InvalidProject"
        invalid_root.mkdir(parents=True, exist_ok=True)
        (invalid_root / "project.json").write_text(json.dumps({"name": "Broken", "paths": []}), encoding="utf-8")
        _, valid_service = self._make_project("ValidProject")

        self.assertFalse(valid_service.validate_project(missing_root))
        self.assertFalse(valid_service.validate_project(invalid_root))
        self.assertTrue(valid_service.validate_project(valid_service.project_root))

    def test_create_project_can_start_from_global_state_without_active_manifest(self) -> None:
        bootstrap = ProjectService(self.workspace, global_state_dir=self.global_state_dir, auto_ensure=False)

        manifest = bootstrap.create_project(self.workspace / "CreatedProject", name="Created Project")

        self.assertTrue(bootstrap.has_project)
        self.assertEqual(manifest.name, "Created Project")
        self.assertTrue((self.workspace / "CreatedProject" / "project.json").exists())
        self.assertTrue((self.workspace / "CreatedProject" / "assets").exists())
        self.assertTrue((self.workspace / "CreatedProject" / "settings" / "project_settings.json").exists())
        self.assertTrue((self.workspace / "CreatedProject" / "levels" / "main_scene.json").exists())
        self.assertEqual(bootstrap.list_recent_projects()[0]["name"], "Created Project")

    def test_register_project_migrates_manifest_and_creates_settings(self) -> None:
        external_root = self.workspace / "LegacyProject"
        external_root.mkdir(parents=True, exist_ok=True)
        (external_root / "project.json").write_text(
            json.dumps(
                {
                    "name": "LegacyProject",
                    "version": 1,
                    "paths": {
                        "assets": "assets",
                        "levels": "levels",
                        "prefabs": "prefabs",
                        "scripts": "scripts",
                        "meta": ".motor/meta",
                    },
                },
                indent=4,
            ),
            encoding="utf-8",
        )
        bootstrap = ProjectService(self.workspace, global_state_dir=self.global_state_dir, auto_ensure=False)

        bootstrap.register_project(external_root)

        migrated = json.loads((external_root / "project.json").read_text(encoding="utf-8"))
        self.assertEqual(migrated["version"], 2)
        self.assertEqual(migrated["template"], "empty")
        self.assertEqual(migrated["engine_version"], "2026.03")
        self.assertIn("settings", migrated["paths"])
        self.assertTrue((external_root / "settings" / "project_settings.json").exists())

    def test_list_project_scenes_returns_project_levels_with_names(self) -> None:
        project_root, service = self._make_project("SceneCatalog")
        self._write_level(project_root, "intro_scene.json", "Intro Scene")
        nested_path = project_root / "levels" / "boss" / "finale.json"
        nested_path.parent.mkdir(parents=True, exist_ok=True)
        nested_path.write_text(json.dumps({"entities": [], "rules": []}, indent=4), encoding="utf-8")

        scenes = service.list_project_scenes()

        self.assertEqual(
            [item["path"] for item in scenes],
            [
                "levels/boss/finale.json",
                "levels/intro_scene.json",
                "levels/main_scene.json",
            ],
        )
        self.assertEqual(scenes[0]["name"], "finale")
        self.assertEqual(scenes[1]["name"], "Intro Scene")
        self.assertEqual(scenes[2]["name"], "Main Scene")

    def test_build_scene_file_path_sanitizes_name_and_avoids_collisions(self) -> None:
        _project_root, service = self._make_project("ScenePaths")
        first = service.build_scene_file_path("Boss Intro")
        first.write_text("{}", encoding="utf-8")

        second = service.build_scene_file_path("Boss Intro")
        levels_root = service.get_project_path("levels")

        self.assertEqual(first, levels_root / "boss_intro.json")
        self.assertEqual(second, levels_root / "boss_intro_2.json")

    def test_list_project_prefabs_supports_prefab_and_json_and_skips_meta(self) -> None:
        project_root, service = self._make_project("PrefabCatalog")
        prefabs_root = project_root / "prefabs"
        prefabs_root.mkdir(parents=True, exist_ok=True)
        (prefabs_root / "enemy.prefab").write_text("{}", encoding="utf-8")
        (prefabs_root / "legacy.json").write_text("{}", encoding="utf-8")
        (prefabs_root / "ignored.meta.json").write_text("{}", encoding="utf-8")

        prefabs = service.list_project_prefabs()

        self.assertEqual(prefabs, ["prefabs/enemy.prefab", "prefabs/legacy.json"])


class AIDiscoverabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self._temp_dir.name)
        self.global_state_dir = self.workspace / "global_state"

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def _make_project(self, name: str) -> tuple[Path, ProjectService]:
        root = self.workspace / name
        service = ProjectService(root, global_state_dir=self.global_state_dir)
        return root, service

    def test_new_project_contains_motor_ai_json_and_start_here_md(self) -> None:
        project_root, service = self._make_project("BootstrapProject")

        motor_ai_path = project_root / "motor_ai.json"
        start_here_path = project_root / "START_HERE_AI.md"

        self.assertTrue(motor_ai_path.exists(), "motor_ai.json must be created on project creation")
        self.assertTrue(start_here_path.exists(), "START_HERE_AI.md must be created on project creation")

    def test_motor_ai_json_has_correct_schema_version(self) -> None:
        project_root, service = self._make_project("SchemaProject")

        motor_ai_path = project_root / "motor_ai.json"
        data = json.loads(motor_ai_path.read_text(encoding="utf-8"))

        self.assertEqual(data["schema_version"], 2)
        self.assertIn("engine", data)
        self.assertIn("project", data)
        self.assertIn("entrypoints", data)
        self.assertIn("capabilities", data)

    def test_motor_ai_json_engine_section_contains_version_info(self) -> None:
        project_root, service = self._make_project("EngineInfoProject")

        motor_ai_path = project_root / "motor_ai.json"
        data = json.loads(motor_ai_path.read_text(encoding="utf-8"))

        self.assertEqual(data["engine"]["name"], "MotorVideojuegosIA")
        self.assertIn("version", data["engine"])
        self.assertIn("api_version", data["engine"])

    def test_motor_ai_json_project_section_contains_manifest_data(self) -> None:
        project_root, service = self._make_project("ProjectDataProject")

        motor_ai_path = project_root / "motor_ai.json"
        data = json.loads(motor_ai_path.read_text(encoding="utf-8"))

        self.assertEqual(data["project"]["name"], "ProjectDataProject")
        self.assertIn("root", data["project"])
        self.assertIn("engine_version", data["project"])
        self.assertIn("template", data["project"])

    def test_motor_ai_json_entrypoints_contains_key_paths(self) -> None:
        project_root, service = self._make_project("EntrypointsProject")

        motor_ai_path = project_root / "motor_ai.json"
        data = json.loads(motor_ai_path.read_text(encoding="utf-8"))

        entrypoints = data["entrypoints"]
        self.assertIn("manifest", entrypoints)
        self.assertIn("settings", entrypoints)
        self.assertIn("startup_scene", entrypoints)
        self.assertIn("scripts_dir", entrypoints)
        self.assertIn("assets_dir", entrypoints)
        self.assertTrue(Path(entrypoints["manifest"]).exists())
        self.assertTrue(Path(entrypoints["settings"]).exists())

    def test_motor_ai_json_capabilities_is_structured_as_registry(self) -> None:
        project_root, service = self._make_project("CapabilitiesProject")

        motor_ai_path = project_root / "motor_ai.json"
        data = json.loads(motor_ai_path.read_text(encoding="utf-8"))

        caps = data["capabilities"]
        self.assertIn("schema_version", caps)
        self.assertIn("engine", caps)
        self.assertIn("capabilities", caps)
        self.assertIsInstance(caps["capabilities"], list)
        self.assertGreater(len(caps["capabilities"]), 0)
        # Verify at least one capability has expected structure
        first_cap = caps["capabilities"][0]
        self.assertIn("id", first_cap)
        self.assertIn("summary", first_cap)
        self.assertIn("mode", first_cap)
        self.assertIn("api_methods", first_cap)
        self.assertIn("cli_command", first_cap)

    def test_start_here_md_contains_project_name_and_engine_version(self) -> None:
        project_root, service = self._make_project("StartHereProject")

        start_here_path = project_root / "START_HERE_AI.md"
        content = start_here_path.read_text(encoding="utf-8")

        self.assertIn("StartHereProject", content)
        self.assertIn("MotorVideojuegosIA", content)
        self.assertIn("motor_ai.json", content)

    def test_generate_ai_bootstrap_overwrites_existing_files(self) -> None:
        project_root, service = self._make_project("RegenProject")

        motor_ai_path = project_root / "motor_ai.json"
        original_content = json.dumps({"schema_version": 99}, indent=4)
        motor_ai_path.write_text(original_content, encoding="utf-8")

        result = service.generate_ai_bootstrap()

        data = json.loads(motor_ai_path.read_text(encoding="utf-8"))
        self.assertEqual(data["schema_version"], 2)
        self.assertIn("engine", data)

    def test_migrate_project_bootstrap_adds_files_to_existing_project(self) -> None:
        project_root = self.workspace / "LegacyProject"
        project_root.mkdir(parents=True, exist_ok=True)
        (project_root / "project.json").write_text(
            json.dumps({
                "name": "LegacyProject",
                "version": 1,
                "paths": {},
            }, indent=4),
            encoding="utf-8",
        )
        bootstrap = ProjectService(self.workspace, global_state_dir=self.global_state_dir, auto_ensure=False)
        bootstrap.register_project(project_root)

        motor_ai_path = project_root / "motor_ai.json"
        start_here_path = project_root / "START_HERE_AI.md"

        self.assertTrue(motor_ai_path.exists(), "migrate_project_bootstrap must create motor_ai.json")
        self.assertTrue(start_here_path.exists(), "migrate_project_bootstrap must create START_HERE_AI.md")

        data = json.loads(motor_ai_path.read_text(encoding="utf-8"))
        self.assertEqual(data["project"]["name"], "LegacyProject")
        self.assertEqual(data["schema_version"], 2)

    def test_generate_ai_bootstrap_with_custom_name_updates_project_name(self) -> None:
        project_root = self.workspace / "CustomNameProject"
        service = ProjectService(self.workspace, global_state_dir=self.global_state_dir, auto_ensure=False)
        service.create_project(project_root, name="Custom Display Name")

        motor_ai_path = project_root / "motor_ai.json"
        data = json.loads(motor_ai_path.read_text(encoding="utf-8"))

        self.assertEqual(data["project"]["name"], "Custom Display Name")

    def test_motor_ai_json_capabilities_has_engine_info(self) -> None:
        project_root, service = self._make_project("CapsSchemaProject")

        motor_ai_path = project_root / "motor_ai.json"
        data = json.loads(motor_ai_path.read_text(encoding="utf-8"))

        self.assertEqual(data["engine"]["capabilities_schema_version"], 1)
        self.assertIn("schema_version", data["capabilities"])


class ProjectSwitchIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self._temp_dir.name)
        self.global_state_dir = self.workspace / "global_state"
        self.api: EngineAPI | None = None

    def tearDown(self) -> None:
        if self.api is not None:
            self.api.shutdown()
        self._temp_dir.cleanup()

    def _make_project(self, name: str) -> tuple[Path, ProjectService]:
        root = self.workspace / name
        service = ProjectService(root, global_state_dir=self.global_state_dir)
        return root, service

    def _write_level(self, project_root: Path, filename: str, scene_name: str) -> Path:
        level_path = project_root / "levels" / filename
        level_path.parent.mkdir(parents=True, exist_ok=True)
        level_path.write_text(
            json.dumps(
                {
                    "name": scene_name,
                    "entities": [],
                    "rules": [],
                },
                indent=4,
            ),
            encoding="utf-8",
        )
        return level_path

    def _copy_real_scene(self, project_root: Path, filename: str) -> Path:
        source = REPO_ROOT / "levels" / filename
        target = project_root / "levels" / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        return target

    def _copy_real_script(self, project_root: Path, filename: str) -> Path:
        source = REPO_ROOT / "scripts" / filename
        target = project_root / "scripts" / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        return target

    def test_engine_api_open_project_loads_last_scene_and_updates_recents(self) -> None:
        project_a_root, project_a_service = self._make_project("ProjectA")
        project_b_root, project_b_service = self._make_project("ProjectB")
        self._write_level(project_a_root, "a_scene.json", "Scene A")
        self._write_level(project_b_root, "b_first.json", "Scene B1")
        self._write_level(project_b_root, "b_last.json", "Scene B2")
        project_b_service.set_last_scene("levels/b_last.json")

        self.api = EngineAPI(project_root=project_a_root.as_posix(), global_state_dir=self.global_state_dir.as_posix())
        self.api.load_level("levels/a_scene.json")

        result = self.api.open_project(project_b_root.as_posix())

        self.assertTrue(result["success"])
        self.assertEqual(self.api.project_service.project_root, project_b_root.resolve())
        self.assertEqual(self.api.scene_manager.scene_name, "Scene B2")
        self.assertEqual(self.api.project_service.get_last_scene(), "levels/b_last.json")
        self.assertTrue(self.api.game.current_scene_path.endswith("levels/b_last.json"))
        self.assertEqual(self.api.list_recent_projects()[0]["path"], project_b_root.resolve().as_posix())
        self.assertEqual(project_a_service.project_root, project_a_root.resolve())

    def test_script_executor_can_open_project_and_write_editor_state(self) -> None:
        project_a_root, _ = self._make_project("ScriptProjectA")
        project_b_root, project_b_service = self._make_project("ScriptProjectB")
        self._write_level(project_a_root, "bootstrap.json", "Bootstrap")
        self._write_level(project_b_root, "target.json", "Target")
        project_b_service.set_last_scene("levels/target.json")

        self.api = EngineAPI(project_root=project_a_root.as_posix(), global_state_dir=self.global_state_dir.as_posix())
        self.api.load_level("levels/bootstrap.json")
        executor = ScriptExecutor(self.api.game)
        executor.commands = [
            {"action": "OPEN_PROJECT", "args": {"path": project_b_root.as_posix()}},
            {"action": "SET_EDITOR_STATE", "args": {"state": {"last_scene": "levels/target.json", "preferences": {"panel": "PROJECT"}}}},
        ]

        self.assertTrue(executor.run_all())
        self.assertEqual(self.api.project_service.project_root, project_b_root.resolve())
        self.assertEqual(self.api.get_editor_state()["preferences"]["panel"], "PROJECT")
        self.assertEqual(self.api.scene_manager.scene_name, "Target")

    def test_open_project_without_saved_scene_loads_first_available_level(self) -> None:
        project_root, _ = self._make_project("FirstSceneProject")
        self._write_level(project_root, "b_scene.json", "B Scene")
        self._write_level(project_root, "a_scene.json", "A Scene")

        self.api = EngineAPI(project_root=project_root.as_posix(), global_state_dir=self.global_state_dir.as_posix())

        result = self.api.open_project(project_root.as_posix())

        self.assertTrue(result["success"])
        self.assertEqual(self.api.scene_manager.scene_name, "Main Scene")
        self.assertTrue(self.api.game.current_scene_path.endswith("levels/main_scene.json"))

    def test_open_project_without_levels_creates_empty_scene(self) -> None:
        project_root, _ = self._make_project("EmptyProject")

        self.api = EngineAPI(project_root=project_root.as_posix(), global_state_dir=self.global_state_dir.as_posix())

        result = self.api.open_project(project_root.as_posix())

        self.assertTrue(result["success"])
        self.assertEqual(self.api.scene_manager.scene_name, "Main Scene")
        self.assertTrue(self.api.game.current_scene_path.endswith("levels/main_scene.json"))

    def test_workspace_state_round_trip_restores_multiple_open_scenes(self) -> None:
        project_root, _ = self._make_project("WorkspaceProject")
        self._write_level(project_root, "intro.json", "Intro")
        self._write_level(project_root, "boss.json", "Boss")

        self.api = EngineAPI(project_root=project_root.as_posix(), global_state_dir=self.global_state_dir.as_posix())
        self.api.load_level("levels/intro.json")
        self.assertTrue(self.api.open_scene("levels/boss.json")["success"])
        self.assertTrue(self.api.activate_scene("levels/intro.json")["success"])

        state = self.api.get_editor_state()
        self.assertEqual(state["open_scenes"], ["levels/intro.json", "levels/boss.json"])
        self.assertEqual(state["active_scene"], "levels/intro.json")

        restored_api = EngineAPI(project_root=project_root.as_posix(), global_state_dir=self.global_state_dir.as_posix())
        self.addCleanup(restored_api.shutdown)

        result = restored_api.open_project(project_root.as_posix())

        self.assertTrue(result["success"])
        self.assertEqual(len(restored_api.list_open_scenes()), 2)
        self.assertTrue(restored_api.get_active_scene()["path"].endswith("levels/intro.json"))

    def test_create_scene_persists_named_file_immediately(self) -> None:
        project_root, _ = self._make_project("CreateSceneProject")

        self.api = EngineAPI(project_root=project_root.as_posix(), global_state_dir=self.global_state_dir.as_posix())

        result = self.api.create_scene("Boss Intro")

        self.assertTrue(result["success"])
        created_path = project_root / "levels" / "boss_intro.json"
        self.assertTrue(created_path.exists())
        raw = json.loads(created_path.read_text(encoding="utf-8"))
        self.assertEqual(raw["name"], "Boss Intro")
        self.assertTrue(self.api.game.current_scene_path.endswith("levels/boss_intro.json"))

    def test_dirty_scene_changes_autosave_to_active_scene_file(self) -> None:
        project_root, _ = self._make_project("AutosaveProject")

        self.api = EngineAPI(project_root=project_root.as_posix(), global_state_dir=self.global_state_dir.as_posix())
        self.assertTrue(self.api.create_scene("Autosave Scene")["success"])
        scene_path = project_root / "levels" / "autosave_scene.json"

        self.assertTrue(self.api.create_entity("Hero")["success"])
        self.assertTrue(self.api.edit_component("Hero", "Transform", "x", 128.0)["success"])

        self.api.game._autosave_dirty_scenes()

        raw = json.loads(scene_path.read_text(encoding="utf-8"))
        hero = next(entity for entity in raw["entities"] if entity["name"] == "Hero")
        self.assertEqual(hero["components"]["Transform"]["x"], 128.0)
        self.assertFalse(self.api.scene_manager.is_dirty)

    def test_scene_flow_connections_are_serialized_and_can_load_next_scene(self) -> None:
        project_root, _ = self._make_project("FlowProject")
        first_path = self._write_level(project_root, "first.json", "First")
        second_path = self._write_level(project_root, "second.json", "Second")

        self.api = EngineAPI(project_root=project_root.as_posix(), global_state_dir=self.global_state_dir.as_posix())
        self.api.load_level(first_path.as_posix())

        set_result = self.api.set_next_scene(second_path.as_posix())
        connections = self.api.get_scene_connections()

        self.assertTrue(set_result["success"])
        self.assertEqual(connections["next_scene"], "levels/second.json")

        self.api.game.save_current_scene()
        raw = json.loads(first_path.read_text(encoding="utf-8"))
        self.assertEqual(raw["feature_metadata"]["scene_flow"]["next_scene"], "levels/second.json")

        load_result = self.api.load_next_scene()

        self.assertTrue(load_result["success"])
        self.assertEqual(self.api.scene_manager.scene_name, "Second")
        self.assertTrue(self.api.game.current_scene_path.endswith("levels/second.json"))
        self.assertEqual(self.api.project_service.get_last_scene(), "levels/second.json")

    def test_scene_flow_connection_can_be_cleared(self) -> None:
        project_root, _ = self._make_project("FlowClearProject")
        first_path = self._write_level(project_root, "first.json", "First")
        second_path = self._write_level(project_root, "second.json", "Second")

        self.api = EngineAPI(project_root=project_root.as_posix(), global_state_dir=self.global_state_dir.as_posix())
        self.api.load_level(first_path.as_posix())
        self.assertTrue(self.api.set_menu_scene(second_path.as_posix())["success"])

        clear_result = self.api.set_menu_scene("")

        self.assertTrue(clear_result["success"])
        self.assertEqual(self.api.get_scene_connections(), {})

    def test_script_context_can_load_next_scene_in_play_mode(self) -> None:
        project_root, _ = self._make_project("FlowScriptProject")
        first_path = self._write_level(project_root, "first.json", "First")
        second_path = self._write_level(project_root, "second.json", "Second")
        script_path = project_root / "scripts" / "flow_jump.py"
        script_path.write_text(
            "def on_update(context, dt):\n"
            "    if context.public_data.get('done'):\n"
            "        return\n"
            "    context.public_data['done'] = True\n"
            "    context.load_scene_flow_target('next_scene')\n",
            encoding="utf-8",
        )

        raw_first = json.loads(first_path.read_text(encoding="utf-8"))
        raw_first["entities"] = [
            {
                "name": "FlowRunner",
                "active": True,
                "tag": "System",
                "layer": "Default",
                "components": {
                    "Transform": {
                        "enabled": True,
                        "x": 0.0,
                        "y": 0.0,
                        "rotation": 0.0,
                        "scale_x": 1.0,
                        "scale_y": 1.0,
                    },
                    "ScriptBehaviour": {
                        "enabled": True,
                        "module_path": "flow_jump",
                        "run_in_edit_mode": False,
                        "public_data": {"done": False},
                    },
                },
            }
        ]
        raw_first["feature_metadata"] = {"scene_flow": {"next_scene": "levels/second.json"}}
        first_path.write_text(json.dumps(raw_first, indent=4), encoding="utf-8")

        self.api = EngineAPI(project_root=project_root.as_posix(), global_state_dir=self.global_state_dir.as_posix())
        self.api.load_level(first_path.as_posix())
        self.api.play()
        self.api.step(1)

        self.assertEqual(self.api.scene_manager.scene_name, "Second")
        self.assertTrue(self.api.game.current_scene_path.endswith("levels/second.json"))
        self.assertTrue(self.api.game.is_play_mode)

    def test_real_platformer_scene_can_persist_menu_connection_and_load_menu_scene(self) -> None:
        project_root, _ = self._make_project("RealSceneFlowProject")
        menu_path = self._copy_real_scene(project_root, "main_menu_scene.json")
        platformer_path = self._copy_real_scene(project_root, "platformer_test_scene.json")
        self._copy_real_script(project_root, "main_menu_controller.py")

        self.api = EngineAPI(project_root=project_root.as_posix(), global_state_dir=self.global_state_dir.as_posix())
        self.api.load_level("levels/platformer_test_scene.json")

        set_result = self.api.set_menu_scene("levels/main_menu_scene.json")
        self.api.game.save_current_scene()
        raw_platformer = json.loads(platformer_path.read_text(encoding="utf-8"))
        load_result = self.api.load_menu_scene()

        self.assertTrue(set_result["success"])
        self.assertEqual(raw_platformer["feature_metadata"]["scene_flow"]["menu_scene"], "levels/main_menu_scene.json")
        self.assertTrue(load_result["success"])
        self.assertEqual(self.api.scene_manager.scene_name, "Main Menu Scene")
        self.assertTrue(self.api.game.current_scene_path.endswith("levels/main_menu_scene.json"))
        self.assertEqual(self.api.project_service.get_last_scene(), "levels/main_menu_scene.json")
        self.assertTrue(menu_path.exists())

    def test_real_main_menu_scene_can_load_platformer_with_next_scene(self) -> None:
        project_root, _ = self._make_project("RealMenuFlowProject")
        self._copy_real_scene(project_root, "main_menu_scene.json")
        self._copy_real_scene(project_root, "platformer_test_scene.json")
        self._copy_real_script(project_root, "main_menu_controller.py")

        self.api = EngineAPI(project_root=project_root.as_posix(), global_state_dir=self.global_state_dir.as_posix())
        self.api.load_level("levels/main_menu_scene.json")

        self.assertEqual(self.api.get_scene_connections()["next_scene"], "levels/platformer_test_scene.json")

        load_result = self.api.load_next_scene()

        self.assertTrue(load_result["success"])
        self.assertEqual(self.api.scene_manager.scene_name, "Platformer Test Scene")
        self.assertTrue(self.api.game.current_scene_path.endswith("levels/platformer_test_scene.json"))
        self.assertEqual(self.api.project_service.get_last_scene(), "levels/platformer_test_scene.json")

    def test_real_main_menu_scene_uses_canvas_button_to_start_game(self) -> None:
        project_root, _ = self._make_project("RealMenuButtonProject")
        self._copy_real_scene(project_root, "main_menu_scene.json")
        self._copy_real_scene(project_root, "platformer_test_scene.json")

        self.api = EngineAPI(project_root=project_root.as_posix(), global_state_dir=self.global_state_dir.as_posix())
        self.api.load_level("levels/main_menu_scene.json")

        menu_entities = {entity["name"] for entity in self.api.list_ui_nodes()}
        self.assertIn("PlayButton", menu_entities)
        self.assertIn("MainCanvas", menu_entities)

        result = self.api.click_ui_button("PlayButton")

        self.assertTrue(result["success"])
        self.assertEqual(self.api.scene_manager.scene_name, "Platformer Test Scene")
        self.assertTrue(self.api.game.current_scene_path.endswith("levels/platformer_test_scene.json"))


if __name__ == "__main__":
    unittest.main()
