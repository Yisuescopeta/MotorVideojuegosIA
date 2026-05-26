"""Pure retained-mode control tree (Godot-style).

This sub-package contains pure data models for a retained-mode control tree:
measure/arrange layout, event dispatch, focus management, and basic controls.

All modules are pure: no pyray, no engine.editor.ui, no window dependencies.
"""

from engine.editor.ui_core.controls.console_control import (
    ConsoleCommandResult,
    ConsoleControlModel,
    LogEntry,
)
from engine.editor.ui_core.controls.container import (
    Container,
    HBoxContainer,
    LayoutDirection,
    ScrollContainer,
    VBoxContainer,
)
from engine.editor.ui_core.controls.context_menu import (
    ContextMenuItem,
    ContextMenuManager,
    ContextMenuModel,
    context_menu_from_tuples,
)
from engine.editor.ui_core.controls.control import (
    Button,
    Control,
    Label,
    Panel,
    TextureRect,
)
from engine.editor.ui_core.controls.dropdown import (
    ComboBoxModel,
    DropdownModel,
    DropdownOption,
)
from engine.editor.ui_core.controls.events import (
    Anchor,
    ControlEvent,
    ControlEventKind,
    Margin,
    Size,
)
from engine.editor.ui_core.controls.file_picker import FileEntry, FilePickerModel
from engine.editor.ui_core.controls.focus import FocusManager
from engine.editor.ui_core.controls.popup import (
    PopupManager,
    PopupModel,
    alert_popup,
    confirm_popup,
    yes_no_popup,
)
from engine.editor.ui_core.controls.text_input import TextInput

__all__ = [
    "Anchor",
    "Button",
    "Container",
    "Control",
    "ControlEvent",
    "ControlEventKind",
    "ComboBoxModel",
    "ConsoleCommandResult",
    "ConsoleControlModel",
    "ContextMenuItem",
    "ContextMenuManager",
    "ContextMenuModel",
    "DropdownModel",
    "DropdownOption",
    "FileEntry",
    "FilePickerModel",
    "FocusManager",
    "HBoxContainer",
    "Label",
    "LayoutDirection",
    "LogEntry",
    "Margin",
    "Panel",
    "PopupManager",
    "PopupModel",
    "ScrollContainer",
    "Size",
    "TextInput",
    "TextureRect",
    "VBoxContainer",
    "alert_popup",
    "confirm_popup",
    "context_menu_from_tuples",
    "yes_no_popup",
]
