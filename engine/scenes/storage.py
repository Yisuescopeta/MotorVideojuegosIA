from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

CHUNKED_SCENE_STORAGE_FORMAT = "chunked_scene"
CHUNKED_SCENE_STORAGE_VERSION = 1
DEFAULT_CHUNKED_SCENE_ENTITY_CHUNK_SIZE = 1000


class SceneStorage(ABC):
    """Storage backend for serialized scene payloads."""

    @abstractmethod
    def load(self, path: str | Path) -> dict[str, Any]:
        """Load a scene payload from path."""

    @abstractmethod
    def save(self, path: str | Path, payload: dict[str, Any]) -> None:
        """Persist a scene payload to path."""


class JsonSceneStorage(SceneStorage):
    def __init__(
        self,
        *,
        compact: bool = False,
        indent: Optional[int] = 4,
        separators: tuple[str, str] = (",", ":"),
    ) -> None:
        self.compact = compact
        self.indent = indent
        self.separators = separators

    def load(self, path: str | Path) -> dict[str, Any]:
        with open(Path(path), "r", encoding="utf-8") as handle:
            return json.load(handle)

    def save(self, path: str | Path, payload: dict[str, Any]) -> None:
        with open(Path(path), "w", encoding="utf-8") as handle:
            if self.compact:
                json.dump(payload, handle, separators=self.separators)
            else:
                json.dump(payload, handle, indent=self.indent)


class ChunkedSceneStorage(SceneStorage):
    """Experimental .scene/ storage that chunks only top-level entities."""

    def __init__(self, *, chunk_size: int = DEFAULT_CHUNKED_SCENE_ENTITY_CHUNK_SIZE, indent: int = 2) -> None:
        if chunk_size <= 0:
            raise ValueError("ChunkedSceneStorage chunk_size must be greater than 0")
        self.chunk_size = chunk_size
        self.indent = indent

    def load(self, path: str | Path) -> dict[str, Any]:
        scene_dir = self._scene_dir(path)
        if not scene_dir.is_dir():
            raise ValueError(f"Chunked scene path must be an existing .scene directory: {scene_dir}")
        manifest_path = scene_dir / "scene.json"
        if not manifest_path.is_file():
            raise FileNotFoundError(f"Chunked scene manifest not found: {manifest_path}")

        with open(manifest_path, "r", encoding="utf-8") as handle:
            manifest = json.load(handle)
        if not isinstance(manifest, dict):
            raise ValueError("Chunked scene manifest must be a JSON object")
        if manifest.get("storage_format") != CHUNKED_SCENE_STORAGE_FORMAT:
            raise ValueError("Chunked scene manifest has unsupported storage_format")
        if manifest.get("storage_version") != CHUNKED_SCENE_STORAGE_VERSION:
            raise ValueError(f"Unsupported chunked scene storage_version: {manifest.get('storage_version')!r}")

        chunks = manifest.get("chunks")
        if not isinstance(chunks, list):
            raise ValueError("Chunked scene manifest chunks must be a list")

        entities: list[Any] = []
        for expected_index, chunk_info in enumerate(chunks):
            if not isinstance(chunk_info, dict):
                raise ValueError(f"Chunked scene manifest chunk {expected_index} must be an object")
            if chunk_info.get("type") != "entities":
                raise ValueError(f"Unsupported chunk type: {chunk_info.get('type')!r}")
            chunk_index = chunk_info.get("index")
            if chunk_index != expected_index:
                raise ValueError(f"Chunked scene chunk index mismatch: expected {expected_index}, got {chunk_index!r}")
            relative_path = chunk_info.get("path")
            if not isinstance(relative_path, str) or not relative_path.strip():
                raise ValueError(f"Chunked scene chunk {expected_index} path must be a non-empty string")
            chunk_path = scene_dir / relative_path
            if not chunk_path.is_file():
                raise FileNotFoundError(f"Chunked scene chunk not found: {chunk_path}")
            with open(chunk_path, "r", encoding="utf-8") as handle:
                chunk_payload = json.load(handle)
            if not isinstance(chunk_payload, dict):
                raise ValueError(f"Chunked scene chunk must be an object: {chunk_path}")
            if chunk_payload.get("chunk_index") != expected_index:
                raise ValueError(
                    f"Chunked scene chunk_index mismatch in {chunk_path}: "
                    f"expected {expected_index}, got {chunk_payload.get('chunk_index')!r}"
                )
            chunk_entities = chunk_payload.get("entities")
            if not isinstance(chunk_entities, list):
                raise ValueError(f"Chunked scene entities chunk must contain an entities list: {chunk_path}")
            expected_count = chunk_info.get("count")
            if expected_count != len(chunk_entities):
                raise ValueError(
                    f"Chunked scene chunk count mismatch in {chunk_path}: "
                    f"expected {expected_count!r}, got {len(chunk_entities)}"
                )
            entities.extend(chunk_entities)

        return {
            "name": manifest.get("name", "Untitled"),
            "schema_version": manifest.get("schema_version"),
            "entities": entities,
            "rules": manifest.get("rules", []),
            "feature_metadata": manifest.get("feature_metadata", {}),
        }

    def save(self, path: str | Path, payload: dict[str, Any]) -> None:
        scene_dir = self._scene_dir(path)
        entities = payload.get("entities")
        if not isinstance(entities, list):
            raise ValueError("ChunkedSceneStorage only supports payloads where entities is a list")

        scene_dir.mkdir(parents=True, exist_ok=True)
        entities_dir = scene_dir / "entities"
        entities_dir.mkdir(parents=True, exist_ok=True)
        for stale_chunk in entities_dir.glob("chunk_*.json"):
            stale_chunk.unlink()

        chunks: list[dict[str, Any]] = []
        for chunk_index, start in enumerate(range(0, len(entities), self.chunk_size)):
            chunk_entities = entities[start : start + self.chunk_size]
            relative_path = f"entities/chunk_{chunk_index:04d}.json"
            chunks.append(
                {
                    "type": "entities",
                    "index": chunk_index,
                    "path": relative_path,
                    "count": len(chunk_entities),
                }
            )
            chunk_payload = {
                "schema_version": payload.get("schema_version"),
                "chunk_index": chunk_index,
                "entities": chunk_entities,
            }
            self._write_json(scene_dir / relative_path, chunk_payload)

        manifest = {
            "storage_format": CHUNKED_SCENE_STORAGE_FORMAT,
            "storage_version": CHUNKED_SCENE_STORAGE_VERSION,
            "name": payload.get("name", "Untitled"),
            "schema_version": payload.get("schema_version"),
            "feature_metadata": payload.get("feature_metadata", {}),
            "rules": payload.get("rules", []),
            "chunks": chunks,
        }
        self._write_json(scene_dir / "scene.json", manifest)

    def _scene_dir(self, path: str | Path) -> Path:
        scene_dir = Path(path)
        if scene_dir.suffix != ".scene":
            raise ValueError(f"Chunked scene path must use .scene suffix: {scene_dir}")
        return scene_dir

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=self.indent)
