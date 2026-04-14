"""
engine/systems/render_system.py - Sistema de renderizado 2D con render graph minimo.
"""

from __future__ import annotations

from typing import Any, Optional

import pyray as rl
from engine.assets.asset_reference import clone_asset_reference, normalize_asset_reference
from engine.assets.asset_service import AssetService
from engine.components.animator import Animator
from engine.components.camera2d import Camera2D
from engine.components.collider import Collider
from engine.components.joint2d import Joint2D
from engine.components.renderorder2d import RenderOrder2D
from engine.components.renderstyle2d import RenderStyle2D
from engine.components.sprite import Sprite
from engine.components.tilemap import Tilemap
from engine.components.transform import Transform
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.rendering.render_targets import RenderTargetPool
from engine.resources.texture_manager import TextureManager


class RenderSystem:
    """Renderiza entidades, calcula batches y resuelve la camara logica del juego."""

    PLACEHOLDER_WIDTH: int = 32
    PLACEHOLDER_HEIGHT: int = 32
    PLACEHOLDER_COLOR = rl.SKYBLUE

    DEBUG_DRAW_COLLIDERS: bool = False
    PASS_SEQUENCE: tuple[str, ...] = ("World", "Overlay", "Debug")
    TILEMAP_CHUNK_SIZE: int = 16

    def __init__(self) -> None:
        self._texture_manager: TextureManager = TextureManager()
        self._project_service: Any = None
        self._asset_service: AssetService | None = None
        self._asset_resolver: Any = None
        self._render_targets: RenderTargetPool = RenderTargetPool()
        self.debug_draw_colliders: bool = self.DEBUG_DRAW_COLLIDERS
        self.debug_draw_labels: bool = False
        self.debug_draw_tile_chunks: bool = False
        self.debug_draw_camera: bool = False
        self._debug_primitives: list[dict[str, Any]] = []
        self._sorted_entities_cache_key: tuple[int, int, tuple[str, ...]] | None = None
        self._sorted_entities_cache: list[Entity] = []
        self._render_graph_cache_key: tuple[int, int, int, tuple[str, ...], bool, bool, bool, bool, tuple[Any, ...], tuple[int, int]] | None = None
        self._render_graph_cache: dict[str, Any] = {"passes": [], "totals": {}}
        self._tilemap_chunk_cache: dict[tuple[int, str, int, int], dict[str, Any]] = {}
        self._last_render_stats: dict[str, Any] = {
            "render_entities": 0,
            "draw_calls": 0,
            "batches": 0,
            "state_changes": 0,
            "tilemap_chunks": 0,
            "tilemap_chunk_rebuilds": 0,
            "pass_count": len(self.PASS_SEQUENCE),
            "render_target_passes": 0,
            "render_target_composites": 0,
            "sort_cache": {"hits": 0, "misses": 0},
            "passes": {},
        }
        self._sort_cache_hits: int = 0
        self._sort_cache_misses: int = 0

    def set_project_service(self, project_service: Any) -> None:
        self._project_service = project_service
        self._asset_service = AssetService(project_service) if project_service is not None else None
        self._asset_resolver = self._asset_service.get_asset_resolver() if self._asset_service is not None else None

    def reset_project_resources(self) -> None:
        self._texture_manager.unload_all()

    def set_debug_options(
        self,
        *,
        draw_colliders: bool | None = None,
        draw_labels: bool | None = None,
        draw_tile_chunks: bool | None = None,
        draw_camera: bool | None = None,
    ) -> None:
        if draw_colliders is not None:
            self.debug_draw_colliders = bool(draw_colliders)
        if draw_labels is not None:
            self.debug_draw_labels = bool(draw_labels)
        if draw_tile_chunks is not None:
            self.debug_draw_tile_chunks = bool(draw_tile_chunks)
        if draw_camera is not None:
            self.debug_draw_camera = bool(draw_camera)

    def set_debug_primitives(self, primitives: list[dict[str, Any]]) -> None:
        self._debug_primitives = [self._normalize_debug_primitive(item) for item in primitives]

    def clear_debug_primitives(self) -> None:
        self._debug_primitives = []

    def get_debug_state(self) -> dict[str, Any]:
        return {
            "draw_colliders": bool(self.debug_draw_colliders),
            "draw_labels": bool(self.debug_draw_labels),
            "draw_tile_chunks": bool(self.debug_draw_tile_chunks),
            "draw_camera": bool(self.debug_draw_camera),
            "primitive_count": len(self._debug_primitives),
        }

    def get_last_render_stats(self) -> dict[str, Any]:
        return self._copy_stats(self._last_render_stats)

    def get_last_render_graph(self) -> dict[str, Any]:
        return self._public_graph(self._render_graph_cache)

    def get_debug_geometry_dump(self, world: World, viewport_size: Optional[tuple[float, float]] = None) -> dict[str, Any]:
        graph = self._public_graph(self._build_render_graph(world, viewport_size=viewport_size))
        debug_pass = next((entry for entry in graph.get("passes", []) if entry.get("name") == "Debug"), {"commands": [], "stats": {}})
        return {
            "pass": "Debug",
            "viewport": {
                "width": int(self._normalize_viewport_size(viewport_size)[0]),
                "height": int(self._normalize_viewport_size(viewport_size)[1]),
            },
            "commands": list(debug_pass.get("commands", [])),
            "stats": dict(debug_pass.get("stats", {})),
        }

    def profile_world(self, world: World, viewport_size: Optional[tuple[float, float]] = None) -> dict[str, Any]:
        frame_plan = self._build_frame_plan(world, viewport_size=viewport_size)
        return self._copy_stats(frame_plan["totals"])

    def render(
        self,
        world: World,
        override_camera: Optional[rl.Camera2D] = None,
        use_world_camera: bool = True,
        viewport_size: Optional[tuple[float, float]] = None,
        allow_render_targets: bool = True,
    ) -> None:
        frame_plan = self._build_frame_plan(world, viewport_size=viewport_size)
        graph = frame_plan["graph"]
        backend_ready = bool(hasattr(rl, "is_window_ready") and rl.is_window_ready())

        if not backend_ready:
            totals = self._copy_stats(frame_plan["totals"])
            if not allow_render_targets:
                totals["render_target_passes"] = 0
                totals["render_target_composites"] = 0
            self._last_render_stats = totals
            return

        camera = override_camera
        if camera is None and use_world_camera:
            camera = self._build_camera_from_world(world, viewport_size=viewport_size)
        if camera is not None:
            rl.begin_mode_2d(camera)

        self._render_pass(graph, "World")
        self._render_pass(graph, "Overlay")

        if not allow_render_targets:
            self._render_pass(graph, "Debug")
            if camera is not None:
                rl.end_mode_2d()
            totals = self._copy_stats(frame_plan["totals"])
            totals["render_target_passes"] = 0
            totals["render_target_composites"] = 0
            self._last_render_stats = totals
            return

        if camera is not None:
            rl.end_mode_2d()

        self._render_targets.begin_frame()
        self._render_debug_overlay(frame_plan, camera=camera, viewport_size=viewport_size)
        self._render_minimap(world, frame_plan, viewport_size=viewport_size)
        target_metrics = self._render_targets.get_frame_metrics()
        totals = self._copy_stats(frame_plan["totals"])
        totals["render_target_passes"] = target_metrics.get("passes", 0)
        totals["render_target_composites"] = target_metrics.get("composites", 0)
        self._last_render_stats = totals

    def _sorted_render_entities(self, world: World) -> list[Entity]:
        sorting_layers = self._get_sorting_layers(world)
        cache_key = (id(world), int(getattr(world, "version", -1)), tuple(sorting_layers))
        if self._sorted_entities_cache_key == cache_key:
            self._sort_cache_hits += 1
            return self._sorted_entities_cache

        self._sort_cache_misses += 1
        entities = world.get_entities_with(Transform)
        sorting_index = {name: index for index, name in enumerate(sorting_layers)}
        pass_index = {name: index for index, name in enumerate(self.PASS_SEQUENCE)}

        def sort_key(entity: Entity) -> tuple[int, int, int, int, int]:
            render_order = entity.get_component(RenderOrder2D)
            transform = entity.get_component(Transform)
            layer_name = self._get_sorting_layer(render_order)
            order_in_layer = self._get_order_in_layer(render_order)
            render_pass = self._get_render_pass(render_order)
            layer_index = sorting_index.get(layer_name, len(sorting_index))
            depth = transform.depth if transform is not None else 0
            return (pass_index.get(render_pass, 0), layer_index, order_in_layer, depth, entity.id)

        self._sorted_entities_cache = sorted(entities, key=sort_key)
        self._sorted_entities_cache_key = cache_key
        return self._sorted_entities_cache

    def _build_render_graph(self, world: World, viewport_size: Optional[tuple[float, float]] = None) -> dict[str, Any]:
        sorting_layers = self._get_sorting_layers(world)
        normalized_viewport = self._normalize_viewport_size(viewport_size)
        cache_key = (
            id(world),
            int(getattr(world, "version", -1)),
            int(getattr(world, "selection_version", -1)),
            tuple(sorting_layers),
            bool(self.debug_draw_colliders),
            bool(self.debug_draw_labels),
            bool(self.debug_draw_tile_chunks),
            bool(self.debug_draw_camera),
            self._debug_overlay_signature(),
            normalized_viewport,
        )
        if self._render_graph_cache_key == cache_key:
            return {
                "passes": self._render_graph_cache.get("passes", []),
                "totals": {
                    **dict(self._render_graph_cache.get("totals", {})),
                    "tilemap_chunk_rebuilds": 0,
                },
            }

        sorted_entities = self._sorted_render_entities(world)
        pass_commands: dict[str, list[dict[str, Any]]] = {name: [] for name in self.PASS_SEQUENCE}
        tilemap_chunks = 0
        tilemap_chunk_rebuilds = 0

        for entity in sorted_entities:
            transform = entity.get_component(Transform)
            if transform is None:
                continue
            tilemap = entity.get_component(Tilemap)
            render_order = entity.get_component(RenderOrder2D)
            pass_name = self._get_render_pass(render_order)
            sorting_layer = self._get_sorting_layer(render_order)
            order_in_layer = self._get_order_in_layer(render_order)
            if tilemap is not None and tilemap.enabled:
                chunk_commands, rebuilds = self._build_tilemap_commands(entity, transform, tilemap, sorting_layer, order_in_layer)
                pass_commands[pass_name].extend(chunk_commands)
                tilemap_chunks += len(chunk_commands)
                tilemap_chunk_rebuilds += rebuilds
                if self.debug_draw_tile_chunks:
                    for chunk_command in chunk_commands:
                        geometry = self._build_tile_chunk_geometry(entity, chunk_command)
                        if geometry is not None:
                            self._append_debug_command(
                                pass_commands["Debug"],
                                {
                                    "kind": "debug",
                                    "debug_kind": "tile_chunk",
                                    "entity": entity,
                                    "entity_name": entity.name,
                                    "chunk_id": chunk_command.get("chunk_id", ""),
                                    "geometry": geometry,
                                },
                            )
                continue
            pass_commands[pass_name].append(
                {
                    "kind": "entity",
                    "entity": entity,
                    "entity_name": entity.name,
                    "sorting_layer": sorting_layer,
                    "order_in_layer": order_in_layer,
                    "batch_key": self._build_batch_key(entity, sorting_layer),
                }
            )

        if self.debug_draw_colliders:
            for entity in sorted_entities:
                transform = entity.get_component(Transform)
                collider = entity.get_component(Collider)
                if transform is None or collider is None or not collider.enabled:
                    continue
                self._append_debug_command(
                    pass_commands["Debug"],
                    {
                        "kind": "debug",
                        "debug_kind": "collider",
                        "entity": entity,
                        "entity_name": entity.name,
                        "geometry": self._build_collider_geometry(transform, collider),
                    }
                )
            for entity in sorted_entities:
                transform = entity.get_component(Transform)
                joint = entity.get_component(Joint2D)
                if transform is None or joint is None or not joint.enabled or not joint.connected_entity:
                    continue
                if world.get_entity_by_name(joint.connected_entity) is None:
                    continue
                self._append_debug_command(
                    pass_commands["Debug"],
                    {
                        "kind": "debug",
                        "debug_kind": "joint",
                        "entity": entity,
                        "entity_name": entity.name,
                        "geometry": self._build_joint_geometry(entity),
                    }
                )

        if world.selected_entity_name:
            selected_entity = world.get_entity_by_name(world.selected_entity_name)
            if selected_entity is not None:
                self._append_debug_command(
                    pass_commands["Debug"],
                    {
                        "kind": "debug",
                        "debug_kind": "selection",
                        "entity": selected_entity,
                        "entity_name": selected_entity.name,
                        "geometry": self._build_selection_geometry(selected_entity),
                    }
                )

        if self.debug_draw_camera:
            camera_geometry = self._build_camera_geometry(world, normalized_viewport)
            if camera_geometry is not None:
                self._append_debug_command(
                    pass_commands["Debug"],
                    {
                        "kind": "debug",
                        "debug_kind": "camera",
                        "entity_name": "__camera__",
                        "geometry": camera_geometry,
                    },
                )

        for primitive in self._debug_primitives:
            self._append_debug_command(
                pass_commands["Debug"],
                {
                    "kind": "debug",
                    "debug_kind": primitive.get("kind", "primitive"),
                    "entity_name": primitive.get("entity_name", "__debug__"),
                    "geometry": primitive,
                },
            )

        passes: list[dict[str, Any]] = []
        total_draw_calls = 0
        total_batches = 0
        total_state_changes = 0
        total_entities = 0

        for pass_name in self.PASS_SEQUENCE:
            commands = pass_commands[pass_name]
            batches = self._build_batches(commands)
            entity_count = sum(1 for command in commands if command["kind"] == "entity")
            draw_calls = len(commands)
            batch_count = len(batches)
            state_changes = max(0, batch_count - 1)
            passes.append(
                {
                    "name": pass_name,
                    "commands": commands,
                    "batches": batches,
                    "stats": {
                        "render_entities": entity_count,
                        "draw_calls": draw_calls,
                        "batches": batch_count,
                        "state_changes": state_changes,
                    },
                }
            )
            total_entities += entity_count
            total_draw_calls += draw_calls
            total_batches += batch_count
            total_state_changes += state_changes

        totals = {
            "render_entities": total_entities,
            "draw_calls": total_draw_calls,
            "batches": total_batches,
            "state_changes": total_state_changes,
            "tilemap_chunks": tilemap_chunks,
            "tilemap_chunk_rebuilds": tilemap_chunk_rebuilds,
            "pass_count": len(self.PASS_SEQUENCE),
            "sort_cache": {"hits": self._sort_cache_hits, "misses": self._sort_cache_misses},
            "passes": {
                pass_data["name"]: dict(pass_data["stats"])
                for pass_data in passes
            },
        }
        graph = {
            "passes": passes,
            "totals": totals,
        }
        self._render_graph_cache_key = cache_key
        self._render_graph_cache = graph
        return graph

    def _build_frame_plan(
        self,
        world: World,
        *,
        viewport_size: Optional[tuple[float, float]],
    ) -> dict[str, Any]:
        graph = self._build_render_graph(world, viewport_size=viewport_size)
        minimap_config = self._get_minimap_config(world)
        debug_commands = next((entry["commands"] for entry in graph["passes"] if entry["name"] == "Debug"), [])
        target_jobs: list[dict[str, Any]] = []
        if debug_commands:
            width, height = self._normalize_viewport_size(viewport_size)
            target_jobs.append(
                {
                    "name": "selection_overlay",
                    "kind": "debug_overlay",
                    "width": width,
                    "height": height,
                }
            )
        if minimap_config.get("enabled"):
            target_jobs.append(
                {
                    "name": "minimap",
                    "kind": "minimap",
                    "width": int(minimap_config["width"]),
                    "height": int(minimap_config["height"]),
                    "margin": int(minimap_config["margin"]),
                }
            )

        totals = self._copy_stats(graph["totals"])
        totals["render_target_passes"] = len(target_jobs)
        totals["render_target_composites"] = len(target_jobs)
        return {
            "graph": graph,
            "render_targets": target_jobs,
            "totals": totals,
        }

    def _build_batches(self, commands: list[dict[str, Any]]) -> list[dict[str, Any]]:
        batches: list[dict[str, Any]] = []
        current: dict[str, Any] | None = None

        for command in commands:
            batch_key = dict(command["batch_key"])
            if current is None or current["key"] != batch_key:
                current = {"key": batch_key, "commands": []}
                batches.append(current)
            current["commands"].append(command)

        return batches

    def _render_pass(self, graph: dict[str, Any], pass_name: str) -> None:
        pass_data = next((entry for entry in graph["passes"] if entry["name"] == pass_name), None)
        if pass_data is None:
            return
        for batch in pass_data["batches"]:
            self._begin_batch_state(batch["key"])
            try:
                for command in batch["commands"]:
                    if command["kind"] == "entity":
                        entity = command["entity"]
                        transform = entity.get_component(Transform)
                        if transform is None:
                            continue
                        self._render_entity(entity, transform)
                    elif command["kind"] == "tilemap_chunk":
                        self._draw_tilemap_chunk(command)
                    elif command["debug_kind"] == "collider":
                        entity = command["entity"]
                        transform = entity.get_component(Transform)
                        collider = entity.get_component(Collider)
                        if transform is not None and collider is not None:
                            self._draw_collider(transform, collider)
                    elif command["debug_kind"] == "joint":
                        self._draw_joint(command["entity"])
                    elif command["debug_kind"] == "selection":
                        self._draw_selection_highlight(command["entity"])
                    else:
                        self._draw_debug_primitive(command.get("geometry", {}))
            finally:
                self._end_batch_state(batch["key"])

    def _render_debug_overlay(
        self,
        frame_plan: dict[str, Any],
        *,
        camera: Optional[rl.Camera2D],
        viewport_size: Optional[tuple[float, float]],
    ) -> None:
        debug_commands = next((entry["commands"] for entry in frame_plan["graph"]["passes"] if entry["name"] == "Debug"), [])
        if not debug_commands:
            return
        width, height = self._normalize_viewport_size(viewport_size)
        self._render_targets.begin("selection_overlay", width, height, rl.Color(0, 0, 0, 0))
        try:
            if camera is not None:
                rl.begin_mode_2d(camera)
            for command in debug_commands:
                if command["debug_kind"] == "collider":
                    entity = command["entity"]
                    transform = entity.get_component(Transform)
                    collider = entity.get_component(Collider)
                    if transform is not None and collider is not None:
                        self._draw_collider(transform, collider)
                elif command["debug_kind"] == "joint":
                    self._draw_joint(command["entity"])
                elif command["debug_kind"] == "selection":
                    self._draw_selection_highlight(command["entity"])
                else:
                    self._draw_debug_primitive(command.get("geometry", {}))
            if camera is not None:
                rl.end_mode_2d()
        finally:
            self._render_targets.end()

        destination = rl.Rectangle(0, 0, width, height)
        self._render_targets.compose("selection_overlay", destination, rl.WHITE)

    def _render_minimap(
        self,
        world: World,
        frame_plan: dict[str, Any],
        *,
        viewport_size: Optional[tuple[float, float]],
    ) -> None:
        minimap_config = self._get_minimap_config(world)
        if not minimap_config.get("enabled"):
            return

        width = int(minimap_config["width"])
        height = int(minimap_config["height"])
        margin = int(minimap_config["margin"])
        self._render_targets.begin("minimap", width, height, rl.Color(12, 14, 18, 235))
        try:
            renderables = [command["entity"] for command in next((entry["commands"] for entry in frame_plan["graph"]["passes"] if entry["name"] == "World"), []) if command["kind"] == "entity"]
            bounds = self._compute_minimap_bounds(renderables)
            for entity in renderables:
                transform = entity.get_component(Transform)
                if transform is None:
                    continue
                point = self._project_to_minimap(transform.x, transform.y, bounds, width, height)
                sprite = entity.get_component(Sprite)
                color = rl.LIGHTGRAY if sprite is None else rl.Color(*sprite.tint)
                rl.draw_circle(int(point[0]), int(point[1]), 2.0, color)
            rl.draw_rectangle_lines(0, 0, width, height, rl.Color(100, 140, 180, 255))
        finally:
            self._render_targets.end()

        viewport_width, _ = self._normalize_viewport_size(viewport_size)
        destination = rl.Rectangle(float(viewport_width - width - margin), float(margin), float(width), float(height))
        self._render_targets.compose("minimap", destination, rl.WHITE)

    def _build_batch_key(self, entity: Entity, sorting_layer: str) -> dict[str, str]:
        style = entity.get_component(RenderStyle2D)
        sprite = entity.get_component(Sprite)
        animator = entity.get_component(Animator)

        material_id = RenderStyle2D.DEFAULT_MATERIAL_ID
        shader_id = RenderStyle2D.DEFAULT_SHADER_ID
        blend_mode = RenderStyle2D.DEFAULT_BLEND_MODE
        atlas_id = ""
        if style is not None and style.enabled:
            material_payload = self._resolve_material_payload(style)
            material_id = str(material_payload.get("material_id") or style.material_id or material_id)
            shader_id = str(material_payload.get("shader_id") or style.shader_id or shader_id)
            blend_mode = str(material_payload.get("blend_mode") or style.blend_mode or blend_mode)
            atlas_id = str(style.atlas_id or "")

        locator: Any = ""
        if animator is not None and animator.enabled and animator.sprite_sheet:
            locator = animator.get_sprite_sheet_reference()
        elif sprite is not None and sprite.enabled and sprite.texture_path:
            locator = sprite.get_texture_reference()

        resolved_atlas_id = atlas_id or self._resolve_atlas_id(locator)
        if not resolved_atlas_id:
            resolved_atlas_id = "__placeholder__"

        return {
            "atlas_id": resolved_atlas_id,
            "material_id": material_id,
            "shader_id": shader_id,
            "blend_mode": blend_mode,
            "layer": sorting_layer,
        }

    def _build_tilemap_commands(
        self,
        entity: Entity,
        transform: Transform,
        tilemap: Tilemap,
        sorting_layer: str,
        order_in_layer: int,
    ) -> tuple[list[dict[str, Any]], int]:
        del transform
        commands: list[dict[str, Any]] = []
        rebuilds = 0
        live_keys: set[tuple[int, str, int, int]] = set()
        tileset_ref = tilemap.get_tileset_reference()
        fallback_atlas_id = self._resolve_atlas_id(tileset_ref)
        if not fallback_atlas_id:
            fallback_atlas_id = str(tileset_ref.get("guid") or tileset_ref.get("path") or "__tilemap__")
        for layer_index, layer in enumerate(tilemap.layers):
            if not bool(layer.get("visible", True)):
                continue
            chunks = self._partition_tilemap_layer(tilemap, layer)
            for (chunk_x, chunk_y), chunk_tiles in sorted(chunks.items()):
                cache_key = (int(entity.id), str(layer.get("name", f"Layer_{layer_index}")), int(chunk_x), int(chunk_y))
                live_keys.add(cache_key)
                signature = self._tilemap_chunk_signature(tilemap, layer, chunk_tiles)
                cached = self._tilemap_chunk_cache.get(cache_key)
                if cached is None or cached.get("signature") != signature:
                    chunk_data = self._build_tilemap_chunk_data(tilemap, layer, chunk_x, chunk_y, chunk_tiles)
                    cached = {
                        "signature": signature,
                        "data": chunk_data,
                    }
                    self._tilemap_chunk_cache[cache_key] = cached
                    rebuilds += 1
                chunk_atlas_id = self._tilemap_chunk_atlas_id(cached["data"], fallback_atlas_id)
                commands.append(
                    {
                        "kind": "tilemap_chunk",
                        "entity": entity,
                        "entity_name": entity.name,
                        "sorting_layer": sorting_layer,
                        "order_in_layer": order_in_layer + layer_index,
                        "chunk_id": f"{layer.get('name', f'Layer_{layer_index}')}/{chunk_x},{chunk_y}",
                        "chunk_data": cached["data"],
                        "batch_key": {
                            "atlas_id": chunk_atlas_id,
                            "material_id": "tilemap_chunk",
                            "shader_id": "default",
                            "blend_mode": "alpha",
                            "layer": sorting_layer,
                            "chunk": f"{chunk_x},{chunk_y}",
                        },
                    }
                )
        stale_keys = [key for key in self._tilemap_chunk_cache.keys() if key[0] == int(entity.id) and key not in live_keys]
        for key in stale_keys:
            self._tilemap_chunk_cache.pop(key, None)
        return commands, rebuilds

    def _partition_tilemap_layer(self, tilemap: Tilemap, layer: dict[str, Any]) -> dict[tuple[int, int], list[dict[str, Any]]]:
        chunks: dict[tuple[int, int], list[dict[str, Any]]] = {}
        for key, tile in layer.get("tiles", {}).items():
            x_value, y_value = key.split(",", 1)
            tile_x = int(x_value)
            tile_y = int(y_value)
            chunk = (tile_x // self.TILEMAP_CHUNK_SIZE, tile_y // self.TILEMAP_CHUNK_SIZE)
            chunks.setdefault(chunk, []).append(
                {
                    "x": tile_x,
                    "y": tile_y,
                    "tile_id": str(tile.get("tile_id", "")),
                    "flags": list(tile.get("flags", [])),
                    "tags": list(tile.get("tags", [])),
                    "custom": dict(tile.get("custom", {})),
                    "source": dict(tile.get("source", {})),
                }
            )
        return chunks

    def _tilemap_chunk_signature(self, tilemap: Tilemap, layer: dict[str, Any], chunk_tiles: list[dict[str, Any]]) -> tuple[Any, ...]:
        tileset_ref = tilemap.get_tileset_reference()
        layer_source = normalize_asset_reference(layer.get("tilemap_source"))
        return (
            int(tilemap.cell_width),
            int(tilemap.cell_height),
            str(tilemap.orientation),
            str(tileset_ref.get("guid", "")),
            str(tileset_ref.get("path", "")),
            int(tilemap.tileset_tile_width),
            int(tilemap.tileset_tile_height),
            int(tilemap.tileset_columns),
            int(tilemap.tileset_spacing),
            int(tilemap.tileset_margin),
            str(layer.get("name", "")),
            bool(layer.get("visible", True)),
            float(layer.get("opacity", 1.0)),
            float(layer.get("offset_x", 0.0)),
            float(layer.get("offset_y", 0.0)),
            str(layer_source.get("guid", "")),
            str(layer_source.get("path", "")),
            tuple(
                (
                    int(tile["x"]),
                    int(tile["y"]),
                    str(tile["tile_id"]),
                    tuple(tile.get("flags", [])),
                    tuple(tile.get("tags", [])),
                    tuple(sorted(tile.get("custom", {}).items())),
                    str(tile.get("source", {}).get("guid", "")),
                    str(tile.get("source", {}).get("path", "")),
                )
                for tile in sorted(chunk_tiles, key=lambda item: (int(item["y"]), int(item["x"]), str(item["tile_id"])))
            ),
        )

    def _build_tilemap_chunk_data(
        self,
        tilemap: Tilemap,
        layer: dict[str, Any],
        chunk_x: int,
        chunk_y: int,
        chunk_tiles: list[dict[str, Any]],
    ) -> dict[str, Any]:
        opacity = max(0.0, min(1.0, float(layer.get("opacity", 1.0))))
        layer_offset_x = float(layer.get("offset_x", 0.0))
        layer_offset_y = float(layer.get("offset_y", 0.0))
        tint = [255, 255, 255, int(255 * opacity)]
        tiles = []
        min_x: float | None = None
        min_y: float | None = None
        max_x: float | None = None
        max_y: float | None = None
        for tile in sorted(chunk_tiles, key=lambda item: (int(item["y"]), int(item["x"]), str(item["tile_id"]))):
            asset_ref = self._resolve_tile_asset_reference(tilemap, layer, tile)
            source_rect, resolution = self._resolve_tile_source_rect(tilemap, asset_ref, tile)
            dest_x = float(int(tile["x"]) * int(tilemap.cell_width)) + layer_offset_x
            dest_y = float(int(tile["y"]) * int(tilemap.cell_height)) + layer_offset_y
            dest_width = int(tilemap.cell_width)
            dest_height = int(tilemap.cell_height)
            resolved = source_rect is not None and bool(asset_ref.get("guid") or asset_ref.get("path"))
            if resolved:
                min_x = dest_x if min_x is None else min(min_x, dest_x)
                min_y = dest_y if min_y is None else min(min_y, dest_y)
                max_x = (dest_x + dest_width) if max_x is None else max(max_x, dest_x + dest_width)
                max_y = (dest_y + dest_height) if max_y is None else max(max_y, dest_y + dest_height)
            tiles.append(
                {
                    "x": int(tile["x"]),
                    "y": int(tile["y"]),
                    "tile_id": str(tile["tile_id"]),
                    "width": dest_width,
                    "height": dest_height,
                    "texture": clone_asset_reference(asset_ref),
                    "texture_path": str(asset_ref.get("path", "")),
                    "source_rect": dict(source_rect or {}),
                    "dest": {
                        "x": dest_x,
                        "y": dest_y,
                        "width": dest_width,
                        "height": dest_height,
                    },
                    "tint": list(tint),
                    "resolved": bool(resolved),
                    "resolution": resolution if resolved else "unresolved",
                }
            )
        bounds = {
            "x": float(min_x or 0.0),
            "y": float(min_y or 0.0),
            "width": float((max_x - min_x) if min_x is not None and max_x is not None else 0.0),
            "height": float((max_y - min_y) if min_y is not None and max_y is not None else 0.0),
        }
        return {
            "layer_name": str(layer.get("name", "")),
            "chunk_x": int(chunk_x),
            "chunk_y": int(chunk_y),
            "tiles": tiles,
            "bounds": bounds,
            "unresolved_tiles": sum(1 for tile in tiles if not tile.get("resolved", False)),
        }

    def _tile_color(self, tile_id: str, opacity: float) -> tuple[int, int, int, int]:
        hashed = abs(hash(tile_id or "tile"))
        red = 60 + (hashed % 160)
        green = 60 + ((hashed // 13) % 160)
        blue = 60 + ((hashed // 29) % 160)
        alpha = int(255 * opacity)
        return (red, green, blue, alpha)

    def _resolve_material_payload(self, style: RenderStyle2D) -> dict[str, Any]:
        material_ref = style.get_material_reference()
        if self._asset_service is None or not (material_ref.get("guid") or material_ref.get("path")):
            return {}
        material = self._asset_service.load_material_definition(material_ref)
        return {
            "material_id": material_ref.get("guid") or material_ref.get("path") or style.material_id,
            "shader_id": material.shader_id,
            "blend_mode": material.blend_mode,
            "tags": list(material.tags),
            "parameters": dict(material.parameters),
        }

    def _begin_batch_state(self, batch_key: dict[str, Any]) -> None:
        blend_mode = str(batch_key.get("blend_mode", "alpha")).lower()
        if blend_mode == "additive":
            rl.begin_blend_mode(rl.BLEND_ADDITIVE)
        elif blend_mode == "multiplied" and hasattr(rl, "BLEND_MULTIPLIED"):
            rl.begin_blend_mode(rl.BLEND_MULTIPLIED)

    def _end_batch_state(self, batch_key: dict[str, Any]) -> None:
        blend_mode = str(batch_key.get("blend_mode", "alpha")).lower()
        if blend_mode in {"additive", "multiplied"}:
            rl.end_blend_mode()

    def _resolve_atlas_id(self, locator: Any) -> str:
        if not locator:
            return ""
        entry = self._asset_resolver.resolve_entry(locator) if self._asset_resolver is not None else None
        if entry is None:
            if isinstance(locator, dict):
                return str(locator.get("guid") or locator.get("path") or "")
            return str(locator)

        atlas_id = ""
        if self._asset_service is not None:
            metadata = self._asset_service.load_metadata(entry.get("path", ""))
            import_settings = metadata.get("import_settings", {})
            atlas_id = str(import_settings.get("atlas_id") or metadata.get("atlas_id") or "")
        return atlas_id or str(entry.get("guid") or entry.get("path") or "")

    def _get_minimap_config(self, world: World) -> dict[str, Any]:
        render_2d = dict(world.feature_metadata.get("render_2d", {}))
        minimap = dict(render_2d.get("minimap", {}))
        return {
            "enabled": bool(minimap.get("enabled", False)),
            "width": max(64, int(minimap.get("width", 180))),
            "height": max(64, int(minimap.get("height", 120))),
            "margin": max(0, int(minimap.get("margin", 12))),
        }

    def _normalize_viewport_size(self, viewport_size: Optional[tuple[float, float]]) -> tuple[int, int]:
        if viewport_size is None:
            if hasattr(rl, "is_window_ready") and rl.is_window_ready():
                return (max(1, int(rl.get_screen_width())), max(1, int(rl.get_screen_height())))
            return (800, 600)
        return (max(1, int(viewport_size[0])), max(1, int(viewport_size[1])))

    def _compute_minimap_bounds(self, entities: list[Entity]) -> tuple[float, float, float, float]:
        min_x = min((entity.get_component(Transform).x for entity in entities if entity.get_component(Transform) is not None), default=-100.0)
        max_x = max((entity.get_component(Transform).x for entity in entities if entity.get_component(Transform) is not None), default=100.0)
        min_y = min((entity.get_component(Transform).y for entity in entities if entity.get_component(Transform) is not None), default=-100.0)
        max_y = max((entity.get_component(Transform).y for entity in entities if entity.get_component(Transform) is not None), default=100.0)
        if min_x == max_x:
            max_x += 1.0
        if min_y == max_y:
            max_y += 1.0
        return (min_x, min_y, max_x, max_y)

    def _project_to_minimap(
        self,
        x: float,
        y: float,
        bounds: tuple[float, float, float, float],
        width: int,
        height: int,
    ) -> tuple[float, float]:
        min_x, min_y, max_x, max_y = bounds
        normalized_x = (x - min_x) / max(1e-5, max_x - min_x)
        normalized_y = (y - min_y) / max(1e-5, max_y - min_y)
        return (
            8.0 + normalized_x * max(1.0, width - 16.0),
            8.0 + normalized_y * max(1.0, height - 16.0),
        )

    def _get_sorting_layers(self, world: World) -> list[str]:
        raw_layers = world.feature_metadata.get("render_2d", {}).get("sorting_layers", ["Default"])
        normalized: list[str] = ["Default"]
        for layer in raw_layers:
            layer_name = str(layer or "").strip()
            if not layer_name or layer_name in normalized:
                continue
            normalized.append(layer_name)
        return normalized

    def _get_render_pass(self, render_order: RenderOrder2D | None) -> str:
        if render_order is None or not render_order.enabled:
            return RenderOrder2D.DEFAULT_RENDER_PASS
        return RenderOrder2D._normalize_render_pass(render_order.render_pass)

    def _get_sorting_layer(self, render_order: RenderOrder2D | None) -> str:
        if render_order is None or not render_order.enabled:
            return "Default"
        return str(render_order.sorting_layer or "Default")

    def _get_order_in_layer(self, render_order: RenderOrder2D | None) -> int:
        if render_order is None or not render_order.enabled:
            return 0
        return int(render_order.order_in_layer)

    def _public_graph(self, graph: dict[str, Any]) -> dict[str, Any]:
        public_passes: list[dict[str, Any]] = []
        for pass_data in graph.get("passes", []):
            public_passes.append(
                {
                    "name": pass_data.get("name", ""),
                    "commands": [
                        {
                            "kind": command.get("kind", ""),
                            "debug_kind": command.get("debug_kind", ""),
                            "entity_name": command.get("entity_name", ""),
                            "chunk_id": command.get("chunk_id", ""),
                            "sorting_layer": command.get("sorting_layer", ""),
                            "order_in_layer": command.get("order_in_layer", 0),
                            "batch_key": dict(command.get("batch_key", {})),
                            "chunk_data": self._clone_geometry(command.get("chunk_data")),
                            "geometry": self._clone_geometry(command.get("geometry")),
                        }
                        for command in pass_data.get("commands", [])
                    ],
                    "batches": [
                        {
                            "key": dict(batch.get("key", {})),
                            "entity_names": [command.get("entity_name", "") for command in batch.get("commands", [])],
                        }
                        for batch in pass_data.get("batches", [])
                    ],
                    "stats": dict(pass_data.get("stats", {})),
                }
            )
        return {
            "passes": public_passes,
            "totals": self._copy_stats(graph.get("totals", {})),
        }

    def _copy_stats(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "render_entities": int(payload.get("render_entities", 0)),
            "draw_calls": int(payload.get("draw_calls", 0)),
            "batches": int(payload.get("batches", 0)),
            "state_changes": int(payload.get("state_changes", 0)),
            "tilemap_chunks": int(payload.get("tilemap_chunks", 0)),
            "tilemap_chunk_rebuilds": int(payload.get("tilemap_chunk_rebuilds", 0)),
            "pass_count": int(payload.get("pass_count", len(self.PASS_SEQUENCE))),
            "render_target_passes": int(payload.get("render_target_passes", 0)),
            "render_target_composites": int(payload.get("render_target_composites", 0)),
            "sort_cache": {
                "hits": int(payload.get("sort_cache", {}).get("hits", 0)),
                "misses": int(payload.get("sort_cache", {}).get("misses", 0)),
            },
            "passes": {
                str(name): {
                    "render_entities": int(stats.get("render_entities", 0)),
                    "draw_calls": int(stats.get("draw_calls", 0)),
                    "batches": int(stats.get("batches", 0)),
                    "state_changes": int(stats.get("state_changes", 0)),
                }
                for name, stats in payload.get("passes", {}).items()
            },
        }

    def _build_camera_from_world(
        self,
        world: World,
        viewport_size: Optional[tuple[float, float]] = None,
    ) -> Optional[rl.Camera2D]:
        primary_entity = None
        for entity in world.get_entities_with(Transform, Camera2D):
            camera_component = entity.get_component(Camera2D)
            if camera_component is not None and camera_component.enabled and camera_component.is_primary:
                primary_entity = entity
                break
        if primary_entity is None:
            return None

        transform = primary_entity.get_component(Transform)
        camera_component = primary_entity.get_component(Camera2D)
        if transform is None or camera_component is None:
            return None

        target_x = transform.x
        target_y = transform.y
        follow_target = world.get_entity_by_name(camera_component.follow_entity) if camera_component.follow_entity else None
        if follow_target is not None and follow_target.active:
            follow_transform = follow_target.get_component(Transform)
            if follow_transform is not None and follow_transform.enabled:
                target_x, target_y = self._resolve_camera_target(camera_component, follow_transform, viewport_size)

        target_x, target_y = self._apply_camera_clamp(camera_component, target_x, target_y)

        camera = rl.Camera2D()
        camera.target = rl.Vector2(target_x, target_y)
        camera.offset = rl.Vector2(camera_component.offset_x, camera_component.offset_y)
        camera.rotation = camera_component.rotation
        camera.zoom = camera_component.zoom
        return camera

    def _resolve_camera_target(
        self,
        camera_component: Camera2D,
        follow_transform: Transform,
        viewport_size: Optional[tuple[float, float]],
    ) -> tuple[float, float]:
        target_x = follow_transform.x
        target_y = follow_transform.y
        if camera_component.framing_mode != "platformer":
            camera_component._runtime_target_x = target_x
            camera_component._runtime_target_y = target_y
            camera_component._has_recentred = True
            return target_x, target_y

        view_width = viewport_size[0] if viewport_size else 800.0
        view_height = viewport_size[1] if viewport_size else 600.0
        dead_zone_width = camera_component.dead_zone_width or (view_width * 0.18)
        dead_zone_height = camera_component.dead_zone_height or (view_height * 0.12)
        vertical_bias = max(0.0, view_height * 0.12)
        desired_y = target_y - vertical_bias

        if camera_component.recenter_on_play and not camera_component._has_recentred:
            camera_component._runtime_target_x = target_x
            camera_component._runtime_target_y = desired_y
            camera_component._has_recentred = True
            return target_x, desired_y

        current_x = camera_component._runtime_target_x
        current_y = camera_component._runtime_target_y
        if not camera_component._has_recentred:
            current_x = target_x
            current_y = desired_y
            camera_component._has_recentred = True

        half_dead_zone_x = dead_zone_width * 0.5
        half_dead_zone_y = dead_zone_height * 0.5
        if target_x > current_x + half_dead_zone_x:
            current_x = target_x - half_dead_zone_x
        elif target_x < current_x - half_dead_zone_x:
            current_x = target_x + half_dead_zone_x

        if desired_y > current_y + half_dead_zone_y:
            current_y = desired_y - half_dead_zone_y
        elif desired_y < current_y - half_dead_zone_y:
            current_y = desired_y + half_dead_zone_y

        camera_component._runtime_target_x = current_x
        camera_component._runtime_target_y = current_y
        return current_x, current_y

    def _apply_camera_clamp(
        self,
        camera_component: Camera2D,
        target_x: float,
        target_y: float,
    ) -> tuple[float, float]:
        if camera_component.clamp_left is not None:
            target_x = max(camera_component.clamp_left, target_x)
        if camera_component.clamp_right is not None:
            target_x = min(camera_component.clamp_right, target_x)
        if camera_component.clamp_top is not None:
            target_y = max(camera_component.clamp_top, target_y)
        if camera_component.clamp_bottom is not None:
            target_y = min(camera_component.clamp_bottom, target_y)
        return target_x, target_y

    def _draw_selection_highlight(self, entity: Entity) -> None:
        bounds = self._selection_bounds(entity)
        if bounds is None:
            return

        import time

        pulse = (time.time() * 10) % 255
        alpha = int(150 + (pulse / 255) * 100)
        color = rl.Color(255, 255, 0, alpha)
        rl.draw_rectangle_lines_ex(rl.Rectangle(bounds["left"], bounds["top"], bounds["width"], bounds["height"]), 2, color)
        if self.debug_draw_labels:
            rl.draw_text(entity.name, int(bounds["left"]), int(bounds["top"] - 20), 10, rl.YELLOW)

    def _render_entity(self, entity: Entity, transform: Transform) -> None:
        if entity.name.startswith("__tilecollider__"):
            return
        animator = entity.get_component(Animator)
        sprite = entity.get_component(Sprite)
        if animator is not None and animator.enabled and animator.sprite_sheet:
            self._draw_animated_sprite(transform, animator)
        elif sprite is not None and sprite.enabled and sprite.texture_path:
            self._draw_sprite(transform, sprite)
        else:
            self._draw_placeholder(entity.name, transform)

    def _draw_animated_sprite(self, transform: Transform, animator: Animator) -> None:
        texture = self._load_texture(animator.get_sprite_sheet_reference(), animator.sprite_sheet, sync_callback=animator.sync_sprite_sheet_reference)
        if texture.id == 0:
            return

        slice_name = animator.get_current_slice_name()
        slice_rect = self._asset_service.get_slice_rect(animator.get_sprite_sheet_reference(), slice_name) if (self._asset_service is not None and slice_name) else None
        if slice_rect is not None:
            src_x = int(slice_rect["x"])
            src_y = int(slice_rect["y"])
            src_w = int(slice_rect["width"])
            src_h = int(slice_rect["height"])
        else:
            sheet_columns = texture.width // max(1, animator.frame_width)
            if sheet_columns <= 0:
                sheet_columns = 1
            src_x, src_y, src_w, src_h = animator.get_source_rect(sheet_columns)

        dest_w = int(src_w * transform.scale_x)
        dest_h = int(src_h * transform.scale_y)
        dest_x = transform.x - dest_w / 2
        dest_y = transform.y - dest_h / 2
        if animator.flip_x:
            source_rect = rl.Rectangle(src_x + src_w, src_y, -src_w, src_h)
        else:
            source_rect = rl.Rectangle(src_x, src_y, src_w, src_h)
        dest_rect = rl.Rectangle(dest_x, dest_y, dest_w, dest_h)
        rl.draw_texture_pro(texture, source_rect, dest_rect, rl.Vector2(0, 0), transform.rotation, rl.WHITE)
        if self.debug_draw_labels:
            state_text = f"{animator.current_state}[{animator.current_frame}]"
            rl.draw_text(state_text, int(dest_x), int(dest_y - 15), 10, rl.YELLOW)

    def _draw_sprite(self, transform: Transform, sprite: Sprite) -> None:
        texture = self._load_texture(sprite.get_texture_reference(), sprite.texture_path, sync_callback=sprite.sync_texture_reference)
        if texture.id == 0:
            return

        width = sprite.width if sprite.width > 0 else texture.width
        height = sprite.height if sprite.height > 0 else texture.height
        width = int(width * transform.scale_x)
        height = int(height * transform.scale_y)
        dest_x = transform.x - (width * sprite.origin_x)
        dest_y = transform.y - (height * sprite.origin_y)

        source_width = texture.width if not sprite.flip_x else -texture.width
        source_height = texture.height if not sprite.flip_y else -texture.height
        source_rect = rl.Rectangle(0, 0, source_width, source_height)
        dest_rect = rl.Rectangle(dest_x, dest_y, width, height)
        tint = rl.Color(*sprite.tint)
        rl.draw_texture_pro(texture, source_rect, dest_rect, rl.Vector2(0, 0), transform.rotation, tint)

    def _draw_placeholder(self, name: str, transform: Transform) -> None:
        width = int(self.PLACEHOLDER_WIDTH * transform.scale_x)
        height = int(self.PLACEHOLDER_HEIGHT * transform.scale_y)
        rect_x = int(transform.x - width / 2)
        rect_y = int(transform.y - height / 2)
        rl.draw_rectangle(rect_x, rect_y, width, height, self.PLACEHOLDER_COLOR)
        if self.debug_draw_labels:
            rl.draw_text(name, rect_x, rect_y - 15, 10, rl.WHITE)

    def _draw_collider(self, transform: Transform, collider: Collider) -> None:
        left, top, right, bottom = collider.get_bounds(transform.x, transform.y)
        rl.draw_rectangle_lines(int(left), int(top), int(right - left), int(bottom - top), rl.GREEN)

    def _draw_debug_primitive(self, geometry: dict[str, Any]) -> None:
        kind = geometry.get("kind", "")
        color = self._color_from_payload(geometry.get("color", [255, 255, 255, 255]))
        if kind == "line":
            start = geometry.get("start", {})
            end = geometry.get("end", {})
            rl.draw_line(
                int(start.get("x", 0.0)),
                int(start.get("y", 0.0)),
                int(end.get("x", 0.0)),
                int(end.get("y", 0.0)),
                color,
            )
            return
        if kind == "rect":
            rl.draw_rectangle_lines_ex(
                rl.Rectangle(
                    float(geometry.get("x", 0.0)),
                    float(geometry.get("y", 0.0)),
                    float(geometry.get("width", 0.0)),
                    float(geometry.get("height", 0.0)),
                ),
                int(geometry.get("thickness", 1)),
                color,
            )
            return
        if kind == "circle":
            rl.draw_circle_lines(
                int(geometry.get("x", 0.0)),
                int(geometry.get("y", 0.0)),
                float(geometry.get("radius", 0.0)),
                color,
            )

    def _append_debug_command(self, commands: list[dict[str, Any]], command: dict[str, Any]) -> None:
        payload = dict(command)
        payload.setdefault(
            "batch_key",
            {
                "atlas_id": "__debug__",
                "material_id": "debug_lines",
                "shader_id": "default",
                "blend_mode": "alpha",
                "layer": "Debug",
            },
        )
        commands.append(payload)

    def _build_collider_geometry(self, transform: Transform, collider: Collider) -> dict[str, Any]:
        left, top, right, bottom = collider.get_bounds(transform.x, transform.y)
        return {
            "kind": "rect",
            "x": float(left),
            "y": float(top),
            "width": float(right - left),
            "height": float(bottom - top),
            "thickness": 1,
            "color": [0, 255, 0, 255],
        }

    def _build_tile_chunk_geometry(self, entity: Entity, command: dict[str, Any]) -> dict[str, Any] | None:
        transform = entity.get_component(Transform)
        if transform is None:
            return None
        bounds = command.get("chunk_data", {}).get("bounds", {})
        return {
            "kind": "rect",
            "x": float(transform.x) + float(bounds.get("x", 0.0)),
            "y": float(transform.y) + float(bounds.get("y", 0.0)),
            "width": float(bounds.get("width", 0.0)),
            "height": float(bounds.get("height", 0.0)),
            "thickness": 1,
            "color": [255, 128, 0, 255],
        }

    def _build_joint_geometry(self, entity: Entity) -> dict[str, Any] | None:
        transform = entity.get_component(Transform)
        joint = entity.get_component(Joint2D)
        if transform is None or joint is None or not joint.enabled or not joint.connected_entity:
            return None
        owner_world = getattr(entity, "_owner_world", None)
        if owner_world is None or not hasattr(owner_world, "get_entity_by_name"):
            return None
        connected_entity = owner_world.get_entity_by_name(joint.connected_entity)
        if connected_entity is None:
            return None
        connected_transform = connected_entity.get_component(Transform)
        if connected_transform is None:
            return None
        color = [255, 165, 0, 255] if joint.joint_type == "fixed" else [135, 206, 235, 255]
        return {
            "kind": "line",
            "start": {"x": float(transform.x + joint.anchor_x), "y": float(transform.y + joint.anchor_y)},
            "end": {
                "x": float(connected_transform.x + joint.connected_anchor_x),
                "y": float(connected_transform.y + joint.connected_anchor_y),
            },
            "color": color,
        }

    def _build_selection_geometry(self, entity: Entity) -> dict[str, Any] | None:
        bounds = self._selection_bounds(entity)
        if bounds is None:
            return None
        return {
            "kind": "rect",
            "x": float(bounds["left"]),
            "y": float(bounds["top"]),
            "width": float(bounds["width"]),
            "height": float(bounds["height"]),
            "thickness": 2,
            "color": [255, 255, 0, 220],
        }

    def _selection_bounds(self, entity: Entity) -> dict[str, float] | None:
        transform = entity.get_component(Transform)
        if transform is None:
            return None

        width = self.PLACEHOLDER_WIDTH
        height = self.PLACEHOLDER_HEIGHT
        offset_x = 0.5
        offset_y = 0.5

        sprite = entity.get_component(Sprite)
        if sprite is not None and sprite.enabled:
            if sprite.width > 0:
                width = sprite.width
            if sprite.height > 0:
                height = sprite.height
            offset_x = sprite.origin_x
            offset_y = sprite.origin_y

        animator = entity.get_component(Animator)
        if animator is not None and animator.enabled:
            current_slice = animator.get_current_slice_name()
            slice_rect = self._asset_service.get_slice_rect(animator.get_sprite_sheet_reference(), current_slice) if (self._asset_service is not None and current_slice) else None
            if slice_rect is not None:
                width = int(slice_rect["width"])
                height = int(slice_rect["height"])
            else:
                if animator.frame_width > 0:
                    width = animator.frame_width
                if animator.frame_height > 0:
                    height = animator.frame_height

        width *= transform.scale_x
        height *= transform.scale_y
        left = transform.x - (width * offset_x)
        top = transform.y - (height * offset_y)
        return {"left": float(left), "top": float(top), "width": float(width), "height": float(height)}

    def _build_camera_geometry(self, world: World, viewport_size: tuple[float, float]) -> dict[str, Any] | None:
        camera = self._build_camera_from_world(world, viewport_size=viewport_size)
        if camera is None:
            return None
        zoom = max(float(camera.zoom), 0.0001)
        width = float(viewport_size[0]) / zoom
        height = float(viewport_size[1]) / zoom
        center_x = float(camera.target.x)
        center_y = float(camera.target.y)
        return {
            "kind": "rect",
            "x": center_x - (width * 0.5),
            "y": center_y - (height * 0.5),
            "width": width,
            "height": height,
            "thickness": 1,
            "color": [64, 224, 208, 255],
        }

    def _normalize_debug_primitive(self, primitive: dict[str, Any]) -> dict[str, Any]:
        payload = dict(primitive)
        payload["kind"] = str(payload.get("kind", "")).lower()
        payload["color"] = list(payload.get("color", [255, 255, 255, 255]))
        if payload["kind"] == "line":
            payload["start"] = {
                "x": float(payload.get("start", {}).get("x", 0.0)),
                "y": float(payload.get("start", {}).get("y", 0.0)),
            }
            payload["end"] = {
                "x": float(payload.get("end", {}).get("x", 0.0)),
                "y": float(payload.get("end", {}).get("y", 0.0)),
            }
        elif payload["kind"] == "rect":
            payload["x"] = float(payload.get("x", 0.0))
            payload["y"] = float(payload.get("y", 0.0))
            payload["width"] = float(payload.get("width", 0.0))
            payload["height"] = float(payload.get("height", 0.0))
            payload["thickness"] = int(payload.get("thickness", 1))
        elif payload["kind"] == "circle":
            payload["x"] = float(payload.get("x", 0.0))
            payload["y"] = float(payload.get("y", 0.0))
            payload["radius"] = float(payload.get("radius", 0.0))
        return payload

    def _debug_overlay_signature(self) -> tuple[Any, ...]:
        signature: list[Any] = []
        for primitive in self._debug_primitives:
            item = self._normalize_debug_primitive(primitive)
            signature.append(
                (
                    item.get("kind", ""),
                    tuple(item.get("color", [])),
                    tuple(sorted((key, repr(value)) for key, value in item.items() if key != "color")),
                )
            )
        return tuple(signature)

    def _clone_geometry(self, geometry: Any) -> Any:
        if isinstance(geometry, dict):
            return {key: self._clone_geometry(value) for key, value in geometry.items()}
        if isinstance(geometry, list):
            return [self._clone_geometry(value) for value in geometry]
        return geometry

    def _color_from_payload(self, color: Any) -> rl.Color:
        values = list(color) if isinstance(color, (list, tuple)) else [255, 255, 255, 255]
        while len(values) < 4:
            values.append(255)
        return rl.Color(int(values[0]), int(values[1]), int(values[2]), int(values[3]))

    def _draw_tilemap_chunk(self, command: dict[str, Any]) -> None:
        entity = command["entity"]
        transform = entity.get_component(Transform)
        if transform is None:
            return
        chunk_data = command.get("chunk_data", {})
        for tile in chunk_data.get("tiles", []):
            if not bool(tile.get("resolved", False)):
                continue
            texture_ref = normalize_asset_reference(tile.get("texture"))
            texture_path = str(tile.get("texture_path", ""))
            texture = self._load_texture(texture_ref, texture_path)
            if texture.id == 0:
                continue
            source_rect_data = dict(tile.get("source_rect", {}))
            dest_data = dict(tile.get("dest", {}))
            source_rect = rl.Rectangle(
                float(source_rect_data.get("x", 0.0)),
                float(source_rect_data.get("y", 0.0)),
                float(source_rect_data.get("width", 0.0)),
                float(source_rect_data.get("height", 0.0)),
            )
            dest_rect = rl.Rectangle(
                float(transform.x) + float(dest_data.get("x", 0.0)),
                float(transform.y) + float(dest_data.get("y", 0.0)),
                float(dest_data.get("width", 0.0)),
                float(dest_data.get("height", 0.0)),
            )
            rl.draw_texture_pro(texture, source_rect, dest_rect, rl.Vector2(0, 0), 0.0, self._color_from_payload(tile.get("tint", [])))

    def _draw_joint(self, entity: Entity) -> None:
        transform = entity.get_component(Transform)
        joint = entity.get_component(Joint2D)
        if transform is None or joint is None or not joint.enabled or not joint.connected_entity:
            return
        owner_world = getattr(entity, "_owner_world", None)
        if owner_world is None or not hasattr(owner_world, "get_entity_by_name"):
            return
        connected_entity = owner_world.get_entity_by_name(joint.connected_entity)
        if connected_entity is None:
            return
        connected_transform = connected_entity.get_component(Transform)
        if connected_transform is None:
            return
        start_x = transform.x + joint.anchor_x
        start_y = transform.y + joint.anchor_y
        end_x = connected_transform.x + joint.connected_anchor_x
        end_y = connected_transform.y + joint.connected_anchor_y
        color = rl.ORANGE if joint.joint_type == "fixed" else rl.SKYBLUE
        rl.draw_line(int(start_x), int(start_y), int(end_x), int(end_y), color)
        rl.draw_circle(int(start_x), int(start_y), 3.0, color)
        rl.draw_circle(int(end_x), int(end_y), 3.0, color)

    def _load_texture(self, reference: Any, fallback_path: str, sync_callback: Any = None) -> rl.Texture:
        entry = self._asset_resolver.resolve_entry(reference) if self._asset_resolver is not None else None
        if entry is not None:
            if sync_callback is not None:
                sync_callback(entry.get("reference", {}))
            return self._texture_manager.load(entry["absolute_path"], cache_key=entry.get("guid") or entry.get("path"))

        resolved_path = self._resolve_texture_path(fallback_path)
        return self._texture_manager.load(resolved_path, cache_key=resolved_path)

    def _resolve_texture_path(self, path: str) -> str:
        if self._project_service is None or not path:
            return path
        return self._project_service.resolve_path(path).as_posix()

    def _tilemap_chunk_atlas_id(self, chunk_data: dict[str, Any], fallback_atlas_id: str) -> str:
        atlas_ids = {
            str(tile.get("texture", {}).get("guid") or tile.get("texture_path") or "")
            for tile in chunk_data.get("tiles", [])
            if bool(tile.get("resolved", False))
        }
        atlas_ids.discard("")
        if len(atlas_ids) == 1:
            return next(iter(atlas_ids))
        if len(atlas_ids) > 1:
            return "__tilemap_mixed__"
        return fallback_atlas_id or "__tilemap__"

    def _resolve_tile_asset_reference(self, tilemap: Tilemap, layer: dict[str, Any], tile: dict[str, Any]) -> dict[str, str]:
        for candidate in (
            normalize_asset_reference(tile.get("source")),
            normalize_asset_reference(layer.get("tilemap_source")),
            tilemap.get_tileset_reference(),
        ):
            if candidate.get("guid") or candidate.get("path"):
                return candidate
        return normalize_asset_reference({})

    def _resolve_tile_source_rect(
        self,
        tilemap: Tilemap,
        asset_ref: dict[str, str],
        tile: dict[str, Any],
    ) -> tuple[dict[str, int] | None, str]:
        tile_id = str(tile.get("tile_id", "")).strip()
        slice_rect = self._resolve_tile_slice_rect(asset_ref, tile_id)
        if slice_rect is not None:
            return slice_rect, "slice"
        grid_rect = self._resolve_tile_grid_rect(tilemap, tile_id)
        if grid_rect is not None:
            return grid_rect, "grid"
        return None, "unresolved"

    def _resolve_tile_slice_rect(self, asset_ref: dict[str, str], tile_id: str) -> dict[str, int] | None:
        if self._asset_service is None or not tile_id or not (asset_ref.get("guid") or asset_ref.get("path")):
            return None
        slice_rect = self._asset_service.get_slice_rect(asset_ref, tile_id)
        if slice_rect is None:
            return None
        return {
            "x": int(slice_rect.get("x", 0)),
            "y": int(slice_rect.get("y", 0)),
            "width": max(1, int(slice_rect.get("width", 0))),
            "height": max(1, int(slice_rect.get("height", 0))),
        }

    def _resolve_tile_grid_rect(self, tilemap: Tilemap, tile_id: str) -> dict[str, int] | None:
        tile_width = max(1, int(tilemap.tileset_tile_width or tilemap.cell_width))
        tile_height = max(1, int(tilemap.tileset_tile_height or tilemap.cell_height))
        columns = max(1, int(tilemap.tileset_columns or 0))
        spacing = max(0, int(tilemap.tileset_spacing))
        margin = max(0, int(tilemap.tileset_margin))
        tile_index = self._parse_tile_index(tile_id)
        if tile_index is None:
            if columns != 1:
                return None
            tile_index = 0
        if tile_index < 0:
            return None
        return {
            "x": margin + ((tile_index % columns) * (tile_width + spacing)),
            "y": margin + ((tile_index // columns) * (tile_height + spacing)),
            "width": tile_width,
            "height": tile_height,
        }

    def _parse_tile_index(self, tile_id: str) -> int | None:
        try:
            return int(str(tile_id).strip())
        except (TypeError, ValueError):
            return None

    def cleanup(self) -> None:
        self._texture_manager.unload_all()
        self._render_targets.unload_all()
