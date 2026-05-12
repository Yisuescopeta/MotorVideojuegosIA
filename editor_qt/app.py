"""PySide6 application entrypoint for the Qt editor."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import cast

from PySide6.QtWidgets import QApplication

from editor_qt.bridge.engine_facade import EditorEngineFacade
from editor_qt.launcher_window import LauncherWindow
from editor_qt.main_window import MainWindow
from editor_qt.theme import DEFAULT_THEME, load_theme


def _parse_args(argv: list[str]) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(description="MotorVideojuegosIA Qt editor")
    parser.add_argument("--project", default="", help="Project root. If omitted, opens the project launcher.")
    parser.add_argument("--scene", default="", help="Optional project-relative scene path to load.")
    parser.add_argument("--theme", default="", help="Theme to load: frost_dark or frost_light.")
    namespace, qt_args = parser.parse_known_args(argv[1:])
    return namespace, [argv[0], *qt_args]


def _create_editor_window(
    app: QApplication,
    project_root: str | Path,
    initial_scene: str = "",
    theme_name: str = "",
) -> MainWindow:
    facade = EditorEngineFacade(project_root=project_root)
    app.aboutToQuit.connect(facade.shutdown)
    return MainWindow(facade=facade, initial_scene=initial_scene, initial_theme=theme_name)


def _create_startup_window(app: QApplication, args: argparse.Namespace) -> LauncherWindow | MainWindow:
    theme_name = str(getattr(args, "theme", "") or "")
    if args.project:
        return _create_editor_window(
            app,
            Path(args.project).expanduser().resolve(),
            args.scene,
            theme_name,
        )

    launcher_facade = EditorEngineFacade(project_root=Path.cwd(), auto_ensure_project=False, read_only=True)
    launcher = LauncherWindow(facade=launcher_facade)
    app.aboutToQuit.connect(launcher_facade.shutdown)

    def open_editor(project_path: str) -> None:
        editor_facade = EditorEngineFacade(project_root=project_path)
        app.aboutToQuit.connect(editor_facade.shutdown)
        window = MainWindow(facade=editor_facade, initial_scene=args.scene, initial_theme=theme_name)
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

    load_theme(cast(QApplication, app), args.theme or DEFAULT_THEME)

    window = _create_startup_window(cast(QApplication, app), args)
    app._motor_startup_window = window  # type: ignore[attr-defined]
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
