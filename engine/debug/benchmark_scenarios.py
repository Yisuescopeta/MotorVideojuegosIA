from __future__ import annotations

from typing import Any


def _normalize_count(value: int, *, minimum: int) -> int:
    return max(minimum, int(value))


def _normalize_columns(value: int) -> int:
    return max(1, int(value))


def _normalize_spacing(value: float) -> float:
    return max(1.0, float(value))


def _normalize_velocity(value: float) -> float:
    return float(value)


def _make_transform_payload(x: float, y: float) -> dict[str, Any]:
    return {
        "enabled": True,
        "x": float(x),
        "y": float(y),
        "rotation": 0.0,
        "scale_x": 1.0,
        "scale_y": 1.0,
    }


def _make_collider_payload(width: float, height: float) -> dict[str, Any]:
    return {
        "enabled": True,
        "shape_type": "box",
        "width": float(width),
        "height": float(height),
        "offset_x": 0.0,
        "offset_y": 0.0,
        "is_trigger": False,
    }


def _make_static_entity(name: str, x: float, y: float, *, width: float = 16.0, height: float = 16.0) -> dict[str, Any]:
    return {
        "name": name,
        "active": True,
        "tag": "",
        "layer": "Gameplay",
        "components": {
            "Transform": _make_transform_payload(x, y),
            "Collider": _make_collider_payload(width, height),
        },
    }


def _make_dynamic_entity(
    name: str,
    x: float,
    y: float,
    *,
    velocity_x: float,
    velocity_y: float = 0.0,
    width: float = 16.0,
    height: float = 16.0,
) -> dict[str, Any]:
    return {
        "name": name,
        "active": True,
        "tag": "",
        "layer": "Gameplay",
        "components": {
            "Transform": _make_transform_payload(x, y),
            "RigidBody": {
                "enabled": True,
                "body_type": "dynamic",
                "gravity_scale": 0.0,
                "velocity_x": float(velocity_x),
                "velocity_y": float(velocity_y),
                "is_grounded": True,
                "collision_detection_mode": "continuous",
            },
            "Collider": _make_collider_payload(width, height),
        },
    }


def _base_feature_metadata(backend: str) -> dict[str, Any]:
    return {
        "physics_2d": {"backend": str(backend or "legacy_aabb")},
        "render_2d": {"sorting_layers": ["Default", "Gameplay", "Foreground"]},
    }


def many_static_colliders(
    *,
    backend: str,
    static_count: int = 100,
    columns: int = 10,
    spacing: float = 24.0,
    **_: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized_static_count = _normalize_count(static_count, minimum=1)
    normalized_columns = _normalize_columns(columns)
    normalized_spacing = _normalize_spacing(spacing)
    entities = [
        _make_static_entity(
            f"Static_{index}",
            x=float((index % normalized_columns) * normalized_spacing),
            y=float((index // normalized_columns) * normalized_spacing),
        )
        for index in range(normalized_static_count)
    ]
    params = {
        "static_count": normalized_static_count,
        "columns": normalized_columns,
        "spacing": normalized_spacing,
    }
    return {
        "name": "many_static_colliders",
        "entities": entities,
        "rules": [],
        "feature_metadata": _base_feature_metadata(backend),
    }, params


def one_dynamic_many_static(
    *,
    backend: str,
    static_count: int = 100,
    columns: int = 10,
    spacing: float = 24.0,
    velocity: float = 160.0,
    **_: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload, params = many_static_colliders(
        backend=backend,
        static_count=static_count,
        columns=columns,
        spacing=spacing,
    )
    normalized_spacing = float(params["spacing"])
    normalized_velocity = _normalize_velocity(velocity)
    dynamic_y = normalized_spacing * max(1, (int(params["static_count"]) // max(1, int(params["columns"]))) // 2)
    payload["entities"].append(
        _make_dynamic_entity(
            "Dynamic_0",
            x=-normalized_spacing,
            y=dynamic_y,
            velocity_x=normalized_velocity,
        )
    )
    params = {
        **params,
        "dynamic_count": 1,
        "velocity": normalized_velocity,
    }
    payload["name"] = "one_dynamic_many_static"
    return payload, params


def many_dynamic_and_static(
    *,
    backend: str,
    static_count: int = 60,
    dynamic_count: int = 12,
    columns: int = 10,
    spacing: float = 24.0,
    velocity: float = 140.0,
    **_: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized_static_count = _normalize_count(static_count, minimum=1)
    normalized_dynamic_count = _normalize_count(dynamic_count, minimum=1)
    normalized_columns = _normalize_columns(columns)
    normalized_spacing = _normalize_spacing(spacing)
    normalized_velocity = _normalize_velocity(velocity)

    entities = [
        _make_static_entity(
            f"Static_{index}",
            x=float((index % normalized_columns) * normalized_spacing),
            y=float((index // normalized_columns) * normalized_spacing * 1.5),
        )
        for index in range(normalized_static_count)
    ]
    dynamic_row_y = normalized_spacing * 0.75
    for index in range(normalized_dynamic_count):
        direction = 1.0 if index % 2 == 0 else -1.0
        row = index // normalized_columns
        column = index % normalized_columns
        entities.append(
            _make_dynamic_entity(
                f"Dynamic_{index}",
                x=float(column * normalized_spacing + (normalized_spacing * 0.5 if direction > 0 else 0.0)),
                y=float(dynamic_row_y + row * normalized_spacing * 1.5),
                velocity_x=normalized_velocity * direction,
            )
        )

    params = {
        "static_count": normalized_static_count,
        "dynamic_count": normalized_dynamic_count,
        "columns": normalized_columns,
        "spacing": normalized_spacing,
        "velocity": normalized_velocity,
    }
    return {
        "name": "many_dynamic_and_static",
        "entities": entities,
        "rules": [],
        "feature_metadata": _base_feature_metadata(backend),
    }, params


SCENARIO_BUILDERS = {
    "many_static_colliders": many_static_colliders,
    "one_dynamic_many_static": one_dynamic_many_static,
    "many_dynamic_and_static": many_dynamic_and_static,
}


def build_benchmark_scenario(name: str, **kwargs: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        builder = SCENARIO_BUILDERS[str(name)]
    except KeyError as exc:
        raise ValueError(f"Unsupported benchmark scenario: {name}") from exc
    return builder(**kwargs)
