import unittest

from engine.events.deferred_queue import DeferredCallQueue
from engine.events.signals import SignalConnectionFlags, SignalRuntime


class SignalRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.deferred_queue = DeferredCallQueue(max_size=32, max_flush_per_cycle=32)
        self.runtime = SignalRuntime(self.deferred_queue)

    def test_connect_emit_disconnect_round_trip(self) -> None:
        valores: list[int] = []

        connection_id = self.runtime.connect(
            "Player",
            "hit",
            lambda damage: valores.append(damage),
        )

        self.assertTrue(self.runtime.is_connected(connection_id))
        self.assertEqual(self.runtime.emit("Player", "hit", 7), 1)
        self.assertEqual(valores, [7])
        self.assertTrue(self.runtime.disconnect(connection_id))
        self.assertFalse(self.runtime.is_connected(connection_id))

    def test_deferred_connection_waits_until_flush(self) -> None:
        valores: list[str] = []

        self.runtime.connect(
            "PlayButton",
            "pressed",
            lambda estado: valores.append(estado),
            flags=SignalConnectionFlags.DEFERRED,
        )

        self.assertEqual(self.runtime.emit("PlayButton", "pressed", "inicio"), 1)
        self.assertEqual(valores, [])
        self.assertEqual(self.deferred_queue.size, 1)
        self.assertEqual(self.deferred_queue.flush(), 1)
        self.assertEqual(valores, ["inicio"])
        self.assertEqual(self.deferred_queue.size, 0)

    def test_one_shot_disconnects_before_recursive_emit(self) -> None:
        valores: list[int] = []

        def on_pressed(value: int) -> None:
            valores.append(value)
            self.runtime.emit("PlayButton", "pressed", value + 1)

        connection_id = self.runtime.connect(
            "PlayButton",
            "pressed",
            on_pressed,
            flags=SignalConnectionFlags.ONE_SHOT,
        )

        self.assertEqual(self.runtime.emit("PlayButton", "pressed", 1), 1)
        self.assertEqual(valores, [1])
        self.assertFalse(self.runtime.is_connected(connection_id))

    def test_reference_counted_reuses_connection_and_counts_disconnects(self) -> None:
        valores: list[int] = []

        def on_defeated(points: int) -> None:
            valores.append(points)

        first_id = self.runtime.connect(
            "Enemy",
            "defeated",
            on_defeated,
            flags=SignalConnectionFlags.REFERENCE_COUNTED,
        )
        second_id = self.runtime.connect(
            "Enemy",
            "defeated",
            on_defeated,
            flags=SignalConnectionFlags.REFERENCE_COUNTED,
        )

        self.assertEqual(first_id, second_id)
        self.assertEqual(self.runtime.list_connections("Enemy", "defeated")[0].reference_count, 2)
        self.assertTrue(self.runtime.disconnect(first_id))
        self.assertTrue(self.runtime.is_connected(first_id))
        self.assertEqual(self.runtime.list_connections("Enemy", "defeated")[0].reference_count, 1)
        self.assertEqual(self.runtime.emit("Enemy", "defeated", 3), 1)
        self.assertEqual(valores, [3])
        self.assertTrue(self.runtime.disconnect(first_id))
        self.assertFalse(self.runtime.is_connected(first_id))

    def test_emit_uses_snapshot_when_callback_disconnects_another_connection(self) -> None:
        orden: list[str] = []

        def first_callback() -> None:
            orden.append("primero")
            self.runtime.disconnect(second_connection_id)

        def second_callback() -> None:
            orden.append("segundo")

        self.runtime.connect("Emitter", "tick", first_callback)
        second_connection_id = self.runtime.connect("Emitter", "tick", second_callback)

        self.assertEqual(self.runtime.emit("Emitter", "tick"), 2)
        self.assertEqual(orden, ["primero", "segundo"])
        self.assertFalse(self.runtime.is_connected(second_connection_id))

    def test_prune_by_source_removes_all_connections_for_emitter(self) -> None:
        valores: list[int] = []
        self.runtime.connect("Player", "hit", lambda d: valores.append(d), target_id="Target1")
        self.runtime.connect("Player", "die", lambda: valores.append(1), target_id="Target2")
        self.runtime.connect("Enemy", "hit", lambda d: valores.append(d), target_id="Target3")

        self.assertEqual(self.runtime.prune_by_source("Player"), 2)
        self.assertEqual(self.runtime.emit("Player", "hit", 5), 0)
        self.assertEqual(self.runtime.emit("Player", "die"), 0)
        self.assertEqual(self.runtime.emit("Enemy", "hit", 3), 1)

    def test_prune_by_target_removes_all_connections_for_receiver(self) -> None:
        valores: list[int] = []
        self.runtime.connect("Player", "hit", lambda d: valores.append(d), target_id="Target1")
        self.runtime.connect("Enemy", "hit", lambda d: valores.append(d), target_id="Target1")
        self.runtime.connect("Enemy", "die", lambda: valores.append(1), target_id="Target2")

        self.assertEqual(self.runtime.prune_by_target("Target1"), 2)
        self.assertEqual(self.runtime.emit("Player", "hit", 5), 0)
        self.assertEqual(self.runtime.emit("Enemy", "hit", 3), 0)
        self.assertEqual(self.runtime.emit("Enemy", "die"), 1)

    def test_prune_by_target_with_reference_counted_removes_connection_completely(self) -> None:
        valores: list[int] = []

        def on_hit(d: int) -> None:
            valores.append(d)

        self.runtime.connect(
            "Player", "hit", on_hit,
            flags=SignalConnectionFlags.REFERENCE_COUNTED,
            target_id="Target1",
        )
        self.runtime.connect(
            "Player", "hit", on_hit,
            flags=SignalConnectionFlags.REFERENCE_COUNTED,
            target_id="Target1",
        )
        self.assertEqual(self.runtime.list_connections("Player", "hit")[0].reference_count, 2)
        self.assertEqual(self.runtime.prune_by_target("Target1"), 1)
        self.assertEqual(self.runtime.emit("Player", "hit", 5), 0)

    def test_emit_after_pruning_source_or_target_does_not_explode(self) -> None:
        self.runtime.connect("Player", "hit", lambda d: None, target_id="Target1")
        self.runtime.prune_by_source("Player")
        self.assertEqual(self.runtime.emit("Player", "hit", 5), 0)

        self.runtime.connect("Enemy", "hit", lambda d: None, target_id="Target2")
        self.runtime.prune_by_target("Target2")
        self.assertEqual(self.runtime.emit("Enemy", "hit", 3), 0)

    def test_one_shot_and_deferred_still_work_after_pruning(self) -> None:
        deferred_vals: list[str] = []
        one_shot_vals: list[int] = []

        self.runtime.connect(
            "Button", "pressed", lambda s: deferred_vals.append(s),
            flags=SignalConnectionFlags.DEFERRED,
            target_id="DeferredTarget",
        )
        self.runtime.connect(
            "Enemy", "die", lambda v: one_shot_vals.append(v),
            flags=SignalConnectionFlags.ONE_SHOT,
            target_id="OneShotTarget",
        )

        self.runtime.prune_by_target("DeferredTarget")
        self.assertEqual(self.runtime.emit("Button", "pressed", "x"), 0)
        self.assertEqual(self.deferred_queue.size, 0)

        self.assertEqual(self.runtime.emit("Enemy", "die", 1), 1)
        self.assertEqual(one_shot_vals, [1])


if __name__ == "__main__":
    unittest.main()
