import copy
import inspect
import unittest
from unittest.mock import patch

import engine.scenes.edit_sync as edit_sync_module
from engine.components.camera2d import Camera2D
from engine.components.transform import Transform
from engine.levels.component_registry import create_default_registry
from engine.scenes.edit_sync import (
    LEGACY_AUTHORING_SYNC_REASON,
    TRANSIENT_PREVIEW_SYNC_REASON,
    SceneEditSyncCoordinator,
)
from engine.scenes.scene_flow import SceneFlowPolicy
from engine.scenes.scene_projection import SceneProjectionService
from engine.scenes.workspace_lifecycle import SceneWorkspace


def _scene_payload() -> dict:
    return {
        "name": "EditSyncProbe",
        "entities": [
            {
                "name": "Actor",
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
                "name": "Camera",
                "active": True,
                "tag": "MainCamera",
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
                    "Camera2D": {
                        "enabled": True,
                        "offset_x": 0.0,
                        "offset_y": 0.0,
                        "zoom": 1.0,
                        "rotation": 0.0,
                        "is_primary": True,
                        "follow_entity": "",
                        "framing_mode": "platformer",
                        "dead_zone_width": 0.0,
                        "dead_zone_height": 0.0,
                        "clamp_left": None,
                        "clamp_right": None,
                        "clamp_top": None,
                        "clamp_bottom": None,
                        "recenter_on_play": True,
                    },
                },
            },
        ],
        "rules": [],
        "feature_metadata": {},
    }


