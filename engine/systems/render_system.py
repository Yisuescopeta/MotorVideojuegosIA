"""
engine/systems/render_system.py - Sistema de renderizado 2D con render graph minimo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, NamedTuple, Optional, Union, cast

import pyray as rl
from engine.assets.asset_reference import clone_asset_reference, normalize_asset_reference
from engine.assets.asset_resolver import AssetResolver
from engine.assets.asset_service import AssetService
from engine.components.animator import Animator
from engine.components.backbuffer_copy import BackBufferCopy
from engine.components.camera2d import Camera2D
from engine.components.canvas_layer import CanvasLayer
from engine.components.canvas_modulate import CanvasModulate
from engine.components.collider import Collider
from engine.components.colorrect import ColorRect
from engine.components.directional_light_2d import DirectionalLight2D
from engine.components.joint2d import Joint2D
from engine.components.polygon2d import Polygon2D
from engine.components.renderorder2d import RenderOrder2D
from engine.components.renderstyle2d import RenderStyle2D
from engine.components.sprite import Sprite
from engine.components.sub_viewport import SubViewport, ViewportTexture
from engine.components.tilemap import Tilemap
from engine.components.transform import Transform
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.rendering.pipeline_executor import RenderPipelineExecutor2D
from engine.rendering.pipeline_planner import RenderPipelinePlanner2D
from engine.rendering.pipeline_types import FramePlan2D
from engine.rendering.post_process import PostProcessPipeline
from engine.rendering.render_spatial_index import AABB, RenderSpatialIndex
from engine.rendering.render_targets import RenderTargetPool
from engine.rendering.tilemap_chunk_renderer import TilemapChunkRenderer
from engine.rendering.viewport_renderer import ViewportRenderer
from engine.resources.texture_manager import TextureManager

if TYPE_CHECKING:
    from engine.project.project_service import ProjectService


class RenderBatchKey(NamedTuple):
    atlas_id: str = ""
    material_id: str = ""
    shader_id: str = ""
    blend_mode: str = "alpha"
    layer: str = ""
    chunk: str = ""

    @classmethod
    def from_payload(cls, payload: Any) -> "RenderBatchKey":  # payload acepta dict, tuple, o el propio RenderBatchKey
        if isinstance(payload, cls):
            return payload
        if isinstance(payload, dict):
            return cls(
                atlas_id=str(payload.get("atlas_id", "")),
                material_id=str(payload.get("material_id", "")),
                shader_id=str(payload.get("shader_id", "")),
                blend_mode=str(payload.get("blend_mode", "alpha")),
                layer=str(payload.get("layer", "")),
                chunk=str(payload.get("chunk", "")),
            )
        values = tuple(payload) if isinstance(payload, tuple) else ()
        padded = values + ("", "", "", "alpha", "", "")
        return cls(*(str(value) for value in padded[:6]))

    def get(self, key: str, default: Any = None) -> Any:  # Acceso genérico tipo dict; el tipo depende del campo accedido
        return self.to_dict().get(key, default)

    def to_dict(self) -> dict[str, str]:
        payload = {
            "atlas_id": self.atlas_id,
            "material_id": self.material_id,
            "shader_id": self.shader_id,
            "blend_mode": self.blend_mode,
            "layer": self.layer,
        }
        if self.chunk:
            payload["chunk"] = self.chunk
        return payload


@dataclass(slots=True)
class RenderCommand:
    kind: str
    entity: Entity | None = None
    entity_name: str = ""
    sorting_layer: str = ""
    order_in_layer: int = 0
    batch_key: RenderBatchKey = field(default_factory=RenderBatchKey)
    debug_kind: str = ""
    chunk_id: str = ""
    chunk_data: dict[str, Any] = field(default_factory=dict)
    geometry: dict[str, Any] = field(default_factory=dict)
    cache_key: object = None
    render_target_name: str = ""
    render_target_dirty: bool = True
    canvas_layer_entity: str = ""

    def get(self, key: str, default: Any = None) -> Any:  # Acceso genérico tipo dict; el tipo depende del campo accedido
        return getattr(self, key, default)

    def __getitem__(self, key: str) -> Any:  # Protocolo contenedor; tipo dinámico por diseño
        return getattr(self, key)

    def __setitem__(self, key: str, value: Any) -> None:  # Protocolo contenedor; tipo dinámico por diseño
        setattr(self, key, value)

    def to_payload(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "entity": self.entity,
            "entity_name": self.entity_name,
            "sorting_layer": self.sorting_layer,
            "order_in_layer": self.order_in_layer,
            "batch_key": self.batch_key.to_dict(),
            "debug_kind": self.debug_kind,
            "chunk_id": self.chunk_id,
            "chunk_data": self.chunk_data,
            "geometry": self.geometry,
            "cache_key": self.cache_key,
            "render_target_name": self.render_target_name,
            "render_target_dirty": self.render_target_dirty,
            "canvas_layer_entity": self.canvas_layer_entity,
        }


@dataclass(slots=True)
class RenderBatch:
    key: RenderBatchKey
    commands: list[RenderCommand] = field(default_factory=list)

    def get(self, key: str, default: Any = None) -> Any:  # Acceso genérico tipo dict; el tipo depende del campo accedido
        return getattr(self, key, default)

    def __getitem__(self, key: str) -> Any:  # Protocolo contenedor; tipo dinámico por diseño
        return getattr(self, key)

    def to_payload(self) -> dict[str, Any]:
        return {
            "key": self.key.to_dict(),
            "commands": [command.to_payload() for command in self.commands],
        }


@dataclass(slots=True)
class RenderPass:
    name: str
    commands: list[RenderCommand] = field(default_factory=list)
    batches: list[RenderBatch] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:  # Acceso genérico tipo dict; el tipo depende del campo accedido
        return getattr(self, key, default)

    def __getitem__(self, key: str) -> Any:  # Protocolo contenedor; tipo dinámico por diseño
        return getattr(self, key)

    def to_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "commands": [command.to_payload() for command in self.commands],
            "batches": [batch.to_payload() for batch in self.batches],
            "stats": dict(self.stats),
        }


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
        self._project_service: ProjectService | None = None
        self._asset_service: AssetService | None = None
        self._asset_resolver: AssetResolver | None = None  # Resuelto dinámicamente desde AssetService
        self._render_targets: RenderTargetPool = RenderTargetPool()
        self._tilemap_chunk_renderer: TilemapChunkRenderer = TilemapChunkRenderer(self._render_targets, lambda reference, fallback_path: self._load_texture(reference, fallback_path))
        self._pipeline_planner: RenderPipelinePlanner2D = RenderPipelinePlanner2D(self)
        self._pipeline_executor: RenderPipelineExecutor2D = RenderPipelineExecutor2D(self)
        self.debug_draw_colliders: bool = self.DEBUG_DRAW_COLLIDERS
        self.debug_draw_labels: bool = False
        self.debug_draw_tile_chunks: bool = False
        self.debug_draw_camera: bool = False
        self.debug_draw_navigation: bool = False
        self.spatial_culling_enabled: bool = True
        self._debug_primitives: list[dict[str, Any]] = []

        self._render_graph_cache: dict[str, Any] = {"passes": [], "totals": {}}
        self._tilemap_chunk_cache: dict[tuple[int, str, int, int], dict[str, Any]] = {}
        self._last_render_stats: dict[str, Any] = {
            "render_entities": 0,
            "render_commands": 0,
            "draw_calls": 0,
            "batches": 0,
            "state_changes": 0,
            "tilemap_chunks": 0,
            "tilemap_total_chunks": 0,
            "tilemap_visible_chunks": 0,
            "tilemap_tile_draw_calls": 0,
            "tilemap_chunk_rebuilds": 0,
            "pass_count": len(self.PASS_SEQUENCE),
            "render_target_passes": 0,
            "render_target_composites": 0,
            "spatial_culling_enabled": False,
            "spatial_total_entities": 0,
            "spatial_visible_entities": 0,
            "sort_cache": {"hits": 0, "misses": 0},
            "passes": {},
        }
        self._sort_cache_hits: int = 0
        self._sort_cache_misses: int = 0
        self._sorted_entities_cache_key: tuple[object, ...] | None = None
        self._sorted_entities_cache: list[Entity] = []
        self._render_graph_cache_key: tuple[object, ...] | None = None
        self._render_spatial_index: RenderSpatialIndex = RenderSpatialIndex()
        self._viewport_renderer: ViewportRenderer = ViewportRenderer()
        self._post_process_pipeline: PostProcessPipeline = PostProcessPipeline()

    @property
    def texture_manager(self) -> TextureManager:
        """Acceso publico al cache de texturas para sistemas externos (p. ej. precarga)."""
        return self._texture_manager

    def set_project_service(self, project_service: ProjectService) -> None:
        self._project_service = project_service
        self._asset_service = AssetService(project_service) if project_service is not None else None
        self._asset_resolver = self._asset_service.get_asset_resolver() if self._asset_service is not None else None

    def reset_project_resources(self) -> None:
        self._texture_manager.unload_all()
        self._tilemap_chunk_renderer.invalidate_cached_targets(self._tilemap_chunk_cache)

    def set_spatial_culling_enabled(self, enabled: bool) -> None:
        self.spatial_culling_enabled = bool(enabled)

    def set_debug_options(
        self,
        *,
        draw_colliders: bool | None = None,
        draw_labels: bool | None = None,
        draw_tile_chunks: bool | None = None,
        draw_camera: bool | None = None,
        draw_navigation: bool | None = None,
    ) -> None:
        if draw_colliders is not None:
            self.debug_draw_colliders = bool(draw_colliders)
        if draw_labels is not None:
            self.debug_draw_labels = bool(draw_labels)
        if draw_tile_chunks is not None:
            self.debug_draw_tile_chunks = bool(draw_tile_chunks)
        if draw_camera is not None:
            self.debug_draw_camera = bool(draw_camera)
        if draw_navigation is not None:
            self.debug_draw_navigation = bool(draw_navigation)

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
            "draw_navigation": bool(self.debug_draw_navigation),
            "primitive_count": len(self._debug_primitives),
        }

    def get_last_render_stats(self) -> dict[str, Any]:
        return self._copy_stats(self._last_render_stats)

    def get_last_render_graph(self) -> dict[str, Any]:
        return self._public_graph(self._render_graph_cache)

    def get_debug_geometry_dump(self, world: World, viewport_size: Optional[tuple[float, float]] = None) -> dict[str, Any]:
        graph = self._public_graph(self._build_render_graph(world, viewport_size=viewport_size))
        debug_pass = cast(
            dict[str, Any],
            next((entry for entry in graph.get("passes", []) if entry.get("name") == "Debug"), {"commands": [], "stats": {}}),
        )
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
        if allow_render_targets:
            self._render_targets.begin_frame()
            self._prepare_tilemap_chunk_targets(graph)

        # --- SubViewport rendering (before main scene) ---
        if allow_render_targets:
            self._render_sub_viewports(world, viewport_size=viewport_size)

        # --- BackBufferCopy capture (before main scene) ---
        if allow_render_targets:
            self._capture_backbuffer(world, viewport_size=viewport_size)

        if camera is not None:
            rl.begin_mode_2d(camera)

        self._render_pass(graph, "World")
        self._render_pass(graph, "Overlay")

        if not allow_render_targets:
            self._render_pass(graph, "Debug")
            if camera is not None:
                rl.end_mode_2d()
            totals = self._copy_stats_with_tilemap_fallback_draws(frame_plan["totals"], graph)
            totals["render_target_passes"] = 0
            totals["render_target_composites"] = 0
            self._last_render_stats = totals
            return

        if camera is not None:
            rl.end_mode_2d()

        self._render_debug_overlay(frame_plan, camera=camera, viewport_size=viewport_size)
        self._render_minimap(world, frame_plan, viewport_size=viewport_size)
        self._render_canvas_modulate(world, viewport_size=viewport_size)

        # --- Post-processing pipeline ---
        if allow_render_targets:
            self._apply_post_processing(world, viewport_size=viewport_size)

        target_metrics = self._render_targets.get_frame_metrics()
        totals = self._copy_stats(frame_plan["totals"])
        totals["render_target_passes"] = target_metrics.get("passes", 0)
        totals["render_target_composites"] = target_metrics.get("composites", 0)
        self._last_render_stats = totals

    def _sorted_render_entities(self, world: World) -> list[Entity]:
        sorting_layers = self._get_sorting_layers(world)
        cache_key = (
            id(world),
            self._world_version(world, "render_version"),
            self._world_version(world, "transform_version"),
            self._world_version(world, "structure_version"),
            tuple(sorting_layers),
        )
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
        camera_bounds = self._resolve_spatial_camera_bounds(world, viewport_size, normalized_viewport)
        cache_key = (
            id(world),
            self._world_version(world, "render_version"),
            self._world_version(world, "transform_version"),
            int(getattr(world, "selection_version", -1)),
            normalized_viewport,
            camera_bounds,
            tuple(sorting_layers),
            bool(self.spatial_culling_enabled),
            bool(self.debug_draw_colliders),
            bool(self.debug_draw_labels),
            bool(self.debug_draw_tile_chunks),
            bool(self.debug_draw_camera),
            bool(self.debug_draw_navigation),
            self._debug_overlay_signature(),
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
        render_entities, spatial_stats = self._spatially_filter_render_entities(sorted_entities, camera_bounds)
        pass_commands: dict[str, list[RenderCommand]] = {name: [] for name in self.PASS_SEQUENCE}
        tilemap_chunks = 0
        tilemap_total_chunks = 0
        tilemap_visible_chunks = 0
        tilemap_chunk_rebuilds = 0

        for entity in render_entities:
            transform = entity.get_component(Transform)
            if transform is None:
                continue
            tilemap = entity.get_component(Tilemap)
            render_order = entity.get_component(RenderOrder2D)
            pass_name = self._get_render_pass(render_order)
            sorting_layer = self._get_sorting_layer(render_order)
            order_in_layer = self._get_order_in_layer(render_order)
            if tilemap is not None and tilemap.enabled:
                chunk_commands, rebuilds, total_chunks, visible_chunks = self._build_tilemap_commands(
                    entity,
                    transform,
                    tilemap,
                    sorting_layer,
                    order_in_layer,
                    camera_bounds=None if self.debug_draw_tile_chunks else camera_bounds,
                )
                pass_commands[pass_name].extend(chunk_commands)
                tilemap_chunks += len(chunk_commands)
                tilemap_total_chunks += total_chunks
                tilemap_visible_chunks += visible_chunks
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
                                    "chunk_id": chunk_command.chunk_id,
                                    "geometry": geometry,
                                },
                            )
                continue
            pass_commands[pass_name].append(
                RenderCommand(
                    kind="entity",
                    entity=entity,
                    entity_name=entity.name,
                    sorting_layer=sorting_layer,
                    order_in_layer=order_in_layer,
                    batch_key=self._build_batch_key(entity, sorting_layer),
                    canvas_layer_entity=getattr(render_order, "canvas_layer_entity", "") if render_order is not None else "",
                )
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

        passes: list[RenderPass] = []
        total_draw_calls = 0
        total_render_commands = 0
        total_tilemap_tile_draw_calls = 0
        total_batches = 0
        total_state_changes = 0
        total_entities = 0

        for pass_name in self.PASS_SEQUENCE:
            commands = pass_commands[pass_name]
            batches = self._build_batches(commands)
            entity_count = sum(1 for command in commands if command["kind"] == "entity")
            render_commands = len(commands)
            draw_calls = sum(self._command_draw_call_count(command) for command in commands)
            tilemap_tile_draw_calls = sum(self._tilemap_command_draw_call_count(command) for command in commands)
            batch_count = len(batches)
            state_changes = max(0, batch_count - 1)
            passes.append(
                RenderPass(
                    name=pass_name,
                    commands=commands,
                    batches=batches,
                    stats={
                        "render_entities": entity_count,
                        "render_commands": render_commands,
                        "draw_calls": draw_calls,
                        "tilemap_tile_draw_calls": tilemap_tile_draw_calls,
                        "batches": batch_count,
                        "state_changes": state_changes,
                    },
                )
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
            "tilemap_total_chunks": tilemap_total_chunks,
            "tilemap_visible_chunks": tilemap_visible_chunks,
            "tilemap_tile_draw_calls": total_tilemap_tile_draw_calls,
            "tilemap_chunk_rebuilds": tilemap_chunk_rebuilds,
            "pass_count": len(self.PASS_SEQUENCE),
            **spatial_stats,
            "sort_cache": {"hits": self._sort_cache_hits, "misses": self._sort_cache_misses},
            "passes": {
                pass_data.name: dict(pass_data.stats)
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

    def _world_version(self, world: World, name: str) -> int:
        if hasattr(world, name):
            return int(getattr(world, name))
        return int(getattr(world, "version", -1))

    def _command_draw_call_count(self, command: RenderCommand) -> int:
        if command.kind == "tilemap_chunk":
            return self._tilemap_chunk_renderer.command_draw_call_count(command.to_payload())
        return 1

    def _tilemap_command_draw_call_count(self, command: RenderCommand) -> int:
        return self._tilemap_chunk_renderer.tile_draw_call_count(command.to_payload())

    def _spatially_filter_render_entities(
        self,
        sorted_entities: list[Entity],
        camera_bounds: AABB | None,
    ) -> tuple[list[Entity], dict[str, Any]]:
        stats = {
            "spatial_culling_enabled": False,
            "spatial_total_entities": len(sorted_entities),
            "spatial_visible_entities": len(sorted_entities),
        }
        if not self.spatial_culling_enabled or self.debug_draw_tile_chunks or camera_bounds is None:
            return sorted_entities, stats

        try:
            self._render_spatial_index.rebuild(sorted_entities)
            visible_ids = self._render_spatial_index.query(camera_bounds)
        except Exception:
            return sorted_entities, stats

        filtered = [entity for entity in sorted_entities if int(entity.id) in visible_ids]
        stats["spatial_culling_enabled"] = True
        stats["spatial_visible_entities"] = len(filtered)
        return filtered, stats

    def _build_frame_plan(
        self,
        world: World,
        *,
        viewport_size: Optional[tuple[float, float]],
    ) -> dict[str, Any]:
        graph = self._build_render_graph(world, viewport_size=viewport_size)
        minimap_config = self._get_minimap_config(world)
        debug_commands: list[RenderCommand] = next((entry["commands"] for entry in graph["passes"] if entry["name"] == "Debug"), [])
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

    def _build_frame_plan_model(
        self,
        world: World,
        *,
        viewport_size: Optional[tuple[float, float]],
    ) -> FramePlan2D:
        return self._pipeline_planner.adapt_frame_plan_payload(
            self._build_frame_plan(world, viewport_size=viewport_size)
        )

    def _build_batches(self, commands: list[RenderCommand]) -> list[RenderBatch]:
        batches: list[RenderBatch] = []
        current: RenderBatch | None = None

        for command in commands:
            batch_key = RenderBatchKey.from_payload(command.batch_key)
            if current is None or current.key != batch_key:
                current = RenderBatch(key=batch_key)
                batches.append(current)
            current.commands.append(command)

        return batches

    def _render_pass(self, graph: dict[str, Any] | FramePlan2D, pass_name: str, camera: rl.Camera2D | None = None) -> None:
        if isinstance(graph, FramePlan2D):
            self._pipeline_executor.render_pass(graph, pass_name)
            return
        pass_data = next((entry for entry in graph["passes"] if entry["name"] == pass_name), None)
        if pass_data is None:
            return

        canvas_layer_map: dict[str, Any] = getattr(self, "_canvas_layer_map", {})

        for batch in pass_data["batches"]:
            self._begin_batch_state(batch["key"])
            try:
                current_canvas_layer: str = ""
                for command in batch["commands"]:
                    if command["kind"] == "entity":
                        command_cl_entity = str(command.get("canvas_layer_entity", ""))
                        if command_cl_entity != current_canvas_layer:
                            if current_canvas_layer:
                                self._pop_canvas_layer_transform(canvas_layer_map.get(current_canvas_layer))
                            current_canvas_layer = command_cl_entity
                            if current_canvas_layer:
                                self._push_canvas_layer_transform(
                                    canvas_layer_map.get(current_canvas_layer),
                                    camera=camera,
                                )
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
                    elif command["debug_kind"] == "tile_chunk":
                        entity = command["entity"]
                        if entity is not None:
                            geometry = command.get("geometry", {})
                            self._draw_debug_primitive(geometry)
                    elif command.get("debug_kind", "") in ("navigation_polygon", "navigation_path", "navigation_radius"):
                        self._draw_debug_primitive(command.get("geometry", {}))
                    else:
                        self._draw_debug_primitive(command.get("geometry", {}))
                if current_canvas_layer:
                    self._pop_canvas_layer_transform(canvas_layer_map.get(current_canvas_layer))
            finally:
                self._end_batch_state(batch["key"])

    def _render_debug_overlay(
        self,
        frame_plan: dict[str, Any] | FramePlan2D,
        *,
        camera: Optional[rl.Camera2D],
        viewport_size: Optional[tuple[float, float]],
    ) -> None:
        if isinstance(frame_plan, FramePlan2D):
            job = next((item for item in frame_plan.render_target_jobs if item.kind == "debug_overlay"), None)
            if job is None:
                return
            self._pipeline_executor.execute_render_target_job(job, world=None, camera=camera, viewport_size=viewport_size)
            return
        width, height = self._normalize_viewport_size(viewport_size)
        debug_commands: list[RenderCommand] = next(
            (entry["commands"] for entry in frame_plan["graph"]["passes"] if entry["name"] == "Debug"),
            [],
        )
        if not debug_commands:
            return
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
                elif command.get("debug_kind", "") in ("navigation_polygon", "navigation_path", "navigation_radius", "tile_chunk"):
                    self._draw_debug_primitive(command.get("geometry", {}))
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
        frame_plan: dict[str, Any] | FramePlan2D,
        *,
        viewport_size: Optional[tuple[float, float]],
    ) -> None:
        if isinstance(frame_plan, FramePlan2D):
            job = next((item for item in frame_plan.render_target_jobs if item.kind == "minimap"), None)
            if job is None:
                return
            self._pipeline_executor.execute_render_target_job(job, world=world, camera=None, viewport_size=viewport_size)
            return
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
                polygon = entity.get_component(Polygon2D)
                if polygon is not None and polygon.enabled:
                    color = rl.Color(*polygon.color)
                elif sprite is None:
                    color = rl.LIGHTGRAY
                else:
                    color = rl.Color(*sprite.tint)
                rl.draw_circle(int(point[0]), int(point[1]), 2.0, color)
            rl.draw_rectangle_lines(0, 0, width, height, rl.Color(100, 140, 180, 255))
        finally:
            self._render_targets.end()

        viewport_width, _ = self._normalize_viewport_size(viewport_size)
        destination = rl.Rectangle(float(viewport_width - width - margin), float(margin), float(width), float(height))
        self._render_targets.compose("minimap", destination, rl.WHITE)

    def _render_canvas_modulate(
        self,
        world: World,
        *,
        viewport_size: Optional[tuple[float, float]] = None,
    ) -> None:
        """Applies CanvasModulate color overlay if any entity has the component."""
        for entity in world.get_entities_with(CanvasModulate):
            modulate = entity.get_component(CanvasModulate)
            if modulate is None or not modulate.enabled:
                continue
            width, height = self._normalize_viewport_size(viewport_size)
            rl.draw_rectangle(0, 0, int(width), int(height), rl.Color(*modulate.color))
            break  # Only first CanvasModulate applies

    def _build_batch_key(self, entity: Entity, sorting_layer: str) -> RenderBatchKey:
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

        locator: Union[str, dict[str, str]] = ""
        if animator is not None and animator.enabled and animator.sprite_sheet:
            locator = animator.get_sprite_sheet_reference()
        elif sprite is not None and sprite.enabled and sprite.texture_path:
            locator = sprite.get_texture_reference()

        if not locator:
            polygon = entity.get_component(Polygon2D)
            if polygon is not None and polygon.enabled and polygon.texture_path:
                locator = polygon.get_texture_reference()

        resolved_atlas_id = atlas_id or self._resolve_atlas_id(locator)
        if not resolved_atlas_id:
            resolved_atlas_id = "__placeholder__"

        return RenderBatchKey(
            atlas_id=resolved_atlas_id,
            material_id=material_id,
            shader_id=shader_id,
            blend_mode=blend_mode,
            layer=sorting_layer,
        )

    def _build_tilemap_commands(
        self,
        entity: Entity,
        transform: Transform,
        tilemap: Tilemap,
        sorting_layer: str,
        order_in_layer: int,
        camera_bounds: AABB | None = None,
    ) -> tuple[list[RenderCommand], int, int, int]:
        commands: list[RenderCommand] = []
        rebuilds = 0
        live_keys: set[tuple[int, str, int, int]] = set()
        total_chunks = 0
        visible_chunks = 0
        tileset_ref = tilemap.get_tileset_reference()
        fallback_atlas_id = self._resolve_atlas_id(tileset_ref)
        if not fallback_atlas_id:
            fallback_atlas_id = str(tileset_ref.get("guid") or tileset_ref.get("path") or "__tilemap__")
        for layer_index, layer in enumerate(tilemap.layers):
            if not bool(layer.get("visible", True)):
                continue
            layer_name = str(layer.get("name", f"Layer_{layer_index}"))
            raw_chunks = layer.get("_runtime_chunks", {})
            if isinstance(raw_chunks, dict):
                live_chunks = [chunk for chunk in raw_chunks.values() if isinstance(chunk, dict) and chunk.get("tiles")]
            else:
                live_chunks = tilemap.iter_runtime_chunks(layer)
            total_chunks += len(live_chunks)
            for runtime_chunk in live_chunks:
                chunk_x, chunk_y = runtime_chunk.get("coord", (0, 0))
                live_keys.add((int(entity.id), layer_name, int(chunk_x), int(chunk_y)))
            runtime_chunks = (
                tilemap.iter_runtime_chunks(layer)
                if camera_bounds is None
                else tilemap.iter_visible_runtime_chunks(layer, transform, camera_bounds)
            )
            visible_chunks += len(runtime_chunks)
            for runtime_chunk in runtime_chunks:
                chunk_x, chunk_y = runtime_chunk.get("coord", (0, 0))
                chunk_tiles = self._runtime_chunk_tiles(runtime_chunk)
                cache_key = (int(entity.id), layer_name, int(chunk_x), int(chunk_y))
                signature = self._tilemap_chunk_signature(tilemap, layer, chunk_tiles)
                runtime_version = int(runtime_chunk.get("version", 0))
                runtime_dirty = bool(runtime_chunk.get("dirty", True))
                cached = self._tilemap_chunk_cache.get(cache_key)
                if cached is None or cached.get("signature") != signature or cached.get("runtime_version") != runtime_version or runtime_dirty:
                    chunk_data = self._build_tilemap_chunk_data(tilemap, layer, chunk_x, chunk_y, chunk_tiles)
                    cached = {
                        "signature": signature,
                        "runtime_version": runtime_version,
                        "data": chunk_data,
                        "render_target_dirty": True,
                        "render_target_name": self._tilemap_chunk_render_target_name(
                            int(entity.id),
                            layer_name,
                            int(chunk_x),
                            int(chunk_y),
                        ),
                    }
                    self._tilemap_chunk_cache[cache_key] = cached
                    tilemap.mark_runtime_chunk_clean(layer, chunk_x, chunk_y, runtime_version)
                    rebuilds += 1
                chunk_atlas_id = self._tilemap_chunk_atlas_id(cached["data"], fallback_atlas_id)
                commands.append(
                    RenderCommand(
                        kind="tilemap_chunk",
                        entity=entity,
                        entity_name=entity.name,
                        sorting_layer=sorting_layer,
                        order_in_layer=order_in_layer + layer_index,
                        chunk_id=f"{layer_name}/{chunk_x},{chunk_y}",
                        chunk_data=cached["data"],
                        cache_key=cache_key,
                        render_target_name=cached.get("render_target_name", ""),
                        render_target_dirty=bool(cached.get("render_target_dirty", True)),
                        batch_key=RenderBatchKey(
                            atlas_id=chunk_atlas_id,
                            material_id="tilemap_chunk",
                            shader_id="default",
                            blend_mode="alpha",
                            layer=sorting_layer,
                            chunk=f"{chunk_x},{chunk_y}",
                        ),
                    )
                )
        stale_keys = [key for key in self._tilemap_chunk_cache.keys() if key[0] == int(entity.id) and key not in live_keys]
        for key in stale_keys:
            cached = self._tilemap_chunk_cache.pop(key, None)
            if cached is not None:
                self._tilemap_chunk_renderer.unload_target(str(cached.get("render_target_name", "")))
        return commands, rebuilds, total_chunks, visible_chunks

    @staticmethod
    def _tilemap_chunk_render_target_name(entity_id: int, layer_name: str, chunk_x: int, chunk_y: int) -> str:
        safe_layer = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in str(layer_name or "Layer"))
        return f"tilemap_chunk_{int(entity_id)}_{safe_layer}_{int(chunk_x)}_{int(chunk_y)}"

    def _runtime_chunk_tiles(self, runtime_chunk: dict[str, Any]) -> list[dict[str, Any]]:
        tiles: list[dict[str, Any]] = []
        raw_tiles = runtime_chunk.get("tiles", {})
        if not isinstance(raw_tiles, dict):
            return tiles
        for coord, tile in raw_tiles.items():
            if not isinstance(tile, dict):
                continue
            if isinstance(coord, tuple) and len(coord) == 2:
                tile_x = int(coord[0])
                tile_y = int(coord[1])
            else:
                x_value, y_value = str(coord).split(",", 1)
                tile_x = int(x_value)
                tile_y = int(y_value)
            tiles.append(
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
        return tiles

    def _partition_tilemap_layer(self, tilemap: Tilemap, layer: dict[str, Any]) -> dict[tuple[int, int], list[dict[str, Any]]]:
        chunks: dict[tuple[int, int], list[dict[str, Any]]] = {}
        for key, tile in layer.get("tiles", {}).items():
            if isinstance(key, tuple) and len(key) == 2:
                tile_x = int(key[0])
                tile_y = int(key[1])
            else:
                x_value, y_value = str(key).split(",", 1)
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

    def _tilemap_chunk_signature(self, tilemap: Tilemap, layer: dict[str, Any], chunk_tiles: list[dict[str, Any]]) -> tuple[object, ...]:
        tileset_ref = tilemap.get_tileset_reference()
        layer_source = normalize_asset_reference(layer.get("tilemap_source"))
        geo = tilemap.resolve_tile_geometry() if hasattr(tilemap, 'resolve_tile_geometry') else None
        if geo:
            tw = int(geo.get("tile_width", 16))
            th = int(geo.get("tile_height", 16))
            cols = int(geo.get("columns", 0))
            spc = int(geo.get("spacing", 0))
            mg = int(geo.get("margin", 0))
        else:
            tw = int(tilemap.tileset_tile_width)
            th = int(tilemap.tileset_tile_height)
            cols = int(tilemap.tileset_columns)
            spc = int(tilemap.tileset_spacing)
            mg = int(tilemap.tileset_margin)
        return (
            int(tilemap.cell_width),
            int(tilemap.cell_height),
            str(tilemap.orientation),
            str(tileset_ref.get("guid", "")),
            str(tileset_ref.get("path", "")),
            str(getattr(tilemap, 'tileset_resource_path', '')),
            tw,
            th,
            cols,
            spc,
            mg,
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

    def _resolve_atlas_id(self, locator: object) -> str:
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

    def _resolve_spatial_camera_bounds(
        self,
        world: World,
        viewport_size: Optional[tuple[float, float]],
        normalized_viewport: tuple[int, int],
    ) -> AABB | None:
        if not self.spatial_culling_enabled:
            return None
        if viewport_size is None and not bool(hasattr(rl, "is_window_ready") and rl.is_window_ready()):
            return None
        camera = self._build_camera_from_world(world, viewport_size=normalized_viewport)
        if camera is None:
            return None
        zoom = max(abs(float(camera.zoom)), 0.0001)
        width = float(normalized_viewport[0]) / zoom
        height = float(normalized_viewport[1]) / zoom
        left = float(camera.target.x) - (float(camera.offset.x) / zoom)
        top = float(camera.target.y) - (float(camera.offset.y) / zoom)
        return (left, top, left + width, top + height)

    def _compute_minimap_bounds(self, entities: list[Entity]) -> tuple[float, float, float, float]:
        transforms = [transform for entity in entities if (transform := entity.get_component(Transform)) is not None]
        min_x = min((transform.x for transform in transforms), default=-100.0)
        max_x = max((transform.x for transform in transforms), default=100.0)
        min_y = min((transform.y for transform in transforms), default=-100.0)
        max_y = max((transform.y for transform in transforms), default=100.0)
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
                            "batch_key": self._batch_key_to_dict(command.get("batch_key", {})),
                            "chunk_data": self._clone_geometry(command.get("chunk_data")),
                            "geometry": self._clone_geometry(command.get("geometry")),
                        }
                        for command in pass_data.get("commands", [])
                    ],
                    "batches": [
                        {
                            "key": self._batch_key_to_dict(batch.get("key", {})),
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

    def _batch_key_to_dict(self, batch_key: object) -> dict[str, str]:
        return RenderBatchKey.from_payload(batch_key).to_dict()

    def _copy_stats(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "render_entities": int(payload.get("render_entities", 0)),
            "render_commands": int(payload.get("render_commands", payload.get("draw_calls", 0))),
            "draw_calls": int(payload.get("draw_calls", 0)),
            "batches": int(payload.get("batches", 0)),
            "state_changes": int(payload.get("state_changes", 0)),
            "tilemap_chunks": int(payload.get("tilemap_chunks", 0)),
            "tilemap_total_chunks": int(payload.get("tilemap_total_chunks", payload.get("tilemap_chunks", 0))),
            "tilemap_visible_chunks": int(payload.get("tilemap_visible_chunks", payload.get("tilemap_chunks", 0))),
            "tilemap_tile_draw_calls": int(payload.get("tilemap_tile_draw_calls", 0)),
            "tilemap_chunk_rebuilds": int(payload.get("tilemap_chunk_rebuilds", 0)),
            "pass_count": int(payload.get("pass_count", len(self.PASS_SEQUENCE))),
            "render_target_passes": int(payload.get("render_target_passes", 0)),
            "render_target_composites": int(payload.get("render_target_composites", 0)),
            "spatial_culling_enabled": bool(payload.get("spatial_culling_enabled", False)),
            "spatial_total_entities": int(payload.get("spatial_total_entities", 0)),
            "spatial_visible_entities": int(payload.get("spatial_visible_entities", 0)),
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

    def _copy_stats_with_tilemap_fallback_draws(self, payload: dict[str, Any], graph: dict[str, Any]) -> dict[str, Any]:
        stats = self._copy_stats(payload)
        total_draw_calls = 0
        pass_stats: dict[str, dict[str, int]] = {}
        for pass_data in graph.get("passes", []):
            pass_name = str(pass_data.get("name", ""))
            commands = list(pass_data.get("commands", []))
            draw_calls = 0
            for command in commands:
                if command.get("kind") == "tilemap_chunk":
                    draw_calls += self._tilemap_command_draw_call_count(command)
                else:
                    draw_calls += 1
            current = dict(stats.get("passes", {}).get(pass_name, {}))
            current["draw_calls"] = draw_calls
            pass_stats[pass_name] = current
            total_draw_calls += draw_calls
        stats["draw_calls"] = total_draw_calls
        stats["passes"] = pass_stats
        return stats

    def _build_canvas_layer_map(self, world: World) -> dict[str, dict[str, Any]]:
        """Build a map of canvas_layer_entity_name -> CanvasLayer data dict."""
        result: dict[str, dict[str, Any]] = {}
        for entity in world.get_entities_with(CanvasLayer):
            canvas_layer = entity.get_component(CanvasLayer)
            if canvas_layer is not None and canvas_layer.visible:
                result[entity.name] = {
                    "layer": canvas_layer.layer,
                    "offset_x": canvas_layer.offset_x,
                    "offset_y": canvas_layer.offset_y,
                    "rotation": canvas_layer.rotation,
                    "scale_x": canvas_layer.scale_x,
                    "scale_y": canvas_layer.scale_y,
                    "follow_viewport": canvas_layer.follow_viewport,
                    "follow_viewport_scale": canvas_layer.follow_viewport_scale,
                    "transform": entity.get_component(Transform),
                }
        return result

    def _push_canvas_layer_transform(
        self,
        layer_data: dict[str, Any] | None,
        camera: rl.Camera2D | None = None,
    ) -> None:
        if layer_data is None:
            return
        if layer_data.get("follow_viewport") and camera is not None:
            zoom = max(float(camera.zoom), 0.0001)
            rl.rlPushMatrix()
            rl.rlTranslatef(camera.target.x, camera.target.y, 0.0)
            rl.rlRotatef(camera.rotation, 0.0, 0.0, 1.0)
            rl.rlScalef(1.0 / zoom, 1.0 / zoom, 1.0)
            fx = float(layer_data["follow_viewport_scale"])
            rl.rlScalef(fx, fx, 1.0)
            ox = float(layer_data.get("offset_x", 0.0))
            oy = float(layer_data.get("offset_y", 0.0))
            rl.rlTranslatef(ox, oy, 0.0)
            rot = float(layer_data.get("rotation", 0.0))
            if rot != 0.0:
                rl.rlRotatef(rot, 0.0, 0.0, 1.0)
            sx = float(layer_data.get("scale_x", 1.0))
            sy = float(layer_data.get("scale_y", 1.0))
            if sx != 1.0 or sy != 1.0:
                rl.rlScalef(sx, sy, 1.0)
        else:
            rl.rlPushMatrix()
            ox = float(layer_data.get("offset_x", 0.0))
            oy = float(layer_data.get("offset_y", 0.0))
            rl.rlTranslatef(ox, oy, 0.0)
            rot = float(layer_data.get("rotation", 0.0))
            if rot != 0.0:
                rl.rlRotatef(rot, 0.0, 0.0, 1.0)
            sx = float(layer_data.get("scale_x", 1.0))
            sy = float(layer_data.get("scale_y", 1.0))
            if sx != 1.0 or sy != 1.0:
                rl.rlScalef(sx, sy, 1.0)

    def _pop_canvas_layer_transform(self, layer_data: dict[str, Any] | None) -> None:
        if layer_data is not None:
            rl.rlPopMatrix()

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
        viewport_tex = entity.get_component(ViewportTexture)
        if viewport_tex is not None and viewport_tex.enabled and viewport_tex.viewport_entity:
            self._draw_viewport_texture_sprite(transform, entity)
        elif animator is not None and animator.enabled and animator.sprite_sheet:
            self._draw_animated_sprite(transform, animator)
        elif sprite is not None and sprite.enabled and sprite.texture_path:
            self._draw_sprite(transform, sprite)
        else:
            polygon = entity.get_component(Polygon2D)
            if polygon is not None and polygon.enabled and len(polygon.points) >= 3:
                self._draw_polygon(transform, polygon)
                return
            color_rect = entity.get_component(ColorRect)
            if color_rect is not None and color_rect.enabled:
                self._draw_color_rect(transform, color_rect)
                return
            dir_light = entity.get_component(DirectionalLight2D)
            if dir_light is not None and dir_light.enabled:
                self._draw_directional_light(transform, dir_light)
                return
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

    def _draw_color_rect(self, transform: Transform, color_rect: ColorRect) -> None:
        width = int(color_rect.width * transform.scale_x)
        height = int(color_rect.height * transform.scale_y)
        rect_x = int(transform.x - width / 2)
        rect_y = int(transform.y - height / 2)
        rl.draw_rectangle(rect_x, rect_y, width, height, rl.Color(*color_rect.color))
        if self.debug_draw_labels:
            rl.draw_text("ColorRect", rect_x, rect_y - 15, 10, rl.WHITE)

    def _draw_directional_light(self, transform: Transform, dir_light: DirectionalLight2D) -> None:
        start_x = int(transform.x)
        start_y = int(transform.y)
        end_x = int(transform.x + dir_light.direction_x * dir_light.max_distance)
        end_y = int(transform.y + dir_light.direction_y * dir_light.max_distance)
        color = rl.Color(dir_light.color_r, dir_light.color_g, dir_light.color_b, min(255, int(dir_light.energy * 100)))
        rl.draw_line(start_x, start_y, end_x, end_y, color)
        rl.draw_circle(start_x, start_y, 6.0, rl.Color(dir_light.color_r, dir_light.color_g, dir_light.color_b, 255))
        if self.debug_draw_labels:
            rl.draw_text("DirLight", start_x + 8, start_y - 12, 10, rl.YELLOW)

    def _draw_polygon(self, transform: Transform, polygon: Polygon2D) -> None:
        if len(polygon.points) < 3:
            return

        import math

        cos_r = math.cos(transform.rotation)
        sin_r = math.sin(transform.rotation)
        sx = transform.scale_x
        sy = transform.scale_y

        world_points: list[tuple[float, float]] = []
        for pt in polygon.points:
            wx = pt[0] * sx
            wy = pt[1] * sy
            rx = wx * cos_r - wy * sin_r
            ry = wx * sin_r + wy * cos_r
            world_points.append((transform.x + rx + polygon.offset_x, transform.y + ry + polygon.offset_y))

        use_uvs = len(polygon.uvs) >= len(polygon.points)

        if polygon.texture_path:
            texture = self._load_texture(polygon.get_texture_reference(), polygon.texture_path, sync_callback=polygon.sync_texture_reference)
            if texture.id != 0:
                rl.rl_set_texture(texture.id)
                rl.rl_begin(rl.RL_TRIANGLES)
                rl.rl_color4ub(*polygon.color)
                for i in range(1, len(world_points) - 1):
                    p0 = world_points[0]
                    p1 = world_points[i]
                    p2 = world_points[i + 1]
                    if use_uvs:
                        uv0 = polygon.uvs[0]
                        uv1 = polygon.uvs[i]
                        uv2 = polygon.uvs[i + 1]
                        rl.rl_tex_coord2f(uv0[0], uv0[1])
                        rl.rl_vertex2f(p0[0], p0[1])
                        rl.rl_tex_coord2f(uv1[0], uv1[1])
                        rl.rl_vertex2f(p1[0], p1[1])
                        rl.rl_tex_coord2f(uv2[0], uv2[1])
                        rl.rl_vertex2f(p2[0], p2[1])
                    else:
                        rl.rl_tex_coord2f(0.5, 0.5)
                        rl.rl_vertex2f(p0[0], p0[1])
                        rl.rl_tex_coord2f(float(i) / len(world_points), 0.0)
                        rl.rl_vertex2f(p1[0], p1[1])
                        rl.rl_tex_coord2f(float(i + 1) / len(world_points), 1.0)
                        rl.rl_vertex2f(p2[0], p2[1])
                rl.rl_end()
                rl.rl_set_texture(0)
                return

        # No texture: solid color using triangle fan
        from pyray import Vector2
        color = rl.Color(*polygon.color)
        for i in range(1, len(world_points) - 1):
            rl.draw_triangle(
                Vector2(world_points[0][0], world_points[0][1]),
                Vector2(world_points[i][0], world_points[i][1]),
                Vector2(world_points[i + 1][0], world_points[i + 1][1]),
                color,
            )

    def _draw_collider(self, transform: Transform, collider: Collider) -> None:
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

    def _append_debug_command(self, commands: list[RenderCommand], command: dict[str, Any]) -> None:
        commands.append(
            RenderCommand(
                kind=str(command.get("kind", "debug")),
                debug_kind=str(command.get("debug_kind", "")),
                entity=command.get("entity"),
                entity_name=str(command.get("entity_name", "")),
                chunk_id=str(command.get("chunk_id", "")),
                geometry=dict(command.get("geometry") or {}),
                batch_key=RenderBatchKey.from_payload(
                    command.get(
                        "batch_key",
                        {
                            "atlas_id": "__debug__",
                            "material_id": "debug_lines",
                            "shader_id": "default",
                            "blend_mode": "alpha",
                            "layer": "Debug",
                        },
                    )
                ),
            )
        )

    def _draw_debug_primitive(self, geometry: dict[str, Any]) -> None:
        kind = str(geometry.get("kind", "")).lower()
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
        elif kind == "rect":
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
        elif kind == "circle":
            rl.draw_circle_lines(
                int(geometry.get("x", 0.0)),
                int(geometry.get("y", 0.0)),
                float(geometry.get("radius", 0.0)),
                color,
            )
        elif kind == "navigation_polygon":
            points = geometry.get("points", [])
            for i in range(len(points)):
                p0 = points[i]
                p1 = points[(i + 1) % len(points)]
                rl.draw_line(int(p0[0]), int(p0[1]), int(p1[0]), int(p1[1]), color)
        elif kind == "navigation_path":
            points = geometry.get("points", [])
            for i in range(len(points) - 1):
                p0 = points[i]
                p1 = points[i + 1]
                rl.draw_line(int(p0[0]), int(p0[1]), int(p1[0]), int(p1[1]), color)
                rl.draw_circle(int(p0[0]), int(p0[1]), 3.0, color)
            if points:
                last = points[-1]
                rl.draw_circle(int(last[0]), int(last[1]), 3.0, color)
        elif kind == "navigation_radius":
            rl.draw_circle_lines(
                int(geometry.get("x", 0.0)),
                int(geometry.get("y", 0.0)),
                float(geometry.get("radius", 0.0)),
                color,
            )
        elif kind == "tile_chunk":
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

    def _build_collider_geometry(self, transform: Transform, collider: Collider) -> dict[str, Any]:
        left, top, right, bottom = collider.get_bounds(transform.x, transform.y)
        is_trigger = bool(getattr(collider, "is_trigger", False))
        return {
            "kind": "rect",
            "x": float(left),
            "y": float(top),
            "width": float(right - left),
            "height": float(bottom - top),
            "thickness": 2 if is_trigger else 1,
            "color": [0, 180, 255, 255] if is_trigger else [0, 255, 0, 255],
            "is_trigger": is_trigger,
        }

    def _build_tile_chunk_geometry(self, entity: Entity, command: RenderCommand) -> dict[str, Any] | None:
        transform = entity.get_component(Transform)
        if transform is None:
            return None
        bounds = command.chunk_data.get("bounds", {})
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

        width = float(self.PLACEHOLDER_WIDTH)
        height = float(self.PLACEHOLDER_HEIGHT)
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

        polygon = entity.get_component(Polygon2D)
        if polygon is not None and polygon.enabled and len(polygon.points) >= 3:
            min_x = float("inf")
            min_y = float("inf")
            max_x = float("-inf")
            max_y = float("-inf")
            sx = transform.scale_x
            sy = transform.scale_y
            for pt in polygon.points:
                wx = pt[0] * sx + polygon.offset_x
                wy = pt[1] * sy + polygon.offset_y
                if wx < min_x:
                    min_x = wx
                if wy < min_y:
                    min_y = wy
                if wx > max_x:
                    max_x = wx
                if wy > max_y:
                    max_y = wy
            width = max_x - min_x
            height = max_y - min_y
            left = transform.x + min_x
            top = transform.y + min_y
            offset_x = -min_x / width if width > 0 else 0.0
            offset_y = -min_y / height if height > 0 else 0.0
            return {"left": float(left), "top": float(top), "width": float(width), "height": float(height)}

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
        elif payload["kind"] in ("navigation_polygon", "navigation_path"):
            raw_points = payload.get("points", [])
            payload["points"] = [[float(pt[0]), float(pt[1])] for pt in raw_points if isinstance(pt, (list, tuple)) and len(pt) >= 2]
        elif payload["kind"] == "navigation_radius":
            payload["x"] = float(payload.get("x", 0.0))
            payload["y"] = float(payload.get("y", 0.0))
            payload["radius"] = float(payload.get("radius", 0.0))
        elif payload["kind"] == "tile_chunk":
            payload["x"] = float(payload.get("x", 0.0))
            payload["y"] = float(payload.get("y", 0.0))
            payload["width"] = float(payload.get("width", 0.0))
            payload["height"] = float(payload.get("height", 0.0))
            payload["thickness"] = int(payload.get("thickness", 1))
        return payload

    def _debug_overlay_signature(self) -> tuple[object, ...]:
        signature: list[object] = []
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

    def _clone_geometry(self, geometry: object) -> object:
        if isinstance(geometry, dict):
            return {key: self._clone_geometry(value) for key, value in geometry.items()}
        if isinstance(geometry, list):
            return [self._clone_geometry(value) for value in geometry]
        return geometry

    def _color_from_payload(self, color: object) -> rl.Color:
        values = list(color) if isinstance(color, (list, tuple)) else [255, 255, 255, 255]
        while len(values) < 4:
            values.append(255)
        return rl.Color(int(values[0]), int(values[1]), int(values[2]), int(values[3]))

    def _prepare_tilemap_chunk_targets(self, graph: dict[str, Any] | FramePlan2D) -> None:
        if isinstance(graph, FramePlan2D):
            self._pipeline_executor.prepare_tilemap_chunk_targets(graph)
            return
        self._tilemap_chunk_renderer.prepare_targets(graph, self._tilemap_chunk_cache)

    def _draw_tilemap_chunk(self, command: dict[str, Any]) -> None:
        self._tilemap_chunk_renderer.draw_chunk(command)

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

    def _load_texture(self, reference: Union[str, dict[str, str]], fallback_path: str, sync_callback: Callable[..., Any] | None = None) -> rl.Texture:
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
        geo = tilemap.resolve_tile_geometry() if hasattr(tilemap, 'resolve_tile_geometry') else None
        if geo:
            tile_width = max(1, int(geo.get("tile_width", 0) or tilemap.cell_width))
            tile_height = max(1, int(geo.get("tile_height", 0) or tilemap.cell_height))
            columns = max(1, int(geo.get("columns", 0) or 0))
            spacing = max(0, int(geo.get("spacing", 0)))
            margin = max(0, int(geo.get("margin", 0)))
        else:
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

    # ------------------------------------------------------------------
    # SubViewport rendering
    # ------------------------------------------------------------------

    def _render_sub_viewports(
        self,
        world: World,
        *,
        viewport_size: Optional[tuple[float, float]] = None,
    ) -> None:
        for entity in world.get_entities_with(SubViewport):
            viewport = entity.get_component(SubViewport)
            if viewport is None or not viewport.enabled:
                continue
            if viewport.render_target_update_mode == "once" and not viewport.needs_update:
                continue
            self._render_single_sub_viewport(world, entity, viewport, viewport_size=viewport_size)
            viewport.needs_update = False

    def _render_single_sub_viewport(
        self,
        world: World,
        entity: Entity,
        viewport: SubViewport,
        *,
        viewport_size: Optional[tuple[float, float]] = None,
    ) -> None:
        del viewport_size
        vp_name = entity.name or f"__subviewport_{entity.id}"
        w = viewport.size_x
        h = viewport.size_y
        transparent = viewport.transparent_bg

        self._viewport_renderer.get_or_create_texture(vp_name, w, h)
        self._viewport_renderer.begin_render(vp_name, transparent)

        try:
            children = world.get_children(entity.name) if hasattr(world, "get_children") else []
            for child_name in children:
                child = world.get_entity_by_name(child_name)
                if child is None or not child.active:
                    continue
                transform = child.get_component(Transform)
                if transform is None:
                    continue
                self._render_entity(child, transform)
        finally:
            self._viewport_renderer.end_render(vp_name)

        self._viewport_renderer.mark_dirty(vp_name)

    # ------------------------------------------------------------------
    # ViewportTexture rendering (Sprite with viewport texture)
    # ------------------------------------------------------------------

    def _draw_viewport_texture_sprite(self, transform: Transform, entity: Entity) -> None:
        viewport_tex = entity.get_component(ViewportTexture)
        if viewport_tex is None or not viewport_tex.enabled:
            return
        vp_name = viewport_tex.viewport_entity
        if not vp_name:
            return

        tex = self._viewport_renderer.get_texture(vp_name)
        if tex is None:
            return

        vp_dims = self._viewport_renderer.get_dimensions(vp_name)
        if vp_dims is None:
            return
        vp_w, vp_h = vp_dims

        width = int(vp_w * transform.scale_x)
        height = int(vp_h * transform.scale_y)
        dest_x = transform.x - (width * 0.5)
        dest_y = transform.y - (height * 0.5)
        source_rect = rl.Rectangle(0, 0, float(vp_w), -float(vp_h))
        dest_rect = rl.Rectangle(dest_x, dest_y, float(width), float(height))
        rl.draw_texture_pro(tex, source_rect, dest_rect, rl.Vector2(0, 0), transform.rotation, rl.WHITE)

    # ------------------------------------------------------------------
    # BackBufferCopy
    # ------------------------------------------------------------------

    def _capture_backbuffer(
        self,
        world: World,
        *,
        viewport_size: Optional[tuple[float, float]] = None,
    ) -> None:
        """Capture screen region to a RenderTexture for BackBufferCopy entities."""
        bb_entities = [
            (entity, entity.get_component(BackBufferCopy))
            for entity in world.get_entities_with(BackBufferCopy)
        ]
        bb_entities = [(e, bb) for e, bb in bb_entities if bb is not None and bb.enabled]
        if not bb_entities:
            return

        screen_w, screen_h = self._normalize_viewport_size(viewport_size)

        for entity, bb in bb_entities:
            name = f"__bbcopy_{entity.name or entity.id}"
            if bb.copy_mode == BackBufferCopy.COPY_MODE_VIEWPORT:
                rw, rh = screen_w, screen_h
                rx, ry = 0.0, 0.0
            else:
                rw = max(1, int(bb.rect_w))
                rh = max(1, int(bb.rect_h))
                rx, ry = bb.rect_x, bb.rect_y

            self._viewport_renderer.get_or_create_texture(name, rw, rh)
            self._viewport_renderer.begin_render(name, True)

            try:
                tex = self._viewport_renderer.get_render_texture(name)
                if tex is not None and hasattr(tex, "texture"):
                    dst = rl.Rectangle(rx, ry, float(rw), float(rh))
                    rl.draw_texture_rec(tex.texture, dst, rl.Vector2(0, 0), rl.WHITE)
            finally:
                self._viewport_renderer.end_render(name)

    # ------------------------------------------------------------------
    # Post-processing pipeline
    # ------------------------------------------------------------------

    def _apply_post_processing(
        self,
        world: World,
        *,
        viewport_size: Optional[tuple[float, float]] = None,
    ) -> None:
        """Capture current screen, apply post-processing effects, draw result."""
        from engine.components.post_process_effect import PostProcessEffectComp
        from engine.rendering.post_process import BlurEffect, ColorCorrectEffect

        pp_entities = [
            (entity, entity.get_component(PostProcessEffectComp))
            for entity in world.get_entities_with(PostProcessEffectComp)
        ]
        pp_entities = [(e, pp) for e, pp in pp_entities if pp is not None and pp.enabled]
        if not pp_entities:
            return

        screen_w, screen_h = self._normalize_viewport_size(viewport_size)
        self._post_process_pipeline.clear_effects()

        for _entity, pp_comp in pp_entities:
            for effect_data in pp_comp.effects:
                if not effect_data.get("enabled", True):
                    continue
                effect_type = str(effect_data.get("type", ""))
                if effect_type == "BlurEffect":
                    self._post_process_pipeline.add_effect(
                        BlurEffect(
                            radius=float(effect_data.get("radius", 4.0)),
                            name=str(effect_data.get("name", "")),
                            enabled=bool(effect_data.get("enabled", True)),
                        )
                    )
                elif effect_type == "ColorCorrectEffect":
                    self._post_process_pipeline.add_effect(
                        ColorCorrectEffect(
                            brightness=float(effect_data.get("brightness", 1.0)),
                            contrast=float(effect_data.get("contrast", 1.0)),
                            saturation=float(effect_data.get("saturation", 1.0)),
                            name=str(effect_data.get("name", "")),
                            enabled=bool(effect_data.get("enabled", True)),
                        )
                    )

        if not self._post_process_pipeline.effects:
            return

        self._render_targets.ensure("__post_process_src", screen_w, screen_h)
        self._render_targets.ensure("__post_process_dst", screen_w, screen_h)

        pp_src = self._render_targets.get("__post_process_src")
        if pp_src is None or pp_src.render_texture is None:
            return

        result = self._post_process_pipeline.process(pp_src.render_texture, screen_w, screen_h)
        result_tex = result.texture if hasattr(result, "texture") else result
        if result_tex is None:
            return

        source_rect = rl.Rectangle(0, 0, float(result_tex.width), -float(result_tex.height))
        dest_rect = rl.Rectangle(0, 0, float(screen_w), float(screen_h))
        rl.draw_texture_pro(result_tex, source_rect, dest_rect, rl.Vector2(0, 0), 0.0, rl.WHITE)

    def cleanup(self) -> None:
        self._texture_manager.unload_all()
        self._render_targets.unload_all()
        self._viewport_renderer.cleanup()
        self._post_process_pipeline.cleanup()
