"""Console panel for editor messages."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QTextEdit, QToolButton, QVBoxLayout, QWidget


@dataclass(frozen=True)
class ConsoleEntry:
    timestamp: str
    level: str
    message: str


class ConsolePanel(QWidget):
    command_submitted = Signal(str)

    _LEVELS = ("All", "Log", "Warning", "Error")

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ConsolePanel")
        self._entries: list[ConsoleEntry] = []
        self._active_filter = "All"

        self.title_label = QLabel("CONSOLE")
        self.title_label.setObjectName("PanelTitle")
        self.summary_label = QLabel("0 Errors   0 Warnings   0 Logs")
        self.summary_label.setObjectName("ConsoleSummary")

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(6)
        header_row.addWidget(self.title_label)
        header_row.addStretch()
        header_row.addWidget(self.summary_label)

        self._filter_buttons: dict[str, QToolButton] = {}
        filter_row = QHBoxLayout()
        filter_row.setContentsMargins(0, 0, 0, 0)
        filter_row.setSpacing(4)
        for label in self._LEVELS:
            button = QToolButton()
            button.setObjectName("ConsoleFilter")
            button.setText(label)
            button.setCheckable(True)
            button.setChecked(label == "All")
            button.clicked.connect(lambda _checked=False, level=label: self.set_filter(level))
            self._filter_buttons[label] = button
            filter_row.addWidget(button)
        filter_row.addStretch()
        self.clear_button = QToolButton()
        self.clear_button.setObjectName("PanelToolButton")
        self.clear_button.setText("Clear")
        self.clear_button.setToolTip("Clear console messages")
        self.clear_button.clicked.connect(self.clear)
        filter_row.addWidget(self.clear_button)

        self.output = QTextEdit()
        self.output.setObjectName("ConsoleOutput")
        self.output.setReadOnly(True)

        input_row = QHBoxLayout()
        input_row.setContentsMargins(0, 0, 0, 0)
        input_row.setSpacing(6)
        self.command_input = QLineEdit()
        self.command_input.setObjectName("ConsoleCommandInput")
        self.command_input.setPlaceholderText("Enter console command...")
        self.command_input.returnPressed.connect(self._submit_command)
        input_row.addWidget(self.command_input)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        layout.addLayout(header_row)
        layout.addLayout(filter_row)
        layout.addWidget(self.output)
        layout.addLayout(input_row)

    def log(self, message: str, level: str = "log") -> None:
        normalized_level = self._normalize_level(level, message)
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._entries.append(ConsoleEntry(timestamp, normalized_level, str(message)))
        self._render_entries()

    def clear(self) -> None:
        self._entries.clear()
        self.output.clear()
        self._refresh_summary()

    def set_filter(self, level: str) -> None:
        if level not in self._LEVELS:
            level = "All"
        self._active_filter = level
        for label, button in self._filter_buttons.items():
            button.setChecked(label == level)
        self._render_entries()

    def _submit_command(self) -> None:
        command = self.command_input.text().strip()
        self.command_input.clear()
        if not command:
            return
        lowered = command.lower()
        if lowered == "clear":
            self.clear()
            return
        if lowered == "help":
            self.log("Commands: clear, help", "log")
            return
        self.command_submitted.emit(command)

    def _render_entries(self) -> None:
        self._refresh_summary()
        self.output.clear()
        cursor = self.output.textCursor()
        for entry in self._entries:
            if self._active_filter != "All" and entry.level != self._active_filter.lower():
                continue
            self._append_entry(cursor, entry)
        self.output.moveCursor(QTextCursor.MoveOperation.End)

    def _refresh_summary(self) -> None:
        errors = sum(1 for entry in self._entries if entry.level == "error")
        warnings = sum(1 for entry in self._entries if entry.level == "warning")
        logs = sum(1 for entry in self._entries if entry.level == "log")
        self.summary_label.setText(f"{errors} Errors   {warnings} Warnings   {logs} Logs")

    def _append_entry(self, cursor: QTextCursor, entry: ConsoleEntry) -> None:
        timestamp_format = QTextCharFormat()
        timestamp_format.setForeground(QColor("#6f8fa8"))
        level_format = QTextCharFormat()
        level_format.setForeground(self._level_color(entry.level))
        message_format = QTextCharFormat()
        message_format.setForeground(self._level_color(entry.level))
        cursor.insertText(f"[{entry.timestamp}] ", timestamp_format)
        cursor.insertText(f"{entry.level.upper():7} ", level_format)
        cursor.insertText(entry.message, message_format)
        cursor.insertBlock()

    @staticmethod
    def _normalize_level(level: str, message: str) -> str:
        lowered = str(level or "").strip().lower()
        if lowered in {"warning", "warn"}:
            return "warning"
        if lowered in {"error", "err"}:
            return "error"
        text = str(message).lower()
        if "error" in text or "failed" in text or "invalid" in text:
            return "error"
        if "warning" in text or "unsupported" in text:
            return "warning"
        return "log"

    @staticmethod
    def _level_color(level: str) -> QColor:
        if level == "warning":
            return QColor("#ffb84d")
        if level == "error":
            return QColor("#ff667d")
        return QColor("#d9ecff")
