from __future__ import annotations

from .cards import Card, RANK_ORDER, RANKS, Suit

RED_SUITS = {Suit.OROS, Suit.COPAS}
BLACK_SUITS = {Suit.ESPADAS, Suit.BASTOS}


def card_color(card: Card) -> str:
    return "red" if card.suit in RED_SUITS else "black"


def foundation_expected_rank(foundation: list[Card]) -> int | None:
    if not foundation:
        return RANKS[0]
    current = foundation[-1].rank
    next_index = RANK_ORDER[current] + 1
    if next_index >= len(RANKS):
        return None
    return RANKS[next_index]


def can_move_to_foundation(card: Card, foundation: list[Card]) -> bool:
    if not card.face_up:
        return False
    expected = foundation_expected_rank(foundation)
    if expected is None or card.rank != expected:
        return False
    return not foundation or card.suit == foundation[-1].suit


def can_move_to_tableau(card: Card, destination_card: Card | None) -> bool:
    if not card.face_up:
        return False
    if destination_card is None:
        return card.rank == 12
    if not destination_card.face_up:
        return False
    return (
        card_color(card) != card_color(destination_card)
        and RANK_ORDER[card.rank] == RANK_ORDER[destination_card.rank] - 1
    )


def is_valid_descending_alternating_sequence(sequence: list[Card]) -> bool:
    if not sequence or any(not card.face_up for card in sequence):
        return False
    for upper, lower in zip(sequence, sequence[1:]):
        if card_color(upper) == card_color(lower):
            return False
        if RANK_ORDER[lower.rank] != RANK_ORDER[upper.rank] - 1:
            return False
    return True


def can_move_sequence(sequence: list[Card]) -> bool:
    return is_valid_descending_alternating_sequence(sequence)
