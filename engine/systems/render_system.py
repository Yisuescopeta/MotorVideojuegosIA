"""
engine/systems/render_system.py - Sistema de renderizado 2D con render graph minimo.
"""

from __future__ import annotations

from typing import Any, Optional

import pyray as rl

from engine.assets.asset_service import AssetService
from engine.components.animator import Animator
from engine.components.camera2d import Camera2D
from engine.components.collider import Collider
from engine.components.joint2d import Joint2D
from engine.components.renderorder2d import RenderOrder2D
from engine.components.renderstyle2d import RenderStyle2D
from engine.components.sprite import Sprite
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

    def __init__(self) -> None:
        self._texture_manager: TextureManager = TextureManager()
        self._project_service: Any = None
        self._asset_service: AssetService | None = None
        self._asset_resolver: Any = None
        self._render_targets: RenderTargetPool = RenderTargetPool()
        self.debug_draw_colliders: bool = self.DEBUG_DRAW_COLLIDERS
        self.debug_draw_labels: bool = False
        self._sorted_entities_cache_key: tuple[int, int, tuple[str, ...]] | None = None
        self._sorted_entities_cache: list[Entity] = []
        self._render_graph_cache_key: tuple[int, int, int, tuple[str, ...], bool, bool] | None = None
        self._render_graph_cache: dict[str, Any] = {"passes": [], "totals": {}}
        self._last_render_stats: dict[str, Any] = {
            "render_entities": 0,
            "draw_calls": 0,
            "batches": 0,
            "state_changes": 0,
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

    def set_debug_options(self, *, draw_colliders: bool | None = None, draw_labels: bool | None = None) -> None:
        if draw_colliders is not None:
            self.debug_draw_colliders = bool(draw_colliders)
        if draw_labels is not None:
            self.debug_draw_labels = bool(draw_labels)

    def get_last_render_stats(self) -> dict[str, Any]:
        return self._copy_stats(self._last_render_stats)

    def get_last_render_graph(self) -> dict[str, Any]:
        return self._public_graph(self._render_graph_cache)

    def profile_world(self, world: World, viewport_size: Optional[tuple[float, float]] = None) -> dict[str, Any]:
        frame_plan = self._build_frame_plan(world, viewport_size=viewport_size)
        return self._copy_stats(frame_plan["totals"])

    def render(
        self,
        world: World,
        override_camera: Optional[rl.Camera2D] = None,
        use_world_camera: bool = True,
        viewport_size: Optional[tuple[float, float]] = None,
    ) -> None:
        frame_plan = self._build_frame_plan(world, viewport_size=viewport_size)
        graph = frame_plan["graph"]

        camera = override_camera
        if camera is None and use_world_camera:
            camera = self._build_camera_from_world(world, viewport_size=viewport_size)
        if camera is not None:
            rl.begin_mode_2d(camera)

        self._render_pass(graph, "World")
        self._render_pass(graph, "Overlay")

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

    def _build_render_graph(self, world: World) -> dict[str, Any]:
        sorting_layers = self._get_sorting_layers(world)
        cache_key = (
            id(world),
            int(getattr(world, "version", -1)),
            int(getattr(world, "selection_version", -1)),
            tuple(sorting_layers),
            bool(self.debug_draw_colliders),
            bool(self.debug_draw_labels),
        )
        if self._render_graph_cache_key == cache_key:
            return self._render_graph_cache

        sorted_entities = self._sorted_render_entities(world)
        pass_commands: dict[str, list[dict[str, Any]]] = {name: [] for name in self.PASS_SEQUENCE}

        for entity in sorted_entities:
            transform = entity.get_component(Transform)
            if transform is None:
                continue
            render_order = entity.get_component(RenderOrder2D)
            pass_name = self._get_render_pass(render_order)
            sorting_layer = self._get_sorting_layer(render_order)
            order_in_layer = self._get_order_in_layer(render_order)
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
                pass_commands["Debug"].append(
                    {
                        "kind": "debug",
                        "debug_kind": "collider",
                        "entity": entity,
                        "entity_name": entity.name,
                        "batch_key": {
                            "atlas_id": "__debug__",
                            "material_id": "debug_lines",
                            "shader_id": "default",
                            "blend_mode": "alpha",
                            "layer": "Debug",
                        },
                    }
                )
            for entity in sorted_entities:
                transform = entity.get_component(Transform)
                joint = entity.get_component(Joint2D)
                if transform is None or joint is None or not joint.enabled or not joint.connected_entity:
                    continue
                if world.get_entity_by_name(joint.connected_entity) is None:
                    continue
                pass_commands["Debug"].append(
                    {
                        "kind": "debug",
                        "debug_kind": "joint",
                        "entity": entity,
                        "entity_name": entity.name,
                        "batch_key": {
                            "atlas_id": "__debug__",
                            "material_id": "debug_lines",
                            "shader_id": "default",
                            "blend_mode": "alpha",
                            "layer": "Debug",
                        },
                    }
                )

        if world.selected_entity_name:
            selected_entity = world.get_entity_by_name(world.selected_entity_name)
            if selected_entity is not None:
                pass_commands["Debug"].append(
                    {
                        "kind": "debug",
                        "debug_kind": "selection",
                        "entity": selected_entity,
                        "entity_name": selected_entity.name,
                        "batch_key": {
                            "atlas_id": "__debug__",
                            "material_id": "debug_lines",
                            "shader_id": "default",
                            "blend_mode": "alpha",
                            "layer": "Debug",
                        },
                    }
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
        graph = self._build_render_graph(world)
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
                            "sorting_layer": command.get("sorting_layer", ""),
                            "order_in_layer": command.get("order_in_layer", 0),
                            "batch_key": dict(command.get("batch_key", {})),
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
        transform = entity.get_component(Transform)
        if transform is None:
            return

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

        import time

        pulse = (time.time() * 10) % 255
        alpha = int(150 + (pulse / 255) * 100)
        color = rl.Color(255, 255, 0, alpha)
        rl.draw_rectangle_lines_ex(rl.Rectangle(left, top, width, height), 2, color)
        if self.debug_draw_labels:
            rl.draw_text(entity.name, int(left), int(top - 20), 10, rl.YELLOW)

    def _render_entity(self, entity: Entity, transform: Transform) -> None:
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

    def cleanup(self) -> None:
        self._texture_manager.unload_all()
        self._render_targets.unload_all()
