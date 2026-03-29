from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from engine.api import EngineAPI
from engine.components.charactercontroller2d import CharacterController2D
from engine.components.inputmap import InputMap
from engine.components.rigidbody import RigidBody
from engine.components.transform import Transform
from engine.rl.gym_compat import GymEnvBase, spaces


ACTION_SPEC_VERSION = 1
OBSERVATION_SPEC_VERSION = 1


@dataclass
class SingleAgentConfig:
    agent_entity: str
    goal_entity: str = ""
    reward_progress_scale: float = 0.01
    reward_goal: float = 1.0
    reward_fall: float = -1.0
    fall_y_threshold: float = 900.0


class MotorGymEnv(GymEnvBase):
    """
    Gymnasium-style wrapper sobre el runtime headless existente.
    """

    metadata = {"render_modes": []}

    def __init__(
        self,
        scene_path: str,
        *,
        project_root: str | None = None,
        agent_entity: str = "",
        goal_entity: str = "",
        max_steps: int = 600,
        frame_skip: int = 1,
    ) -> None:
        self.scene_path = str(scene_path)
        self.project_root = project_root
        self.max_steps = max(1, int(max_steps))
        self.frame_skip = max(1, int(frame_skip))
        self.action_space = spaces.Discrete(6)
        self.observation_space = spaces.Dict(
            {
                "self_position": spaces.Box(low=-100000.0, high=100000.0, shape=(2,), dtype=float),
                "self_velocity": spaces.Box(low=-100000.0, high=100000.0, shape=(2,), dtype=float),
                "goal_delta": spaces.Box(low=-100000.0, high=100000.0, shape=(2,), dtype=float),
                "on_ground": spaces.Box(low=0.0, high=1.0, shape=(1,), dtype=float),
                "goal_exists": spaces.Box(low=0.0, high=1.0, shape=(1,), dtype=float),
                "last_action": spaces.Box(low=-1.0, high=1.0, shape=(4,), dtype=float),
            }
        )
        self._api: EngineAPI | None = None
        self._scene_payload = json.loads(Path(self.scene_path).read_text(encoding="utf-8"))
        self._initial_agent_entity = agent_entity or self._discover_default_agent()
        self._initial_goal_entity = goal_entity or self._discover_default_goal()
        self._config = SingleAgentConfig(agent_entity=self._initial_agent_entity, goal_entity=self._initial_goal_entity)
        self._rng = random.Random()
        self._seed: int | None = None
        self._episode_step = 0
        self._episode_index = 0
        self._settle_frames = 1
        self._last_progress_x = 0.0
        self._last_action_state = {"horizontal": 0.0, "vertical": 0.0, "action_1": 0.0, "action_2": 0.0}

    @property
    def action_spec(self) -> dict[str, Any]:
        return {
            "version": ACTION_SPEC_VERSION,
            "mode": "discrete_6",
            "future_multiagent_ready": True,
            "actions": {
                "0": {"horizontal": 0.0, "vertical": 0.0, "action_1": 0.0, "action_2": 0.0, "label": "idle"},
                "1": {"horizontal": -1.0, "vertical": 0.0, "action_1": 0.0, "action_2": 0.0, "label": "left"},
                "2": {"horizontal": 1.0, "vertical": 0.0, "action_1": 0.0, "action_2": 0.0, "label": "right"},
                "3": {"horizontal": 0.0, "vertical": 0.0, "action_1": 1.0, "action_2": 0.0, "label": "jump"},
                "4": {"horizontal": -1.0, "vertical": 0.0, "action_1": 1.0, "action_2": 0.0, "label": "left_jump"},
                "5": {"horizontal": 1.0, "vertical": 0.0, "action_1": 1.0, "action_2": 0.0, "label": "right_jump"},
            },
        }

    @property
    def observation_spec(self) -> dict[str, Any]:
        return {
            "version": OBSERVATION_SPEC_VERSION,
            "future_multiagent_ready": True,
            "fields": {
                "self_position": {"shape": [2], "dtype": "float"},
                "self_velocity": {"shape": [2], "dtype": "float"},
                "goal_delta": {"shape": [2], "dtype": "float"},
                "on_ground": {"shape": [1], "dtype": "float"},
                "goal_exists": {"shape": [1], "dtype": "float"},
                "last_action": {"shape": [4], "dtype": "float"},
            },
        }

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
        options = dict(options or {})
        if seed is not None:
            self._seed = int(seed)
        if self._seed is not None:
            self._rng.seed(self._seed)
            if hasattr(self.action_space, "seed"):
                self.action_space.seed(self._seed)
        self._episode_step = 0
        self._episode_index += 1
        self._last_action_state = {"horizontal": 0.0, "vertical": 0.0, "action_1": 0.0, "action_2": 0.0}

        self._config = SingleAgentConfig(
            agent_entity=str(options.get("agent_entity", self._initial_agent_entity)),
            goal_entity=str(options.get("goal_entity", self._initial_goal_entity)),
            reward_progress_scale=float(options.get("reward_progress_scale", 0.01)),
            reward_goal=float(options.get("reward_goal", 1.0)),
            reward_fall=float(options.get("reward_fall", -1.0)),
            fall_y_threshold=float(options.get("fall_y_threshold", 900.0)),
        )
        self._settle_frames = max(0, int(options.get("settle_frames", 1)))
        self._api = EngineAPI(project_root=self.project_root)
        self._api.load_level(self.scene_path)
        if self._seed is not None:
            self._api.set_seed(self._seed)
        self._api.play()
        if self._settle_frames > 0:
            self._api.step(frames=self._settle_frames)

        agent_entity = self._require_agent_entity()
        transform = agent_entity.get_component(Transform)
        self._last_progress_x = float(transform.x if transform is not None else 0.0)
        observation = self._build_observation()
        info = self._build_info(reward=0.0, terminated=False, truncated=False)
        return observation, info

    def step(self, action: int) -> tuple[dict[str, Any], float, bool, bool, dict[str, Any]]:
        if self._api is None:
            raise RuntimeError("Environment not reset")
        action_index = int(action)
        self._last_action_state = self._action_to_state(action_index)
        injection = self._api.inject_input_state(self._config.agent_entity, self._last_action_state, frames=self.frame_skip)
        if not injection["success"]:
            raise RuntimeError(injection["message"] or "Input injection failed")
        self._api.step(frames=self.frame_skip)
        self._episode_step += 1

        observation = self._build_observation()
        reward, reward_details = self._compute_reward(observation)
        terminated = bool(reward_details["goal_reached"] or reward_details["fell_out"])
        truncated = self._episode_step >= self.max_steps and not terminated
        info = self._build_info(reward=reward, terminated=terminated, truncated=truncated)
        info["reward_breakdown"] = reward_details
        return observation, reward, terminated, truncated, info

    def sample_action(self) -> int:
        return self._rng.randrange(int(getattr(self.action_space, "n", 6)))

    def close(self) -> None:
        if self._api is not None:
            self._api.shutdown()
        self._api = None

    def _discover_default_agent(self) -> str:
        for entity in self._scene_payload.get("entities", []):
            if "InputMap" in entity.get("components", {}):
                return str(entity.get("name", ""))
        raise ValueError("No InputMap entity found for RL wrapper")

    def _discover_default_goal(self) -> str:
        for entity in self._scene_payload.get("entities", []):
            if entity.get("tag") == "Goal":
                return str(entity.get("name", ""))
        return ""

    def _require_agent_entity(self):
        world = self._require_world()
        entity = world.get_entity_by_name(self._config.agent_entity)
        if entity is None:
            raise RuntimeError(f"Agent entity '{self._config.agent_entity}' not found")
        return entity

    def _goal_entity(self):
        if not self._config.goal_entity:
            return None
        return self._require_world().get_entity_by_name(self._config.goal_entity)

    def _require_world(self):
        if self._api is None or self._api.game is None or self._api.game.world is None:
            raise RuntimeError("Runtime world unavailable")
        return self._api.game.world

    def _build_observation(self) -> dict[str, Any]:
        entity = self._require_agent_entity()
        transform = entity.get_component(Transform)
        rigidbody = entity.get_component(RigidBody)
        controller = entity.get_component(CharacterController2D)
        goal_entity = self._goal_entity()
        goal_transform = goal_entity.get_component(Transform) if goal_entity is not None else None

        position_x = float(transform.x if transform is not None else 0.0)
        position_y = float(transform.y if transform is not None else 0.0)
        velocity_x = float(rigidbody.velocity_x if rigidbody is not None else getattr(controller, "velocity_x", 0.0))
        velocity_y = float(rigidbody.velocity_y if rigidbody is not None else getattr(controller, "velocity_y", 0.0))
        on_ground = bool(rigidbody.is_grounded if rigidbody is not None else getattr(controller, "on_floor", False))
        goal_x = float(goal_transform.x if goal_transform is not None else position_x)
        goal_y = float(goal_transform.y if goal_transform is not None else position_y)

        return {
            "self_position": [position_x, position_y],
            "self_velocity": [velocity_x, velocity_y],
            "goal_delta": [goal_x - position_x, goal_y - position_y],
            "on_ground": [1.0 if on_ground else 0.0],
            "goal_exists": [1.0 if goal_entity is not None else 0.0],
            "last_action": [
                float(self._last_action_state["horizontal"]),
                float(self._last_action_state["vertical"]),
                float(self._last_action_state["action_1"]),
                float(self._last_action_state["action_2"]),
            ],
        }

    def _compute_reward(self, observation: dict[str, Any]) -> tuple[float, dict[str, Any]]:
        position_x = float(observation["self_position"][0])
        position_y = float(observation["self_position"][1])
        progress_delta = position_x - self._last_progress_x
        self._last_progress_x = position_x
        goal_reached = observation["goal_exists"][0] < 0.5 and bool(self._config.goal_entity)
        fell_out = position_y > self._config.fall_y_threshold
        reward = progress_delta * self._config.reward_progress_scale
        if goal_reached:
            reward += self._config.reward_goal
        if fell_out:
            reward += self._config.reward_fall
        return reward, {
            "progress_delta_x": progress_delta,
            "goal_reached": goal_reached,
            "fell_out": fell_out,
        }

    def _build_info(self, *, reward: float, terminated: bool, truncated: bool) -> dict[str, Any]:
        return {
            "episode_index": self._episode_index,
            "episode_step": self._episode_step,
            "agent_entity": self._config.agent_entity,
            "goal_entity": self._config.goal_entity,
            "reward": reward,
            "terminated": terminated,
            "truncated": truncated,
            "settle_frames": self._settle_frames,
            "action_spec_version": ACTION_SPEC_VERSION,
            "observation_spec_version": OBSERVATION_SPEC_VERSION,
        }

    def _action_to_state(self, action: int) -> dict[str, float]:
        mapping = self.action_spec["actions"].get(str(int(action)))
        if mapping is None:
            raise ValueError(f"Unsupported action: {action}")
        return {
            "horizontal": float(mapping["horizontal"]),
            "vertical": float(mapping["vertical"]),
            "action_1": float(mapping["action_1"]),
            "action_2": float(mapping["action_2"]),
        }
