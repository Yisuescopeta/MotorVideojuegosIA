from __future__ import annotations

from typing import Any, Optional

import pyray as rl
from engine.components.collider import Collider
from engine.components.sprite import Sprite
from engine.components.transform import Transform
from engine.ecs.world import World
from engine.rendering.pipeline_types import FramePlan2D, RenderCommand2D, RenderTargetJob2D


class RenderPipelineExecutor2D:
    """Executes typed frame plans using the current RenderSystem draw helpers."""

    def __init__(self, owner: Any) -> None:
        self._owner = owner
        self._command_handlers = {
            "entity": self._render_entity_command,
            "tilemap_chunk": self._render_tilemap_chunk_command,
            "debug": self._render_debug_command,
        }
        self._debug_handlers = {
            "collider": self._render_collider_debug_command,
            "joint": self._render_joint_debug_command,
            "selection": self._render_selection_debug_command,
        }
        self._target_job_handlers = {
            "debug_overlay": self._execute_debug_overlay_job,
            "minimap": self._execute_minimap_job,
        }

    def prepare_tilemap_chunk_targets(self, frame_plan: FramePlan2D) -> None:
        for pass_plan in frame_plan.passes:
            for command in pass_plan.commands:
                if command.kind == "tilemap_chunk":
                    self._owner._tilemap_chunk_renderer.prepare_target(command.to_payload(), self._owner._tilemap_chunk_cache)

    def render_pass(self, frame_plan: FramePlan2D, pass_name: str) -> None:
        pass_plan = frame_plan.get_pass(pass_name)
        if pass_plan is None:
            return
        for batch in pass_plan.batches:
            self._owner._begin_batch_state(batch.key)
            try:
                for command in batch.commands:
                    handler = self._command_handlers.get(command.kind)
                    if handler is not None:
                        handler(command)
            finally:
                self._owner._end_batch_state(batch.key)

    def execute_render_target_jobs(
        self,
        frame_plan: FramePlan2D,
        *,
        world: World | None,
        camera: Optional[rl.Camera2D],
        viewport_size: Optional[tuple[float, float]],
    ) -> None:
        for job in frame_plan.render_target_jobs:
            handler = self._target_job_handlers.get(job.kind)
            if handler is not None:
                handler(job, world=world, camera=camera, viewport_size=viewport_size)

    def execute_render_target_job(
        self,
        job: RenderTargetJob2D,
        *,
        world: World | None,
        camera: Optional[rl.Camera2D],
        viewport_size: Optional[tuple[float, float]],
    ) -> None:
        handler = self._target_job_handlers.get(job.kind)
        if handler is not None:
            handler(job, world=world, camera=camera, viewport_size=viewport_size)

    def _render_entity_command(self, command: RenderCommand2D) -> None:
        entity = command.entity
        if entity is None:
            return
        transform = entity.get_component(Transform)
        if transform is None:
            return
        self._owner._render_entity(entity, transform)

    def _render_tilemap_chunk_command(self, command: RenderCommand2D) -> None:
        self._owner._draw_tilemap_chunk(command.to_payload())

    def _render_debug_command(self, command: RenderCommand2D) -> None:
        handler = self._debug_handlers.get(command.debug_kind, self._render_generic_debug_command)
        handler(command)

    def _render_collider_debug_command(self, command: RenderCommand2D) -> None:
        entity = command.entity
        if entity is None:
            return
        transform = entity.get_component(Transform)
        collider = entity.get_component(Collider)
        if transform is not None and collider is not None:
            self._owner._draw_collider(transform, collider)

    def _render_joint_debug_command(self, command: RenderCommand2D) -> None:
        if command.entity is not None:
            self._owner._draw_joint(command.entity)

    def _render_selection_debug_command(self, command: RenderCommand2D) -> None:
        if command.entity is not None:
            self._owner._draw_selection_highlight(command.entity)

    def _render_generic_debug_command(self, command: RenderCommand2D) -> None:
        self._owner._draw_debug_primitive(command.geometry)

    def _execute_debug_overlay_job(
        self,
        job: RenderTargetJob2D,
        *,
        world: World | None,
        camera: Optional[rl.Camera2D],
        viewport_size: Optional[tuple[float, float]],
    ) -> None:
        del world, viewport_size
        self._owner._render_targets.begin(job.name, job.width, job.height, rl.Color(0, 0, 0, 0))
        try:
            if camera is not None:
                rl.begin_mode_2d(camera)
            for command in job.commands:
                self._render_debug_command(command)
            if camera is not None:
                rl.end_mode_2d()
        finally:
            self._owner._render_targets.end()

        destination = rl.Rectangle(0, 0, job.width, job.height)
        self._owner._render_targets.compose(job.name, destination, rl.WHITE)

    def _execute_minimap_job(
        self,
        job: RenderTargetJob2D,
        *,
        world: World | None,
        camera: Optional[rl.Camera2D],
        viewport_size: Optional[tuple[float, float]],
    ) -> None:
        del world, camera
        self._owner._render_targets.begin(job.name, job.width, job.height, rl.Color(12, 14, 18, 235))
        try:
            renderables = [command.entity for command in job.commands if command.kind == "entity" and command.entity is not None]
            bounds = self._owner._compute_minimap_bounds(renderables)
            for entity in renderables:
                transform = entity.get_component(Transform)
                if transform is None:
                    continue
                point = self._owner._project_to_minimap(transform.x, transform.y, bounds, job.width, job.height)
                sprite = entity.get_component(Sprite)
                color = rl.LIGHTGRAY if sprite is None else rl.Color(*sprite.tint)
                rl.draw_circle(int(point[0]), int(point[1]), 2.0, color)
            rl.draw_rectangle_lines(0, 0, job.width, job.height, rl.Color(100, 140, 180, 255))
        finally:
            self._owner._render_targets.end()

        viewport_width, _ = self._owner._normalize_viewport_size(viewport_size)
        destination = rl.Rectangle(float(viewport_width - job.width - job.margin), float(job.margin), float(job.width), float(job.height))
        self._owner._render_targets.compose(job.name, destination, rl.WHITE)
