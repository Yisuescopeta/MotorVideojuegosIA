from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RenderCommand2D:
    """Typed render command used by the 2D pipeline foundation."""

    kind: str
    entity: Any = None
    entity_name: str = ""
    render_pass: str = ""
    sorting_layer: str = ""
    order_in_layer: int = 0
    batch_key: dict[str, Any] = field(default_factory=dict)
    debug_kind: str = ""
    chunk_id: str = ""
    chunk_data: dict[str, Any] = field(default_factory=dict)
    geometry: dict[str, Any] = field(default_factory=dict)
    cache_key: Any = None
    render_target_name: str = ""
    render_target_dirty: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "RenderCommand2D":
        known_fields = {
            "kind",
            "entity",
            "entity_name",
            "render_pass",
            "sorting_layer",
            "order_in_layer",
            "batch_key",
            "debug_kind",
            "chunk_id",
            "chunk_data",
            "geometry",
            "cache_key",
            "render_target_name",
            "render_target_dirty",
        }
        return cls(
            kind=str(payload.get("kind", "")),
            entity=payload.get("entity"),
            entity_name=str(payload.get("entity_name", "")),
            render_pass=str(payload.get("render_pass", "")),
            sorting_layer=str(payload.get("sorting_layer", "")),
            order_in_layer=int(payload.get("order_in_layer", 0)),
            batch_key=dict(payload.get("batch_key", {})),
            debug_kind=str(payload.get("debug_kind", "")),
            chunk_id=str(payload.get("chunk_id", "")),
            chunk_data=dict(payload.get("chunk_data", {})),
            geometry=dict(payload.get("geometry", {})),
            cache_key=payload.get("cache_key"),
            render_target_name=str(payload.get("render_target_name", "")),
            render_target_dirty=bool(payload.get("render_target_dirty", True)),
            metadata={key: value for key, value in payload.items() if key not in known_fields},
        )

    def to_payload(self) -> dict[str, Any]:
        payload = dict(self.metadata)
        payload.update(
            {
                "kind": self.kind,
                "entity": self.entity,
                "entity_name": self.entity_name,
                "render_pass": self.render_pass,
                "sorting_layer": self.sorting_layer,
                "order_in_layer": self.order_in_layer,
                "batch_key": self.batch_key,
                "debug_kind": self.debug_kind,
                "chunk_id": self.chunk_id,
                "chunk_data": self.chunk_data,
                "geometry": self.geometry,
                "cache_key": self.cache_key,
                "render_target_name": self.render_target_name,
                "render_target_dirty": self.render_target_dirty,
            }
        )
        return payload


@dataclass
class RenderBatch2D:
    """Contiguous batch grouped by render state."""

    key: dict[str, Any]
    commands: list[RenderCommand2D] = field(default_factory=list)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "RenderBatch2D":
        return cls(
            key=dict(payload.get("key", {})),
            commands=[RenderCommand2D.from_payload(command) for command in payload.get("commands", [])],
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "key": dict(self.key),
            "commands": [command.to_payload() for command in self.commands],
        }


@dataclass
class RenderPassPlan2D:
    """Planned render pass with commands, batches and metrics."""

    name: str
    commands: list[RenderCommand2D] = field(default_factory=list)
    batches: list[RenderBatch2D] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "RenderPassPlan2D":
        return cls(
            name=str(payload.get("name", "")),
            commands=[RenderCommand2D.from_payload(command) for command in payload.get("commands", [])],
            batches=[RenderBatch2D.from_payload(batch) for batch in payload.get("batches", [])],
            stats=dict(payload.get("stats", {})),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "commands": [command.to_payload() for command in self.commands],
            "batches": [batch.to_payload() for batch in self.batches],
            "stats": dict(self.stats),
        }


@dataclass
class RenderTargetJob2D:
    """Post-pass render target work scheduled by the pipeline."""

    name: str
    kind: str
    width: int
    height: int
    margin: int = 0
    commands: list[RenderCommand2D] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_payload(self, *, include_commands: bool = False) -> dict[str, Any]:
        payload = dict(self.metadata)
        payload.update(
            {
                "name": self.name,
                "kind": self.kind,
                "width": int(self.width),
                "height": int(self.height),
            }
        )
        if self.margin:
            payload["margin"] = int(self.margin)
        if include_commands:
            payload["commands"] = [command.to_payload() for command in self.commands]
        return payload


@dataclass
class FramePlan2D:
    """Typed frame plan produced by the planner and consumed by the executor."""

    passes: list[RenderPassPlan2D] = field(default_factory=list)
    render_target_jobs: list[RenderTargetJob2D] = field(default_factory=list)
    totals: dict[str, Any] = field(default_factory=dict)

    def get_pass(self, name: str) -> RenderPassPlan2D | None:
        for pass_plan in self.passes:
            if pass_plan.name == name:
                return pass_plan
        return None

    def to_graph_payload(self) -> dict[str, Any]:
        return {
            "passes": [pass_plan.to_payload() for pass_plan in self.passes],
            "totals": deepcopy(self.totals),
        }

    def to_payload(self) -> dict[str, Any]:
        return {
            "graph": self.to_graph_payload(),
            "render_targets": [job.to_payload() for job in self.render_target_jobs],
            "totals": deepcopy(self.totals),
        }
