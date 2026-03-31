import unittest
from unittest.mock import Mock, patch

import main


class MainBootstrapTests(unittest.TestCase):
    @patch("main.Box2DPhysicsBackend", side_effect=RuntimeError("box2d gui init failed"))
    @patch("builtins.print")
    def test_register_optional_box2d_backend_warns_without_blocking_bootstrap(self, print_mock, _box2d_backend_mock) -> None:
        game = Mock()
        event_bus = Mock()

        result = main._register_optional_box2d_backend(game, gravity=600, event_bus=event_bus)

        self.assertFalse(result)
        game.set_physics_backend.assert_not_called()
        game.set_physics_backend_unavailable.assert_called_once_with("box2d", "box2d gui init failed")
        print_mock.assert_any_call("[WARNING] Box2D backend unavailable: box2d gui init failed")


if __name__ == "__main__":
    unittest.main()
