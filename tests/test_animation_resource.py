import unittest

from engine.resources.animation_resource import AnimationResource, AnimationTrack, AnimationTrackType


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

    def test_track_type_property_default(self) -> None:
        track = AnimationTrack()
        self.assertEqual(track.track_type, AnimationTrackType.PROPERTY)

    def test_method_track_serialization(self) -> None:
        track = AnimationTrack(
            track_type=AnimationTrackType.METHOD,
            method_name="play_sound",
            keyframes=[
                {"time": 0.5, "args": ["jump"], "kwargs": {"volume": 1.0}},
            ],
        )
        data = track.to_dict()
        restored = AnimationTrack.from_dict(data)
        self.assertEqual(restored.track_type, "method")
        self.assertEqual(restored.method_name, "play_sound")
        self.assertEqual(restored.keyframes[0]["time"], 0.5)
        self.assertEqual(restored.keyframes[0]["args"], ["jump"])
        self.assertEqual(restored.keyframes[0]["kwargs"], {"volume": 1.0})

    def test_event_track_serialization(self) -> None:
        track = AnimationTrack(
            track_type=AnimationTrackType.EVENT,
            event_name="hit",
            keyframes=[{"time": 0.3}],
        )
        data = track.to_dict()
        restored = AnimationTrack.from_dict(data)
        self.assertEqual(restored.track_type, "event")
        self.assertEqual(restored.event_name, "hit")
        self.assertEqual(restored.keyframes[0]["time"], 0.3)

    def test_track_type_roundtrip_all_three(self) -> None:
        resource = AnimationResource(length=2.0, loop=False)
        # property track
        pt = resource.add_track("Transform.x", "linear")
        pt.keyframes.append({"time": 0.0, "value": 0.0})
        pt.keyframes.append({"time": 2.0, "value": 100.0})
        # method track
        mt = AnimationTrack(
            track_type=AnimationTrackType.METHOD,
            method_name="flash",
            keyframes=[{"time": 1.0, "args": [], "kwargs": {}}],
        )
        resource.tracks.append(mt)
        # event track
        et = AnimationTrack(
            track_type=AnimationTrackType.EVENT,
            event_name="finished",
            keyframes=[{"time": 2.0}],
        )
        resource.tracks.append(et)

        data = resource.to_dict()
        restored = AnimationResource.from_dict(data)

        self.assertEqual(len(restored.tracks), 3)
        self.assertEqual(restored.tracks[0].track_type, "property")
        self.assertEqual(restored.tracks[0].property_path, "Transform.x")
        self.assertEqual(restored.tracks[1].track_type, "method")
        self.assertEqual(restored.tracks[1].method_name, "flash")
        self.assertEqual(restored.tracks[2].track_type, "event")
        self.assertEqual(restored.tracks[2].event_name, "finished")


if __name__ == "__main__":
    unittest.main()
