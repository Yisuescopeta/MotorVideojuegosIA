from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cards import BACK_ASSET_PATH, Card, SUITS, Suit, asset_path_for, build_spanish_deck, card_entity_name
from .layout import (
    CARD_HEIGHT,
    CARD_WIDTH,
    ClickTarget,
    foundation_rect,
    stock_rect,
    tableau_card_rect,
    tableau_slot_rect,
    waste_rect,
)
from .state import SolitaireGameState

SELECTED_TINT = (255, 232, 125, 255)
HOVER_TINT = (255, 246, 178, 255)
NORMAL_TINT = (255, 255, 255, 255)
HIDDEN_TINT = (255, 255, 255, 255)
INVALID_TINT = (196, 61, 61, 210)
SLOT_TINT = (42, 98, 76, 180)
FOUNDATION_TINT = (56, 118, 88, 190)
TABLEAU_TINT = (35, 68, 86, 160)


@dataclass
class RuntimeSession:
    state: SolitaireGameState
    invalid_timer: float = 0.0
    hovered_card_name: str | None = None


_SESSIONS: dict[int, RuntimeSession] = {}


def on_play(context: Any) -> None:
    state = SolitaireGameState.deal(_seed_from_public_data(context.public_data))
    _SESSIONS[id(context.world)] = RuntimeSession(state=state)
    _render(context.world, _SESSIONS[id(context.world)])


def on_update(context: Any, dt: float) -> None:
    session = _SESSIONS.get(id(context.world))
    if session is None:
        on_play(context)
        session = _SESSIONS[id(context.world)]

    if _key_pressed(context, "R"):
        session.state = SolitaireGameState.deal(_seed_from_public_data(context.public_data))
        session.invalid_timer = 0.0

    if bool(getattr(getattr(context, "input", None), "left_pressed", False)):
        _handle_click(context, session)

    session.invalid_timer = max(0.0, session.invalid_timer - float(dt or 0.0))
    _update_hover(context, session)
    _render(context.world, session)


def on_stop(context: Any) -> None:
    _SESSIONS.pop(id(context.world), None)


def _seed_from_public_data(public_data: dict[str, Any]) -> int | None:
    raw = public_data.get("seed") if isinstance(public_data, dict) else None
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _handle_click(context: Any, session: RuntimeSession) -> None:
    state = session.state
    target = _resolve_click_target(context, state)
    if target is None:
        state.clear_selection()
        return

    changed = False
    had_selection = bool(state.selected_cards)
    if target.kind == "stock":
        changed = state.draw_stock()
    elif had_selection:
        changed = _try_selected_move(state, target)
        if not changed:
            state.clear_selection()
            session.invalid_timer = 0.65
    elif target.kind == "waste":
        changed = state.select_waste_top()
    elif target.kind == "tableau" and isinstance(target.index, int) and target.card_index is not None:
        changed = state.select_tableau_sequence(target.index, target.card_index)

    if not changed and not had_selection and target.kind not in {"waste", "tableau"}:
        session.invalid_timer = 0.65


def _try_selected_move(state: SolitaireGameState, target: Any) -> bool:
    if target.kind == "tableau" and isinstance(target.index, int):
        return state.move_selection_to_tableau(target.index)
    if target.kind == "foundation" and isinstance(target.index, Suit):
        return state.move_selection_to_foundation(target.index)
    return False


def _resolve_click_target(context: Any, state: SolitaireGameState) -> ClickTarget | None:
    entity = _pick_entity_at_mouse(context)
    if entity is None:
        return None
    return _target_for_entity_name(state, str(getattr(entity, "name", "")))


def _update_hover(context: Any, session: RuntimeSession) -> None:
    entity = _pick_entity_at_mouse(context)
    entity_name = str(getattr(entity, "name", "")) if entity is not None else ""
    session.hovered_card_name = entity_name if entity_name in _card_targets_by_entity_name(session.state) else None


def _pick_entity_at_mouse(context: Any) -> Any | None:
    picking = getattr(context, "picking", None) or getattr(context, "render", None)
    if picking is None or not hasattr(picking, "pick_sprite_at_mouse"):
        return None
    return picking.pick_sprite_at_mouse()


