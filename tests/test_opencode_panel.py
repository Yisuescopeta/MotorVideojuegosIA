import os
import sys
import time
import unittest

import pyray as rl

sys.path.append(os.getcwd())

from engine.editor.opencode_panel import OpenCodePanel
from engine.core.game import Game


class _FakeOpenCodeBridge:
    def __init__(self) -> None:
        self.connect_calls = 0
        self.ensure_server_calls = 0
        self.start_visible_calls = 0
        self.list_sessions_calls = 0
        self.refresh_calls = 0
        self.export_calls = 0
        self.export_messages_calls = 0
        self.create_session_calls = []
        self.select_calls = []
        self.send_calls = []
        self.respond_calls = []
        self._sessions = [
            {"id": "sess_1", "title": "Smoke Session", "status": "ready", "updatedAt": "2026-03-24T09:10:00Z"},
        ]

    def _snapshot(self, session_id: str = ""):
        resolved = session_id or (self.select_calls[-1] if self.select_calls else "")
        messages = []
        diff = []
        approvals = []
        if resolved:
            messages = [
                {"info": {"role": "user"}, "parts": [{"type": "text", "text": "Build me a test"}]},
                {"info": {"role": "assistant"}, "parts": [{"type": "text", "text": "Plan ready"}]},
            ]
            diff = [{"path": "docs/example.md"}]
            approvals = [{"permission_id": "perm_1", "tool": "edit", "description": "docs/**"}]
        return {
            "connection_status": self.get_connection_status(),
            "active_session_id": resolved,
            "sessions": list(self._sessions),
            "messages": messages,
            "diff": diff,
            "approvals": approvals,
            "last_error": "",
            "last_operation": "refresh_sessions",
            "last_artifacts": {},
        }

    def get_connection_status(self):
        return {
            "healthy": True,
            "state": "connected",
            "status": "connected",
            "summary": "Conectado a OpenCode",
            "technical_detail": "",
            "action_hint": "",
            "base_url": "http://127.0.0.1:4096",
            "version": "test",
        }

    def connect(self):
        self.connect_calls += 1
        return self._snapshot()

    def ensure_server(self):
        self.ensure_server_calls += 1
        return self._snapshot()

    def start_visible(self):
        self.start_visible_calls += 1
        snapshot = self._snapshot()
        snapshot["connection_status"] = {
            **snapshot["connection_status"],
            "summary": "OpenCode abierto y conectado",
            "command": "cmd.exe /c start \"\" opencode",
        }
        return snapshot

    def load_initial_state(self):
        self.connect_calls += 1
        return self._snapshot()

    def list_sessions(self):
        self.list_sessions_calls += 1
        time.sleep(0.05)
        return list(self._sessions)

    def create_session(self, title: str):
        self.create_session_calls.append(title)
        time.sleep(0.05)
        return {"id": "sess_2", "title": title}

    def create_and_select_session(self, title: str):
        self.create_session_calls.append(title)
        self._sessions.append({"id": "sess_2", "title": title, "status": "working", "updatedAt": "2026-03-24T09:11:00Z"})
        return self._snapshot("sess_2")

    def refresh_session_view(self, session_id: str, limit: int = 100):
        self.refresh_calls += 1
        time.sleep(0.05)
        return self._snapshot(session_id)

    def select_session(self, session_id: str, limit: int = 100):
        self.select_calls.append(session_id)
        self.refresh_calls += 1
        time.sleep(0.05)
        return self._snapshot(session_id)

    def send_prompt(self, session_id: str, text: str, agent: str = "plan", model=None, out_dir: str = ""):
        if not session_id:
            session_id = "sess_auto"
            if not any(item.get("id") == session_id for item in self._sessions):
                self._sessions.append({"id": session_id, "title": "Auto Session", "status": "working", "updatedAt": "2026-03-24T09:12:00Z"})
        self.send_calls.append((session_id, text, agent, model, out_dir))
        time.sleep(0.05)
        return {
            "artifact_dir": "artifacts/opencode/demo",
            "transcript_path": "artifacts/opencode/demo/transcript.json",
            "diff_path": "artifacts/opencode/demo/diff.json",
            "snapshot": self._snapshot(session_id),
        }

    def export_diff_artifact(self, session_id: str):
        self.export_calls += 1
        return {"artifact_dir": "artifacts/opencode/demo", "diff_path": "artifacts/opencode/demo/diff.json"}

    def export_messages_artifact(self, session_id: str, limit: int = 100):
        self.export_messages_calls += 1
        return {
            "artifact_dir": "artifacts/opencode/demo",
            "transcript_path": "artifacts/opencode/demo/transcript.json",
        }

    def respond_permission(self, session_id: str, permission_id: str, response: str, remember: bool = False):
        self.respond_calls.append((session_id, permission_id, response, remember))
        return {"accepted": True, "snapshot": self._snapshot(session_id)}


