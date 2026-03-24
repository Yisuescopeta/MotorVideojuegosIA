from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from engine.api import EngineAPI
from engine.components.inputmap import InputMap
from engine.components.rigidbody import RigidBody
from engine.components.transform import Transform
from engine.rl.gym_env import ACTION_SPEC_VERSION, OBSERVATION_SPEC_VERSION
from engine.rl.gym_compat import spaces
from engine.rl.pettingzoo_compat import ParallelEnv


class MotorParallelEnv(ParallelEnv):
    metadata = {"name": "motor_parallel_v1", "is_parallelizable": True}

    def __init__(
        self,
        scene_path: str,
        *,
        project_root: str | None = None,
        max_steps: int = 600,
    ) -> None:
        self.scene_path = str(scene_path)
        self.project_root = project_root
        self.max_steps = max(1, int(max_steps))
        self._scene_payload = json.loads(Path(self.scene_path).read_text(encoding="utf-8"))
        self.possible_agents = self._discover_agents()
        if len(self.possible_agents) < 2:
            raise ValueError("MotorParallelEnv requires at least 2 InputMap entities")
        self.agents = list(self.possible_agents)
        self._goal_entity = self._discover_default_goal()
        self._api: EngineAPI | None = None
        self._rng = random.Random()
        self._seed: int | None = None
        self._episode_step = 0
        self._settle_frames = 1
        self._last_distances: dict[str, float] = {}
        self.action_spaces = {agent: spaces.Discrete(6) for agent in self.possible_agents}
        self.observation_spaces = {
            agent: spaces.Dict(
                {
                    "self_position": spaces.Box(low=-100000.0, high=100000.0, shape=(2,), dtype=float),
                    "self_velocity": spaces.Box(low=-100000.0, high=100000.0, shape=(2,), dtype=float),
                    "goal_delta": spaces.Box(low=-100000.0, high=100000.0, shape=(2,), dtype=float),
                    "goal_exists": spaces.Box(low=0.0, high=1.0, shape=(1,), dtype=float),
                    "last_action": spaces.Box(low=-1.0, high=1.0, shape=(4,), dtype=float),
                }
            )
            for agent in self.possible_agents
        }
        self._last_action_states = {
            agent: {"horizontal": 0.0, "vertical": 0.0, "action_1": 0.0, "action_2": 0.0}
            for agent in self.possible_agents
        }

    def reset(self, seed: int | None = None, options: dict[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
        options = dict(options or {})
        self.agents = list(self.possible_agents)
        self._episode_step = 0
        if seed is not None:
            self._seed = int(seed)
        if self._seed is not None:
            self._rng.seed(self._seed)
            for action_space in self.action_spaces.values():
                if hasattr(action_space, "seed"):
                    action_space.seed(self._seed)
        self._settle_frames = max(0, int(options.get("settle_frames", 1)))
        self._api = EngineAPI(project_root=self.project_root)
        self._api.load_level(self.scene_path)
        if self._seed is not None:
            self._api.set_seed(self._seed)
        self._api.play()
        if self._settle_frames > 0:
            self._api.step(frames=self._settle_frames)
        observations = {agent: self._build_observation(agent) for agent in self.agents}
        infos = {agent: self._build_info(agent, 0.0, False, False) for agent in self.agents}
        self._last_distances = {agent: abs(float(observations[agent]["goal_delta"][0])) for agent in self.agents}
        self._last_action_states = {
            agent: {"horizontal": 0.0, "vertical": 0.0, "action_1": 0.0, "action_2": 0.0}
            for agent in self.possible_agents
        }
        return observations, infos

    def step(
        self,
        actions: dict[str, int],
    ) -> tuple[dict[str, Any], dict[str, float], dict[str, bool], dict[str, bool], dict[str, Any]]:
        if self._api is None or self._api.game is None or self._api.game._input_system is None:
            raise RuntimeError("Environment not reset")
        acting_agents = [agent for agent in self.agents if agent in actions]
        for agent in acting_agents:
            state = self._action_to_state(int(actions[agent]))
            self._last_action_states[agent] = state
            self._api.game._input_system.inject_state(agent, state, frames=1)
        self._api.step(frames=1)
        self._episode_step += 1

        observations: dict[str, Any] = {}
        rewards: dict[str, float] = {}
        terminations: dict[str, bool] = {}
        truncations: dict[str, bool] = {}
        infos: dict[str, Any] = {}
        goal_missing = self._goal_runtime_entity() is None and bool(self._goal_entity)
        remaining_agents: list[str] = []
        for agent in list(self.agents):
            observations[agent] = self._build_observation(agent)
            reward, fell_out = self._compute_reward(agent, observations[agent], goal_missing)
            terminated = bool(goal_missing or fell_out)
            truncated = bool(self._episode_step >= self.max_steps and not terminated)
            rewards[agent] = reward
            terminations[agent] = terminated
            truncations[agent] = truncated
            infos[agent] = self._build_info(agent, reward, terminated, truncated)
            if not terminated and not truncated:
                remaining_agents.append(agent)
        self.agents = remaining_agents
        return observations, rewards, terminations, truncations, infos

    def action_space(self, agent: str):
        return self.action_spaces[agent]

    def observation_space(self, agent: str):
        return self.observation_spaces[agent]

    def sample_actions(self) -> dict[str, int]:
        return {agent: self._rng.randrange(int(getattr(self.action_spaces[agent], "n", 6))) for agent in self.agents}

    def close(self) -> None:
        if self._api is not None:
            self._api.shutdown()
        self._api = None
        self.agents = []

    def _discover_agents(self) -> list[str]:
        agents: list[str] = []
        for entity in self._scene_payload.get("entities", []):
            if "InputMap" in entity.get("components", {}):
                agents.append(str(entity.get("name", "")))
        return agents

    def _discover_default_goal(self) -> str:
        for entity in self._scene_payload.get("entities", []):
            if entity.get("tag") == "Goal":
                return str(entity.get("name", ""))
        return ""

    def _require_world(self):
        if self._api is None or self._api.game is None or self._api.game.world is None:
            raise RuntimeError("Runtime world unavailable")
        return self._api.game.world

    def _runtime_entity(self, entity_name: str):
        return self._require_world().get_entity_by_name(entity_name)

    def _goal_runtime_entity(self):
        if not self._goal_entity:
            return None
        return self._runtime_entity(self._goal_entity)

    def _build_observation(self, agent: str) -> dict[str, Any]:
        entity = self._runtime_entity(agent)
        if entity is None:
            return {
                "self_position": [0.0, 0.0],
                "self_velocity": [0.0, 0.0],
                "goal_delta": [0.0, 0.0],
                "goal_exists": [0.0],
                "last_action": [0.0, 0.0, 0.0, 0.0],
            }
        transform = entity.get_component(Transform)
        rigidbody = entity.get_component(RigidBody)
        goal = self._goal_runtime_entity()
        goal_transform = goal.get_component(Transform) if goal is not None else None
        pos_x = float(transform.x if transform is not None else 0.0)
        pos_y = float(transform.y if transform is not None else 0.0)
        goal_x = float(goal_transform.x if goal_transform is not None else pos_x)
        goal_y = float(goal_transform.y if goal_transform is not None else pos_y)
        last_action = self._last_action_states.get(agent, {"horizontal": 0.0, "vertical": 0.0, "action_1": 0.0, "action_2": 0.0})
        return {
            "self_position": [pos_x, pos_y],
            "self_velocity": [
                float(rigidbody.velocity_x if rigidbody is not None else 0.0),
                float(rigidbody.velocity_y if rigidbody is not None else 0.0),
            ],
            "goal_delta": [goal_x - pos_x, goal_y - pos_y],
            "goal_exists": [1.0 if goal is not None else 0.0],
            "last_action": [
                float(last_action["horizontal"]),
                float(last_action["vertical"]),
                float(last_action["action_1"]),
                float(last_action["action_2"]),
            ],
        }

    def _compute_reward(self, agent: str, observation: dict[str, Any], goal_missing: bool) -> tuple[float, bool]:
        distance = abs(float(observation["goal_delta"][0]))
        previous = self._last_distances.get(agent, distance)
        self._last_distances[agent] = distance
        fell_out = float(observation["self_position"][1]) > 900.0
        reward = (previous - distance) * 0.01
        if goal_missing:
            reward += 1.0
        if fell_out:
            reward -= 1.0
        return reward, fell_out

    def _build_info(self, agent: str, reward: float, terminated: bool, truncated: bool) -> dict[str, Any]:
        return {
            "agent": agent,
            "episode_step": self._episode_step,
            "reward": reward,
            "terminated": terminated,
            "truncated": truncated,
            "parallel_api": True,
            "action_spec_version": ACTION_SPEC_VERSION,
            "observation_spec_version": OBSERVATION_SPEC_VERSION,
        }

    def _action_to_state(self, action: int) -> dict[str, float]:
        mapping = {
            0: {"horizontal": 0.0, "vertical": 0.0, "action_1": 0.0, "action_2": 0.0},
            1: {"horizontal": -1.0, "vertical": 0.0, "action_1": 0.0, "action_2": 0.0},
            2: {"horizontal": 1.0, "vertical": 0.0, "action_1": 0.0, "action_2": 0.0},
            3: {"horizontal": 0.0, "vertical": 0.0, "action_1": 1.0, "action_2": 0.0},
            4: {"horizontal": -1.0, "vertical": 0.0, "action_1": 1.0, "action_2": 0.0},
            5: {"horizontal": 1.0, "vertical": 0.0, "action_1": 1.0, "action_2": 0.0},
        }
        if action not in mapping:
            raise ValueError(f"Unsupported action: {action}")
        return dict(mapping[action])
