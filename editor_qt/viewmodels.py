"""Small normalized data shapes consumed by Qt panels."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def normalize_project_manifest(payload: dict[str, Any] | None) -> dict[str, Any]:
    data = payload if isinstance(payload, dict) else {}
    name = str(data.get("name") or "Untitled Project")
    root = str(data.get("root") or data.get("project_root") or data.get("path") or "")
    return {
        "name": name,
        "root": root,
        "manifest_path": str(data.get("manifest_path") or ""),
        "engine_version": str(data.get("engine_version") or ""),
        "template": str(data.get("template") or ""),
        "activity": data.get("activity") or data.get("last_opened") or data.get("last_accessed") or "",
        "has_project": bool(root or data),
    }


def normalize_scene_summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    data = payload if isinstance(payload, dict) else {}
    path = str(data.get("path") or "")
    name = str(data.get("name") or (Path(path).stem.replace("_", " ").strip() if path else "Scene"))
    return {
        "name": name,
        "path": path,
        "key": str(data.get("key") or path),
        "dirty": bool(data.get("dirty", False)),
        "entity_count": int(data.get("entity_count") or 0),
        "has_scene": bool(data.get("has_scene", bool(path))),
        "source_field": str(data.get("source_field") or ""),
    }


def normalize_asset_summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    data = payload if isinstance(payload, dict) else {}
    path = str(data.get("path") or "")
    name = str(data.get("name") or data.get("display_name") or (Path(path).name if path else "Asset"))
    return {
        "name": name,
        "path": path,
        "type": str(data.get("type") or data.get("asset_type") or Path(path).suffix.lstrip(".") or "asset"),
        "folder": str(data.get("folder") or ""),
    }


def normalize_entity_snapshot(payload: dict[str, Any] | None) -> dict[str, Any]:
    data = payload if isinstance(payload, dict) else {}
    return {
        "name": str(data.get("name") or ""),
        "active": bool(data.get("active", True)),
        "tag": str(data.get("tag") or ""),
        "layer": str(data.get("layer") or ""),
        "parent": data.get("parent"),
        "prefab_instance": data.get("prefab_instance"),
        "components": dict(data.get("components") or {}),
        "component_metadata": dict(data.get("component_metadata") or {}),
    }


def normalize_viewport_entity(payload: dict[str, Any] | None) -> dict[str, Any]:
    entity = normalize_entity_snapshot(payload)
    components = entity["components"]
    transform = components.get("Transform", {}) if isinstance(components.get("Transform"), dict) else {}
    rect = components.get("RectTransform", {}) if isinstance(components.get("RectTransform"), dict) else {}
    sprite = components.get("Sprite", {}) if isinstance(components.get("Sprite"), dict) else {}
    collider = components.get("Collider", {}) if isinstance(components.get("Collider"), dict) else {}

    x = _float(transform.get("x", rect.get("anchored_x", 0.0)))
    y = _float(transform.get("y", rect.get("anchored_y", 0.0)))
    width = _float(rect.get("width", collider.get("width", sprite.get("width", 48.0)))) or 48.0
    height = _float(rect.get("height", collider.get("height", sprite.get("height", 48.0)))) or 48.0
    asset_path = sprite.get("asset_path") or sprite.get("path") or sprite.get("sprite") or sprite.get("texture") or ""
    if isinstance(asset_path, dict):
        asset_path = asset_path.get("path") or asset_path.get("asset_path") or ""
    return {
        "name": entity["name"],
        "active": entity["active"],
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "sprite": str(asset_path or ""),
        "components": sorted(components.keys()),
    }


def normalize_flow_connections(payload: dict[str, Any] | None) -> list[dict[str, str]]:
    data = payload if isinstance(payload, dict) else {}
    rows: list[dict[str, str]] = []
    for key, value in sorted(data.items()):
        key_text = str(key or "").strip()
        target_text = str(value or "").strip()
        if key_text:
            rows.append({"key": key_text, "target": target_text})
    return rows


def normalize_animator_info(payload: dict[str, Any] | None) -> dict[str, Any]:
    data = payload if isinstance(payload, dict) else {}
    states = data.get("states", [])
    if not isinstance(states, list):
        states = []
    return {
        "exists": bool(data.get("exists", False)),
        "sprite_sheet": str(data.get("sprite_sheet") or data.get("sprite_sheet_path") or ""),
        "speed": _float(data.get("speed", 1.0)) or 1.0,
        "flip_x": bool(data.get("flip_x", False)),
        "flip_y": bool(data.get("flip_y", False)),
        "default_state": str(data.get("default_state") or ""),
        "current_state": str(data.get("current_state") or ""),
        "states": [dict(state) for state in states if isinstance(state, dict)],
    }


def normalize_agent_provider(payload: dict[str, Any] | None) -> dict[str, Any]:
    data = payload if isinstance(payload, dict) else {}
    return {
        "id": str(data.get("id") or data.get("provider_id") or ""),
        "name": str(data.get("name") or data.get("id") or "Provider"),
        "status": str(data.get("status") or data.get("auth_status") or ""),
        "models": list(data.get("models") or []),
    }


def normalize_agent_session(payload: dict[str, Any] | None) -> dict[str, Any]:
    data = payload if isinstance(payload, dict) else {}
    return {
        "session_id": str(data.get("session_id") or ""),
        "status": str(data.get("status") or ""),
        "messages": list(data.get("messages") or data.get("events") or []),
        "pending_actions": list(data.get("pending_actions") or []),
        "response": str(data.get("response") or data.get("message") or ""),
    }


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
