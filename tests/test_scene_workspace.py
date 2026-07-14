import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from engine.levels.component_registry import create_default_registry
from engine.scenes.scene_flow import SceneFlowPolicy
from engine.scenes.scene_manager import SceneManager
from engine.scenes.scene_projection import SceneProjectionService
from engine.scenes.workspace_lifecycle import SceneWorkspace, SceneWorkspaceEntry


class SceneWorkspaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scene_manager = SceneManager(create_default_registry())

    def _transform_payload(self) -> dict:
        return {
            "enabled": True,
            "x": 0.0,
            "y": 0.0,
            "rotation": 0.0,
            "scale_x": 1.0,
            "scale_y": 1.0,
        }

    def test_exit_play_clears_pending_edit_sync(self) -> None:
        self.scene_manager.load_scene(
            {"name": "Exit", "entities": [], "rules": [], "feature_metadata": {}}
        )
        entry = self.scene_manager.resolve_entry(None)
        assert entry is not None
        self.assertTrue(self.scene_manager.mark_edit_world_dirty())
        self.assertIsNotNone(self.scene_manager.enter_play())

        self.assertIsNotNone(self.scene_manager.exit_play())

        self.assertFalse(entry.edit_world_sync_pending)
        self.assertIsNone(entry.dirty_before_pending_edit_world_sync)

    def test_reload_scene_clears_pending_edit_sync(self) -> None:
        self.scene_manager.load_scene(
            {"name": "Reload", "entities": [], "rules": [], "feature_metadata": {}}
        )
        entry = self.scene_manager.resolve_entry(None)
        assert entry is not None
        self.assertTrue(self.scene_manager.mark_edit_world_dirty())

        self.assertIsNotNone(self.scene_manager.reload_scene())

        self.assertFalse(entry.edit_world_sync_pending)
        self.assertIsNone(entry.dirty_before_pending_edit_world_sync)
        self.assertFalse(entry.dirty)

    def test_scene_link_syncs_feature_metadata_and_invalid_badge(self) -> None:
        self.scene_manager.load_scene(
            {
                "name": "Links",
                "entities": [
                    {
                        "name": "Portal",
                        "active": True,
                        "tag": "Untagged",
                        "layer": "Default",
                        "components": {"Transform": self._transform_payload()},
                    }
                ],
                "rules": [],
                "feature_metadata": {},
            }
        )

        added = self.scene_manager.add_component_to_entity(
            "Portal",
            "SceneLink",
            {
                "enabled": True,
                "target_path": "levels/menu.json",
                "flow_key": "menu_scene",
                "preview_label": "Main Menu",
            },
        )

        self.assertTrue(added)
        self.assertEqual(self.scene_manager.get_scene_flow(), {"menu_scene": "levels/menu.json"})
        self.assertEqual(
            self.scene_manager.current_scene.feature_metadata["scene_flow"]["menu_scene"],
            "levels/menu.json",
        )
        self.assertFalse(self.scene_manager.list_open_scenes()[0]["has_invalid_links"])

        self.assertTrue(
            self.scene_manager.replace_component_data(
                "Portal",
                "SceneLink",
                {
                    "enabled": True,
                    "target_path": "",
                    "flow_key": "menu_scene",
                    "preview_label": "Broken",
                },
            )
        )
        self.assertTrue(self.scene_manager.list_open_scenes()[0]["has_invalid_links"])

    def test_component_metadata_persists_through_scene_and_world(self) -> None:
        self.scene_manager.load_scene(
            {
                "name": "Metadata",
                "entities": [
                    {
                        "name": "Actor",
                        "active": True,
                        "tag": "Untagged",
                        "layer": "Default",
                        "components": {"Transform": self._transform_payload()},
                    }
                ],
                "rules": [],
                "feature_metadata": {},
            }
        )

        updated = self.scene_manager.set_component_metadata("Actor", "Transform", {"origin": "ai_custom"})

        self.assertTrue(updated)
        self.assertEqual(
            self.scene_manager.current_scene.find_entity("Actor")["component_metadata"]["Transform"]["origin"],
            "ai_custom",
        )


        world = self.scene_manager.get_edit_world()
        actor = world.get_entity_by_name("Actor")
        self.assertEqual(actor.get_component_metadata_by_name("Transform")["origin"], "ai_custom")

    def test_copy_paste_entities_between_open_scenes(self) -> None:
        self.scene_manager.create_new_scene("Scene A")
        self.assertTrue(
            self.scene_manager.create_entity(
                "Root",
                components={
                    "Transform": self._transform_payload(),
                    "SceneLink": {
                        "enabled": True,
                        "target_path": "levels/next.json",
                        "flow_key": "next_scene",
                        "preview_label": "Next",
                    },
                },
            )
        )
        self.assertTrue(self.scene_manager.create_child_entity("Root", "Child", {"Transform": self._transform_payload()}))
        scene_a_key = self.scene_manager.active_scene_key

        self.assertTrue(self.scene_manager.copy_entity_subtree("Root"))
        self.scene_manager.create_new_scene("Scene B", activate=False)
        scene_b_key = next(scene["key"] for scene in self.scene_manager.list_open_scenes() if scene["name"] == "Scene B")
        self.assertIsNotNone(self.scene_manager.activate_scene(scene_b_key))

        pasted = self.scene_manager.paste_copied_entities()

        self.assertTrue(pasted)
        scene_b_world = self.scene_manager.get_edit_world()
        self.assertIsNotNone(scene_b_world.get_entity_by_name("Root"))
        self.assertIsNotNone(scene_b_world.get_entity_by_name("Child"))

        self.assertIsNotNone(self.scene_manager.activate_scene(scene_a_key))
        scene_a_world = self.scene_manager.get_edit_world()
        self.assertIsNotNone(scene_a_world.get_entity_by_name("Root"))
        self.assertIsNotNone(scene_a_world.get_entity_by_name("Child"))

    def test_copy_paste_subtree_preserves_internal_parent_and_renames_conflicts(self) -> None:
        self.scene_manager.create_new_scene("Source")
        self.assertTrue(self.scene_manager.create_entity("Root", components={"Transform": self._transform_payload()}))
        self.assertTrue(self.scene_manager.create_child_entity("Root", "Child", {"Transform": self._transform_payload()}))
        source_key = self.scene_manager.active_scene_key

        self.assertTrue(self.scene_manager.copy_entity_subtree("Root"))

        self.scene_manager.create_new_scene("Target", activate=False)
        target_key = next(scene["key"] for scene in self.scene_manager.list_open_scenes() if scene["name"] == "Target")
        self.assertIsNotNone(self.scene_manager.activate_scene(target_key))
        self.assertTrue(self.scene_manager.create_entity("Root", components={"Transform": self._transform_payload()}))

        pasted = self.scene_manager.paste_copied_entities()

        self.assertTrue(pasted)
        target_world = self.scene_manager.get_edit_world()
        pasted_root = target_world.get_entity_by_name("Root_copy")
        pasted_child = target_world.get_entity_by_name("Child")
        self.assertIsNotNone(pasted_root)
        self.assertIsNotNone(pasted_child)
        self.assertEqual(pasted_child.parent_name, "Root_copy")

        self.assertIsNotNone(self.scene_manager.activate_scene(source_key))
        source_world = self.scene_manager.get_edit_world()
        self.assertIsNotNone(source_world.get_entity_by_name("Root"))
        self.assertIsNotNone(source_world.get_entity_by_name("Child"))
        self.assertIsNone(source_world.get_entity_by_name("Root_copy"))

    def test_workspace_activate_and_close_preserves_expected_active_scene(self) -> None:
        self.scene_manager.create_new_scene("Scene A")
        scene_a_key = self.scene_manager.active_scene_key
        self.scene_manager.create_new_scene("Scene B", activate=False)
        scene_b_key = next(scene["key"] for scene in self.scene_manager.list_open_scenes() if scene["name"] == "Scene B")

        self.assertEqual(self.scene_manager.active_scene_key, scene_a_key)
        self.assertTrue(self.scene_manager.close_scene(scene_b_key, discard_changes=True))
        self.assertEqual(self.scene_manager.active_scene_key, scene_a_key)

        self.scene_manager.create_new_scene("Scene C", activate=False)
        scene_c_key = next(scene["key"] for scene in self.scene_manager.list_open_scenes() if scene["name"] == "Scene C")
        self.assertIsNotNone(self.scene_manager.activate_scene(scene_c_key))
        self.assertEqual(self.scene_manager.active_scene_key, scene_c_key)

        self.assertTrue(self.scene_manager.close_scene(scene_c_key, discard_changes=True))
        self.assertEqual(self.scene_manager.active_scene_key, scene_a_key)

    def test_activate_scene_is_blocked_while_active_scene_is_playing(self) -> None:
        self.scene_manager.create_new_scene("Scene A")
        scene_a_key = self.scene_manager.active_scene_key
        self.scene_manager.create_new_scene("Scene B", activate=False)
        scene_b_key = next(scene["key"] for scene in self.scene_manager.list_open_scenes() if scene["name"] == "Scene B")

        runtime_world = self.scene_manager.enter_play()

        self.assertIsNotNone(runtime_world)
        self.assertIsNone(self.scene_manager.activate_scene(scene_b_key))
        self.assertEqual(self.scene_manager.active_scene_key, scene_a_key)
        self.assertTrue(self.scene_manager.is_playing)

    def test_workspace_state_tracks_active_scene_and_view_state(self) -> None:
        self.scene_manager.create_new_scene("Scene A")
        scene_a_key = self.scene_manager.active_scene_key
        self.scene_manager.set_scene_view_state(
            scene_a_key,
            {
                "selected_entity": "Hero",
                "camera_target": {"x": 12.0, "y": 24.0},
                "camera_zoom": 1.75,
            },
        )
        self.scene_manager.create_new_scene("Scene B", activate=False)
        scene_b_key = next(scene["key"] for scene in self.scene_manager.list_open_scenes() if scene["name"] == "Scene B")
        self.assertIsNotNone(self.scene_manager.activate_scene(scene_b_key))

        workspace_state = self.scene_manager.get_workspace_state()

        self.assertEqual(workspace_state["active_scene"], scene_b_key)
        self.assertEqual(workspace_state["open_scenes"], [scene_a_key, scene_b_key])
        self.assertEqual(
            workspace_state["scene_view_states"][scene_a_key],
            {
                "selected_entity": "Hero",
                "camera_target": {"x": 12.0, "y": 24.0},
                "camera_zoom": 1.75,
            },
        )

    def test_edit_play_stop_cycle_restores_edit_world_without_dirtying_scene(self) -> None:
        self.scene_manager.load_scene(
            {
                "name": "PlayProbe",
                "entities": [
                    {
                        "name": "Player",
                        "active": True,
                        "tag": "Untagged",
                        "layer": "Default",
                        "components": {"Transform": self._transform_payload()},
                    }
                ],
                "rules": [],
                "feature_metadata": {},
            }
        )
        edit_world = self.scene_manager.get_edit_world()
        self.scene_manager.set_selected_entity("Player")

        runtime_world = self.scene_manager.enter_play()

        self.assertIsNotNone(runtime_world)
        self.assertTrue(self.scene_manager.is_playing)
        self.assertFalse(self.scene_manager.is_dirty)
        runtime_world.selected_entity_name = "Player"

        restored_world = self.scene_manager.exit_play()

        self.assertIs(restored_world, self.scene_manager.get_edit_world())
        self.assertIsNot(restored_world, runtime_world)
        self.assertIsNot(restored_world, edit_world)
        self.assertFalse(self.scene_manager.is_playing)
        self.assertFalse(self.scene_manager.is_dirty)
        self.assertEqual(restored_world.selected_entity_name, "Player")

    def test_selection_is_isolated_and_restored_per_workspace_entry(self) -> None:
        self.scene_manager.create_new_scene("Scene A")
        self.assertTrue(self.scene_manager.create_entity("ActorA", components={"Transform": self._transform_payload()}))
        self.assertTrue(self.scene_manager.set_selected_entity("ActorA"))
        scene_a_key = self.scene_manager.active_scene_key

        self.scene_manager.create_new_scene("Scene B", activate=False)
        scene_b_key = next(scene["key"] for scene in self.scene_manager.list_open_scenes() if scene["name"] == "Scene B")
        self.assertIsNotNone(self.scene_manager.activate_scene(scene_b_key))
        self.assertTrue(self.scene_manager.create_entity("ActorB", components={"Transform": self._transform_payload()}))
        self.assertTrue(self.scene_manager.set_selected_entity("ActorB"))

        self.assertIsNotNone(self.scene_manager.activate_scene(scene_a_key))
        self.assertEqual(self.scene_manager.resolve_entry(None).selected_entity_name, "ActorA")
        self.assertEqual(self.scene_manager.get_edit_world().selected_entity_name, "ActorA")

        self.assertIsNotNone(self.scene_manager.activate_scene(scene_b_key))
        self.assertEqual(self.scene_manager.resolve_entry(None).selected_entity_name, "ActorB")
        self.assertEqual(self.scene_manager.get_edit_world().selected_entity_name, "ActorB")

    def test_enter_play_prefers_live_edit_world_selection(self) -> None:
        self.scene_manager.load_scene(
            {
                "name": "LiveSelection",
                "entities": [
                    {
                        "name": name,
                        "active": True,
                        "tag": "Untagged",
                        "layer": "Default",
                        "components": {"Transform": self._transform_payload()},
                    }
                    for name in ("A", "B")
                ],
                "rules": [],
                "feature_metadata": {},
            }
        )
        self.assertTrue(self.scene_manager.set_selected_entity("A"))
        entry = self.scene_manager.resolve_entry(None)
        edit_world = self.scene_manager.get_edit_world()
        entity_b = self.scene_manager.find_entity_data("B")
        assert entry is not None
        assert edit_world is not None
        assert entity_b is not None
        expected_b_id = entity_b["id"]
        edit_world.selected_entity_name = "B"

        runtime_world = self.scene_manager.enter_play()

        self.assertIsNotNone(entry)
        self.assertIsNotNone(runtime_world)
        assert runtime_world is not None
        self.assertEqual(entry.selected_entity_name, "B")
        self.assertEqual(entry.selected_entity_id, expected_b_id)
        self.assertEqual(runtime_world.selected_entity_name, "B")

    def test_dirty_state_is_isolated_per_workspace_entry(self) -> None:
        self.scene_manager.create_new_scene("Clean Scene")
        clean_key = self.scene_manager.active_scene_key
        self.scene_manager.create_new_scene("Dirty Scene", activate=False)
        dirty_key = next(
            scene["key"] for scene in self.scene_manager.list_open_scenes() if scene["name"] == "Dirty Scene"
        )
        self.scene_manager.clear_all_dirty()

        self.assertIsNotNone(self.scene_manager.activate_scene(dirty_key))
        self.assertTrue(self.scene_manager.create_entity("Changed"))
        self.assertTrue(self.scene_manager.is_dirty)
        self.assertTrue(self.scene_manager.has_unsaved_scenes)

        self.assertIsNotNone(self.scene_manager.activate_scene(clean_key))
        self.assertFalse(self.scene_manager.is_dirty)
        self.assertTrue(self.scene_manager.has_unsaved_scenes)

        self.assertIsNotNone(self.scene_manager.activate_scene(dirty_key))
        self.assertTrue(self.scene_manager.is_dirty)

    def test_enter_play_clone_failure_rolls_back_lifecycle_without_losing_selection_or_dirty(self) -> None:
        self.scene_manager.load_scene(
            {
                "name": "CloneFailure",
                "entities": [
                    {
                        "name": "Player",
                        "active": True,
                        "tag": "Untagged",
                        "layer": "Default",
                        "components": {"Transform": self._transform_payload()},
                    }
                ],
                "rules": [],
                "feature_metadata": {},
            }
        )
        self.assertTrue(self.scene_manager.set_selected_entity("Player"))
        self.assertTrue(self.scene_manager.update_entity_property("Player", "tag", "Hero"))
        edit_world = self.scene_manager.get_edit_world()
        entry = self.scene_manager.resolve_entry(None)

        with patch.object(edit_world, "clone", side_effect=RuntimeError("clone failed")):
            runtime_world = self.scene_manager.enter_play()

        self.assertIsNone(runtime_world)
        self.assertFalse(self.scene_manager.is_playing)
        self.assertIs(self.scene_manager.active_world, edit_world)
        self.assertTrue(self.scene_manager.is_dirty)
        self.assertEqual(entry.selected_entity_name, "Player")
        self.assertEqual(entry.selected_entity_id, self.scene_manager.find_entity_data("Player")["id"])
        self.assertEqual(edit_world.selected_entity_name, "Player")

    def test_untitled_scene_keys_are_unique_for_repeated_names(self) -> None:
        self.scene_manager.create_new_scene("Repeated")
        first_key = self.scene_manager.active_scene_key
        self.scene_manager.create_new_scene("Repeated", activate=False)
        keys = [scene["key"] for scene in self.scene_manager.list_open_scenes()]

        self.assertEqual(len(keys), 2)
        self.assertEqual(len(set(keys)), 2)
        self.assertIn(first_key, keys)

    def test_enter_play_invokes_runtime_signal_compiler_with_runtime_world(self) -> None:
        self.scene_manager.load_scene(
            {
                "name": "SignalPlayProbe",
                "entities": [
                    {
                        "name": "Emitter",
                        "active": True,
                        "tag": "Untagged",
                        "layer": "Default",
                        "components": {"Transform": self._transform_payload()},
                    }
                ],
                "rules": [],
                "feature_metadata": {
                    "signals": {
                        "connections": [
                            {
                                "id": "emit_to_event",
                                "source": {"id": "Emitter", "signal": "pressed"},
                                "target": {"kind": "event_bus"},
                                "callable": {"event": "ui.emitter_pressed"},
                            }
                        ]
                    }
                },
            }
        )
        invocaciones: list[tuple[str, object]] = []

        def compilar(scene, world):
            invocaciones.append((scene.name, world))
            return len(scene.list_signal_connections())

        self.scene_manager.set_runtime_signal_compiler(compilar)

        runtime_world = self.scene_manager.enter_play()

        self.assertIsNotNone(runtime_world)
        self.assertEqual(len(invocaciones), 1)
        self.assertEqual(invocaciones[0][0], "SignalPlayProbe")
        self.assertIs(invocaciones[0][1], runtime_world)

    def test_enter_play_builds_runtime_group_registry_from_entity_groups(self) -> None:
        self.scene_manager.load_scene(
            {
                "name": "GroupPlayProbe",
                "entities": [
                    {
                        "name": "EnemyA",
                        "active": True,
                        "tag": "Enemy",
                        "layer": "Gameplay",
                        "groups": ["Enemies", "Damageables"],
                        "components": {"Transform": self._transform_payload()},
                    },
                    {
                        "name": "EnemyB",
                        "active": True,
                        "tag": "Enemy",
                        "layer": "Gameplay",
                        "groups": ["Enemies"],
                        "components": {"Transform": self._transform_payload()},
                    },
                    {
                        "name": "Pickup",
                        "active": True,
                        "tag": "Collectible",
                        "layer": "Gameplay",
                        "components": {"Transform": self._transform_payload()},
                    },
                ],
                "rules": [],
                "feature_metadata": {},
            }
        )

        runtime_world = self.scene_manager.enter_play()

        self.assertIsNotNone(runtime_world)
        self.assertEqual(runtime_world.group_registry.list_groups(), ["Damageables", "Enemies"])
        self.assertEqual(runtime_world.group_registry.get_entity_names("Enemies"), ["EnemyA", "EnemyB"])
        self.assertEqual(runtime_world.group_registry.get_entity_names("Damageables"), ["EnemyA"])
        self.assertTrue(runtime_world.group_registry.has("Enemies", "EnemyA"))
        self.assertFalse(runtime_world.group_registry.has("Enemies", "Pickup"))

    def test_save_scene_preserves_component_metadata(self) -> None:
        self.scene_manager.load_scene(
            {
                "name": "SaveMetadata",
                "entities": [
                    {
                        "name": "Actor",
                        "active": True,
                        "tag": "Untagged",
                        "layer": "Default",
                        "components": {"Transform": self._transform_payload()},
                    }
                ],
                "rules": [],
                "feature_metadata": {},
            }
        )
        self.assertTrue(self.scene_manager.set_component_metadata("Actor", "Transform", {"origin": "ai_custom"}))

        with tempfile.TemporaryDirectory() as temp_dir:
            target_path = Path(temp_dir) / "scene.json"
            saved = self.scene_manager.save_scene_to_file(target_path.as_posix())
            self.assertTrue(saved)
            raw = target_path.read_text(encoding="utf-8")

        self.assertIn('"component_metadata"', raw)
        self.assertIn('"ai_custom"', raw)


