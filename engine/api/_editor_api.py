from __future__ import annotations

import json
from typing import Any

from engine.api._context import EngineAPIComponent
from engine.api.types import ActionResult
from engine.editor.ui_core.theme import THEME_REGISTRY, EditorTheme


class EditorAPI(EngineAPIComponent):
    """Editor-only project preferences exposed through EngineAPI."""

    _THEME_PREFERENCE_KEY = "editor_theme"
    _THEME_DATA_PREFERENCE_KEY = "editor_theme_data"

    def load_editor_preferences(self) -> None:
        if self.project_service is None:
            return
        preferences = self.project_service.load_editor_state().get("preferences", {})
        if not isinstance(preferences, dict):
            return
        theme_data = preferences.get(self._THEME_DATA_PREFERENCE_KEY)
        if isinstance(theme_data, dict):
            try:
                THEME_REGISTRY.register(EditorTheme.from_dict(theme_data))
            except Exception:
                pass
        name = preferences.get(self._THEME_PREFERENCE_KEY, "")
        if not name:
            return
        try:
            THEME_REGISTRY.set_active(str(name))
        except KeyError:
            pass

    def list_editor_themes(self) -> list[dict[str, Any]]:
        return [THEME_REGISTRY.get(name).to_dict() for name in THEME_REGISTRY.names()]

    def get_active_editor_theme(self) -> dict[str, Any]:
        return THEME_REGISTRY.active().to_dict()

    def set_active_editor_theme(self, name: str) -> ActionResult:
        if self.project_service is None:
            return self.fail("Project service not ready")
        try:
            theme = THEME_REGISTRY.set_active(str(name))
        except KeyError:
            return self.fail(f"Unknown editor theme: {name}")
        self.project_service.set_preference(self._THEME_PREFERENCE_KEY, theme.name)
        return self.ok("Editor theme updated", theme.to_dict())

    def export_editor_theme(self, path: str, name: str | None = None) -> ActionResult:
        try:
            theme = THEME_REGISTRY.get(str(name)) if name else THEME_REGISTRY.active()
        except KeyError:
            return self.fail(f"Unknown editor theme: {name}")
        target = self.resolve_api_path(path, purpose="export editor theme")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(theme.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return self.ok("Editor theme exported", {"path": target.as_posix(), "theme": theme.to_dict()})

    def import_editor_theme(self, path: str, activate: bool = True) -> ActionResult:
        if self.project_service is None:
            return self.fail("Project service not ready")
        source = self.resolve_api_path(path, purpose="import editor theme")
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                return self.fail("Editor theme file must contain a JSON object")
            theme = EditorTheme.from_dict(payload)
            THEME_REGISTRY.register(theme)
        except Exception as exc:
            return self.fail(f"Failed to import editor theme: {exc}")
        if activate:
            THEME_REGISTRY.set_active(theme.name)
            self.project_service.set_preference(self._THEME_PREFERENCE_KEY, theme.name)
            self.project_service.set_preference(self._THEME_DATA_PREFERENCE_KEY, theme.to_dict())
        return self.ok("Editor theme imported", theme.to_dict())
