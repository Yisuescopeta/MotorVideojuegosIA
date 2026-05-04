import unittest

from engine.components.animator import Animator
from engine.resources.sprite_frames_resource import SpriteFramesResource


class SpriteFramesResourceTests(unittest.TestCase):
    def test_create_sprite_frames(self) -> None:
        resource = SpriteFramesResource()
        self.assertEqual(resource.resource_id, "")
        self.assertEqual(resource.resource_name, "New SpriteFrames")
        self.assertEqual(resource.texture_path, "")
        self.assertEqual(resource.fps, 8.0)
        self.assertEqual(resource.animations, {})

    def test_sprite_frames_serialization(self) -> None:
        resource = SpriteFramesResource(
            resource_id="sf_001",
            resource_name="PlayerFrames",
            texture_path="player.png",
            fps=12.0,
        )
        resource.add_animation("idle", [0, 1], fps=6.0)
        resource.add_animation("run", [2, 3, 4, 5], fps=12.0)

        data = resource.to_dict()
        restored = SpriteFramesResource.from_dict(data)

        self.assertEqual(restored.resource_id, "sf_001")
        self.assertEqual(restored.resource_name, "PlayerFrames")
        self.assertEqual(restored.texture_path, "player.png")
        self.assertEqual(restored.fps, 12.0)
        self.assertIn("idle", restored.animations)
        self.assertIn("run", restored.animations)
        self.assertEqual(restored.animations["idle"]["frames"], [0, 1])
        self.assertEqual(restored.animations["idle"]["fps"], 6.0)
        self.assertEqual(restored.animations["run"]["frames"], [2, 3, 4, 5])
        self.assertEqual(restored.animations["run"]["fps"], 12.0)

    def test_add_animation(self) -> None:
        resource = SpriteFramesResource()
        resource.add_animation("jump", [6, 7], fps=10.0)
        self.assertIn("jump", resource.animations)
        self.assertEqual(resource.animations["jump"]["frames"], [6, 7])
        self.assertEqual(resource.animations["jump"]["fps"], 10.0)

    def test_get_animation(self) -> None:
        resource = SpriteFramesResource()
        resource.add_animation("attack", [8, 9, 10], fps=15.0)

        anim = resource.get_animation("attack")
        self.assertIsNotNone(anim)
        self.assertEqual(anim["frames"], [8, 9, 10])  # type: ignore[index]

        missing = resource.get_animation("nonexistent")
        self.assertIsNone(missing)

    def test_animator_sprite_frames_ref(self) -> None:
        animator = Animator(
            sprite_frames_resource_path="res://player_frames.tres",
        )
        self.assertEqual(animator.sprite_frames_resource_path, "res://player_frames.tres")

        data = animator.to_dict()
        self.assertIn("sprite_frames_resource_path", data)
        self.assertEqual(data["sprite_frames_resource_path"], "res://player_frames.tres")

        restored = Animator.from_dict(data)
        self.assertEqual(restored.sprite_frames_resource_path, "res://player_frames.tres")

    def test_animator_default_sprite_frames_ref(self) -> None:
        animator = Animator()
        self.assertEqual(animator.sprite_frames_resource_path, "")

        data = animator.to_dict()
        self.assertNotIn("sprite_frames_resource_path", data)

        restored = Animator.from_dict(data)
        self.assertEqual(restored.sprite_frames_resource_path, "")


if __name__ == "__main__":
    unittest.main()
