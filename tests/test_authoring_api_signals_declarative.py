"""Tests para los helpers declarativos de señales en AuthoringAPI."""

import unittest
from unittest.mock import MagicMock

from engine.api._authoring_api import AuthoringAPI


class FakeContext:
    def __init__(self, feature_metadata=None, set_metadata_result=True):
        self._feature_metadata = feature_metadata or {}
        self._set_metadata_result = set_metadata_result
        self.api = MagicMock()
        self.api.get_feature_metadata.return_value = self._feature_metadata
        self.scene_authoring = MagicMock()
        self.scene_authoring.set_feature_metadata.return_value = self._set_metadata_result

    def ok(self, message, data=None):
        return {"success": True, "message": message, "data": data or {}}

    def fail(self, message):
        return {"success": False, "message": message}

    def ensure_edit_mode(self):
        pass


class TestAuthoringAPISignalDeclarative(unittest.TestCase):
    def test_list_signal_connections_declarative_empty(self):
        ctx = FakeContext()
        api = AuthoringAPI(ctx)
        self.assertEqual(api.list_signal_connections_declarative(), [])

    def test_list_signal_connections_declarative_with_data(self):
        connections = [{"id": "c1", "source": {"id": "e1", "signal": "on_die"}}]
        ctx = FakeContext(feature_metadata={"signals": {"connections": connections}})
        auth = AuthoringAPI(ctx)
        result = auth.list_signal_connections_declarative()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "c1")

    def test_get_signal_metadata_empty(self):
        ctx = FakeContext()
        api = AuthoringAPI(ctx)
        self.assertEqual(api.get_signal_metadata(), {})

    def test_get_signal_metadata_with_data(self):
        ctx = FakeContext(feature_metadata={"signals": {"connections": [{"id": "c1"}]}})
        api = AuthoringAPI(ctx)
        result = api.get_signal_metadata()
        self.assertEqual(result["connections"][0]["id"], "c1")

    def test_add_signal_connection_success(self):
        ctx = FakeContext(feature_metadata={"signals": {"connections": []}})
        api = AuthoringAPI(ctx)
        conn = {"id": "c2", "source": {"id": "e2", "signal": "on_jump"}}
        result = api.add_signal_connection(conn)
        self.assertTrue(result["success"])
        ctx.scene_authoring.set_feature_metadata.assert_called_once()
        args = ctx.scene_authoring.set_feature_metadata.call_args[0]
        self.assertEqual(args[0], "signals")
        self.assertEqual(len(args[1]["connections"]), 1)
        self.assertEqual(args[1]["connections"][0]["id"], "c2")

    def test_add_signal_connection_duplicate_id_fails(self):
        ctx = FakeContext(feature_metadata={"signals": {"connections": [{"id": "c1"}]}})
        api = AuthoringAPI(ctx)
        result = api.add_signal_connection({"id": "c1"})
        self.assertFalse(result["success"])
        self.assertIn("already exists", result["message"])

    def test_add_signal_connection_missing_id_fails(self):
        ctx = FakeContext()
        api = AuthoringAPI(ctx)
        result = api.add_signal_connection({"source": {"id": "e1"}})
        self.assertFalse(result["success"])
        self.assertIn("'id'", result["message"])

    def test_remove_signal_connection_success(self):
        ctx = FakeContext(feature_metadata={"signals": {"connections": [{"id": "c1"}, {"id": "c2"}]}})
        api = AuthoringAPI(ctx)
        result = api.remove_signal_connection("c1")
        self.assertTrue(result["success"])
        args = ctx.scene_authoring.set_feature_metadata.call_args[0]
        self.assertEqual(len(args[1]["connections"]), 1)
        self.assertEqual(args[1]["connections"][0]["id"], "c2")

    def test_remove_signal_connection_not_found(self):
        ctx = FakeContext(feature_metadata={"signals": {"connections": [{"id": "c1"}]}})
        api = AuthoringAPI(ctx)
        result = api.remove_signal_connection("c99")
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])


if __name__ == "__main__":
    unittest.main()
