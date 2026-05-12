"""Theme loading helpers for the Qt editor."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QApplication

DEFAULT_THEME = "frost_dark"
EDITOR_ASSET_ROOT = Path(__file__).resolve().parents[2] / "assets" / "ui" / "frostline"

_THEME_ALIASES = {
    "dark": "frost_dark",
    "frost_dark": "frost_dark",
    "frost-dark": "frost_dark",
    "light": "frost_light",
    "frost_light": "frost_light",
    "frost-light": "frost_light",
}


def normalize_theme_name(theme_name: str | None) -> str:
    key = str(theme_name or "").strip().lower()
    return _THEME_ALIASES.get(key, DEFAULT_THEME)


def theme_path(theme_name: str | None) -> Path:
    resolved = normalize_theme_name(theme_name)
    return Path(__file__).resolve().parent / f"{resolved}.qss"


def load_theme(app: QApplication, theme_name: str | None = None) -> str:
    resolved = normalize_theme_name(theme_name)
    path = theme_path(resolved)
    app.setStyleSheet(path.read_text(encoding="utf-8"))
    app.setProperty("motor_editor_theme", resolved)
    return resolved


def editor_asset_path(*parts: str) -> Path:
    return EDITOR_ASSET_ROOT.joinpath(*parts)


def load_editor_pixmap(*parts: str) -> QPixmap | None:
    path = editor_asset_path(*parts)
    if not path.exists():
        return None
    pixmap = QPixmap(path.as_posix())
    return None if pixmap.isNull() else pixmap


def load_editor_icon(*parts: str, fallback: QIcon | None = None) -> QIcon:
    path = editor_asset_path(*parts)
    if path.exists():
        icon = QIcon(path.as_posix())
        if not icon.isNull():
            return icon
    return fallback or QIcon()
