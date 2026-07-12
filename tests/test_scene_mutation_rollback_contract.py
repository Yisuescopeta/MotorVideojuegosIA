import copy
import unittest
from contextlib import nullcontext
from dataclasses import fields
from unittest.mock import patch

from engine.levels.component_registry import create_default_registry
from engine.scenes.scene_manager import SceneManager


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

    def test_snapshot_has_only_characterized_fields_and_is_frozen(self) -> None:
        manager, entry = self._manager_and_entry(active=True)

        snapshot = manager._capture_serializable_mutation(entry)

        self.assertEqual(
            [field.name for field in fields(snapshot)],
            [
                "scene_data",
                "selected_entity_name",
                "selected_entity_id",
                "dirty",
                "pending_edit_world_sync_reason",
            ],
        )
        self.assertTrue(type(snapshot).__dataclass_params__.frozen)

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
                original_install = manager._install_scene_payload
                install_calls = 0

                def fail_first_install(*args, **kwargs):
                    nonlocal install_calls
                    install_calls += 1
                    if fail_install and install_calls == 1:
                        raise ValueError("reject mutation")
                    return original_install(*args, **kwargs)

                install_context = (
                    patch.object(manager, "_install_scene_payload", side_effect=fail_first_install)
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
                self.assertIsNone(entry.dirty_before_pending_edit_world_sync)
                self.assertNotEqual(entry.edit_world_version, 777)
                self.assertEqual(entry.edit_world_version, entry.edit_world.version)
                if fail_install:
                    self.assertEqual(entry.scene.to_dict(), scene_before)
                    self.assertFalse(entry.dirty)
                    self.assertEqual(entry.pending_edit_world_sync_reason, "contract_pending")
                else:
                    self.assertIn("Marker2D", entry.scene.find_entity("Hero")["components"])
                    self.assertTrue(entry.dirty)
                    self.assertIsNone(entry.pending_edit_world_sync_reason)

    def test_incremental_transform_paths_do_not_capture_serializable_snapshot(self) -> None:
        manager, _entry = self._manager_and_entry(active=True)

        with patch.object(
            manager,
            "_capture_serializable_mutation",
            wraps=manager._capture_serializable_mutation,
        ) as capture:
            self.assertTrue(manager.apply_transform_state("Hero", {"x": 5.0}))
            self.assertTrue(manager.apply_rect_transform_state("Widget", {"width": 120.0}))

        capture.assert_not_called()

    def test_authoring_fallback_uses_serializable_snapshot(self) -> None:
        manager, _entry = self._manager_and_entry(active=True)

        with patch.object(manager, "_can_apply_direct_transform_state", return_value=False), patch.object(
            manager,
            "_capture_serializable_mutation",
            wraps=manager._capture_serializable_mutation,
        ) as capture:
            self.assertTrue(manager.apply_transform_state("Hero", {"x": 8.0}))

        capture.assert_called_once()


if __name__ == "__main__":
    unittest.main()
