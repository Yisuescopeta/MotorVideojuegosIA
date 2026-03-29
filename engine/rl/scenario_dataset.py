from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from engine.debug.state_fingerprint import world_fingerprint
from engine.rl import MotorGymEnv, MotorParallelEnv

SCENARIO_SPEC_VERSION = 1
EPISODE_LOG_VERSION = 1


def load_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: str, payload: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def generate_scenarios(
    template_scene: str,
    *,
    out_dir: str,
    count: int,
    seed: int,
    spec: dict[str, Any] | None = None,
) -> dict[str, Any]:
    template = load_json(template_scene)
    scenario_spec = spec or build_default_scenario_spec(template)
    rng = random.Random(int(seed))
    output_root = Path(out_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    scenarios: list[dict[str, Any]] = []
    for index in range(max(1, int(count))):
        scenario_seed = rng.randrange(0, 2**31)
        scenario_rng = random.Random(scenario_seed)
        payload = json.loads(json.dumps(template))
        _apply_randomizations(payload, scenario_spec, scenario_rng)
        scenario_id = f"scenario_{index:04d}"
        scene_path = output_root / f"{scenario_id}.json"
        scene_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
        scenarios.append(
            {
                "scenario_id": scenario_id,
                "scene_path": scene_path.as_posix(),
                "seed": scenario_seed,
                "entity_count": len(payload.get("entities", [])),
                "name": payload.get("name", ""),
            }
        )
    manifest = {
        "scenario_spec_version": SCENARIO_SPEC_VERSION,
        "template_scene": str(template_scene),
        "seed": int(seed),
        "spec": scenario_spec,
        "scenarios": scenarios,
    }
    write_json((output_root / "manifest.json").as_posix(), manifest)
    return manifest


def build_default_scenario_spec(template: dict[str, Any]) -> dict[str, Any]:
    randomizations: list[dict[str, Any]] = []
    for entity in template.get("entities", []):
        transform = entity.get("components", {}).get("Transform")
        if not isinstance(transform, dict):
            continue
        entity_name = str(entity.get("name", ""))
        entity_tag = str(entity.get("tag", ""))
        if entity_tag in {"Agent", "Goal"} or "InputMap" in entity.get("components", {}):
            base_x = float(transform.get("x", 0.0))
            randomizations.append(
                {
                    "entity": entity_name,
                    "component": "Transform",
                    "property": "x",
                    "min": base_x - 48.0,
                    "max": base_x + 48.0,
                }
            )
    return {"version": SCENARIO_SPEC_VERSION, "randomizations": randomizations}


def _apply_randomizations(payload: dict[str, Any], spec: dict[str, Any], rng: random.Random) -> None:
    rules = list(spec.get("randomizations", []))
    by_name = {str(entity.get("name", "")): entity for entity in payload.get("entities", [])}
    for rule in rules:
        entity = by_name.get(str(rule.get("entity", "")))
        if entity is None:
            continue
        component = entity.get("components", {}).get(str(rule.get("component", "")))
        if not isinstance(component, dict):
            continue
        minimum = float(rule.get("min", 0.0))
        maximum = float(rule.get("max", minimum))
        component[str(rule.get("property", ""))] = rng.uniform(minimum, maximum)


def run_episode_dataset(
    *,
    scene_path: str,
    out_jsonl: str,
    episodes: int,
    max_steps: int,
    seed: int,
    env_kind: str = "auto",
    project_root: str | None = None,
) -> dict[str, Any]:
    output = Path(out_jsonl)
    output.parent.mkdir(parents=True, exist_ok=True)
    completed_episodes = 0
    total_steps = 0
    terminated_count = 0
    truncated_count = 0
    with output.open("w", encoding="utf-8") as handle:
        for episode_index in range(max(1, int(episodes))):
            episode_seed = int(seed) + episode_index
            episode_id = f"episode_{episode_index:04d}"
            env = _make_env(scene_path, max_steps=max_steps, env_kind=env_kind, project_root=project_root)
            obs, infos = env.reset(seed=episode_seed)
            last_event_count = 0
            step_index = 0
            done = False
            while not done:
                actions = env.sample_actions() if hasattr(env, "sample_actions") else env.sample_action()
                step_result = env.step(actions)
                if isinstance(env, MotorParallelEnv):
                    next_obs, rewards, terminations, truncations, step_infos = step_result
                    done = not env.agents
                    reward_payload = rewards
                    terminated_payload = terminations
                    truncated_payload = truncations
                else:
                    next_obs, reward, terminated, truncated, step_info = step_result
                    step_infos = {"agent_0": step_info}
                    reward_payload = {"agent_0": reward}
                    terminated_payload = {"agent_0": terminated}
                    truncated_payload = {"agent_0": truncated}
                    done = bool(terminated or truncated)
                runtime_api = getattr(env, "_api", None)
                runtime_world = runtime_api.game.world if runtime_api is not None and runtime_api.game is not None else None
                events = []
                if runtime_api is not None:
                    recent = runtime_api.get_recent_events(50)
                    events = recent[last_event_count:]
                    last_event_count = len(recent)
                game = runtime_api.game if runtime_api is not None else None
                fingerprint = (
                    world_fingerprint(
                        runtime_world,
                        frame=getattr(game.time, "frame_count", None) if game is not None else None,
                        time=getattr(game.time, "total_time", None) if game is not None else None,
                    )
                    if runtime_world is not None
                    else {}
                )
                handle.write(
                    json.dumps(
                        {
                            "episode_log_version": EPISODE_LOG_VERSION,
                            "episode_id": episode_id,
                            "episode_seed": episode_seed,
                            "scene_path": scene_path,
                            "step": step_index,
                            "actions": actions if isinstance(actions, dict) else {"agent_0": actions},
                            "observations": obs if isinstance(obs, dict) and "self_position" not in obs else {"agent_0": obs},
                            "rewards": reward_payload,
                            "terminations": terminated_payload,
                            "truncations": truncated_payload,
                            "infos": step_infos,
                            "events": events,
                            "fingerprint": fingerprint,
                        },
                        ensure_ascii=True,
                    )
                    + "\n"
                )
                obs = next_obs
                step_index += 1
            completed_episodes += 1
            total_steps += step_index
            terminated_count += int(any(bool(value) for value in terminated_payload.values()))
            truncated_count += int(any(bool(value) for value in truncated_payload.values()))
            env.close()
    return {
        "episode_log_version": EPISODE_LOG_VERSION,
        "scene_path": scene_path,
        "episodes": int(episodes),
        "max_steps": int(max_steps),
        "seed": int(seed),
        "env_kind": env_kind,
        "completed_episodes": completed_episodes,
        "steps": total_steps,
        "terminated": terminated_count,
        "truncated": truncated_count,
    }


def replay_episode(dataset_jsonl: str, episode_id: str) -> dict[str, Any]:
    steps = [
        json.loads(line)
        for line in Path(dataset_jsonl).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    episode_steps = [item for item in steps if item.get("episode_id") == episode_id]
    if not episode_steps:
        raise ValueError(f"Episode '{episode_id}' not found")
    first = episode_steps[0]
    scene_path = str(first["scene_path"])
    env_kind = "parallel" if len(first.get("actions", {})) > 1 else "single"
    env = _make_env(scene_path, max_steps=max(len(episode_steps) + 1, 1), env_kind=env_kind)
    env.reset(seed=int(first["episode_seed"]))
    final_fingerprint = {}
    for item in episode_steps:
        actions = item["actions"]
        env.step(actions if env_kind == "parallel" else int(actions["agent_0"]))
        runtime_api = getattr(env, "_api", None)
        game = runtime_api.game if runtime_api is not None else None
        runtime_world = game.world if game is not None else None
        if runtime_world is not None and game is not None:
            final_fingerprint = world_fingerprint(
                runtime_world,
                frame=getattr(game.time, "frame_count", None),
                time=getattr(game.time, "total_time", None),
            )
    env.close()
    expected = episode_steps[-1].get("fingerprint", {})
    return {
        "episode_id": episode_id,
        "scene_path": scene_path,
        "expected_world_hash": expected.get("world_hash", ""),
        "replayed_world_hash": final_fingerprint.get("world_hash", ""),
        "match": expected.get("world_hash", "") == final_fingerprint.get("world_hash", ""),
    }


def _make_env(scene_path: str, *, max_steps: int, env_kind: str, project_root: str | None = None):
    if env_kind == "parallel":
        return MotorParallelEnv(scene_path, project_root=project_root, max_steps=max_steps)
    if env_kind == "single":
        return MotorGymEnv(scene_path, project_root=project_root, max_steps=max_steps)
    payload = load_json(scene_path)
    agent_count = sum(1 for entity in payload.get("entities", []) if "InputMap" in entity.get("components", {}))
    if agent_count >= 2:
        return MotorParallelEnv(scene_path, project_root=project_root, max_steps=max_steps)
    return MotorGymEnv(scene_path, project_root=project_root, max_steps=max_steps)
