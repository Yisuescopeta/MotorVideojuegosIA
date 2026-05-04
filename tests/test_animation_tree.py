"""tests/test_animation_tree.py - Tests for AnimationTree, BlendSpace2D, StateMachine, and enhanced tracks."""

import json
import os
import tempfile
import unittest

from engine.components.animation_tree import AnimationTree
from engine.components.animator import Animator, AnimationData
from engine.components.animation_player_2d import AnimationPlayer2D
from engine.components.sprite import Sprite
from engine.components.transform import Transform
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.levels.component_registry import create_default_registry
from engine.resources.animation_resource import (
    AnimationResource,
    AnimationTrack,
    AnimationTrackType,
)
from engine.resources.animation_tree import (
    AnimationNode,
    AnimationNodeType,
    AnimationTreeResource,
    BlendPoint2D,
)
from engine.systems.animation_player_system import AnimationPlayerSystem
from engine.systems.animation_tree_system import AnimationTreeSystem


class AnimationTreeResourceTests(unittest.TestCase):
    def test_create_resource(self) -> None:
        resource = AnimationTreeResource()
        self.assertEqual(resource.resource_id, "")
        self.assertEqual(resource.root_node_id, "output")
        self.assertEqual(resource.nodes, {})
        self.assertEqual(resource.parameters, {})

    def test_add_node(self) -> None:
        resource = AnimationTreeResource()
        node = AnimationNode(node_id="walk", node_type=AnimationNodeType.ANIMATION, animation="walk_right")
        resource.add_node(node)
        self.assertIn("walk", resource.nodes)
        self.assertEqual(resource.nodes["walk"].animation, "walk_right")

    def test_connect_nodes(self) -> None:
        resource = AnimationTreeResource()
        parent = AnimationNode(node_id="output", node_type=AnimationNodeType.OUTPUT)
        child = AnimationNode(node_id="walk", node_type=AnimationNodeType.ANIMATION, animation="walk_right")
        resource.add_node(parent)
        resource.add_node(child)
        resource.connect_nodes("output", "walk")
        self.assertIn("walk", resource.nodes["output"].children)

    def test_serialization_roundtrip(self) -> None:
        resource = AnimationTreeResource(resource_id="tree_001", root_node_id="output")
        node = AnimationNode(node_id="walk", node_type=AnimationNodeType.ANIMATION, animation="walk_right")
        resource.add_node(node)
        resource.parameters["speed"] = 2.0

        data = resource.to_dict()
        restored = AnimationTreeResource.from_dict(data)
        self.assertEqual(restored.resource_id, "tree_001")
        self.assertEqual(restored.root_node_id, "output")
        self.assertIn("walk", restored.nodes)
        self.assertEqual(restored.nodes["walk"].animation, "walk_right")
        self.assertEqual(restored.parameters["speed"], 2.0)

    def test_from_dict_none(self) -> None:
        resource = AnimationTreeResource.from_dict(None)
        self.assertEqual(resource.resource_id, "")


class BlendPoint2DTests(unittest.TestCase):
    def test_create(self) -> None:
        bp = BlendPoint2D(x=0.5, y=-0.3, animation="walk")
        self.assertEqual(bp.x, 0.5)
        self.assertEqual(bp.y, -0.3)
        self.assertEqual(bp.animation, "walk")

    def test_serialization(self) -> None:
        bp = BlendPoint2D(x=1.0, y=0.0, animation="run")
        data = bp.to_dict()
        restored = BlendPoint2D.from_dict(data)
        self.assertEqual(restored.x, 1.0)
        self.assertEqual(restored.y, 0.0)
        self.assertEqual(restored.animation, "run")

    def test_from_dict_none(self) -> None:
        bp = BlendPoint2D.from_dict(None)
        self.assertEqual(bp.x, 0.0)


