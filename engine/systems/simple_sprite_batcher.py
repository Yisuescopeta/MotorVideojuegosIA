"""Runtime helpers for batching simple 2D sprite render commands.

The historical render graph already grouped commands by render state, but the
runtime path still submitted every sprite through ``draw_texture_pro``.  This
module installs a narrow internal patch for ``RenderSystem`` that keeps the
existing graph/order contracts intact while drawing consecutive simple sprites
with the same texture as one rlgl quad batch.
"""

from __future__ import annotations

import importlib.abc
import importlib.machinery
import sys
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class SpriteBatchItem:
    entity: Any
    transform: Any
    sprite: Any
    dest_x: float
    dest_y: float
    dest_width: float
    dest_height: float
    src_x: int
    src_y: int
    src_width: int
    src_height: int
    tint: tuple[int, int, int, int]


class _RenderSystemPatchLoader(importlib.abc.Loader):
    def __init__(self, wrapped: importlib.abc.Loader) -> None:
        self._wrapped = wrapped

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> Any:
        create_module = getattr(self._wrapped, "create_module", None)
        if create_module is None:
            return None
        return create_module(spec)

    def exec_module(self, module: Any) -> None:
        self._wrapped.exec_module(module)
        apply_simple_sprite_batcher(module)
        _remove_patch_finder()


class _RenderSystemPatchFinder(importlib.abc.MetaPathFinder):
    target_module = "engine.systems.render_system"

    def __init__(self) -> None:
        self._active = False

    def find_spec(
        self,
        fullname: str,
        path: Any,
        target: Any = None,
    ) -> importlib.machinery.ModuleSpec | None:
        del target
        if fullname != self.target_module or self._active:
            return None
        self._active = True
        try:
            spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        finally:
            self._active = False
        if spec is None or spec.loader is None:
            return spec
        spec.loader = _RenderSystemPatchLoader(spec.loader)
        return spec


_PATCH_FINDER: _RenderSystemPatchFinder | None = None


def install_simple_sprite_batcher() -> None:
    """Install the import hook that patches RenderSystem after it loads."""
    global _PATCH_FINDER
    existing = sys.modules.get("engine.systems.render_system")
    if existing is not None:
        apply_simple_sprite_batcher(existing)
        return
    if _PATCH_FINDER is not None:
        return
    _PATCH_FINDER = _RenderSystemPatchFinder()
    sys.meta_path.insert(0, _PATCH_FINDER)


def _remove_patch_finder() -> None:
    global _PATCH_FINDER
    if _PATCH_FINDER is not None and _PATCH_FINDER in sys.meta_path:
        sys.meta_path.remove(_PATCH_FINDER)
    _PATCH_FINDER = None


def apply_simple_sprite_batcher(render_system_module: Any) -> None:
    render_system_cls = getattr(render_system_module, "RenderSystem", None)
    if render_system_cls is None or getattr(render_system_cls, "_simple_sprite_batcher_installed", False):
        return

    render_system_cls._simple_sprite_batcher_original_render_pass = render_system_cls._render_pass
    render_system_cls._simple_sprite_batcher_original_build_render_graph = render_system_cls._build_render_graph
    render_system_cls._simple_sprite_batcher_original_copy_stats = render_system_cls._copy_stats
    render_system_cls._simple_sprite_batcher_original_copy_stats_with_tilemap_fallback_draws = (
        render_system_cls._copy_stats_with_tilemap_fallback_draws
    )

    setattr(render_system_cls, "_is_simple_sprite_batchable", _is_simple_sprite_batchable)
    setattr(render_system_cls, "_build_sprite_batch_item", _build_sprite_batch_item)
    setattr(render_system_cls, "_draw_sprite_batch", _draw_sprite_batch)
    setattr(render_system_cls, "_render_batch_commands", _render_batch_commands)
    setattr(render_system_cls, "_render_single_command", _render_single_command)
    setattr(render_system_cls, "_estimate_simple_sprite_batch_stats", _estimate_simple_sprite_batch_stats)
    setattr(render_system_cls, "_apply_simple_sprite_batch_stats_to_graph", _apply_simple_sprite_batch_stats_to_graph)
    setattr(render_system_cls, "_apply_simple_sprite_batch_stats_to_stats", _apply_simple_sprite_batch_stats_to_stats)

    render_system_cls._render_pass = _render_pass_with_simple_sprite_batcher
    render_system_cls._build_render_graph = _build_render_graph_with_simple_sprite_batch_stats
    render_system_cls._copy_stats = _copy_stats_with_simple_sprite_fields
    render_system_cls._copy_stats_with_tilemap_fallback_draws = _copy_stats_with_tilemap_fallback_draws
    render_system_cls._simple_sprite_batcher_installed = True

    _patch_pipeline_executor()


