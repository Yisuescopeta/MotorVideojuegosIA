import inspect
import unittest
from typing import Callable

import engine.scenes.incremental_authoring as incremental_module
from engine.components.recttransform import RectTransform
from engine.components.transform import Transform
from engine.levels.component_registry import create_default_registry
from engine.scenes.incremental_authoring import SceneIncrementalAuthoring
from engine.scenes.scene_flow import SceneFlowPolicy
from engine.scenes.scene_projection import SceneProjectionService
from engine.scenes.workspace_lifecycle import SceneWorkspace, SceneWorkspaceEntry


class FakeHistory:
    def __init__(self) -> None:
        self.records: list[tuple[str, Callable[[], bool], Callable[[], bool]]] = []

    def record_differential_change(
        self,
        *,
        label: str,
        undo: Callable[[], bool],
        redo: Callable[[], bool],
    ) -> None:
        self.records.append((label, undo, redo))


class FakeEditSync:
    def __init__(self) -> None:
        self.cleared: list[str] = []

    def clear_pending(self, entry: SceneWorkspaceEntry) -> None:
        self.cleared.append(entry.key)
        entry.pending_edit_world_sync_reason = None
        entry.dirty_before_pending_edit_world_sync = None


def _scene_payload() -> dict:
    return {
        "name": "IncrementalProbe",
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
                "name": "Panel",
                "active": True,
                "tag": "UI",
                "layer": "UI",
                "components": {
                    "RectTransform": {
                        "enabled": True,
                        "anchored_x": 4.0,
                        "anchored_y": 8.0,
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


class SceneIncrementalAuthoringTests(unittest.TestCase):
    def setUp(self) -> None:
        registry = create_default_registry()
        projection = SceneProjectionService(registry)
        self.workspace = SceneWorkspace(
            projection=projection,
            flow_policy=SceneFlowPolicy(),
        )
        self.history = FakeHistory()
        self.edit_sync = FakeEditSync()
        self.authoring = SceneIncrementalAuthoring(
            self.workspace,
            self.edit_sync,
            self.history,
        )
        self.workspace.load_scene(_scene_payload())
        self.entry = self.workspace.get_active_entry()
        assert self.entry is not None

    def _transform(self) -> Transform:
        assert self.entry.edit_world is not None
        entity = self.entry.edit_world.get_entity_by_name("Actor")
        assert entity is not None
        transform = entity.get_component(Transform)
        assert transform is not None
        return transform

    def _rect_transform(self) -> RectTransform:
        assert self.entry.edit_world is not None
        entity = self.entry.edit_world.get_entity_by_name("Panel")
        assert entity is not None
        rect_transform = entity.get_component(RectTransform)
        assert rect_transform is not None
        return rect_transform

    def test_transform_updates_scene_world_float_versions_and_entry_state(self) -> None:
        assert self.entry.edit_world is not None
        world = self.entry.edit_world
        version_before = world.transform_version
        self.entry.pending_edit_world_sync_reason = "legacy_authoring"
        self.entry.dirty_before_pending_edit_world_sync = False

        applied = self.authoring.apply_state(
            self.entry,
            "Actor",
            "Transform",
            {"x": "7.5", "y": 9},
            record_history=False,
            label="move-actor",
        )

        self.assertTrue(applied)
        data = self.entry.scene.find_entity("Actor")["components"]["Transform"]
        self.assertEqual(data["x"], 7.5)
        self.assertIsInstance(data["x"], float)
        self.assertEqual(data["y"], 9.0)
        self.assertEqual(self._transform().x, 7.5)
        self.assertEqual(self._transform().y, 9.0)
        self.assertEqual(world.transform_version, version_before + 1)
        self.assertEqual(self.entry.edit_world_version, world.version)
        self.assertEqual(self.entry.selected_entity_name, "Actor")
        self.assertTrue(self.entry.dirty)
        self.assertFalse(self.entry.edit_world_sync_pending)
        self.assertEqual(self.edit_sync.cleared, [self.entry.key])

    def test_rect_transform_updates_scene_world_and_ui_layout_version(self) -> None:
        assert self.entry.edit_world is not None
        world = self.entry.edit_world
        version_before = world.ui_layout_version

        applied = self.authoring.apply_state(
            self.entry,
            "Panel",
            "RectTransform",
            {"anchored_x": "12", "height": 96},
            record_history=False,
            label="resize-panel",
        )

        self.assertTrue(applied)
        data = self.entry.scene.find_entity("Panel")["components"]["RectTransform"]
        self.assertEqual(data["anchored_x"], 12.0)
        self.assertEqual(data["height"], 96.0)
        self.assertEqual(self._rect_transform().anchored_x, 12.0)
        self.assertEqual(self._rect_transform().height, 96.0)
        self.assertEqual(world.ui_layout_version, version_before + 1)
        self.assertEqual(self.entry.selected_entity_name, "Panel")

    def test_noop_does_not_touch_versions_dirty_selection_or_pending(self) -> None:
        assert self.entry.edit_world is not None
        world = self.entry.edit_world
        version_before = world.version
        transform_version_before = world.transform_version

        applied = self.authoring.apply_state(
            self.entry,
            "Actor",
            "Transform",
            {"x": 1, "y": 2.0},
            record_history=True,
            label="noop",
        )

        self.assertTrue(applied)
        self.assertEqual(world.version, version_before)
        self.assertEqual(world.transform_version, transform_version_before)
        self.assertFalse(self.entry.dirty)
        self.assertIsNone(self.entry.selected_entity_name)
        self.assertEqual(self.edit_sync.cleared, [])
        self.assertEqual(self.history.records, [])

    def test_inactive_scene_edit_does_not_change_active_scene(self) -> None:
        self.workspace.create_new_scene("Other", activate=True)

        applied = self.authoring.apply_state(
            self.entry,
            "Actor",
            "Transform",
            {"x": 21},
            record_history=False,
            label="inactive",
        )

        self.assertTrue(applied)
        self.assertNotEqual(self.workspace.active_scene_key, self.entry.key)
        self.assertEqual(
            self.entry.scene.find_entity("Actor")["components"]["Transform"]["x"],
            21.0,
        )
        self.assertEqual(self.entry.selected_entity_name, "Actor")

    def test_playing_entry_rejects_incremental_edit(self) -> None:
        scene_before = self.entry.scene.to_dict()
        self.assertIsNotNone(self.workspace.enter_play())

        self.assertFalse(self.authoring.can_apply(self.entry, "Actor", "Transform"))
        self.assertFalse(
            self.authoring.apply_state(
                self.entry,
                "Actor",
                "Transform",
                {"x": 30},
                record_history=False,
                label="play-reject",
            )
        )
        self.assertEqual(self.entry.scene.to_dict(), scene_before)

    def test_history_undo_redo_uses_incremental_service(self) -> None:
        self.assertTrue(
            self.authoring.apply_state(
                self.entry,
                "Actor",
                "Transform",
                {"x": 30},
                record_history=True,
                label="move-once",
            )
        )

        self.assertEqual(len(self.history.records), 1)
        label, undo, redo = self.history.records[0]
        self.assertEqual(label, "move-once")
        self.assertTrue(undo())
        self.assertEqual(self._transform().x, 1.0)
        self.assertTrue(redo())
        self.assertEqual(self._transform().x, 30.0)

    def test_transaction_commit_groups_deltas_for_undo_redo(self) -> None:
        self.assertTrue(self.authoring.begin_transaction(self.entry, "drag"))
        self.assertTrue(
            self.authoring.update_transaction(
                self.entry,
                "Actor",
                "Transform",
                {"x": 10},
            )
        )
        self.assertTrue(
            self.authoring.update_transaction(
                self.entry,
                "Actor",
                "Transform",
                {"x": 20, "y": 12},
            )
        )

        result = self.authoring.commit_transaction()

        self.assertEqual(
            result,
            {"label": "drag", "scene_key": self.entry.key, "changed_component_count": 1},
        )
        self.assertEqual(len(self.history.records), 1)
        _label, undo, redo = self.history.records[0]
        self.assertTrue(undo())
        self.assertEqual((self._transform().x, self._transform().y), (1.0, 2.0))
        self.assertTrue(redo())
        self.assertEqual((self._transform().x, self._transform().y), (20.0, 12.0))

    def test_transaction_net_noop_does_not_record_history(self) -> None:
        self.assertTrue(self.authoring.begin_transaction(self.entry, "net-noop"))
        self.assertTrue(
            self.authoring.update_transaction(
                self.entry,
                "Actor",
                "Transform",
                {"x": 10},
            )
        )
        self.assertTrue(
            self.authoring.update_transaction(
                self.entry,
                "Actor",
                "Transform",
                {"x": 1},
            )
        )

        result = self.authoring.commit_transaction()

        self.assertEqual(result["changed_component_count"], 0)
        self.assertEqual(self.history.records, [])
        self.assertEqual(self._transform().x, 1.0)

    def test_cancel_transaction_restores_transform_and_rect_transform(self) -> None:
        self.assertTrue(self.authoring.begin_transaction(self.entry, "cancel"))
        self.assertTrue(
            self.authoring.update_transaction(
                self.entry,
                "Actor",
                "Transform",
                {"x": 40},
            )
        )
        self.assertTrue(
            self.authoring.update_transaction(
                self.entry,
                "Panel",
                "RectTransform",
                {"width": 200},
            )
        )

        self.assertTrue(self.authoring.cancel_transaction())

        self.assertEqual(self._transform().x, 1.0)
        self.assertEqual(self._rect_transform().width, 100.0)
        self.assertEqual(self.history.records, [])

    def test_supports_only_incremental_numeric_fields(self) -> None:
        self.assertTrue(self.authoring.supports("Transform", "rotation"))
        self.assertTrue(self.authoring.supports("RectTransform", "width"))
        self.assertFalse(self.authoring.supports("Transform", "enabled"))
        self.assertFalse(self.authoring.supports("Sprite", "width"))

    def test_service_dependencies_exclude_manager_and_serializable_fallbacks(self) -> None:
        parameters = tuple(inspect.signature(SceneIncrementalAuthoring).parameters)
        source = inspect.getsource(incremental_module)

        self.assertEqual(parameters, ("workspace", "edit_sync", "history"))
        self.assertNotIn("scene_manager", source)
        self.assertNotIn("SceneManager", source)
        self.assertNotIn("Prefab", source)
        self.assertNotIn("Persistence", source)
        self.assertNotIn("scene_flow", source)
        self.assertNotIn("rebuild_edit_world", source)
        self.assertNotIn("serializable", source.lower())


if __name__ == "__main__":
    unittest.main()
