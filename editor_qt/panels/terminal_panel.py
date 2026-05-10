"""Manual-start Qt terminal panel."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QByteArray, QProcess
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget


class TerminalPanel(QWidget):
    """Embedded shell via QProcess; process starts only when user requests it."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project_root = Path.cwd()
        self.process: QProcess | None = None

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.input = QLineEdit()
        self.input.setPlaceholderText("Command input")
        self.start_button = QPushButton("Start")
        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)
        self.send_button = QPushButton("Send")

        controls = QHBoxLayout()
        controls.addWidget(self.start_button)
        controls.addWidget(self.stop_button)
        controls.addWidget(self.input, stretch=1)
        controls.addWidget(self.send_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(self.output, stretch=1)
        layout.addLayout(controls)

        self.start_button.clicked.connect(self.start_terminal)
        self.stop_button.clicked.connect(self.stop_terminal)
        self.send_button.clicked.connect(self.send_input)
        self.input.returnPressed.connect(self.send_input)

    def set_project_root(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()

    def start_terminal(self) -> None:
        if self.process is not None:
            return
        self.process = QProcess(self)
        self.process.setWorkingDirectory(self.project_root.as_posix())
        self.process.readyReadStandardOutput.connect(self._read_stdout)
        self.process.readyReadStandardError.connect(self._read_stderr)
        self.process.finished.connect(self._on_finished)
        if os.name == "nt":
            self.process.start("powershell.exe", ["-NoLogo", "-NoProfile"])
        else:
            self.process.start("/bin/sh", [])
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.output.appendPlainText(f"Terminal started in {self.project_root.as_posix()}")

    def stop_terminal(self) -> None:
        if self.process is None:
            return
        self.process.terminate()
        if not self.process.waitForFinished(1000):
            self.process.kill()

    def send_input(self) -> None:
        if self.process is None:
            self.output.appendPlainText("Terminal is not running.")
            return
        text = self.input.text()
        if not text:
            return
        self.process.write((text + "\n").encode("utf-8"))
        self.input.clear()

    def _read_stdout(self) -> None:
        if self.process is not None:
            data: QByteArray = self.process.readAllStandardOutput()
            self.output.appendPlainText(bytes(data.data()).decode("utf-8", errors="replace"))

    def _read_stderr(self) -> None:
        if self.process is not None:
            data: QByteArray = self.process.readAllStandardError()
            self.output.appendPlainText(bytes(data.data()).decode("utf-8", errors="replace"))

    def _on_finished(self, *_args: object) -> None:
        self.process = None
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.output.appendPlainText("Terminal stopped.")