def _patch_pipeline_executor() -> None:
    try:
        from engine.rendering.pipeline_executor import RenderPipelineExecutor2D
    except Exception:
        return
    if getattr(RenderPipelineExecutor2D, "_simple_sprite_batcher_installed", False):
        return
    RenderPipelineExecutor2D._simple_sprite_batcher_original_render_pass = RenderPipelineExecutor2D.render_pass
    RenderPipelineExecutor2D.render_pass = _pipeline_render_pass_with_simple_sprite_batcher
    RenderPipelineExecutor2D._simple_sprite_batcher_installed = True


def _command_get(command: Any, key: str, default: Any = None) -> Any:
    if isinstance(command, dict):
        return command.get(key, default)
    getter = getattr(command, "get", None)
    if callable(getter):
        return getter(key, default)
    return getattr(command, key, default)


def _command_payload(command: Any) -> dict[str, Any]:
    if isinstance(command, dict):
        return command
    to_payload = getattr(command, "to_payload", None)
    if callable(to_payload):
        return to_payload()
    return {}


def _pass_get(pass_data: Any, key: str, default: Any = None) -> Any:
    if isinstance(pass_data, dict):
        return pass_data.get(key, default)
    getter = getattr(pass_data, "get", None)
    if callable(getter):
        return getter(key, default)
    return getattr(pass_data, key, default)


def _pass_set_stats(pass_data: Any, stats: dict[str, Any]) -> None:
    if isinstance(pass_data, dict):
        pass_data["stats"] = stats
    else:
        pass_data.stats = stats


def _texture_key(texture: Any) -> int:
    return int(getattr(texture, "id", 0) or 0)


def _load_sprite_texture(owner: Any, sprite: Any) -> Any:
    return owner._load_texture(
        sprite.get_texture_reference(),
        sprite.texture_path,
        sync_callback=getattr(sprite, "sync_texture_reference", None),
    )


def _is_entity_active(entity: Any) -> bool:
    return bool(getattr(entity, "active", True))


def _is_simple_sprite_batchable(self: Any, entity: Any, transform: Any, sprite: Any, texture: Any = None) -> bool:
    from engine.components.animator import Animator
    from engine.components.polygon2d import Polygon2D

    if entity is None or transform is None or sprite is None:
        return False
    if not _is_entity_active(entity):
        return False
    if not bool(getattr(sprite, "enabled", False)) or not getattr(sprite, "texture_path", ""):
        return False
    animator = entity.get_component(Animator)
    if animator is not None and bool(getattr(animator, "enabled", False)) and getattr(animator, "sprite_sheet", ""):
        return False
    polygon = entity.get_component(Polygon2D)
    if polygon is not None and bool(getattr(polygon, "enabled", False)):
        return False
    if float(getattr(transform, "rotation", 0.0) or 0.0) != 0.0:
        return False
    texture = texture if texture is not None else _load_sprite_texture(self, sprite)
    return _texture_key(texture) != 0


