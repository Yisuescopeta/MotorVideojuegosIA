from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from engine.components.renderorder2d import RenderOrder2D
from engine.components.sprite import Sprite
from engine.components.transform import Transform
from engine.core.game import Game
from engine.ecs.world import World
from engine.systems.render_system import RenderSystem


class FakeGameLayout:
    active_tab = "GAME"
    game_view_device_profile = ""

    @staticmethod
    def get_center_view_rect() -> SimpleNamespace:
        return SimpleNamespace(x=100.0, y=50.0, width=800.0, height=450.0)

    @staticmethod
    def get_game_view_content_rect() -> SimpleNamespace:
        return SimpleNamespace(x=100.0, y=50.0, width=800.0, height=450.0)

    @staticmethod
    def map_game_view_screen_point_to_texture(screen_x: float, screen_y: float) -> tuple[float, float]:
        rect = FakeGameLayout.get_game_view_content_rect()
        scale_x = 1280.0 / rect.width
        scale_y = 720.0 / rect.height
        return ((screen_x - rect.x) * scale_x, (screen_y - rect.y) * scale_y)


def test_editor_game_view_input_uses_game_view_texture_coords_for_picking() -> None:
    game = Game(editor_enabled=False, hot_reload_enabled=False)
    game.editor_layout = FakeGameLayout()

    world = World()
    card = world.create_entity("Card_oros_1")
    card.add_component(Transform(x=320.0, y=240.0))
    card.add_component(Sprite(texture_path="assets/spanish_deck/1.PNG", width=90, height=140))
    card.add_component(RenderOrder2D(sorting_layer="Cards", order_in_layer=10))

    game._world = world
    game._render_system = RenderSystem()

    mouse = SimpleNamespace(x=300.0, y=200.0)
    with (
        patch("engine.core.game.rl.get_mouse_position", return_value=mouse),
        patch("engine.core.game.rl.is_mouse_button_down", return_value=True),
        patch("engine.core.game.rl.is_mouse_button_pressed", return_value=True),
        patch("engine.core.game.rl.is_mouse_button_released", return_value=False),
        patch.object(game, "_runtime_pressed_keys", return_value=[]),
    ):
        game._update_runtime_input_from_editor((1280.0, 720.0), active_tab="GAME")

    assert tuple(game.runtime_input.mouse_screen) == (300.0, 200.0)
    assert tuple(game.runtime_input.mouse_viewport) == (320.0, 240.0)
    assert tuple(game.runtime_input.mouse_world) == (320.0, 240.0)

    picked = game.runtime_render_queries.pick_sprite_at_mouse()
    assert picked is not None
    assert picked.name == "Card_oros_1"
