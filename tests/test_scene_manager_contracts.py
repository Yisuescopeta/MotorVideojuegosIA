import copy
import inspect
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import engine.scenes.scene_manager as scene_manager_module
from engine.levels.component_registry import create_default_registry
from engine.scenes.edit_sync import LEGACY_AUTHORING_SYNC_REASON, TRANSIENT_PREVIEW_SYNC_REASON
from engine.scenes.prefab_overrides import PrefabOverrideService
from engine.scenes.scene_manager import SceneManager
from engine.scenes.structural_authoring import ScenePrefabAuthoring, SceneStructuralAuthoring
from engine.scenes.workspace_lifecycle import SceneWorkspace, SceneWorkspaceEntry


class SceneManagerContractsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = SceneManager(create_default_registry())
        self.manager.load_scene(
            {
                "name": "Contracts Probe",
                "entities": [
                    {
                        "name": "Player",
                        "active": True,
                        "tag": "Untagged",
                        "layer": "Default",
                        "components": {
                            "Transform": {
                                "enabled": True,
                                "x": 10.0,
                                "y": 20.0,
                                "rotation": 0.0,
                                "scale_x": 1.0,
                                "scale_y": 1.0,
                            }
                        },
                    }
                ],
                "rules": [],
                "feature_metadata": {},
            }
        )

    def test_projection_algorithms_are_not_implemented_by_manager(self) -> None:
        source = inspect.getsource(scene_manager_module)

        self.assertNotIn("engine.serialization.schema", source)
        self.assertNotIn("self._registry.create(", source)
        self.assertFalse(hasattr(self.manager, "_install_scene_payload"))
        self.assertFalse(hasattr(self.manager, "_rebuild_edit_world"))
        self.assertFalse(hasattr(self.manager, "_build_canonical_scene_payload"))

    def test_prefab_override_authority_is_extracted_and_shared(self) -> None:
        manager_source = inspect.getsource(SceneManager)
        serializable_source = inspect.getsource(self.manager._serializable_authoring.__class__)
        prefab_authoring_source = inspect.getsource(ScenePrefabAuthoring)
        structural_source = inspect.getsource(SceneStructuralAuthoring)

        self.assertIsInstance(self.manager._prefab_overrides, PrefabOverrideService)
        self.assertIs(
            self.manager._structural_authoring._prefab_overrides,
            self.manager._prefab_overrides,
        )
        self.assertIs(
            self.manager._serializable_authoring._prefab_overrides,
            self.manager._prefab_overrides,
        )
        for direct_call in (
            "self._prefab_overrides.update_component_property(",
            "self._prefab_overrides.update_entity_property(",
            "self._prefab_overrides.replace_component(",
            "self._prefab_overrides.remove_component(",
        ):
            self.assertNotIn(direct_call, manager_source)
            self.assertIn(direct_call, serializable_source)
            self.assertIn(direct_call, structural_source)
        for removed_name in (
            "_update_prefab_component_override",
            "_update_prefab_entity_override",
            "_replace_prefab_component_override",
            "_remove_prefab_component_override",
            "_ensure_prefab_override_ops",
            "_upsert_prefab_override_operation",
            "_remove_prefab_override_operations",
        ):
            self.assertFalse(hasattr(self.manager, removed_name))
        for moved_algorithm in (
            "ensure_prefab_override_ops",
            "upsert_prefab_override_operation",
            "remove_prefab_override_operations",
            "_resolve_prefab_override_target",
        ):
            self.assertNotIn(moved_algorithm, prefab_authoring_source)
            self.assertNotIn(moved_algorithm, structural_source)

    def test_pending_edit_sync_policy_is_not_implemented_by_manager(self) -> None:
        source = inspect.getsource(scene_manager_module)
        manager_source = inspect.getsource(SceneManager)
        entry_source = inspect.getsource(SceneWorkspaceEntry)

        self.assertIn("pending_edit_world_sync_reason: Optional[str]", entry_source)
        self.assertNotIn("entry.pending_edit_world_sync_reason", manager_source)
        self.assertNotIn("dirty_before_pending_edit_world_sync", source)
        self.assertFalse(hasattr(self.manager, "_flush_pending_edit_world"))
        self.assertFalse(hasattr(self.manager, "_clear_pending_edit_world_sync"))
        self.assertFalse(hasattr(self.manager, "_sync_entry_from_edit_world"))

    def test_legacy_sync_reason_constants_remain_reexported_by_manager_module(self) -> None:
        self.assertEqual(
            scene_manager_module.LEGACY_AUTHORING_SYNC_REASON,
            LEGACY_AUTHORING_SYNC_REASON,
        )
        self.assertEqual(
            scene_manager_module.TRANSIENT_PREVIEW_SYNC_REASON,
            TRANSIENT_PREVIEW_SYNC_REASON,
        )

    def test_runtime_port_is_memoized_and_preserves_play_stop_semantics(self) -> None:
        port = self.manager.runtime_port

        self.assertIs(port, self.manager.runtime_port)
        self.assertIs(port.current_scene, self.manager.current_scene)
        self.assertIs(port.active_world, self.manager.active_world)

        runtime_world = port.enter_play()

        self.assertIsNotNone(runtime_world)
        self.assertTrue(self.manager.is_playing)
        self.assertIs(runtime_world, self.manager.active_world)

        edit_world = port.exit_play()

        self.assertIsNotNone(edit_world)
        self.assertFalse(self.manager.is_playing)
        self.assertIs(edit_world, self.manager.active_world)

    def test_authoring_and_workspace_ports_delegate_serializable_state(self) -> None:
        authoring = self.manager.authoring_port
        workspace = self.manager.workspace_port

        self.assertIs(authoring, self.manager.authoring_port)
        self.assertIs(workspace, self.manager.workspace_port)
        self.assertTrue(
            authoring.create_entity(
                "Enemy",
                components={
                    "Transform": {
                        "enabled": True,
                        "x": 8.0,
                        "y": 4.0,
                        "rotation": 0.0,
                        "scale_x": 1.0,
                        "scale_y": 1.0,
                    }
                },
            )
        )
        self.assertTrue(authoring.set_feature_metadata("phase_1", {"enabled": True}))
        self.assertTrue(workspace.set_scene_flow_target("next_scene", "levels/next_scene.json"))
        self.assertEqual(authoring.get_component_data("Enemy", "Transform")["x"], 8.0)
        enemy_data = self.manager.find_entity_data("Enemy")
        self.assertIsInstance(enemy_data.get("id"), str)
        self.assertTrue(enemy_data["id"])

        with tempfile.TemporaryDirectory() as temp_dir:
            scene_path = Path(temp_dir) / "contracts_probe.json"

            self.assertTrue(workspace.save_scene_to_file(scene_path.as_posix(), key=workspace.active_scene_key))

            reloaded = SceneManager(create_default_registry())
            self.assertIsNotNone(reloaded.load_scene_from_file(scene_path.as_posix()))
            self.assertIsNotNone(reloaded.find_entity_data("Enemy"))
            self.assertEqual(reloaded.get_feature_metadata()["phase_1"], {"enabled": True})
            self.assertEqual(reloaded.get_scene_flow()["next_scene"], "levels/next_scene.json")

    def test_internal_id_authoring_wrappers_resolve_current_name(self) -> None:
        player_id = self.manager.find_entity_data("Player")["id"]

        self.assertTrue(self.manager.update_entity_property_by_id(player_id, "tag", "Hero"))
        self.assertEqual(self.manager.find_entity_data("Player")["tag"], "Hero")
        self.assertTrue(
            self.manager.add_component_to_entity_by_id(
                player_id,
                "Marker2D",
                {"enabled": True, "marker_name": "player"},
            )
        )
        self.assertEqual(
            self.manager.find_entity_data_by_id(player_id)["components"]["Marker2D"]["marker_name"],
            "player",
        )
        self.assertTrue(self.manager.update_entity_property_by_id(player_id, "name", "RenamedPlayer"))
        self.assertIsNone(self.manager.find_entity_data("Player"))
        self.assertEqual(self.manager.find_entity_data_by_id(player_id)["name"], "RenamedPlayer")
        self.assertTrue(self.manager.remove_component_from_entity_by_id(player_id, "Marker2D"))
        self.assertNotIn("Marker2D", self.manager.find_entity_data_by_id(player_id)["components"])

    def test_selected_entity_rename_preserves_selection_by_id(self) -> None:
        player_id = self.manager.find_entity_data("Player")["id"]

        self.assertTrue(self.manager.set_selected_entity("Player"))
        self.assertTrue(self.manager.update_entity_property("Player", "name", "Hero"))

        self.assertEqual(self.manager.resolve_entry(None).selected_entity_id, player_id)
        self.assertEqual(self.manager.resolve_entry(None).selected_entity_name, "Hero")
        self.assertEqual(self.manager.get_edit_world().selected_entity_name, "Hero")
        self.assertIsNone(self.manager.find_entity_data("Player"))
        self.assertEqual(self.manager.find_entity_data_by_id(player_id)["name"], "Hero")

    def test_selected_renamed_entity_survives_play_stop_rebuild(self) -> None:
        player_id = self.manager.find_entity_data("Player")["id"]

        self.assertTrue(self.manager.set_selected_entity("Player"))
        self.assertTrue(self.manager.update_entity_property("Player", "name", "Hero"))

        runtime_world = self.manager.enter_play()
        self.assertIsNotNone(runtime_world)
        self.assertEqual(runtime_world.selected_entity_name, "Hero")

        edit_world = self.manager.exit_play()
        self.assertIsNotNone(edit_world)
        self.assertEqual(edit_world.selected_entity_name, "Hero")
        self.assertEqual(self.manager.resolve_entry(None).selected_entity_id, player_id)

    def test_reparent_renamed_entity_resolves_current_name_from_id(self) -> None:
        player_id = self.manager.find_entity_data("Player")["id"]
        self.assertTrue(self.manager.create_entity("Parent"))
        self.assertTrue(self.manager.update_entity_property_by_id(player_id, "name", "Hero"))

        self.assertTrue(self.manager.set_entity_parent("Hero", "Parent"))

        self.assertEqual(self.manager.find_entity_data_by_id(player_id)["parent"], "Parent")

    def test_workspace_canonicalizes_windows_short_path_aliases(self) -> None:
        alias_path = "C:/Users/RUNNER~1/AppData/Local/Temp/secondary.json"
        canonical_path = Path("C:/Users/runneradmin/AppData/Local/Temp/secondary.json")

        with patch("engine.scenes.workspace_lifecycle.Path.resolve", return_value=canonical_path):
            self.manager.load_scene(
                {
                    "name": "Secondary",
                    "entities": [],
                    "rules": [],
                    "feature_metadata": {},
                },
                source_path=alias_path,
                activate=False,
            )
            entry = self.manager.resolve_entry(alias_path)

        self.assertIsNotNone(entry)
        self.assertEqual(entry.key, canonical_path.as_posix())
        self.assertEqual(entry.source_path, canonical_path.as_posix())

    def test_serializable_rollback_restores_full_pending_sync_state(self) -> None:
        primary_key = self.manager.active_scene_key
        with tempfile.TemporaryDirectory() as temp_dir:
            secondary_path = Path(temp_dir) / "secondary.json"
            self.manager.load_scene(
                {
                    "name": "Secondary",
                    "entities": [
                        {
                            "name": "SecondaryPlayer",
                            "active": True,
                            "tag": "Untagged",
                            "layer": "Default",
                            "components": {},
                        }
                    ],
                    "rules": [],
                    "feature_metadata": {},
                },
                source_path=secondary_path.as_posix(),
                activate=False,
            )
            entry = self.manager.resolve_entry(secondary_path.as_posix())
            self.assertIsNotNone(entry)

            player_id = entry.scene.find_entity("SecondaryPlayer")["id"]
            entry.selected_entity_name = "SecondaryPlayer"
            entry.selected_entity_id = player_id
            entry.edit_world.selected_entity_name = "SecondaryPlayer"
            self.assertIsNotNone(self.manager.activate_scene(entry.key))
            self.assertTrue(self.manager.mark_edit_world_dirty())
            self.manager.clear_dirty()
            self.assertIsNotNone(self.manager.activate_scene(primary_key))
            entry.edit_world_version = 777
            scene_before = copy.deepcopy(entry.scene.to_dict())
            original_install = SceneWorkspace.install_entry_state
            install_calls = 0

            def fail_first_install(_workspace, *args, **kwargs):
                nonlocal install_calls
                install_calls += 1
                if install_calls == 1:
                    raise ValueError("reject mutation")
                return original_install(*args, **kwargs)

            with patch.object(
                SceneWorkspace,
                "install_entry_state",
                new=fail_first_install,
            ):
                changed = self.manager.upsert_component_for_scene(
                    entry.key,
                    "SecondaryPlayer",
                    "Marker2D",
                    {"enabled": True, "marker_name": "probe"},
                )

        self.assertFalse(changed)
        self.assertEqual(entry.scene.to_dict(), scene_before)
        self.assertEqual(entry.selected_entity_name, "SecondaryPlayer")
        self.assertEqual(entry.selected_entity_id, player_id)
        self.assertEqual(entry.edit_world.selected_entity_name, "SecondaryPlayer")
        self.assertFalse(entry.dirty)
        self.assertEqual(entry.pending_edit_world_sync_reason, LEGACY_AUTHORING_SYNC_REASON)
        self.assertFalse(entry.dirty_before_pending_edit_world_sync)
        self.assertNotEqual(entry.edit_world_version, 777)
        self.assertEqual(entry.edit_world_version, entry.edit_world.version)


if __name__ == "__main__":
    unittest.main()
