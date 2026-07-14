from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from engine.scenes.scene import Scene


class SceneFlowPolicy:
    """Pure precedence and synchronization rules for SceneLink metadata."""

    @staticmethod
    def _metadata_flow(scene: "Scene") -> dict[str, str]:
        metadata = scene.feature_metadata.get("scene_flow", {})
        if not isinstance(metadata, dict):
            return {}
        return {
            str(key): str(value)
            for key, value in metadata.items()
            if str(key).strip() and str(value).strip()
        }

    @staticmethod
    def _payload_metadata_flow(payload: dict[str, Any]) -> dict[str, str]:
        feature_metadata = payload.get("feature_metadata", {})
        metadata = feature_metadata.get("scene_flow", {}) if isinstance(feature_metadata, dict) else {}
        if not isinstance(metadata, dict):
            return {}
        return {
            str(key): str(value)
            for key, value in metadata.items()
            if str(key).strip() and str(value).strip()
        }

    def prepare_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Complete absent targets before schema migration can canonicalize them to empty."""
        prepared = copy.deepcopy(payload)
        metadata = self._payload_metadata_flow(prepared)
        feature_metadata = prepared.get("feature_metadata", {})
        if isinstance(feature_metadata, dict) and feature_metadata.get("scene_flow") == {}:
            feature_metadata.pop("scene_flow", None)
        entities = prepared.get("entities", [])
        if not isinstance(entities, list):
            return prepared
        for entity_data in entities:
            if not isinstance(entity_data, dict):
                continue
            components = entity_data.get("components", {})
            scene_link = components.get("SceneLink") if isinstance(components, dict) else None
            if not isinstance(scene_link, dict) or "target_path" in scene_link:
                continue
            flow_key = str(scene_link.get("flow_key", "") or "").strip()
            fallback = metadata.get(flow_key, "")
            if flow_key and fallback:
                scene_link["target_path"] = fallback
        return prepared

    def prepare_component(self, scene: "Scene", component_data: dict[str, Any]) -> dict[str, Any]:
        prepared = copy.deepcopy(component_data)
        if "target_path" in prepared:
            return prepared
        flow_key = str(prepared.get("flow_key", "") or "").strip()
        fallback = self._metadata_flow(scene).get(flow_key, "")
        if flow_key and fallback:
            prepared["target_path"] = fallback
        return prepared

    def prepare_entity(self, scene: "Scene", entity_data: dict[str, Any]) -> dict[str, Any]:
        prepared = copy.deepcopy(entity_data)
        components = prepared.get("components", {})
        if isinstance(components, dict) and isinstance(components.get("SceneLink"), dict):
            components["SceneLink"] = self.prepare_component(scene, components["SceneLink"])
        return prepared

    def get_effective_flow(self, scene: "Scene") -> dict[str, str]:
        metadata = self._metadata_flow(scene)
        effective = dict(metadata)
        for entity_data in scene.to_dict().get("entities", []):
            if not isinstance(entity_data, dict):
                continue
            components = entity_data.get("components", {})
            scene_link = components.get("SceneLink") if isinstance(components, dict) else None
            if not isinstance(scene_link, dict):
                continue
            flow_key = str(scene_link.get("flow_key", "") or "").strip()
            if not flow_key:
                continue
            if "target_path" not in scene_link:
                fallback = metadata.get(flow_key, "")
                if fallback:
                    effective[flow_key] = fallback
                else:
                    effective.pop(flow_key, None)
                continue
            target_path = str(scene_link.get("target_path", "") or "").strip()
            if target_path:
                effective[flow_key] = target_path
            else:
                effective.pop(flow_key, None)
        return effective

    def sync_metadata_from_links(self, scene: "Scene") -> dict[str, str]:
        effective = self.get_effective_flow(scene)
        scene.set_feature_metadata("scene_flow", copy.deepcopy(effective))
        return effective

    def sync_links_from_metadata(self, scene: "Scene") -> None:
        metadata = self._metadata_flow(scene)
        for entity_data in scene.entities_data:
            if not isinstance(entity_data, dict):
                continue
            components = entity_data.get("components", {})
            scene_link = components.get("SceneLink") if isinstance(components, dict) else None
            if not isinstance(scene_link, dict) or "target_path" in scene_link:
                continue
            flow_key = str(scene_link.get("flow_key", "") or "").strip()
            if not flow_key:
                continue
            fallback = metadata.get(flow_key, "")
            if not fallback:
                continue
            updated_link = copy.deepcopy(scene_link)
            updated_link["target_path"] = fallback
            entity_name = str(entity_data.get("name", "") or "")
            if entity_name:
                scene.replace_component_data(entity_name, "SceneLink", updated_link)

    def set_metadata_target(self, scene: "Scene", key: str, target_path: str) -> dict[str, str]:
        scene_key = str(key).strip()
        metadata = self._metadata_flow(scene)
        target = str(target_path or "").strip()
        if target:
            metadata[scene_key] = target
        else:
            metadata.pop(scene_key, None)
        scene.set_feature_metadata("scene_flow", copy.deepcopy(metadata))
        self.sync_links_from_metadata(scene)
        return self.sync_metadata_from_links(scene)

    def has_invalid_links(self, scene: "Scene") -> bool:
        metadata = self._metadata_flow(scene)
        for entity_data in scene.entities_data:
            if not isinstance(entity_data, dict):
                continue
            components = entity_data.get("components", {})
            scene_link = components.get("SceneLink") if isinstance(components, dict) else None
            if not isinstance(scene_link, dict):
                continue
            flow_key = str(scene_link.get("flow_key", "") or "").strip()
            if "target_path" not in scene_link:
                if not flow_key or not metadata.get(flow_key, ""):
                    return True
                continue
            if not str(scene_link.get("target_path", "") or "").strip():
                return True
        return False

    @staticmethod
    def entity_has_scene_link(entity_data: dict[str, Any]) -> bool:
        components = entity_data.get("components", {})
        return isinstance(components, dict) and "SceneLink" in components
