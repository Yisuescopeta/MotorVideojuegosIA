import unittest

from engine.editor.ui.widget_state import (
    WidgetResult,
    WidgetState,
    WidgetVisualState,
    resolve_visual_state,
)


class EditorUIWidgetStateTests(unittest.TestCase):
    def test_widget_result_defaults(self) -> None:
        result = WidgetResult()
        self.assertFalse(result.hovered)
        self.assertFalse(result.pressed)
        self.assertFalse(result.clicked)
        self.assertFalse(result.right_clicked)
        self.assertFalse(result.changed)
        self.assertIsNone(result.value)

    def test_widget_result_consumed(self) -> None:
        self.assertFalse(WidgetResult().consumed())
        self.assertTrue(WidgetResult(pressed=True).consumed())
        self.assertTrue(WidgetResult(clicked=True).consume())
        self.assertTrue(WidgetResult(right_clicked=True).consumed())
        self.assertTrue(WidgetResult(changed=True).consumed())

    def test_visual_state_enum_members(self) -> None:
        self.assertEqual(WidgetVisualState.NORMAL.name, "NORMAL")
        self.assertEqual(WidgetVisualState.HOVER.name, "HOVER")
        self.assertEqual(WidgetVisualState.PRESSED.name, "PRESSED")
        self.assertEqual(WidgetVisualState.ACTIVE.name, "ACTIVE")
        self.assertEqual(WidgetVisualState.DISABLED.name, "DISABLED")
        self.assertEqual(WidgetVisualState.FOCUSED.name, "FOCUSED")
        self.assertEqual(WidgetVisualState.SELECTED.name, "SELECTED")

    def test_resolve_visual_state_priority(self) -> None:
        self.assertIs(resolve_visual_state(enabled=False, pressed=True), WidgetVisualState.DISABLED)
        self.assertIs(resolve_visual_state(pressed=True, active=True), WidgetVisualState.PRESSED)
        self.assertIs(resolve_visual_state(active=True, selected=True), WidgetVisualState.ACTIVE)
        self.assertIs(resolve_visual_state(selected=True, focused=True), WidgetVisualState.SELECTED)
        self.assertIs(resolve_visual_state(focused=True, hovered=True), WidgetVisualState.FOCUSED)
        self.assertIs(resolve_visual_state(hovered=True), WidgetVisualState.HOVER)
        self.assertIs(resolve_visual_state(), WidgetVisualState.NORMAL)

    def test_widget_state_transitions(self) -> None:
        state = WidgetState()
        self.assertIs(state.visual, WidgetVisualState.NORMAL)
        state = state.update(hovered=True)
        self.assertIs(state.visual, WidgetVisualState.HOVER)
        state = state.update(pressed=True, active=True)
        self.assertIs(state.visual, WidgetVisualState.PRESSED)
        state = state.update(pressed=False, selected=True)
        self.assertIs(state.visual, WidgetVisualState.ACTIVE)
        state = state.update(active=False)
        self.assertIs(state.visual, WidgetVisualState.SELECTED)
        state = state.update(enabled=False)
        self.assertIs(state.visual, WidgetVisualState.DISABLED)


if __name__ == "__main__":
    unittest.main()
