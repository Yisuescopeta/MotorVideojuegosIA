import unittest
from unittest.mock import patch

from engine.editor.hierarchy_panel import HierarchyPanel
from engine.ecs.world import World


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


if __name__ == "__main__":
    unittest.main()
