"""
engine/inspector/component_editor_registry.py - Registro de editores dedicados.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional


ComponentEditor = Callable[..., int]


class ComponentEditorRegistry:
    """Mapa de nombre de componente a funcion de render especializado."""

    def __init__(self) -> None:
        self._editors: Dict[str, ComponentEditor] = {}

    def register(self, component_name: str, editor: ComponentEditor) -> None:
        self._editors[component_name] = editor

    def get(self, component_name: str) -> Optional[ComponentEditor]:
        return self._editors.get(component_name)

    def has(self, component_name: str) -> bool:
        return component_name in self._editors
