import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from engine.ecs.component import Component
from engine.ecs.world import World, WorldCloneError, WorldSerializationError
from engine.levels.component_registry import create_default_registry
from engine.scenes.scene_manager import SceneManager


class BrokenCloneComponent(Component):
    def __init__(self) -> None:
        self.enabled = True

    def to_dict(self) -> dict[str, object]:
        raise RuntimeError("clone serialize failed")

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "BrokenCloneComponent":
        raise RuntimeError("clone deserialize failed")

    def __deepcopy__(self, memo: dict[int, object]) -> "BrokenCloneComponent":
        raise RuntimeError("clone deepcopy failed")


class BrokenSerializeComponent(Component):
    def __init__(self) -> None:
        self.enabled = True

    def to_dict(self) -> dict[str, object]:
        raise RuntimeError("serialize failed")


class WorldFailFastTests(unittest.TestCase):
    def test_clone_raises_contextual_error_when_component_cannot_be_cloned(self) -> None:
        world = World()
        entity = world.create_entity("Hero")
        entity.add_component(BrokenCloneComponent())

        with self.assertRaisesRegex(WorldCloneError, "Hero.BrokenCloneComponent"):
            world.clone()

    def test_serialize_raises_contextual_error_when_component_cannot_be_serialized(self) -> None:
        world = World()
        entity = world.create_entity("Hero")
        entity.add_component(BrokenSerializeComponent())

        with self.assertRaisesRegex(WorldSerializationError, "Hero.BrokenSerializeComponent"):
            world.serialize()

    def test_prefab_override_serialization_uses_same_fail_fast_path(self) -> None:
        world = World()
        entity = world.create_entity("Hero")
        entity.prefab_instance = {"prefab_path": "prefabs/hero.prefab", "root_name": "Hero"}
        entity.add_component(BrokenSerializeComponent())

        with self.assertRaisesRegex(WorldSerializationError, "Hero.BrokenSerializeComponent"):
            world.serialize()


class SceneManagerFailFastTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scene_manager = SceneManager(create_default_registry())
        self.scene_manager.load_scene(
            {
                "name": "FailFast",
                "entities": [
                    {
                        "name": "Player",
                        "active": True,
                        "tag": "Untagged",
                        "layer": "Default",
                        "components": {
                            "Transform": {
                                "enabled": True,
                                "x": 0.0,
                                "y": 0.0,
                                "rotation": 0.0,
                                "scale_x": 1.0,
                                "scale_y": 1.0,
                            }
                        },
                    }
                ],
                "rules": [],
                "feature_metadata": {},
            }
        )

    def test_enter_play_returns_none_when_world_clone_fails(self) -> None:
        edit_world = self.scene_manager.get_edit_world()
        player = edit_world.get_entity_by_name("Player")
        player.add_component(BrokenCloneComponent())

        with patch("engine.scenes.workspace_lifecycle.log_err") as log_err:
            runtime_world = self.scene_manager.enter_play()

        self.assertIsNone(runtime_world)
        self.assertFalse(self.scene_manager.is_playing)
        log_err.assert_called_once()

    def test_save_scene_to_file_returns_false_when_serialization_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target_path = Path(temp_dir) / "broken_scene.json"
            current_scene = self.scene_manager.current_scene
            with patch.object(current_scene, "to_dict", side_effect=RuntimeError("serialize failed")):
                with patch("engine.scenes.scene_manager.log_err") as log_err:
                    success = self.scene_manager.save_scene_to_file(target_path.as_posix())
            self.assertFalse(target_path.exists())

        self.assertFalse(success)
        log_err.assert_called_once()


if __name__ == "__main__":
    unittest.main()
