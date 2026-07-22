"""
engine/components/scene_link.py - Enlace declarativo a otra escena.
"""

from __future__ import annotations

from engine.ecs.component import Component


class SceneLink(Component):
    """Referencia serializable a otra escena del proyecto."""

    def __init__(
        self,
        target_path: str = "",
        target_entity_name: str = "",
        flow_key: str = "",
        preview_label: str = "",
        link_mode: str = "",
        target_entry_id: str = "",
        target_scene: dict[str, str] | None = None,
        target_entity_id: str = "",
    ) -> None:
        self.enabled: bool = True
        self.target_path: str = str(target_path or "").strip()
        self.target_entity_name: str = str(target_entity_name or "").strip()
        self.flow_key: str = str(flow_key or "").strip()
        self.preview_label: str = str(preview_label or "").strip()
        self.link_mode: str = str(link_mode or "").strip()
        self.target_entry_id: str = str(target_entry_id or "").strip()
        self.target_scene: dict[str, str] | None = (
            {
                "guid": str(target_scene.get("guid", "") or "").strip(),
                "path_hint": str(target_scene.get("path_hint", "") or "").strip(),
            }
            if isinstance(target_scene, dict)
            else None
        )
        if self.target_scene is not None and not self.target_path:
            # Runtime consumers use the mutable path hint for lookup; the
            # serialized component keeps the GUID-first target_scene object.
            self.target_path = self.target_scene.get("path_hint", "")
        self.target_entity_id: str = str(target_entity_id or "").strip()

    def to_dict(self) -> dict[str, object]:
        payload = {
            "enabled": self.enabled,
            "target_path": self.target_path,
            "target_entity_name": self.target_entity_name,
            "flow_key": self.flow_key,
            "preview_label": self.preview_label,
            "link_mode": self.link_mode,
            "target_entry_id": self.target_entry_id,
        }
        if self.target_scene is not None:
            payload["target_scene"] = dict(self.target_scene)
            payload.pop("target_path", None)
        if self.target_entity_id:
            payload["target_entity_id"] = self.target_entity_id
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "SceneLink":
        component = cls(
            target_path=str(data.get("target_path", "") or ""),
            target_entity_name=str(data.get("target_entity_name", "") or ""),
            flow_key=str(data.get("flow_key", "") or ""),
            preview_label=str(data.get("preview_label", "") or ""),
            link_mode=str(data.get("link_mode", "") or ""),
            target_entry_id=str(data.get("target_entry_id", "") or ""),
            target_scene=data.get("target_scene") if isinstance(data.get("target_scene"), dict) else None,
            target_entity_id=str(data.get("target_entity_id", "") or ""),
        )
        component.enabled = bool(data.get("enabled", True))
        return component
