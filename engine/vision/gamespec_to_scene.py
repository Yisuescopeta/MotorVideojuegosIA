"""Internal experimental GameSpec2D to scene builder."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any

from engine.api import EngineAPI

from .gamespec2d import GameSpec2D, TileCell
from .semantic_prefabs import camera_payload, collider_payload, semantic_components, transform_payload


JsonDict = dict[str, Any]


@dataclass(frozen=True)
class SceneBuildReport:
    """Structured scene build result intended for agents and tooling."""

    scene_path: str
    scene_name: str
    representation: str
    entity_names: list[str] = field(default_factory=list)
    semantic_mapping: dict[str, list[str]] = field(default_factory=dict)


class GameSpecSceneBuildError(RuntimeError):
    """Raised when the public EngineAPI scene authoring path fails."""


def build_scene_from_gamespec2d(
    spec: GameSpec2D,
    output_path: str | Path,
    *,
    project_root: str | Path | None = None,
    scene_name: str = "gamespec_scene",
) -> SceneBuildReport:
    """Validate ``spec`` and persist a loadable scene through public EngineAPI."""
    spec.validate()
    path = Path(output_path)
    resolved_project_root = Path(project_root) if project_root is not None else path.parent
    levels_root = resolved_project_root / "levels"
    preexisting_intermediates = set(levels_root.glob(f"{_slug(scene_name)}*.json")) if levels_root.exists() else set()
    editor_state_path = resolved_project_root / ".motor" / "editor_state.json"
    had_editor_state = editor_state_path.exists()
    original_editor_state = editor_state_path.read_bytes() if had_editor_state else b""
    created_scene_path: Path | None = None
    api = EngineAPI(project_root=resolved_project_root.as_posix(), sandbox_paths=False, auto_ensure_project=True)
    try:
        create_result = api.create_scene(scene_name)
        _require_ok(create_result, "create scene")
        created_scene_ref = str((create_result.get("data") or {}).get("path") or "")
        if created_scene_ref:
            created_scene_path = Path(created_scene_ref)

        created: list[str] = []
        mapping: dict[str, list[str]] = {}
        type_counts: dict[str, int] = {}

        world_width = float(spec.grid.width) * float(spec.grid.tile_size)
        world_height = float(spec.grid.height) * float(spec.grid.tile_size)
        camera_name = "vision_camera"
        _create_entity(
            api,
            camera_name,
            {
                "Transform": transform_payload(float(spec.camera.x), float(spec.camera.y)),
                "Camera2D": camera_payload(world_width, world_height),
            },
            tag="MainCamera",
            layer="Camera",
        )
        created.append(camera_name)
        mapping.setdefault("camera", []).append(camera_name)

        for cell_index, cell in enumerate(sorted(spec.tilemap.solid_cells, key=lambda item: (item.y, item.x, item.label or "", item.semantics or "")), start=1):
            semantic = _cell_semantic(cell)
            name = f"{_slug(semantic)}_cell_{cell.y:03d}_{cell.x:03d}"
            x, y = _cell_center(spec, cell)
            _create_entity(
                api,
                name,
                {
                    "Transform": transform_payload(x, y),
                    "Collider": collider_payload(spec.grid.tile_size, spec.grid.tile_size),
                },
                tag=_tag_for(semantic),
                layer="Collision",
            )
            created.append(name)
            mapping.setdefault(semantic, []).append(name)
            type_counts[semantic] = max(type_counts.get(semantic, 0), cell_index)

        for entity in spec.entities:
            entity_type = str(entity.type)
            type_counts[entity_type] = type_counts.get(entity_type, 0) + 1
            index = type_counts[entity_type]
            name = f"{_slug(entity_type)}_{index:03d}"
            components = {"Transform": transform_payload(float(entity.x), float(entity.y))}
            components.update(semantic_components(entity_type, spec.grid.tile_size, spec.grid.tile_size, index=index))
            _create_entity(api, name, components, tag=_tag_for(entity_type), layer=_layer_for(entity_type))
            created.append(name)
            mapping.setdefault(entity_type, []).append(name)

        for cell in sorted(spec.tilemap.decorative_cells, key=lambda item: (item.y, item.x, item.label or "", item.semantics or "")):
            semantic = _cell_semantic(cell, default="decorative_prop")
            type_counts[semantic] = type_counts.get(semantic, 0) + 1
            name = f"{_slug(semantic)}_cell_{cell.y:03d}_{cell.x:03d}_{type_counts[semantic]:03d}"
            x, y = _cell_center(spec, cell)
            components = {"Transform": transform_payload(x, y)}
            components.update(semantic_components("decorative_prop", spec.grid.tile_size, spec.grid.tile_size))
            _create_entity(api, name, components, tag="Decorative", layer="Decorative")
            created.append(name)
            mapping.setdefault("decorative_prop", []).append(name)

        _require_ok(api.save_scene(path=path.as_posix()), "save scene")
        return SceneBuildReport(
            scene_path=path.as_posix(),
            scene_name=scene_name,
            representation="collider_blocks",
            entity_names=created,
            semantic_mapping={key: list(value) for key, value in sorted(mapping.items())},
        )
    finally:
        _cleanup_builder_side_effects(
            created_scene_path=created_scene_path,
            requested_output=path,
            preexisting_intermediates=preexisting_intermediates,
            editor_state_path=editor_state_path,
            had_editor_state=had_editor_state,
            original_editor_state=original_editor_state,
        )
        try:
            api.shutdown()
        except Exception:
            pass


def _cleanup_builder_side_effects(
    *,
    created_scene_path: Path | None,
    requested_output: Path,
    preexisting_intermediates: set[Path],
    editor_state_path: Path,
    had_editor_state: bool,
    original_editor_state: bytes,
) -> None:
    """Remove only builder-created intermediate files and restore editor state."""
    if created_scene_path is not None:
        requested = requested_output.resolve()
        created = created_scene_path.resolve()
        preexisting = {item.resolve() for item in preexisting_intermediates}
        if created != requested and created not in preexisting and created.exists():
            created.unlink()
    if had_editor_state:
        if editor_state_path.exists() and editor_state_path.read_bytes() != original_editor_state:
            editor_state_path.write_bytes(original_editor_state)
    elif editor_state_path.exists():
        editor_state_path.unlink()


def _create_entity(api: EngineAPI, name: str, components: JsonDict, *, tag: str, layer: str) -> None:
    _require_ok(api.create_entity(name, components, tag=tag, layer=layer, active=True), f"create entity {name}")


def _require_ok(result: JsonDict, action: str) -> None:
    if not result.get("success"):
        raise GameSpecSceneBuildError(f"Could not {action}: {result.get('message')}")


def _cell_center(spec: GameSpec2D, cell: TileCell) -> tuple[float, float]:
    tile_size = float(spec.grid.tile_size)
    return (float(spec.grid.origin_x) + (float(cell.x) + 0.5) * tile_size, float(spec.grid.origin_y) + (float(cell.y) + 0.5) * tile_size)


def _cell_semantic(cell: TileCell, default: str = "solid_ground") -> str:
    return str(cell.semantics or cell.label or default)


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "entity"


def _tag_for(entity_type: str) -> str:
    return {
        "player_spawn": "Respawn",
        "solid_ground": "Ground",
        "platform": "Platform",
        "coin": "Collectible",
        "enemy_patrol": "Enemy",
        "hazard": "Hazard",
        "goal": "Goal",
        "checkpoint": "Checkpoint",
        "killzone": "KillZone",
        "decorative_prop": "Decorative",
    }.get(entity_type, "Generated")


def _layer_for(entity_type: str) -> str:
    if entity_type in {"solid_ground", "platform"}:
        return "Collision"
    if entity_type == "decorative_prop":
        return "Decorative"
    return "Gameplay"


__all__ = ["GameSpecSceneBuildError", "SceneBuildReport", "build_scene_from_gamespec2d"]
