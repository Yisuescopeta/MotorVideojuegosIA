"""Load content pack in exported runtime."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any


class ContentLoader:
    def __init__(self, base_path: str | Path = "."):
        self.base_path = Path(base_path)
        self.manifest: dict[str, Any] = {}
        self._loaded = False

    def load_manifest(self) -> dict[str, Any]:
        manifest_path = self.base_path / "game.manifest.json"
        if not manifest_path.exists():
            pak_manifest = self._read_manifest_from_pak()
            if pak_manifest is not None:
                self.manifest = pak_manifest
                self._loaded = True
                return self.manifest
            self._loaded = True
            return {}
        self.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self._loaded = True
        return self.manifest

    def get_entry_scene(self) -> str:
        if not self._loaded:
            self.load_manifest()
        return str(self.manifest.get("entry_scene", ""))

    def load_scene_json(self, scene_path: str) -> dict[str, Any] | None:
        """Load scene JSON data, trying filesystem first, then game.pak."""
        if not self._loaded:
            self.load_manifest()
        data = self._load_scene_from_fs(scene_path)
        if data is not None:
            return data
        return self._read_scene_from_pak(scene_path)

    def _load_scene_from_fs(self, scene_path: str) -> dict[str, Any] | None:
        for candidate in (
            self.base_path / "content" / scene_path,
            self.base_path / scene_path,
        ):
            if candidate.exists():
                try:
                    return json.loads(candidate.read_text(encoding="utf-8"))
                except Exception:
                    pass
        return None

    def _read_scene_from_pak(self, scene_path: str) -> dict[str, Any] | None:
        pak_path = self.base_path / "game.pak"
        if not pak_path.exists():
            return None
        with zipfile.ZipFile(pak_path, "r") as pak:
            try:
                return json.loads(pak.read(scene_path).decode("utf-8"))
            except KeyError:
                return None
        return None

    def resolve_asset(self, relative_path: str) -> Path:
        candidate = self.base_path / "content" / relative_path
        if candidate.exists():
            return candidate
        return self.base_path / relative_path

    def verify_integrity(self) -> dict[str, Any]:
        if not self._loaded:
            self.load_manifest()
        results: dict[str, Any] = {"valid": True, "checks": [], "tampered": []}
        pak = self._open_pak()

        for entry_type in ("assets", "scenes", "scripts"):
            for entry in self.manifest.get(entry_type, []):
                path = entry.get("path", "")
                expected_sha = entry.get("sha256", "")
                if not path or not expected_sha:
                    continue
                check = {
                    "path": path,
                    "expected_sha256": expected_sha,
                    "actual_sha256": "",
                    "match": False,
                }
                actual = None
                asset_path = self.resolve_asset(path)
                if asset_path.exists():
                    actual = _sha256_file(asset_path)
                elif pak is not None:
                    # Try reading from pak before reporting missing
                    try:
                        data = pak.read(path)
                        actual = hashlib.sha256(data).hexdigest()
                    except KeyError:
                        actual = None

                if actual is not None:
                    check["actual_sha256"] = actual
                    check["match"] = actual == expected_sha
                    if not check["match"]:
                        results["valid"] = False
                        results["tampered"].append(path)
                else:
                    check["actual_sha256"] = "FILE_NOT_FOUND"
                    results["valid"] = False
                    results["tampered"].append(path)
                results["checks"].append(check)

        return results

    def _open_pak(self):
        """Open game.pak zip file if it exists. Returns None otherwise."""
        pak_path = self.base_path / "game.pak"
        if pak_path.exists():
            return zipfile.ZipFile(pak_path, "r")
        return None

    def _read_manifest_from_pak(self) -> dict[str, Any] | None:
        pak_path = self.base_path / "game.pak"
        if not pak_path.exists():
            return None
        with zipfile.ZipFile(pak_path, "r") as pak:
            try:
                return json.loads(pak.read("game.manifest.json").decode("utf-8"))
            except KeyError:
                return None
        return None


def _sha256_file(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
