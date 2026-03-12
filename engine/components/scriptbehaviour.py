"""
engine/components/scriptbehaviour.py - Script adjunto serializable
"""

from __future__ import annotations

import copy
from typing import Any, Dict

from engine.ecs.component import Component


class ScriptBehaviour(Component):
    """Asocia una entidad con un modulo Python recargable y datos serializables."""

    def __init__(
        self,
        module_path: str = "",
        run_in_edit_mode: bool = False,
        public_data: Dict[str, Any] | None = None,
    ) -> None:
        self.enabled: bool = True
        self.module_path: str = module_path
        self.run_in_edit_mode: bool = run_in_edit_mode
        self.public_data: Dict[str, Any] = copy.deepcopy(public_data or {})

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "module_path": self.module_path,
            "run_in_edit_mode": self.run_in_edit_mode,
            "public_data": copy.deepcopy(self.public_data),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScriptBehaviour":
        component = cls(
            module_path=data.get("module_path", ""),
            run_in_edit_mode=data.get("run_in_edit_mode", False),
            public_data=data.get("public_data", {}),
        )
        component.enabled = data.get("enabled", True)
        return component
