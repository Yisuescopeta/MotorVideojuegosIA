"""Application-level controllers extracted from the Game orchestrator."""

from __future__ import annotations

import importlib
from typing import Any

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "DebugToolsController": ("engine.app.debug_tools_controller", "DebugToolsController"),
    "EditorInteractionController": ("engine.app.editor_interaction_controller", "EditorInteractionController"),
    "ProjectWorkspaceController": ("engine.app.project_workspace_controller", "ProjectWorkspaceController"),
    "RuntimeController": ("engine.app.runtime_controller", "RuntimeController"),
    "SceneTransitionController": ("engine.app.scene_transition_controller", "SceneTransitionController"),
    "SceneWorkflowController": ("engine.app.scene_workflow_controller", "SceneWorkflowController"),
}

__all__ = list(_LAZY_IMPORTS)


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(name)
    module_name, attr_name = _LAZY_IMPORTS[name]
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
