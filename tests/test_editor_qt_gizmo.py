"""Unit tests for GizmoManager."""
from __future__ import annotations

import unittest

from PySide6.QtCore import QPointF, QRectF

from editor_qt.gizmo.gizmo_modes import (
    CompletedGizmoDrag,
    GizmoHandle,
    GizmoManager,
    GizmoMode,
)


class TestGizmoModeEnum(unittest.TestCase):
    def test_all_modes_present(self):
        modes = [m for m in GizmoMode]
        names = {m.name for m in modes}
        for expected in ("NONE", "SELECT", "TRANSLATE_X", "TRANSLATE_Y", "TRANSLATE_FREE",
                         "ROTATE_Z", "SCALE_X", "SCALE_Y", "SCALE_UNIFORM", "RECT"):
            self.assertIn(expected, names)


class TestGizmoManagerInit(unittest.TestCase):
    def setUp(self):
        self.gizmo = GizmoManager()

    def test_default_mode_is_none(self):
        self.assertEqual(self.gizmo.mode, GizmoMode.NONE)

    def test_default_not_dragging(self):
        self.assertFalse(self.gizmo.is_dragging)

    def test_default_angle_zero(self):
        self.assertEqual(self.gizmo.current_angle, 0.0)

    def test_default_scale_one(self):
        sx, sy = self.gizmo.current_scale
        self.assertEqual(sx, 1.0)
        self.assertEqual(sy, 1.0)


class TestGizmoManagerSetMode(unittest.TestCase):
    def setUp(self):
        self.gizmo = GizmoManager()

    def test_set_mode_select(self):
        self.gizmo.set_mode(GizmoMode.SELECT)
        self.assertEqual(self.gizmo.mode, GizmoMode.SELECT)

    def test_set_mode_translate_free(self):
        self.gizmo.set_mode(GizmoMode.TRANSLATE_FREE)
        self.assertEqual(self.gizmo.mode, GizmoMode.TRANSLATE_FREE)

    def test_set_mode_rotate_z(self):
        self.gizmo.set_mode(GizmoMode.ROTATE_Z)
        self.assertEqual(self.gizmo.mode, GizmoMode.ROTATE_Z)

    def test_set_mode_scale_uniform(self):
        self.gizmo.set_mode(GizmoMode.SCALE_UNIFORM)
        self.assertEqual(self.gizmo.mode, GizmoMode.SCALE_UNIFORM)


class TestGizmoManagerTranslateDrag(unittest.TestCase):
    """Translate drag cycle: start -> update -> end."""

    def setUp(self):
        self.gizmo = GizmoManager()
        self.gizmo.set_mode(GizmoMode.TRANSLATE_FREE)
        self.gizmo.build_handles(
            QPointF(400, 300), zoom=1.0
        )

    def test_start_drag_captures_position(self):
        self.gizmo.start_drag(
            "center", QPointF(400, 300), 100.0, 200.0,
            entity_name="Player", component_name="Transform",
        )
        self.assertTrue(self.gizmo.is_dragging)

    def test_update_drag_computes_delta(self):
        self.gizmo.start_drag(
            "center", QPointF(400, 300), 100.0, 200.0,
            entity_name="Player", component_name="Transform",
        )
        result = self.gizmo.update_drag(QPointF(420, 310), zoom=1.0)
        # moved right 20px, down 10px in screen -> world delta same (zoom=1)
        self.assertAlmostEqual(result[0], 120.0, delta=2.0)
        self.assertAlmostEqual(result[1], 210.0, delta=2.0)

    def test_end_drag_returns_data(self):
        self.gizmo.start_drag(
            "center", QPointF(400, 300), 100.0, 200.0,
            entity_name="Player", component_name="Transform",
        )
        self.gizmo.update_drag(QPointF(420, 310), zoom=1.0)
        result = self.gizmo.end_drag()
        self.assertIsNotNone(result)
        self.assertIn("before_state", result)
        self.assertIn("after_state", result)
        self.assertIn("handle", result)
        self.assertEqual(result["handle"], "center")
        self.assertEqual(result["before_state"]["x"], 100.0)
        self.assertEqual(result["before_state"]["y"], 200.0)
        self.assertAlmostEqual(result["after_state"]["x"], 120.0, delta=2.0)
        self.assertAlmostEqual(result["after_state"]["y"], 210.0, delta=2.0)

    def test_end_drag_clears_dragging(self):
        self.gizmo.start_drag(
            "center", QPointF(400, 300), 100.0, 200.0,
            entity_name="Player", component_name="Transform",
        )
        self.gizmo.update_drag(QPointF(420, 310), zoom=1.0)
        self.gizmo.end_drag()
        self.assertFalse(self.gizmo.is_dragging)

    def test_no_drag_end_returns_none(self):
        result = self.gizmo.end_drag()
        self.assertIsNone(result)


class TestGizmoManagerSnap(unittest.TestCase):
    def setUp(self):
        self.gizmo = GizmoManager()

    def test_snap_to_grid(self):
        snapped = self.gizmo._snap_value(17.3)
        self.assertEqual(snapped, 16.0)

    def test_snap_to_grid_rounds_up(self):
        snapped = self.gizmo._snap_value(25.0)
        self.assertEqual(snapped, 32.0)

    def test_snap_custom_step(self):
        snapped = self.gizmo._snap_value(47.0, step=10.0)
        self.assertEqual(snapped, 50.0)

    def test_snap_zero_step_uses_default(self):
        # step=0.0 is falsy, so _snap_value uses SNAP_STEP=16.0
        snapped = self.gizmo._snap_value(17.3, step=0.0)
        self.assertEqual(snapped, 16.0)

    def test_snap_negative_step_returns_value(self):
        snapped = self.gizmo._snap_value(17.3, step=-1.0)
        self.assertEqual(snapped, 17.3)


