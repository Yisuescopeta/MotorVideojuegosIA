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
from engine.editor.ui_core.icon_names import (
    ICON_ANIMATION,
    ICON_AUDIO,
    ICON_CAMERA,
    ICON_CANVAS,
    ICON_COLLIDER,
    ICON_ENTITY,
    ICON_LIGHT,
    ICON_NODE2D,
    ICON_PARTICLES,
    ICON_RIGIDBODY,
    ICON_SPRITE,
    ICON_TILEMAP,
    ICON_UI_BUTTON,
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
        self.assertEqual(get_type_icon("Entity"), ICON_ENTITY)

        entity.add_component(Transform())
        self.assertEqual(get_entity_type(entity), "Node2D")
        self.assertEqual(get_type_icon("Node2D"), ICON_NODE2D)

        camera = world.create_entity("CameraThing")
        camera.add_component(type("Camera2D", (), {})())
        self.assertEqual(get_entity_type(camera), "Camera")
        self.assertEqual(get_type_icon(get_entity_type(camera)), ICON_CAMERA)

        sprite = world.create_entity("SpriteThing")
        sprite.add_component(type("Sprite", (), {})())
        self.assertEqual(get_entity_type(sprite), "Sprite")
        self.assertEqual(get_type_icon("Sprite"), ICON_SPRITE)

        tilemap = world.create_entity("TilemapThing")
        tilemap.add_component(type("TileMap", (), {})())
        self.assertEqual(get_entity_type(tilemap), "TileMap")
        self.assertEqual(get_type_icon("TileMap"), ICON_TILEMAP)

        rigidbody = world.create_entity("BodyThing")
        rigidbody.add_component(type("RigidBody2D", (), {})())
        self.assertEqual(get_entity_type(rigidbody), "RigidBody")
        self.assertEqual(get_type_icon("RigidBody"), ICON_RIGIDBODY)

        collider = world.create_entity("ColliderThing")
        collider.add_component(type("BoxCollider", (), {})())
        self.assertEqual(get_entity_type(collider), "Collider")
        self.assertEqual(get_type_icon("Collider"), ICON_COLLIDER)

        canvas = world.create_entity("CanvasThing")
        canvas.add_component(type("CanvasLayer", (), {})())
        self.assertEqual(get_entity_type(canvas), "Canvas")
        self.assertEqual(get_type_icon("Canvas"), ICON_CANVAS)

        ui_button = world.create_entity("ButtonThing")
        ui_button.add_component(type("UIButton", (), {})())
        self.assertEqual(get_entity_type(ui_button), "UIButton")
        self.assertEqual(get_type_icon("UIButton"), ICON_UI_BUTTON)

        audio = world.create_entity("AudioThing")
        audio.add_component(type("AudioStreamPlayer2D", (), {})())
        self.assertEqual(get_entity_type(audio), "Audio")
        self.assertEqual(get_type_icon("Audio"), ICON_AUDIO)

        animation = world.create_entity("AnimationThing")
        animation.add_component(type("AnimationPlayer", (), {})())
        self.assertEqual(get_entity_type(animation), "Animation")
        self.assertEqual(get_type_icon("Animation"), ICON_ANIMATION)

        light = world.create_entity("LightThing")
        light.add_component(type("Light2D", (), {})())
        self.assertEqual(get_entity_type(light), "Light")
        self.assertEqual(get_type_icon("Light"), ICON_LIGHT)

        particles = world.create_entity("ParticlesThing")
        particles.add_component(type("CPUParticles2D", (), {})())
        self.assertEqual(get_entity_type(particles), "Particles")
        self.assertEqual(get_type_icon("Particles"), ICON_PARTICLES)

        component_only = world.create_entity("ComponentOnly")
        component_only.add_component(type("CustomComponent", (), {})())
        self.assertEqual(get_entity_type(component_only), "ComponentEntity")
        self.assertEqual(get_type_icon("ComponentEntity"), ICON_ENTITY)


if __name__ == "__main__":
    unittest.main()
