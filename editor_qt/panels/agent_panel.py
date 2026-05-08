"""Qt agent panel wired through MainWindow and EditorEngineFacade."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


class AgentPanel(QWidget):
    """Minimal chat/approval UI for EngineAPI AgentAPI."""

    refresh_requested = Signal()
    session_create_requested = Signal()
    message_send_requested = Signal(str)
    action_approval_requested = Signal(str, bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.session_id = ""

        self.status_label = QLabel("No agent session")
        self.providers_tree = QTreeWidget()
        self.providers_tree.setHeaderLabels(["Providers"])
        self.tools_tree = QTreeWidget()
        self.tools_tree.setHeaderLabels(["Tools"])
        self.transcript = QPlainTextEdit()
        self.transcript.setReadOnly(True)
        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("Message")
        self.action_id_input = QLineEdit()
        self.action_id_input.setPlaceholderText("Pending action id")

        self.refresh_button = QPushButton("Refresh")
        self.start_button = QPushButton("Start Session")
        self.send_button = QPushButton("Send")
        self.approve_button = QPushButton("Approve")
        self.reject_button = QPushButton("Reject")

        top = QHBoxLayout()
        top.addWidget(self.refresh_button)
        top.addWidget(self.start_button)
        top.addStretch(1)

        send_row = QHBoxLayout()
        send_row.addWidget(self.message_input, stretch=1)
        send_row.addWidget(self.send_button)

        approval_row = QHBoxLayout()
        approval_row.addWidget(self.action_id_input, stretch=1)
        approval_row.addWidget(self.approve_button)
        approval_row.addWidget(self.reject_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(self.status_label)
        layout.addLayout(top)
        layout.addWidget(self.providers_tree)
        layout.addWidget(self.tools_tree)
        layout.addWidget(self.transcript, stretch=1)
        layout.addLayout(send_row)
        layout.addLayout(approval_row)

        self.refresh_button.clicked.connect(self.refresh_requested.emit)
        self.start_button.clicked.connect(self.session_create_requested.emit)
        self.send_button.clicked.connect(self._emit_send)
        self.message_input.returnPressed.connect(self._emit_send)
        self.approve_button.clicked.connect(lambda: self._emit_approval(True))
        self.reject_button.clicked.connect(lambda: self._emit_approval(False))

    def set_agent_data(self, providers: list[dict[str, Any]], tools: list[dict[str, Any]]) -> None:
        self.providers_tree.clear()
        for provider in providers:
            label = str(provider.get("name") or provider.get("id") or "Provider")
            status = str(provider.get("status") or "")
            self.providers_tree.addTopLevelItem(QTreeWidgetItem([f"{label} {status}".strip()]))
        self.tools_tree.clear()
        for tool in tools:
            self.tools_tree.addTopLevelItem(QTreeWidgetItem([str(tool.get("name") or tool.get("id") or "tool")]))

    def set_session(self, session: dict[str, Any]) -> None:
        self.session_id = str(session.get("session_id") or self.session_id)
        status = str(session.get("status") or "ready")
        self.status_label.setText(f"Session {self.session_id or '-'} | {status}")
        response = str(session.get("response") or "")
        if response:
            self.transcript.appendPlainText(response)
        pending = session.get("pending_actions") or []
        if isinstance(pending, list) and pending:
            first = pending[0]
            if isinstance(first, dict):
                self.action_id_input.setText(str(first.get("action_id") or first.get("id") or ""))

    def append_result(self, result: dict[str, object]) -> None:
        message = str(result.get("message") or "")
        self.transcript.appendPlainText(message)
        data = result.get("data")
        if isinstance(data, dict):
            self.set_session(data)

    def _emit_send(self) -> None:
        message = self.message_input.text().strip()
        if message:
            self.transcript.appendPlainText(f"> {message}")
            self.message_send_requested.emit(message)
            self.message_input.clear()

    def _emit_approval(self, approved: bool) -> None:
        action_id = self.action_id_input.text().strip()
        if action_id:
            self.action_approval_requested.emit(action_id, approved)