def _target_for_entity_name(state: SolitaireGameState, entity_name: str) -> ClickTarget | None:
    card_targets = _card_targets_by_entity_name(state)
    if entity_name in card_targets:
        return card_targets[entity_name]
    return _slot_target_by_entity_name(entity_name)


def _card_targets_by_entity_name(state: SolitaireGameState) -> dict[str, ClickTarget]:
    targets: dict[str, ClickTarget] = {}
    for card in state.stock:
        targets[card_entity_name(card)] = ClickTarget("stock")
    if state.waste:
        targets[card_entity_name(state.waste[-1])] = ClickTarget("waste")
    for suit in SUITS:
        if state.foundations[suit]:
            targets[card_entity_name(state.foundations[suit][-1])] = ClickTarget("foundation", suit)
    for column_index, column in enumerate(state.tableau):
        for card_index, card in enumerate(column):
            targets[card_entity_name(card)] = ClickTarget("tableau", column_index, card_index)
    return targets


def _slot_target_by_entity_name(entity_name: str) -> ClickTarget | None:
    if entity_name == "Slot_Stock":
        return ClickTarget("stock")
    if entity_name == "Slot_Waste":
        return ClickTarget("waste")
    for suit in SUITS:
        if entity_name == f"Slot_Foundation_{suit.value}":
            return ClickTarget("foundation", suit)
    prefix = "Slot_Tableau_"
    if entity_name.startswith(prefix):
        try:
            index = int(entity_name[len(prefix):]) - 1
        except ValueError:
            return None
        if 0 <= index < 7:
            return ClickTarget("tableau", index, None)
    return None


def _render(world: Any, session: RuntimeSession) -> None:
    state = session.state
    selected_ids = {id(card) for card in state.selected_cards}
    hovered_name = session.hovered_card_name
    _hide_all_cards(world)

    stock = stock_rect()
    for order, card in enumerate(state.stock):
        _place_card(
            world,
            card,
            stock.x,
            stock.y,
            100 + order,
            selected=id(card) in selected_ids,
            hovered=card_entity_name(card) == hovered_name,
        )

    waste = waste_rect()
    for order, card in enumerate(state.waste):
        _place_card(
            world,
            card,
            waste.x,
            waste.y,
            250 + order,
            selected=id(card) in selected_ids,
            hovered=card_entity_name(card) == hovered_name,
        )

    for foundation_index, suit in enumerate(SUITS):
        rect = foundation_rect(suit)
        for order, card in enumerate(state.foundations[suit]):
            _place_card(
                world,
                card,
                rect.x,
                rect.y,
                400 + foundation_index * 30 + order,
                selected=False,
                hovered=card_entity_name(card) == hovered_name,
            )

    for column_index, column in enumerate(state.tableau):
        for card_index, card in enumerate(column):
            rect = tableau_card_rect(column_index, card_index, len(column))
            _place_card(
                world,
                card,
                rect.x,
                rect.y,
                1000 + column_index * 100 + card_index,
                selected=id(card) in selected_ids,
                hovered=card_entity_name(card) == hovered_name,
            )

    _update_slot_tints(world, session)
    _update_ui(world, session)
    _touch_world(world)


def _hide_all_cards(world: Any) -> None:
    for card in build_spanish_deck():
        entity = world.get_entity_by_name(card_entity_name(card))
        if entity is None:
            continue
        transform = entity.get_component_by_name("Transform")
        sprite = entity.get_component_by_name("Sprite")
        collider = entity.get_component_by_name("Collider")
        if transform is not None:
            transform.x = -400.0
            transform.y = -400.0
        if sprite is not None:
            sprite.enabled = False
        if collider is not None:
            collider.enabled = False


