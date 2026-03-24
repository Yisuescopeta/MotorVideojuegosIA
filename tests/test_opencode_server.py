import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(os.getcwd())

from engine.integrations.opencode import (
    OpenCodeBackendManager,
    OpenCodeServerConfig,
    OpenCodeServerProcess,
    OpenCodeUnavailableError,
)


class OpenCodeServerConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_root = Path(tempfile.mkdtemp(prefix="opencode-config-test-"))
        self.project_root = self._temp_root / "Project"
        self.project_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self._temp_root, ignore_errors=True)

    def test_load_creates_default_config_under_motor_directory(self) -> None:
        config = OpenCodeServerConfig.load(self.project_root)
        config_path = self.project_root / ".motor" / "opencode" / "config.json"

        self.assertTrue(config_path.exists())
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["hostname"], "127.0.0.1")
        self.assertEqual(payload["port"], 4096)
        self.assertEqual(config.port, 4096)


class OpenCodeServerProcessTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_root = Path(tempfile.mkdtemp(prefix="opencode-process-test-"))
        self.project_root = self._temp_root / "Project"
        self.project_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self._temp_root, ignore_errors=True)

    def test_start_fails_softly_when_opencode_is_missing(self) -> None:
        config = OpenCodeServerConfig(
            port=self._find_free_port(),
            hostname="127.0.0.1",
            password="",
            startup_timeout_seconds=2.0,
            health_timeout_seconds=0.5,
            shutdown_timeout_seconds=1.0,
        )
        config.save(self.project_root)
        server = OpenCodeServerProcess(project_root=self.project_root, executable="__missing_opencode_binary__")

        with self.assertRaises(OpenCodeUnavailableError) as exc:
            server.start()

        message = str(exc.exception)
        self.assertIn("OpenCode is not installed", message)
        self.assertIn("opencode", message)
        self.assertFalse(server.is_running)

    @unittest.skipUnless(shutil.which("opencode"), "OpenCode executable not available on PATH")
    def test_start_health_stop_roundtrip_when_opencode_is_available(self) -> None:
        config = OpenCodeServerConfig(
            port=self._find_free_port(),
            hostname="127.0.0.1",
            password="",
            startup_timeout_seconds=15.0,
            health_timeout_seconds=3.0,
            shutdown_timeout_seconds=5.0,
        )
        config.save(self.project_root)
        server = OpenCodeServerProcess(project_root=self.project_root)

        start_result = server.start()
        try:
            health = server.health()
            self.assertTrue(start_result["started"])
            self.assertTrue(health["healthy"])
            self.assertTrue(bool(health["version"]))
        finally:
            stop_result = server.stop()

        self.assertTrue(stop_result["stopped"])
        self.assertFalse(server.is_running)

    def _find_free_port(self) -> int:
        import socket

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])


class OpenCodeBackendManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_root = Path(tempfile.mkdtemp(prefix="opencode-backend-test-"))
        self.project_root = self._temp_root / "Project"
        self.project_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self._temp_root, ignore_errors=True)

    def test_connect_reports_unavailable_when_binary_missing(self) -> None:
        from unittest import mock
        from engine.integrations.opencode import OpenCodeUnavailableError

        manager = OpenCodeBackendManager(self.project_root)
        with mock.patch.object(manager._server, "health", side_effect=OpenCodeUnavailableError("OpenCode is not installed or is not on PATH.")):
            status = manager.connect()
        self.assertEqual(status["state"], "unavailable")
        self.assertIn("OpenCode no esta instalado", status["summary"])

    def test_ensure_server_reports_connected_after_start(self) -> None:
        from unittest import mock

        manager = OpenCodeBackendManager(self.project_root)
        with mock.patch.object(manager, "connect", side_effect=[{"healthy": False, "state": "unreachable"}, {"healthy": True, "state": "connected", "summary": "Conectado a OpenCode", "technical_detail": "", "action_hint": "", "base_url": "http://127.0.0.1:4096", "version": "test", "pid": 123, "owned_by_editor": True}]):
            with mock.patch.object(manager._server, "start", return_value={"pid": 123, "already_running": False}):
                status = manager.ensure_server()
        self.assertTrue(status["healthy"])
        self.assertEqual(status["state"], "connected")

    def test_start_visible_reports_unavailable_when_binary_missing(self) -> None:
        from unittest import mock

        manager = OpenCodeBackendManager(self.project_root)
        with mock.patch.object(manager, "connect", return_value={"healthy": False, "state": "unreachable"}):
            with mock.patch.object(manager._server, "launch_visible_client", side_effect=OpenCodeUnavailableError("OpenCode is not installed or is not on PATH.")):
                status = manager.start_visible()
        self.assertEqual(status["state"], "unavailable")
        self.assertIn("OpenCode no esta instalado", status["summary"])

    def test_start_visible_waits_for_connection_after_launch(self) -> None:
        from unittest import mock

        manager = OpenCodeBackendManager(self.project_root)
        launch_payload = {
            "launch_command": "cmd.exe /c start \"\" opencode",
            "target_command": "opencode project --hostname 127.0.0.1 --port 4096",
        }
        with mock.patch.object(manager, "connect", side_effect=[
            {"healthy": False, "state": "unreachable"},
            {"healthy": False, "state": "unreachable", "command": ""},
            {"healthy": True, "state": "connected", "summary": "Conectado a OpenCode", "technical_detail": "", "action_hint": "", "base_url": "http://127.0.0.1:4096", "version": "test", "pid": 0, "owned_by_editor": False, "command": ""},
        ]):
            with mock.patch.object(manager._server, "launch_visible_client", return_value=launch_payload):
                status = manager.start_visible()
        self.assertTrue(status["healthy"])
        self.assertEqual(status["summary"], "OpenCode abierto y conectado")
        self.assertEqual(status["command"], launch_payload["launch_command"])


if __name__ == "__main__":
    unittest.main()
