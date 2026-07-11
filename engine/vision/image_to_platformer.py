"""Build a platformer scene from a simple image through GameSpec2D."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .gamespec_to_scene import SceneBuildReport, build_scene_from_gamespec2d
from .tilemap_reconstructor import reconstruct_tilemap_from_image


@dataclass(frozen=True)
class ImagePlatformerBuildResult:
    """Structured result for the image -> GameSpec2D -> scene pipeline."""

    image_path: str
    gamespec_path: str
    scene_path: str
    schema_version: str
    game_type: str
    entity_count: int
    representation: str
    warnings: list[dict[str, Any]]
    confidence: float | None
    unsupported_features: list[str]
    report: SceneBuildReport

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["report"] = asdict(self.report)
        return data


def default_gamespec_path(scene_path: str | Path) -> Path:
    """Return the deterministic sidecar path for a scene output path."""

    return Path(f"{Path(scene_path)}.gamespec.json")


def build_platformer_from_image(
    image_path: str | Path,
    scene_path: str | Path,
    *,
    project_root: str | Path | None = None,
    gamespec_path: str | Path | None = None,
) -> ImagePlatformerBuildResult:
    """Build a platformer scene from a supported image without ML detection.

    The pipeline is intentionally narrow and deterministic:
    ``reconstruct_tilemap_from_image`` -> ``GameSpec2D.validate`` ->
    ``build_scene_from_gamespec2d``. Outputs are never overwritten.
    """

    image = Path(image_path)
    scene = Path(scene_path)
    sidecar = Path(gamespec_path) if gamespec_path is not None else default_gamespec_path(scene)
    created_files: list[Path] = []

    _refuse_overlapping_outputs(scene, sidecar)
    _refuse_existing(scene, "scene")
    _refuse_existing(sidecar, "gamespec")

    try:
        spec = reconstruct_tilemap_from_image(image)
        spec.validate()

        sidecar.parent.mkdir(parents=True, exist_ok=True)
        sidecar.write_text(json.dumps(spec.to_dict(), indent=2, ensure_ascii=True), encoding="utf-8")
        created_files.append(sidecar)

        scene.parent.mkdir(parents=True, exist_ok=True)
        report = build_scene_from_gamespec2d(spec, scene, project_root=project_root)
        if scene.exists():
            created_files.append(scene)

        return ImagePlatformerBuildResult(
            image_path=image.as_posix(),
            gamespec_path=sidecar.as_posix(),
            scene_path=scene.as_posix(),
            schema_version=spec.schema_version,
            game_type=spec.game_type,
            entity_count=len(report.entity_names),
            representation=report.representation,
            warnings=[asdict(warning) for warning in spec.warnings],
            confidence=spec.confidence,
            unsupported_features=[],
            report=report,
        )
    except Exception:
        if scene.exists() and scene not in created_files:
            created_files.append(scene)
        if sidecar.exists() and sidecar not in created_files:
            created_files.append(sidecar)
        _cleanup_created_files(created_files)
        raise


def _refuse_existing(path: Path, label: str) -> None:
    if path.exists():
        raise FileExistsError(f"{label} output already exists: {path}")


def _refuse_overlapping_outputs(scene_path: Path, gamespec_path: Path) -> None:
    if _normalized_output_path(scene_path) == _normalized_output_path(gamespec_path):
        raise ValueError(f"scene and gamespec outputs must be distinct: {scene_path}")


def _normalized_output_path(path: Path) -> Path:
    try:
        return path.resolve(strict=False)
    except OSError:
        return path.absolute()


def _cleanup_created_files(paths: list[Path]) -> None:
    for path in reversed(paths):
        try:
            if path.exists() and path.is_file():
                path.unlink()
        except OSError:
            pass


__all__ = ["ImagePlatformerBuildResult", "build_platformer_from_image", "default_gamespec_path"]
