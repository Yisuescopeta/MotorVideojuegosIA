"""Collect files for content pack."""

from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path
from typing import Any

from engine.export.models import BuildGraphResult, ContentManifest, ContentManifestEntry

try:
    from engine.config import ENGINE_VERSION
except ImportError:
    ENGINE_VERSION = "0.0.0"


def _sha256_file(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _classify_kind(path: str) -> str:
    if path.endswith((".png", ".jpg", ".jpeg", ".bmp", ".gif", ".svg")):
        return "texture"
    if path.endswith((".wav", ".mp3", ".ogg", ".flac")):
        return "audio"
    if path.endswith((".ttf", ".otf")):
        return "font"
    if path.endswith(".json"):
        if "levels/" in path or path.startswith("levels/"):
            return "scene"
        if "prefabs/" in path or path.startswith("prefabs/"):
            return "prefab"
        return "data"
    if path.endswith((".py", ".pyc")):
        return "script"
    return "asset"


def collect_content(
    graph: BuildGraphResult,
    project_root: str | Path,
    staging_dir: str | Path,
) -> ContentManifest:
    root = Path(project_root).resolve()
    staging = Path(staging_dir)
    staging.mkdir(parents=True, exist_ok=True)

    manifest = ContentManifest(
        schema_version=1,
        entry_scene=graph.entry_scene,
        engine_version=ENGINE_VERSION,
        project={"name": "", "version": "0.1.0"},
    )

    project_json = root / "project.json"
    if project_json.exists():
        try:
            pdata = json.loads(project_json.read_text(encoding="utf-8"))
            manifest.project = {
                "name": str(pdata.get("name", "")),
                "version": str(pdata.get("version_name", pdata.get("version", "0.1.0"))),
            }
        except Exception:
            pass

    all_assets = list(graph.reachable_assets) + list(graph.reachable_scenes)
    content_dir = staging / "content"
    content_dir.mkdir(parents=True, exist_ok=True)

    dep_map = graph.dependency_map

    copied_asset_paths: set[str] = set()
    for asset_path in sorted(set(all_assets)):
        entry = _copy_manifest_entry(root, content_dir, asset_path, dep_map)
        if entry is None:
            continue
        copied_asset_paths.add(entry.path)
        if asset_path.endswith(".json") and (
            "levels/" in asset_path or asset_path.startswith("levels/")
        ):
            manifest.scenes.append(entry)
        else:
            manifest.assets.append(entry)

        sidecar_path = f"{asset_path}.meta.json"
        if sidecar_path not in copied_asset_paths:
            sidecar_entry = _copy_manifest_entry(root, content_dir, sidecar_path, dep_map)
            if sidecar_entry is not None:
                copied_asset_paths.add(sidecar_entry.path)
                manifest.assets.append(sidecar_entry)

    for script_path in sorted(graph.reachable_scripts):
        src = _safe_project_path(root, script_path)
        if src is None:
            continue
        if not src.exists():
            continue
        dst = content_dir / script_path
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        sha = _sha256_file(src)
        manifest.scripts.append(ContentManifestEntry(
            guid=_stable_guid(script_path),
            path=script_path,
            kind="script",
            sha256=sha,
            size_bytes=src.stat().st_size,
        ))

    return manifest


def _copy_manifest_entry(
    root: Path,
    content_dir: Path,
    asset_path: str,
    dep_map: dict[str, list[str]],
) -> ContentManifestEntry | None:
    src = _safe_project_path(root, asset_path)
    if src is None:
        return None
    if not src.exists() or not src.is_file():
        return None
    dst = content_dir / asset_path
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return ContentManifestEntry(
        guid=_stable_guid(asset_path),
        path=asset_path,
        kind=_classify_kind(asset_path),
        sha256=_sha256_file(src),
        size_bytes=src.stat().st_size,
        dependencies=list(dep_map.get(asset_path, [])),
    )


def write_manifest(manifest: ContentManifest, staging_dir: str | Path) -> Path:
    staging = Path(staging_dir)
    manifest_path = staging / "game.manifest.json"
    manifest_path.write_text(
        json.dumps(manifest.to_dict(), indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    return manifest_path


def write_pak(staging_dir: str | Path) -> Path:
    staging = Path(staging_dir)
    content_dir = staging / "content"
    pak_path = staging / "game.pak"
    with zipfile.ZipFile(pak_path, "w", compression=zipfile.ZIP_DEFLATED) as pak:
        manifest_path = staging / "game.manifest.json"
        if manifest_path.exists():
            info = zipfile.ZipInfo("game.manifest.json", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            pak.writestr(info, manifest_path.read_bytes())
        if content_dir.exists():
            for file_path in sorted(p for p in content_dir.rglob("*") if p.is_file()):
                rel = file_path.relative_to(content_dir).as_posix()
                info = zipfile.ZipInfo(rel, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                pak.writestr(info, file_path.read_bytes())
    return pak_path


def verify_pak(staging_dir: str | Path) -> dict[str, Any]:
    """Verify integrity of game.pak by checking every manifest entry inside it.

    Opens game.pak, reads game.manifest.json, and for each asset/scene/script
    entry verifies the file exists inside the pak with the expected SHA-256 hash.

    Returns dict with 'valid': bool, 'checks': list, 'tampered': list.
    """
    staging = Path(staging_dir)
    pak_path = staging / "game.pak"
    result: dict[str, Any] = {"valid": True, "checks": [], "tampered": []}

    if not pak_path.exists():
        result["valid"] = False
        result["tampered"].append("game.pak")
        return result

    try:
        with zipfile.ZipFile(pak_path, "r") as pak:
            # Read all entries while pak is open
            manifest_data = json.loads(pak.read("game.manifest.json").decode("utf-8"))

            for entry_type in ("assets", "scenes", "scripts"):
                for entry in manifest_data.get(entry_type, []):
                    path = entry.get("path", "")
                    expected_sha = entry.get("sha256", "")
                    if not path or not expected_sha:
                        continue
                    check: dict[str, Any] = {
                        "path": path,
                        "expected_sha256": expected_sha,
                        "actual_sha256": "",
                        "match": False,
                    }
                    try:
                        data = pak.read(path)
                        actual = hashlib.sha256(data).hexdigest()
                        check["actual_sha256"] = actual
                        check["match"] = actual == expected_sha
                        if not check["match"]:
                            result["valid"] = False
                            result["tampered"].append(path)
                    except KeyError:
                        check["actual_sha256"] = "FILE_NOT_FOUND"
                        result["valid"] = False
                        result["tampered"].append(path)
                    result["checks"].append(check)

    except (KeyError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
        result["valid"] = False
        result["tampered"].append(f"game.pak corrupt: {exc}")
        return result

    return result


def _stable_guid(path: str) -> str:
    return "guid_" + hashlib.sha256(path.encode("utf-8")).hexdigest()[:24]


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
