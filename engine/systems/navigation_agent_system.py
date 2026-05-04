"""engine/systems/navigation_agent_system.py — NavigationAgentSystem: updates NavigationAgent2D entities."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from engine.components.navigation_agent_2d import NavigationAgent2D
from engine.components.transform import Transform

if TYPE_CHECKING:
    from engine.ecs.world import World
    from engine.navigation.service import NavigationService


class NavigationAgentSystem:
    """Moves entities with NavigationAgent2D toward their target using pathfinding.

    Injects NavigationService for path queries. Updates velocity and position
    each update tick.
    """

    def __init__(self, nav_service: "NavigationService | None" = None) -> None:
        self._nav_service: NavigationService | None = nav_service

    def set_nav_service(self, nav_service: "NavigationService") -> None:
        self._nav_service = nav_service

    def reset(self) -> None:
        pass

    def update(self, world: "World", dt: float) -> None:
        dt = max(0.0, float(dt))
        if dt <= 0.0:
            return
        if self._nav_service is None:
            return
        grid = self._nav_service.grid
        if grid is None:
            return

        if not hasattr(world, "get_entities_with"):
            return

        for entity in world.get_entities_with(Transform, NavigationAgent2D):
            agent = entity.get_component(NavigationAgent2D)
            transform = entity.get_component(Transform)
            if agent is None or transform is None:
                continue
            if not agent.enabled:
                continue

            target_changed = (
                abs(agent.target_x - agent._last_target_x) > 0.001
                or abs(agent.target_y - agent._last_target_y) > 0.001
            )

            if target_changed or not agent.path:
                self._recalculate_path(agent, transform)
                agent._last_target_x = agent.target_x
                agent._last_target_y = agent.target_y
                agent.current_path_index = 0
                agent.is_navigation_finished = False
                agent.is_target_reached = False

            if agent.is_navigation_finished or agent.is_target_reached:
                agent.velocity_x = 0.0
                agent.velocity_y = 0.0
                continue

            dist_to_target = agent.distance_to_target(transform.x, transform.y)
            if dist_to_target <= agent.target_reached_distance:
                agent.is_target_reached = True
                agent.is_navigation_finished = True
                agent.velocity_x = 0.0
                agent.velocity_y = 0.0
                continue

            self._move_along_path(agent, transform, dt)

            world.touch_transform()

    def _recalculate_path(self, agent: NavigationAgent2D, transform: Transform) -> None:
        if self._nav_service is None:
            return

        result = self._nav_service.query_world_path(
            wx_start=transform.x,
            wy_start=transform.y,
            wx_goal=agent.target_x,
            wy_goal=agent.target_y,
            diagonal=True,
        )

        if not result.success or not result.path:
            agent.path = []
            agent.is_navigation_finished = True
            agent.velocity_x = 0.0
            agent.velocity_y = 0.0
            return

        grid = self._nav_service.grid
        if grid is None:
            agent.path = []
            agent.is_navigation_finished = True
            return

        agent.path = []
        for gp in result.path:
            wx, wy = grid.grid_to_world_center(gp.x, gp.y)
            agent.path.append([wx, wy])

        agent.is_navigation_finished = False

    def _move_along_path(
        self, agent: NavigationAgent2D, transform: Transform, dt: float
    ) -> None:
        if not agent.path or agent.current_path_index >= len(agent.path):
            agent.is_navigation_finished = True
            agent.velocity_x = 0.0
            agent.velocity_y = 0.0
            return

        # Advance through waypoints we're close enough to
        while agent.current_path_index < len(agent.path):
            wp = agent.path[agent.current_path_index]
            dx = wp[0] - transform.x
            dy = wp[1] - transform.y
            dist = math.sqrt(dx * dx + dy * dy)

            if dist <= agent.path_desired_distance:
                agent.current_path_index += 1
                if agent.current_path_index >= len(agent.path):
                    agent.is_navigation_finished = True
                    agent.velocity_x = 0.0
                    agent.velocity_y = 0.0
                    return
            else:
                break

        wp = agent.path[agent.current_path_index]
        dx = wp[0] - transform.x
        dy = wp[1] - transform.y
        dist = math.sqrt(dx * dx + dy * dy)

        if dist < 0.001:
            agent.current_path_index += 1
            return

        dir_x = dx / dist
        dir_y = dy / dist

        move = agent.speed * dt
        agent.velocity_x = dir_x * agent.speed
        agent.velocity_y = dir_y * agent.speed
        transform.x += dir_x * move
        transform.y += dir_y * move
