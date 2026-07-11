from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1] / "projects" / "Opengame cartas"
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from solitario_espanol import controller  # noqa: E402
from solitario_espanol.cards import (  # noqa: E402
    RANKS,
    SUITS,
    Card,
    Suit,
    asset_path_for,
    build_spanish_deck,
    card_entity_name,  # noqa: E402
)
from solitario_espanol.layout import CARD_HEIGHT, CARD_WIDTH, tableau_card_rect  # noqa: E402
from solitario_espanol.rules import can_move_to_foundation, can_move_to_tableau  # noqa: E402
from solitario_espanol.state import SolitaireGameState  # noqa: E402


def face_up(suit: Suit, rank: int) -> Card:
    return Card(suit=suit, rank=rank, face_up=True)


def test_deck_has_40_unique_spanish_cards_without_8_or_9() -> None:
    deck = build_spanish_deck()

    assert len(deck) == 40
    assert {card.suit for card in deck} == set(SUITS)
    assert all(sum(1 for card in deck if card.suit == suit) == 10 for suit in SUITS)
    assert {card.rank for card in deck} == set(RANKS)
    assert 8 not in {card.rank for card in deck}
    assert 9 not in {card.rank for card in deck}
    assert len({(card.suit, card.rank) for card in deck}) == 40
    assert asset_path_for(Card(Suit.OROS, 1)) == "assets/spanish_deck/1.PNG"
    assert asset_path_for(Card(Suit.BASTOS, 12)) == "assets/spanish_deck/40.PNG"


def test_foundation_rules() -> None:
    assert can_move_to_foundation(face_up(Suit.OROS, 1), [])
    assert not can_move_to_foundation(face_up(Suit.OROS, 2), [])
    assert can_move_to_foundation(face_up(Suit.OROS, 2), [face_up(Suit.OROS, 1)])
    assert not can_move_to_foundation(face_up(Suit.COPAS, 2), [face_up(Suit.OROS, 1)])
    assert not can_move_to_foundation(face_up(Suit.OROS, 3), [face_up(Suit.OROS, 1)])


def test_tableau_rules() -> None:
    assert can_move_to_tableau(face_up(Suit.OROS, 12), None)
    assert not can_move_to_tableau(face_up(Suit.OROS, 11), None)
    assert can_move_to_tableau(face_up(Suit.ESPADAS, 11), face_up(Suit.COPAS, 12))
    assert can_move_to_tableau(face_up(Suit.COPAS, 7), face_up(Suit.BASTOS, 10))
    assert not can_move_to_tableau(face_up(Suit.OROS, 11), face_up(Suit.COPAS, 12))
    assert not can_move_to_tableau(face_up(Suit.ESPADAS, 10), face_up(Suit.COPAS, 12))


def test_initial_deal_distribution_and_visibility() -> None:
    state = SolitaireGameState.deal(seed=7)

    assert len(state.tableau) == 7
    assert [len(column) for column in state.tableau] == [1, 2, 3, 4, 5, 6, 7]
    for column in state.tableau:
        assert column[-1].face_up
        assert all(not card.face_up for card in column[:-1])
    assert len(state.stock) == 12
    assert len(state.all_cards()) == 40
    assert len({(card.suit, card.rank) for card in state.all_cards()}) == 40


def test_stock_waste_draw_and_recycle() -> None:
    state = SolitaireGameState.deal(seed=3)
    original_stock = list(state.stock)

    assert state.draw_stock()
    assert len(state.stock) == 11
    assert len(state.waste) == 1
    assert state.waste[-1] is original_stock[-1]
    assert state.waste[-1].face_up

    while state.stock:
        assert state.draw_stock()
    assert len(state.waste) == 12
    assert state.draw_stock()
    assert len(state.stock) == 12
    assert not state.waste
    assert all(not card.face_up for card in state.stock)


def test_move_to_tableau_flips_new_top_card() -> None:
    state = SolitaireGameState()
    hidden = Card(Suit.BASTOS, 6, face_up=False)
    moving = face_up(Suit.ESPADAS, 4)
    destination = face_up(Suit.COPAS, 5)
    state.tableau[0] = [hidden, moving]
    state.tableau[1] = [destination]

    assert state.select_tableau_sequence(0, 1)
    assert state.move_selection_to_tableau(1)
    assert state.tableau[0] == [hidden]
    assert state.tableau[0][0].face_up
    assert state.tableau[1][-1] is moving


def test_move_to_foundation_and_victory() -> None:
    state = SolitaireGameState()
    ace = face_up(Suit.OROS, 1)
    two = face_up(Suit.OROS, 2)
    state.waste = [ace]
    assert state.select_waste_top()
    assert state.move_selection_to_foundation(Suit.OROS)
    assert state.foundations[Suit.OROS] == [ace]

    state.waste = [two]
    assert state.select_waste_top()
    assert state.move_selection_to_foundation(Suit.OROS)
    assert state.foundations[Suit.OROS] == [ace, two]

    state.foundations = {
        suit: [Card(suit, rank, face_up=True) for rank in RANKS]
        for suit in SUITS
    }
    assert state.is_won()


