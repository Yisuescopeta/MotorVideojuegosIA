"""Build dependency graph from entry scene."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

from engine.export.models import BuildGraphResult

_ASSET_FIELD_PATTERNS = [
    "texture_path", "asset_path", "sprite_sheet", "tilemap_source",
    "prefab_path", "target_path", "script_path", "material_path",
    "shader_path", "audio_path", "font_path", "image_path",
    "tileset_source", "source", "file_path",
]

_SCENE_FLOW_FIELDS = ["next_scene", "menu_scene", "target_scene"]

_EXCLUDED_DIRS = {
    ".git", ".pytest_cache", "__pycache__", ".motor", "dist",
    "tests", "docs", "build", ".opencode", ".agents", "node_modules",
}


def build_content_graph(
    entry_scene: str,
    project_root: str | Path,
    include_all_assets: bool = False,
) -> BuildGraphResult:
    root = Path(project_root).resolve()
    result = BuildGraphResult(entry_scene=entry_scene)

    visited_scenes: set[str] = set()
    visited_assets: set[str] = set()
    visited_scripts: set[str] = set()
    deps: dict[str, list[str]] = {}

    if _safe_project_path(root, entry_scene) is None:
        result.missing_assets.append(entry_scene)
        result.warnings.append(f"Unsafe entry scene path: {entry_scene}")
        return result

    _traverse_scene(
        entry_scene, root, visited_scenes, visited_assets,
        visited_scripts, result, deps,
    )
    _expand_script_dependencies(root, visited_assets, visited_scripts, result)

    if include_all_assets:
        assets_dir = root / "assets"
        if assets_dir.exists():
            for f in assets_dir.rglob("*"):
                if f.is_file() and not any(p.startswith(".") for p in f.parts):
                    rel = str(f.relative_to(root)).replace("\\", "/")
                    visited_assets.add(rel)

    result.reachable_scenes = sorted(visited_scenes)
    result.reachable_assets = sorted(visited_assets)
    result.reachable_scripts = sorted(visited_scripts)
    result.dependency_map = {k: sorted(set(v)) for k, v in deps.items()}
    return result


def _traverse_scene(
    scene_path: str,
    root: Path,
    visited_scenes: set[str],
    visited_assets: set[str],
    visited_scripts: set[str],
    result: BuildGraphResult,
    deps: dict[str, list[str]],
) -> None:
    normalized = scene_path.replace("\\", "/")
    if _safe_project_path(root, normalized) is None:
        result.missing_assets.append(normalized)
        result.warnings.append(f"Unsafe scene path: {normalized}")
        return
    if normalized in visited_scenes:
        return
    visited_scenes.add(normalized)

    scene_file = root / normalized
    if not scene_file.exists():
        result.missing_assets.append(normalized)
        result.warnings.append(f"Scene not found: {normalized}")
        return

    try:
        data = json.loads(scene_file.read_text(encoding="utf-8"))
    except Exception as exc:
        result.warnings.append(f"Cannot parse scene {normalized}: {exc}")
        return

    deps.setdefault(normalized, [])
    _extract_references(data, root, visited_assets, visited_scripts, result)

    feature_meta = data.get("feature_metadata", {})
    scene_flow = feature_meta.get("scene_flow", {})
    for key in _SCENE_FLOW_FIELDS:
        target = scene_flow.get(key)
        if target and isinstance(target, str):
            if target.endswith(".json"):
                deps.setdefault(normalized, []).append(target)
                _traverse_scene(
                    target, root, visited_scenes, visited_assets,
                    visited_scripts, result, deps,
                )

    for entity in data.get("entities", []):
        if not isinstance(entity, dict):
            continue
        prefab = entity.get("prefab_path")
        if prefab and isinstance(prefab, str):
            if prefab.endswith(".json"):
                deps.setdefault(normalized, []).append(prefab)
                _traverse_scene(
                    prefab, root, visited_scenes, visited_assets,
                    visited_scripts, result, deps,
                )


def _extract_references(
    data: Any,
    root: Path,
    visited_assets: set[str],
    visited_scripts: set[str],
    result: BuildGraphResult,
) -> None:
    if isinstance(data, dict):
        asset_ref_path = data.get("path")
        if _looks_like_asset_reference(data, asset_ref_path):
            _add_reference(
                str(asset_ref_path), root, visited_assets, visited_scripts, result,
            )
        module_script = _script_reference_from_module_path(data.get("module_path"))
        if module_script:
            _add_reference(
                module_script, root, visited_assets, visited_scripts, result,
            )
        for key, value in data.items():
            if key in _ASSET_FIELD_PATTERNS and isinstance(value, str) and value:
                _add_reference(
                    value, root, visited_assets, visited_scripts, result,
                )
            elif isinstance(value, (dict, list)):
                _extract_references(
                    value, root, visited_assets, visited_scripts, result,
                )
    elif isinstance(data, list):
        for item in data:
            _extract_references(
                item, root, visited_assets, visited_scripts, result,
            )


def _looks_like_asset_reference(data: dict[str, Any], path: Any) -> bool:
    if not isinstance(path, str) or not path:
        return False
    if path.endswith(".json"):
        return False
    if "guid" in data:
        return True
    return path.startswith(("assets/", "scripts/", "prefabs/"))


def _script_reference_from_module_path(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return ""
    normalized = value.strip().replace("\\", "/").strip("/")
    if normalized.endswith(".py"):
        return normalized
    if normalized.startswith("scripts/"):
        return f"{normalized}.py"
    return f"scripts/{normalized.replace('.', '/')}.py"


def _add_reference(
    path: str,
    root: Path,
    visited_assets: set[str],
    visited_scripts: set[str],
    result: BuildGraphResult,
) -> None:
    normalized = path.replace("\\", "/")
    if normalized.startswith(("http://", "https://", "#", "@")):
        return
    if _safe_project_path(root, normalized) is None:
        result.missing_assets.append(normalized)
        result.warnings.append(f"Unsafe asset path: {normalized}")
        return
    if any(normalized.startswith(excl) for excl in _EXCLUDED_DIRS):
        return
    full = root / normalized
    if not full.exists():
        if not normalized.startswith(("http://", "https://", "#", "@")):
            result.missing_assets.append(normalized)
        return
    if normalized.endswith(".py"):
        visited_scripts.add(normalized)
    elif full.is_file():
        visited_assets.add(normalized)


def _expand_script_dependencies(
    root: Path,
    visited_assets: set[str],
    visited_scripts: set[str],
    result: BuildGraphResult,
) -> None:
    processed: set[str] = set()
    queue: list[str] = sorted(visited_scripts)
    while queue:
        script_path = queue.pop(0)
        if script_path in processed:
            continue
        processed.add(script_path)
        before_scripts = set(visited_scripts)
        for dependency in _script_dependencies(root, script_path, result):
            _add_reference(dependency, root, visited_assets, visited_scripts, result)
        queue.extend(sorted(visited_scripts - before_scripts - processed))


def _script_dependencies(root: Path, script_path: str, result: BuildGraphResult) -> list[str]:
    dependencies: set[str] = set()
    meta_path = root / f"{script_path}.meta.json"
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            dependencies.update(
                str(item).replace("\\", "/")
                for item in meta.get("dependencies", [])
                if isinstance(item, str) and item.strip()
            )
        except Exception as exc:
            result.warnings.append(f"Cannot parse script metadata {script_path}.meta.json: {exc}")

    full = root / script_path
    if full.exists():
        try:
            tree = ast.parse(full.read_text(encoding="utf-8"))
        except Exception as exc:
            result.warnings.append(f"Cannot parse script {script_path}: {exc}")
        else:
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    value = node.value.replace("\\", "/").strip()
                    if _looks_like_project_reference(value):
                        dependencies.add(value)
    return sorted(dependencies)


def _looks_like_project_reference(value: str) -> bool:
    if not value.startswith(("assets/", "scripts/", "prefabs/", "levels/")):
        return False
    suffix = Path(value).suffix.lower()
    return suffix in {
        ".png",
        ".jpg",
        ".jpeg",
        ".bmp",
        ".gif",
        ".svg",
        ".wav",
        ".mp3",
        ".ogg",
        ".flac",
        ".ttf",
        ".otf",
        ".prefab",
        ".json",
        ".py",
        ".material",
    }


def _safe_project_path(root: Path, relative_path: str) -> Path | None:
    candidate = Path(relative_path)
    if candidate.is_absolute() or ".." in candidate.parts:
        return None
    try:
        resolved = (root / candidate).resolve()
        resolved.relative_to(root)
    except (ValueError, OSError):
        return None
    return resolved
