"""
engine/physics/island_manager.py - Constraint island builder for 2D physics.

Groups rigid bodies into independent islands based on contact constraints
and joint connections. Each island is solved independently by the PGS solver,
enabling correct multi-body stacking and island-level sleeping.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.physics.contact_solver import ContactConstraint2D


@dataclass
class Island2D:
    """A group of bodies connected by contacts and/or joints.

    All constraints within an island are solved together in one PGS pass.
    Islands are independent — bodies in different islands don't interact.
    """
    body_ids: set[int] = field(default_factory=set)
    constraints: list[ContactConstraint2D] = field(default_factory=list)
    sleeping: bool = False
    sleep_timer: float = 0.0

    @property
    def size(self) -> int:
        """Number of bodies in this island."""
        return len(self.body_ids)

    @property
    def constraint_count(self) -> int:
        """Number of constraints in this island."""
        return len(self.constraints)


class IslandBuilder2D:
    """Builds constraint islands from contacts and joints using BFS connectivity."""

    @staticmethod
    def build_islands(
        constraints: list[ContactConstraint2D],
        joint_pairs: list[tuple[int, int]],
        all_body_ids: set[int],
        body_id_to_island: dict[int, Island2D] | None = None,
    ) -> list[Island2D]:
        """Group bodies into islands based on contact + joint connectivity.

        Args:
            constraints: All contact constraints for this frame.
            joint_pairs: List of (body_a_id, body_b_id) tuples for active joints.
            all_body_ids: Set of all dynamic/kinematic body IDs in the scene.
            body_id_to_island: Optional previous frame island mapping for
                island persistence (sleep state transfer).

        Returns:
            List of Island2D, one per connected component.
        """
        # Collect all referenced body IDs (explicit + implicit from constraints/joints)
        effective_ids: set[int] = set(all_body_ids)
        for c in constraints:
            effective_ids.add(c.entity_a_id)
            effective_ids.add(c.entity_b_id)
        for a, b in joint_pairs:
            effective_ids.add(a)
            effective_ids.add(b)

        # Build adjacency list from constraints and joints
        adjacency: dict[int, set[int]] = {bid: set() for bid in effective_ids}

        for c in constraints:
            a, b = c.entity_a_id, c.entity_b_id
            adjacency.setdefault(a, set()).add(b)
            adjacency.setdefault(b, set()).add(a)

        for a, b in joint_pairs:
            adjacency.setdefault(a, set()).add(b)
            adjacency.setdefault(b, set()).add(a)

        # BFS to find connected components (islands)
        visited: set[int] = set()
        islands: list[Island2D] = []

        # Track previous island sleep state for persistence
        prev_island_for_body: dict[int, Island2D] = {}
        if body_id_to_island:
            for island in body_id_to_island.values():
                for bid in island.body_ids:
                    prev_island_for_body[bid] = island

        for start_id in sorted(effective_ids):
            if start_id in visited:
                continue

            # BFS from this unvisited body
            component = IslandBuilder2D._bfs_component(start_id, adjacency, visited)
            island = Island2D(body_ids=component)

            # Assign constraints to this island
            for c in constraints:
                if c.entity_a_id in component and c.entity_b_id in component:
                    island.constraints.append(c)

            # Transfer sleep state from previous frame if available
            if body_id_to_island and component:
                sample_body = next(iter(component))
                prev = prev_island_for_body.get(sample_body)
                if prev and prev.sleeping:
                    # Check if all bodies in this island were in the same sleeping island
                    all_same_prev = all(
                        prev_island_for_body.get(bid) is prev
                        for bid in component
                    )
                    if all_same_prev:
                        island.sleeping = True
                        island.sleep_timer = prev.sleep_timer

            islands.append(island)

        return islands

    @staticmethod
    def _bfs_component(
        start_id: int,
        adjacency: dict[int, set[int]],
        visited: set[int],
    ) -> set[int]:
        """BFS from start_id to find all connected body IDs."""
        component: set[int] = set()
        queue = [start_id]
        visited.add(start_id)

        while queue:
            current = queue.pop(0)
            component.add(current)
            for neighbor in adjacency.get(current, ()):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)

        return component
