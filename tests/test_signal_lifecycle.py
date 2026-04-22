import unittest

from engine.ecs.world import World
from engine.events.deferred_queue import DeferredCallQueue
from engine.events.signals import SignalConnectionFlags, SignalRuntime


class SignalLifecycleIntegrationTests(unittest.TestCase):
    """Tests de integración entre World.destroy_entity y SignalRuntime pruning."""

    def setUp(self) -> None:
        self.world = World()
        self.deferred_queue = DeferredCallQueue(max_size=32, max_flush_per_cycle=32)
        self.runtime = SignalRuntime(self.deferred_queue)
        self.world.on_entity_destroyed.append(self._on_entity_destroyed)

    def _on_entity_destroyed(self, entity):
        self.runtime.prune_by_source(entity.name)
        self.runtime.prune_by_target(entity.name)

    def test_destroy_emitter_cleans_its_connections(self) -> None:
        valores: list[int] = []
        self.runtime.connect("Player", "hit", lambda d: valores.append(d), target_id="Enemy")
        player = self.world.create_entity("Player")
        self.world.destroy_entity(player.id)
        self.assertEqual(self.runtime.emit("Player", "hit", 5), 0)

    def test_destroy_receiver_cleans_its_connections(self) -> None:
        valores: list[int] = []
        self.runtime.connect("Player", "hit", lambda d: valores.append(d), target_id="Enemy")
        enemy = self.world.create_entity("Enemy")
        self.world.destroy_entity(enemy.id)
        self.assertEqual(self.runtime.emit("Player", "hit", 5), 0)

    def test_emit_after_destroying_entities_does_not_explode(self) -> None:
        self.runtime.connect("Player", "hit", lambda d: None, target_id="Enemy")
        player = self.world.create_entity("Player")
        enemy = self.world.create_entity("Enemy")
        self.world.destroy_entity(player.id)
        self.world.destroy_entity(enemy.id)
        self.assertEqual(self.runtime.emit("Player", "hit", 5), 0)

    def test_one_shot_and_deferred_work_with_lifecycle(self) -> None:
        deferred_vals: list[str] = []
        one_shot_vals: list[int] = []

        self.runtime.connect(
            "Button", "pressed", lambda s: deferred_vals.append(s),
            flags=SignalConnectionFlags.DEFERRED,
            target_id="ButtonTarget",
        )
        self.runtime.connect(
            "Enemy", "die", lambda v: one_shot_vals.append(v),
            flags=SignalConnectionFlags.ONE_SHOT,
            target_id="EnemyTarget",
        )

        button = self.world.create_entity("Button")
        enemy = self.world.create_entity("Enemy")

        self.world.destroy_entity(button.id)
        self.assertEqual(self.runtime.emit("Button", "pressed", "x"), 0)
        self.assertEqual(self.deferred_queue.size, 0)

        self.assertEqual(self.runtime.emit("Enemy", "die", 1), 1)
        self.assertEqual(one_shot_vals, [1])

    def test_multiple_observers_receive_destroy_notification(self) -> None:
        notified: list[int] = []
        self.world.on_entity_destroyed.append(lambda e: notified.append(1))
        self.world.on_entity_destroyed.append(lambda e: notified.append(2))
        entity = self.world.create_entity("TestEntity")
        self.world.destroy_entity(entity.id)
        self.assertEqual(notified, [1, 2])

    def test_destroy_entity_as_source_and_target_cleans_both_directions(self) -> None:
        valores: list[int] = []
        self.runtime.connect("Player", "hit", lambda d: valores.append(d), target_id="Player")
        self.runtime.connect("Player", "die", lambda: valores.append(1), target_id="Player")
        self.runtime.connect("Enemy", "hit", lambda d: valores.append(d), target_id="Player")

        player = self.world.create_entity("Player")
        self.world.destroy_entity(player.id)

        self.assertEqual(self.runtime.emit("Player", "hit", 5), 0)
        self.assertEqual(self.runtime.emit("Player", "die"), 0)
        self.assertEqual(self.runtime.emit("Enemy", "hit", 3), 0)

    def test_pruning_during_emit_does_not_break_snapshot(self) -> None:
        orden: list[str] = []

        def callback_that_destroys() -> None:
            orden.append("callback")
            enemy = self.world.get_entity_by_name("Enemy")
            if enemy is not None:
                self.world.destroy_entity(enemy.id)

        self.runtime.connect("Player", "attack", callback_that_destroys, target_id="Player")
        self.runtime.connect("Player", "attack", lambda: orden.append("second"), target_id="Enemy")

        player = self.world.create_entity("Player")
        enemy = self.world.create_entity("Enemy")

        self.assertEqual(self.runtime.emit("Player", "attack"), 2)
        self.assertEqual(orden, ["callback", "second"])

    def test_clear_fires_on_entity_destroyed_for_each_entity(self) -> None:
        nombres_destruidos: list[str] = []
        self.world.on_entity_destroyed.append(lambda e: nombres_destruidos.append(e.name))

        self.world.create_entity("A")
        self.world.create_entity("B")
        self.world.create_entity("C")

        self.world.clear()
        self.assertEqual(sorted(nombres_destruidos), ["A", "B", "C"])

    def test_clear_prunes_signal_connections_by_source_and_target(self) -> None:
        valores: list[int] = []
        self.runtime.connect("Player", "hit", lambda d: valores.append(d), target_id="Enemy")
        self.runtime.connect("Enemy", "die", lambda: valores.append(1), target_id="Player")

        self.world.create_entity("Player")
        self.world.create_entity("Enemy")

        self.world.clear()
        self.assertEqual(self.runtime.emit("Player", "hit", 5), 0)
        self.assertEqual(self.runtime.emit("Enemy", "die"), 0)
        self.assertEqual(len(self.runtime.list_connections()), 0)

    def test_clear_leaves_world_in_consistent_state(self) -> None:
        ent = self.world.create_entity("Hero")
        ent.groups = ["heroes"]
        self.world.selected_entity_name = "Hero"

        self.world.clear()
        self.assertEqual(self.world.entity_count(), 0)
        self.assertEqual(self.world.group_registry.list_groups(), [])
        self.assertIsNone(self.world.get_entity_by_name("Hero"))
        self.assertIsNone(self.world.selected_entity_name)

    def test_remove_entity_still_works_after_clear_changes(self) -> None:
        notificado: list[str] = []
        self.world.on_entity_destroyed.append(lambda e: notificado.append(e.name))

        ent = self.world.create_entity("Solo")
        self.world.destroy_entity(ent.id)
        self.assertEqual(notificado, ["Solo"])
        self.assertEqual(self.world.entity_count(), 0)


if __name__ == "__main__":
    unittest.main()
