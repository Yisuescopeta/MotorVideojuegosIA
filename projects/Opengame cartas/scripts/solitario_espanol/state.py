from __future__ import annotations

import random
from dataclasses import dataclass, field

from .cards import Card, Suit, build_spanish_deck
from .rules import can_move_sequence, can_move_to_foundation, can_move_to_tableau


@dataclass(frozen=True)
class SelectionSource:
    kind: str
    index: int | None = None
    offset: int | None = None


@dataclass
class SolitaireGameState:
    tableau: list[list[Card]] = field(default_factory=lambda: [[] for _ in range(7)])
    stock: list[Card] = field(default_factory=list)
    waste: list[Card] = field(default_factory=list)
    foundations: dict[Suit, list[Card]] = field(default_factory=lambda: {suit: [] for suit in Suit})
    selected_cards: list[Card] = field(default_factory=list)
    selected_source: SelectionSource | None = None
    moves_count: int = 0
    game_won: bool = False

    @classmethod
    def deal(cls, seed: int | None = None) -> "SolitaireGameState":
        deck = build_spanish_deck(face_up=False)
        rng = random.Random(seed)
        rng.shuffle(deck)
        state = cls()
        cursor = 0
        for column_index in range(7):
            count = column_index + 1
            column = deck[cursor : cursor + count]
            cursor += count
            for card in column[:-1]:
                card.face_up = False
            column[-1].face_up = True
            state.tableau[column_index] = column
        state.stock = deck[cursor:]
        for card in state.stock:
            card.face_up = False
        return state

    def all_cards(self) -> list[Card]:
        cards: list[Card] = []
        for column in self.tableau:
            cards.extend(column)
        cards.extend(self.stock)
        cards.extend(self.waste)
        for foundation in self.foundations.values():
            cards.extend(foundation)
        return cards

    def clear_selection(self) -> None:
        self.selected_cards = []
        self.selected_source = None

    def draw_stock(self) -> bool:
        if self.game_won:
            return False
        if not self.stock:
            return self.recycle_waste()
        card = self.stock.pop()
        card.face_up = True
        self.waste.append(card)
        self.moves_count += 1
        self.clear_selection()
        return True

    def recycle_waste(self) -> bool:
        if self.stock or not self.waste:
            return False
        self.stock = list(reversed(self.waste))
        self.waste = []
        for card in self.stock:
            card.face_up = False
        self.moves_count += 1
        self.clear_selection()
        return True

    def select_waste_top(self) -> bool:
        if not self.waste:
            self.clear_selection()
            return False
        self.selected_cards = [self.waste[-1]]
        self.selected_source = SelectionSource("waste")
        return True

    def select_tableau_sequence(self, column_index: int, card_index: int) -> bool:
        if column_index < 0 or column_index >= len(self.tableau):
            self.clear_selection()
            return False
        column = self.tableau[column_index]
        if card_index < 0 or card_index >= len(column):
            self.clear_selection()
            return False
        sequence = column[card_index:]
        if not can_move_sequence(sequence):
            self.clear_selection()
            return False
        self.selected_cards = sequence
        self.selected_source = SelectionSource("tableau", column_index, card_index)
        return True

    def move_selection_to_tableau(self, destination_index: int) -> bool:
        if not self.selected_cards or destination_index < 0 or destination_index >= len(self.tableau):
            self.clear_selection()
            return False
        source = self.selected_source
        if source and source.kind == "tableau" and source.index == destination_index:
            self.clear_selection()
            return False
        destination = self.tableau[destination_index]
        destination_card = destination[-1] if destination else None
        moving_card = self.selected_cards[0]
        if not can_move_to_tableau(moving_card, destination_card):
            self.clear_selection()
            return False
        moved = self._remove_selection_from_source()
        if not moved:
            self.clear_selection()
            return False
        destination.extend(moved)
        self._after_successful_move()
        return True

    def move_selection_to_foundation(self, suit: Suit) -> bool:
        if len(self.selected_cards) != 1:
            self.clear_selection()
            return False
        card = self.selected_cards[0]
        if card.suit != suit or not can_move_to_foundation(card, self.foundations[suit]):
            self.clear_selection()
            return False
        moved = self._remove_selection_from_source()
        if len(moved) != 1:
            self.clear_selection()
            return False
        self.foundations[suit].append(moved[0])
        self._after_successful_move()
        return True

    def _remove_selection_from_source(self) -> list[Card]:
        source = self.selected_source
        cards = list(self.selected_cards)
        if source is None:
            return []
        if source.kind == "waste":
            if self.waste and self.waste[-1] is cards[0]:
                return [self.waste.pop()]
            return []
        if source.kind == "tableau" and source.index is not None and source.offset is not None:
            column = self.tableau[source.index]
            if len(column) >= source.offset and column[source.offset:] == cards:
                del column[source.offset:]
                self._auto_flip_tableau(source.index)
                return cards
        return []

    def _auto_flip_tableau(self, column_index: int) -> None:
        column = self.tableau[column_index]
        if column and not column[-1].face_up:
            column[-1].face_up = True

    def _after_successful_move(self) -> None:
        self.moves_count += 1
        self.clear_selection()
        self.game_won = self.is_won()

    def is_won(self) -> bool:
        return sum(len(foundation) for foundation in self.foundations.values()) == 40
