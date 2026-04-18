from __future__ import annotations

from copy import deepcopy
from typing import Any

from engine.rendering.pipeline_types import FramePlan2D, RenderPassPlan2D, RenderTargetJob2D


class RenderPipelinePlanner2D:
    """Adapts legacy render payloads into typed plans for future pipeline work."""

    def __init__(self, owner: Any | None = None) -> None:
        self._owner = owner

    def adapt_graph_payload(self, graph_payload: dict[str, Any]) -> FramePlan2D:
        return FramePlan2D(
            passes=[RenderPassPlan2D.from_payload(pass_payload) for pass_payload in graph_payload.get("passes", [])],
            render_target_jobs=[],
            totals=deepcopy(dict(graph_payload.get("totals", {}))),
        )

    def adapt_frame_plan_payload(self, frame_plan_payload: dict[str, Any]) -> FramePlan2D:
        graph_model = self.adapt_graph_payload(frame_plan_payload.get("graph", {}))
        passes_by_name = {pass_plan.name: pass_plan for pass_plan in graph_model.passes}
        jobs = [
            self._adapt_render_target_job_payload(job_payload, passes_by_name)
            for job_payload in frame_plan_payload.get("render_targets", [])
        ]
        return FramePlan2D(
            passes=list(graph_model.passes),
            render_target_jobs=jobs,
            totals=deepcopy(dict(frame_plan_payload.get("totals", graph_model.totals))),
        )

    def _adapt_render_target_job_payload(
        self,
        job_payload: dict[str, Any],
        passes_by_name: dict[str, RenderPassPlan2D],
    ) -> RenderTargetJob2D:
        kind = str(job_payload.get("kind", ""))
        commands = []
        if kind == "debug_overlay":
            commands = list(passes_by_name.get("Debug", RenderPassPlan2D(name="Debug")).commands)
        elif kind == "minimap":
            world_pass = passes_by_name.get("World")
            if world_pass is not None:
                commands = [command for command in world_pass.commands if command.kind == "entity"]
        return RenderTargetJob2D(
            name=str(job_payload.get("name", "")),
            kind=kind,
            width=int(job_payload.get("width", 0)),
            height=int(job_payload.get("height", 0)),
            margin=int(job_payload.get("margin", 0)),
            commands=commands,
        )
