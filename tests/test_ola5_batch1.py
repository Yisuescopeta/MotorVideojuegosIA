"""
tests/test_ola5_batch1.py - Tests for AnimatedSprite2D, RayCast2D, CanvasModulate.
"""

import unittest
from unittest.mock import MagicMock, patch

from engine.components.animated_sprite_2d import AnimatedSprite2D
from engine.components.canvas_modulate import CanvasModulate
from engine.components.raycast_2d import RayCast2D
from engine.components.sprite import Sprite
from engine.components.transform import Transform
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.systems.animated_sprite_system import AnimatedSpriteSystem
from engine.systems.raycast_2d_system import RayCast2DSystem


# ============================================================
# AnimatedSprite2D tests
# ============================================================

class AnimatedSprite2DTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = World()
        self.system = AnimatedSpriteSystem()

    def _make_entity(self) -> Entity:
        entity = Entity("TestAnim")
        entity.add_component(Transform(x=0, y=0))
        sprite = Sprite(texture_path="frame_0.png")
        entity.add_component(sprite)
        return entity

    def _make_anim(self, playing: bool = True) -> AnimatedSprite2D:
        anim = AnimatedSprite2D()
        anim.enabled = True
        anim.animation = "walk"
        anim.playing = playing
        anim.speed_scale = 1.0
        anim._sprite_frames = {
            "loop_mode": "loop",
            "animations": {
                "walk": [
                    {"texture": "frame_0.png", "duration": 0.1},
                    {"texture": "frame_1.png", "duration": 0.1},
                    {"texture": "frame_2.png", "duration": 0.1},
                ]
            },
        }
        return anim

    # -------------------------------------------------------
    # 1. AnimatedSprite2D serialization round-trip
    # -------------------------------------------------------
    def test_serialization_round_trip(self) -> None:
        anim = AnimatedSprite2D()
        anim.animation = "idle"
        anim.playing = True
        anim.speed_scale = 2.0
        anim.flip_h = True
        anim.offset_x = 5.0
        anim.offset_y = -3.0

        data = anim.to_dict()
        restored = AnimatedSprite2D.from_dict(data)

        self.assertEqual(restored.animation, "idle")
        self.assertTrue(restored.playing)
        self.assertEqual(restored.speed_scale, 2.0)
        self.assertTrue(restored.flip_h)
        self.assertFalse(restored.flip_v)
        self.assertEqual(restored.offset_x, 5.0)
        self.assertEqual(restored.offset_y, -3.0)

    # -------------------------------------------------------
    # 2. AnimatedSpriteSystem advances frame after elapsed time
    # -------------------------------------------------------
    def test_anim_system_advances_frame_on_time(self) -> None:
        entity = self._make_entity()
        anim = self._make_anim(playing=True)
        self.world.add_entity(entity)
        entity.add_component(anim)

        self.assertEqual(anim._current_frame, 0)
        self.system.update(self.world, 0.15)  # > 0.1s duration
        self.assertEqual(anim._current_frame, 1)

    # -------------------------------------------------------
    # 3. Loop mode wraps around
    # -------------------------------------------------------
    def test_anim_system_loop_wraps(self) -> None:
        entity = self._make_entity()
        anim = self._make_anim(playing=True)
        anim._current_frame = 2  # start at last frame
        self.world.add_entity(entity)
        entity.add_component(anim)

        self.system.update(self.world, 0.15)
        self.assertEqual(anim._current_frame, 0)

    # -------------------------------------------------------
    # 4. 'none' loop mode stops at last frame
    # -------------------------------------------------------
    def test_anim_system_none_stops_at_end(self) -> None:
        entity = self._make_entity()
        anim = self._make_anim(playing=True)
        anim._sprite_frames["loop_mode"] = "none"
        anim._current_frame = 2  # last frame
        self.world.add_entity(entity)
        entity.add_component(anim)

        self.system.update(self.world, 0.15)
        self.assertEqual(anim._current_frame, 2)
        self.assertFalse(anim.playing)

    # -------------------------------------------------------
    # 5. 'pingpong' reverses direction
    # -------------------------------------------------------
    def test_anim_system_pingpong_bounces(self) -> None:
        entity = self._make_entity()
        anim = self._make_anim(playing=True)
        anim._sprite_frames["loop_mode"] = "pingpong"
        anim._current_frame = 2  # last frame
        anim._pingpong_dir = 1
        self.world.add_entity(entity)
        entity.add_component(anim)

        self.system.update(self.world, 0.15)
        self.assertEqual(anim._current_frame, 1)
        self.assertEqual(getattr(anim, "_pingpong_dir", 1), -1)

    # -------------------------------------------------------
    # 6. Playing=False does not advance
    # -------------------------------------------------------
    def test_anim_system_not_playing_does_nothing(self) -> None:
        entity = self._make_entity()
        anim = self._make_anim(playing=False)
        self.world.add_entity(entity)
        entity.add_component(anim)

        self.system.update(self.world, 1.0)
        self.assertEqual(anim._current_frame, 0)

    # -------------------------------------------------------
    # 7. Speed_scale affects advance rate
    # -------------------------------------------------------
    def test_anim_system_speed_scale(self) -> None:
        entity = self._make_entity()
        anim = self._make_anim(playing=True)
        anim.speed_scale = 3.0
        self.world.add_entity(entity)
        entity.add_component(anim)

        self.system.update(self.world, 0.04)  # 0.04 * 3 = 0.12 > 0.1
        self.assertEqual(anim._current_frame, 1)

    # -------------------------------------------------------
    # 8. Applies flip from AnimatedSprite2D to Sprite
    # -------------------------------------------------------
    def test_anim_system_applies_flip_to_sprite(self) -> None:
        entity = self._make_entity()
        anim = self._make_anim(playing=True)
        anim.flip_h = True
        anim.flip_v = True
        self.world.add_entity(entity)
        entity.add_component(anim)

        self.system.update(self.world, 0.15)
        sprite = entity.get_component(Sprite)
        self.assertIsNotNone(sprite)
        self.assertTrue(sprite.flip_x)
        self.assertTrue(sprite.flip_y)


