import copy
import unittest
from contextlib import nullcontext
from unittest.mock import patch

from engine.components.transform import Transform
from engine.editor.undo_redo import UndoRedoManager
from engine.levels.component_registry import create_default_registry
from engine.scenes.scene_manager import SceneManager
from engine.scenes.workspace_lifecycle import SceneWorkspace


def _scene_payload(name: str) -> dict:
    return {
        "name": name,
        "entities": [
            {
                "name": "Hero",
                "active": True,
                "tag": "Untagged",
                "layer": "Default",
                "components": {
                    "Transform": {
                        "enabled": True,
                        "x": 1.0,
                        "y": 2.0,
                        "rotation": 0.0,
                        "scale_x": 1.0,
                        "scale_y": 1.0,
                    }
                },
            },
            {
                "name": "Widget",
                "active": True,
                "tag": "Untagged",
                "layer": "Default",
                "components": {
                    "RectTransform": {
                        "enabled": True,
                        "anchored_x": 0.0,
                        "anchored_y": 0.0,
                        "width": 100.0,
                        "height": 40.0,
                        "rotation": 0.0,
                        "scale_x": 1.0,
                        "scale_y": 1.0,
                    }
                },
            },
        ],
        "rules": [],
        "feature_metadata": {},
    }


class SceneMutationRollbackContractTests(unittest.TestCase):
    def _manager_and_entry(self, *, active: bool) -> tuple[SceneManager, object]:
        manager = SceneManager(create_default_registry())
        manager.load_scene(_scene_payload("Primary"), source_path="primary.json", activate=True)
        if active:
            return manager, manager.resolve_entry(manager.active_scene_key)
        manager.load_scene(_scene_payload("Secondary"), source_path="secondary.json", activate=False)
        secondary_key = next(item["key"] for item in manager.list_open_scenes() if item["name"] == "Secondary")
        return manager, manager.resolve_entry(secondary_key)

    def test_serializable_mutation_success_and_failure_for_active_and_inactive_entries(self) -> None:
        scenarios = (
            ("active_success", True, False),
            ("active_failure", True, True),
            ("inactive_success", False, False),
            ("inactive_failure", False, True),
        )
        for name, active, fail_install in scenarios:
            with self.subTest(name=name):
                manager, entry = self._manager_and_entry(active=active)
                hero_id = entry.scene.find_entity("Hero")["id"]
                entry.selected_entity_name = "Hero"
                entry.selected_entity_id = hero_id
                entry.edit_world.selected_entity_name = "Hero"
                entry.dirty = False
                entry.pending_edit_world_sync_reason = "contract_pending"
                entry.dirty_before_pending_edit_world_sync = True
                entry.edit_world_version = 777
                scene_before = copy.deepcopy(entry.scene.to_dict())
                world_before = copy.deepcopy(entry.edit_world.serialize())
                history = UndoRedoManager()
                manager.set_history_manager(history)
                original_install = SceneWorkspace.install_entry_state
                install_calls = 0

                def fail_first_install(_workspace, *args, **kwargs):
                    nonlocal install_calls
                    install_calls += 1
                    if fail_install and install_calls == 1:
                        raise ValueError("reject mutation")
                    return original_install(*args, **kwargs)

                install_context = (
                    patch.object(SceneWorkspace, "install_entry_state", new=fail_first_install)
                    if fail_install
                    else nullcontext()
                )
                with install_context:
                    changed = manager.upsert_component_for_scene(
                        entry.key,
                        "Hero",
                        "Marker2D",
                        {"enabled": True, "marker_name": "checkpoint"},
                    )

                self.assertEqual(changed, not fail_install)
                self.assertEqual(entry.selected_entity_name, "Hero")
                self.assertEqual(entry.selected_entity_id, hero_id)
                self.assertEqual(entry.edit_world.selected_entity_name, "Hero")
                self.assertNotEqual(entry.edit_world_version, 777)
                self.assertEqual(entry.edit_world_version, entry.edit_world.version)
                if fail_install:
                    self.assertEqual(entry.scene.to_dict(), scene_before)
                    self.assertEqual(entry.edit_world.serialize(), world_before)
                    self.assertFalse(entry.dirty)
                    self.assertEqual(entry.pending_edit_world_sync_reason, "contract_pending")
                    self.assertTrue(entry.dirty_before_pending_edit_world_sync)
                    self.assertFalse(history.can_undo())
                else:
                    self.assertIn("Marker2D", entry.scene.find_entity("Hero")["components"])
                    self.assertTrue(entry.dirty)
                    self.assertIsNone(entry.pending_edit_world_sync_reason)
                    self.assertIsNone(entry.dirty_before_pending_edit_world_sync)
                    self.assertEqual(history.can_undo(), active)

    def test_incremental_transform_paths_update_observable_scene_without_rebuild(self) -> None:
        manager, _entry = self._manager_and_entry(active=True)
        world_before = manager.get_edit_world()

        self.assertTrue(manager.apply_transform_state("Hero", {"x": 5.0}))
        self.assertTrue(manager.apply_rect_transform_state("Widget", {"width": 120.0}))

        payload = manager.current_scene.to_dict()
        hero = next(entity for entity in payload["entities"] if entity["name"] == "Hero")
        widget = next(entity for entity in payload["entities"] if entity["name"] == "Widget")
        self.assertEqual(hero["components"]["Transform"]["x"], 5.0)
        self.assertEqual(widget["components"]["RectTransform"]["width"], 120.0)
        self.assertIs(manager.get_edit_world(), world_before)

    def test_incremental_wrapper_validates_service_boundary_once(self) -> None:
        manager, entry = self._manager_and_entry(active=True)

        with patch.object(
            manager._incremental_authoring,
            "can_apply",
            wraps=manager._incremental_authoring.can_apply,
        ) as can_apply:
            self.assertTrue(manager.apply_transform_state("Hero", {"x": 5.0}))

        can_apply.assert_called_once_with(entry, "Hero", "Transform")

    def test_authoring_fallback_updates_observable_scene_and_world(self) -> None:
        manager, entry = self._manager_and_entry(active=True)

        with patch.object(manager._incremental_authoring, "can_apply", return_value=False):
            self.assertTrue(manager.apply_transform_state("Hero", {"x": 8.0}))

        self.assertEqual(
            entry.scene.find_entity("Hero")["components"]["Transform"]["x"],
            8.0,
        )
        transform = entry.edit_world.get_entity_by_name("Hero").get_component(Transform)
        self.assertEqual(transform.x, 8.0)
        self.assertTrue(entry.dirty)


if __name__ == "__main__":
    unittest.main()
