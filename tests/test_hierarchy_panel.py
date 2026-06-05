import unittest
from contextlib import nullcontext
from unittest.mock import patch

from engine.ecs.world import World
from engine.editor.hierarchy_panel import HierarchyPanel


class HierarchyPanelRowsTests(unittest.TestCase):
    def test_roots_use_world_children_index(self) -> None:
        world = World()
        parent = world.create_entity("Parent")
        child_without_transform = world.create_entity("Child")
        child_without_transform.parent_name = "Parent"

        panel = HierarchyPanel()

        self.assertEqual(panel._get_root_entities(world), [parent])

    def test_visible_rows_follow_expanded_ids(self) -> None:
        world = World()
        root = world.create_entity("Root")
        child = world.create_entity("Child")
        child.parent_name = "Root"
        grandchild = world.create_entity("Grandchild")
        grandchild.parent_name = "Child"
        sibling = world.create_entity("Sibling")

        panel = HierarchyPanel()

        self.assertEqual(panel._get_visible_rows(world), [(root.id, 0), (sibling.id, 0)])

        panel.expanded_ids.add(root.id)
        self.assertEqual(
            panel._get_visible_rows(world),
            [(root.id, 0), (child.id, 1), (sibling.id, 0)],
        )

        panel.expanded_ids.add(child.id)
        self.assertEqual(
            panel._get_visible_rows(world),
            [(root.id, 0), (child.id, 1), (grandchild.id, 2), (sibling.id, 0)],
        )

    def test_visible_rows_cache_tracks_expanded_ids(self) -> None:
        world = World()
        root = world.create_entity("Root")
        child = world.create_entity("Child")
        child.parent_name = "Root"
        panel = HierarchyPanel()

        first_rows = panel._get_visible_rows(world)
        second_rows = panel._get_visible_rows(world)
        self.assertIs(second_rows, first_rows)

        panel.expanded_ids.add(root.id)
        expanded_rows = panel._get_visible_rows(world)
        self.assertIsNot(expanded_rows, first_rows)
        self.assertEqual(expanded_rows, [(root.id, 0), (child.id, 1)])

    def test_visible_rows_cache_tracks_search_text(self) -> None:
        world = World()
        root = world.create_entity("Root")
        child = world.create_entity("Needle")
        child.parent_name = "Root"
        sibling = world.create_entity("Sibling")
        panel = HierarchyPanel()

        first_rows = panel._get_visible_rows(world)
        panel.search_text = "needle"
        filtered_rows = panel._get_visible_rows(world)

        self.assertIsNot(filtered_rows, first_rows)
        self.assertEqual(filtered_rows, [(root.id, 0), (child.id, 1)])
        self.assertNotIn((sibling.id, 0), filtered_rows)

    def test_visible_rows_cache_invalidates_on_structure_version(self) -> None:
        world = World()
        root = world.create_entity("Root")
        panel = HierarchyPanel()

        first_rows = panel._get_visible_rows(world)
        with patch.object(panel, "_build_visible_rows", wraps=panel._build_visible_rows) as build_rows:
            self.assertIs(panel._get_visible_rows(world), first_rows)
            build_rows.assert_not_called()

            second_root = world.create_entity("SecondRoot")
            updated_rows = panel._get_visible_rows(world)

        self.assertIsNot(updated_rows, first_rows)
        self.assertEqual(updated_rows, [(root.id, 0), (second_root.id, 0)])

    def test_tree_model_cache_tracks_structure_version(self) -> None:
        world = World()
        root = world.create_entity("Root")
        panel = HierarchyPanel()

        first_model = panel._get_tree_model(world)
        self.assertIn(root.id, first_model.node_map)

        second = world.create_entity("Second")
        second_model = panel._get_tree_model(world)

        self.assertIsNot(second_model, first_model)
        self.assertIn(second.id, second_model.node_map)

    def test_render_does_not_crash_with_normal_entities(self) -> None:
        world = World()
        world.create_entity("Root")
        panel = HierarchyPanel()

        class FakeMouse:
            x = 0.0
            y = 0.0

        fake_rl = unittest.mock.MagicMock()
        fake_rl.Color.side_effect = lambda r, g, b, a: (r, g, b, a)
        fake_rl.Rectangle.side_effect = lambda x, y, w, h: unittest.mock.MagicMock(x=x, y=y, width=w, height=h)
        fake_rl.Vector2.side_effect = lambda x, y: unittest.mock.MagicMock(x=x, y=y)
        fake_rl.get_mouse_position.return_value = FakeMouse()
        fake_rl.check_collision_point_rec.return_value = False
        fake_rl.get_mouse_wheel_move.return_value = 0.0
        fake_rl.is_mouse_button_pressed.return_value = False
        fake_rl.is_mouse_button_released.return_value = False
        fake_rl.is_mouse_button_down.return_value = False
        fake_rl.MOUSE_BUTTON_LEFT = 0
        fake_rl.MOUSE_BUTTON_RIGHT = 1
        fake_rl.GRAY = (128, 128, 128, 255)

        with patch("engine.editor.hierarchy_panel.rl", fake_rl), patch(
            "engine.editor.hierarchy_panel.editor_scissor", lambda *_args, **_kwargs: nullcontext()
        ), patch("engine.editor.hierarchy_panel.draw_icon") as draw_icon_mock:
            panel.render(world, 0, 0, 240, 180)

        draw_icon_mock.assert_called()


if __name__ == "__main__":
    unittest.main()
