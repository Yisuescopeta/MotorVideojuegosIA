import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from engine.editor import EditorLayout, EditorPanelSlots, EditorSelectionState, EditorShell, EditorShellState
from engine.editor.hierarchy_panel import HierarchyPanel


class EditorShellTests(unittest.TestCase):
    def test_editor_shell_composes_layout_with_shared_state_and_slots(self) -> None:
        state = EditorShellState(active_tab="FLOW", active_bottom_tab="TERMINAL")
        slots = EditorPanelSlots(
            project_panel=Mock(),
            flow_panel=Mock(),
            flow_workspace_panel=Mock(),
            console_panel=Mock(),
            terminal_panel=Mock(),
            agent_panel=Mock(),
        )

        with patch.object(EditorLayout, "_resize_render_textures", lambda *args, **kwargs: None):
            shell = EditorShell(1280, 720, state=state, panel_slots=slots)

        self.assertIsNotNone(shell.layout)
        self.assertEqual(shell.layout.active_tab, "FLOW")
        self.assertIs(shell.layout.project_panel, slots.project_panel)
        self.assertIs(shell.layout.terminal_panel, slots.terminal_panel)
        self.assertIs(shell.layout.agent_panel, slots.agent_panel)

        shell.layout.active_bottom_tab = "PROJECT"
        self.assertEqual(state.active_bottom_tab, "PROJECT")

    def test_editor_shell_binds_scene_manager_into_extension_points(self) -> None:
        flow_panel = Mock()
        flow_workspace_panel = Mock()
        shell = EditorShell(
            panel_slots=EditorPanelSlots(
                project_panel=Mock(),
                flow_panel=flow_panel,
                flow_workspace_panel=flow_workspace_panel,
                console_panel=Mock(),
                terminal_panel=None,
                agent_panel=Mock(),
            ),
            hierarchy_panel=HierarchyPanel(),
        )
        manager = Mock()

        shell.bind_scene_manager(manager)

        self.assertIs(shell.hierarchy_panel._scene_manager, manager)
        flow_panel.set_scene_manager.assert_called_once_with(manager)
        flow_workspace_panel.set_scene_manager.assert_called_once_with(manager)

    def test_editor_shell_shares_selection_state_with_hierarchy(self) -> None:
        selection_state = EditorSelectionState()
        shell = EditorShell(selection_state=selection_state, hierarchy_panel=HierarchyPanel())
        world = SimpleNamespace(selected_entity_name="Hero")

        selected_name = shell.hierarchy_panel._get_selected_entity_name(world)

        self.assertEqual(selected_name, "Hero")
        self.assertEqual(selection_state.entity_name, "Hero")


if __name__ == "__main__":
    unittest.main()
