"""engine/resources/shader2d_resource.py — Shader2D resource adaptado de Godot Shader.

Shader2DResource es un recurso serializable que define transformaciones
declarativas de píxel (modulate, tint, alpha, UV) sin GPU real (MVP).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Shader2DResource:
    """Recurso Shader 2D serializable (adaptado de Godot Shader).

    MVP: operaciones de color y UV implementadas en Python, no GLSL real.
    Los shaders son definiciones declarativas de transformaciones de píxel.
    """

    resource_id: str = ""
    resource_name: str = "New Shader"
    shader_type: str = "canvas_item"
    vertex_source: str = ""
    fragment_source: str = ""
    uniforms: dict[str, Any] = field(default_factory=dict)
    blend_mode: str = "alpha"

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "resource_name": self.resource_name,
            "shader_type": self.shader_type,
            "vertex_source": self.vertex_source,
            "fragment_source": self.fragment_source,
            "uniforms": dict(self.uniforms),
            "blend_mode": self.blend_mode,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Shader2DResource":
        return cls(
            resource_id=str(data.get("resource_id", "")),
            resource_name=str(data.get("resource_name", "New Shader")),
            shader_type=str(data.get("shader_type", "canvas_item")),
            vertex_source=str(data.get("vertex_source", "")),
            fragment_source=str(data.get("fragment_source", "")),
            uniforms=dict(data.get("uniforms", {}) or {}),
            blend_mode=str(data.get("blend_mode", "alpha")),
        )

    def __repr__(self) -> str:
        return (
            f"Shader2DResource(name={self.resource_name!r}, "
            f"type={self.shader_type}, uniforms={list(self.uniforms.keys())})"
        )
