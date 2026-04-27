"""
engine/components/scriptbehaviour.py - Script adjunto serializable.
"""

from __future__ import annotations

import copy
from typing import Any, Dict

from engine.assets.asset_reference import (
    build_asset_reference,
    clone_asset_reference,
    normalize_asset_path,
    normalize_asset_reference,
)
from engine.ecs.component import Component


class ScriptBehaviour(Component):
    """Asocia una entidad con un modulo Python recargable y datos serializables."""

    def __init__(
        self,
        module_path: str = "",
        script: Any = None,
        run_in_edit_mode: bool = False,
        public_data: Dict[str, Any] | None = None,
    ) -> None:
        self.enabled: bool = True
        self.script = self._normalize_script_reference(script, module_path)
        self.module_path: str = self._normalize_module_name(module_path or self.script.get("path", ""))
        self.run_in_edit_mode: bool = run_in_edit_mode
        self.public_data: Dict[str, Any] = copy.deepcopy(public_data or {})

    def get_script_reference(self) -> dict[str, str]:
        return clone_asset_reference(self.script)

    def sync_script_reference(self, reference: Any) -> None:
        self.script = self._normalize_script_reference(reference, self.module_path)
        if self.script.get("path"):
            self.module_path = self._normalize_module_name(self.script["path"])

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "script": self.get_script_reference(),
            "module_path": self.module_path,
            "run_in_edit_mode": self.run_in_edit_mode,
            "public_data": copy.deepcopy(self.public_data),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScriptBehaviour":
        script_ref = normalize_asset_reference(data.get("script"))
        module_path = data.get("module_path", "")
        if module_path and script_ref.get("path"):
            expected_module = cls._normalize_module_name(script_ref["path"])
            if module_path != expected_module and module_path != script_ref["path"]:
                script_ref = build_asset_reference()
        component = cls(
            module_path=module_path,
            script=script_ref,
            run_in_edit_mode=data.get("run_in_edit_mode", False),
            public_data=data.get("public_data", {}),
        )
        component.enabled = data.get("enabled", True)
        return component

    def _normalize_script_reference(self, script: Any, module_path: str) -> dict[str, str]:
        ref = normalize_asset_reference(script)
        if ref.get("path"):
            return ref
        value = normalize_asset_path(module_path)
        if value.endswith(".py") or value.startswith("scripts/"):
            return build_asset_reference(path=value)
        return build_asset_reference()

    @staticmethod
    def _normalize_module_name(module_path: str) -> str:
        value = normalize_asset_path(module_path)
        if value.endswith(".py"):
            if value.startswith("scripts/"):
                value = value[len("scripts/"):]
            value = value[:-3]
        return value.strip("/").replace("/", ".")
