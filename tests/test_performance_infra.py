import os
import sys
import unittest
from unittest.mock import patch

sys.path.append(os.getcwd())

from engine.components.canvas import Canvas
from engine.components.recttransform import RectTransform
from engine.components.renderorder2d import RenderOrder2D
from engine.components.sprite import Sprite
from engine.components.transform import Transform
from engine.components.uibutton import UIButton
from engine.ecs.world import World
from engine.systems.render_system import RenderSystem
from engine.systems.ui_system import UISystem


class PerformanceInfraTests(unittest.TestCase):
    def _make_transform(self, x: float = 0.0, y: float = 0.0) -> Transform:
        return Transform(x=x, y=y, rotation=0.0, scale_x=1.0, scale_y=1.0)

    def test_world_indices_track_name_parent_and_component_lookup(self) -> None:
        world = World()
        parent = world.create_entity("Parent")
        parent.add_component(self._make_transform())
        child = world.create_entity("Child")
        child.add_component(self._make_transform())
        child.parent_name = "Parent"
        world.selected_entity_name = "Child"

        self.assertIs(world.get_entity_by_name("Child"), child)
        self.assertEqual([entity.name for entity in world.get_children("Parent")], ["Child"])
        self.assertEqual([entity.name for entity in world.get_entities_with(Transform)], ["Parent", "Child"])
        self.assertIs(world.get_entity_by_component_instance(child.get_component(Transform)), child)

        child.name = "ChildRenamed"
        self.assertIsNone(world.get_entity_by_name("Child"))
        self.assertIs(world.get_entity_by_name("ChildRenamed"), child)
        self.assertEqual(world.selected_entity_name, "ChildRenamed")

        child.remove_component(Transform)
        self.assertEqual([entity.name for entity in world.get_entities_with(Transform)], ["Parent"])

    def test_ui_layout_cache_reuses_layout_until_world_changes(self) -> None:
        world = World()
        canvas = world.create_entity("CanvasRoot")
        canvas.add_component(Canvas())
        canvas.add_component(RectTransform())
        button = world.create_entity("Button")
        button.parent_name = "CanvasRoot"
        button.add_component(
            RectTransform(
                anchor_min_x=0.5,
                anchor_min_y=0.5,
                anchor_max_x=0.5,
                anchor_max_y=0.5,
                pivot_x=0.5,
                pivot_y=0.5,
                width=200.0,
                height=80.0,
            )
        )
        button.add_component(UIButton(label="Play"))

        system = UISystem()

        with patch.object(system, "_layout_children", wraps=system._layout_children) as layout_children:
            system.update(world, (800.0, 600.0))
            first_call_count = layout_children.call_count
            system.update(world, (800.0, 600.0))
            self.assertEqual(layout_children.call_count, first_call_count)

            button.layer = "UI"
            system.update(world, (800.0, 600.0))
            self.assertGreater(layout_children.call_count, first_call_count)

        snapshot_ref = system.get_layout_snapshot(copy_result=False)
        snapshot_copy = system.get_layout_snapshot()
        self.assertIsNot(snapshot_ref, snapshot_copy)
        self.assertIn("Button", snapshot_ref)

    def test_render_entity_sort_cache_rebuilds_only_when_world_changes(self) -> None:
        world = World()
        first = world.create_entity("A")
        first.add_component(self._make_transform())
        first.add_component(RenderOrder2D(sorting_layer="Default", order_in_layer=0))
        second = world.create_entity("B")
        second.add_component(self._make_transform())
        second.add_component(RenderOrder2D(sorting_layer="Default", order_in_layer=10))
        second.add_component(Sprite(texture_path="", width=32, height=32))

        render_system = RenderSystem()

        first_sorted = render_system._sorted_render_entities(world)
        second_sorted = render_system._sorted_render_entities(world)
        self.assertIs(first_sorted, second_sorted)
        self.assertEqual([entity.name for entity in first_sorted], ["A", "B"])

        third = world.create_entity("C")
        third.add_component(self._make_transform())
        updated_sorted = render_system._sorted_render_entities(world)
        self.assertIsNot(updated_sorted, first_sorted)
        self.assertEqual([entity.name for entity in updated_sorted], ["A", "C", "B"])


if __name__ == "__main__":
    unittest.main()