def _build_sprite_batch_item(self: Any, entity: Any, transform: Any, sprite: Any) -> SpriteBatchItem | None:
    texture = _load_sprite_texture(self, sprite)
    if not self._is_simple_sprite_batchable(entity, transform, sprite, texture):
        return None

    src_x = 0
    src_y = 0
    src_w = int(getattr(texture, "width", 0))
    src_h = int(getattr(texture, "height", 0))

    slice_rect = None
    if getattr(sprite, "source_slice", "") and getattr(self, "_asset_service", None) is not None:
        slice_rect = self._asset_service.get_slice_rect(sprite.get_texture_reference(), sprite.source_slice)
    if slice_rect is not None:
        src_x = int(slice_rect.get("x", 0))
        src_y = int(slice_rect.get("y", 0))
        src_w = max(1, int(slice_rect.get("width", 0)))
        src_h = max(1, int(slice_rect.get("height", 0)))

    width = int((sprite.width if sprite.width > 0 else src_w) * transform.scale_x)
    height = int((sprite.height if sprite.height > 0 else src_h) * transform.scale_y)
    dest_x = float(transform.x - (width * sprite.origin_x))
    dest_y = float(transform.y - (height * sprite.origin_y))
    source_width = src_w if not sprite.flip_x else -src_w
    source_height = src_h if not sprite.flip_y else -src_h

    return SpriteBatchItem(
        entity=entity,
        transform=transform,
        sprite=sprite,
        dest_x=dest_x,
        dest_y=dest_y,
        dest_width=float(width),
        dest_height=float(height),
        src_x=src_x,
        src_y=src_y,
        src_width=source_width,
        src_height=source_height,
        tint=tuple(sprite.tint),
    )


def _draw_sprite_batch(self: Any, texture: Any, items: list[SpriteBatchItem]) -> None:
    if not items:
        return

    import pyray as rl

    required = ("rl_set_texture", "rl_begin", "rl_end", "rl_tex_coord2f", "rl_color4ub", "rl_vertex2f", "RL_QUADS")
    if not all(hasattr(rl, name) for name in required):
        # Some pyray/raylib-py builds do not expose rlgl QUADS.  Keep the
        # render visually safe by falling back to the existing per-sprite path.
        for item in items:
            self._draw_sprite(item.transform, item.sprite)
        return

    texture_width = max(1.0, float(getattr(texture, "width", 1) or 1))
    texture_height = max(1.0, float(getattr(texture, "height", 1) or 1))
    rl.rl_set_texture(int(texture.id))
    rl.rl_begin(rl.RL_QUADS)
    for item in items:
        u0 = item.src_x / texture_width
        v0 = item.src_y / texture_height
        u1 = (item.src_x + item.src_width) / texture_width
        v1 = (item.src_y + item.src_height) / texture_height
        x0 = item.dest_x
        y0 = item.dest_y
        x1 = item.dest_x + item.dest_width
        y1 = item.dest_y + item.dest_height
        red, green, blue, alpha = item.tint

        rl.rl_color4ub(red, green, blue, alpha)
        rl.rl_tex_coord2f(u0, v0)
        rl.rl_vertex2f(x0, y0)
        rl.rl_tex_coord2f(u1, v0)
        rl.rl_vertex2f(x1, y0)
        rl.rl_tex_coord2f(u1, v1)
        rl.rl_vertex2f(x1, y1)
        rl.rl_tex_coord2f(u0, v1)
        rl.rl_vertex2f(x0, y1)
    rl.rl_end()
    rl.rl_set_texture(0)


def _render_batch_commands(self: Any, commands: list[Any]) -> None:
    from engine.components.sprite import Sprite
    from engine.components.transform import Transform

    pending_texture: Any = None
    pending_items: list[SpriteBatchItem] = []

    def flush_pending() -> None:
        nonlocal pending_texture, pending_items
        if pending_texture is not None and pending_items:
            self._draw_sprite_batch(pending_texture, pending_items)
        pending_texture = None
        pending_items = []

    for command in commands:
        if _command_get(command, "kind") == "entity":
            entity = _command_get(command, "entity")
            transform = entity.get_component(Transform) if entity is not None else None
            sprite = entity.get_component(Sprite) if entity is not None else None
            item = self._build_sprite_batch_item(entity, transform, sprite) if sprite is not None else None
            if item is not None:
                texture = _load_sprite_texture(self, sprite)
                if pending_texture is None or _texture_key(texture) == _texture_key(pending_texture):
                    pending_texture = texture
                    pending_items.append(item)
                else:
                    flush_pending()
                    pending_texture = texture
                    pending_items.append(item)
                continue
        flush_pending()
        self._render_single_command(command)
    flush_pending()