# ============================================================
# RayCast2D tests
# ============================================================

class RayCast2DTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = World()

    # -------------------------------------------------------
    # 9. RayCast2D serialization round-trip
    # -------------------------------------------------------
    def test_serialization_round_trip(self) -> None:
        rc = RayCast2D()
        rc.cast_to_x = 100.0
        rc.cast_to_y = 50.0
        rc.collision_mask = 3
        rc.collide_with_areas = True
        rc.exclude_parent = False

        data = rc.to_dict()
        restored = RayCast2D.from_dict(data)

        self.assertEqual(restored.cast_to_x, 100.0)
        self.assertEqual(restored.cast_to_y, 50.0)
        self.assertEqual(restored.collision_mask, 3)
        self.assertTrue(restored.collide_with_areas)
        self.assertFalse(restored.exclude_parent)

    # -------------------------------------------------------
    # 10. RayCast2DSystem populates collision result on hit
    # -------------------------------------------------------
    def test_system_passes_ray_cast_fn_called(self) -> None:
        def mock_ray(ox, oy, dx, dy, max_dist):
            return [{"entity": "wall", "point": {"x": 10.0, "y": 20.0},
                     "normal": {"x": 0.0, "y": -1.0}}]

        system = RayCast2DSystem(ray_cast_query=mock_ray)
        entity = Entity("TestRay")
        entity.add_component(Transform(x=5, y=5))
        rc = RayCast2D()
        rc.cast_to_x = 10.0
        rc.cast_to_y = 10.0
        entity.add_component(rc)
        self.world.add_entity(entity)

        system.update(self.world, 0.016)

        self.assertTrue(rc.is_colliding)
        self.assertEqual(rc.collision_point_x, 10.0)
        self.assertEqual(rc.collision_point_y, 20.0)
        self.assertEqual(rc.collision_normal_y, -1.0)
        self.assertEqual(rc.collider_entity, "wall")

    # -------------------------------------------------------
    # 11. RayCast2DSystem clears result when no hit
    # -------------------------------------------------------
    def test_system_no_hit_clears_results(self) -> None:
        def mock_ray_empty(ox, oy, dx, dy, max_dist):
            return []

        system = RayCast2DSystem(ray_cast_query=mock_ray_empty)
        entity = Entity("TestRay")
        entity.add_component(Transform(x=0, y=0))
        rc = RayCast2D()
        rc.is_colliding = True
        rc.collision_point_x = 99.0
        entity.add_component(rc)
        self.world.add_entity(entity)

        system.update(self.world, 0.016)

        self.assertFalse(rc.is_colliding)
        self.assertEqual(rc.collision_point_x, 0.0)
        self.assertEqual(rc.collider_entity, "")

    # -------------------------------------------------------
    # 12. RayCast2DSystem skips disabled raycast
    # -------------------------------------------------------
    def test_system_skips_disabled_raycast(self) -> None:
        call_count = [0]

        def mock_ray(ox, oy, dx, dy, max_dist):
            call_count[0] += 1
            return []

        system = RayCast2DSystem(ray_cast_query=mock_ray)
        entity = Entity("TestRay")
        entity.add_component(Transform(x=0, y=0))
        rc = RayCast2D()
        rc.enabled = False
        entity.add_component(rc)
        self.world.add_entity(entity)

        system.update(self.world, 0.016)
        self.assertEqual(call_count[0], 0)


