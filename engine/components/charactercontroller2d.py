from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


class CharacterController2D(Component):
    """Controlador de personaje 2D data-driven con semanticas de slide/collide."""

    VALID_MODES = {"move_and_slide", "move_and_collide"}

    def __init__(
        self,
        move_mode: str = "move_and_slide",
        move_speed: float = 180.0,
        jump_velocity: float = -320.0,
        gravity: float = 600.0,
        max_fall_speed: float = 900.0,
        air_control: float = 0.75,
        floor_snap_distance: float = 2.0,
        use_input_map: bool = True,
        velocity_x: float = 0.0,
        velocity_y: float = 0.0,
        on_floor: bool = False,
        collision_normal_x: float = 0.0,
        collision_normal_y: float = 0.0,
        last_hit_entity: str = "",
        up_direction_x: float = 0.0,
        up_direction_y: float = -1.0,
        floor_max_angle: float = 0.785398,
        wall_min_slide_angle: float = 0.261799,
        on_wall: bool = False,
        on_ceiling: bool = False,
        floor_stop_on_slope: bool = False,
        floor_block_on_wall: bool = True,
        platform_velocity_x: float = 0.0,
        platform_velocity_y: float = 0.0,
        max_slides: int = 4,
    ) -> None:
        self.enabled: bool = True
        self.move_mode: str = str(move_mode or "move_and_slide")
        if self.move_mode not in self.VALID_MODES:
            self.move_mode = "move_and_slide"
        self.move_speed: float = float(move_speed)
        self.jump_velocity: float = float(jump_velocity)
        self.gravity: float = float(gravity)
        self.max_fall_speed: float = float(max_fall_speed)
        self.air_control: float = float(air_control)
        self.floor_snap_distance: float = float(floor_snap_distance)
        self.use_input_map: bool = bool(use_input_map)
        self.velocity_x: float = float(velocity_x)
        self.velocity_y: float = float(velocity_y)
        self.on_floor: bool = bool(on_floor)
        self.collision_normal_x: float = float(collision_normal_x)
        self.collision_normal_y: float = float(collision_normal_y)
        self.last_hit_entity: str = str(last_hit_entity or "")
        self._jump_was_pressed: bool = False
        self.up_direction_x: float = float(up_direction_x)
        self.up_direction_y: float = float(up_direction_y)
        self.floor_max_angle: float = float(floor_max_angle)
        self.wall_min_slide_angle: float = float(wall_min_slide_angle)
        self.on_wall: bool = bool(on_wall)
        self.on_ceiling: bool = bool(on_ceiling)
        self.floor_stop_on_slope: bool = bool(floor_stop_on_slope)
        self.floor_block_on_wall: bool = bool(floor_block_on_wall)
        self.platform_velocity_x: float = float(platform_velocity_x)
        self.platform_velocity_y: float = float(platform_velocity_y)
        self.max_slides: int = int(max_slides)
        self.slide_collisions: list[dict] = []
        self._was_on_floor: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "move_mode": self.move_mode,
            "move_speed": self.move_speed,
            "jump_velocity": self.jump_velocity,
            "gravity": self.gravity,
            "max_fall_speed": self.max_fall_speed,
            "air_control": self.air_control,
            "floor_snap_distance": self.floor_snap_distance,
            "use_input_map": self.use_input_map,
            "velocity_x": self.velocity_x,
            "velocity_y": self.velocity_y,
            "on_floor": self.on_floor,
            "collision_normal_x": self.collision_normal_x,
            "collision_normal_y": self.collision_normal_y,
            "last_hit_entity": self.last_hit_entity,
            "up_direction_x": self.up_direction_x,
            "up_direction_y": self.up_direction_y,
            "floor_max_angle": self.floor_max_angle,
            "wall_min_slide_angle": self.wall_min_slide_angle,
            "on_wall": self.on_wall,
            "on_ceiling": self.on_ceiling,
            "floor_stop_on_slope": self.floor_stop_on_slope,
            "floor_block_on_wall": self.floor_block_on_wall,
            "platform_velocity_x": self.platform_velocity_x,
            "platform_velocity_y": self.platform_velocity_y,
            "max_slides": self.max_slides,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CharacterController2D":
        component = cls(
            move_mode=data.get("move_mode", "move_and_slide"),
            move_speed=data.get("move_speed", 180.0),
            jump_velocity=data.get("jump_velocity", -320.0),
            gravity=data.get("gravity", 600.0),
            max_fall_speed=data.get("max_fall_speed", 900.0),
            air_control=data.get("air_control", 0.75),
            floor_snap_distance=data.get("floor_snap_distance", 2.0),
            use_input_map=data.get("use_input_map", True),
            velocity_x=data.get("velocity_x", 0.0),
            velocity_y=data.get("velocity_y", 0.0),
            on_floor=data.get("on_floor", False),
            collision_normal_x=data.get("collision_normal_x", 0.0),
            collision_normal_y=data.get("collision_normal_y", 0.0),
            last_hit_entity=data.get("last_hit_entity", ""),
            up_direction_x=data.get("up_direction_x", 0.0),
            up_direction_y=data.get("up_direction_y", -1.0),
            floor_max_angle=data.get("floor_max_angle", 0.785398),
            wall_min_slide_angle=data.get("wall_min_slide_angle", 0.261799),
            on_wall=data.get("on_wall", False),
            on_ceiling=data.get("on_ceiling", False),
            floor_stop_on_slope=data.get("floor_stop_on_slope", False),
            floor_block_on_wall=data.get("floor_block_on_wall", True),
            platform_velocity_x=data.get("platform_velocity_x", 0.0),
            platform_velocity_y=data.get("platform_velocity_y", 0.0),
            max_slides=data.get("max_slides", 4),
        )
        component.enabled = data.get("enabled", True)
        return component
