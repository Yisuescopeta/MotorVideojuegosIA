"""
tests/test_runtime_api_signals_groups_services.py - Validación de la API pública
de señales, grupos y servicios globales expuesta por RuntimeAPI.
"""

import unittest
from unittest.mock import MagicMock

from engine.api._runtime_api import RuntimeAPI
from engine.ecs.entity import normalize_entity_groups
from engine.events.signals import SignalConnectionFlags


class FakeContext:
    """Contexto mínimo para instanciar RuntimeAPI sin EngineAPI completo."""

    def __init__(self, runtime=None, scene_authoring=None):
        self._runtime = runtime
        self._scene_authoring = scene_authoring
        self.api = MagicMock()
        self.api.game = runtime

    @property
    def runtime(self):
        return self._runtime

    @property
    def scene_authoring(self):
        return self._scene_authoring

    def ok(self, message, data=None):
        return {"success": True, "message": message, "data": data}

    def fail(self, message):
        return {"success": False, "message": message, "data": None}


class TestRuntimeAPIServices(unittest.TestCase):
    """Tests de servicios globales expuestos por RuntimeAPI."""

    def _make_runtime(self):
        runtime = MagicMock()
        runtime.is_edit_mode = False
        servicios = MagicMock()
        servicios.obtener = lambda name: {"score": 100} if name == "GameState" else None
        servicios.tiene = lambda name: name in {"GameState", "AudioManager"}
        servicios.registrar = MagicMock()
        servicios.registrar_builtin = MagicMock()
        runtime.servicios = servicios
        runtime.signal_runtime = None
        runtime.group_operations = None
        runtime.world = None
        return runtime

    def test_get_service_returns_value(self):
        runtime = self._make_runtime()
        api = RuntimeAPI(FakeContext(runtime))
        self.assertEqual(api.get_service("GameState"), {"score": 100})

    def test_get_service_returns_none_when_missing(self):
        runtime = self._make_runtime()
        api = RuntimeAPI(FakeContext(runtime))
        self.assertIsNone(api.get_service("Missing"))

    def test_has_service_returns_true_when_exists(self):
        runtime = self._make_runtime()
        api = RuntimeAPI(FakeContext(runtime))
        self.assertTrue(api.has_service("AudioManager"))

    def test_has_service_returns_false_when_missing(self):
        runtime = self._make_runtime()
        api = RuntimeAPI(FakeContext(runtime))
        self.assertFalse(api.has_service("Missing"))

    def test_register_service_runtime(self):
        runtime = self._make_runtime()
        api = RuntimeAPI(FakeContext(runtime))
        result = api.register_service_runtime("MyService", {"data": 1})
        self.assertTrue(result["success"])
        runtime.servicios.registrar.assert_called_once_with("MyService", {"data": 1})

    def test_register_service_builtin(self):
        runtime = self._make_runtime()
        api = RuntimeAPI(FakeContext(runtime))
        result = api.register_service_builtin("BuiltinService", {"data": 2})
        self.assertTrue(result["success"])
        runtime.servicios.registrar_builtin.assert_called_once_with("BuiltinService", {"data": 2})

    def test_service_methods_fail_without_runtime(self):
        api = RuntimeAPI(FakeContext(None))
        self.assertIsNone(api.get_service("Any"))
        self.assertFalse(api.has_service("Any"))
        result = api.register_service_runtime("Any", {})
        self.assertFalse(result["success"])


