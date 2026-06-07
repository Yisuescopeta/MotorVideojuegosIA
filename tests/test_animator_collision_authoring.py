import unittest

from engine.components.animator import AnimationData, Animator, normalize_collision_frame_payload
from engine.components.collider import Collider
from engine.editor.collider_authoring import (
    apply_payload_to_collider,
    build_collider_payload,
    clear_animator_frame_collider_payload,
    copy_base_collider_to_animator_frame,
    get_effective_animator_collider_payload,
    get_payload_bounds,
    set_animator_frame_collider_payload,
)


class AnimatorCollisionAuthoringTests(unittest.TestCase):
    def test_animation_data_serializes_collision_frames_with_string_keys(self) -> None:
        animation = AnimationData(
            slice_names=["idle_0", "idle_1"],
            collision_frames={
                1: {
                    "shape_type": "box",
                    "width": 18,
                    "height": 24,
                    "offset_x": 3,
                    "offset_y": -2,
                }
            },
        )

        data = animation.to_dict()

        self.assertIn("collision_frames", data)
        self.assertIn("1", data["collision_frames"])
        self.assertEqual(data["collision_frames"]["1"]["width"], 18.0)
        self.assertEqual(data["collision_frames"]["1"]["offset_y"], -2.0)

        restored = AnimationData.from_dict(data)
        override = restored.get_collision_frame(1)

        self.assertIsNotNone(override)
        self.assertEqual(override["height"], 24.0)
        self.assertEqual(override["shape_type"], "box")

    def test_animator_gets_current_collision_frame_override(self) -> None:
        animator = Animator(
            animations={
                "attack": AnimationData(
                    slice_names=["attack_0", "attack_1"],
                    collision_frames={
                        1: {
                            "shape_type": "circle",
                            "radius": 12,
                            "offset_x": 5,
                        }
                    },
                )
            },
            default_state="attack",
        )
        animator.current_state = "attack"
        animator.current_frame = 1

        override = animator.get_collision_frame_override()

        self.assertIsNotNone(override)
        self.assertEqual(override["shape_type"], "circle")
        self.assertEqual(override["radius"], 12.0)
        self.assertEqual(override["offset_x"], 5.0)

    def test_effective_payload_merges_base_collider_and_frame_override(self) -> None:
        base = Collider(width=32, height=48, offset_x=0, offset_y=4)
        animator = Animator(
            animations={
                "run": AnimationData(
                    slice_names=["run_0", "run_1"],
                    collision_frames={
                        1: {
                            "width": 20,
                            "height": 48,
                            "offset_x": 6,
                            "offset_y": 4,
                        }
                    },
                )
            },
            default_state="run",
        )

        effective = get_effective_animator_collider_payload(
            animator,
            base_collider=base,
            state_name="run",
            frame_index=1,
        )

        self.assertEqual(effective["width"], 20.0)
        self.assertEqual(effective["height"], 48.0)
        self.assertEqual(effective["offset_x"], 6.0)
        self.assertEqual(effective["offset_y"], 4.0)

    def test_copy_and_clear_animator_frame_collider_payload(self) -> None:
        animator = Animator(
            animations={"jump": AnimationData(slice_names=["jump_0"])},
            default_state="jump",
        )
        base = Collider(width=18, height=40, offset_y=-6)

        self.assertTrue(copy_base_collider_to_animator_frame(animator, base, "jump", 0))
        copied = animator.get_collision_frame_override("jump", 0)
        self.assertIsNotNone(copied)
        self.assertEqual(copied["width"], 18.0)
        self.assertEqual(copied["offset_y"], -6.0)

        self.assertTrue(clear_animator_frame_collider_payload(animator, "jump", 0))
        self.assertIsNone(animator.get_collision_frame_override("jump", 0))

    def test_set_payload_normalizes_values_and_apply_to_collider(self) -> None:
        animator = Animator(
            animations={"idle": AnimationData(slice_names=["idle_0"])},
            default_state="idle",
        )

        self.assertTrue(
            set_animator_frame_collider_payload(
                animator,
                "idle",
                0,
                {
                    "shape_type": "invalid",
                    "width": "12",
                    "height": "24",
                    "offset_x": "2",
                    "offset_y": "-3",
                },
            )
        )
        payload = animator.get_collision_frame_override("idle", 0)
        self.assertEqual(payload["shape_type"], "box")
        self.assertEqual(payload["width"], 12.0)
        self.assertEqual(payload["offset_y"], -3.0)

        collider = Collider()
        self.assertTrue(apply_payload_to_collider(collider, payload))
        self.assertEqual(collider.width, 12.0)
        self.assertEqual(collider.height, 24.0)
        self.assertEqual(collider.offset_x, 2.0)

    def test_payload_bounds_match_collider_geometry(self) -> None:
        payload = normalize_collision_frame_payload({"shape_type": "box", "width": 20, "height": 10, "offset_x": 5})
        self.assertEqual(get_payload_bounds(payload, 100, 50), (95.0, 45.0, 115.0, 55.0))

    def test_build_collider_payload_accepts_dicts(self) -> None:
        payload = build_collider_payload({"shape_type": "circle", "radius": 8, "offset_y": 4})
        self.assertEqual(payload["shape_type"], "circle")
        self.assertEqual(payload["radius"], 8.0)
        self.assertEqual(payload["offset_y"], 4.0)


if __name__ == "__main__":
    unittest.main()
