"""
engine/assets/asset_database.py - Catalogo persistente y metadata unificada.
"""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from engine.assets.asset_reference import build_asset_reference, normalize_asset_path, normalize_asset_reference
from engine.project.project_service import ProjectService


class AssetDatabase:
    """Mantiene un catalogo serializable de los assets del proyecto."""

    CATALOG_FILE_NAME = "asset_catalog.json"
    SCAN_PATH_KEYS = ("assets", "scripts", "prefabs", "levels")
    IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp"}
    AUDIO_EXTENSIONS = {".wav", ".ogg", ".mp3"}
    SCRIPT_EXTENSIONS = {".py"}
    PREFAB_EXTENSIONS = {".prefab"}
    SCENE_EXTENSIONS = {".json"}

    def __init__(self, project_service: ProjectService) -> None:
        self._project_service = project_service
        self._catalog_cache: Optional[Dict[str, Any]] = None
        self._guid_index: Dict[str, Dict[str, Any]] = {}
        self._path_index: Dict[str, Dict[str, Any]] = {}
        self._metadata_cache: Dict[str, Dict[str, Any]] = {}
        self._metadata_mtime_ns: Dict[str, int] = {}
        self._slice_index: Dict[str, Dict[str, Dict[str, Any]]] = {}

    def get_catalog_path(self) -> Path:
        return self._project_service.get_project_path("meta") / self.CATALOG_FILE_NAME

    def get_import_artifacts_root(self) -> Path:
        root = self._project_service.get_project_path("meta") / "imported_assets"
        root.mkdir(parents=True, exist_ok=True)
        return root

    def get_build_root(self) -> Path:
        root = self._project_service.get_project_path("build")
        root.mkdir(parents=True, exist_ok=True)
        return root

    def ensure_catalog(self) -> Dict[str, Any]:
        if self._catalog_cache is not None:
            return self._catalog_cache
        catalog_path = self.get_catalog_path()
        if catalog_path.exists():
            try:
                with catalog_path.open("r", encoding="utf-8") as handle:
                    payload = json.load(handle)
                self._set_catalog_cache(payload)
                return self._catalog_cache or payload
            except Exception as exc:
                print(f"[WARNING] AssetDatabase: catalogo invalido en {catalog_path.as_posix()}, reconstruyendo: {exc}")
        return self.refresh_catalog()

    def refresh_catalog(self) -> Dict[str, Any]:
        entries: List[Dict[str, Any]] = []
        seen_guids: set[str] = set()

        for root_key in self.SCAN_PATH_KEYS:
            root = self._project_service.get_project_path(root_key)
            if not root.exists():
                continue

            for path in sorted(root.rglob("*")):
                if not path.is_file() or path.name.endswith(".meta.json") or path.suffix.lower() == ".pyc":
                    continue

                asset_path = self._project_service.to_relative_path(path)
                metadata = self.load_metadata(asset_path)
                self.save_metadata(asset_path, metadata, refresh_catalog=False)
                guid = str(metadata.get("guid", "")).strip()
                if not guid or guid in seen_guids:
                    metadata["guid"] = self._generate_guid()
                    self.save_metadata(asset_path, metadata, refresh_catalog=False)
                seen_guids.add(str(metadata["guid"]))
                entries.append(self._build_catalog_entry(asset_path, metadata))

        by_path = {entry["path"]: entry for entry in entries}
        for entry in entries:
            referenced_by: list[str] = []
            for dependency in entry.get("dependencies", []):
                if dependency in by_path:
                    by_path[dependency].setdefault("referenced_by", []).append(entry["path"])
            entry.setdefault("referenced_by", referenced_by)
        for entry in entries:
            entry["referenced_by"] = sorted(set(entry.get("referenced_by", [])))

        payload = {
            "version": 1,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "assets": sorted(entries, key=lambda item: item["path"]),
        }
        self._write_json(self.get_catalog_path(), payload)
        self._set_catalog_cache(payload)
        self._prune_metadata_cache({entry["path"] for entry in entries})
        return payload

    def load_metadata(self, asset_path: str) -> Dict[str, Any]:
        return copy.deepcopy(self._get_cached_metadata(asset_path))

    def save_metadata(
        self,
        asset_path: str,
        metadata: Dict[str, Any],
        *,
        refresh_catalog: bool = True,
    ) -> Dict[str, Any]:
        asset_path = normalize_asset_path(asset_path)
        payload = self._normalize_metadata(asset_path, metadata)
        metadata_path = self.get_metadata_path(asset_path)
        self._write_json(metadata_path, payload)
        self._store_metadata_cache(asset_path, payload, metadata_path=metadata_path)
        if refresh_catalog:
            self.refresh_catalog()
        else:
            self._invalidate_catalog_cache()
        return payload

    def get_metadata_path(self, asset_path: str) -> Path:
        return Path(str(self._project_service.resolve_path(asset_path)) + ".meta.json")

    def get_asset_entry(self, locator: Any) -> Optional[Dict[str, Any]]:
        self.ensure_catalog()
        if isinstance(locator, str) and locator.startswith("ast_"):
            guid = locator
            path = ""
        else:
            ref = normalize_asset_reference(locator)
            guid = ref.get("guid", "")
            path = self._normalize_locator_path(ref.get("path", ""))

        if guid:
            entry = self._guid_index.get(guid)
            if entry is not None:
                return dict(entry)
        if path:
            normalized_path = normalize_asset_path(path)
            entry = self._path_index.get(normalized_path)
            if entry is not None:
                return dict(entry)

        if path:
            if path.endswith(".meta.json"):
                return None
            candidate = self._project_service.resolve_path(path)
            if candidate.exists() and candidate.is_file():
                self.refresh_catalog()
                if guid:
                    entry = self._guid_index.get(guid)
                    if entry is not None:
                        return dict(entry)
                refreshed_path = self._normalize_locator_path(path)
                entry = self._path_index.get(refreshed_path)
                if entry is not None:
                    return dict(entry)
        return None

    def list_slices(self, asset_path: str) -> List[Dict[str, Any]]:
        metadata = self._get_cached_metadata(asset_path)
        return [dict(item) for item in metadata.get("slices", [])]

    def get_slice_rect(self, asset_path: str, slice_name: str) -> Optional[Dict[str, Any]]:
        normalized_path = normalize_asset_path(asset_path)
        self._get_cached_metadata(normalized_path)
        slice_info = self._slice_index.get(normalized_path, {}).get(str(slice_name))
        return dict(slice_info) if slice_info is not None else None

    def build_reference(self, locator: Any) -> Dict[str, str]:
        entry = self.get_asset_entry(locator)
        if entry is not None:
            return build_asset_reference(entry.get("path", ""), entry.get("guid", ""))
        return normalize_asset_reference(locator)

    def find_assets(
        self,
        search: str = "",
        *,
        asset_kind: str = "",
        importer: str = "",
        extensions: Optional[Iterable[str]] = None,
    ) -> List[Dict[str, Any]]:
        catalog = self.ensure_catalog()
        search_value = search.lower().strip()
        wanted_kind = asset_kind.strip().lower()
        wanted_importer = importer.strip().lower()
        allowed_extensions = {str(ext).lower() for ext in extensions or []}

        result: List[Dict[str, Any]] = []
        for entry in catalog.get("assets", []):
            path = str(entry.get("path", ""))
            if search_value and search_value not in path.lower():
                continue
            if wanted_kind and str(entry.get("asset_kind", "")).lower() != wanted_kind:
                continue
            if wanted_importer and str(entry.get("importer", "")).lower() != wanted_importer:
                continue
            if allowed_extensions and Path(path).suffix.lower() not in allowed_extensions:
                continue
            result.append(dict(entry))
        return result

    def reimport_asset(self, locator: Any) -> Optional[Dict[str, Any]]:
        entry = self.get_asset_entry(locator)
        if entry is None:
            return None
        self.save_metadata(entry["path"], self.load_metadata(entry["path"]))
        return self.get_asset_entry(entry["guid"])

    def build_asset_artifacts(self) -> Dict[str, Any]:
        catalog = self.refresh_catalog()
        artifacts_root = self.get_import_artifacts_root()
        artifacts: list[dict[str, Any]] = []
        total_bytes = 0
        for entry in catalog.get("assets", []):
            artifact = self._build_asset_artifact(entry["path"])
            artifacts.append(artifact)
            total_bytes += int(artifact.get("artifact_size_bytes", 0))
        payload = {
            "version": 1,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "artifact_count": len(artifacts),
            "total_artifact_bytes": total_bytes,
            "artifacts_root": artifacts_root.as_posix(),
            "artifacts": sorted(artifacts, key=lambda item: item["path"]),
        }
        self._write_json(self.get_build_root() / "asset_build_report.json", payload)
        return payload

    def create_bundle(self) -> Dict[str, Any]:
        catalog = self.ensure_catalog()
        build_report = self.build_asset_artifacts()
        bundle_assets: list[dict[str, Any]] = []
        for entry in catalog.get("assets", []):
            artifact_path = self.get_import_artifacts_root() / f"{entry['guid']}.json"
            bundle_assets.append(
                {
                    "guid": entry["guid"],
                    "path": entry["path"],
                    "asset_kind": entry["asset_kind"],
                    "artifact_path": self._project_service.to_relative_path(artifact_path),
                    "dependencies": list(entry.get("dependencies", [])),
                }
            )
        bundle = {
            "version": 1,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "asset_count": len(bundle_assets),
            "build_report": "build/asset_build_report.json",
            "assets": sorted(bundle_assets, key=lambda item: item["path"]),
        }
        bundle_path = self.get_build_root() / "content_bundle.json"
        self._write_json(bundle_path, bundle)
        report = {
            "version": 1,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "bundle_path": bundle_path.as_posix(),
            "asset_count": len(bundle_assets),
            "total_input_bytes": sum(
                int(self._project_service.resolve_path(entry["path"]).stat().st_size)
                for entry in catalog.get("assets", [])
                if self._project_service.resolve_path(entry["path"]).exists()
            ),
            "top_assets_by_size": self._top_assets_by_size(catalog.get("assets", [])),
            "artifacts": build_report["artifacts"],
        }
        self._write_json(self.get_build_root() / "bundle_report.json", report)
        return report

    def move_asset(self, locator: Any, destination_path: str) -> Optional[Dict[str, Any]]:
        entry = self.get_asset_entry(locator)
        if entry is None:
            return None

        source_path = self._project_service.resolve_path(entry["path"])
        self._clear_metadata_cache(entry["path"])
        target_relative = normalize_asset_path(destination_path)
        target_path = self._project_service.resolve_path(target_relative)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(source_path.as_posix(), target_path.as_posix())

        source_meta = self.get_metadata_path(entry["path"])
        target_meta = Path(str(target_path) + ".meta.json")
        if source_meta.exists():
            target_meta.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(source_meta.as_posix(), target_meta.as_posix())

        new_relative_path = self._project_service.to_relative_path(target_path)
        self._clear_metadata_cache(new_relative_path)
        self._rewrite_reference_paths(entry["guid"], new_relative_path)
        self.refresh_catalog()
        return self.get_asset_entry(entry["guid"])

    def rename_asset(self, locator: Any, new_name: str) -> Optional[Dict[str, Any]]:
        entry = self.get_asset_entry(locator)
        if entry is None:
            return None
        current_path = Path(entry["path"])
        clean_name = str(new_name or "").strip()
        if not clean_name:
            return None
        target_name = clean_name if "." in Path(clean_name).name else f"{clean_name}{current_path.suffix}"
        return self.move_asset(locator, current_path.with_name(target_name).as_posix())

    def _build_catalog_entry(self, asset_path: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        resolved = self._project_service.resolve_path(asset_path)
        dependencies = self._collect_dependencies(asset_path, metadata)
        source_hash = self._compute_file_hash(resolved)
        import_settings_hash = self._compute_json_hash(metadata.get("import_settings", {}))
        return {
            "guid": str(metadata.get("guid", "")),
            "guid_short": str(metadata.get("guid", ""))[:8],
            "name": Path(asset_path).name,
            "path": asset_path,
            "absolute_path": resolved.as_posix(),
            "folder": Path(asset_path).parent.as_posix() if "/" in asset_path else "",
            "asset_kind": str(metadata.get("asset_kind", "unknown")),
            "importer": str(metadata.get("importer", "unknown")),
            "labels": list(metadata.get("labels", [])),
            "dependencies": dependencies,
            "has_meta": self.get_metadata_path(asset_path).exists(),
            "import_status": "ready",
            "last_seen_mtime": resolved.stat().st_mtime if resolved.exists() else 0.0,
            "source_hash": source_hash,
            "import_settings_hash": import_settings_hash,
            "reference": build_asset_reference(asset_path, metadata.get("guid", "")),
        }

    def _collect_dependencies(self, asset_path: str, metadata: Dict[str, Any]) -> List[str]:
        declared = [normalize_asset_path(item) for item in metadata.get("dependencies", []) if str(item).strip()]
        inferred: set[str] = set(declared)
        asset_kind = str(metadata.get("asset_kind", "unknown"))
        if asset_kind not in {"scene_data", "prefab"}:
            return sorted(inferred)
        file_path = self._project_service.resolve_path(asset_path)
        if not file_path.exists():
            return sorted(inferred)
        try:
            payload = json.loads(file_path.read_text(encoding="utf-8"))
        except Exception:
            return sorted(inferred)
        self._collect_dependencies_from_value(payload, inferred)
        inferred.discard(normalize_asset_path(asset_path))
        return sorted(inferred)

    def _collect_dependencies_from_value(self, value: Any, dependencies: set[str]) -> None:
        if isinstance(value, dict):
            ref_path = str(value.get("path", "")).strip() if "path" in value else ""
            ref_guid = str(value.get("guid", "")).strip() if "guid" in value else ""
            if ref_path and (ref_guid or self._looks_like_project_asset_path(ref_path)):
                dependencies.add(normalize_asset_path(ref_path))
            for key, nested in value.items():
                if isinstance(nested, str) and self._is_dependency_field(str(key), nested):
                    dependencies.add(normalize_asset_path(nested))
                else:
                    self._collect_dependencies_from_value(nested, dependencies)
            return
        if isinstance(value, list):
            for nested in value:
                self._collect_dependencies_from_value(nested, dependencies)

    def _looks_like_project_asset_path(self, value: str) -> bool:
        normalized = normalize_asset_path(value)
        if not normalized:
            return False
        return normalized.startswith(("assets/", "scripts/", "prefabs/", "levels/"))

    def _is_dependency_field(self, key: str, value: str) -> bool:
        normalized = normalize_asset_path(value)
        if not normalized:
            return False
        if key in {"texture_path", "asset_path", "sprite_sheet", "prefab_path", "target_path", "script_path", "material_path", "shader_path"}:
            return self._looks_like_project_asset_path(normalized)
        if normalized.endswith((".png", ".jpg", ".jpeg", ".bmp", ".wav", ".ogg", ".mp3", ".prefab", ".json", ".py", ".material.json")):
            return self._looks_like_project_asset_path(normalized)
        return False

    def _normalize_metadata(self, asset_path: str, raw: Dict[str, Any]) -> Dict[str, Any]:
        asset_kind = self._infer_asset_kind(asset_path)
        importer = self._infer_importer(asset_kind)
        normalized: Dict[str, Any] = {
            "guid": str(raw.get("guid", "")).strip() or self._generate_guid(),
            "source_path": asset_path,
            "path": asset_path,
            "asset_kind": str(raw.get("asset_kind", "")).strip() or asset_kind,
            "importer": str(raw.get("importer", "")).strip() or importer,
            "labels": [str(item) for item in raw.get("labels", []) if str(item).strip()],
            "dependencies": [str(item) for item in raw.get("dependencies", []) if str(item).strip()],
            "import_settings": dict(raw.get("import_settings", {})) if isinstance(raw.get("import_settings", {}), dict) else {},
            "asset_type": raw.get("asset_type", "sprite_sheet" if asset_kind == "texture" else asset_kind),
            "import_mode": raw.get("import_mode", "grid" if asset_kind == "texture" else "raw"),
            "grid": dict(raw.get("grid", {})) if isinstance(raw.get("grid", {}), dict) else {},
            "automatic": dict(raw.get("automatic", {})) if isinstance(raw.get("automatic", {}), dict) else {},
            "slices": list(raw.get("slices", [])) if isinstance(raw.get("slices", []), list) else [],
        }
        normalized["import_settings"] = self._build_import_settings(normalized)
        return normalized

    def _build_import_settings(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        existing = dict(metadata.get("import_settings", {}))
        existing.setdefault("asset_type", metadata.get("asset_type", ""))
        existing.setdefault("import_mode", metadata.get("import_mode", ""))
        existing.setdefault("grid", dict(metadata.get("grid", {})))
        existing.setdefault("automatic", dict(metadata.get("automatic", {})))
        existing.setdefault("slices", list(metadata.get("slices", [])))
        return existing

    def _infer_asset_kind(self, asset_path: str) -> str:
        suffix = Path(asset_path).suffix.lower()
        parts = Path(asset_path).parts
        normalized_path = normalize_asset_path(asset_path)
        if normalized_path.endswith(".material.json") or "materials" in parts:
            return "material"
        if "scripts" in parts or suffix in self.SCRIPT_EXTENSIONS:
            return "script"
        if "prefabs" in parts or suffix in self.PREFAB_EXTENSIONS:
            return "prefab"
        if "levels" in parts:
            return "scene_data"
        if suffix in self.IMAGE_EXTENSIONS:
            return "texture"
        if suffix in self.AUDIO_EXTENSIONS:
            return "audio"
        return "unknown"

    def _infer_importer(self, asset_kind: str) -> str:
        if asset_kind in {"texture", "audio", "script", "prefab", "scene_data", "material"}:
            return asset_kind
        return "unknown"

    def _generate_guid(self) -> str:
        return f"ast_{uuid.uuid4().hex}"

    def _compute_file_hash(self, path: Path) -> str:
        if not path.exists() or not path.is_file():
            return ""
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _compute_json_hash(self, value: Any) -> str:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _artifact_payload_for_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        resolved = self._project_service.resolve_path(entry["path"])
        metadata = self.load_metadata(entry["path"])
        return {
            "version": 1,
            "guid": entry["guid"],
            "path": entry["path"],
            "asset_kind": entry["asset_kind"],
            "importer": entry["importer"],
            "source_hash": entry.get("source_hash", ""),
            "import_settings_hash": entry.get("import_settings_hash", ""),
            "dependencies": list(entry.get("dependencies", [])),
            "metadata": metadata,
            "source_size_bytes": resolved.stat().st_size if resolved.exists() else 0,
        }

    def _build_asset_artifact(self, asset_path: str) -> Dict[str, Any]:
        entry = self.get_asset_entry(asset_path)
        if entry is None:
            raise FileNotFoundError(f"Asset entry not found for {asset_path}")
        artifact_path = self.get_import_artifacts_root() / f"{entry['guid']}.json"
        artifact_payload = self._artifact_payload_for_entry(entry)
        previous_payload: Dict[str, Any] | None = None
        if artifact_path.exists():
            try:
                previous_payload = json.loads(artifact_path.read_text(encoding="utf-8"))
            except Exception:
                previous_payload = None
        cache_hit = previous_payload is not None and (
            previous_payload.get("source_hash") == artifact_payload["source_hash"]
            and previous_payload.get("import_settings_hash") == artifact_payload["import_settings_hash"]
        )
        if not cache_hit:
            self._write_json(artifact_path, artifact_payload)
        artifact_size = artifact_path.stat().st_size if artifact_path.exists() else 0
        return {
            "guid": entry["guid"],
            "path": entry["path"],
            "asset_kind": entry["asset_kind"],
            "artifact_path": self._project_service.to_relative_path(artifact_path),
            "source_hash": artifact_payload["source_hash"],
            "import_settings_hash": artifact_payload["import_settings_hash"],
            "cache_hit": cache_hit,
            "artifact_size_bytes": artifact_size,
        }

    def _top_assets_by_size(self, entries: List[Dict[str, Any]], limit: int = 10) -> List[Dict[str, Any]]:
        sized_entries: list[dict[str, Any]] = []
        for entry in entries:
            resolved = self._project_service.resolve_path(entry["path"])
            size = resolved.stat().st_size if resolved.exists() else 0
            sized_entries.append(
                {
                    "guid": entry["guid"],
                    "path": entry["path"],
                    "asset_kind": entry["asset_kind"],
                    "size_bytes": size,
                }
            )
        sized_entries.sort(key=lambda item: (-item["size_bytes"], item["path"]))
        return sized_entries[:limit]

    def _normalize_locator_path(self, path: Any) -> str:
        normalized = normalize_asset_path(path)
        if not normalized:
            return ""
        return self._project_service.to_relative_path(normalized)

    def _get_cached_metadata(self, asset_path: str) -> Dict[str, Any]:
        asset_path = normalize_asset_path(asset_path)
        metadata_path = self.get_metadata_path(asset_path)
        current_mtime_ns = metadata_path.stat().st_mtime_ns if metadata_path.exists() else -1
        cached_mtime_ns = self._metadata_mtime_ns.get(asset_path)
        cached = self._metadata_cache.get(asset_path)
        if cached is not None and cached_mtime_ns == current_mtime_ns:
            return cached

        raw: Dict[str, Any] = {}
        if metadata_path.exists():
            try:
                with metadata_path.open("r", encoding="utf-8") as handle:
                    loaded = json.load(handle)
                    if isinstance(loaded, dict):
                        raw = loaded
            except Exception:
                raw = {}

        payload = self._normalize_metadata(asset_path, raw)
        self._store_metadata_cache(asset_path, payload, mtime_ns=current_mtime_ns)
        return self._metadata_cache[asset_path]

    def _store_metadata_cache(
        self,
        asset_path: str,
        payload: Dict[str, Any],
        *,
        metadata_path: Optional[Path] = None,
        mtime_ns: Optional[int] = None,
    ) -> None:
        asset_path = normalize_asset_path(asset_path)
        if mtime_ns is None:
            metadata_file = metadata_path or self.get_metadata_path(asset_path)
            mtime_ns = metadata_file.stat().st_mtime_ns if metadata_file.exists() else -1
        stored = copy.deepcopy(payload)
        self._metadata_cache[asset_path] = stored
        self._metadata_mtime_ns[asset_path] = int(mtime_ns)
        self._slice_index[asset_path] = {
            str(item.get("name", "")): dict(item)
            for item in stored.get("slices", [])
            if str(item.get("name", "")).strip()
        }

    def _clear_metadata_cache(self, asset_path: str) -> None:
        asset_path = normalize_asset_path(asset_path)
        self._metadata_cache.pop(asset_path, None)
        self._metadata_mtime_ns.pop(asset_path, None)
        self._slice_index.pop(asset_path, None)

    def _prune_metadata_cache(self, valid_paths: set[str]) -> None:
        wanted = {normalize_asset_path(path) for path in valid_paths}
        stale_paths = [path for path in self._metadata_cache if path not in wanted]
        for path in stale_paths:
            self._clear_metadata_cache(path)

    def _invalidate_catalog_cache(self) -> None:
        self._catalog_cache = None
        self._guid_index = {}
        self._path_index = {}

    def _set_catalog_cache(self, catalog: Dict[str, Any]) -> None:
        self._catalog_cache = catalog
        self._guid_index = {}
        self._path_index = {}
        for entry in catalog.get("assets", []):
            guid = str(entry.get("guid", "")).strip()
            path = normalize_asset_path(str(entry.get("path", "")))
            if guid:
                self._guid_index[guid] = dict(entry)
            if path:
                self._path_index[path] = dict(entry)

    def _iter_reference_containers(self) -> Iterable[Path]:
        for root_key in ("levels", "prefabs"):
            root = self._project_service.get_project_path(root_key)
            if not root.exists():
                continue
            for path in root.rglob("*"):
                if not path.is_file():
                    continue
                if root_key == "levels" and path.suffix.lower() != ".json":
                    continue
                if root_key == "prefabs" and path.suffix.lower() not in {".prefab", ".json"}:
                    continue
                yield path

    def _rewrite_reference_paths(self, guid: str, new_path: str) -> None:
        for path in self._iter_reference_containers():
            try:
                with path.open("r", encoding="utf-8") as handle:
                    data = json.load(handle)
            except Exception:
                continue
            if self._rewrite_reference_paths_in_value(data, guid, new_path):
                self._write_json(path, data)

    def _rewrite_reference_paths_in_value(self, value: Any, guid: str, new_path: str) -> bool:
        changed = False
        if isinstance(value, dict):
            if str(value.get("guid", "")).strip() == guid and "path" in value and value.get("path") != new_path:
                value["path"] = new_path
                changed = True
            for nested in value.values():
                if self._rewrite_reference_paths_in_value(nested, guid, new_path):
                    changed = True
        elif isinstance(value, list):
            for nested in value:
                if self._rewrite_reference_paths_in_value(nested, guid, new_path):
                    changed = True
        return changed

    def _write_json(self, path: Path, data: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=4)