def _render_single_command(self: Any, command: Any) -> None:
    from engine.components.collider import Collider
    from engine.components.transform import Transform

    kind = _command_get(command, "kind")
    debug_kind = _command_get(command, "debug_kind", "")
    if kind == "entity":
        entity = _command_get(command, "entity")
        transform = entity.get_component(Transform) if entity is not None else None
        if transform is not None:
            self._render_entity(entity, transform)
        return
    if kind == "tilemap_chunk":
        self._draw_tilemap_chunk(_command_payload(command))
        return
    if debug_kind == "collider":
        entity = _command_get(command, "entity")
        transform = entity.get_component(Transform) if entity is not None else None
        collider = entity.get_component(Collider) if entity is not None else None
        if transform is not None and collider is not None:
            self._draw_collider(transform, collider)
        return
    if debug_kind == "joint":
        entity = _command_get(command, "entity")
        if entity is not None:
            self._draw_joint(entity)
        return
    if debug_kind == "selection":
        entity = _command_get(command, "entity")
        if entity is not None:
            self._draw_selection_highlight(entity)
        return
    self._draw_debug_primitive(_command_get(command, "geometry", {}))


def _render_pass_with_simple_sprite_batcher(self: Any, graph: Any, pass_name: str) -> None:
    try:
        from engine.rendering.pipeline_types import FramePlan2D
    except Exception:
        FramePlan2D = ()
    if isinstance(graph, FramePlan2D):
        self._pipeline_executor.render_pass(graph, pass_name)
        return
    pass_data = next((entry for entry in graph["passes"] if _pass_get(entry, "name") == pass_name), None)
    if pass_data is None:
        return
    for batch in _pass_get(pass_data, "batches", []):
        batch_key = _command_get(batch, "key", {})
        self._begin_batch_state(batch_key)
        try:
            self._render_batch_commands(list(_command_get(batch, "commands", [])))
        finally:
            self._end_batch_state(batch_key)


def _pipeline_render_pass_with_simple_sprite_batcher(self: Any, frame_plan: Any, pass_name: str) -> None:
    pass_plan = frame_plan.get_pass(pass_name)
    if pass_plan is None:
        return
    for batch in pass_plan.batches:
        self._owner._begin_batch_state(batch.key)
        try:
            self._owner._render_batch_commands(batch.commands)
        finally:
            self._owner._end_batch_state(batch.key)


def _fallback_draw_call_count(self: Any, command: Any) -> int:
    if _command_get(command, "kind") == "tilemap_chunk":
        return int(self._tilemap_chunk_renderer.command_draw_call_count(_command_payload(command)))
    return 1


def _sprite_candidate_for_fallback(command: Any) -> bool:
    from engine.components.sprite import Sprite

    if _command_get(command, "kind") != "entity":
        return False
    entity = _command_get(command, "entity")
    if entity is None:
        return False
    sprite = entity.get_component(Sprite)
    return sprite is not None and bool(getattr(sprite, "enabled", False)) and bool(getattr(sprite, "texture_path", ""))


def _estimate_simple_sprite_batch_stats(self: Any, batches: list[Any]) -> dict[str, int]:
    from engine.components.sprite import Sprite
    from engine.components.transform import Transform

    stats = {"draw_calls": 0, "sprite_batches": 0, "batched_sprites": 0, "sprite_batch_fallbacks": 0}
    for batch in batches:
        pending_texture: Any = None
        pending_count = 0

        def flush_pending() -> None:
            nonlocal pending_texture, pending_count
            if pending_count > 0:
                stats["draw_calls"] += 1
                stats["sprite_batches"] += 1
                stats["batched_sprites"] += pending_count
            pending_texture = None
            pending_count = 0

        for command in _command_get(batch, "commands", []):
            if _command_get(command, "kind") == "entity":
                entity = _command_get(command, "entity")
                transform = entity.get_component(Transform) if entity is not None else None
                sprite = entity.get_component(Sprite) if entity is not None else None
                texture = _load_sprite_texture(self, sprite) if sprite is not None and getattr(sprite, "texture_path", "") else None
                if sprite is not None and self._is_simple_sprite_batchable(entity, transform, sprite, texture):
                    if pending_texture is None or _texture_key(texture) == _texture_key(pending_texture):
                        pending_texture = texture
                        pending_count += 1
                    else:
                        flush_pending()
                        pending_texture = texture
                        pending_count = 1
                    continue
            flush_pending()
            stats["draw_calls"] += _fallback_draw_call_count(self, command)
            if _sprite_candidate_for_fallback(command):
                stats["sprite_batch_fallbacks"] += 1
        flush_pending()
    return stats


