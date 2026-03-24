from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Any, Dict, List

import pyray as rl


class OpenCodePanel:
    HEADER_HEIGHT = 54
    ACTION_HEIGHT = 30
    COMPOSER_HEIGHT = 112
    CARD_GAP = 8
    CARD_PADDING = 8
    MIN_LEFT_COL = 220
    TWO_COL_THRESHOLD = 760

    BG = rl.Color(32, 32, 32, 255)
    BG_MID = rl.Color(42, 42, 42, 255)
    BG_LIGHT = rl.Color(52, 52, 52, 255)
    BG_CARD = rl.Color(36, 36, 36, 255)
    BORDER = rl.Color(25, 25, 25, 255)
    TEXT = rl.Color(220, 220, 220, 255)
    TEXT_DIM = rl.Color(150, 150, 150, 255)
    TEXT_MUTED = rl.Color(124, 124, 124, 255)
    ACTIVE = rl.Color(44, 93, 135, 255)
    SUCCESS = rl.Color(116, 188, 126, 255)
    WARNING = rl.Color(220, 170, 90, 255)
    DANGER = rl.Color(200, 90, 90, 255)
    USER = rl.Color(102, 168, 224, 255)
    ASSISTANT = rl.Color(136, 210, 136, 255)
    SYSTEM = rl.Color(220, 190, 120, 255)

    def __init__(self) -> None:
        self.bridge = None
        self.sessions: List[Dict[str, Any]] = []
        self.messages: List[Dict[str, Any]] = []
        self.diff: List[Dict[str, Any]] = []
        self.approvals: List[Dict[str, Any]] = []
        self.selected_session_id: str = ""
        self.selected_permission_id: str = ""
        self.composer_text: str = ""
        self.composer_focused: bool = False
        self.agent_mode: str = "plan"
        self.status_line: str = "idle"
        self.last_refresh_label: str = ""
        self.last_request_label: str = ""
        self.last_artifacts: Dict[str, str] = {}
        self.connection_status: Dict[str, Any] = {}
        self.poll_enabled: bool = True
        self.poll_interval_seconds: float = 1.5
        self.auto_start_on_open: bool = True
        self.is_minimized: bool = False
        self._last_poll_time: float = 0.0
        self._auto_start_attempted: bool = False
        self._sessions_scroll: float = 0.0
        self._content_scroll: float = 0.0
        self._worker_thread: threading.Thread | None = None
        self._worker_lock = threading.Lock()
        self._worker_pending: Dict[str, Any] | None = None
        self._worker_result: Dict[str, Any] | None = None
        self._busy_label: str = ""

    def set_bridge(self, bridge: Any) -> None:
        self.bridge = bridge
        self.sessions = []
        self.messages = []
        self.diff = []
        self.approvals = []
        self.selected_session_id = ""
        self.selected_permission_id = ""
        self.composer_text = ""
        self.composer_focused = False
        self.status_line = "idle"
        self.last_refresh_label = ""
        self.last_request_label = ""
        self.last_artifacts = {}
        self.connection_status = {}
        self._auto_start_attempted = False
        if self.bridge is not None:
            self.refresh_overview()

    def update(self, rect: rl.Rectangle) -> None:
        self._consume_worker_result()
        if self.bridge is None or rect.width <= 0 or rect.height <= 0:
            return
        if self.is_minimized:
            self.composer_focused = False
            return

        layout = self._compute_layout(rect)
        mouse = rl.get_mouse_position()
        if rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
            self.composer_focused = rl.check_collision_point_rec(mouse, layout["composer_input"])

        if rl.check_collision_point_rec(mouse, layout["sessions_list"]):
            self._sessions_scroll = max(0.0, self._sessions_scroll - rl.get_mouse_wheel_move() * 24)
        elif rl.check_collision_point_rec(mouse, layout["content_scroll"]):
            self._content_scroll = max(0.0, self._content_scroll - rl.get_mouse_wheel_move() * 24)

        if self.poll_enabled and self.selected_session_id and not self._is_busy():
            now = time.time()
            if now - self._last_poll_time >= self.poll_interval_seconds:
                self.refresh_selected_session()

        if self.composer_focused:
            self._handle_text_input()

    def render(self, x: int, y: int, width: int, height: int) -> None:
        rect = rl.Rectangle(float(x), float(y), float(width), float(height))
        rl.draw_rectangle_rec(rect, self.BG)
        rl.draw_line(int(rect.x), int(rect.y), int(rect.x), int(rect.y + rect.height), self.BORDER)
        if self.is_minimized:
            self._draw_minimized(rect)
            return

        layout = self._compute_layout(rect)
        self._draw_header(layout)
        self._draw_action_bar(layout)
        self._draw_session_column(layout)
        self._draw_main_column(layout)
        self._draw_composer(layout)

    def render_bottom_summary(self, x: int, y: int, width: int, height: int) -> None:
        rect = rl.Rectangle(float(x), float(y), float(width), float(height))
        rl.draw_rectangle_rec(rect, self.BG)
        rl.draw_rectangle_lines_ex(rect, 1, self.BORDER)
        self._draw_text_block("OpenCode moved to the right rail", rect.x + 12, rect.y + 10, rect.width - 24, 16, self.TEXT, max_lines=1)
        self._draw_text_block("Use the right panel for sessions, activity, approvals, diff and artifacts.", rect.x + 12, rect.y + 34, rect.width - 24, 10, self.TEXT_DIM, max_lines=2)
        summary = self._connection_summary()
        self._draw_text_block(summary, rect.x + 12, rect.y + 70, rect.width - 24, 10, self.TEXT_DIM, max_lines=2)

    def refresh_overview(self) -> None:
        if self.bridge is None or self._is_busy():
            return
        self._start_background_call("Refreshing OpenCode...", self.bridge.load_initial_state)

    def refresh_selected_session(self) -> None:
        if self.bridge is None or not self.selected_session_id or self._is_busy():
            return
        self._last_poll_time = time.time()
        self._start_background_call("Refreshing session...", self.bridge.select_session, session_id=self.selected_session_id, limit=100)

    def refresh_connection(self) -> None:
        if self.bridge is None or self._is_busy():
            return
        self._start_background_call("Connecting...", self.bridge.connect)

    def start_visible(self) -> None:
        if self.bridge is None or self._is_busy():
            return
        launcher = getattr(self.bridge, "start_visible", None)
        if callable(launcher):
            self._start_background_call("Opening OpenCode...", launcher)
            return
        self._start_background_call("Starting backend...", self.bridge.ensure_server)

    def create_session(self, title: str = "") -> None:
        if self.bridge is None or self._is_busy():
            return
        default_title = title or f"OpenCode {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        self._start_background_call("Creating session...", self.bridge.create_and_select_session, title=default_title)

    def send_prompt(self) -> None:
        text = self.composer_text.strip()
        healthy = bool(self.connection_status.get("healthy", False))
        if self.bridge is None or not healthy or not text or self._is_busy():
            return
        self._start_background_call(
            "Sending prompt...",
            self.bridge.send_prompt,
            session_id=self.selected_session_id,
            text=text,
            agent=self.agent_mode,
        )

    def export_selected_diff(self) -> None:
        if self.bridge is None or not self.selected_session_id or self._is_busy():
            return
        self._start_background_call("Exporting diff...", self.bridge.export_diff_artifact, session_id=self.selected_session_id)

    def export_selected_messages(self) -> None:
        if self.bridge is None or not self.selected_session_id or self._is_busy():
            return
        self._start_background_call("Exporting transcript...", self.bridge.export_messages_artifact, session_id=self.selected_session_id, limit=100)

    def respond_to_selected_permission(self, response: str) -> None:
        if self.bridge is None or not self.selected_session_id or not self.selected_permission_id or self._is_busy():
            return
        self._start_background_call(
            f"{response.title()} permission...",
            self.bridge.respond_permission,
            session_id=self.selected_session_id,
            permission_id=self.selected_permission_id,
            response=response,
        )

    def toggle_minimized(self) -> None:
        self.is_minimized = not self.is_minimized
        if self.is_minimized:
            self.composer_focused = False

    def _draw_minimized(self, rect: rl.Rectangle) -> None:
        header = rl.Rectangle(rect.x, rect.y, rect.width, min(78.0, rect.height))
        rl.draw_rectangle_rec(header, self.BG_MID)
        rl.draw_rectangle_lines_ex(header, 1, self.BORDER)
        self._draw_text_block("OpenCode", header.x + 6, header.y + 8, header.width - 12, 12, self.TEXT, max_lines=1)
        self._draw_text_block(self.status_line, header.x + 6, header.y + 26, header.width - 12, 9, self.TEXT_DIM, max_lines=1)
        label = ">" if header.width < 64 else "Open"
        if self._draw_button(rl.Rectangle(header.x + 6, header.y + header.height - 24, max(28.0, header.width - 12), 18), label):
            self.toggle_minimized()

    def _draw_header(self, layout: Dict[str, rl.Rectangle]) -> None:
        rect = layout["header"]
        rl.draw_rectangle_rec(rect, self.BG_MID)
        rl.draw_line(int(rect.x), int(rect.y + rect.height - 1), int(rect.x + rect.width), int(rect.y + rect.height - 1), self.BORDER)
        self._draw_text_block("OpenCode", rect.x + self.CARD_PADDING, rect.y + 8, rect.width * 0.55, 18, self.TEXT, max_lines=1)
        self._draw_text_block(self._header_subtitle(), rect.x + self.CARD_PADDING, rect.y + 29, rect.width * 0.55, 10, self.TEXT_DIM, max_lines=2)

        action_y = rect.y + 8
        right = rect.x + rect.width - self.CARD_PADDING
        for key, label in reversed(self._header_actions()):
            button_w = max(48.0, self._measure_text(label, 10) + 16.0)
            button_rect = rl.Rectangle(right - button_w, action_y, button_w, 20.0)
            clicked = self._draw_button(button_rect, label, disabled=self._is_busy() and key != "minimize")
            right = button_rect.x - 6
            if clicked:
                self._dispatch_header_action(key)

    def _draw_action_bar(self, layout: Dict[str, rl.Rectangle]) -> None:
        rect = layout["action_bar"]
        rl.draw_rectangle_rec(rect, self.BG)
        rl.draw_line(int(rect.x), int(rect.y + rect.height - 1), int(rect.x + rect.width), int(rect.y + rect.height - 1), self.BORDER)
        x = rect.x + self.CARD_PADDING
        y = rect.y + 5
        row_h = 22.0
        for key, label, active, disabled in self._toolbar_actions():
            button_w = max(42.0, self._measure_text(label, 10) + 18.0)
            if x + button_w > rect.x + rect.width - self.CARD_PADDING:
                x = rect.x + self.CARD_PADDING
                y += row_h + 4
            if self._draw_button(rl.Rectangle(x, y, button_w, row_h), label, active=active, disabled=disabled):
                self._dispatch_toolbar_action(key)
            x += button_w + 6

    def _draw_session_column(self, layout: Dict[str, rl.Rectangle]) -> None:
        card = layout["session_card"]
        self._draw_card(card, "Session", "Sesion activa y lista de sesiones")

        summary_rect = rl.Rectangle(card.x + self.CARD_PADDING, card.y + 30, card.width - self.CARD_PADDING * 2, 70)
        session_title = self._selected_session_title()
        summary_lines = [
            f"Estado: {self.status_line}",
            f"Sesion: {session_title}",
            f"Modo: {self.agent_mode}",
            f"Server: {self._status_chip_label()}",
        ]
        self._draw_lines(summary_lines, summary_rect.x, summary_rect.y, summary_rect.width, 10, self.TEXT, max_lines=4)

        list_rect = layout["sessions_list"]
        rl.draw_rectangle_rec(list_rect, self.BG_LIGHT)
        rl.draw_rectangle_lines_ex(list_rect, 1, self.BORDER)
        rl.begin_scissor_mode(int(list_rect.x), int(list_rect.y), int(list_rect.width), int(list_rect.height))
        try:
            if not self.sessions:
                self._draw_placeholder(list_rect, "No sessions available", "Crea una sesion nueva o revisa la conexion.")
            else:
                cursor_y = int(list_rect.y + 6 - self._sessions_scroll)
                for session in self.sessions:
                    cursor_y = self._draw_session_row(list_rect, cursor_y, session)
        finally:
            rl.end_scissor_mode()

    def _draw_main_column(self, layout: Dict[str, rl.Rectangle]) -> None:
        scroll_rect = layout["content_scroll"]
        rl.begin_scissor_mode(int(scroll_rect.x), int(scroll_rect.y), int(scroll_rect.width), int(scroll_rect.height))
        try:
            y = scroll_rect.y + self.CARD_GAP - self._content_scroll
            y = self._draw_activity_card(layout["content_col"], y)
            y = self._draw_conversation_card(layout["content_col"], y)
            y = self._draw_approvals_card(layout["content_col"], y)
            y = self._draw_diff_card(layout["content_col"], y)
            self._draw_artifacts_card(layout["content_col"], y)
        finally:
            rl.end_scissor_mode()

    def _draw_composer(self, layout: Dict[str, rl.Rectangle]) -> None:
        rect = layout["composer"]
        self._draw_card(rect, "Prompt", "Composer de mensajes")
        input_rect = layout["composer_input"]
        rl.draw_rectangle_rec(input_rect, self.BG_LIGHT)
        rl.draw_rectangle_lines_ex(input_rect, 1, self.ACTIVE if self.composer_focused else self.BORDER)
        healthy = bool(self.connection_status.get("healthy", False))
        if not healthy:
            preview = "Esperando conexion con OpenCode."
        elif not self.selected_session_id:
            preview = "Escribe un prompt. Si no hay sesion activa, el panel creara una automaticamente."
        elif self.composer_text:
            preview = self.composer_text
        else:
            preview = "Escribe un prompt. Enter envia, Shift+Enter anade salto."
        lines = self._wrap_preserving_newlines(preview, input_rect.width - 12, 10)
        self._draw_lines(lines, input_rect.x + 6, input_rect.y + 6, input_rect.width - 12, 10, self.TEXT if self.composer_text else self.TEXT_DIM, max_lines=4)
        footer = f"Agent: {self.agent_mode} | Session: {self._selected_session_short()}"
        self._draw_text_block(footer, rect.x + self.CARD_PADDING, rect.y + rect.height - 24, rect.width - 96, 10, self.TEXT_DIM, max_lines=1)
        send_rect = rl.Rectangle(rect.x + rect.width - 74, rect.y + rect.height - 30, 66, 22)
        if self._draw_button(send_rect, "Send", active=bool(self.composer_text.strip()), disabled=self._is_busy() or not healthy or not self.composer_text.strip()):
            self.send_prompt()

    def _draw_activity_card(self, column: rl.Rectangle, y: float) -> float:
        status = self.connection_status
        detail_lines = self._activity_lines()
        height = max(110.0, 36.0 + len(detail_lines) * 14.0)
        rect = rl.Rectangle(column.x, y, column.width, height)
        self._draw_card(rect, "Activity", self._activity_subtitle())
        color = self._status_chip_color()
        chip = rl.Rectangle(rect.x + rect.width - 102, rect.y + 8, 90, 18)
        rl.draw_rectangle_rec(chip, color)
        self._draw_text_block(self._status_chip_label(), chip.x + 6, chip.y + 4, chip.width - 12, 9, self.TEXT, max_lines=1)
        self._draw_lines(detail_lines, rect.x + self.CARD_PADDING, rect.y + 34, rect.width - self.CARD_PADDING * 2, 10, self.TEXT, max_lines=8)
        if status and not status.get("healthy", False):
            self._draw_lines([status.get("action_hint", "")], rect.x + self.CARD_PADDING, rect.y + rect.height - 18, rect.width - self.CARD_PADDING * 2, 9, self.WARNING, max_lines=1)
        return rect.y + rect.height + self.CARD_GAP

    def _draw_conversation_card(self, column: rl.Rectangle, y: float) -> float:
        lines = self._conversation_lines()
        height = max(132.0, 38.0 + len(lines[:8]) * 13.0)
        rect = rl.Rectangle(column.x, y, column.width, height)
        self._draw_card(rect, "Conversation", f"{len(self.messages)} message(s)")
        if not self.messages:
            self._draw_placeholder(rect, "No session selected", "Selecciona una sesion para ver mensajes.")
        else:
            self._draw_lines(lines, rect.x + self.CARD_PADDING, rect.y + 34, rect.width - self.CARD_PADDING * 2, 10, self.TEXT, max_lines=8)
        return rect.y + rect.height + self.CARD_GAP

    def _draw_approvals_card(self, column: rl.Rectangle, y: float) -> float:
        rows = max(1, min(4, len(self.approvals)))
        extra = 30.0 if self.selected_permission_id else 0.0
        rect = rl.Rectangle(column.x, y, column.width, 56.0 + rows * 26.0 + extra)
        self._draw_card(rect, "Approvals", "Permisos pendientes")
        if not self.approvals:
            self._draw_placeholder(rect, "No approvals pending", "El backend no ha pedido aprobaciones.")
            return rect.y + rect.height + self.CARD_GAP

        current_y = rect.y + 34
        for approval in self.approvals[:4]:
            current_y = self._draw_approval_row(rect, current_y, approval)
        if self.selected_permission_id:
            allow_rect = rl.Rectangle(rect.x + self.CARD_PADDING, rect.y + rect.height - 28, 58, 20)
            deny_rect = rl.Rectangle(rect.x + self.CARD_PADDING + 64, rect.y + rect.height - 28, 52, 20)
            if self._draw_button(allow_rect, "Allow", disabled=self._is_busy()):
                self.respond_to_selected_permission("allow")
            if self._draw_button(deny_rect, "Deny", disabled=self._is_busy()):
                self.respond_to_selected_permission("deny")
        return rect.y + rect.height + self.CARD_GAP

    def _draw_diff_card(self, column: rl.Rectangle, y: float) -> float:
        lines = self._diff_lines()
        rect = rl.Rectangle(column.x, y, column.width, max(86.0, 40.0 + len(lines[:6]) * 13.0))
        self._draw_card(rect, "Diff", "Cambios disponibles")
        if not self.diff:
            self._draw_placeholder(rect, "No diff available", "Todavia no hay diff exportado para esta sesion.")
        else:
            self._draw_lines(lines, rect.x + self.CARD_PADDING, rect.y + 34, rect.width - self.CARD_PADDING * 2, 10, self.TEXT, max_lines=6)
        return rect.y + rect.height + self.CARD_GAP

    def _draw_artifacts_card(self, column: rl.Rectangle, y: float) -> float:
        lines = self._artifact_lines()
        rect = rl.Rectangle(column.x, y, column.width, max(86.0, 40.0 + len(lines[:6]) * 13.0))
        self._draw_card(rect, "Artifacts", "Rutas exportadas")
        if not self.last_artifacts:
            self._draw_placeholder(rect, "No artifacts yet", "Exporta transcript o diff para generar artifacts.")
        else:
            self._draw_lines(lines, rect.x + self.CARD_PADDING, rect.y + 34, rect.width - self.CARD_PADDING * 2, 10, self.TEXT, max_lines=6)
        return rect.y + rect.height + self.CARD_GAP

    def _draw_card(self, rect: rl.Rectangle, title: str, subtitle: str) -> None:
        rl.draw_rectangle_rec(rect, self.BG_CARD)
        rl.draw_rectangle_lines_ex(rect, 1, self.BORDER)
        self._draw_text_block(title, rect.x + self.CARD_PADDING, rect.y + 8, rect.width - self.CARD_PADDING * 2, 11, self.TEXT, max_lines=1)
        self._draw_text_block(subtitle, rect.x + self.CARD_PADDING, rect.y + 21, rect.width - self.CARD_PADDING * 2, 9, self.TEXT_MUTED, max_lines=1)

    def _draw_placeholder(self, rect: rl.Rectangle, title: str, subtitle: str) -> None:
        self._draw_text_block(title, rect.x + self.CARD_PADDING, rect.y + 38, rect.width - self.CARD_PADDING * 2, 10, self.TEXT_DIM, max_lines=2)
        self._draw_text_block(subtitle, rect.x + self.CARD_PADDING, rect.y + 54, rect.width - self.CARD_PADDING * 2, 9, self.TEXT_MUTED, max_lines=3)

    def _draw_session_row(self, list_rect: rl.Rectangle, cursor_y: int, session: Dict[str, Any]) -> int:
        session_id = str(session.get("id", "") or "")
        item_rect = rl.Rectangle(list_rect.x + 6, float(cursor_y), list_rect.width - 12, 52.0)
        hover = rl.check_collision_point_rec(rl.get_mouse_position(), item_rect)
        active = session_id == self.selected_session_id
        if active:
            rl.draw_rectangle_rec(item_rect, self.ACTIVE)
        elif hover:
            rl.draw_rectangle_rec(item_rect, self.BG_MID)
        if hover and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
            self.selected_session_id = session_id
            self.selected_permission_id = ""
            self.refresh_selected_session()
        self._draw_text_block(str(session.get("title", "") or session_id or "Session"), item_rect.x + 6, item_rect.y + 6, item_rect.width - 12, 10, self.TEXT, max_lines=1)
        meta = " | ".join(part for part in (str(session.get("status", "") or ""), self._format_timestamp(session.get("updatedAt", session.get("updated_at", "")))) if part)
        self._draw_text_block(session_id, item_rect.x + 6, item_rect.y + 20, item_rect.width - 12, 9, self.TEXT_DIM, max_lines=1)
        self._draw_text_block(meta, item_rect.x + 6, item_rect.y + 33, item_rect.width - 12, 8, self.TEXT_MUTED, max_lines=1)
        return cursor_y + 56

    def _draw_approval_row(self, rect: rl.Rectangle, y: float, approval: Dict[str, Any]) -> float:
        permission_id = str(approval.get("permission_id", "") or "")
        row = rl.Rectangle(rect.x + self.CARD_PADDING, y, rect.width - self.CARD_PADDING * 2, 22.0)
        hover = rl.check_collision_point_rec(rl.get_mouse_position(), row)
        active = permission_id == self.selected_permission_id
        if active:
            rl.draw_rectangle_rec(row, self.BG_MID)
        elif hover:
            rl.draw_rectangle_rec(row, self.BG_LIGHT)
        if hover and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
            self.selected_permission_id = permission_id
        label = f"{approval.get('tool', 'permission')}: {approval.get('description', approval.get('pattern', permission_id))}"
        self._draw_text_block(label, row.x + 6, row.y + 6, row.width - 12, 10, self.WARNING if active else self.TEXT, max_lines=1)
        return y + 26

    def _header_actions(self) -> List[tuple[str, str]]:
        return [("start", "Start"), ("connect", "Connect"), ("reconnect", "Reconnect"), ("new", "New"), ("minimize", "Min")]

    def _toolbar_actions(self) -> List[tuple[str, str, bool, bool]]:
        disabled = self._is_busy()
        session_required = disabled or not self.selected_session_id
        return [
            ("refresh", "Refresh", False, disabled),
            ("toggle_poll", "Poll", self.poll_enabled, False),
            ("plan", "Plan", self.agent_mode == "plan", disabled),
            ("build", "Build", self.agent_mode == "build", disabled),
            ("export_diff", "Diff out", False, session_required),
            ("export_transcript", "Transcript", False, session_required),
        ]

    def _dispatch_header_action(self, key: str) -> None:
        if key == "start":
            self.start_visible()
        elif key == "connect":
            self.refresh_connection()
        elif key == "reconnect":
            reconnect = getattr(self.bridge, "reconnect", None)
            if callable(reconnect) and not self._is_busy():
                self._start_background_call("Reconnecting...", reconnect)
            else:
                self.refresh_connection()
        elif key == "new":
            self.create_session()
        elif key == "minimize":
            self.toggle_minimized()

    def _dispatch_toolbar_action(self, key: str) -> None:
        if key == "refresh":
            self.refresh_overview()
        elif key == "toggle_poll":
            self.poll_enabled = not self.poll_enabled
        elif key == "plan":
            self.agent_mode = "plan"
        elif key == "build":
            self.agent_mode = "build"
        elif key == "export_diff":
            self.export_selected_diff()
        elif key == "export_transcript":
            self.export_selected_messages()

    def _load_overview(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "connection_status": self.bridge.get_connection_status(),
            "sessions": self.bridge.list_sessions(),
        }
        if self.selected_session_id:
            payload.update(self.bridge.refresh_session_view(self.selected_session_id, limit=100))
        return payload

    def _load_session_payload(self, session_id: str) -> Dict[str, Any]:
        payload = self.bridge.refresh_session_view(session_id, limit=100)
        payload["connection_status"] = self.bridge.get_connection_status()
        return payload

    def _create_session_payload(self, title: str) -> Dict[str, Any]:
        created = self.bridge.create_session(title=title)
        session_id = str(created.get("id", "") or "")
        payload = self._load_overview()
        payload["created_session"] = created
        if session_id:
            payload.update(self.bridge.refresh_session_view(session_id, limit=100))
        return payload

    def _send_prompt_payload(self, session_id: str, text: str, agent: str) -> Dict[str, Any]:
        manifest = self.bridge.send_message(session_id=session_id, text=text, agent=agent)
        payload = self._load_session_payload(session_id)
        payload["manifest"] = manifest
        payload["submitted_text"] = text
        return payload

    def _respond_permission_payload(self, session_id: str, permission_id: str, response: str) -> Dict[str, Any]:
        result = self.bridge.respond_permission(session_id=session_id, permission_id=permission_id, response=response, remember=False)
        payload = self._load_session_payload(session_id)
        payload["permission_result"] = result
        return payload

    def _start_background_call(self, busy_label: str, fn, **kwargs: Any) -> None:
        if self._is_busy():
            return
        self._busy_label = busy_label
        self.status_line = "working"
        with self._worker_lock:
            self._worker_pending = {"fn": fn, "kwargs": dict(kwargs)}
            self._worker_result = None
        self._worker_thread = threading.Thread(target=self._run_background_call, daemon=True)
        self._worker_thread.start()

    def _run_background_call(self) -> None:
        with self._worker_lock:
            pending = dict(self._worker_pending or {})
        if not pending:
            return
        try:
            fn = pending.get("fn")
            result = fn(**dict(pending.get("kwargs", {}) or {})) if callable(fn) else {}
        except Exception as exc:
            status = self.bridge.get_connection_status() if self.bridge is not None and hasattr(self.bridge, "get_connection_status") else {}
            result = {"__opencode_error__": str(exc), "connection_status": status}
        with self._worker_lock:
            self._worker_result = result if isinstance(result, dict) else {"result": result}

    def _consume_worker_result(self) -> None:
        with self._worker_lock:
            result = self._worker_result
            if result is None:
                return
            self._worker_result = None
        self._worker_thread = None
        self._busy_label = ""
        self.last_refresh_label = time.strftime("%H:%M:%S")

        snapshot = None
        if isinstance(result.get("snapshot"), dict):
            snapshot = dict(result.get("snapshot", {}))
        elif isinstance(result.get("sessions"), list) or "active_session_id" in result or "connection_status" in result:
            snapshot = dict(result)

        if snapshot is not None:
            self._apply_snapshot(snapshot)

        if "connection_status" in result and isinstance(result.get("connection_status"), dict):
            self.connection_status = dict(result.get("connection_status", {}))

        if "__opencode_error__" in result:
            self.status_line = "error"
            if not self.connection_status:
                self.connection_status = {
                    "healthy": False,
                    "status": "error",
                    "summary": "La solicitud fallo",
                    "technical_detail": str(result.get("__opencode_error__", "")),
                    "action_hint": "Revisa el detalle tecnico y vuelve a intentar.",
                }
            return

        if snapshot is None and "sessions" in result:
            self.sessions = [item for item in result.get("sessions", []) if isinstance(item, dict)]
        if snapshot is None and "selected_session_id" in result:
            self.selected_session_id = str(result.get("selected_session_id", "") or self.selected_session_id)
        if snapshot is None and "created_session" in result:
            self.selected_session_id = str(result.get("created_session", {}).get("id", "") or self.selected_session_id)
        if snapshot is None and "messages" in result:
            self.messages = [item for item in result.get("messages", []) if isinstance(item, dict)]
        if snapshot is None and "diff" in result:
            self.diff = [item for item in result.get("diff", []) if isinstance(item, dict)]
        if snapshot is None and "approvals" in result:
            self.approvals = [item for item in result.get("approvals", []) if isinstance(item, dict)]
            valid_ids = {str(item.get("permission_id", "") or "") for item in self.approvals}
            if self.selected_permission_id not in valid_ids:
                self.selected_permission_id = next(iter(valid_ids), "")
        if "manifest" in result:
            manifest = result.get("manifest", {})
            self.last_artifacts = {
                "artifact_dir": str(manifest.get("artifact_dir", "") or ""),
                "transcript_path": str(manifest.get("transcript_path", "") or ""),
                "diff_path": str(manifest.get("diff_path", "") or ""),
            }
            self.composer_text = ""
        if "artifact_dir" in result or "transcript_path" in result or "diff_path" in result:
            self.last_artifacts = {
                "artifact_dir": str(result.get("artifact_dir", "") or ""),
                "transcript_path": str(result.get("transcript_path", "") or ""),
                "diff_path": str(result.get("diff_path", "") or ""),
            }
            self.composer_text = ""
        if "submitted_text" in result:
            self.last_request_label = f"Prompt sent at {self.last_refresh_label}"

        state = str(self.connection_status.get("state", "") or "")
        if state == "starting":
            self.status_line = "starting"
        elif self.approvals:
            self.status_line = "waiting_permission"
        elif self.connection_status and not self.connection_status.get("healthy", False):
            self.status_line = "error"
        elif self.selected_session_id:
            self.status_line = "ready"
        else:
            self.status_line = "idle"
        self._maybe_auto_start_on_open()

    def _apply_snapshot(self, snapshot: Dict[str, Any]) -> None:
        if "connection_status" in snapshot and isinstance(snapshot.get("connection_status"), dict):
            self.connection_status = dict(snapshot.get("connection_status", {}))
        if "sessions" in snapshot:
            self.sessions = [item for item in snapshot.get("sessions", []) if isinstance(item, dict)]
        if "active_session_id" in snapshot:
            self.selected_session_id = str(snapshot.get("active_session_id", "") or self.selected_session_id)
        elif "selected_session_id" in snapshot:
            self.selected_session_id = str(snapshot.get("selected_session_id", "") or self.selected_session_id)
        if "messages" in snapshot:
            self.messages = [item for item in snapshot.get("messages", []) if isinstance(item, dict)]
        if "diff" in snapshot:
            self.diff = [item for item in snapshot.get("diff", []) if isinstance(item, dict)]
        if "approvals" in snapshot:
            self.approvals = [item for item in snapshot.get("approvals", []) if isinstance(item, dict)]
        if "last_error" in snapshot and not self.connection_status.get("technical_detail"):
            technical_detail = str(snapshot.get("last_error", "") or "")
            if technical_detail:
                self.connection_status = {
                    **self.connection_status,
                    "technical_detail": technical_detail,
                }
        if "last_operation" in snapshot and snapshot.get("last_operation"):
            self.last_request_label = str(snapshot.get("last_operation", "")).replace("_", " ")
        if "last_artifacts" in snapshot and isinstance(snapshot.get("last_artifacts"), dict):
            artifacts = dict(snapshot.get("last_artifacts", {}))
            if any(str(value or "") for value in artifacts.values()):
                self.last_artifacts = {
                    "artifact_dir": str(artifacts.get("artifact_dir", "") or ""),
                    "transcript_path": str(artifacts.get("transcript_path", "") or ""),
                    "diff_path": str(artifacts.get("diff_path", "") or ""),
                }

    def _maybe_auto_start_on_open(self) -> None:
        if not self.auto_start_on_open or self._auto_start_attempted or self.bridge is None or self._is_busy():
            return
        status = self.connection_status or {}
        if status.get("healthy", False):
            return
        state = str(status.get("state", "") or "").strip()
        if state in {"auth_error", "unavailable", "starting"}:
            return
        launcher = getattr(self.bridge, "start_visible", None)
        if not callable(launcher):
            return
        self._auto_start_attempted = True
        self._start_background_call("Opening OpenCode...", launcher)

    def _compute_layout(self, rect: rl.Rectangle) -> Dict[str, rl.Rectangle]:
        body_top = rect.y + self.HEADER_HEIGHT + self.ACTION_HEIGHT + 4
        body_height = rect.height - self.HEADER_HEIGHT - self.ACTION_HEIGHT - 4
        two_col = rect.width >= self.TWO_COL_THRESHOLD
        left_width = max(self.MIN_LEFT_COL, min(rect.width * 0.34, 280.0)) if two_col else rect.width
        content_x = rect.x + left_width + (self.CARD_GAP if two_col else 0.0)
        content_width = rect.width - left_width - (self.CARD_GAP if two_col else 0.0) if two_col else rect.width
        composer_y = rect.y + rect.height - self.COMPOSER_HEIGHT
        content_height = composer_y - body_top - self.CARD_GAP
        if not two_col:
            content_x = rect.x
            content_width = rect.width
        return {
            "header": rl.Rectangle(rect.x, rect.y, rect.width, self.HEADER_HEIGHT),
            "action_bar": rl.Rectangle(rect.x, rect.y + self.HEADER_HEIGHT, rect.width, self.ACTION_HEIGHT),
            "session_card": rl.Rectangle(rect.x, body_top, left_width, body_height if two_col else 186.0),
            "sessions_list": rl.Rectangle(rect.x + self.CARD_PADDING, body_top + 108, left_width - self.CARD_PADDING * 2, (body_height - 116) if two_col else 70.0),
            "content_col": rl.Rectangle(content_x, body_top if two_col else body_top + 194.0, content_width, content_height if two_col else max(120.0, content_height - 194.0)),
            "content_scroll": rl.Rectangle(content_x, body_top if two_col else body_top + 194.0, content_width, content_height if two_col else max(120.0, content_height - 194.0)),
            "composer": rl.Rectangle(content_x, composer_y, content_width, self.COMPOSER_HEIGHT),
            "composer_input": rl.Rectangle(content_x + self.CARD_PADDING, composer_y + 30, content_width - self.CARD_PADDING * 2, self.COMPOSER_HEIGHT - 62),
        }

    def _handle_text_input(self) -> None:
        if (rl.is_key_down(rl.KEY_LEFT_SHIFT) or rl.is_key_down(rl.KEY_RIGHT_SHIFT)) and (
            rl.is_key_pressed(rl.KEY_ENTER) or rl.is_key_pressed(rl.KEY_KP_ENTER)
        ):
            self.composer_text += "\n"
            return
        if rl.is_key_pressed(rl.KEY_ENTER) or rl.is_key_pressed(rl.KEY_KP_ENTER):
            self.send_prompt()
            return
        if rl.is_key_pressed(rl.KEY_BACKSPACE) and self.composer_text:
            self.composer_text = self.composer_text[:-1]
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
                self.composer_text += char

    def _header_subtitle(self) -> str:
        status = self._status_chip_label()
        session = self._selected_session_short()
        version = str(self.connection_status.get("version", "") or "").strip()
        details = [status]
        if version:
            details.append(version)
        details.append(self.agent_mode)
        if session != "none":
            details.append(session)
        return " | ".join(details)

    def _activity_subtitle(self) -> str:
        endpoint = str(self.connection_status.get("base_url", "") or "")
        if endpoint:
            return endpoint
        if self.last_request_label:
            return self.last_request_label
        return f"Last refresh: {self.last_refresh_label or '-'}"

    def _activity_lines(self) -> List[str]:
        status = self.connection_status or {}
        lines = [
            f"Global state: {self.status_line}",
            f"Connection: {status.get('summary', 'No conectado')}",
        ]
        if self.selected_session_id:
            lines.append(f"Active session: {self.selected_session_id}")
        if status.get("action_hint"):
            lines.append(f"Hint: {status.get('action_hint')}")
        if status.get("command"):
            lines.extend(self._wrap_preserving_newlines(f"Command: {status.get('command')}", 48, 9)[:2])
        if status.get("technical_detail"):
            lines.extend(self._wrap_preserving_newlines(str(status.get("technical_detail")), 48, 9)[:3])
        return lines

    def _conversation_lines(self) -> List[str]:
        if not self.messages:
            return []
        lines: List[str] = []
        for message in self.messages[-4:]:
            role = self._message_role(message)
            prefix = "User" if role == "user" else ("System" if role == "system" else "Agent")
            body = self._message_preview(message)
            wrapped = self._wrap_preserving_newlines(f"{prefix}: {body}", 56, 10)
            lines.extend(wrapped[:2])
        return lines

    def _diff_lines(self) -> List[str]:
        if not self.diff:
            return []
        lines: List[str] = []
        for entry in self.diff[:4]:
            label = str(entry.get("path", entry.get("file", entry.get("summary", ""))) or "")
            lines.extend(self._wrap_preserving_newlines(label, 56, 10)[:2])
        return lines

    def _artifact_lines(self) -> List[str]:
        if not self.last_artifacts:
            return []
        lines: List[str] = []
        for key in ("artifact_dir", "transcript_path", "diff_path"):
            value = str(self.last_artifacts.get(key, "") or "")
            if value:
                lines.append(f"{key.replace('_', ' ')}:")
                lines.extend(self._wrap_preserving_newlines(value, 56, 10)[:2])
        return lines

    def _message_preview(self, message: Dict[str, Any]) -> str:
        parts = message.get("parts", []) if isinstance(message, dict) else []
        preferred_text: List[str] = []
        reasoning_text: List[str] = []
        fallback_chunks: List[str] = []
        for part in parts:
            if not isinstance(part, dict):
                continue
            part_type = str(part.get("type", "") or "").lower()
            text = str(part.get("text", "") or "").strip()
            if text:
                if part_type == "text":
                    preferred_text.append(text)
                elif part_type == "reasoning":
                    reasoning_text.append(text)
                else:
                    preferred_text.append(text)
                continue
            if part_type not in {"step-start", "step-finish"}:
                fallback_chunks.append(part_type or "part")
        if preferred_text:
            return " | ".join(preferred_text)
        if reasoning_text:
            return " | ".join(reasoning_text)
        return " | ".join(fallback_chunks) if fallback_chunks else "(empty message)"

    def _message_role(self, message: Dict[str, Any]) -> str:
        info = message.get("info", {}) if isinstance(message, dict) else {}
        return str(info.get("role", info.get("type", "message")) or "message").lower()

    def _connection_summary(self) -> str:
        status = self.connection_status or {}
        summary = str(status.get("summary", "") or "No conectado")
        detail = str(status.get("technical_detail", "") or "")
        return summary if not detail else f"{summary} | {detail}"

    def _selected_session_title(self) -> str:
        for session in self.sessions:
            if str(session.get("id", "") or "") == self.selected_session_id:
                return str(session.get("title", "") or self.selected_session_id)
        return self.selected_session_id or "none"

    def _selected_session_short(self) -> str:
        return self.selected_session_id[:18] if self.selected_session_id else "none"

    def _status_chip_label(self) -> str:
        if self._is_busy():
            busy = str(self._busy_label or "").lower()
            if "opening opencode" in busy or "starting backend" in busy:
                return "starting"
            return "syncing"
        if self.approvals:
            return "waiting approval"
        status = self.connection_status or {}
        if status.get("healthy"):
            return "connected"
        status_name = str(status.get("state", status.get("status", "")) or "")
        return status_name if status_name else "disconnected"

    def _status_chip_color(self) -> rl.Color:
        label = self._status_chip_label()
        if label == "connected":
            return self.SUCCESS
        if label == "waiting approval":
            return self.WARNING
        if label in {"starting", "syncing"}:
            return self.ACTIVE
        return self.DANGER

    def _format_timestamp(self, value: Any) -> str:
        text = str(value or "").strip()
        return text.replace("T", " ")[:16] if text else ""

    def _draw_text_block(self, text: str, x: float, y: float, width: float, font_size: int, color: rl.Color, *, max_lines: int = 2) -> int:
        lines = self._wrap_preserving_newlines(str(text or ""), width, font_size)[:max_lines]
        line_height = font_size + 2
        current_y = int(y)
        for line in lines:
            rl.draw_text(line, int(x), current_y, font_size, color)
            current_y += line_height
        return current_y

    def _draw_lines(self, lines: List[str], x: float, y: float, width: float, font_size: int, color: rl.Color, *, max_lines: int = 8) -> int:
        current_y = int(y)
        drawn = 0
        for line in lines:
            for wrapped in self._wrap_preserving_newlines(line, width, font_size):
                if drawn >= max_lines:
                    return current_y
                rl.draw_text(wrapped, int(x), current_y, font_size, color)
                current_y += font_size + 3
                drawn += 1
        return current_y

    def _draw_button(self, rect: rl.Rectangle, label: str, *, active: bool = False, disabled: bool = False) -> bool:
        color = self.ACTIVE if active else rl.Color(72, 72, 72, 255)
        if disabled:
            color = rl.Color(48, 48, 48, 220)
        hover = rl.check_collision_point_rec(rl.get_mouse_position(), rect)
        if hover and not active and not disabled:
            color = rl.Color(86, 86, 86, 255)
        rl.draw_rectangle_rec(rect, color)
        rl.draw_rectangle_lines_ex(rect, 1, self.BORDER)
        self._draw_text_block(label, rect.x + 6, rect.y + 5, rect.width - 12, 10, self.TEXT if not disabled else self.TEXT_DIM, max_lines=1)
        return hover and not disabled and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT)

    def _measure_text(self, text: str, font_size: int) -> int:
        return rl.measure_text(str(text or ""), font_size)

    def _wrap_preserving_newlines(self, text: str, width: float, font_size: int) -> List[str]:
        max_width = max(12.0, width)
        raw_lines = str(text or "").replace("\r", "").split("\n")
        lines: List[str] = []
        for raw_line in raw_lines:
            words = raw_line.split() or [""]
            current = words[0]
            for word in words[1:]:
                candidate = f"{current} {word}".strip()
                if self._measure_text(candidate, font_size) <= max_width:
                    current = candidate
                else:
                    lines.append(self._truncate_to_width(current, max_width, font_size))
                    current = word
            lines.append(self._truncate_to_width(current, max_width, font_size))
        return lines or [""]

    def _truncate_to_width(self, text: str, width: float, font_size: int) -> str:
        candidate = str(text or "")
        if self._measure_text(candidate, font_size) <= width:
            return candidate
        ellipsis = "..."
        while candidate and self._measure_text(candidate + ellipsis, font_size) > width:
            candidate = candidate[:-1]
        return (candidate + ellipsis) if candidate else ellipsis

    def _is_busy(self) -> bool:
        return self._worker_thread is not None and self._worker_thread.is_alive()

    def _drain_background_tasks_for_tests(self) -> None:
        while True:
            worker = self._worker_thread
            if worker is not None:
                worker.join(timeout=2.0)
            self._consume_worker_result()
            if self._worker_thread is None:
                break