class AnimationNodeTests(unittest.TestCase):
    def test_blend_space_2d_serialization(self) -> None:
        node = AnimationNode(
            node_id="bs2d",
            node_type=AnimationNodeType.BLEND_SPACE_2D,
            blend_space_name="move",
            blend_points=[
                BlendPoint2D(x=-1, y=0, animation="walk_left"),
                BlendPoint2D(x=1, y=0, animation="walk_right"),
                BlendPoint2D(x=0, y=1, animation="walk_up"),
                BlendPoint2D(x=0, y=-1, animation="walk_down"),
            ],
            children=["walk_left", "walk_right", "walk_up", "walk_down"],
        )
        data = node.to_dict()
        restored = AnimationNode.from_dict(data)
        self.assertEqual(restored.node_type, AnimationNodeType.BLEND_SPACE_2D)
        self.assertEqual(len(restored.blend_points), 4)
        self.assertEqual(restored.blend_points[0].animation, "walk_left")
        self.assertEqual(restored.blend_points[1].animation, "walk_right")

    def test_state_machine_serialization(self) -> None:
        node = AnimationNode(
            node_id="sm",
            node_type=AnimationNodeType.STATE_MACHINE,
            entry_state="idle",
            states={"idle": {}, "walk": {}},
            children=["idle", "walk"],
        )
        data = node.to_dict()
        restored = AnimationNode.from_dict(data)
        self.assertEqual(restored.entry_state, "idle")
        self.assertEqual(len(restored.states), 2)

    def test_from_dict_none(self) -> None:
        node = AnimationNode.from_dict(None)
        self.assertEqual(node.node_type, AnimationNodeType.ANIMATION)


class AnimationTreeComponentTests(unittest.TestCase):
    def test_create(self) -> None:
        tree = AnimationTree()
        self.assertTrue(tree.enabled)
        self.assertTrue(tree.active)
        self.assertEqual(tree.speed_scale, 1.0)
        self.assertIsNone(tree.tree_root)

    def test_serialization(self) -> None:
        tree = AnimationTree(animation_tree_path="res://tree.json", active=False, speed_scale=2.0)
        tree.set_parameter("blend_x", 0.5)
        data = tree.to_dict()
        restored = AnimationTree.from_dict(data)
        self.assertEqual(restored.animation_tree_path, "res://tree.json")
        self.assertFalse(restored.active)
        self.assertEqual(restored.speed_scale, 2.0)
        self.assertEqual(restored.parameters["blend_x"], 0.5)

    def test_parameters(self) -> None:
        tree = AnimationTree()
        tree.set_parameter("speed", 2.0)
        self.assertEqual(tree.get_parameter("speed"), 2.0)
        self.assertIsNone(tree.get_parameter("nonexistent"))


class AnimationTreeSystemTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = World()
        self.system = AnimationTreeSystem()

    def _create_entity_with_tree(self, tree_resource: AnimationTreeResource) -> tuple[Entity, AnimationTree, Animator]:
        entity = Entity("TreeEntity")
        tree = AnimationTree(active=True, speed_scale=1.0)
        tree.tree_root = tree_resource
        animator = Animator(
            animations={
                "idle": AnimationData(frames=[0], fps=8.0),
                "walk_right": AnimationData(frames=[1, 2, 3], fps=8.0),
                "walk_left": AnimationData(frames=[4, 5, 6], fps=8.0),
                "walk_up": AnimationData(frames=[7, 8], fps=8.0),
                "walk_down": AnimationData(frames=[9, 10], fps=8.0),
            },
            default_state="idle",
        )
        entity.add_component(tree)
        entity.add_component(animator)
        self.world.add_entity(entity)
        return entity, tree, animator

    def test_simple_animation_node(self) -> None:
        """Single animation node → sets animator to that animation."""
        resource = AnimationTreeResource(root_node_id="output")
        node = AnimationNode(node_id="output", node_type=AnimationNodeType.ANIMATION, animation="walk_right")
        resource.add_node(node)

        entity, tree, animator = self._create_entity_with_tree(resource)
        self.assertEqual(animator.current_state, "idle")

        self.system.update(self.world, 0.1)
        self.assertEqual(animator.current_state, "walk_right")

    def test_blend_space_2d_nearest(self) -> None:
        """BlendSpace2D with 4 points picks nearest based on parameters."""
        resource = AnimationTreeResource(root_node_id="bs2d")

        up = AnimationNode(node_id="up", node_type=AnimationNodeType.ANIMATION, animation="walk_up")
        down = AnimationNode(node_id="down", node_type=AnimationNodeType.ANIMATION, animation="walk_down")
        left = AnimationNode(node_id="left", node_type=AnimationNodeType.ANIMATION, animation="walk_left")
        right = AnimationNode(node_id="right", node_type=AnimationNodeType.ANIMATION, animation="walk_right")
        for n in [up, down, left, right]:
            resource.add_node(n)

        bs2d = AnimationNode(
            node_id="bs2d",
            node_type=AnimationNodeType.BLEND_SPACE_2D,
            blend_space_name="move",
            blend_points=[
                BlendPoint2D(x=0, y=1, animation="walk_up"),
                BlendPoint2D(x=0, y=-1, animation="walk_down"),
                BlendPoint2D(x=-1, y=0, animation="walk_left"),
                BlendPoint2D(x=1, y=0, animation="walk_right"),
            ],
            children=["up", "down", "left", "right"],
        )
        resource.add_node(bs2d)

        entity, tree, animator = self._create_entity_with_tree(resource)
        # Set blend position to right side
        tree.set_parameter("move_x", 0.9)
        tree.set_parameter("move_y", 0.1)

        self.system.update(self.world, 0.1)
        self.assertEqual(animator.current_state, "walk_right")

        # Change to up
        tree.set_parameter("move_x", 0.1)
        tree.set_parameter("move_y", 0.9)
        self.system.update(self.world, 0.1)
        self.assertEqual(animator.current_state, "walk_up")

    def test_state_machine(self) -> None:
        """State machine picks active child based on parameter."""
        resource = AnimationTreeResource(root_node_id="sm")

        idle = AnimationNode(node_id="idle", node_type=AnimationNodeType.ANIMATION, animation="idle")
        walk = AnimationNode(node_id="walk", node_type=AnimationNodeType.ANIMATION, animation="walk_right")
        resource.add_node(idle)
        resource.add_node(walk)

        sm = AnimationNode(
            node_id="sm",
            node_type=AnimationNodeType.STATE_MACHINE,
            entry_state="idle",
            children=["idle", "walk"],
        )
        resource.add_node(sm)

        entity, tree, animator = self._create_entity_with_tree(resource)
        # Default → idle
        self.system.update(self.world, 0.1)
        self.assertEqual(animator.current_state, "idle")

        # Switch to walk
        tree.set_parameter("sm_state", "walk")
        self.system.update(self.world, 0.1)
        self.assertEqual(animator.current_state, "walk_right")

    def test_inactive_tree_skipped(self) -> None:
        """Tree with active=False is not processed."""
        resource = AnimationTreeResource(root_node_id="output")
        node = AnimationNode(node_id="output", node_type=AnimationNodeType.ANIMATION, animation="walk_right")
        resource.add_node(node)

        entity, tree, animator = self._create_entity_with_tree(resource)
        tree.active = False

        self.system.update(self.world, 0.1)
        self.assertEqual(animator.current_state, "idle")  # unchanged

    def test_tree_no_animator_skipped(self) -> None:
        """Tree without Animator component is skipped."""
        entity = Entity("NoAnim")
        tree = AnimationTree(active=True)
        entity.add_component(tree)
        self.world.add_entity(entity)
        # Should not crash
        self.system.update(self.world, 0.1)

    def test_registry_creation(self) -> None:
        registry = create_default_registry()
        tree = registry.create("AnimationTree", {"active": True, "speed_scale": 1.5})
        self.assertIsInstance(tree, AnimationTree)
        self.assertTrue(tree.active)
        self.assertEqual(tree.speed_scale, 1.5)


class EnhancedAnimationPlayerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = World()
        self.system = AnimationPlayerSystem()
        self.temp_dir = tempfile.mkdtemp()

    def _create_anim_json(self, resource: AnimationResource) -> str:
        path = os.path.join(self.temp_dir, "test_anim.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(resource.to_dict(), f)
        return path

    def test_audio_track_emits(self) -> None:
        """Audio track emits play_audio event."""
        events: list[dict] = []

        class FakeEventBus:
            def emit(self, name: str, data: dict) -> None:
                events.append({"name": name, "data": data})

        self.system._event_bus = FakeEventBus()

        entity = Entity("AudioEntity")
        entity.add_component(Transform(x=0.0, y=0.0))
        player = AnimationPlayer2D()
        entity.add_component(player)
        self.world.add_entity(entity)

        resource = AnimationResource(length=1.0, loop=False)
        at = AnimationTrack(
            track_type=AnimationTrackType.AUDIO,
            audio_stream="sfx/jump.wav",
            volume=0.8,
            keyframes=[{"time": 0.5}],
        )
        resource.tracks.append(at)

        player._resource_cache = resource
        player.play()
        self.system.update(self.world, 0.5)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["name"], "play_audio")
        self.assertEqual(events[0]["data"]["audio_stream"], "sfx/jump.wav")
        self.assertEqual(events[0]["data"]["volume"], 0.8)

    def test_audio_track_from_keyframe_data(self) -> None:
        """Audio track with stream/volume in keyframe dict."""
        events: list[dict] = []

        class FakeEventBus:
            def emit(self, name: str, data: dict) -> None:
                events.append({"name": name, "data": data})

        self.system._event_bus = FakeEventBus()

        entity = Entity("AudioKfEntity")
        entity.add_component(Transform(x=0.0, y=0.0))
        player = AnimationPlayer2D()
        entity.add_component(player)
        self.world.add_entity(entity)

        resource = AnimationResource(length=1.0, loop=False)
        at = AnimationTrack(
            track_type=AnimationTrackType.AUDIO,
            keyframes=[{"time": 0.3, "audio_stream": "sfx/hit.wav", "volume": 0.5}],
        )
        resource.tracks.append(at)

        player._resource_cache = resource
        player.play()
        self.system.update(self.world, 0.3)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["data"]["audio_stream"], "sfx/hit.wav")
        self.assertEqual(events[0]["data"]["volume"], 0.5)

    def test_animation_track_emits(self) -> None:
        """Animation track emits play_sub_animation event."""
        events: list[dict] = []

        class FakeEventBus:
            def emit(self, name: str, data: dict) -> None:
                events.append({"name": name, "data": data})

        self.system._event_bus = FakeEventBus()

        entity = Entity("SubAnimEntity")
        entity.add_component(Transform(x=0.0, y=0.0))
        player = AnimationPlayer2D()
        entity.add_component(player)
        self.world.add_entity(entity)

        resource = AnimationResource(length=1.0, loop=False)
        at = AnimationTrack(
            track_type=AnimationTrackType.ANIMATION,
            keyframes=[{"time": 0.8, "animation": "explode", "target": "vfx_entity"}],
        )
        resource.tracks.append(at)

        player._resource_cache = resource
        player.play()
        self.system.update(self.world, 0.8)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["name"], "play_sub_animation")
        self.assertEqual(events[0]["data"]["animation"], "explode")
        self.assertEqual(events[0]["data"]["target"], "vfx_entity")

    def test_animation_player_serialization_with_new_fields(self) -> None:
        """Roundtrip with method_tracks, audio_tracks, animation_tracks."""
        player = AnimationPlayer2D(auto_capture=False, capture_on_play=True)
        player.add_method_track({"time": 0.5, "method": "activate", "args": []})
        player.add_audio_track({"time": 1.0, "audio_stream": "sfx/boom.wav", "volume": 1.0})
        player.add_animation_track({"time": 0.0, "animation": "idle", "target": "child"})

        data = player.to_dict()
        restored = AnimationPlayer2D.from_dict(data)
        self.assertFalse(restored.auto_capture)
        self.assertTrue(restored.capture_on_play)
        self.assertEqual(len(restored.method_tracks), 1)
        self.assertEqual(restored.method_tracks[0]["method"], "activate")
        self.assertEqual(len(restored.audio_tracks), 1)
        self.assertEqual(restored.audio_tracks[0]["audio_stream"], "sfx/boom.wav")
        self.assertEqual(len(restored.animation_tracks), 1)
        self.assertEqual(restored.animation_tracks[0]["animation"], "idle")

    def test_animation_resource_loop_mode(self) -> None:
        """loop_mode and step are serialized."""
        resource = AnimationResource(loop_mode="pingpong", step=0.05)
        data = resource.to_dict()
        restored = AnimationResource.from_dict(data)
        self.assertEqual(restored.loop_mode, "pingpong")
        self.assertEqual(restored.step, 0.05)

    def test_animation_track_new_types_serialization(self) -> None:
        """Audio, Animation, Bezier, Discrete track types roundtrip."""
        resource = AnimationResource()
        audio = AnimationTrack(track_type="audio", audio_stream="sfx/click.wav", volume=1.0)
        anim = AnimationTrack(track_type="animation", target_animation="idle", target_entity="child")
        bezier = AnimationTrack(track_type="bezier", property_path="Transform.x", interpolation="bezier")
        discrete = AnimationTrack(track_type="discrete", property_path="Transform.y", interpolation="step")
        for t in [audio, anim, bezier, discrete]:
            resource.tracks.append(t)

        data = resource.to_dict()
        restored = AnimationResource.from_dict(data)
        self.assertEqual(len(restored.tracks), 4)
        self.assertEqual(restored.tracks[0].track_type, "audio")
        self.assertEqual(restored.tracks[0].audio_stream, "sfx/click.wav")
        self.assertEqual(restored.tracks[1].track_type, "animation")
        self.assertEqual(restored.tracks[1].target_animation, "idle")
        self.assertEqual(restored.tracks[2].track_type, "bezier")
        self.assertEqual(restored.tracks[3].track_type, "discrete")


if __name__ == "__main__":
    unittest.main()