def _apply_simple_sprite_batch_stats_to_graph(self: Any, graph: dict[str, Any]) -> None:
    passes = list(graph.get("passes", []))
    total_draw_calls = 0
    total_sprite_batches = 0
    total_batched_sprites = 0
    total_fallbacks = 0
    pass_stats: dict[str, dict[str, Any]] = {}

    for pass_data in passes:
        pass_name = str(_pass_get(pass_data, "name", ""))
        current_stats = dict(_pass_get(pass_data, "stats", {}))
        estimate = self._estimate_simple_sprite_batch_stats(list(_pass_get(pass_data, "batches", [])))
        current_stats["draw_calls"] = estimate["draw_calls"]
        current_stats["sprite_batches"] = estimate["sprite_batches"]
        current_stats["batched_sprites"] = estimate["batched_sprites"]
        current_stats["sprite_batch_fallbacks"] = estimate["sprite_batch_fallbacks"]
        _pass_set_stats(pass_data, current_stats)
        pass_stats[pass_name] = current_stats
        total_draw_calls += estimate["draw_calls"]
        total_sprite_batches += estimate["sprite_batches"]
        total_batched_sprites += estimate["batched_sprites"]
        total_fallbacks += estimate["sprite_batch_fallbacks"]

    totals = dict(graph.get("totals", {}))
    totals["draw_calls"] = total_draw_calls
    totals["sprite_batches"] = total_sprite_batches
    totals["batched_sprites"] = total_batched_sprites
    totals["sprite_batch_fallbacks"] = total_fallbacks
    totals["passes"] = pass_stats
    graph["totals"] = totals


def _apply_simple_sprite_batch_stats_to_stats(self: Any, stats: dict[str, Any], graph: dict[str, Any]) -> dict[str, Any]:
    scratch = {"passes": list(graph.get("passes", [])), "totals": dict(stats)}
    self._apply_simple_sprite_batch_stats_to_graph(scratch)
    return self._copy_stats(scratch["totals"])


def _build_render_graph_with_simple_sprite_batch_stats(self: Any, *args: Any, **kwargs: Any) -> dict[str, Any]:
    graph = self._simple_sprite_batcher_original_build_render_graph(*args, **kwargs)
    try:
        self._apply_simple_sprite_batch_stats_to_graph(graph)
    except Exception:
        return graph
    return graph


def _copy_stats_with_simple_sprite_fields(self: Any, payload: dict[str, Any]) -> dict[str, Any]:
    stats = self._simple_sprite_batcher_original_copy_stats(payload)
    for key in ("sprite_batches", "batched_sprites", "sprite_batch_fallbacks"):
        stats[key] = int(payload.get(key, 0))
    for pass_name, pass_payload in payload.get("passes", {}).items():
        pass_stats = stats.setdefault("passes", {}).setdefault(str(pass_name), {})
        for key in ("sprite_batches", "batched_sprites", "sprite_batch_fallbacks"):
            pass_stats[key] = int(pass_payload.get(key, 0))
    return stats


def _copy_stats_with_tilemap_fallback_draws(self: Any, payload: dict[str, Any], graph: dict[str, Any]) -> dict[str, Any]:
    stats = self._simple_sprite_batcher_original_copy_stats_with_tilemap_fallback_draws(payload, graph)
    try:
        return self._apply_simple_sprite_batch_stats_to_stats(stats, graph)
    except Exception:
        return stats
