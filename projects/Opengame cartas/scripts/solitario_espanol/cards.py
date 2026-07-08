from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Suit(str, Enum):
    OROS = "oros"
    COPAS = "copas"
    ESPADAS = "espadas"
    BASTOS = "bastos"


SUITS = (Suit.OROS, Suit.COPAS, Suit.ESPADAS, Suit.BASTOS)
RANKS = (1, 2, 3, 4, 5, 6, 7, 10, 11, 12)
RANK_ORDER = {rank: index for index, rank in enumerate(RANKS)}
RANK_NAMES = {1: "As", 10: "Sota", 11: "Caballo", 12: "Rey"}
BACK_ASSET_PATH = "assets/spanish_deck/back.PNG"


@dataclass
class Card:
    suit: Suit
    rank: int
    face_up: bool = False

    @property
    def id(self) -> str:
        return f"{self.suit.value}_{self.rank}"

    @property
    def display_name(self) -> str:
        return f"{RANK_NAMES.get(self.rank, str(self.rank))} de {self.suit.value}"


def build_spanish_deck(*, face_up: bool = False) -> list[Card]:
    return [Card(suit=suit, rank=rank, face_up=face_up) for suit in SUITS for rank in RANKS]


def asset_index_for(card: Card) -> int:
    suit_offset = SUITS.index(card.suit) * len(RANKS)
    return suit_offset + RANKS.index(card.rank) + 1


def asset_path_for(card: Card) -> str:
    return f"assets/spanish_deck/{asset_index_for(card)}.PNG"


def card_entity_name(card: Card) -> str:
    return f"Card_{card.suit.value}_{card.rank}"
