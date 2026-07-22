import unittest
from unittest.mock import Mock

import pyray as rl
from engine.components.transform import Transform
from engine.editor.editor_tools import EditorTool
from engine.editor.gizmo_system import GizmoMode, GizmoSystem
from engine.editor.transform_preview import TransformPreviewHandle
from engine.ecs.world import World
from engine.scenes.refs import EntityRef, OpenDocumentId, OpenSceneRef
from engine.scenes.preview_leases import PreviewCancelReason
from engine.scenes.result import CommandError, CommandErrorCode, Err, Ok


class GizmoTransformPreviewTests(unittest.TestCase):
    def test_transform_drag_opens_updates_and_completes_typed_preview(self) -> None:
        scene_ref = OpenSceneRef(OpenDocumentId.new())
        target = EntityRef(scene_ref, "hero-id")
        handle = TransformPreviewHandle("lease-1", target, 4)
        commands = Mock()
        commands.begin.return_value = Ok(handle)
        commands.update.return_value = Ok(None)

        world = World()
        entity = world.create_entity("Hero")
        entity.serialized_id = "hero-id"
        transform = Transform(x=1.0, y=2.0, rotation=0.0, scale_x=1.0, scale_y=1.0)
        entity.add_component(transform)
        gizmo = GizmoSystem()
        gizmo.set_transform_preview_context(commands, scene_ref)

        gizmo._start_transform_drag(entity, transform, 0.0, 0.0, 1.0, 2.0, GizmoMode.TRANSLATE_FREE)
        gizmo._handle_transform_drag(transform, 10.0, 12.0, False, False)
        gizmo._end_drag(transform)

        commands.begin.assert_called_once_with(target)
        commands.update.assert_called_once()
        drag = gizmo.consume_completed_drag()
        self.assertIsNotNone(drag)
        assert drag is not None
        self.assertEqual(drag.entity_id, "hero-id")
        self.assertIs(drag.preview_handle, handle)
        self.assertEqual(drag.component_name, "Transform")
        self.assertEqual(drag.after_state["x"], 11.0)
        self.assertEqual(drag.after_state["y"], 14.0)

    def test_typed_preview_rejection_prevents_drag_start(self) -> None:
        scene_ref = OpenSceneRef(OpenDocumentId.new())
        commands = Mock()
        commands.begin.return_value = Err(
            CommandError(CommandErrorCode.PREVIEW_ACTIVE, "busy")
        )
        world = World()
        entity = world.create_entity("Hero")
        entity.serialized_id = "hero-id"
        transform = Transform()
        entity.add_component(transform)
        gizmo = GizmoSystem()
        gizmo.set_transform_preview_context(commands, scene_ref)

        gizmo._start_transform_drag(entity, transform, 0.0, 0.0, 0.0, 0.0, GizmoMode.TRANSLATE_FREE)

        self.assertFalse(gizmo.is_dragging)
        self.assertIsNone(gizmo.consume_completed_drag())

    def _gizmo_with_preview(self, *, update_result=Ok(None)) -> tuple[GizmoSystem, Mock, Transform]:
        scene_ref = OpenSceneRef(OpenDocumentId.new())
        target = EntityRef(scene_ref, "hero-id")
        commands = Mock()
        commands.begin.return_value = Ok(TransformPreviewHandle("lease-1", target, 4))
        commands.update.return_value = update_result
        world = World()
        entity = world.create_entity("Hero")
        entity.serialized_id = "hero-id"
        transform = Transform(x=1.0, y=2.0)
        entity.add_component(transform)
        gizmo = GizmoSystem()
        gizmo.set_transform_preview_context(commands, scene_ref)
        gizmo._start_transform_drag(entity, transform, 0.0, 0.0, 1.0, 2.0, GizmoMode.TRANSLATE_FREE)
        return gizmo, commands, transform

    def test_pointer_capture_loss_cancels_typed_preview(self) -> None:
        gizmo, commands, _transform = self._gizmo_with_preview()

        gizmo._end_drag(None)

        commands.cancel.assert_called_once_with(
            unittest.mock.ANY,
            PreviewCancelReason.POINTER_CAPTURE_LOST,
        )
        self.assertFalse(gizmo.has_typed_transform_preview)
        self.assertIsNone(gizmo.consume_completed_drag())

    def test_drag_without_changes_cancels_typed_preview(self) -> None:
        gizmo, commands, transform = self._gizmo_with_preview()

        gizmo._end_drag(transform)

        commands.cancel.assert_called_once_with(
            unittest.mock.ANY,
            PreviewCancelReason.DRAG_NO_CHANGES,
        )
        self.assertIsNone(gizmo.consume_completed_drag())

    def test_preview_update_error_cancels_without_completed_drag(self) -> None:
        update_error = Err(CommandError(CommandErrorCode.INTERNAL_ERROR, "update failed"))
        gizmo, commands, transform = self._gizmo_with_preview(update_result=update_error)

        gizmo._handle_transform_drag(transform, 10.0, 12.0, False, False)

        commands.cancel.assert_called_once_with(
            unittest.mock.ANY,
            PreviewCancelReason.ERROR,
        )
        self.assertFalse(gizmo.has_typed_transform_preview)
        self.assertIsNone(gizmo.consume_completed_drag())


if __name__ == "__main__":
    unittest.main()