class TestRuntimeAPIGroups(unittest.TestCase):
    """Tests de operaciones de grupos en RuntimeAPI."""

    def _make_runtime_with_world(self):
        runtime = MagicMock()
        runtime.is_edit_mode = False
        world = MagicMock()
        runtime.world = world
        runtime.signal_runtime = None
        runtime.servicios = None

        group_ops = MagicMock()
        group_ops.get_entities = lambda name: []
        group_ops.get_first_entity = lambda name: None
        group_ops.has = lambda group, entity: False
        group_ops.count = lambda name: 0
        group_ops.call_group = lambda *a, **k: 0
        group_ops.emit_group = lambda *a, **k: 0
        runtime.group_operations = group_ops
        return runtime, world, group_ops

    def test_get_entities_in_group_delegates(self):
        runtime, world, group_ops = self._make_runtime_with_world()
        fake_entity = MagicMock()
        fake_entity.name = "Player"
        group_ops.get_entities = lambda name: [fake_entity] if name == "Players" else []
        api = RuntimeAPI(FakeContext(runtime))
        self.assertEqual(api.get_entities_in_group("Players"), ["Player"])

    def test_add_entity_to_group(self):
        runtime, world, _ = self._make_runtime_with_world()
        entity = MagicMock()
        entity.groups = ("Damageables",)
        world.get_entity_by_name = lambda name: entity if name == "EnemyA" else None
        api = RuntimeAPI(FakeContext(runtime))
        result = api.add_entity_to_group("EnemyA", "Enemies")
        self.assertTrue(result["success"])
        self.assertEqual(set(entity.groups), {"Damageables", "Enemies"})

    def test_add_entity_to_group_missing_entity(self):
        runtime, world, _ = self._make_runtime_with_world()
        world.get_entity_by_name = lambda _: None
        api = RuntimeAPI(FakeContext(runtime))
        result = api.add_entity_to_group("Missing", "Enemies")
        self.assertFalse(result["success"])

    def test_add_entity_to_group_no_runtime(self):
        api = RuntimeAPI(FakeContext(None))
        result = api.add_entity_to_group("A", "B")
        self.assertFalse(result["success"])

    def test_add_entity_to_group_uses_authoring_route_in_edit_mode(self):
        runtime, world, _ = self._make_runtime_with_world()
        runtime.is_edit_mode = True
        authoring = MagicMock()
        authoring.find_entity_data = MagicMock(return_value={"name": "EnemyA", "groups": ["Damageables"]})
        authoring.update_entity_property = MagicMock(return_value=True)
        api = RuntimeAPI(FakeContext(runtime, scene_authoring=authoring))

        result = api.add_entity_to_group("EnemyA", "Enemies")

        self.assertTrue(result["success"])
        world.get_entity_by_name.assert_not_called()
        authoring.update_entity_property.assert_called_once_with(
            "EnemyA",
            "groups",
            ["Damageables", "Enemies"],
        )

    def test_remove_entity_from_group_runtime(self):
        runtime, world, _ = self._make_runtime_with_world()
        entity = MagicMock()
        entity.groups = ("Damageables", "Enemies")
        world.get_entity_by_name = lambda name: entity if name == "EnemyA" else None
        api = RuntimeAPI(FakeContext(runtime))

        result = api.remove_entity_from_group("EnemyA", "Enemies")

        self.assertTrue(result["success"])
        self.assertEqual(set(entity.groups), {"Damageables"})

    def test_get_entity_groups_uses_authoring_in_edit_mode(self):
        runtime, _, _ = self._make_runtime_with_world()
        runtime.is_edit_mode = True
        authoring = MagicMock()
        authoring.find_entity_data = MagicMock(return_value={"name": "EnemyA", "groups": ["Enemies", "Damageables", "Enemies"]})
        api = RuntimeAPI(FakeContext(runtime, scene_authoring=authoring))

        groups = api.get_entity_groups("EnemyA")

        self.assertEqual(groups, list(normalize_entity_groups(["Enemies", "Damageables", "Enemies"])))


class TestRuntimeAPISignals(unittest.TestCase):
    """Tests de señales en RuntimeAPI."""

    def _make_runtime_with_signals(self):
        runtime = MagicMock()
        runtime.is_edit_mode = False
        signal_runtime = MagicMock()
        signal_runtime.connect = MagicMock(return_value="conn::1")
        signal_runtime.emit = MagicMock(return_value=2)
        signal_runtime.disconnect = MagicMock(return_value=True)

        conn = MagicMock()
        conn.connection_id = "conn::1"
        conn.signal.source_id = "Player"
        conn.signal.signal_name = "on_jump"
        conn.flags = SignalConnectionFlags.ONE_SHOT
        conn.binds = (10,)
        conn.enabled = True
        conn.target_id = None
        conn.description = "test"
        conn.reference_count = 1
        signal_runtime.list_connections = MagicMock(return_value=[conn])

        runtime.signal_runtime = signal_runtime
        runtime.world = None
        runtime.servicios = None
        runtime.group_operations = None
        return runtime, signal_runtime

    def test_connect_signal(self):
        runtime, signal_runtime = self._make_runtime_with_signals()
        api = RuntimeAPI(FakeContext(runtime))

        def callback(x):
            return x

        cid = api.connect_signal("Player", "on_jump", callback, flags=["one_shot"], binds=(10,))
        self.assertEqual(cid, "conn::1")
        signal_runtime.connect.assert_called_once()
        _, kwargs = signal_runtime.connect.call_args
        self.assertEqual(kwargs["flags"], SignalConnectionFlags.ONE_SHOT)

    def test_connect_signal_without_runtime(self):
        api = RuntimeAPI(FakeContext(None))
        cid = api.connect_signal("Player", "on_jump", lambda: None)
        self.assertEqual(cid, "")

    def test_emit_signal(self):
        runtime, signal_runtime = self._make_runtime_with_signals()
        api = RuntimeAPI(FakeContext(runtime))
        total = api.emit_signal("Player", "on_jump", 42)
        self.assertEqual(total, 2)
        signal_runtime.emit.assert_called_once_with("Player", "on_jump", 42)

    def test_emit_signal_without_runtime(self):
        api = RuntimeAPI(FakeContext(None))
        self.assertEqual(api.emit_signal("Player", "on_jump"), 0)

    def test_disconnect_signal(self):
        runtime, signal_runtime = self._make_runtime_with_signals()
        api = RuntimeAPI(FakeContext(runtime))
        self.assertTrue(api.disconnect_signal("conn::1"))
        signal_runtime.disconnect.assert_called_once_with("conn::1")

    def test_list_signal_connections(self):
        runtime, signal_runtime = self._make_runtime_with_signals()
        api = RuntimeAPI(FakeContext(runtime))
        connections = api.list_signal_connections(source_id="Player")
        self.assertEqual(len(connections), 1)
        self.assertEqual(connections[0]["connection_id"], "conn::1")
        self.assertEqual(connections[0]["flags"], ["one_shot"])

    def test_list_signal_connections_no_runtime(self):
        api = RuntimeAPI(FakeContext(None))
        self.assertEqual(api.list_signal_connections(), [])


if __name__ == "__main__":
    unittest.main()
