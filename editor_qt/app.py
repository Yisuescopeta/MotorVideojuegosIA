"""PySide6 application entrypoint for the Qt editor."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from editor_qt.bridge.engine_facade import EditorEngineFacade
from editor_qt.launcher_window import LauncherWindow
from editor_qt.main_window import MainWindow


def _load_dark_theme(app: QApplication) -> None:
    theme_path = Path(__file__).resolve().parent / "theme" / "dark.qss"
    if theme_path.exists():
        app.setStyleSheet(theme_path.read_text(encoding="utf-8"))


def _parse_args(argv: list[str]) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(description="MotorVideojuegosIA Qt editor")
    parser.add_argument("--project", default="", help="Project root. If omitted, opens the project launcher.")
    parser.add_argument("--scene", default="", help="Optional project-relative scene path to load.")
    namespace, qt_args = parser.parse_known_args(argv[1:])
    return namespace, [argv[0], *qt_args]


def _create_editor_window(app: QApplication, project_root: str | Path, initial_scene: str = "") -> MainWindow:
    facade = EditorEngineFacade(project_root=project_root)
    app.aboutToQuit.connect(facade.shutdown)
    return MainWindow(facade=facade, initial_scene=initial_scene)


def _create_startup_window(app: QApplication, args: argparse.Namespace) -> LauncherWindow | MainWindow:
    if args.project:
        return _create_editor_window(app, Path(args.project).expanduser().resolve(), args.scene)

    launcher_facade = EditorEngineFacade(project_root=Path.cwd(), auto_ensure_project=False, read_only=True)
    launcher = LauncherWindow(facade=launcher_facade)
    app.aboutToQuit.connect(launcher_facade.shutdown)

    def open_editor(project_path: str) -> None:
        editor_facade = EditorEngineFacade(project_root=project_path)
        app.aboutToQuit.connect(editor_facade.shutdown)
        window = MainWindow(facade=editor_facade, initial_scene=args.scene)
        app._motor_editor_facade = editor_facade  # type: ignore[attr-defined]
        app._motor_editor_window = window  # type: ignore[attr-defined]
        window.show()
        launcher.hide()

    launcher.project_open_requested.connect(open_editor)
    return launcher


def main(argv: list[str] | None = None) -> int:
    raw_argv = sys.argv if argv is None else argv
    args, qt_argv = _parse_args(raw_argv)

    app = QApplication.instance()
    if app is None:
        app = QApplication(qt_argv)

    _load_dark_theme(app)

    window = _create_startup_window(app, args)
    app._motor_startup_window = window  # type: ignore[attr-defined]
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
