from __future__ import annotations

from typing import Any

from engine.assets.asset_reference import build_asset_reference, clone_asset_reference, normalize_asset_reference
from engine.ecs.component import Component


class RenderStyle2D(Component):
    """Estado serializable de material/shader/blend para batching 2D."""

    DEFAULT_MATERIAL_ID = "sprite_default"
    DEFAULT_SHADER_ID = "default"
    DEFAULT_BLEND_MODE = "alpha"

    def __init__(
        self,
        material_id: str = DEFAULT_MATERIAL_ID,
        shader_id: str = DEFAULT_SHADER_ID,
        blend_mode: str = DEFAULT_BLEND_MODE,
        atlas_id: str = "",
        material: Any = None,
    ) -> None:
        self.enabled: bool = True
        self.material = normalize_asset_reference(material)
        self.material_path: str = self.material.get("path", "")
        self.material_id: str = str(material_id or self.DEFAULT_MATERIAL_ID)
        self.shader_id: str = str(shader_id or self.DEFAULT_SHADER_ID)
        self.blend_mode: str = str(blend_mode or self.DEFAULT_BLEND_MODE)
        self.atlas_id: str = str(atlas_id or "")

    def get_material_reference(self) -> dict[str, str]:
        return clone_asset_reference(self.material)

    def sync_material_reference(self, reference: Any) -> None:
        self.material = normalize_asset_reference(reference)
        self.material_path = self.material.get("path", "")

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "material": self.get_material_reference(),
            "material_path": self.material_path,
            "material_id": self.material_id,
            "shader_id": self.shader_id,
            "blend_mode": self.blend_mode,
            "atlas_id": self.atlas_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RenderStyle2D":
        material_ref = normalize_asset_reference(data.get("material"))
        material_path = data.get("material_path", "")
        if material_path and material_ref.get("path") != material_path:
            material_ref = build_asset_reference(material_path, material_ref.get("guid", ""))
        component = cls(
            material=material_ref,
            material_id=data.get("material_id", cls.DEFAULT_MATERIAL_ID),
            shader_id=data.get("shader_id", cls.DEFAULT_SHADER_ID),
            blend_mode=data.get("blend_mode", cls.DEFAULT_BLEND_MODE),
            atlas_id=data.get("atlas_id", ""),
        )
        component.enabled = data.get("enabled", True)
        return component