class SceneEditSyncCoordinatorTests(unittest.TestCase):
    def setUp(self) -> None:
        registry = create_default_registry()
        self.projection = SceneProjectionService(registry)
        self.workspace = SceneWorkspace(
            projection=self.projection,
            flow_policy=SceneFlowPolicy(),
        )
        self.coordinator = SceneEditSyncCoordinator(self.workspace, self.projection)
        self.workspace.load_scene(_scene_payload())
        self.entry = self.workspace.get_active_entry()
        assert self.entry is not None

    def _actor_transform(self) -> Transform:
        assert self.entry.edit_world is not None
        actor = self.entry.edit_world.get_entity_by_name("Actor")
        assert actor is not None
        transform = actor.get_component(Transform)
        assert transform is not None
        return transform

    def test_legacy_pending_flushes_active_world_and_keeps_dirty(self) -> None:
        self._actor_transform().x = 77.0

        self.assertTrue(self.coordinator.mark_edit_world_dirty())
        self.assertEqual(self.entry.pending_edit_world_sync_reason, LEGACY_AUTHORING_SYNC_REASON)
        self.assertFalse(self.entry.dirty_before_pending_edit_world_sync)
        self.assertTrue(self.entry.dirty)
        self.assertTrue(self.coordinator.flush_pending(self.entry, failure_context="direct_legacy"))

        transform_data = self.entry.scene.find_entity("Actor")["components"]["Transform"]
        self.assertEqual(transform_data["x"], 77.0)
        self.assertFalse(self.entry.edit_world_sync_pending)
        self.assertIsNone(self.entry.dirty_before_pending_edit_world_sync)
        self.assertTrue(self.entry.dirty)

    def test_transient_preview_stays_pending_without_force_and_does_not_mark_dirty(self) -> None:
        self._actor_transform().x = 33.0

        self.assertTrue(
            self.coordinator.mark_edit_world_dirty(reason=TRANSIENT_PREVIEW_SYNC_REASON)
        )

        self.assertFalse(self.coordinator.sync_from_edit_world())
        self.assertEqual(self.entry.pending_edit_world_sync_reason, TRANSIENT_PREVIEW_SYNC_REASON)
        self.assertFalse(self.entry.dirty)
        self.assertEqual(
            self.entry.scene.find_entity("Actor")["components"]["Transform"]["x"],
            1.0,
        )

    def test_force_sync_accepts_transient_preview_without_marking_dirty(self) -> None:
        self._actor_transform().x = 44.0
        self.coordinator.mark_edit_world_dirty(reason=TRANSIENT_PREVIEW_SYNC_REASON)

        self.assertTrue(self.coordinator.sync_from_edit_world(force=True))

        self.assertEqual(
            self.entry.scene.find_entity("Actor")["components"]["Transform"]["x"],
            44.0,
        )
        self.assertFalse(self.entry.edit_world_sync_pending)
        self.assertFalse(self.entry.dirty)

    def test_prepare_for_save_discards_transient_preview(self) -> None:
        self._actor_transform().x = 55.0
        self.coordinator.mark_edit_world_dirty(reason=TRANSIENT_PREVIEW_SYNC_REASON)

        self.assertTrue(
            self.coordinator.prepare_for_save(self.entry, failure_context="save_transient")
        )

        self.assertEqual(self._actor_transform().x, 1.0)
        self.assertEqual(
            self.entry.scene.find_entity("Actor")["components"]["Transform"]["x"],
            1.0,
        )
        self.assertFalse(self.entry.edit_world_sync_pending)
        self.assertFalse(self.entry.dirty)

    def test_prepare_for_save_flushes_legacy_pending(self) -> None:
        self._actor_transform().x = 66.0
        self.coordinator.mark_edit_world_dirty(reason=LEGACY_AUTHORING_SYNC_REASON)

        self.assertTrue(
            self.coordinator.prepare_for_save(self.entry, failure_context="save_legacy")
        )

        self.assertEqual(
            self.entry.scene.find_entity("Actor")["components"]["Transform"]["x"],
            66.0,
        )
        self.assertFalse(self.entry.edit_world_sync_pending)
        self.assertTrue(self.entry.dirty)

    def test_prepare_for_save_syncs_unmarked_world_version_change(self) -> None:
        self._actor_transform().x = 72.0
        assert self.entry.edit_world is not None
        self.entry.edit_world.touch_transform()

        self.assertTrue(
            self.coordinator.prepare_for_save(self.entry, failure_context="save_version")
        )

        self.assertEqual(
            self.entry.scene.find_entity("Actor")["components"]["Transform"]["x"],
            72.0,
        )
        self.assertFalse(self.entry.edit_world_sync_pending)
        self.assertFalse(self.entry.dirty)

    def test_prepare_for_save_does_not_sync_unmarked_edit_world_during_play(self) -> None:
        self._actor_transform().x = 73.0
        assert self.entry.edit_world is not None
        self.entry.edit_world.touch_transform()
        self.assertIsNotNone(self.workspace.enter_play())

        self.assertTrue(
            self.coordinator.prepare_for_save(self.entry, failure_context="save_play")
        )

        self.assertEqual(
            self.entry.scene.find_entity("Actor")["components"]["Transform"]["x"],
            1.0,
        )
        self.assertTrue(self.entry.is_playing)

    def test_inactive_entry_pending_is_not_flushed(self) -> None:
        self._actor_transform().x = 88.0
        self.coordinator.mark_edit_world_dirty(reason=LEGACY_AUTHORING_SYNC_REASON)
        self.workspace.create_new_scene("Other", activate=True)

        self.assertTrue(self.coordinator.flush_pending(self.entry, failure_context="inactive"))

        self.assertEqual(
            self.entry.scene.find_entity("Actor")["components"]["Transform"]["x"],
            1.0,
        )
        self.assertEqual(self.entry.pending_edit_world_sync_reason, LEGACY_AUTHORING_SYNC_REASON)

    def test_invalid_snapshot_rebuilds_world_restores_dirty_baseline_and_clears_pending(self) -> None:
        self.workspace.mark_dirty(self.entry)
        scene_before = copy.deepcopy(self.entry.scene.to_dict())
        assert self.entry.edit_world is not None
        camera = self.entry.edit_world.get_entity_by_name("Camera")
        assert camera is not None
        camera_component = camera.get_component(Camera2D)
        assert camera_component is not None
        camera_component.zoom = 0.0
        self.coordinator.mark_edit_world_dirty(reason=LEGACY_AUTHORING_SYNC_REASON)

        with patch.object(
            self.projection,
            "validate_payload",
            side_effect=ValueError("invalid snapshot"),
        ) as validate:
            flushed = self.coordinator.flush_pending(
                self.entry,
                failure_context="invalid_direct",
            )

        self.assertFalse(flushed)
        validate.assert_called_once()
        self.assertEqual(self.entry.scene.to_dict(), scene_before)
        self.assertTrue(self.entry.dirty)
        self.assertFalse(self.entry.edit_world_sync_pending)
        self.assertIsNone(self.entry.dirty_before_pending_edit_world_sync)
        assert self.entry.edit_world is not None
        restored_camera = self.entry.edit_world.get_entity_by_name("Camera")
        assert restored_camera is not None
        restored_component = restored_camera.get_component(Camera2D)
        assert restored_component is not None
        self.assertEqual(restored_component.zoom, 1.0)

    def test_snapshot_roundtrip_is_owned_by_coordinator(self) -> None:
        self.coordinator.mark_edit_world_dirty(reason=TRANSIENT_PREVIEW_SYNC_REASON)
        snapshot = self.coordinator.capture_snapshot(self.entry)

        self.coordinator.clear_pending(self.entry)
        self.coordinator.restore_snapshot(self.entry, snapshot)

        self.assertEqual(self.entry.pending_edit_world_sync_reason, TRANSIENT_PREVIEW_SYNC_REASON)
        self.assertIsNone(self.entry.dirty_before_pending_edit_world_sync)

    def test_reason_only_restore_preserves_serializable_rollback_baseline(self) -> None:
        self.coordinator.mark_edit_world_dirty(reason=LEGACY_AUTHORING_SYNC_REASON)
        reason = self.coordinator.capture_pending_reason(self.entry)

        self.coordinator.clear_pending(self.entry)
        self.coordinator.restore_pending_reason(self.entry, reason)

        self.assertEqual(self.entry.pending_edit_world_sync_reason, LEGACY_AUTHORING_SYNC_REASON)
        self.assertIsNone(self.entry.dirty_before_pending_edit_world_sync)

    def test_coordinator_has_only_workspace_and_projection_dependencies(self) -> None:
        parameters = tuple(inspect.signature(SceneEditSyncCoordinator).parameters)
        source = inspect.getsource(SceneEditSyncCoordinator)
        module_source = inspect.getsource(edit_sync_module)

        self.assertEqual(parameters, ("workspace", "projection"))
        self.assertNotIn("SceneManager", source)
        self.assertNotIn("Persistence", source)
        self.assertNotIn("History", source)
        self.assertNotIn("flow_policy", source)
        self.assertNotIn("runtime_logging", module_source)


if __name__ == "__main__":
    unittest.main()
