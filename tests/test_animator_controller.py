import json
import tempfile
import unittest
from pathlib import Path

from engine.api import EngineAPI
from engine.components.animator import AnimationData, Animator
from engine.components.animator_controller import AnimatorController
from engine.components.transform import Transform
from engine.ecs.world import World
from engine.events.event_bus import EventBus
from engine.systems.animation_system import AnimationSystem
from engine.systems.animator_controller_system import AnimatorControllerSystem


class AnimatorControllerSystemTests(unittest.TestCase):
    def _make_entity(
        self,
        *,
        animator_states: dict[str, AnimationData],
        controller_payload: dict,
    ):
        world = World()
        entity = world.create_entity("Hero")
        entity.add_component(Transform(x=0.0, y=0.0, rotation=0.0, scale_x=1.0, scale_y=1.0))
        entity.add_component(Animator(animations=animator_states, default_state=next(iter(animator_states.keys()))))
        entity.add_component(AnimatorController.from_dict(controller_payload))
        return world, entity

    def test_controller_transitions_by_bool_float_and_int_parameters(self) -> None:
        world, entity = self._make_entity(
            animator_states={
                "idle": AnimationData(slice_names=["idle_0"], fps=8.0, loop=True),
                "run": AnimationData(slice_names=["run_0"], fps=8.0, loop=True),
                "dash": AnimationData(slice_names=["dash_0"], fps=8.0, loop=True),
            },
            controller_payload={
                "enabled": True,
                "entry_state": "idle_logic",
                "parameters": {
                    "grounded": {"type": "bool", "default": True},
                    "speed_x": {"type": "float", "default": 0.0},
                    "combo": {"type": "int", "default": 0},
                },
                "states": {
                    "idle_logic": {"animation_state": "idle", "enter_events": [], "exit_events": []},
                    "run_logic": {"animation_state": "run", "enter_events": [], "exit_events": []},
                    "dash_logic": {"animation_state": "dash", "enter_events": [], "exit_events": []},
                },
                "transitions": [
                    {
                        "id": "idle_to_run",
                        "from_state": "idle_logic",
                        "to_state": "run_logic",
                        "conditions": [
                            {"parameter": "grounded", "op": "is_true"},
                            {"parameter": "speed_x", "op": "greater", "value": 0.1},
                        ],
                    },
                    {
                        "id": "run_to_dash",
                        "from_state": "run_logic",
                        "to_state": "dash_logic",
                        "conditions": [{"parameter": "combo", "op": "greater_or_equal", "value": 1}],
                    },
                ],
            },
        )
        system = AnimatorControllerSystem(EventBus())
        animator = entity.get_component(Animator)
        controller = entity.get_component(AnimatorController)

        self.assertIsNotNone(animator)
        self.assertIsNotNone(controller)

        system.update(world, 0.1)
        self.assertEqual(controller.active_state, "idle_logic")
        self.assertEqual(animator.current_state, "idle")

        controller.set_parameter("speed_x", 1.0)
        system.update(world, 0.1)
        self.assertEqual(controller.active_state, "run_logic")
        self.assertEqual(animator.current_state, "run")

        controller.set_parameter("combo", 1)
        system.update(world, 0.1)
        self.assertEqual(controller.active_state, "dash_logic")
        self.assertEqual(animator.current_state, "dash")

    def test_controller_consumes_trigger_and_any_state_has_priority(self) -> None:
        world, entity = self._make_entity(
            animator_states={
                "idle": AnimationData(slice_names=["idle_0"], fps=8.0, loop=True),
                "fall": AnimationData(slice_names=["fall_0"], fps=8.0, loop=True),
                "hit": AnimationData(slice_names=["hit_0"], fps=8.0, loop=True),
            },
            controller_payload={
                "enabled": True,
                "entry_state": "idle_logic",
                "parameters": {
                    "danger": {"type": "bool", "default": True},
                    "hit": {"type": "trigger"},
                },
                "states": {
                    "idle_logic": {"animation_state": "idle", "enter_events": [], "exit_events": []},
                    "fall_logic": {"animation_state": "fall", "enter_events": [], "exit_events": []},
                    "hit_logic": {"animation_state": "hit", "enter_events": [], "exit_events": []},
                },
                "transitions": [
                    {
                        "id": "any_hit",
                        "from_any_state": True,
                        "to_state": "hit_logic",
                        "conditions": [{"parameter": "hit", "op": "is_set"}],
                    },
                    {
                        "id": "idle_to_fall",
                        "from_state": "idle_logic",
                        "to_state": "fall_logic",
                        "conditions": [{"parameter": "danger", "op": "is_true"}],
                    },
                ],
            },
        )
        system = AnimatorControllerSystem(EventBus())
        animator = entity.get_component(Animator)
        controller = entity.get_component(AnimatorController)

        self.assertIsNotNone(animator)
        self.assertIsNotNone(controller)

        system.update(world, 0.1)
        controller.set_trigger("hit")
        system.update(world, 0.1)

        self.assertEqual(controller.active_state, "hit_logic")
        self.assertEqual(animator.current_state, "hit")
        self.assertNotIn("hit", controller.pending_triggers)

    def test_controller_respects_exit_time_and_force_restart(self) -> None:
        world, entity = self._make_entity(
            animator_states={
                "attack": AnimationData(slice_names=["attack_0", "attack_1"], fps=8.0, loop=False),
                "idle": AnimationData(slice_names=["idle_0"], fps=8.0, loop=True),
            },
            controller_payload={
                "enabled": True,
                "entry_state": "attack_logic",
                "parameters": {"reset": {"type": "trigger"}},
                "states": {
                    "attack_logic": {"animation_state": "attack", "enter_events": [], "exit_events": []},
                    "idle_logic": {"animation_state": "idle", "enter_events": [], "exit_events": []},
                },
                "transitions": [
                    {
                        "id": "restart_attack",
                        "from_any_state": True,
                        "to_state": "attack_logic",
                        "force_restart": True,
                        "conditions": [{"parameter": "reset", "op": "is_set"}],
                    },
                    {
                        "id": "attack_to_idle",
                        "from_state": "attack_logic",
                        "to_state": "idle_logic",
                        "has_exit_time": True,
                        "exit_time": 1.0,
                        "conditions": [],
                    },
                ],
            },
        )
        system = AnimatorControllerSystem(EventBus())
        animator = entity.get_component(Animator)
        controller = entity.get_component(AnimatorController)

        self.assertIsNotNone(animator)
        self.assertIsNotNone(controller)

        system.update(world, 0.1)
        animator.current_frame = 1
        controller.set_trigger("reset")
        system.update(world, 0.1)
        self.assertEqual(controller.active_state, "attack_logic")
        self.assertEqual(animator.current_state, "attack")
        self.assertEqual(animator.current_frame, 0)

        animator.current_frame = 1
        system.update(world, 0.1)
        self.assertEqual(controller.active_state, "idle_logic")
        self.assertEqual(animator.current_state, "idle")

    def test_animation_system_ignores_on_complete_when_controller_is_enabled(self) -> None:
        world = World()
        entity = world.create_entity("Hero")
        entity.add_component(Transform(x=0.0, y=0.0, rotation=0.0, scale_x=1.0, scale_y=1.0))
        entity.add_component(
            Animator(
                animations={
                    "idle": AnimationData(slice_names=["idle_0"], fps=1.0, loop=False, on_complete="run"),
                    "run": AnimationData(slice_names=["run_0"], fps=1.0, loop=True),
                },
                default_state="idle",
            )
        )
        entity.add_component(
            AnimatorController.from_dict(
                {
                    "enabled": True,
                    "entry_state": "idle_logic",
                    "parameters": {},
                    "states": {"idle_logic": {"animation_state": "idle", "enter_events": [], "exit_events": []}},
                    "transitions": [],
                }
            )
        )
        system = AnimationSystem(EventBus())

        system.update(world, 1.5)

        animator = entity.get_component(Animator)
        self.assertIsNotNone(animator)
        self.assertEqual(animator.current_state, "idle")
        self.assertTrue(animator.is_finished)

    def test_controller_does_not_restart_animator_when_state_does_not_change(self) -> None:
        world, entity = self._make_entity(
            animator_states={
                "idle": AnimationData(slice_names=["idle_0", "idle_1"], fps=8.0, loop=True),
                "run": AnimationData(slice_names=["run_0", "run_1"], fps=8.0, loop=True),
            },
            controller_payload={
                "enabled": True,
                "entry_state": "run_logic",
                "parameters": {"speed_x": {"type": "float", "default": 1.0}},
                "states": {
                    "idle_logic": {"animation_state": "idle", "enter_events": [], "exit_events": []},
                    "run_logic": {"animation_state": "run", "enter_events": [], "exit_events": []},
                },
                "transitions": [
                    {
                        "id": "idle_to_run",
                        "from_state": "idle_logic",
                        "to_state": "run_logic",
                        "conditions": [{"parameter": "speed_x", "op": "greater", "value": 0.1}],
                    }
                ],
            },
        )
        system = AnimatorControllerSystem(EventBus())
        animator = entity.get_component(Animator)
        controller = entity.get_component(AnimatorController)

        self.assertIsNotNone(animator)
        self.assertIsNotNone(controller)

        system.update(world, 0.1)
        animator.current_frame = 1
        animator.elapsed_time = 0.25

        system.update(world, 0.1)

        self.assertEqual(controller.active_state, "run_logic")
        self.assertEqual(animator.current_state, "run")
        self.assertEqual(animator.current_frame, 1)
        self.assertAlmostEqual(animator.elapsed_time, 0.25, places=4)


class AnimatorControllerApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self._temp_dir.name)
        self.project_root = self.root / "project"
        self.project_root.mkdir(parents=True, exist_ok=True)
        self.global_state_dir = self.root / "global_state"
        self.scene_path = self.project_root / "levels" / "animator_controller_scene.json"
        self.scene_path.parent.mkdir(parents=True, exist_ok=True)
        self.scene_path.write_text(
            json.dumps({"name": "Animator Controller Scene", "entities": [], "rules": [], "feature_metadata": {}}, indent=2),
            encoding="utf-8",
        )
        self.api = EngineAPI(
            project_root=self.project_root.as_posix(),
            global_state_dir=self.global_state_dir.as_posix(),
        )
        self.api.load_level(self.scene_path.as_posix())

    def tearDown(self) -> None:
        self.api.shutdown()
        self._temp_dir.cleanup()

    def _create_hero(self) -> None:
        result = self.api.create_entity(
            "Hero",
            {
                "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                "Animator": {
                    "enabled": True,
                    "sprite_sheet": "assets/hero.png",
                    "sprite_sheet_path": "assets/hero.png",
                    "frame_width": 16,
                    "frame_height": 16,
                    "animations": {
                        "idle": {"frames": [0], "slice_names": ["idle_0"], "fps": 8.0, "loop": True},
                        "run": {"frames": [1], "slice_names": ["run_0"], "fps": 8.0, "loop": True},
                        "jump": {"frames": [2], "slice_names": ["jump_0"], "fps": 8.0, "loop": True},
                    },
                    "default_state": "idle",
                    "current_state": "idle",
                    "current_frame": 0,
                    "is_finished": False,
                },
            },
        )
        self.assertTrue(result["success"])

    def _controller_payload(self) -> dict:
        return {
            "enabled": True,
            "entry_state": "idle_logic",
            "parameters": {
                "speed_x": {"type": "float", "default": 0.0},
                "jump": {"type": "trigger"},
            },
            "states": {
                "idle_logic": {"animation_state": "idle", "enter_events": [], "exit_events": []},
                "run_logic": {"animation_state": "run", "enter_events": [], "exit_events": []},
                "jump_logic": {"animation_state": "jump", "enter_events": [], "exit_events": []},
            },
            "transitions": [
                {
                    "id": "any_jump",
                    "from_any_state": True,
                    "to_state": "jump_logic",
                    "conditions": [{"parameter": "jump", "op": "is_set"}],
                },
                {
                    "id": "idle_to_run",
                    "from_state": "idle_logic",
                    "to_state": "run_logic",
                    "conditions": [{"parameter": "speed_x", "op": "greater", "value": 0.1}],
                },
            ],
        }

    def test_authoring_api_roundtrips_animator_controller_payload(self) -> None:
        self._create_hero()

        result = self.api.set_animator_controller("Hero", self._controller_payload())
        self.assertTrue(result["success"])

        payload = self.api.get_animator_controller("Hero")
        info = self.api.get_animator_info("Hero")

        self.assertTrue(payload["exists"])
        self.assertEqual(payload["entry_state"], "idle_logic")
        self.assertIn("run_logic", payload["states"])
        self.assertTrue(info["controller"]["exists"])
        self.assertEqual(info["controller"]["entry_state"], "idle_logic")
        self.assertEqual(info["controller"]["state_count"], 3)
        self.assertEqual(info["controller"]["transition_count"], 2)

    def test_runtime_api_updates_controller_parameters_and_debug_snapshot(self) -> None:
        self._create_hero()
        controller_result = self.api.set_animator_controller("Hero", self._controller_payload())
        self.assertTrue(controller_result["success"])

        self.api.play()

        result = self.api.set_animator_parameter("Hero", "speed_x", 1.0)
        self.assertTrue(result["success"])
        self.api.step(1)

        hero = self.api.get_entity("Hero")
        self.assertEqual(hero["components"]["Animator"]["current_state"], "run")

        trigger_result = self.api.set_animator_trigger("Hero", "jump")
        self.assertTrue(trigger_result["success"])
        self.api.step(1)

        hero = self.api.get_entity("Hero")
        snapshot = self.api.get_runtime_debug_snapshot()
        animator_entry = next(entry for entry in snapshot["animators"] if entry["entity"] == "Hero")

        self.assertEqual(hero["components"]["Animator"]["current_state"], "jump")
        self.assertTrue(animator_entry["controller_enabled"])
        self.assertEqual(animator_entry["controller_state"], "jump_logic")
        self.assertEqual(animator_entry["mapped_animation_state"], "jump")
        self.assertIn("speed_x", animator_entry["parameters"])
        self.assertEqual(animator_entry["last_transition_id"], "any_jump")

    def test_animator_controller_persists_after_save_and_reload(self) -> None:
        self._create_hero()
        controller_result = self.api.set_animator_controller("Hero", self._controller_payload())
        self.assertTrue(controller_result["success"])

        save_path = self.project_root / "levels" / "animator_controller_roundtrip.json"
        save_result = self.api.save_scene(path=save_path.as_posix())
        self.assertTrue(save_result["success"])

        persisted = json.loads(save_path.read_text(encoding="utf-8"))
        saved_entity = next(entry for entry in persisted["entities"] if entry["name"] == "Hero")
        self.assertIn("AnimatorController", saved_entity["components"])
        self.assertEqual(saved_entity["components"]["AnimatorController"]["entry_state"], "idle_logic")

        self.api.load_level(save_path.as_posix())
        payload = self.api.get_animator_controller("Hero")
        self.assertTrue(payload["exists"])
        self.assertEqual(payload["entry_state"], "idle_logic")
        self.assertIn("jump_logic", payload["states"])


if __name__ == "__main__":
    unittest.main()
