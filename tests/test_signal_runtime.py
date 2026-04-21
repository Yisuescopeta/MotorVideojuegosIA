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


if __name__ == "__main__":
    unittest.main()