# ============================================================
# CanvasModulate tests
# ============================================================

class CanvasModulateTests(unittest.TestCase):
    # -------------------------------------------------------
    # 13. CanvasModulate serialization round-trip
    # -------------------------------------------------------
    def test_serialization_round_trip(self) -> None:
        cm = CanvasModulate(color=(128, 64, 32, 200))
        data = cm.to_dict()
        restored = CanvasModulate.from_dict(data)

        self.assertEqual(restored.color, (128, 64, 32, 200))
        self.assertTrue(restored.enabled)

    # -------------------------------------------------------
    # 14. Default color is white
    # -------------------------------------------------------
    def test_default_color_is_white(self) -> None:
        cm = CanvasModulate()
        self.assertEqual(cm.color, (255, 255, 255, 255))

    # -------------------------------------------------------
    # 15. Color clamping works
    # -------------------------------------------------------
    def test_color_clamping(self) -> None:
        cm = CanvasModulate(color=(300, -10, 128, 500))
        self.assertEqual(cm.color, (255, 0, 128, 255))

    # -------------------------------------------------------
    # 16. from_dict with missing color defaults to white
    # -------------------------------------------------------
    def test_from_dict_defaults(self) -> None:
        cm = CanvasModulate.from_dict({})
        self.assertEqual(cm.color, (255, 255, 255, 255))
        self.assertTrue(cm.enabled)

    # -------------------------------------------------------
    # 17. Component can be disabled
    # -------------------------------------------------------
    def test_disabled(self) -> None:
        cm = CanvasModulate()
        cm.enabled = False
        self.assertFalse(cm.enabled)
        data = cm.to_dict()
        restored = CanvasModulate.from_dict(data)
        self.assertFalse(restored.enabled)


# ============================================================
# ComponentRegistry integration test
# ============================================================

class ComponentRegistryIntegrationTests(unittest.TestCase):
    def test_all_three_registered(self) -> None:
        from engine.levels.component_registry import create_default_registry

        registry = create_default_registry()
        registered = registry.list_registered()

        self.assertIn("AnimatedSprite2D", registered)
        self.assertIn("RayCast2D", registered)
        self.assertIn("CanvasModulate", registered)

    def test_can_create_from_registry(self) -> None:
        from engine.levels.component_registry import create_default_registry

        registry = create_default_registry()

        anim = registry.create("AnimatedSprite2D", {})
        self.assertIsInstance(anim, AnimatedSprite2D)

        rc = registry.create("RayCast2D", {})
        self.assertIsInstance(rc, RayCast2D)

        cm = registry.create("CanvasModulate", {})
        self.assertIsInstance(cm, CanvasModulate)


if __name__ == "__main__":
    unittest.main()
