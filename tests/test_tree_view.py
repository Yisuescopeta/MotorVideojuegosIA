import unittest

from engine.components.transform import Transform
from engine.ecs.world import World
from engine.editor.ui.tree_view import (
    TreeModel,
    filter_nodes,
    filter_visible_rows,
    get_entity_type,
    get_type_icon,
)


class TreeViewTests(unittest.TestCase):
    def test_build_uses_world_children_index_without_mutating_world(self) -> None:
        world = World()
        parent = world.create_entity("Parent")
        child = world.create_entity("Child")
        child.parent_name = "Parent"
        version = world.structure_version

        model = TreeModel.build(world)

        self.assertEqual(world.structure_version, version)
        self.assertEqual([node.id for node in model.root_nodes], [parent.id])
        parent_node = model.node_map[parent.id]
        self.assertTrue(parent_node.is_expandable)
        self.assertEqual(parent_node.children[0].id, child.id)
        self.assertEqual(parent_node.children[0].parent_id, parent.id)

    def test_build_falls_back_to_transform_parent(self) -> None:
        class MinimalWorld:
            structure_version = 7

            def __init__(self) -> None:
                self.entities = []

            def iter_all_entities(self):
                return iter(self.entities)

        world = MinimalWorld()
        real_world = World()
        parent = real_world.create_entity("Parent")
        child = real_world.create_entity("Child")
        parent_transform = Transform()
        child_transform = Transform()
        child_transform.set_parent(parent_transform)
        parent.add_component(parent_transform)
        child.add_component(child_transform)
        world.entities = [parent, child]

        model = TreeModel.build(world)

        self.assertEqual([node.id for node in model.root_nodes], [parent.id])
        self.assertEqual(model.root_nodes[0].children[0].id, child.id)

    def test_visible_rows_follow_expanded_ids_depth_first(self) -> None:
        world = World()
        root = world.create_entity("Root")
        child = world.create_entity("Child")
        child.parent_name = "Root"
        grandchild = world.create_entity("Grandchild")
        grandchild.parent_name = "Child"
        sibling = world.create_entity("Sibling")
        model = TreeModel.build(world)

        self.assertEqual(model.get_visible_rows(set()), [(root.id, 0), (sibling.id, 0)])
        self.assertEqual(model.get_visible_rows({root.id}), [(root.id, 0), (child.id, 1), (sibling.id, 0)])
        self.assertEqual(
            model.get_visible_rows({root.id, child.id}),
            [(root.id, 0), (child.id, 1), (grandchild.id, 2), (sibling.id, 0)],
        )

    def test_filter_helpers_are_case_insensitive_and_include_ancestors(self) -> None:
        world = World()
        root = world.create_entity("Root")
        child = world.create_entity("EnemyShip")
        child.parent_name = "Root"
        sibling = world.create_entity("Camera")
        model = TreeModel.build(world)

        self.assertEqual([node.id for node in filter_nodes(model, "enemy")], [child.id])
        self.assertEqual(filter_visible_rows(model, set(), "ENEMY"), [(root.id, 0), (child.id, 1)])
        self.assertEqual(filter_visible_rows(model, set(), "camera"), [(sibling.id, 0)])

    def test_type_and_icon_helpers(self) -> None:
        world = World()
        entity = world.create_entity("Thing")
        self.assertEqual(get_entity_type(entity), "Entity")
        self.assertEqual(get_type_icon("Entity"), "menu")

        entity.add_component(Transform())
        self.assertEqual(get_entity_type(entity), "ComponentEntity")
        self.assertEqual(get_type_icon("ComponentEntity"), "gear")


if __name__ == "__main__":
    unittest.main()
