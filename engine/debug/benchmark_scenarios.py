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


def _make_render_order_payload(order_in_layer: int = 0) -> dict[str, Any]:
    return {
        "enabled": True,
        "sorting_layer": "Default",
        "order_in_layer": int(order_in_layer),
        "render_pass": "World",
    }


def _make_sprite_payload(index: int = 0) -> dict[str, Any]:
    tint_cycle = (
        [255, 255, 255, 255],
        [180, 220, 255, 255],
        [255, 210, 160, 255],
        [190, 255, 190, 255],
    )
    return {
        "enabled": True,
        "texture": {"guid": "", "path": ""},
        "texture_path": "",
        "width": 16,
        "height": 16,
        "origin_x": 0.5,
        "origin_y": 0.5,
        "flip_x": False,
        "flip_y": False,
        "tint": tint_cycle[int(index) % len(tint_cycle)],
    }


def _make_rect_transform_payload(
    x: float,
    y: float,
    *,
    width: float = 160.0,
    height: float = 36.0,
    layout_order: int = 0,
) -> dict[str, Any]:
    return {
        "enabled": True,
        "anchor_min_x": 0.0,
        "anchor_min_y": 0.0,
        "anchor_max_x": 0.0,
        "anchor_max_y": 0.0,
        "pivot_x": 0.0,
        "pivot_y": 0.0,
        "anchored_x": float(x),
        "anchored_y": float(y),
        "width": float(width),
        "height": float(height),
        "rotation": 0.0,
        "scale_x": 1.0,
        "scale_y": 1.0,
        "layout_mode": "free",
        "layout_order": int(layout_order),
        "layout_ignore": False,
        "size_mode_x": "fixed",
        "size_mode_y": "fixed",
        "layout_align": "start",
        "padding_left": 0.0,
        "padding_top": 0.0,
        "padding_right": 0.0,
        "padding_bottom": 0.0,
        "spacing": 0.0,
    }


def _make_canvas_payload() -> dict[str, Any]:
    return {
        "enabled": True,
        "render_mode": "screen_space_overlay",
        "reference_width": 800,
        "reference_height": 600,
        "match_mode": "stretch",
        "sort_order": 0,
    }


def _make_ui_button_payload(index: int) -> dict[str, Any]:
    return {
        "enabled": True,
        "interactable": True,
        "label": f"Button {index}",
        "normal_color": [72, 72, 72, 255],
        "hover_color": [92, 92, 92, 255],
        "pressed_color": [56, 56, 56, 255],
        "disabled_color": [48, 48, 48, 200],
        "transition_scale_pressed": 0.96,
        "on_click": {"type": "emit_event", "name": f"benchmark_button_{index}"},
        "normal_sprite": {"guid": "", "path": ""},
        "hover_sprite": {"guid": "", "path": ""},
        "pressed_sprite": {"guid": "", "path": ""},
        "disabled_sprite": {"guid": "", "path": ""},
        "normal_slice": "",
        "hover_slice": "",
        "pressed_slice": "",
        "disabled_slice": "",
        "image_tint": [255, 255, 255, 255],
        "preserve_aspect": True,
    }


def _make_transform_entity(name: str, x: float, y: float) -> dict[str, Any]:
    return {
        "name": name,
        "active": True,
        "tag": "",
        "layer": "Gameplay",
        "components": {
            "Transform": _make_transform_payload(x, y),
        },
    }


