"""
tests/test_group_operations.py - Validación de operaciones de gameplay sobre grupos.
"""

import unittest
from unittest.mock import MagicMock

from engine.ecs.entity import Entity
from engine.ecs.group_operations import GroupOperations
from engine.ecs.world import World


class FakeScriptBehaviourSystem:
    """Sistema fake que registra invocaciones para testear call_group."""

    def __init__(self):
        self.invocations: list[tuple[str, str, tuple, dict]] = []

    def invoke_callable(self, world, entity_name, method_name, *args, **kwargs):
        self.invocations.append((entity_name, method_name, args, kwargs))
        return True


class FakeSignalRuntime:
    """SignalRuntime fake que registra emisiones para testear emit_group."""

    def __init__(self):
        self.emissions: list[tuple[str, str, tuple, dict]] = []

    def emit(self, source_id, signal_name, *args, **kwargs):
        self.emissions.append((source_id, signal_name, args, kwargs))
        return 1


class TestGroupOperationsQueries(unittest.TestCase):
    """Tests de consultas puras sobre GroupOperations."""

    def _make_world_with_entities(self):
        world = World()
        e1 = Entity("Player")
        e1.groups = ("Players", "Damageables")
        e2 = Entity("EnemyA")
        e2.groups = ("Enemies", "Damageables")
        e3 = Entity("EnemyB")
        e3.groups = ("Enemies",)
        e4 = Entity("Pickup")
        # sin grupos
        for ent in (e1, e2, e3, e4):
            world.add_entity(ent)
        return world, e1, e2, e3, e4

    def test_get_entities(self):
        world, *_ = self._make_world_with_entities()
        ops = GroupOperations(world)
        nombres = [e.name for e in ops.get_entities("Enemies")]
        self.assertEqual(nombres, ["EnemyA", "EnemyB"])

    def test_get_first_entity_returns_active(self):
        world, e1, *_ = self._make_world_with_entities()
        ops = GroupOperations(world)
        first = ops.get_first_entity("Players")
        self.assertIsNotNone(first)
        self.assertEqual(first.name, "Player")

    def test_get_first_entity_returns_none_when_inactive(self):
        world, e1, *_ = self._make_world_with_entities()
        e1.active = False
        ops = GroupOperations(world)
        # get_first_entity filtra por active, por eso debe devolver None
        first = ops.get_first_entity("Players")
        self.assertIsNone(first)

    def test_has_by_name(self):
        world, *_ = self._make_world_with_entities()
        ops = GroupOperations(world)
        self.assertTrue(ops.has("Enemies", "EnemyA"))
        self.assertFalse(ops.has("Enemies", "Player"))

    def test_has_entity(self):
        world, e1, *_ = self._make_world_with_entities()
        ops = GroupOperations(world)
        self.assertTrue(ops.has_entity("Players", e1))
        self.assertFalse(ops.has_entity("Enemies", e1))

    def test_count(self):
        world, *_ = self._make_world_with_entities()
        ops = GroupOperations(world)
        self.assertEqual(ops.count("Enemies"), 2)
        self.assertEqual(ops.count("Damageables"), 2)
        self.assertEqual(ops.count("NonExistent"), 0)

    def test_is_empty(self):
        world, *_ = self._make_world_with_entities()
        ops = GroupOperations(world)
        self.assertFalse(ops.is_empty("Enemies"))
        self.assertTrue(ops.is_empty("NonExistent"))

    def test_list_groups(self):
        world, *_ = self._make_world_with_entities()
        ops = GroupOperations(world)
        self.assertEqual(
            ops.list_groups(),
            ["Damageables", "Enemies", "Players"],
        )

    def test_serialization_preserved(self):
        """La serialización del World sigue incluyendo groups intactos."""
        world, *_ = self._make_world_with_entities()
        data = world.serialize()
        entidades = {e["name"]: e for e in data["entities"]}
        self.assertEqual(entidades["Player"].get("groups"), ["Players", "Damageables"])
        self.assertNotIn("groups", entidades["Pickup"])


class TestGroupOperationsCallGroup(unittest.TestCase):
    """Tests de invocación masiva sobre grupos (call_group)."""

    def test_call_group_invokes_on_all_active(self):
        world = World()
        e1 = Entity("A")
        e1.groups = ("Targets",)
        e2 = Entity("B")
        e2.groups = ("Targets",)
        e3 = Entity("C")
        e3.groups = ("Targets",)
        e3.active = False
        world.add_entity(e1)
        world.add_entity(e2)
        world.add_entity(e3)

        fake_sbs = FakeScriptBehaviourSystem()
        ops = GroupOperations(world, script_behaviour_system=fake_sbs)
        invocado = ops.call_group("Targets", "do_thing", 42, extra="value")

        self.assertEqual(invocado, 2)
        self.assertEqual(len(fake_sbs.invocations), 2)
        self.assertIn(("A", "do_thing", (42,), {"extra": "value"}), fake_sbs.invocations)
        self.assertIn(("B", "do_thing", (42,), {"extra": "value"}), fake_sbs.invocations)

    def test_call_group_returns_zero_when_no_system(self):
        world = World()
        e = Entity("A")
        e.groups = ("Targets",)
        world.add_entity(e)
        ops = GroupOperations(world)
        self.assertEqual(ops.call_group("Targets", "method"), 0)

    def test_call_group_returns_zero_on_empty_group(self):
        world = World()
        fake_sbs = FakeScriptBehaviourSystem()
        ops = GroupOperations(world, script_behaviour_system=fake_sbs)
        self.assertEqual(ops.call_group("Empty", "method"), 0)


class TestGroupOperationsEmitGroup(unittest.TestCase):
    """Tests de emisión masiva de señales sobre grupos (emit_group)."""

    def test_emit_group_emits_to_all_active(self):
        world = World()
        e1 = Entity("A")
        e1.groups = ("Targets",)
        e2 = Entity("B")
        e2.groups = ("Targets",)
        e3 = Entity("C")
        e3.groups = ("Targets",)
        e3.active = False
        world.add_entity(e1)
        world.add_entity(e2)
        world.add_entity(e3)

        fake_signals = FakeSignalRuntime()
        ops = GroupOperations(world, signal_runtime=fake_signals)
        total = ops.emit_group("Targets", "damage", 10)

        self.assertEqual(total, 2)
        self.assertEqual(len(fake_signals.emissions), 2)
        self.assertIn(("A", "damage", (10,), {}), fake_signals.emissions)
        self.assertIn(("B", "damage", (10,), {}), fake_signals.emissions)

    def test_emit_group_returns_zero_when_no_signal_runtime(self):
        world = World()
        e = Entity("A")
        e.groups = ("Targets",)
        world.add_entity(e)
        ops = GroupOperations(world)
        self.assertEqual(ops.emit_group("Targets", "damage"), 0)

    def test_emit_group_returns_zero_on_empty_group(self):
        world = World()
        fake_signals = FakeSignalRuntime()
        ops = GroupOperations(world, signal_runtime=fake_signals)
        self.assertEqual(ops.emit_group("Empty", "damage"), 0)


if __name__ == "__main__":
    unittest.main()
