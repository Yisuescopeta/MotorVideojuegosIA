"""engine/systems/animation_tree_system.py - Processes AnimationTree components and blends animations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional

from engine.components.animation_tree import AnimationTree
from engine.components.animator import Animator
from engine.resources.animation_tree import AnimationNodeType

if TYPE_CHECKING:
    from engine.ecs.world import World


class AnimationTreeSystem:
    """Processes AnimationTree components and blends animation results."""

    def update(self, world: "World", dt: float) -> None:
        for entity in world.get_entities_with(AnimationTree):
            tree = entity.get_component(AnimationTree)
            if tree is None or not tree.active:
                continue
            animator = entity.get_component(Animator)
            if animator is None:
                continue
            self._process_tree(tree, animator, world, dt)

    def _process_tree(self, tree: AnimationTree, animator: Animator, world: "World", dt: float) -> None:
        if tree.tree_root is None:
            return

        tree._current_weights.clear()
        self._walk_node(tree.tree_root.root_node_id, tree, animator, 1.0, dt)
        self._apply_blend(tree, animator)

    def _walk_node(self, node_id: str, tree: AnimationTree, animator: Animator, weight: float, dt: float) -> None:
        node = tree.tree_root.nodes.get(node_id) if tree.tree_root else None
        if node is None:
            return

        if node.node_type == AnimationNodeType.ANIMATION:
            anim_name = node.animation
            if anim_name:
                tree._current_weights[anim_name] = tree._current_weights.get(anim_name, 0.0) + weight
                pos = tree._current_positions.get(anim_name, 0.0)
                tree._current_positions[anim_name] = pos + dt * tree.speed_scale

        elif node.node_type == AnimationNodeType.BLEND_SPACE_2D:
            x = float(tree.parameters.get(f"{node.blend_space_name}_x", 0.0))
            y = float(tree.parameters.get(f"{node.blend_space_name}_y", 0.0))
            weights_map = self._compute_blend_space_2d(node, x, y)
            for point_idx, point_weight in weights_map.items():
                child_id = node.children[point_idx] if point_idx < len(node.children) else None
                if child_id:
                    self._walk_node(child_id, tree, animator, weight * point_weight, dt)

        elif node.node_type == AnimationNodeType.STATE_MACHINE:
            current_state = tree.parameters.get(f"{node_id}_state", node.entry_state)
            for child_id in node.children:
                child_node = tree.tree_root.nodes.get(child_id) if tree.tree_root else None
                if child_node and child_node.node_id == current_state:
                    self._walk_node(child_id, tree, animator, weight, dt)

        elif node.node_type == AnimationNodeType.BLEND2:
            blend = node.blend_amount
            for i, child_id in enumerate(node.children):
                child_weight = blend if i == 0 else (1.0 - blend)
                self._walk_node(child_id, tree, animator, weight * child_weight, dt)

        elif node.node_type == AnimationNodeType.TIME_SCALE:
            scale = float(tree.parameters.get(f"{node_id}_scale", 1.0))
            for child_id in node.children:
                self._walk_node(child_id, tree, animator, weight, dt * scale)

    def _compute_blend_space_2d(self, node: "AnimationNode", x: float, y: float) -> Dict[int, float]:
        if not node.blend_points:
            return {}
        best_idx = 0
        best_dist = float("inf")
        for i, pt in enumerate(node.blend_points):
            dist = ((pt.x - x) ** 2 + (pt.y - y) ** 2) ** 0.5
            if dist < best_dist:
                best_dist = dist
                best_idx = i
        return {best_idx: 1.0}

    def _apply_blend(self, tree: AnimationTree, animator: Animator) -> None:
        if not tree._current_weights:
            return
        total_weight = sum(tree._current_weights.values())
        if total_weight <= 0:
            return
        best_anim = max(tree._current_weights, key=tree._current_weights.get)
        if best_anim != animator.current_state and best_anim in animator.animations:
            animator.play(best_anim)
