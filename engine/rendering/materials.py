from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.assets.asset_reference import build_asset_reference, clone_asset_reference, normalize_asset_reference


@dataclass
class Material2D:
    """Modelo serializable de material 2D."""

    name: str = "Material2D"
    shader: dict[str, str] = field(default_factory=dict)
    shader_path: str = ""
    shader_id: str = "default"
    parameters: dict[str, Any] = field(default_factory=dict)
    blend_mode: str = "alpha"
    tags: list[str] = field(default_factory=list)

    def get_shader_reference(self) -> dict[str, str]:
        return clone_asset_reference(self.shader)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "material_2d",
            "name": self.name,
            "shader": self.get_shader_reference(),
            "shader_path": self.shader_path,
            "shader_id": self.shader_id,
            "parameters": dict(self.parameters),
            "blend_mode": self.blend_mode,
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Material2D":
        shader_ref = normalize_asset_reference(data.get("shader"))
        shader_path = str(data.get("shader_path", "")).strip()
        if shader_path and shader_ref.get("path") != shader_path:
            shader_ref = build_asset_reference(shader_path, shader_ref.get("guid", ""))
        return cls(
            name=str(data.get("name", "Material2D")),
            shader=shader_ref,
            shader_path=shader_ref.get("path", ""),
            shader_id=str(data.get("shader_id", "default")),
            parameters=dict(data.get("parameters", {})) if isinstance(data.get("parameters", {}), dict) else {},
            blend_mode=str(data.get("blend_mode", "alpha")),
            tags=[str(item) for item in data.get("tags", []) if str(item).strip()],
        )