class SceneWorkspaceAuthorityTests(unittest.TestCase):
    def setUp(self) -> None:
        registry = create_default_registry()
        policy = SceneFlowPolicy()
        self.projection = SceneProjectionService(registry)
        self.workspace = SceneWorkspace(
            projection=self.projection,
            flow_policy=policy,
        )

    def test_pending_edit_sync_flag_is_read_only(self) -> None:
        self.assertIsNone(SceneWorkspaceEntry.edit_world_sync_pending.fset)

    def test_workspace_owns_path_normalization_and_untitled_keys(self) -> None:
        source_path = "scenes/../scenes/workspace_probe.json"

        self.workspace.load_scene(
            {"name": "FromDisk", "entities": [], "rules": [], "feature_metadata": {}},
            source_path,
        )
        disk_entry = self.workspace.get_active_entry()
        self.workspace.create_new_scene("First", activate=False)
        self.workspace.create_new_scene("Second", activate=False)

        self.assertIsNotNone(disk_entry)
        assert disk_entry is not None
        self.assertEqual(disk_entry.key, self.workspace.normalize_path_reference(source_path))
        self.assertEqual(disk_entry.source_path, self.workspace.normalize_path_reference(source_path))
        untitled_keys = [key for key in self.workspace.entries if key.startswith("untitled:")]
        self.assertEqual(untitled_keys, ["untitled:1", "untitled:2"])

    def test_resolve_entry_accepts_workspace_key_and_normalized_path(self) -> None:
        self.workspace.create_new_scene("Keyed")
        keyed_entry = self.workspace.get_active_entry()
        source_path = "scenes/../scenes/resolve_probe.json"
        normalized_path = self.workspace.normalize_path_reference(source_path)
        self.workspace.load_scene(
            {"name": "FromDisk", "entities": [], "rules": [], "feature_metadata": {}},
            source_path,
        )
        disk_entry = self.workspace.get_active_entry()

        assert keyed_entry is not None
        assert disk_entry is not None
        self.assertIs(self.workspace.resolve_entry(keyed_entry.key), keyed_entry)
        self.assertIs(self.workspace.resolve_entry(normalized_path), disk_entry)

    def test_install_entry_state_explicitly_installs_scene_world_and_version(self) -> None:
        self.workspace.load_scene(
            {
                "name": "Original",
                "entities": [{"id": "actor-id", "name": "Actor", "components": {}}],
                "rules": [],
                "feature_metadata": {},
            }
        )
        entry = self.workspace.get_active_entry()
        assert entry is not None
        self.assertTrue(self.workspace.select_entity(entry, entity_name="Actor"))
        selection = self.workspace.capture_selection(entry)
        replacement = self.projection.create_scene(
            {
                "name": "Replacement",
                "entities": [{"id": "actor-id", "name": "Actor", "components": {}}],
                "rules": [],
                "feature_metadata": {},
            }
        )
        replacement_world = self.projection.create_world(replacement)

        self.workspace.install_entry_state(entry, replacement, replacement_world)
        self.workspace.restore_selection(entry, selection)

        self.assertIs(entry.scene, replacement)
        self.assertIs(entry.edit_world, replacement_world)
        self.assertEqual(entry.edit_world_version, replacement_world.version)
        self.assertEqual(entry.selected_entity_name, "Actor")
        self.assertEqual(replacement_world.selected_entity_name, "Actor")

    def test_replace_entry_scene_does_not_install_partial_projection(self) -> None:
        self.workspace.load_scene(
            {"name": "Stable", "entities": [], "rules": [], "feature_metadata": {}}
        )
        entry = self.workspace.get_active_entry()
        assert entry is not None
        scene_before = entry.scene
        world_before = entry.edit_world
        version_before = entry.edit_world_version

        with patch.object(self.projection, "create_world", side_effect=ValueError("projection failed")):
            with self.assertRaisesRegex(ValueError, "projection failed"):
                self.workspace.replace_entry_scene(
                    entry,
                    {"name": "Rejected", "entities": [], "rules": [], "feature_metadata": {}},
                )

        self.assertIs(entry.scene, scene_before)
        self.assertIs(entry.edit_world, world_before)
        self.assertEqual(entry.edit_world_version, version_before)

    def test_workspace_preserves_selection_and_controls_dirty_state(self) -> None:
        transform = {
            "enabled": True,
            "x": 0.0,
            "y": 0.0,
            "rotation": 0.0,
            "scale_x": 1.0,
            "scale_y": 1.0,
        }
        self.workspace.load_scene(
            {
                "name": "Selection",
                "entities": [
                    {
                        "name": "Actor",
                        "active": True,
                        "tag": "Untagged",
                        "layer": "Default",
                        "components": {"Transform": transform},
                    }
                ],
                "rules": [],
                "feature_metadata": {},
            }
        )
        entry = self.workspace.get_active_entry()

        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertTrue(self.workspace.select_entity(entry, entity_name="Actor"))
        selected_id = entry.selected_entity_id
        self.workspace.mark_dirty(entry)
        self.workspace.rebuild_edit_world(entry)

        self.assertTrue(entry.dirty)
        self.assertEqual(entry.selected_entity_name, "Actor")
        self.assertEqual(entry.selected_entity_id, selected_id)
        assert entry.edit_world is not None
        self.assertEqual(entry.edit_world.selected_entity_name, "Actor")

        self.workspace.clear_selection(entry)
        self.workspace.clear_dirty(entry)
        self.assertIsNone(entry.selected_entity_name)
        self.assertFalse(entry.dirty)


if __name__ == "__main__":
    unittest.main()