def test_generated_scene_contract() -> None:
    scene_path = PROJECT_ROOT / "levels" / "main_scene.json"
    if not scene_path.exists():
        return
    scene = json.loads(scene_path.read_text(encoding="utf-8"))
    entities = scene["entities"]
    names = {entity["name"] for entity in entities}
    by_name = {entity["name"]: entity for entity in entities}

    assert "SolitaireDirector" in names
    assert sum(1 for name in names if name.startswith("Card_")) == 40
    director = next(entity for entity in entities if entity["name"] == "SolitaireDirector")
    script = director["components"]["ScriptBehaviour"]
    assert script["module_path"] == "solitario_espanol.controller"
    assert {"SolitaireCanvas", "TitleBanner", "MovesPanel", "StatusPanel", "VictoryPanel", "RestartButton"} <= names

    restart_button = by_name["RestartButton"]["components"]["UIButton"]
    assert restart_button["normal_sprite"]["path"].endswith("UI_Flat_Banner01a.png")
    assert restart_button["hover_sprite"]["path"].endswith("UI_Flat_Banner02a.png")
    assert restart_button["pressed_sprite"]["path"].endswith("UI_Flat_Banner03a.png")
    assert restart_button["disabled_sprite"]["path"].endswith("UI_Flat_Banner04a.png")

    victory_panel = by_name["VictoryPanel"]["components"]["UIImage"]
    assert victory_panel["sprite"]["path"].endswith("UI_Flat_Frame03a.png")

    manifest = json.loads((PROJECT_ROOT / "game.manifest.json").read_text(encoding="utf-8"))
    asset_paths = {asset["path"] for asset in manifest["assets"]}
    assert "assets/Complete_UI_Essential_Pack_Free/01_Flat_Theme/Sprites/UI_Flat_Banner01a.png" in asset_paths
    assert "assets/Complete_UI_Essential_Pack_Free/01_Flat_Theme/Sprites/UI_Flat_Frame02a.png" in asset_paths
    assert "assets/Complete_UI_Essential_Pack_Free/01_Flat_Theme/Sprites/UI_Flat_Frame03a.png" in asset_paths
    assert "assets/Complete_UI_Essential_Pack_Free/01_Flat_Theme/Sprites/UI_Flat_Bar01a.png" in asset_paths
    assert "assets/Complete_UI_Essential_Pack_Free/01_Flat_Theme/Sprites/UI_Flat_FrameSlot01a.png" in asset_paths


class FakeEntity:
    def __init__(self, name: str) -> None:
        self.name = name
        self.components = {
            "Transform": FakeTransform(),
            "Sprite": FakeSprite(),
            "Collider": FakeCollider(),
            "RenderOrder2D": FakeRenderOrder(),
        }

    def get_component_by_name(self, name: str):
        return self.components.get(name)


class FakeTransform:
    x = -400.0
    y = -400.0
    scale_x = 1.0
    scale_y = 1.0


class FakeSprite:
    enabled = False
    width = int(CARD_WIDTH)
    height = int(CARD_HEIGHT)
    origin_x = 0.5
    origin_y = 0.5
    tint = [255, 255, 255, 255]
    texture_path = ""

    def sync_texture_reference(self, texture: str) -> None:
        self.texture_path = texture


class FakeCollider:
    enabled = False
    width = CARD_WIDTH
    height = CARD_HEIGHT


class FakeRenderOrder:
    sorting_layer = "Cards"
    order_in_layer = 0


class FakeWorld:
    def __init__(self) -> None:
        self.entities = {card_entity_name(card): FakeEntity(card_entity_name(card)) for card in build_spanish_deck()}

    def get_entity_by_name(self, name: str):
        return self.entities.get(name)

    def touch_transform(self) -> None:
        pass

    def touch_render(self) -> None:
        pass

    def touch_ui_layout(self) -> None:
        pass


class FakeInput:
    def __init__(self, *, left_pressed: bool = False, keys_pressed: set[str] | None = None) -> None:
        self.left_down = left_pressed
        self.left_pressed = left_pressed
        self.left_released = False
        self.mouse_screen = (0.0, 0.0)
        self.mouse_viewport = (0.0, 0.0)
        self.mouse_world = (0.0, 0.0)
        self._keys_pressed = keys_pressed or set()

    def key_pressed(self, key_name: str) -> bool:
        return key_name.upper() in self._keys_pressed


