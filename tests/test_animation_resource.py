import unittest

from engine.resources.animation_resource import AnimationResource, AnimationTrack


class AnimationResourceTests(unittest.TestCase):
    def test_create_animation_resource(self) -> None:
        resource = AnimationResource()
        self.assertEqual(resource.resource_id, "")
        self.assertEqual(resource.resource_name, "New Animation")
        self.assertEqual(resource.length, 1.0)
        self.assertTrue(resource.loop)
        self.assertEqual(resource.tracks, [])

    def test_animation_serialization(self) -> None:
        resource = AnimationResource(
            resource_id="anim_001",
            resource_name="Walk",
            length=0.8,
            loop=True,
        )
        track = resource.add_track("Transform.position", "linear")
        track.keyframes.append({"time": 0.0, "value": [0, 0]})
        track.keyframes.append({"time": 0.5, "value": [100, 0]})
        track.keyframes.append({"time": 0.8, "value": [100, 50]})

        data = resource.to_dict()
        restored = AnimationResource.from_dict(data)

        self.assertEqual(restored.resource_id, "anim_001")
        self.assertEqual(restored.resource_name, "Walk")
        self.assertAlmostEqual(restored.length, 0.8)
        self.assertTrue(restored.loop)
        self.assertEqual(len(restored.tracks), 1)
        self.assertEqual(restored.tracks[0].property_path, "Transform.position")
        self.assertEqual(restored.tracks[0].interpolation, "linear")
        self.assertEqual(len(restored.tracks[0].keyframes), 3)
        self.assertEqual(restored.tracks[0].keyframes[0]["time"], 0.0)
        self.assertEqual(restored.tracks[0].keyframes[0]["value"], [0, 0])

    def test_add_track(self) -> None:
        resource = AnimationResource()
        track = resource.add_track("Sprite.tint", "cubic")
        self.assertIsInstance(track, AnimationTrack)
        self.assertEqual(track.property_path, "Sprite.tint")
        self.assertEqual(track.interpolation, "cubic")
        self.assertEqual(len(resource.tracks), 1)

    def test_keyframes(self) -> None:
        track = AnimationTrack(property_path="Transform.rotation", interpolation="linear")
        track.keyframes.append({"time": 0.0, "value": 0.0})
        track.keyframes.append({"time": 1.0, "value": 6.28})

        data = track.to_dict()
        restored = AnimationTrack.from_dict(data)

        self.assertEqual(len(restored.keyframes), 2)
        self.assertEqual(restored.keyframes[0]["time"], 0.0)
        self.assertEqual(restored.keyframes[0]["value"], 0.0)
        self.assertEqual(restored.keyframes[1]["time"], 1.0)
        self.assertEqual(restored.keyframes[1]["value"], 6.28)

    def test_interpolation_types(self) -> None:
        resource = AnimationResource()
        t1 = resource.add_track("a", "linear")
        t2 = resource.add_track("b", "step")
        t3 = resource.add_track("c", "cubic")

        data = resource.to_dict()
        restored = AnimationResource.from_dict(data)

        self.assertEqual(restored.tracks[0].interpolation, "linear")
        self.assertEqual(restored.tracks[1].interpolation, "step")
        self.assertEqual(restored.tracks[2].interpolation, "cubic")

    def test_animation_track_from_dict_empty(self) -> None:
        track = AnimationTrack.from_dict({})
        self.assertEqual(track.property_path, "")
        self.assertEqual(track.interpolation, "linear")
        self.assertEqual(track.keyframes, [])

    def test_animation_resource_from_dict_empty(self) -> None:
        resource = AnimationResource.from_dict({})
        self.assertEqual(resource.resource_id, "")
        self.assertEqual(resource.resource_name, "New Animation")
        self.assertEqual(resource.length, 1.0)
        self.assertTrue(resource.loop)
        self.assertEqual(resource.tracks, [])

    def test_animation_resource_from_dict_non_dict(self) -> None:
        resource = AnimationResource.from_dict(None)  # type: ignore[arg-type]
        self.assertEqual(resource.resource_name, "New Animation")


if __name__ == "__main__":
    unittest.main()
