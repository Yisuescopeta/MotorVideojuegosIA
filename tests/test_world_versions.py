import unittest

from engine.components.canvas import Canvas
from engine.components.collider import Collider
from engine.components.recttransform import RectTransform
from engine.components.renderorder2d import RenderOrder2D
from engine.components.renderstyle2d import RenderStyle2D
from engine.components.sprite import Sprite
from engine.components.tilemap import Tilemap
from engine.components.transform import Transform
from engine.components.uibutton import UIButton
from engine.ecs.component import Component
from engine.ecs.world import World


class ProbeComponent(Component):
    def __init__(self) -> None:
        self.enabled = True


class WorldVersionTests(unittest.TestCase):
    def test_new_world_versions_start_at_zero(self) -> None:
        world = World()

        self.assertEqual(world.version, 0)
        self.assertEqual(world.structure_version, 0)
        self.assertEqual(world.transform_version, 0)
        self.assertEqual(world.render_version, 0)
        self.assertEqual(world.physics_version, 0)
        self.assertEqual(world.ui_layout_version, 0)
        self.assertEqual(world.selection_version, 0)

    def test_entity_add_and_remove_increment_structure_and_global_versions(self) -> None:
        world = World()

        entity = world.create_entity("Entity")

        self.assertEqual(world.structure_version, 1)
        self.assertEqual(world.version, 1)

        world.remove_entity(entity.id)

        self.assertEqual(world.structure_version, 2)
        self.assertEqual(world.version, 2)

    def test_structural_entity_fields_increment_structure_and_global_versions(self) -> None:
        for field_name, value in (
            ("name", "Renamed"),
            ("parent_name", "Parent"),
            ("groups", ("Gameplay",)),
            ("active", False),
        ):
            with self.subTest(field_name=field_name):
                world = World()
                entity = world.create_entity("Entity")
                structure_before = world.structure_version
                version_before = world.version

                setattr(entity, field_name, value)

                self.assertEqual(world.structure_version, structure_before + 1)
                self.assertEqual(world.version, version_before + 1)

    def test_unrelated_tracked_entity_field_keeps_global_version_compatibility(self) -> None:
        world = World()
        entity = world.create_entity("Entity")
        structure_before = world.structure_version
        version_before = world.version

        entity.tag = "Player"

        self.assertEqual(world.structure_version, structure_before)
        self.assertEqual(world.version, version_before + 1)

    def test_generic_component_membership_increments_only_structure_and_global_versions(self) -> None:
        world = World()
        entity = world.create_entity("Entity")
        structure_before = world.structure_version
        version_before = world.version

        entity.add_component(ProbeComponent())

        self.assertEqual(world.structure_version, structure_before + 1)
        self.assertEqual(world.version, version_before + 1)
        self.assertEqual(world.transform_version, 0)
        self.assertEqual(world.render_version, 0)
        self.assertEqual(world.physics_version, 0)
        self.assertEqual(world.ui_layout_version, 0)

        entity.remove_component(ProbeComponent)

        self.assertEqual(world.structure_version, structure_before + 2)
        self.assertEqual(world.version, version_before + 2)
        self.assertEqual(world.transform_version, 0)
        self.assertEqual(world.render_version, 0)
        self.assertEqual(world.physics_version, 0)
        self.assertEqual(world.ui_layout_version, 0)

    def test_mapped_component_membership_increments_specific_versions(self) -> None:
        cases = (
            (Transform, "transform_version"),
            (Collider, "physics_version"),
            (Sprite, "render_version"),
            (Tilemap, "render_version"),
            (RenderOrder2D, "render_version"),
            (RenderStyle2D, "render_version"),
            (RectTransform, "ui_layout_version"),
            (Canvas, "ui_layout_version"),
            (UIButton, "ui_layout_version"),
        )

        for component_type, version_name in cases:
            with self.subTest(component_type=component_type.__name__):
                world = World()
                entity = world.create_entity("Entity")
                specific_before = getattr(world, version_name)
                structure_before = world.structure_version
                version_before = world.version

                entity.add_component(component_type())

                self.assertEqual(getattr(world, version_name), specific_before + 1)
                self.assertEqual(world.structure_version, structure_before + 1)
                self.assertEqual(world.version, version_before + 1)

                entity.remove_component(component_type)

                self.assertEqual(getattr(world, version_name), specific_before + 2)
                self.assertEqual(world.structure_version, structure_before + 2)
                self.assertEqual(world.version, version_before + 2)

    def test_selected_entity_name_only_increments_selection_version(self) -> None:
        world = World()
        world.create_entity("Entity")
        version_before = world.version
        structure_before = world.structure_version

        world.selected_entity_name = "Entity"

        self.assertEqual(world.selection_version, 1)
        self.assertEqual(world.structure_version, structure_before)
        self.assertEqual(world.version, version_before)

    def test_internal_component_mutation_does_not_increment_world_versions(self) -> None:
        world = World()
        entity = world.create_entity("Entity")
        transform = Transform()
        entity.add_component(transform)
        versions_before = (
            world.version,
            world.structure_version,
            world.transform_version,
            world.render_version,
            world.physics_version,
            world.ui_layout_version,
        )

        transform.x = 10

        self.assertEqual(
            versions_before,
            (
                world.version,
                world.structure_version,
                world.transform_version,
                world.render_version,
                world.physics_version,
                world.ui_layout_version,
            ),
        )


if __name__ == "__main__":
    unittest.main()
