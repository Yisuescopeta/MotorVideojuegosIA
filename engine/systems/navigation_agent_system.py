"""engine/systems/navigation_agent_system.py — NavigationAgentSystem: updates NavigationAgent2D entities."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

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

    def _collect_obstacles(self, world: "World") -> list:
        """Collect entities with NavigationObstacle2D for avoidance."""
        from engine.components.navigation_obstacle_2d import NavigationObstacle2D

        obstacles: list = []
        if not hasattr(world, "get_entities_with"):
            return obstacles
        for entity in world.get_entities_with(Transform, NavigationObstacle2D):
            obstacle = entity.get_component(NavigationObstacle2D)
            transform = entity.get_component(Transform)
            if obstacle is not None and transform is not None:
                obstacles.append((entity, obstacle, transform))
        return obstacles

    def _apply_avoidance(
        self,
        agent_entity,
        agent_comp: NavigationAgent2D,
        transform: Transform,
        world: "World",
        obstacles: list,
        dt: float,
    ) -> None:
        """Apply local avoidance to prevent agents from colliding with each other."""
        if agent_comp.avoidance_radius <= 0.0:
            return

        avoidance_force_x = 0.0
        avoidance_force_y = 0.0

        # Avoidance between navigation agents
        for other_entity in world.get_entities_with(Transform, NavigationAgent2D):
            if other_entity is agent_entity:
                continue
            other_agent = other_entity.get_component(NavigationAgent2D)
            other_transform = other_entity.get_component(Transform)
            if other_agent is None or other_transform is None:
                continue
            if other_agent.avoidance_radius <= 0.0:
                continue

            dx = transform.x - other_transform.x
            dy = transform.y - other_transform.y
            dist = math.sqrt(dx * dx + dy * dy)

            avoidance_dist = agent_comp.avoidance_radius + other_agent.avoidance_radius
            if dist < avoidance_dist and dist > 0.01:
                overlap = avoidance_dist - dist
                force = overlap / avoidance_dist * agent_comp.speed * 2.0
                nx = dx / dist
                ny = dy / dist
                avoidance_force_x += nx * force
                avoidance_force_y += ny * force

        # Avoidance against dynamic obstacles
        for _entity, obstacle, obs_transform in obstacles:
            if not obstacle.affect_avoidance:
                continue
            dx = transform.x - obs_transform.x
            dy = transform.y - obs_transform.y
            dist = math.sqrt(dx * dx + dy * dy)

            avoidance_dist = agent_comp.avoidance_radius + obstacle.radius
            if dist < avoidance_dist and dist > 0.01:
                overlap = avoidance_dist - dist
                force = overlap / avoidance_dist * agent_comp.speed * 1.5
                nx = dx / dist
                ny = dy / dist
                avoidance_force_x += nx * force
                avoidance_force_y += ny * force

        # Blend avoidance with path following velocity
        if abs(avoidance_force_x) > 0.01 or abs(avoidance_force_y) > 0.01:
            blend = 0.5
            agent_comp.velocity_x = agent_comp.velocity_x * blend + avoidance_force_x * (1.0 - blend)
            agent_comp.velocity_y = agent_comp.velocity_y * blend + avoidance_force_y * (1.0 - blend)

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

        obstacles = self._collect_obstacles(world)

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
            self._apply_avoidance(entity, agent, transform, world, obstacles, dt)

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

    def get_debug_primitives(self, world: "World") -> list[dict[str, Any]]:
        """Build debug primitives for navigation visualization.

        Returns list of debug primitives compatible with RenderSystem.set_debug_primitives().
        Colors: navigation_polygon=blue, agent_path=green, agent_radius=yellow, obstacle=red.
        """
        primitives: list[dict[str, Any]] = []
        NAV_BLUE = [50, 100, 255, 150]
        NAV_GREEN = [50, 255, 50, 150]
        NAV_YELLOW = [255, 255, 50, 150]
        NAV_RED = [255, 50, 50, 150]

        # Draw navigation grid bounds if available
        if self._nav_service is not None and self._nav_service.grid is not None:
            grid = self._nav_service.grid
            gw = float(grid.width * grid.cell_size)
            gh = float(grid.height * grid.cell_size)
            primitives.append({
                "kind": "navigation_polygon",
                "color": NAV_BLUE,
                "points": [
                    [0.0, 0.0],
                    [gw, 0.0],
                    [gw, gh],
                    [0.0, gh],
                ],
                "entity_name": "__nav_grid__",
            })

        if not hasattr(world, "get_entities_with"):
            return primitives

        # Collect agent paths and avoidance radii
        for entity in world.get_entities_with(Transform, NavigationAgent2D):
            agent = entity.get_component(NavigationAgent2D)
            transform = entity.get_component(Transform)
            if agent is None or transform is None or not agent.enabled:
                continue

            # Agent path
            if agent.path:
                path_points: list[list[float]] = []
                path_points.append([transform.x, transform.y])
                for wp in agent.path:
                    path_points.append([float(wp[0]), float(wp[1])])
                primitives.append({
                    "kind": "navigation_path",
                    "color": NAV_GREEN,
                    "points": path_points,
                    "entity_name": entity.name,
                })

            # Agent avoidance radius
            if agent.avoidance_radius > 0.0:
                primitives.append({
                    "kind": "navigation_radius",
                    "color": NAV_YELLOW,
                    "x": transform.x,
                    "y": transform.y,
                    "radius": agent.avoidance_radius,
                    "entity_name": entity.name,
                })

        # Obstacle radii
        obstacles = self._collect_obstacles(world)
        for obs_entity, obstacle, obs_transform in obstacles:
            if obstacle.radius > 0.0:
                primitives.append({
                    "kind": "navigation_radius",
                    "color": NAV_RED,
                    "x": obs_transform.x,
                    "y": obs_transform.y,
                    "radius": obstacle.radius,
                    "entity_name": obs_entity.name,
                })

        return primitives
