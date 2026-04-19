from __future__ import annotations

import pyray as rl

from engine.agent import AgentActionStatus, AgentPermissionMode, AgentSessionService, EditorLiveAgentEnginePort
from engine.project.project_service import ProjectService


class AgentPanel:
    """Simple visual shell for the experimental engine-native agent."""

    TOOLBAR_HEIGHT = 28
    INPUT_HEIGHT = 26
    UNITY_BG = rl.Color(30, 30, 30, 255)
    UNITY_HEADER = rl.Color(42, 42, 42, 255)
    UNITY_BORDER = rl.Color(25, 25, 25, 255)
    UNITY_TEXT = rl.Color(205, 205, 205, 255)
    UNITY_TEXT_DIM = rl.Color(135, 135, 135, 255)
    UNITY_BLUE = rl.Color(44, 93, 135, 255)
    UNITY_WARN = rl.Color(205, 133, 63, 255)

    def __init__(self) -> None:
        self.project_service: ProjectService | None = None
        self.live_game = None
        self.live_scene_manager = None
        self.agent_service: AgentSessionService | None = None
        self.session_id = ""
        self.permission_mode = AgentPermissionMode.CONFIRM_ACTIONS
        self.input_text = ""
        self.has_focus = False
        self.status_text = "No active project"
        self.preview_action_id = ""
        self.pending_login_provider = ""
        self.login_input_text = ""
        self.login_has_focus = False
        self.live_port_connected = False
        self._binding_key: tuple[str, int, int] | None = None
        self.content_rect = rl.Rectangle(0, 0, 0, 0)
        self.input_rect = rl.Rectangle(0, 0, 0, 0)

    def set_project_service(self, project_service: ProjectService | None) -> None:
        self.project_service = project_service
        if project_service is None or not project_service.has_project:
            self.agent_service = None
            self.session_id = ""
            self._binding_key = None
            self.status_text = "No active project"
            return
        self._restart_project_session()

    def set_live_engine(self, *, game=None, scene_manager=None, project_service: ProjectService | None = None) -> None:
        self.live_game = game
        self.live_scene_manager = scene_manager
        if project_service is not None:
            self.project_service = project_service
        if self.project_service is not None and self.project_service.has_project:
            self._restart_project_session()

    def _restart_project_session(self) -> None:
        if self.project_service is None or not self.project_service.has_project:
            self.agent_service = None
            self.session_id = ""
            self._binding_key = None
            self.live_port_connected = False
            self.status_text = "No active project"
            return
        binding_key = (
            self.project_service.project_root_display.as_posix(),
            id(self.live_game),
            id(self.live_scene_manager),
        )
        if self._binding_key == binding_key and self.agent_service is not None and self.session_id:
            return
        if self.agent_service is not None and self.session_id:
            try:
                self.agent_service.cancel_session(self.session_id)
            except Exception:
                pass
        self._binding_key = binding_key
        engine_port = None
        if self.live_game is not None and self.live_scene_manager is not None:
            engine_port = EditorLiveAgentEnginePort(
                game=self.live_game,
                scene_manager=self.live_scene_manager,
                project_service=self.project_service,
            )
        self.live_port_connected = engine_port is not None
        self.agent_service = AgentSessionService(
            project_root=self.project_service.project_root_display,
            engine_port=engine_port,
        )
        provider_id = "fake"
        model = ""
        stream = False
        try:
            status = self.agent_service.get_provider_status()
            provider_id = str(status.get("default_provider_id", "fake") or "fake")
            settings = dict(status.get("settings", {}))
            model = str(settings.get("model", ""))
            stream = bool(settings.get("stream", False))
            if provider_id != "fake":
                selected = self.agent_service.get_provider_status(provider_id)
                if selected.get("auth_status") == "missing":
                    provider_id = "fake"
                    model = ""
                    stream = False
        except Exception:
            provider_id = "fake"
        session = self.agent_service.create_session(
            permission_mode=self.permission_mode.value,
            title="Editor Agent",
            provider_id=provider_id,
            model=model,
            stream=stream,
        )
        self.session_id = str(session["session_id"])
        project_name = self.project_service.project_name if self.project_service.has_project else "project"
        self.status_text = f"Agent ready: {project_name}"

    def set_agent_service(self, service: AgentSessionService | None) -> None:
        self.agent_service = service
        self.session_id = ""
        self._binding_key = None
        if service is not None:
            session = service.create_session(permission_mode=self.permission_mode.value, title="Editor Agent")
            self.session_id = str(session["session_id"])
            self.status_text = "Agent ready"

    def shutdown(self) -> None:
        if self.agent_service is not None and self.session_id:
            try:
                self.agent_service.cancel_session(self.session_id)
            except Exception:
                pass
        self.status_text = "Agent stopped"

    def captures_keyboard(self) -> bool:
        return self.has_focus

    def update_input(self, active: bool) -> None:
        if not active:
            return
        mouse = rl.get_mouse_position()
        if rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
            self.has_focus = rl.check_collision_point_rec(mouse, self.input_rect)
        if not self.has_focus:
            return
        target = "login" if self.pending_login_provider else "chat"
        if rl.is_key_down(rl.KEY_LEFT_CONTROL) or rl.is_key_down(rl.KEY_RIGHT_CONTROL):
            if rl.is_key_pressed(rl.KEY_C):
                text_to_copy = self.login_input_text if target == "login" else self.input_text
                rl.set_clipboard_text(text_to_copy)
            elif rl.is_key_pressed(rl.KEY_V):
                clipboard_content = rl.get_clipboard_text()
                if clipboard_content:
                    if target == "login" and len(self.login_input_text) + len(clipboard_content) <= 2000:
                        self.login_input_text += clipboard_content
                    elif target == "chat" and len(self.input_text) + len(clipboard_content) <= 1000:
                        self.input_text += clipboard_content
        if rl.is_key_pressed(rl.KEY_BACKSPACE):
            if target == "login" and self.login_input_text:
                self.login_input_text = self.login_input_text[:-1]
            elif target == "chat" and self.input_text:
                self.input_text = self.input_text[:-1]
        while True:
            codepoint = rl.get_char_pressed()
            if codepoint == 0:
                break
            if codepoint in (10, 13):
                continue
            try:
                char = chr(codepoint)
            except ValueError:
                continue
            if char.isprintable():
                if target == "login" and len(self.login_input_text) < 2000:
                    self.login_input_text += char
                elif target == "chat" and len(self.input_text) < 1000:
                    self.input_text += char
        if rl.is_key_pressed(rl.KEY_ENTER) or rl.is_key_pressed(rl.KEY_KP_ENTER):
            self._send_current_input()

    def render(self, x: int, y: int, width: int, height: int) -> None:
        toolbar = rl.Rectangle(float(x), float(y), float(width), float(self.TOOLBAR_HEIGHT))
        self.content_rect = rl.Rectangle(
            float(x),
            float(y + self.TOOLBAR_HEIGHT),
            float(width),
            float(max(0, height - self.TOOLBAR_HEIGHT - self.INPUT_HEIGHT)),
        )
        self.input_rect = rl.Rectangle(
            float(x + 6),
            float(y + height - self.INPUT_HEIGHT + 3),
            float(max(0, width - 12)),
            float(self.INPUT_HEIGHT - 6),
        )

        rl.draw_rectangle_rec(toolbar, self.UNITY_HEADER)
        rl.draw_text("Agent", x + 8, y + 8, 10, self.UNITY_TEXT)
        mode_rect = rl.Rectangle(float(x + 64), float(y + 4), 152.0, 20.0)
        mode_label = "Confirmar acciones" if self.permission_mode == AgentPermissionMode.CONFIRM_ACTIONS else "Acceso completo"
        if rl.gui_button(mode_rect, mode_label):
            self.permission_mode = (
                AgentPermissionMode.FULL_ACCESS
                if self.permission_mode == AgentPermissionMode.CONFIRM_ACTIONS
                else AgentPermissionMode.CONFIRM_ACTIONS
            )
            self._send_text(f"/permissions {self.permission_mode.value}")
        stop_rect = rl.Rectangle(float(x + 224), float(y + 4), 52.0, 20.0)
        if rl.gui_button(stop_rect, "Stop") and self.agent_service is not None and self.session_id:
            self.agent_service.cancel_session(self.session_id)
            self.status_text = "Agent stopped"
        rl.draw_text(self.status_text, x + 290, y + 8, 10, self.UNITY_TEXT_DIM)

        rl.draw_rectangle_rec(self.content_rect, self.UNITY_BG)
        rl.draw_rectangle_lines_ex(self.content_rect, 1, self.UNITY_BORDER)
        self._draw_session_content()

        rl.draw_rectangle_rec(self.input_rect, rl.Color(38, 38, 38, 255))
        rl.draw_rectangle_lines_ex(self.input_rect, 1, self.UNITY_BLUE if self.has_focus else self.UNITY_BORDER)
        if self.pending_login_provider:
            display = "*" * min(len(self.login_input_text), 160) if self.login_input_text else f"Paste API key for {self.pending_login_provider}..."
        else:
            display = self.input_text if self.input_text else "Ask the engine agent..."
        color = self.UNITY_TEXT if (self.login_input_text if self.pending_login_provider else self.input_text) else self.UNITY_TEXT_DIM
        rl.draw_text(display[-160:], int(self.input_rect.x + 6), int(self.input_rect.y + 7), 10, color)

    def _draw_session_content(self) -> None:
        if self.agent_service is None or not self.session_id:
            rl.draw_text(
                "Open a project to start an agent session.",
                int(self.content_rect.x + 8),
                int(self.content_rect.y + 10),
                10,
                self.UNITY_TEXT_DIM,
            )
            return
        try:
            session = self.agent_service.get_session(self.session_id)
        except Exception as exc:
            rl.draw_text(f"Agent unavailable: {exc}", int(self.content_rect.x + 8), int(self.content_rect.y + 10), 10, self.UNITY_WARN)
            return

        line_y = int(self.content_rect.y + 8)
        if self.project_service is not None and self.project_service.has_project:
            live_label = "live engine" if self.live_port_connected else "file tools only"
            rl.draw_text(
                f"Proyecto: {self.project_service.project_name} ({live_label})",
                int(self.content_rect.x + 8),
                line_y,
                10,
                self.UNITY_TEXT_DIM,
            )
            line_y += 16
        if self.pending_login_provider:
            rl.draw_text(
                f"Secure login: {self.pending_login_provider}. Press Enter after pasting API key.",
                int(self.content_rect.x + 8),
                line_y,
                10,
                self.UNITY_WARN,
            )
            line_y += 16
        messages = session.get("messages", [])[-8:]
        for message in messages:
            role = str(message.get("role", ""))
            content = str(message.get("content", "")).replace("\n", " ")[:180]
            rl.draw_text(f"{role}: {content}", int(self.content_rect.x + 8), line_y, 10, self.UNITY_TEXT)
            line_y += 16

        provider = dict(session.get("provider_metadata", {}))
        provider_id = str(provider.get("provider_id", session.get("provider_id", "fake")))
        provider_kind = str(provider.get("provider_kind", "unknown"))
        auth_status = str(provider.get("auth_status", ""))
        test_label = " test/offline" if provider.get("test_only") else ""
        rl.draw_text(
            f"Proveedor: {provider_id} ({provider_kind}{test_label}) auth={auth_status or 'n/a'}",
            int(self.content_rect.x + 8),
            line_y,
            10,
            self.UNITY_TEXT_DIM,
        )
        line_y += 18
        events = session.get("events", [])
        if events:
            last_event = str(events[-1].get("kind", ""))
            if last_event in {"assistant_delta", "provider_stream_started", "provider_stream_completed", "provider_stream_failed"}:
                rl.draw_text(f"Streaming: {last_event}", int(self.content_rect.x + 8), line_y, 10, self.UNITY_TEXT_DIM)
                line_y += 16
        usage = session.get("usage_records", [])
        if usage:
            total_tokens = sum(int(item.get("total_tokens") or 0) for item in usage if isinstance(item, dict))
            rl.draw_text(f"Tokens: {total_tokens} (coste: unknown)", int(self.content_rect.x + 8), line_y, 10, self.UNITY_TEXT_DIM)
            line_y += 16

        pending = [action for action in session.get("pending_actions", []) if action.get("status") == AgentActionStatus.PENDING.value]
        for action in pending[:3]:
            if line_y + 26 > self.content_rect.y + self.content_rect.height:
                break
            action_id = str(action.get("action_id", ""))
            tool = str(action.get("tool_call", {}).get("tool_name", "tool"))
            rl.draw_text(f"Pending: {tool}", int(self.content_rect.x + 8), line_y, 10, self.UNITY_WARN)
            diff_rect = rl.Rectangle(self.content_rect.x + self.content_rect.width - 210, float(line_y - 3), 68.0, 20.0)
            approve_rect = rl.Rectangle(self.content_rect.x + self.content_rect.width - 138, float(line_y - 3), 62.0, 20.0)
            reject_rect = rl.Rectangle(self.content_rect.x + self.content_rect.width - 70, float(line_y - 3), 62.0, 20.0)
            if rl.gui_button(diff_rect, "View diff"):
                self.preview_action_id = "" if self.preview_action_id == action_id else action_id
            if rl.gui_button(approve_rect, "Approve"):
                self.agent_service.approve_action(self.session_id, action_id, True)
            if rl.gui_button(reject_rect, "Reject"):
                self.agent_service.approve_action(self.session_id, action_id, False)
            line_y += 24
            if self.preview_action_id == action_id:
                preview = str(action.get("preview", "")).splitlines()
                for preview_line in preview[:6]:
                    if line_y + 14 > self.content_rect.y + self.content_rect.height:
                        break
                    rl.draw_text(preview_line[:190], int(self.content_rect.x + 18), line_y, 10, self.UNITY_TEXT_DIM)
                    line_y += 14

    def _send_current_input(self) -> None:
        if self.pending_login_provider:
            self._complete_login()
            return
        text = self.input_text.strip()
        if not text:
            return
        self.input_text = ""
        self._send_text(text)

    def _send_text(self, text: str) -> None:
        if self.agent_service is None or not self.session_id:
            self.status_text = "No active project"
            return
        try:
            result = self.agent_service.send_message(self.session_id, text)
            command_result = dict(result.get("command_result", {})) if isinstance(result, dict) else {}
            if command_result.get("action") == "open_login":
                self.pending_login_provider = str(command_result.get("provider_id", "opencode-go"))
                self.login_input_text = ""
                self.status_text = str(command_result.get("message", "Enter API key."))
            elif command_result:
                self.status_text = str(command_result.get("message", "Agent command processed"))
            else:
                self.status_text = "Agent ready"
        except Exception as exc:
            self.status_text = f"Agent error: {exc}"

    def _complete_login(self) -> None:
        if self.agent_service is None or not self.pending_login_provider:
            return
        api_key = self.login_input_text.strip()
        provider_id = self.pending_login_provider
        self.login_input_text = ""
        self.pending_login_provider = ""
        if not api_key:
            self.status_text = "Login cancelled"
            return
        try:
            result = self.agent_service.login_provider(provider_id, api_key=api_key)
            self.status_text = str(result.get("message", "Provider configured"))
            self._binding_key = None
            self._restart_project_session()
        except Exception as exc:
            self.status_text = f"Login failed: {exc}"
