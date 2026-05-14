"""Adapters between legacy editor panels and pure EditorControl models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.editor.console_panel import ConsolePanel
from engine.editor.editor_control_flags import (
    EditorControlFeatureFlagManager,
    EditorControlFeatureFlags,
    default_editor_control_feature_flags,
)
from engine.editor.ui_core.controls.console_control import ConsoleControlModel


@dataclass(slots=True)
class ConsolePanelEditorControlAdapter:
    """Console pilot adapter. Flag off delegates entirely to legacy panel."""

    panel: ConsolePanel = field(default_factory=ConsolePanel)
    flags: EditorControlFeatureFlags = field(default_factory=default_editor_control_feature_flags)
    flag_manager: EditorControlFeatureFlagManager = field(default_factory=EditorControlFeatureFlagManager)
    control_model: ConsoleControlModel = field(default_factory=ConsoleControlModel)

    def __post_init__(self) -> None:
        self.flag_manager.flags = self.flags

    def apply_feature_flag_preferences(self, preferences: dict[str, Any]) -> None:
        self.flags = self.flag_manager.apply_preferences(preferences)

    def update_feature_flags(self, values: dict[str, Any]) -> None:
        self.flags = self.flag_manager.update(values)

    def render(self, x: int, y: int, width: int, height: int) -> None:
        if self.flags.console_panel:
            self._copy_model_to_panel()
        self.panel.render(x, y, width, height)
        if self.flags.console_panel:
            self._copy_panel_to_model()

    def _copy_model_to_panel(self) -> None:
        self.panel.show_info = self.control_model.show_info
        self.panel.show_warn = self.control_model.show_warn
        self.panel.show_err = self.control_model.show_err
        self.panel.show_debug = self.control_model.show_debug
        self.panel.search_text = self.control_model.search_text
        self.panel.command_text = self.control_model.command_text
        self.panel.command_output = self.control_model.command_output
        self.panel.scroll_offset = self.control_model.scroll_offset

    def _copy_panel_to_model(self) -> None:
        self.control_model.show_info = self.panel.show_info
        self.control_model.show_warn = self.panel.show_warn
        self.control_model.show_err = self.panel.show_err
        self.control_model.show_debug = self.panel.show_debug
        self.control_model.search_text = self.panel.search_text
        self.control_model.command_text = self.panel.command_text
        self.control_model.command_output = self.panel.command_output
        self.control_model.scroll_offset = self.panel.scroll_offset

    def __getattr__(self, name: str) -> Any:
        return getattr(self.panel, name)