class TestGizmoHandle(unittest.TestCase):
    def test_handle_has_mode_and_rect(self):
        rect = QRectF(0, 0, 10, 10)
        handle = GizmoHandle(GizmoMode.TRANSLATE_FREE, rect)
        self.assertEqual(handle.mode, GizmoMode.TRANSLATE_FREE)
        self.assertEqual(handle.rect, rect)


class TestCompletedGizmoDrag(unittest.TestCase):
    def test_drag_holds_state(self):
        drag = CompletedGizmoDrag(
            entity_name="Player",
            component_name="Transform",
            before_state={"x": 0.0, "y": 0.0},
            after_state={"x": 10.0, "y": 12.0},
            label="Move Player",
        )
        self.assertEqual(drag.entity_name, "Player")
        self.assertEqual(drag.after_state["x"], 10.0)
        self.assertEqual(drag.label, "Move Player")


class TestGizmoManagerHitTest(unittest.TestCase):
    def setUp(self):
        self.gizmo = GizmoManager()

    def test_hit_test_no_handles_returns_none(self):
        result = self.gizmo.hit_test(QPointF(400, 300))
        self.assertIsNone(result)

    def test_hit_test_hits_center_handle(self):
        self.gizmo.set_mode(GizmoMode.TRANSLATE_FREE)
        self.gizmo.build_handles(QPointF(400, 300), zoom=1.0)
        result = self.gizmo.hit_test(QPointF(400, 300))
        self.assertEqual(result, "center")

    def test_hit_test_hits_x_axis_handle(self):
        self.gizmo.set_mode(GizmoMode.TRANSLATE_FREE)
        self.gizmo.build_handles(QPointF(400, 300), zoom=1.0)
        # X handle is at center + axis_len (50px) = 450, 300
        result = self.gizmo.hit_test(QPointF(450, 300))
        self.assertEqual(result, "x_axis")

    def test_hit_test_hits_y_axis_handle(self):
        self.gizmo.set_mode(GizmoMode.TRANSLATE_FREE)
        self.gizmo.build_handles(QPointF(400, 300), zoom=1.0)
        # Y handle is at center - axis_len (50px) = 400, 250
        result = self.gizmo.hit_test(QPointF(400, 250))
        self.assertEqual(result, "y_axis")

    def test_hit_test_misses(self):
        self.gizmo.set_mode(GizmoMode.TRANSLATE_FREE)
        self.gizmo.build_handles(QPointF(400, 300), zoom=1.0)
        result = self.gizmo.hit_test(QPointF(999, 999))
        self.assertIsNone(result)


class TestGizmoManagerRotate(unittest.TestCase):
    def setUp(self):
        self.gizmo = GizmoManager()
        self.gizmo.set_mode(GizmoMode.ROTATE_Z)
        self.gizmo.build_handles(QPointF(400, 300), zoom=1.0)

    def test_hit_test_rotate_ring(self):
        # Ring radius is 40px. Point at (400+40, 300) = (440, 300)
        result = self.gizmo.hit_test(QPointF(440, 300))
        self.assertEqual(result, "rotate_ring")

    def test_rotate_updates_angle(self):
        self.gizmo.start_drag(
            "rotate_ring", QPointF(440, 300), 100.0, 200.0,
            rotation=0.0, entity_name="Player", component_name="Transform",
        )
        # Move 10px down -> positive angle
        self.gizmo.update_drag(QPointF(440, 310), zoom=1.0)
        # The angle should have changed from 0
        self.assertNotEqual(self.gizmo.current_angle, 0.0)


class TestGizmoManagerScale(unittest.TestCase):
    def setUp(self):
        self.gizmo = GizmoManager()
        self.gizmo.set_mode(GizmoMode.SCALE_UNIFORM)
        self.gizmo.build_handles(QPointF(400, 300), zoom=1.0)

    def test_scale_uniform_updates_scale(self):
        self.gizmo.start_drag(
            "scale_x_pos", QPointF(450, 300), 100.0, 200.0,
            scale_x=1.0, scale_y=1.0, entity_name="Player", component_name="Transform",
        )
        # Move further away from center -> larger scale
        self.gizmo.update_drag(QPointF(500, 300), zoom=1.0)
        sx, sy = self.gizmo.current_scale
        self.assertGreater(sx, 1.0)
        self.assertGreater(sy, 1.0)


class TestGizmoManagerBuildHandles(unittest.TestCase):
    def setUp(self):
        self.gizmo = GizmoManager()

    def test_build_translate_handles(self):
        self.gizmo.set_mode(GizmoMode.TRANSLATE_FREE)
        self.gizmo.build_handles(QPointF(400, 300), zoom=1.0)
        self.assertIsNotNone(self.gizmo.hit_test(QPointF(400, 300)))
        self.assertIsNotNone(self.gizmo.hit_test(QPointF(450, 300)))
        self.assertIsNotNone(self.gizmo.hit_test(QPointF(400, 250)))

    def test_build_rect_handles(self):
        self.gizmo.set_mode(GizmoMode.RECT)
        self.gizmo.build_handles(QPointF(400, 300), zoom=1.0, rect_w=200, rect_h=150)
        # Center of rect should hit "rect_tc" (top center)
        result = self.gizmo.hit_test(QPointF(400, 225))
        self.assertEqual(result, "rect_tc")


if __name__ == "__main__":
    unittest.main()
