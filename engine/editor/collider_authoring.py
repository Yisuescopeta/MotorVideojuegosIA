"""
engine/editor/collider_authoring.py - Utilidades de authoring para previsualizar
y editar colliders base o colliders sobreescritos por frame de Animator.
"""

from __future__ import annotations

from typing import Any, Optional

from engine.components.animator import Animator, normalize_collision_frame_payload
from engine.components.collider import Collider

COLLIDER_FIELDS = {
    "enabled",
    "shape_type",
    "width",
    "height",
    "offset_x",
    "offset_y",
    "is_trigger",
    "radius",
    "points",
    "friction",
    "restitution",
    "density",
    "capsule_height",
    "one_way_collision",
    "one_way_collision_direction_y",
    "one_way_collision_margin",
    "one_way_collision_direction_x",
}


def build_collider_payload(component: Any) -> dict[str, Any]:
    """Convierte Collider-like components a payload serializable de authoring."""
    if component is None:
        return normalize_collision_frame_payload({})
    if hasattr(component, "to_dict"):
        raw = component.to_dict()
    elif isinstance(component, dict):
        raw = dict(component)
    else:
        raw = {
            field: getattr(component, field)
            for field in COLLIDER_FIELDS
            if hasattr(component, field)
        }
    return normalize_collision_frame_payload(raw)


def merge_collider_payload(base_payload: Any, override_payload: Any) -> dict[str, Any]:
    """Devuelve el collider efectivo: base + override de frame.

    Acepta overrides parciales sin forzar defaults antes del merge. Los
    overrides guardados por Animator suelen venir completos, pero este
    comportamiento permite a tests y herramientas aplicar solo un campo.
    """
    base = build_collider_payload(base_payload)
    if not isinstance(override_payload, dict):
        return base
    merged = dict(base)
    for field in COLLIDER_FIELDS:
        if field in override_payload:
            merged[field] = override_payload[field]
    return normalize_collision_frame_payload(merged)


def get_effective_animator_collider_payload(
    animator: Animator,
    *,
    base_collider: Optional[Any] = None,
    state_name: Optional[str] = None,
    frame_index: Optional[int] = None,
) -> dict[str, Any]:
    """Obtiene el collider que debe mostrarse para el frame de animacion activo."""
    base_payload = build_collider_payload(base_collider)
    override = animator.get_collision_frame_override(state_name, frame_index)
    return merge_collider_payload(base_payload, override)


def set_animator_frame_collider_payload(
    animator: Animator,
    state_name: str,
    frame_index: int,
    payload: dict[str, Any],
) -> bool:
    """Guarda un collider override en un frame concreto del Animator."""
    normalized = normalize_collision_frame_payload(payload)
    if not normalized:
        return False
    return animator.set_collision_frame_override(state_name, frame_index, normalized)


def copy_base_collider_to_animator_frame(
    animator: Animator,
    base_collider: Any,
    state_name: str,
    frame_index: int,
) -> bool:
    """Inicializa un frame de animacion con una copia editable del collider base."""
    return set_animator_frame_collider_payload(
        animator,
        state_name,
        frame_index,
        build_collider_payload(base_collider),
    )


def clear_animator_frame_collider_payload(
    animator: Animator,
    state_name: str,
    frame_index: int,
) -> bool:
    """Elimina el override del frame para que vuelva a heredar el collider base."""
    return animator.clear_collision_frame_override(state_name, frame_index)


def apply_payload_to_collider(collider: Collider, payload: dict[str, Any]) -> bool:
    """Aplica un payload de authoring sobre un Collider real."""
    normalized = normalize_collision_frame_payload(payload)
    if not normalized:
        return False
    collider.enabled = bool(normalized["enabled"])
    collider.shape_type = str(normalized["shape_type"])
    collider.width = float(normalized["width"])
    collider.height = float(normalized["height"])
    collider.offset_x = float(normalized["offset_x"])
    collider.offset_y = float(normalized["offset_y"])
    collider.is_trigger = bool(normalized["is_trigger"])
    collider.radius = float(normalized["radius"])
    collider.points = [list(point) for point in normalized["points"]]
    collider.friction = float(normalized["friction"])
    collider.restitution = float(normalized["restitution"])
    collider.density = float(normalized["density"])
    collider.capsule_height = float(normalized["capsule_height"])
    collider.one_way_collision = bool(normalized["one_way_collision"])
    collider.one_way_collision_direction_y = float(normalized["one_way_collision_direction_y"])
    collider.one_way_collision_margin = float(normalized["one_way_collision_margin"])
    collider.one_way_collision_direction_x = float(normalized["one_way_collision_direction_x"])
    return True


def get_payload_bounds(payload: dict[str, Any], x: float = 0.0, y: float = 0.0) -> tuple[float, float, float, float]:
    """Calcula el AABB de previsualizacion de un payload sin instanciar entidad."""
    normalized = normalize_collision_frame_payload(payload)
    temp = Collider.from_dict(normalized)
    return temp.get_bounds(float(x), float(y))