class FakePicking:
    def __init__(self, world: FakeWorld, point: tuple[float, float] | None = None) -> None:
        self.world = world
        self.point = point

    def pick_sprite_at_mouse(self, layer: str | None = None):
        if self.point is None:
            return None
        x, y = self.point
        hits = []
        for entity in self.world.entities.values():
            sprite = entity.get_component_by_name("Sprite")
            transform = entity.get_component_by_name("Transform")
            if sprite is None or transform is None or not getattr(sprite, "enabled", True):
                continue
            width = float(getattr(sprite, "width", CARD_WIDTH)) * float(getattr(transform, "scale_x", 1.0))
            height = float(getattr(sprite, "height", CARD_HEIGHT)) * float(getattr(transform, "scale_y", 1.0))
            left = float(getattr(transform, "x", 0.0)) - width * float(getattr(sprite, "origin_x", 0.5))
            top = float(getattr(transform, "y", 0.0)) - height * float(getattr(sprite, "origin_y", 0.5))
            min_x, max_x = sorted((left, left + width))
            min_y, max_y = sorted((top, top + height))
            if min_x <= x <= max_x and min_y <= y <= max_y:
                render_order = entity.get_component_by_name("RenderOrder2D")
                order = int(getattr(render_order, "order_in_layer", 0)) if render_order is not None else 0
                hits.append((order, entity.name))
        if not hits:
            return None
        _order, entity_name = max(hits, key=lambda item: item[0])
        return self.world.get_entity_by_name(entity_name)


class FakeContext:
    def __init__(
        self,
        world: FakeWorld,
        *,
        point: tuple[float, float] | None = None,
        left_pressed: bool = False,
        keys_pressed: set[str] | None = None,
    ) -> None:
        self.world = world
        self.public_data = {}
        self.input = FakeInput(left_pressed=left_pressed, keys_pressed=keys_pressed)
        self.picking = FakePicking(world, point)
        self.render = self.picking


def render_fake_world(state: SolitaireGameState) -> FakeWorld:
    world = FakeWorld()
    controller._render(world, controller.RuntimeSession(state))
    return world


def card_tint(world: FakeWorld, card: Card):
    return world.get_entity_by_name(card_entity_name(card)).get_component_by_name("Sprite").tint


def test_picking_click_inside_rendered_tableau_card_selects_that_card() -> None:
    state = SolitaireGameState()
    state.tableau[0] = [face_up(Suit.OROS, 12), face_up(Suit.ESPADAS, 11)]
    world = render_fake_world(state)
    rect = tableau_card_rect(0, 0, 2)

    context = FakeContext(world, point=(rect.x + 10.0, rect.y + 10.0), left_pressed=True)
    controller._handle_click(context, controller.RuntimeSession(state))

    assert state.selected_source is not None
    assert state.selected_source.kind == "tableau"
    assert state.selected_source.index == 0
    assert state.selected_source.offset == 0
    assert state.selected_cards == state.tableau[0]


def test_picking_overlap_prefers_visually_top_card() -> None:
    state = SolitaireGameState()
    state.tableau[0] = [face_up(Suit.OROS, 12), face_up(Suit.ESPADAS, 11)]
    world = render_fake_world(state)
    lower_rect = tableau_card_rect(0, 1, 2)

    context = FakeContext(world, point=(lower_rect.x + 10.0, lower_rect.y + 10.0))
    target = controller._resolve_click_target(context, state)

    assert target is not None
    assert target.kind == "tableau"
    assert target.index == 0
    assert target.card_index == 1


def test_picking_visible_band_of_lower_tableau_card_selects_sequence_start() -> None:
    state = SolitaireGameState()
    state.tableau[0] = [face_up(Suit.OROS, 12), face_up(Suit.ESPADAS, 11)]
    world = render_fake_world(state)
    upper_rect = tableau_card_rect(0, 0, 2)

    context = FakeContext(world, point=(upper_rect.x + 10.0, upper_rect.y + 10.0))
    target = controller._resolve_click_target(context, state)

    assert target is not None
    assert target.kind == "tableau"
    assert target.index == 0
    assert target.card_index == 0


def test_picking_click_outside_cards_and_slots_clears_selection() -> None:
    state = SolitaireGameState()
    state.tableau[0] = [face_up(Suit.OROS, 12), face_up(Suit.ESPADAS, 11)]
    state.select_tableau_sequence(0, 1)
    world = render_fake_world(state)

    context = FakeContext(world, point=(1279.0, 719.0), left_pressed=True)
    controller._handle_click(context, controller.RuntimeSession(state))

    assert state.selected_cards == []
    assert state.selected_source is None