def _place_card(world: Any, card: Card, x: float, y: float, order: int, *, selected: bool, hovered: bool) -> None:
    entity = world.get_entity_by_name(card_entity_name(card))
    if entity is None:
        return
    transform = entity.get_component_by_name("Transform")
    sprite = entity.get_component_by_name("Sprite")
    collider = entity.get_component_by_name("Collider")
    render_order = entity.get_component_by_name("RenderOrder2D")
    if transform is not None:
        transform.x = x + CARD_WIDTH / 2.0
        transform.y = y + CARD_HEIGHT / 2.0
    if sprite is not None:
        sprite.enabled = True
        texture = asset_path_for(card) if card.face_up else BACK_ASSET_PATH
        if hasattr(sprite, "sync_texture_reference"):
            sprite.sync_texture_reference(texture)
        else:
            sprite.texture_path = texture
        sprite.width = int(CARD_WIDTH)
        sprite.height = int(CARD_HEIGHT)
        if selected:
            sprite.tint = SELECTED_TINT
        elif hovered:
            sprite.tint = HOVER_TINT
        else:
            sprite.tint = NORMAL_TINT if card.face_up else HIDDEN_TINT
    if collider is not None:
        collider.enabled = True
        collider.width = CARD_WIDTH
        collider.height = CARD_HEIGHT
    if render_order is not None:
        render_order.sorting_layer = "Cards"
        render_order.order_in_layer = int(order)


def _update_slot_tints(world: Any, session: RuntimeSession) -> None:
    invalid = session.invalid_timer > 0.0
    _set_polygon_color(world, "Slot_Stock", INVALID_TINT if invalid else SLOT_TINT)
    _set_polygon_color(world, "Slot_Waste", SLOT_TINT)
    for suit in SUITS:
        _set_polygon_color(world, f"Slot_Foundation_{suit.value}", FOUNDATION_TINT)
    for index in range(7):
        _set_polygon_color(world, f"Slot_Tableau_{index + 1}", TABLEAU_TINT)


def _set_polygon_color(world: Any, entity_name: str, color: tuple[int, int, int, int]) -> None:
    entity = world.get_entity_by_name(entity_name)
    if entity is None:
        return
    polygon = entity.get_component_by_name("Polygon2D")
    if polygon is not None:
        polygon.color = color


def _update_ui(world: Any, session: RuntimeSession) -> None:
    state = session.state
    _set_text(world, "MovesText", f"Movimientos: {state.moves_count}")
    selected = state.selected_cards[0].display_name if state.selected_cards else "ninguna"
    hovered = _card_display_name_by_entity_name(state, session.hovered_card_name) or "ninguna"
    if state.game_won:
        status = "Victoria. Partida completada. Reiniciar para jugar otra vez."
    elif session.invalid_timer > 0.0:
        status = "Movimiento invalido"
    else:
        status = f"Hover: {hovered}. Seleccion: {selected}. R o Reiniciar."
    _set_text(world, "StatusText", status)
    _set_text(world, "VictoryText", "Victoria\nPartida completada" if state.game_won else "")
    _set_ui_enabled(world, "VictoryPanel", state.game_won, "UIImage")


def _card_display_name_by_entity_name(state: SolitaireGameState, entity_name: str | None) -> str | None:
    if not entity_name:
        return None
    for card in state.all_cards():
        if card_entity_name(card) == entity_name:
            return card.display_name
    return None


def _set_text(world: Any, entity_name: str, text: str) -> None:
    entity = world.get_entity_by_name(entity_name)
    if entity is None:
        return
    ui_text = entity.get_component_by_name("UIText")
    if ui_text is not None:
        ui_text.text = text
        ui_text.enabled = bool(text) or entity_name != "VictoryText"


def _set_ui_enabled(world: Any, entity_name: str, enabled: bool, component_name: str) -> None:
    entity = world.get_entity_by_name(entity_name)
    if entity is None:
        return
    component = entity.get_component_by_name(component_name)
    if component is not None:
        component.enabled = bool(enabled)


def _touch_world(world: Any) -> None:
    if hasattr(world, "touch_transform"):
        world.touch_transform()
    if hasattr(world, "touch_render"):
        world.touch_render()
    if hasattr(world, "touch_ui_layout"):
        world.touch_ui_layout()


def _key_pressed(context: Any, key_name: str) -> bool:
    runtime_input = getattr(context, "input", None)
    if runtime_input is None or not hasattr(runtime_input, "key_pressed"):
        return False
    return bool(runtime_input.key_pressed(key_name))
