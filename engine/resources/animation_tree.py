"""engine/resources/animation_tree.py - AnimationTree resource (Godot-style blending tree)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List


class AnimationNodeType(Enum):
    OUTPUT = "output"
    ANIMATION = "animation"
    BLEND_SPACE_2D = "blend_space_2d"
    STATE_MACHINE = "state_machine"
    BLEND2 = "blend2"
    TIME_SCALE = "time_scale"


@dataclass
class BlendPoint2D:
    """A point in 2D blend space mapping (x, y) position to an animation."""
    x: float = 0.0
    y: float = 0.0
    animation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"x": self.x, "y": self.y, "animation": self.animation}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BlendPoint2D":
        if not isinstance(data, dict):
            return cls()
        return cls(
            x=float(data.get("x", 0.0)),
            y=float(data.get("y", 0.0)),
            animation=str(data.get("animation", "")),
        )


@dataclass
class AnimationNode:
    """A node in the animation tree."""
    node_id: str = ""
    node_type: AnimationNodeType = AnimationNodeType.ANIMATION
    animation: str = ""
    children: List[str] = field(default_factory=list)
    # BlendSpace2D
    blend_space_name: str = ""
    blend_points: List[BlendPoint2D] = field(default_factory=list)
    min_x: float = -1.0
    max_x: float = 1.0
    min_y: float = -1.0
    max_y: float = 1.0
    x_label: str = "x"
    y_label: str = "y"
    # Blend2
    blend_amount: float = 0.0
    # State Machine properties
    entry_state: str = ""
    states: Dict[str, dict] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "node_id": self.node_id,
            "node_type": self.node_type.value,
            "animation": self.animation,
            "children": list(self.children),
        }
        if self.node_type == AnimationNodeType.BLEND_SPACE_2D:
            result.update({
                "blend_space_name": self.blend_space_name,
                "blend_points": [bp.to_dict() for bp in self.blend_points],
                "min_x": self.min_x,
                "max_x": self.max_x,
                "min_y": self.min_y,
                "max_y": self.max_y,
                "x_label": self.x_label,
                "y_label": self.y_label,
            })
        if self.node_type == AnimationNodeType.BLEND2:
            result["blend_amount"] = self.blend_amount
        if self.node_type == AnimationNodeType.STATE_MACHINE:
            result["entry_state"] = self.entry_state
            result["states"] = {k: dict(v) for k, v in self.states.items()}
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AnimationNode":
        if not isinstance(data, dict):
            return cls()
        raw_type = data.get("node_type", "animation")
        try:
            node_type = AnimationNodeType(raw_type)
        except ValueError:
            node_type = AnimationNodeType.ANIMATION
        return cls(
            node_id=str(data.get("node_id", "")),
            node_type=node_type,
            animation=str(data.get("animation", "")),
            children=list(data.get("children", []) or []),
            blend_space_name=str(data.get("blend_space_name", "")),
            blend_points=[BlendPoint2D.from_dict(bp) for bp in (data.get("blend_points") or [])],
            min_x=float(data.get("min_x", -1.0)),
            max_x=float(data.get("max_x", 1.0)),
            min_y=float(data.get("min_y", -1.0)),
            max_y=float(data.get("max_y", 1.0)),
            x_label=str(data.get("x_label", "x")),
            y_label=str(data.get("y_label", "y")),
            blend_amount=float(data.get("blend_amount", 0.0)),
            entry_state=str(data.get("entry_state", "")),
            states={k: dict(v) for k, v in (data.get("states") or {}).items()},
        )


@dataclass
class AnimationTreeResource:
    """AnimationTree resource — defines blending and state machine logic."""
    resource_id: str = ""
    root_node_id: str = "output"
    nodes: Dict[str, AnimationNode] = field(default_factory=dict)
    parameters: Dict[str, Any] = field(default_factory=dict)

    def add_node(self, node: AnimationNode) -> None:
        self.nodes[node.node_id] = node

    def connect_nodes(self, parent_id: str, child_id: str) -> None:
        if parent_id in self.nodes:
            if child_id not in self.nodes[parent_id].children:
                self.nodes[parent_id].children.append(child_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "root_node_id": self.root_node_id,
            "nodes": {nid: node.to_dict() for nid, node in self.nodes.items()},
            "parameters": dict(self.parameters),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AnimationTreeResource":
        if not isinstance(data, dict):
            return cls()
        nodes = {}
        raw_nodes = data.get("nodes", {}) or {}
        if isinstance(raw_nodes, dict):
            for nid, ndata in raw_nodes.items():
                if isinstance(ndata, dict):
                    nodes[str(nid)] = AnimationNode.from_dict(ndata)
        return cls(
            resource_id=str(data.get("resource_id", "")),
            root_node_id=str(data.get("root_node_id", "output")),
            nodes=nodes,
            parameters=dict(data.get("parameters", {}) or {}),
        )
