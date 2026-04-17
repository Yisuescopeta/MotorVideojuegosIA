from __future__ import annotations

from typing import Any, Optional

from engine.components.collider import Collider
from engine.components.joint2d import Joint2D
from engine.components.renderorder2d import RenderOrder2D
from engine.components.tilemap import Tilemap
from engine.components.transform import Transform
from engine.ecs.world import World
from engine.rendering.pipeline_types import FramePlan2D, RenderBatch2D, RenderPassPlan2D, RenderTargetJob2D


class RenderPipelinePlanner2D:
    """Builds typed render plans while preserving the current public graph contract."""

    def __init__(self, owner: Any) -> None:
        self._owner = owner

    def build_graph_payload(self, world: World, viewport_size: Optional[tuple[float, float]] = None) -> dict[str, Any]:
        sorting_layers = self._owner._get_sorting_layers(world)
        normalized_viewport = self._owner._normalize_viewport_size(viewport_size)
        cache_key = (
            id(world),
            int(getattr(world, "version", -1)),
            int(getattr(world, "selection_version", -1)),
            tuple(sorting_layers),
            bool(self._owner.debug_draw_colliders),
            bool(self._owner.debug_draw_labels),
            bool(self._owner.debug_draw_tile_chunks),
            bool(self._owner.debug_draw_camera),
            self._owner._debug_overlay_signature(),
            normalized_viewport,
        )
        if self._owner._render_graph_cache_key == cache_key:
            return {
                "passes": self._owner._render_graph_cache.get("passes", []),
                "totals": {
                    **dict(self._owner._render_graph_cache.get("totals", {})),
                    "tilemap_chunk_rebuilds": 0,
                },
            }

        sorted_entities = self._owner._sorted_render_entities(world)
        pass_commands: dict[str, list[dict[str, Any]]] = {name: [] for name in self._owner.PASS_SEQUENCE}
        tilemap_chunks = 0
        tilemap_chunk_rebuilds = 0

        for entity in sorted_entities:
            transform = entity.get_component(Transform)
            if transform is None:
                continue
            tilemap = entity.get_component(Tilemap)
            render_order = entity.get_component(RenderOrder2D)
            pass_name = self._owner._get_render_pass(render_order)
            sorting_layer = self._owner._get_sorting_layer(render_order)
            order_in_layer = self._owner._get_order_in_layer(render_order)
            if tilemap is not None and tilemap.enabled:
                chunk_commands, rebuilds = self._owner._build_tilemap_commands(entity, transform, tilemap, sorting_layer, order_in_layer)
                pass_commands[pass_name].extend(chunk_commands)
                tilemap_chunks += len(chunk_commands)
                tilemap_chunk_rebuilds += rebuilds
                if self._owner.debug_draw_tile_chunks:
                    for chunk_command in chunk_commands:
                        geometry = self._owner._build_tile_chunk_geometry(entity, chunk_command)
                        if geometry is not None:
                            self._owner._append_debug_command(
                                pass_commands["Debug"],
                                {
                                    "kind": "debug",
                                    "debug_kind": "tile_chunk",
                                    "entity": entity,
                                    "entity_name": entity.name,
                                    "render_pass": "Debug",
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
                    "render_pass": pass_name,
                    "sorting_layer": sorting_layer,
                    "order_in_layer": order_in_layer,
                    "batch_key": self._owner._build_batch_key(entity, sorting_layer),
                }
            )

        if self._owner.debug_draw_colliders:
            for entity in sorted_entities:
                transform = entity.get_component(Transform)
                collider = entity.get_component(Collider)
                if transform is None or collider is None or not collider.enabled:
                    continue
                self._owner._append_debug_command(
                    pass_commands["Debug"],
                    {
                        "kind": "debug",
                        "debug_kind": "collider",
                        "entity": entity,
                        "entity_name": entity.name,
                        "render_pass": "Debug",
                        "geometry": self._owner._build_collider_geometry(transform, collider),
                    },
                )
            for entity in sorted_entities:
                transform = entity.get_component(Transform)
                joint = entity.get_component(Joint2D)
                if transform is None or joint is None or not joint.enabled or not joint.connected_entity:
                    continue
                if world.get_entity_by_name(joint.connected_entity) is None:
                    continue
                self._owner._append_debug_command(
                    pass_commands["Debug"],
                    {
                        "kind": "debug",
                        "debug_kind": "joint",
                        "entity": entity,
                        "entity_name": entity.name,
                        "render_pass": "Debug",
                        "geometry": self._owner._build_joint_geometry(entity),
                    },
                )

        if world.selected_entity_name:
            selected_entity = world.get_entity_by_name(world.selected_entity_name)
            if selected_entity is not None:
                self._owner._append_debug_command(
                    pass_commands["Debug"],
                    {
                        "kind": "debug",
                        "debug_kind": "selection",
                        "entity": selected_entity,
                        "entity_name": selected_entity.name,
                        "render_pass": "Debug",
                        "geometry": self._owner._build_selection_geometry(selected_entity),
                    },
                )

        if self._owner.debug_draw_camera:
            camera_geometry = self._owner._build_camera_geometry(world, normalized_viewport)
            if camera_geometry is not None:
                self._owner._append_debug_command(
                    pass_commands["Debug"],
                    {
                        "kind": "debug",
                        "debug_kind": "camera",
                        "entity_name": "__camera__",
                        "render_pass": "Debug",
                        "geometry": camera_geometry,
                    },
                )

        for primitive in self._owner._debug_primitives:
            self._owner._append_debug_command(
                pass_commands["Debug"],
                {
                    "kind": "debug",
                    "debug_kind": primitive.get("kind", "primitive"),
                    "entity_name": primitive.get("entity_name", "__debug__"),
                    "render_pass": "Debug",
                    "geometry": primitive,
                },
            )

        passes: list[dict[str, Any]] = []
        total_draw_calls = 0
        total_render_commands = 0
        total_tilemap_tile_draw_calls = 0
        total_batches = 0
        total_state_changes = 0
        total_entities = 0

        for pass_name in self._owner.PASS_SEQUENCE:
            commands = pass_commands[pass_name]
            batches = self.build_batches_payload(commands)
            entity_count = sum(1 for command in commands if command["kind"] == "entity")
            render_commands = len(commands)
            draw_calls = sum(self._owner._command_draw_call_count(command) for command in commands)
            tilemap_tile_draw_calls = sum(self._owner._tilemap_command_draw_call_count(command) for command in commands)
            batch_count = len(batches)
            state_changes = max(0, batch_count - 1)
            passes.append(
                {
                    "name": pass_name,
                    "commands": commands,
                    "batches": batches,
                    "stats": {
                        "render_entities": entity_count,
                        "render_commands": render_commands,
                        "draw_calls": draw_calls,
                        "tilemap_tile_draw_calls": tilemap_tile_draw_calls,
                        "batches": batch_count,
                        "state_changes": state_changes,
                    },
                }
            )
            total_entities += entity_count
            total_draw_calls += draw_calls
            total_render_commands += render_commands
            total_tilemap_tile_draw_calls += tilemap_tile_draw_calls
            total_batches += batch_count
            total_state_changes += state_changes

        totals = {
            "render_entities": total_entities,
            "render_commands": total_render_commands,
            "draw_calls": total_draw_calls,
            "batches": total_batches,
            "state_changes": total_state_changes,
            "tilemap_chunks": tilemap_chunks,
            "tilemap_tile_draw_calls": total_tilemap_tile_draw_calls,
            "tilemap_chunk_rebuilds": tilemap_chunk_rebuilds,
            "pass_count": len(self._owner.PASS_SEQUENCE),
            "sort_cache": {"hits": self._owner._sort_cache_hits, "misses": self._owner._sort_cache_misses},
            "passes": {pass_data["name"]: dict(pass_data["stats"]) for pass_data in passes},
        }
        graph = {
            "passes": passes,
            "totals": totals,
        }
        self._owner._render_graph_cache_key = cache_key
        self._owner._render_graph_cache = graph
        return graph

    def build_frame_plan(self, world: World, *, viewport_size: Optional[tuple[float, float]]) -> FramePlan2D:
        graph_payload = self.build_graph_payload(world, viewport_size=viewport_size)
        passes = [RenderPassPlan2D.from_payload(pass_payload) for pass_payload in graph_payload.get("passes", [])]
        totals = self.copy_stats(graph_payload.get("totals", {}))
        minimap_config = self._owner._get_minimap_config(world)
        render_target_jobs: list[RenderTargetJob2D] = []

        debug_pass = next((pass_plan for pass_plan in passes if pass_plan.name == "Debug"), None)
        if debug_pass is not None and debug_pass.commands:
            width, height = self._owner._normalize_viewport_size(viewport_size)
            render_target_jobs.append(
                RenderTargetJob2D(
                    name="selection_overlay",
                    kind="debug_overlay",
                    width=width,
                    height=height,
                    commands=list(debug_pass.commands),
                )
            )

        if minimap_config.get("enabled"):
            world_pass = next((pass_plan for pass_plan in passes if pass_plan.name == "World"), None)
            minimap_commands = [] if world_pass is None else [command for command in world_pass.commands if command.kind == "entity"]
            render_target_jobs.append(
                RenderTargetJob2D(
                    name="minimap",
                    kind="minimap",
                    width=int(minimap_config["width"]),
                    height=int(minimap_config["height"]),
                    margin=int(minimap_config["margin"]),
                    commands=minimap_commands,
                )
            )

        totals["render_target_passes"] = len(render_target_jobs)
        totals["render_target_composites"] = len(render_target_jobs)
        return FramePlan2D(
            passes=passes,
            render_target_jobs=render_target_jobs,
            totals=totals,
        )

    def build_frame_plan_payload(self, world: World, *, viewport_size: Optional[tuple[float, float]]) -> dict[str, Any]:
        return self.build_frame_plan(world, viewport_size=viewport_size).to_payload()

    def build_batches_payload(self, commands: list[dict[str, Any]]) -> list[dict[str, Any]]:
        batches: list[dict[str, Any]] = []
        current: dict[str, Any] | None = None

        for command in commands:
            batch_key = dict(command["batch_key"])
            if current is None or current["key"] != batch_key:
                current = {"key": batch_key, "commands": []}
                batches.append(current)
            current["commands"].append(command)

        return batches

    def public_graph(self, graph: dict[str, Any]) -> dict[str, Any]:
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
                            "chunk_data": self._owner._clone_geometry(command.get("chunk_data")),
                            "geometry": self._owner._clone_geometry(command.get("geometry")),
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
            "totals": self.copy_stats(graph.get("totals", {})),
        }

    def copy_stats(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "render_entities": int(payload.get("render_entities", 0)),
            "render_commands": int(payload.get("render_commands", payload.get("draw_calls", 0))),
            "draw_calls": int(payload.get("draw_calls", 0)),
            "batches": int(payload.get("batches", 0)),
            "state_changes": int(payload.get("state_changes", 0)),
            "tilemap_chunks": int(payload.get("tilemap_chunks", 0)),
            "tilemap_tile_draw_calls": int(payload.get("tilemap_tile_draw_calls", 0)),
            "tilemap_chunk_rebuilds": int(payload.get("tilemap_chunk_rebuilds", 0)),
            "pass_count": int(payload.get("pass_count", len(self._owner.PASS_SEQUENCE))),
            "render_target_passes": int(payload.get("render_target_passes", 0)),
            "render_target_composites": int(payload.get("render_target_composites", 0)),
            "sort_cache": {
                "hits": int(payload.get("sort_cache", {}).get("hits", 0)),
                "misses": int(payload.get("sort_cache", {}).get("misses", 0)),
            },
            "passes": {
                str(name): {
                    "render_entities": int(stats.get("render_entities", 0)),
                    "render_commands": int(stats.get("render_commands", stats.get("draw_calls", 0))),
                    "draw_calls": int(stats.get("draw_calls", 0)),
                    "tilemap_tile_draw_calls": int(stats.get("tilemap_tile_draw_calls", 0)),
                    "batches": int(stats.get("batches", 0)),
                    "state_changes": int(stats.get("state_changes", 0)),
                }
                for name, stats in payload.get("passes", {}).items()
            },
        }

    def copy_stats_with_tilemap_fallback_draws(self, payload: dict[str, Any], graph: dict[str, Any]) -> dict[str, Any]:
        stats = self.copy_stats(payload)
        total_draw_calls = 0
        pass_stats: dict[str, dict[str, int]] = {}
        for pass_data in graph.get("passes", []):
            pass_name = str(pass_data.get("name", ""))
            commands = list(pass_data.get("commands", []))
            draw_calls = 0
            for command in commands:
                if command.get("kind") == "tilemap_chunk":
                    draw_calls += self._owner._tilemap_command_draw_call_count(command)
                else:
                    draw_calls += 1
            current = dict(stats.get("passes", {}).get(pass_name, {}))
            current["draw_calls"] = draw_calls
            pass_stats[pass_name] = current
            total_draw_calls += draw_calls
        stats["draw_calls"] = total_draw_calls
        stats["passes"] = pass_stats
        return stats
