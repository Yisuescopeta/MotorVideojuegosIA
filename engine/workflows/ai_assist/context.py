from __future__ import annotations

from typing import Any

from engine.api import EngineAPI
from engine.workflows.ai_assist.types import (
    AssetInventoryEntry,
    ProjectContextSnapshot,
    SceneContextEntry,
    utc_now_iso,
)


def _normalize_open_scene(entry: dict[str, Any], *, active_key: str) -> SceneContextEntry:
    key = str(entry.get("key", "")).strip()
    return SceneContextEntry(
        key=key,
        name=str(entry.get("name", "")).strip(),
        path=str(entry.get("path", "")).strip(),
        dirty=bool(entry.get("dirty", False)),
        is_active=bool(key and key == active_key),
    )


def _normalize_asset_summary(asset: dict[str, Any]) -> AssetInventoryEntry:
    return AssetInventoryEntry(
        path=str(asset.get("path", "")).strip(),
        asset_kind=str(asset.get("asset_kind", "")).strip(),
        guid=str(asset.get("guid", "")).strip(),
        importer=str(asset.get("importer", "")).strip(),
    )


def build_project_context_snapshot(api: EngineAPI, *, snapshot_id: str) -> ProjectContextSnapshot:
    manifest = api.get_project_manifest()
    active_scene = api.get_active_scene()
    open_scenes_raw = api.list_open_scenes()
    active_key = str(active_scene.get("key", "")).strip()
    runtime_mode = ""
    if api.game is not None:
        runtime_mode = "edit" if getattr(api.game, "is_edit_mode", False) else "play"

    return ProjectContextSnapshot(
        snapshot_id=snapshot_id,
        created_at=utc_now_iso(),
        project_root=str(manifest.get("root", "")).strip(),
        project_name=str(manifest.get("name", "")).strip(),
        current_scene_name=str(active_scene.get("name", "")).strip(),
        current_scene_path=str(active_scene.get("path", "")).strip(),
        open_scenes=[_normalize_open_scene(entry, active_key=active_key) for entry in open_scenes_raw],
        feature_metadata=dict(api.get_feature_metadata()),
        asset_summaries=[_normalize_asset_summary(entry) for entry in api.list_project_assets()],
        prefab_paths=list(api.list_project_prefabs()),
        script_paths=list(api.list_project_scripts()),
        runtime_mode=runtime_mode,
        selected_entity_name=None,
    )

