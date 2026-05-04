"""
tests/test_animation_player_2d.py - Tests de AnimationPlayer2D y AnimationPlayerSystem.
"""

import json
import os
import tempfile
import unittest

from engine.components.animation_player_2d import AnimationPlayer2D
from engine.components.sprite import Sprite
from engine.components.transform import Transform
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.levels.component_registry import create_default_registry
from engine.resources.animation_resource import AnimationResource, AnimationTrack
from engine.systems.animation_player_system import AnimationPlayerSystem


class AnimationPlayer2DTests(unittest.TestCase):
    def test_create_player(self) -> None:
        player = AnimationPlayer2D()
        self.assertTrue(player.enabled)
        self.assertFalse(player.autoplay)
        self.assertEqual(player.playback_speed, 1.0)
        self.assertEqual(player.animation_resource_path, "")
        self.assertEqual(player.current_animation, "")
        self.assertEqual(player._playback_time, 0.0)
        self.assertFalse(player._is_playing)

    def test_player_serialization(self) -> None:
        player = AnimationPlayer2D(
            autoplay=True,
            playback_speed=2.0,
            animation_resource_path="res://anim/walk.json",
            current_animation="walk_right",
        )
        player.enabled = False
        data = player.to_dict()

        restored = AnimationPlayer2D.from_dict(data)
        self.assertTrue(restored.autoplay)
        self.assertEqual(restored.playback_speed, 2.0)
        self.assertEqual(restored.animation_resource_path, "res://anim/walk.json")
        self.assertEqual(restored.current_animation, "walk_right")
        self.assertFalse(restored.enabled)

    def test_play_stop(self) -> None:
        player = AnimationPlayer2D()
        self.assertFalse(player._is_playing)

        player.play()
        self.assertTrue(player._is_playing)
        self.assertEqual(player._playback_time, 0.0)

        player.stop()
        self.assertFalse(player._is_playing)

    def test_seek(self) -> None:
        player = AnimationPlayer2D()
        player.seek(5.0)
        self.assertEqual(player._playback_time, 5.0)
        player.seek(-1.0)
        self.assertEqual(player._playback_time, 0.0)

    def test_playback_speed(self) -> None:
        player = AnimationPlayer2D(playback_speed=2.0)
        player.play()
        self.assertTrue(player._is_playing)
        self.assertEqual(player.playback_speed, 2.0)

    def test_track_evaluation(self) -> None:
        system = AnimationPlayerSystem()

        track = AnimationTrack(property_path="Transform.x", interpolation="linear")
        track.keyframes.append({"time": 0.0, "value": 0.0})
        track.keyframes.append({"time": 1.0, "value": 100.0})

        self.assertAlmostEqual(system._evaluate_track(track, 0.0), 0.0)
        self.assertAlmostEqual(system._evaluate_track(track, 0.5), 50.0)
        self.assertAlmostEqual(system._evaluate_track(track, 1.0), 100.0)

    def test_apply_transform_position(self) -> None:
        world = World()
        system = AnimationPlayerSystem()
        entity = Entity("TestEntity")
        entity.add_component(Transform(x=0.0, y=0.0))
        world.add_entity(entity)

        transform = entity.get_component(Transform)
        assert transform is not None

        # Aplicar valor directamente a Transform.x
        system._apply_property(entity, "Transform.x", 42.0)
        self.assertEqual(transform.x, 42.0)

        system._apply_property(entity, "Transform.y", -10.0)
        self.assertEqual(transform.y, -10.0)

    def test_registry_creation(self) -> None:
        registry = create_default_registry()
        player = registry.create("AnimationPlayer2D", {"autoplay": True, "playback_speed": 1.5})
        self.assertIsInstance(player, AnimationPlayer2D)
        self.assertTrue(player.autoplay)
        self.assertEqual(player.playback_speed, 1.5)


class AnimationPlayerSystemTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = World()
        self.system = AnimationPlayerSystem()
        self.temp_dir = tempfile.mkdtemp()

    def _create_anim_json(self, resource: AnimationResource) -> str:
        path = os.path.join(self.temp_dir, "test_anim.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(resource.to_dict(), f)
        return path

    def test_system_advances_playback_time(self) -> None:
        resource = AnimationResource(length=2.0, loop=False)
        track = resource.add_track("Transform.x", "linear")
        track.keyframes.append({"time": 0.0, "value": 0.0})
        track.keyframes.append({"time": 2.0, "value": 200.0})
        anim_path = self._create_anim_json(resource)

        entity = Entity("AnimEntity")
        entity.add_component(Transform(x=0.0, y=0.0))
        player = AnimationPlayer2D(animation_resource_path=anim_path)
        entity.add_component(player)
        self.world.add_entity(entity)

        player.play()
        self.system.update(self.world, 1.0)

        transform = entity.get_component(Transform)
        assert transform is not None
        self.assertAlmostEqual(transform.x, 100.0, places=5)
        self.assertAlmostEqual(player._playback_time, 1.0)

    def test_system_loops(self) -> None:
        resource = AnimationResource(length=1.0, loop=True)
        track = resource.add_track("Transform.x", "linear")
        track.keyframes.append({"time": 0.0, "value": 0.0})
        track.keyframes.append({"time": 1.0, "value": 100.0})
        anim_path = self._create_anim_json(resource)

        entity = Entity("LoopEntity")
        entity.add_component(Transform(x=0.0, y=0.0))
        player = AnimationPlayer2D(animation_resource_path=anim_path)
        entity.add_component(player)
        self.world.add_entity(entity)

        player.play()
        self.system.update(self.world, 1.5)

        # 1.5s → loop: t = 0.5 en el segundo ciclo → x ≈ 50
        transform = entity.get_component(Transform)
        assert transform is not None
        self.assertAlmostEqual(transform.x, 50.0, places=5)
        self.assertAlmostEqual(player._playback_time, 0.5, places=5)

    def test_system_stops_at_end_when_no_loop(self) -> None:
        resource = AnimationResource(length=1.0, loop=False)
        track = resource.add_track("Transform.x", "linear")
        track.keyframes.append({"time": 0.0, "value": 0.0})
        track.keyframes.append({"time": 1.0, "value": 100.0})
        anim_path = self._create_anim_json(resource)

        entity = Entity("NoLoopEntity")
        entity.add_component(Transform(x=0.0, y=0.0))
        player = AnimationPlayer2D(animation_resource_path=anim_path)
        entity.add_component(player)
        self.world.add_entity(entity)

        player.play()
        self.system.update(self.world, 1.5)

        # Debe detenerse al final
        self.assertFalse(player._is_playing)
        self.assertAlmostEqual(player._playback_time, 1.0)

    def test_system_respects_playback_speed(self) -> None:
        resource = AnimationResource(length=2.0, loop=False)
        track = resource.add_track("Transform.x", "linear")
        track.keyframes.append({"time": 0.0, "value": 0.0})
        track.keyframes.append({"time": 2.0, "value": 200.0})
        anim_path = self._create_anim_json(resource)

        entity = Entity("SpeedEntity")
        entity.add_component(Transform(x=0.0, y=0.0))
        player = AnimationPlayer2D(animation_resource_path=anim_path, playback_speed=2.0)
        entity.add_component(player)
        self.world.add_entity(entity)

        player.play()
        self.system.update(self.world, 0.5)
        # Con speed=2, en 0.5s reales avanza 1.0s de animación → x = 100
        transform = entity.get_component(Transform)
        assert transform is not None
        self.assertAlmostEqual(transform.x, 100.0, places=5)

    def test_system_skips_disabled(self) -> None:
        resource = AnimationResource(length=1.0, loop=False)
        track = resource.add_track("Transform.x", "linear")
        track.keyframes.append({"time": 0.0, "value": 0.0})
        track.keyframes.append({"time": 1.0, "value": 100.0})
        anim_path = self._create_anim_json(resource)

        entity = Entity("DisabledEntity")
        entity.add_component(Transform(x=0.0, y=0.0))
        player = AnimationPlayer2D(animation_resource_path=anim_path)
        player.enabled = False
        entity.add_component(player)
        self.world.add_entity(entity)

        player.play()
        self.system.update(self.world, 1.0)

        transform = entity.get_component(Transform)
        assert transform is not None
        self.assertEqual(transform.x, 0.0)

    def test_system_step_interpolation(self) -> None:
        resource = AnimationResource(length=1.0, loop=False)
        track = resource.add_track("Transform.x", "step")
        track.keyframes.append({"time": 0.0, "value": 0.0})
        track.keyframes.append({"time": 0.5, "value": 100.0})
        anim_path = self._create_anim_json(resource)

        entity = Entity("StepEntity")
        entity.add_component(Transform(x=0.0, y=0.0))
        player = AnimationPlayer2D(animation_resource_path=anim_path)
        entity.add_component(player)
        self.world.add_entity(entity)

        player.play()
        self.system.update(self.world, 0.3)
        transform = entity.get_component(Transform)
        assert transform is not None
        self.assertEqual(transform.x, 0.0)  # step: se mantiene en valor previo

        self.system.update(self.world, 0.3)
        self.assertEqual(transform.x, 100.0)  # ya cruzó el keyframe

    def test_system_sprite_tint(self) -> None:
        resource = AnimationResource(length=1.0, loop=False)
        track = resource.add_track("Sprite.tint", "linear")
        track.keyframes.append({"time": 0.0, "value": [255, 255, 255, 255]})
        track.keyframes.append({"time": 1.0, "value": [0, 0, 0, 0]})
        anim_path = self._create_anim_json(resource)

        entity = Entity("TintEntity")
        entity.add_component(Sprite(tint=(255, 255, 255, 255)))
        player = AnimationPlayer2D(animation_resource_path=anim_path)
        entity.add_component(player)
        self.world.add_entity(entity)

        player.play()
        self.system.update(self.world, 0.5)

        sprite = entity.get_component(Sprite)
        assert sprite is not None
        # En t=0.5, cada canal debería estar a mitad: ~127
        self.assertAlmostEqual(sprite.tint[0], 127, delta=1)
        self.assertAlmostEqual(sprite.tint[1], 127, delta=1)
        self.assertAlmostEqual(sprite.tint[2], 127, delta=1)
        self.assertAlmostEqual(sprite.tint[3], 127, delta=1)


if __name__ == "__main__":
    unittest.main()