def test_picking_waste_only_targets_top_card() -> None:
    state = SolitaireGameState()
    bottom = face_up(Suit.OROS, 1)
    top = face_up(Suit.COPAS, 2)
    state.waste = [bottom, top]
    world = render_fake_world(state)
    top_entity = world.get_entity_by_name(card_entity_name(top))
    transform = top_entity.get_component_by_name("Transform")

    context = FakeContext(world, point=(transform.x, transform.y))
    target = controller._resolve_click_target(context, state)
    target_names = controller._card_targets_by_entity_name(state)

    assert target is not None
    assert target.kind == "waste"
    assert card_entity_name(top) in target_names
    assert card_entity_name(bottom) not in target_names


def test_hover_over_visible_card_applies_hover_tint() -> None:
    card = face_up(Suit.OROS, 12)
    state = SolitaireGameState()
    state.tableau[0] = [card]
    session = controller.RuntimeSession(state)
    world = FakeWorld()
    controller._render(world, session)
    rect = tableau_card_rect(0, 0, 1)

    context = FakeContext(world, point=(rect.x + 10.0, rect.y + 10.0))
    controller._update_hover(context, session)
    controller._render(world, session)

    assert card_tint(world, card) == controller.HOVER_TINT


def test_selected_card_keeps_selected_tint_over_hover() -> None:
    card = face_up(Suit.OROS, 12)
    state = SolitaireGameState()
    state.tableau[0] = [card]
    state.select_tableau_sequence(0, 0)
    session = controller.RuntimeSession(state)
    world = FakeWorld()
    controller._render(world, session)
    rect = tableau_card_rect(0, 0, 1)

    context = FakeContext(world, point=(rect.x + 10.0, rect.y + 10.0))
    controller._update_hover(context, session)
    controller._render(world, session)

    assert card_tint(world, card) == controller.SELECTED_TINT


def test_hover_overlap_illuminates_top_card() -> None:
    lower = face_up(Suit.OROS, 12)
    top = face_up(Suit.ESPADAS, 11)
    state = SolitaireGameState()
    state.tableau[0] = [lower, top]
    session = controller.RuntimeSession(state)
    world = FakeWorld()
    controller._render(world, session)
    top_rect = tableau_card_rect(0, 1, 2)

    context = FakeContext(world, point=(top_rect.x + 10.0, top_rect.y + 10.0))
    controller._update_hover(context, session)
    controller._render(world, session)

    assert card_tint(world, top) == controller.HOVER_TINT
    assert card_tint(world, lower) == controller.NORMAL_TINT


def test_hover_outside_cards_illuminates_nothing() -> None:
    card = face_up(Suit.OROS, 12)
    state = SolitaireGameState()
    state.tableau[0] = [card]
    session = controller.RuntimeSession(state)
    world = FakeWorld()
    controller._render(world, session)

    context = FakeContext(world, point=(1279.0, 719.0))
    controller._update_hover(context, session)
    controller._render(world, session)

    assert session.hovered_card_name is None
    assert card_tint(world, card) == controller.NORMAL_TINT


def test_hover_waste_illuminates_only_top_card() -> None:
    bottom = face_up(Suit.OROS, 1)
    top = face_up(Suit.COPAS, 2)
    state = SolitaireGameState()
    state.waste = [bottom, top]
    session = controller.RuntimeSession(state)
    world = FakeWorld()
    controller._render(world, session)
    top_entity = world.get_entity_by_name(card_entity_name(top))
    transform = top_entity.get_component_by_name("Transform")

    context = FakeContext(world, point=(transform.x, transform.y))
    controller._update_hover(context, session)
    controller._render(world, session)

    assert card_tint(world, top) == controller.HOVER_TINT
    assert card_tint(world, bottom) == controller.NORMAL_TINT


def test_solitario_controller_does_not_import_pyray_for_input() -> None:
    source = Path(controller.__file__).read_text(encoding="utf-8")
    assert "import pyray" not in source
    assert "get_mouse_position" not in source
    assert "is_mouse_button_pressed" not in source


def test_hover_and_click_share_runtime_picking() -> None:
    card = face_up(Suit.OROS, 12)
    state = SolitaireGameState()
    state.tableau[0] = [card]
    session = controller.RuntimeSession(state)
    world = FakeWorld()
    controller._render(world, session)
    entity = world.get_entity_by_name(card_entity_name(card))
    transform = entity.get_component_by_name("Transform")
    context = FakeContext(world, point=(transform.x, transform.y), left_pressed=True)

    controller._update_hover(context, session)
    controller._handle_click(context, session)

    assert session.hovered_card_name == card_entity_name(card)
    assert state.selected_cards == [card]


def test_hover_update_does_not_change_existing_selection() -> None:
    selected = face_up(Suit.OROS, 12)
    state = SolitaireGameState()
    state.tableau[0] = [selected]
    state.select_tableau_sequence(0, 0)
    session = controller.RuntimeSession(state)
    world = FakeWorld()
    controller._render(world, session)
    context = FakeContext(world, point=(1279.0, 719.0))

    controller._update_hover(context, session)

    assert session.hovered_card_name is None
    assert state.selected_cards == [selected]
