"""
engine/api/ai_context.py - Contexto resumido para asistentes IA

PROPÓSITO:
    Construir un resumen pequeño, estable y útil del estado del editor/motor
    sin depender de un volcado completo del World.

NIVELES:
    - minimal: contexto global + foco básico
    - editor_focus: prioriza selección, jerarquía y viewport
    - runtime_focus: prioriza simulación y señales de runtime

EJEMPLO DE USO:
    context = build_ai_context(game, scene_manager, level="editor_focus")
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Optional

from engine.components.animator import Animator
from engine.components.collider import Collider
from engine.components.rigidbody import RigidBody
from engine.components.sprite import Sprite
from engine.components.transform import Transform
from engine.core.engine_state import EngineState

if False:  # pragma: no cover
    from engine.core.game import Game
    from engine.ecs.entity import Entity
    from engine.ecs.world import World
    from engine.scenes.scene_manager import SceneManager


AIContextLevel = Literal["minimal", "editor_focus", "runtime_focus"]

LEVEL_LIMITS: dict[AIContextLevel, dict[str, int]] = {
    "minimal": {
        "relevant_entities": 5,
        "main_components": 3,
        "visible_entities": 0,
        "recent_events": 0,
    },
    "editor_focus": {
        "relevant_entities": 8,
        "main_components": 5,
        "visible_entities": 8,
        "recent_events": 0,
    },
    "runtime_focus": {
        "relevant_entities": 10,
        "main_components": 5,
        "visible_entities": 10,
        "recent_events": 5,
    },
}

COMPONENT_PRIORITY = {
    "Transform": 0,
    "RigidBody": 1,
    "Collider": 2,
    "Sprite": 3,
    "Animator": 4,
}


@dataclass(frozen=True)
class _ViewportBounds:
    left: float
    top: float
    right: float
    bottom: float


def build_ai_context(
    game: Optional["Game"],
    scene_manager: Optional["SceneManager"],
    level: AIContextLevel = "minimal",
    include_world_fallback: bool = False,
) -> dict[str, Any]:
    """Construye un contexto resumido y estable para asistentes IA."""
    _validate_level(level)

    state = game.state if game is not None else EngineState.EDIT
    world = _resolve_world(game, scene_manager, state)
    world_source = _resolve_world_source(scene_manager, state)
    scene = _build_scene_info(game, scene_manager, world)
    limits = LEVEL_LIMITS[level]
    selected_name = world.selected_entity_name if world is not None else None
    selected_entity = world.get_entity_by_name(selected_name) if world is not None and selected_name else None
    entities = world.get_all_entities() if world is not None else []
    duplicate_names = _find_duplicate_names(entities)
    viewport_bounds = _get_viewport_bounds(game)
    visible_entities = _collect_visible_entities(entities, viewport_bounds)
    relevant_entities, relevant_total = _collect_relevant_entities(
        entities=entities,
        selected_entity=selected_entity,
        visible_entities=visible_entities,
        limit=limits["relevant_entities"],
        level=level,
    )
    selected_components = _summarize_components(
        selected_entity,
        limit=limits["main_components"],
    )

    context: dict[str, Any] = {
        "schema": "ai_context/v1",
        "level": level,
        "mode": state.name,
        "world_source": world_source,
        "scene": scene,
        "play_state": _build_play_state(game, scene_manager, state),
        "selection": _build_selection_info(
            world=world,
            entity=selected_entity,
            selected_name=selected_name,
            duplicate_names=duplicate_names,
            component_summaries=selected_components,
        ),
        "relevant_entities": relevant_entities,
        "truncation": {
            "relevant_entities_limited": relevant_total > len(relevant_entities),
            "relevant_entities_total": relevant_total,
            "component_limit": limits["main_components"],
            "visible_entities_limited": False,
            "visible_entities_total": 0,
        },
    }

    if level != "minimal":
        viewport_payload = _build_viewport_payload(
            visible_entities=visible_entities,
            selected_entity=selected_entity,
            limit=limits["visible_entities"],
            duplicate_names=duplicate_names,
        )
        context["viewport"] = viewport_payload["viewport"]
        context["truncation"]["visible_entities_limited"] = viewport_payload["truncated"]
        context["truncation"]["visible_entities_total"] = viewport_payload["total"]

    if level == "runtime_focus":
        context["runtime"] = _build_runtime_payload(game)
        recent_events = _build_recent_events(game, limits["recent_events"])
        if recent_events:
            context["recent_events"] = recent_events

    if include_world_fallback:
        context["fallback"] = {
            "world_dump_available": world is not None,
            "recommended": False,
            "reason": "explicit_opt_in_only",
        }

    return context


def format_ai_context_for_chat(context: dict[str, Any]) -> str:
    """Devuelve un bloque compacto listo para adjuntar a prompts/chat."""
    import json

    return "AI_CONTEXT\n" + json.dumps(context, ensure_ascii=False, separators=(",", ":"))


def build_ai_context_examples() -> dict[str, dict[str, Any]]:
    """Ejemplos estáticos para documentación e integración."""
    return {
        "minimal": {
            "schema": "ai_context/v1",
            "level": "minimal",
            "mode": "EDIT",
            "world_source": "edit_world",
            "scene": {"name": "Demo Level", "path": "levels/demo_level.json", "entity_count": 5},
            "play_state": {"is_playing": False, "is_paused": False, "is_stepping": False},
            "selection": {
                "entity": {"name": "Player", "duplicate_name": False},
                "exists_in_world": True,
                "main_components": [
                    {"type": "Transform", "summary": "pos=(150.0,100.0) scale=(1.0,1.0)"},
                    {"type": "RigidBody", "summary": "vel=(0.0,0.0) grounded=false"},
                ],
            },
            "relevant_entities": [
                {"name": "Player", "reason": "selected"},
                {"name": "Enemy", "reason": "near_selection"},
            ],
            "truncation": {
                "relevant_entities_limited": False,
                "relevant_entities_total": 2,
                "component_limit": 3,
                "visible_entities_limited": False,
                "visible_entities_total": 0,
            },
        },
        "runtime_focus": {
            "schema": "ai_context/v1",
            "level": "runtime_focus",
            "mode": "PLAY",
            "world_source": "runtime_world",
            "scene": {"name": "Demo Level", "path": "levels/demo_level.json", "entity_count": 5},
            "play_state": {"is_playing": True, "is_paused": False, "is_stepping": False},
            "runtime": {"frame": 120, "time": 2.0, "fps": 60},
            "selection": {
                "entity": {"name": "Player", "duplicate_name": False},
                "exists_in_world": True,
                "main_components": [
                    {"type": "Transform", "summary": "pos=(150.0,100.0) scale=(1.0,1.0)"},
                    {"type": "RigidBody", "summary": "vel=(10.0,-45.0) grounded=false"},
                    {"type": "Animator", "summary": "state=run frame=2 finished=false"},
                ],
            },
            "relevant_entities": [
                {"name": "Player", "reason": "selected"},
                {"name": "Enemy", "reason": "near_selection"},
                {"name": "Coin", "reason": "visible"},
            ],
            "viewport": {
                "available": True,
                "anchor": "editor_camera",
                "visible_entities": [
                    {"name": "Player", "reason": "visible"},
                    {"name": "Enemy", "reason": "visible"},
                ],
            },
            "truncation": {
                "relevant_entities_limited": False,
                "relevant_entities_total": 3,
                "component_limit": 5,
                "visible_entities_limited": False,
                "visible_entities_total": 2,
            },
        },
    }


def _validate_level(level: str) -> None:
    if level not in LEVEL_LIMITS:
        raise ValueError(f"Unsupported AI context level: {level}")


def _resolve_world(
    game: Optional["Game"],
    scene_manager: Optional["SceneManager"],
    state: EngineState,
) -> Optional["World"]:
    if scene_manager is not None:
        return scene_manager.active_world
    if game is not None:
        return game.world
    return None


def _resolve_world_source(
    scene_manager: Optional["SceneManager"],
    state: EngineState,
) -> str:
    if scene_manager is not None:
        return "runtime_world" if scene_manager.is_playing else "edit_world"
    if state in (EngineState.PLAY, EngineState.PAUSED, EngineState.STEPPING):
        return "runtime_world"
    return "edit_world"


def _build_scene_info(
    game: Optional["Game"],
    scene_manager: Optional["SceneManager"],
    world: Optional["World"],
) -> dict[str, Any]:
    scene_name = scene_manager.scene_name if scene_manager is not None else "Sin escena"
    path = getattr(game, "current_scene_path", None) if game is not None else None
    path_str = str(path) if path else None
    return {
        "name": scene_name,
        "path": path_str,
        "entity_count": world.entity_count() if world is not None else 0,
    }


def _build_play_state(
    game: Optional["Game"],
    scene_manager: Optional["SceneManager"],
    state: EngineState,
) -> dict[str, Any]:
    return {
        "is_playing": bool(scene_manager.is_playing) if scene_manager is not None else state.is_running(),
        "is_paused": state.is_paused(),
        "is_stepping": state == EngineState.STEPPING,
    }


def _build_runtime_payload(game: Optional["Game"]) -> dict[str, Any]:
    if game is None:
        return {"frame": 0, "time": 0.0, "fps": 0}

    frame = getattr(game.time, "frame_count", 0)
    if not frame and getattr(game, "timeline", None) is not None:
        frame = game.timeline.count()

    return {
        "frame": frame,
        "time": round(game.time.total_time, 4),
        "fps": game.time.fps,
    }


def _build_recent_events(game: Optional["Game"], limit: int) -> list[dict[str, Any]]:
    if game is None or limit <= 0:
        return []

    event_bus = getattr(game, "_event_bus", None)
    if event_bus is None:
        return []

    events = event_bus.get_recent_events(limit)
    payload: list[dict[str, Any]] = []
    for event in events:
        payload.append(
            {
                "name": event.name,
                "keys": sorted(list(event.data.keys()))[:4],
            }
        )
    return payload


def _build_selection_info(
    world: Optional["World"],
    entity: Optional["Entity"],
    selected_name: Optional[str],
    duplicate_names: set[str],
    component_summaries: list[dict[str, str]],
) -> dict[str, Any]:
    selection: dict[str, Any] = {
        "entity": None,
        "exists_in_world": False,
        "main_components": component_summaries,
    }

    if entity is None and selected_name is None:
        return selection

    if entity is None:
        selection["entity"] = {
            "name": selected_name,
            "duplicate_name": selected_name in duplicate_names if selected_name else False,
        }
        selection["exists_in_world"] = False
        return selection

    selection["entity"] = _entity_brief(entity, "selected", duplicate_names)
    selection["exists_in_world"] = True

    transform = entity.get_component(Transform)
    if transform is not None:
        parent_entity = _find_parent_entity(world, entity) if world is not None else None
        child_count = len(transform.children)
        if parent_entity is not None:
            selection["parent"] = _entity_brief(parent_entity, "parent", duplicate_names)
        if child_count:
            selection["child_count"] = child_count

    if entity in (None,):
        return selection

    selection["components_count"] = len(entity.get_all_components())
    return selection


def _find_duplicate_names(entities: list["Entity"]) -> set[str]:
    counts: dict[str, int] = {}
    for entity in entities:
        counts[entity.name] = counts.get(entity.name, 0) + 1
    return {name for name, count in counts.items() if count > 1}


def _collect_relevant_entities(
    entities: list["Entity"],
    selected_entity: Optional["Entity"],
    visible_entities: list["Entity"],
    limit: int,
    level: AIContextLevel,
) -> tuple[list[dict[str, Any]], int]:
    candidates: list[tuple["Entity", str, float]] = []
    seen: set[int] = set()

    if selected_entity is not None:
        candidates.append((selected_entity, "selected", -1.0))
        seen.add(selected_entity.id)

    selected_transform = selected_entity.get_component(Transform) if selected_entity is not None else None

    if level != "minimal":
        for entity in visible_entities:
            if entity.id in seen:
                continue
            distance = _distance_to(selected_transform, entity)
            candidates.append((entity, "visible", distance))
            seen.add(entity.id)

    for entity in entities:
        if entity.id in seen:
            continue
        distance = _distance_to(selected_transform, entity)
        reason = "near_selection" if selected_transform is not None else "scene_entity"
        candidates.append((entity, reason, distance))

    candidates.sort(key=lambda item: (_reason_priority(item[1]), item[2], item[0].name.lower(), item[0].id))
    duplicate_names = _find_duplicate_names(entities)
    limited = candidates[:limit]
    return [
        _entity_brief(entity, reason, duplicate_names)
        for entity, reason, _ in limited
    ], len(candidates)


def _reason_priority(reason: str) -> int:
    priorities = {
        "selected": 0,
        "parent": 1,
        "visible": 2,
        "near_selection": 3,
        "scene_entity": 4,
    }
    return priorities.get(reason, 10)


def _distance_to(origin: Optional[Transform], entity: "Entity") -> float:
    transform = entity.get_component(Transform)
    if origin is None or transform is None:
        return float("inf")
    dx = transform.x - origin.x
    dy = transform.y - origin.y
    return (dx * dx) + (dy * dy)


def _summarize_components(
    entity: Optional["Entity"],
    limit: int,
) -> list[dict[str, str]]:
    if entity is None:
        return []

    components = sorted(
        entity.get_all_components(),
        key=lambda component: (
            COMPONENT_PRIORITY.get(type(component).__name__, 99),
            type(component).__name__,
        ),
    )

    return [
        {
            "type": type(component).__name__,
            "summary": _truncate(_component_summary(component), 80),
        }
        for component in components[:limit]
    ]


def _component_summary(component: Any) -> str:
    if isinstance(component, Transform):
        return (
            f"pos=({component.x:.1f},{component.y:.1f}) "
            f"scale=({component.scale_x:.1f},{component.scale_y:.1f})"
        )
    if isinstance(component, RigidBody):
        return (
            f"vel=({component.velocity_x:.1f},{component.velocity_y:.1f}) "
            f"grounded={str(component.is_grounded).lower()}"
        )
    if isinstance(component, Collider):
        return (
            f"size=({component.width:.1f},{component.height:.1f}) "
            f"trigger={str(component.is_trigger).lower()}"
        )
    if isinstance(component, Sprite):
        texture_name = Path(component.texture_path).name if component.texture_path else "none"
        width = component.width if component.width > 0 else "auto"
        height = component.height if component.height > 0 else "auto"
        return f"texture={texture_name} size=({width},{height})"
    if isinstance(component, Animator):
        return (
            f"state={component.current_state} frame={component.current_frame} "
            f"finished={str(component.is_finished).lower()}"
        )

    component_type = type(component).__name__
    if hasattr(component, "to_dict"):
        try:
            data = component.to_dict()
            keys = ",".join(sorted(data.keys())[:4])
            return f"{component_type} keys={keys}" if keys else component_type
        except Exception:
            pass

    return component_type


def _entity_brief(entity: "Entity", reason: str, duplicate_names: set[str]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": _truncate(entity.name, 48),
        "reason": reason,
    }
    if entity.name in duplicate_names:
        payload["duplicate_name"] = True

    transform = entity.get_component(Transform)
    if transform is not None:
        payload["position"] = {
            "x": round(transform.x, 1),
            "y": round(transform.y, 1),
        }

    return payload


def _build_viewport_payload(
    visible_entities: list["Entity"],
    selected_entity: Optional["Entity"],
    limit: int,
    duplicate_names: set[str],
) -> dict[str, Any]:
    if limit <= 0:
        return {
            "viewport": {"available": False, "anchor": None, "visible_entities": []},
            "truncated": False,
            "total": 0,
        }

    ordered = list(visible_entities)
    if selected_entity is not None and selected_entity not in ordered:
        ordered.insert(0, selected_entity)

    unique_ordered: list["Entity"] = []
    seen: set[int] = set()
    for entity in ordered:
        if entity.id in seen:
            continue
        seen.add(entity.id)
        unique_ordered.append(entity)

    limited = unique_ordered[:limit]
    return {
        "viewport": {
            "available": True,
            "anchor": "editor_camera",
            "visible_entities": [
                _entity_brief(entity, "visible", duplicate_names)
                for entity in limited
            ],
        },
        "truncated": len(unique_ordered) > len(limited),
        "total": len(unique_ordered),
    }


def _get_viewport_bounds(game: Optional["Game"]) -> Optional[_ViewportBounds]:
    if game is None:
        return None

    layout = getattr(game, "editor_layout", None)
    if layout is None or getattr(layout, "scene_texture", None) is None:
        return None

    camera = getattr(layout, "editor_camera", None)
    texture = layout.scene_texture.texture
    if camera is None or texture is None:
        return None

    zoom = camera.zoom if camera.zoom else 1.0
    half_w = texture.width / (2.0 * zoom)
    half_h = texture.height / (2.0 * zoom)
    center_x = camera.target.x
    center_y = camera.target.y
    return _ViewportBounds(
        left=center_x - half_w,
        top=center_y - half_h,
        right=center_x + half_w,
        bottom=center_y + half_h,
    )


def _collect_visible_entities(
    entities: list["Entity"],
    viewport_bounds: Optional[_ViewportBounds],
) -> list["Entity"]:
    if viewport_bounds is None:
        return []

    visible: list["Entity"] = []
    for entity in entities:
        transform = entity.get_component(Transform)
        if transform is None:
            continue
        if (
            viewport_bounds.left <= transform.x <= viewport_bounds.right
            and viewport_bounds.top <= transform.y <= viewport_bounds.bottom
        ):
            visible.append(entity)

    visible.sort(key=lambda entity: entity.name.lower())
    return visible


def _find_parent_entity(world: Optional["World"], entity: "Entity") -> Optional["Entity"]:
    if world is None:
        return None

    transform = entity.get_component(Transform)
    if transform is None or transform.parent is None:
        return None

    for candidate in world.get_all_entities():
        candidate_transform = candidate.get_component(Transform)
        if candidate_transform is transform.parent:
            return candidate
    return None


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    if limit <= 3:
        return text[:limit]
    return text[: limit - 3] + "..."
