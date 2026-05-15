"""JSON persistence for editor theme state.

This writes editor-state theme files only. It does not touch scene schema.
"""

from __future__ import annotations

import json
from pathlib import Path

from engine.editor.ui_core.theme import THEME_REGISTRY, ThemeRegistry


class ThemeSerializer:
    """Save/load active theme name for editor state."""

    schema_version = 1

    def __init__(self, registry: ThemeRegistry = THEME_REGISTRY) -> None:
        self.registry = registry

    def to_dict(self) -> dict[str, object]:
        return {"schema_version": self.schema_version, "active_theme": self.registry.active_name}

    def save(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")

    def load(self, path: str | Path) -> str:
        source = Path(path)
        data = json.loads(source.read_text(encoding="utf-8"))
        name = str(data.get("active_theme", "unity_dark"))
        self.registry.set_active(name)
        return name


def save_active_theme(path: str | Path, registry: ThemeRegistry = THEME_REGISTRY) -> None:
    ThemeSerializer(registry).save(path)


def load_active_theme(path: str | Path, registry: ThemeRegistry = THEME_REGISTRY) -> str:
    return ThemeSerializer(registry).load(path)
