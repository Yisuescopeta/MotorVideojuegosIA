import unittest

from engine.ecs.component import Component
from engine.ecs.entity import Entity
from engine.ecs.world import World


class ProbeComponent(Component):
    def __init__(self, value: int = 0) -> None:
        self.enabled = True
        self.value = value


class ExtraProbeComponent(Component):
    def __init__(self) -> None:
        self.enabled = True


class ECSIteratorTests(unittest.TestCase):
    def test_iter_all_entities_returns_all_entities_without_list(self) -> None:
        world = World()
        active = world.create_entity("Active")
        inactive = world.create_entity("Inactive")
        inactive.active = False

        entities = world.iter_all_entities()

        self.assertNotIsInstance(entities, list)
        self.assertEqual(list(entities), [active, inactive])

    def test_iter_entities_returns_only_active_entities_without_list(self) -> None:
        world = World()
        active = world.create_entity("Active")
        inactive = world.create_entity("Inactive")
        inactive.active = False

        entities = world.iter_entities()

        self.assertNotIsInstance(entities, list)
        self.assertEqual(list(entities), [active])

    def test_get_all_entities_keeps_list_compatibility(self) -> None:
        world = World()
        entity = world.create_entity("Entity")

        entities = world.get_all_entities()

        self.assertIsInstance(entities, list)
        self.assertEqual(entities, [entity])

    def test_iter_components_returns_components_without_list(self) -> None:
        entity = Entity("Entity")
        first = ProbeComponent(1)
        second = ExtraProbeComponent()
        entity.add_component(first)
        entity.add_component(second)

        components = entity.iter_components()

        self.assertNotIsInstance(components, list)
        self.assertEqual(list(components), [first, second])

    def test_get_all_components_keeps_list_compatibility(self) -> None:
        entity = Entity("Entity")
        component = ProbeComponent(1)
        entity.add_component(component)

        components = entity.get_all_components()

        self.assertIsInstance(components, list)
        self.assertEqual(components, [component])


if __name__ == "__main__":
    unittest.main()