class _FakeLayout:
    def __init__(self, panel: OpenCodePanel) -> None:
        self.opencode_panel = panel
        self.assistant_minimized = False
        self.calls = []

    def set_assistant_minimized(self, value: bool) -> None:
        self.assistant_minimized = value
        self.calls.append(value)

    def update_layout(self, width: int, height: int) -> None:
        self.calls.append((width, height))


class OpenCodePanelIntegrationTests(unittest.TestCase):
    def test_panel_background_refresh_does_not_block_editor_loop(self) -> None:
        panel = OpenCodePanel()
        bridge = _FakeOpenCodeBridge()
        panel.set_bridge(bridge)
        panel._drain_background_tasks_for_tests()
        self.assertEqual(panel.sessions[0]["id"], "sess_1")
        self.assertEqual(bridge.connect_calls, 1)

        panel.selected_session_id = "sess_1"
        panel.refresh_selected_session()
        rect = rl.Rectangle(0.0, 0.0, 1280.0, 720.0)

        start = time.perf_counter()
        panel.update(rect)
        elapsed = time.perf_counter() - start

        self.assertLess(elapsed, 0.08)
        self.assertEqual(panel.status_line, "working")

        panel._drain_background_tasks_for_tests()
        self.assertEqual(panel.status_line, "waiting_permission")
        self.assertEqual(panel.messages[1]["parts"][0]["text"], "Plan ready")
        self.assertEqual(panel.diff[0]["path"], "docs/example.md")
        self.assertEqual(panel.approvals[0]["permission_id"], "perm_1")
        self.assertTrue(panel.connection_status["healthy"])

    def test_panel_can_create_session_send_prompt_and_track_artifacts(self) -> None:
        panel = OpenCodePanel()
        bridge = _FakeOpenCodeBridge()
        panel.set_bridge(bridge)
        panel._drain_background_tasks_for_tests()

        panel.create_session("Editor Session")
        panel._drain_background_tasks_for_tests()
        self.assertEqual(panel.selected_session_id, "sess_2")
        self.assertEqual(bridge.create_session_calls[-1], "Editor Session")

        panel.composer_text = "Analyze the repo"
        panel.agent_mode = "build"
        panel.send_prompt()
        panel._drain_background_tasks_for_tests()

        self.assertEqual(bridge.send_calls[-1][0], "sess_2")
        self.assertEqual(bridge.send_calls[-1][1], "Analyze the repo")
        self.assertEqual(bridge.send_calls[-1][2], "build")
        self.assertEqual(panel.last_artifacts["artifact_dir"], "artifacts/opencode/demo")
        self.assertEqual(panel.composer_text, "")

    def test_panel_can_send_first_prompt_without_preselecting_session(self) -> None:
        panel = OpenCodePanel()
        bridge = _FakeOpenCodeBridge()
        panel.set_bridge(bridge)
        panel._drain_background_tasks_for_tests()

        panel.selected_session_id = ""
        panel.composer_text = "Primera orden"
        panel.send_prompt()
        panel._drain_background_tasks_for_tests()

        self.assertEqual(bridge.send_calls[-1][1], "Primera orden")
        self.assertTrue(panel.selected_session_id)

    def test_message_preview_prefers_final_text_over_step_markers(self) -> None:
        panel = OpenCodePanel()
        preview = panel._message_preview(
            {
                "parts": [
                    {"type": "step-start"},
                    {"type": "reasoning", "text": "Pensando"},
                    {"type": "text", "text": "Hola, en que puedo ayudarte?"},
                    {"type": "step-finish"},
                ]
            }
        )
        self.assertEqual(preview, "Hola, en que puedo ayudarte?")

    def test_busy_status_chip_uses_syncing_for_refresh_work(self) -> None:
        panel = OpenCodePanel()
        panel._busy_label = "Refreshing session..."
        panel._worker_thread = object()
        original_is_busy = panel._is_busy
        try:
            panel._is_busy = lambda: True
            self.assertEqual(panel._status_chip_label(), "syncing")
        finally:
            panel._is_busy = original_is_busy
            panel._worker_thread = None

    def test_panel_can_start_visible_from_header_flow(self) -> None:
        panel = OpenCodePanel()
        bridge = _FakeOpenCodeBridge()
        panel.set_bridge(bridge)
        panel._drain_background_tasks_for_tests()

        panel.start_visible()
        panel._drain_background_tasks_for_tests()

        self.assertEqual(bridge.start_visible_calls, 1)
        self.assertEqual(panel.connection_status["state"], "connected")

    def test_panel_routes_permission_response_through_bridge(self) -> None:
        panel = OpenCodePanel()
        bridge = _FakeOpenCodeBridge()
        panel.set_bridge(bridge)
        panel._drain_background_tasks_for_tests()

        panel.selected_session_id = "sess_1"
        panel.refresh_selected_session()
        panel._drain_background_tasks_for_tests()
        panel.selected_permission_id = "perm_1"
        panel.respond_to_selected_permission("allow")
        panel._drain_background_tasks_for_tests()

        self.assertEqual(bridge.respond_calls[-1], ("sess_1", "perm_1", "allow", False))

    def test_panel_computes_adaptive_layout_for_narrow_and_wide_widths(self) -> None:
        panel = OpenCodePanel()
        wide = panel._compute_layout(rl.Rectangle(0.0, 0.0, 980.0, 720.0))
        narrow = panel._compute_layout(rl.Rectangle(0.0, 0.0, 540.0, 720.0))

        self.assertLess(wide["session_card"].x, wide["content_col"].x)
        self.assertEqual(narrow["session_card"].x, narrow["content_col"].x)
        self.assertGreater(narrow["content_col"].y, narrow["session_card"].y)

    def test_panel_exposes_structured_error_state(self) -> None:
        class ErrorBridge(_FakeOpenCodeBridge):
            def get_connection_status(self):
                return {
                    "healthy": False,
                    "state": "unreachable",
                    "status": "error",
                    "summary": "No se pudo conectar con OpenCode",
                    "technical_detail": "OpenCode health request failed: [WinError 1]",
                    "action_hint": "Revisa si el servidor esta iniciado y vuelve a intentar.",
                    "base_url": "",
                    "version": "",
                }

            def load_initial_state(self):
                return {
                    "connection_status": self.get_connection_status(),
                    "active_session_id": "",
                    "sessions": [],
                    "messages": [],
                    "diff": [],
                    "approvals": [],
                    "last_error": "OpenCode health request failed: [WinError 1]",
                    "last_operation": "connect",
                    "last_artifacts": {},
                }

        panel = OpenCodePanel()
        panel.auto_start_on_open = False
        panel.set_bridge(ErrorBridge())
        panel._drain_background_tasks_for_tests()

        self.assertEqual(panel.status_line, "error")
        self.assertEqual(panel.connection_status["summary"], "No se pudo conectar con OpenCode")
        self.assertIn("WinError 1", panel.connection_status["technical_detail"])

    def test_panel_auto_starts_visible_client_once_when_initial_connection_is_unreachable(self) -> None:
        class AutoStartBridge(_FakeOpenCodeBridge):
            def __init__(self) -> None:
                super().__init__()
                self._healthy = False

            def get_connection_status(self):
                if self._healthy:
                    return super().get_connection_status()
                return {
                    "healthy": False,
                    "state": "unreachable",
                    "status": "error",
                    "summary": "No se pudo conectar con OpenCode",
                    "technical_detail": "Connection refused",
                    "action_hint": "Pulsa Start o Connect.",
                    "base_url": "http://127.0.0.1:4096",
                    "version": "",
                }

            def load_initial_state(self):
                return {
                    "connection_status": self.get_connection_status(),
                    "active_session_id": "",
                    "sessions": [],
                    "messages": [],
                    "diff": [],
                    "approvals": [],
                    "last_error": "Connection refused",
                    "last_operation": "connect",
                    "last_artifacts": {},
                }

            def start_visible(self):
                self.start_visible_calls += 1
                self._healthy = True
                return self._snapshot()

        panel = OpenCodePanel()
        bridge = AutoStartBridge()
        panel.set_bridge(bridge)
        panel._drain_background_tasks_for_tests()

        self.assertEqual(bridge.start_visible_calls, 1)
        self.assertTrue(panel.connection_status["healthy"])

    def test_game_syncs_right_rail_minimized_state_from_opencode_panel(self) -> None:
        panel = OpenCodePanel()
        panel.is_minimized = True
        layout = _FakeLayout(panel)
        game = Game.__new__(Game)
        game.editor_layout = layout
        game.width = 0
        game.height = 0

        original_get_screen_width = rl.get_screen_width
        original_get_screen_height = rl.get_screen_height
        try:
            rl.get_screen_width = lambda: 1440
            rl.get_screen_height = lambda: 900
            Game._sync_assistant_panel_layout(game, force=True)
        finally:
            rl.get_screen_width = original_get_screen_width
            rl.get_screen_height = original_get_screen_height

        self.assertTrue(layout.assistant_minimized)
        self.assertEqual(game.width, 1440)
        self.assertEqual(game.height, 900)


if __name__ == "__main__":
    unittest.main()