def _make_sprite_entity(name: str, x: float, y: float, index: int) -> dict[str, Any]:
    return {
        "name": name,
        "active": True,
        "tag": "",
        "layer": "Gameplay",
        "components": {
            "Transform": _make_transform_payload(x, y),
            "Sprite": _make_sprite_payload(index),
            "RenderOrder2D": _make_render_order_payload(order_in_layer=index % 32),
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


def many_transform_entities(
    *,
    backend: str,
    entity_count: int = 1000,
    columns: int = 100,
    spacing: float = 8.0,
    **_: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized_entity_count = _normalize_count(entity_count, minimum=1)
    normalized_columns = _normalize_columns(columns)
    normalized_spacing = _normalize_spacing(spacing)
    entities = [
        _make_transform_entity(
            f"Entity_{index}",
            x=float((index % normalized_columns) * normalized_spacing),
            y=float((index // normalized_columns) * normalized_spacing),
        )
        for index in range(normalized_entity_count)
    ]
    params = {
        "entity_count": normalized_entity_count,
        "columns": normalized_columns,
        "spacing": normalized_spacing,
    }
    return {
        "name": "many_transform_entities",
        "entities": entities,
        "rules": [],
        "feature_metadata": _base_feature_metadata(backend),
    }, params


def many_sprite_entities(
    *,
    backend: str,
    entity_count: int = 1000,
    columns: int = 100,
    spacing: float = 16.0,
    **_: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized_entity_count = _normalize_count(entity_count, minimum=1)
    normalized_columns = _normalize_columns(columns)
    normalized_spacing = _normalize_spacing(spacing)
    entities = [
        _make_sprite_entity(
            f"Entity_{index}",
            x=float((index % normalized_columns) * normalized_spacing),
            y=float((index // normalized_columns) * normalized_spacing),
            index=index,
        )
        for index in range(normalized_entity_count)
    ]
    params = {
        "entity_count": normalized_entity_count,
        "columns": normalized_columns,
        "spacing": normalized_spacing,
    }
    return {
        "name": "many_sprite_entities",
        "entities": entities,
        "rules": [],
        "feature_metadata": _base_feature_metadata(backend),
    }, params


def many_ui_buttons(
    *,
    backend: str,
    entity_count: int = 1000,
    columns: int = 10,
    spacing: float = 44.0,
    **_: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized_button_count = _normalize_count(entity_count, minimum=1)
    normalized_columns = _normalize_columns(columns)
    normalized_spacing = _normalize_spacing(spacing)
    entities = [
        {
            "name": "CanvasRoot",
            "active": True,
            "tag": "",
            "layer": "UI",
            "components": {
                "Canvas": _make_canvas_payload(),
                "RectTransform": _make_rect_transform_payload(
                    0.0,
                    0.0,
                    width=800.0,
                    height=600.0,
                ),
            },
        }
    ]
    for index in range(normalized_button_count):
        entities.append(
            {
                "name": f"Entity_{index}",
                "active": True,
                "tag": "",
                "layer": "UI",
                "parent": "CanvasRoot",
                "components": {
                    "RectTransform": _make_rect_transform_payload(
                        x=float((index % normalized_columns) * (160.0 + 8.0)),
                        y=float((index // normalized_columns) * normalized_spacing),
                        layout_order=index,
                    ),
                    "UIButton": _make_ui_button_payload(index),
                },
            }
        )
    params = {
        "entity_count": normalized_button_count,
        "total_entities": len(entities),
        "columns": normalized_columns,
        "spacing": normalized_spacing,
    }
    return {
        "name": "many_ui_buttons",
        "entities": entities,
        "rules": [],
        "feature_metadata": _base_feature_metadata(backend),
    }, params


def huge_tilemap(
    *,
    backend: str,
    tilemap_width: int = 128,
    tilemap_height: int = 128,
    **_: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    width = _normalize_count(tilemap_width, minimum=1)
    height = _normalize_count(tilemap_height, minimum=1)
    tiles = {
        f"{x},{y}": {
            "tile_id": str((x + y) % 8),
            "source": {"guid": "", "path": ""},
            "flags": [],
            "tags": [],
            "custom": {},
            "animated": False,
            "animation_id": "",
            "terrain_type": "",
        }
        for y in range(height)
        for x in range(width)
    }
    entity = {
        "name": "HugeTilemap",
        "active": True,
        "tag": "",
        "layer": "Gameplay",
        "components": {
            "Transform": _make_transform_payload(0.0, 0.0),
            "Tilemap": {
                "enabled": True,
                "cell_width": 16,
                "cell_height": 16,
                "orientation": "orthogonal",
                "tileset": {"guid": "", "path": ""},
                "tileset_path": "",
                "layers": [
                    {
                        "name": "Ground",
                        "visible": True,
                        "opacity": 1.0,
                        "locked": False,
                        "offset_x": 0.0,
                        "offset_y": 0.0,
                        "collision_layer": 0,
                        "tilemap_source": {"guid": "", "path": ""},
                        "metadata": {},
                        "tiles": tiles,
                    }
                ],
                "metadata": {"benchmark_width": width, "benchmark_height": height},
                "tileset_tile_width": 16,
                "tileset_tile_height": 16,
                "tileset_columns": 8,
                "tileset_spacing": 0,
                "tileset_margin": 0,
                "default_layer_name": "Ground",
            },
        },
    }
    params = {
        "tilemap_width": width,
        "tilemap_height": height,
        "tile_count": width * height,
    }
    return {
        "name": "huge_tilemap",
        "entities": [entity],
        "rules": [],
        "feature_metadata": _base_feature_metadata(backend),
    }, params


def transform_edit_stress(
    *,
    backend: str,
    entity_count: int = 1000,
    columns: int = 100,
    spacing: float = 8.0,
    **kwargs: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload, params = many_transform_entities(
        backend=backend,
        entity_count=entity_count,
        columns=columns,
        spacing=spacing,
        **kwargs,
    )
    payload["name"] = "transform_edit_stress"
    params = {
        **params,
        "target_entity": f"Entity_{int(params['entity_count']) - 1}",
        "target_component": "Transform",
        "target_property": "x",
        "target_value": 123456.0,
    }
    return payload, params


def play_mode_clone_stress(
    *,
    backend: str,
    entity_count: int = 1000,
    columns: int = 100,
    spacing: float = 12.0,
    **kwargs: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload, params = many_sprite_entities(
        backend=backend,
        entity_count=entity_count,
        columns=columns,
        spacing=spacing,
        **kwargs,
    )
    payload["name"] = "play_mode_clone_stress"
    return payload, params


SCENARIO_BUILDERS = {
    "many_static_colliders": many_static_colliders,
    "one_dynamic_many_static": one_dynamic_many_static,
    "many_dynamic_and_static": many_dynamic_and_static,
    "many_transform_entities": many_transform_entities,
    "many_sprite_entities": many_sprite_entities,
    "many_ui_buttons": many_ui_buttons,
    "huge_tilemap": huge_tilemap,
    "transform_edit_stress": transform_edit_stress,
    "play_mode_clone_stress": play_mode_clone_stress,
}


def build_benchmark_scenario(name: str, **kwargs: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        builder = SCENARIO_BUILDERS[str(name)]
    except KeyError as exc:
        raise ValueError(f"Unsupported benchmark scenario: {name}") from exc
    return builder(**kwargs)
