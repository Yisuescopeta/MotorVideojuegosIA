import base64
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from urllib import error

sys.path.append(os.getcwd())

from engine.integrations.opencode import OpenCodeClient, OpenCodeHTTPError, OpenCodeServerConfig


class _FakeHTTPResponse:
    def __init__(self, body: bytes, lines: list[bytes] | None = None) -> None:
        self._body = body
        self._lines = list(lines or [])

    def read(self) -> bytes:
        return self._body

    def __iter__(self):
        return iter(self._lines)

    def close(self) -> None:
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class OpenCodeClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_root = Path(tempfile.mkdtemp(prefix="opencode-client-test-"))
        self.project_root = self._temp_root / "Project"
        self.project_root.mkdir(parents=True, exist_ok=True)
        OpenCodeServerConfig(
            port=4310,
            hostname="127.0.0.1",
            password="secret",
            startup_timeout_seconds=2.0,
            health_timeout_seconds=1.0,
            shutdown_timeout_seconds=1.0,
        ).save(self.project_root)
        self.client = OpenCodeClient(project_root=self.project_root)

    def tearDown(self) -> None:
        shutil.rmtree(self._temp_root, ignore_errors=True)

    def test_create_session_posts_expected_payload_and_auth_header(self) -> None:
        captured: dict[str, object] = {}

        def fake_urlopen(req, timeout=None):
            captured["url"] = req.full_url
            captured["method"] = req.get_method()
            captured["body"] = req.data.decode("utf-8")
            captured["auth"] = req.get_header("Authorization")
            return _FakeHTTPResponse(json.dumps({"id": "sess_1", "title": "Plan"}).encode("utf-8"))

        with mock.patch("engine.integrations.opencode.client.request.urlopen", side_effect=fake_urlopen):
            result = self.client.create_session("Plan")

        self.assertEqual(result["id"], "sess_1")
        self.assertEqual(captured["url"], "http://127.0.0.1:4310/session")
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(json.loads(str(captured["body"])), {"title": "Plan"})
        expected_auth = "Basic " + base64.b64encode(b"opencode:secret").decode("ascii")
        self.assertEqual(captured["auth"], expected_auth)

    def test_send_message_uses_plan_agent_and_writes_artifacts(self) -> None:
        def fake_urlopen(req, timeout=None):
            if req.get_method() == "POST" and req.full_url.endswith("/message"):
                payload = json.loads(req.data.decode("utf-8"))
                self.assertEqual(payload["agent"], "plan")
                self.assertEqual(payload["parts"], [{"type": "text", "text": "Analiza esto"}])
                return _FakeHTTPResponse(json.dumps({"info": {"id": "msg_1"}, "parts": []}).encode("utf-8"))
            if req.get_method() == "GET" and "/message" in req.full_url:
                return _FakeHTTPResponse(json.dumps([{"info": {"id": "msg_1"}, "parts": []}]).encode("utf-8"))
            if req.get_method() == "GET" and req.full_url.endswith("/diff"):
                return _FakeHTTPResponse(json.dumps([{"path": "docs/file.md"}]).encode("utf-8"))
            raise AssertionError(f"Unexpected request: {req.get_method()} {req.full_url}")

        with mock.patch("engine.integrations.opencode.client.request.urlopen", side_effect=fake_urlopen):
            result = self.client.send_message("sess_1", "Analiza esto")

        self.assertEqual(result["info"]["id"], "msg_1")
        transcript_path = self.project_root / "artifacts" / "opencode" / "sessions" / "sess_1" / "transcript.json"
        diff_path = self.project_root / "artifacts" / "opencode" / "sessions" / "sess_1" / "diff.json"
        self.assertTrue(transcript_path.exists())
        self.assertTrue(diff_path.exists())
        self.assertEqual(json.loads(diff_path.read_text(encoding="utf-8"))[0]["path"], "docs/file.md")

    def test_get_messages_passes_limit_query(self) -> None:
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["url"] = req.full_url
            return _FakeHTTPResponse(json.dumps([{"info": {"id": "msg_1"}, "parts": []}]).encode("utf-8"))

        with mock.patch("engine.integrations.opencode.client.request.urlopen", side_effect=fake_urlopen):
            messages = self.client.get_messages("sess_1", limit=5)

        self.assertEqual(messages[0]["info"]["id"], "msg_1")
        self.assertEqual(captured["url"], "http://127.0.0.1:4310/session/sess_1/message?limit=5")

    def test_respond_permission_serializes_remember_flag(self) -> None:
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["body"] = json.loads(req.data.decode("utf-8"))
            return _FakeHTTPResponse(b"true")

        with mock.patch("engine.integrations.opencode.client.request.urlopen", side_effect=fake_urlopen):
            ok = self.client.respond_permission("sess_1", "perm_1", "allow", remember=True)

        self.assertTrue(ok)
        self.assertEqual(captured["body"], {"response": "allow", "remember": True})

    def test_stream_events_parses_basic_sse_frames(self) -> None:
        response = _FakeHTTPResponse(
            b"",
            lines=[
                b"event: server.connected\n",
                b"id: evt_1\n",
                b"data: {\"healthy\": true}\n",
                b"\n",
            ],
        )

        with mock.patch("engine.integrations.opencode.client.request.urlopen", return_value=response):
            events = list(self.client.stream_events())

        self.assertEqual(events[0]["type"], "server.connected")
        self.assertEqual(events[0]["id"], "evt_1")
        self.assertEqual(events[0]["properties"]["healthy"], True)

    def test_http_errors_raise_opencode_http_error(self) -> None:
        http_error = error.HTTPError(
            url="http://127.0.0.1:4310/session",
            code=403,
            msg="Forbidden",
            hdrs=None,
            fp=_FakeHTTPResponse(b'{"error":"forbidden"}'),
        )

        with mock.patch("engine.integrations.opencode.client.request.urlopen", side_effect=http_error):
            with self.assertRaises(OpenCodeHTTPError) as exc:
                self.client.list_sessions()

        self.assertIn("HTTP 403", str(exc.exception))

    def test_export_transcript_writes_requested_output_and_artifact_copy(self) -> None:
        def fake_urlopen(req, timeout=None):
            return _FakeHTTPResponse(json.dumps([{"info": {"id": "msg_1"}, "parts": []}]).encode("utf-8"))

        out_path = self.project_root / "artifacts" / "exports" / "session_transcript.json"
        with mock.patch("engine.integrations.opencode.client.request.urlopen", side_effect=fake_urlopen):
            written = self.client.export_transcript("sess_1", out_path)

        self.assertEqual(written, out_path)
        self.assertTrue(out_path.exists())
        session_copy = self.project_root / "artifacts" / "opencode" / "sessions" / "sess_1" / "transcript.json"
        self.assertTrue(session_copy.exists())


if __name__ == "__main__":
    unittest.main()
