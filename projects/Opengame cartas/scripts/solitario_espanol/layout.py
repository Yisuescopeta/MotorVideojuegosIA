from __future__ import annotations

from dataclasses import dataclass

from .cards import SUITS, Suit

REFERENCE_WIDTH = 1280
REFERENCE_HEIGHT = 720
CARD_WIDTH = 90.0
CARD_HEIGHT = 140.0
TOP_Y = 48.0
TABLEAU_Y = 226.0
LEFT_X = 70.0
GAP_X = 28.0
DEFAULT_OVERLAP_Y = 34.0
MIN_OVERLAP_Y = 22.0
BOTTOM_MARGIN = 24.0


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    width: float = CARD_WIDTH
    height: float = CARD_HEIGHT

    def contains(self, px: float, py: float) -> bool:
        return self.x <= px <= self.x + self.width and self.y <= py <= self.y + self.height

    @property
    def center(self) -> tuple[float, float]:
        return (self.x + self.width / 2.0, self.y + self.height / 2.0)


@dataclass(frozen=True)
class ClickTarget:
    kind: str
    index: int | Suit | None = None
    card_index: int | None = None


def tableau_x(column_index: int) -> float:
    return LEFT_X + column_index * (CARD_WIDTH + GAP_X)


def stock_rect() -> Rect:
    return Rect(LEFT_X, TOP_Y)


def waste_rect() -> Rect:
    return Rect(LEFT_X + CARD_WIDTH + GAP_X, TOP_Y)


def foundation_x(index: int) -> float:
    return 690.0 + index * (CARD_WIDTH + 22.0)


def foundation_rect(suit: Suit) -> Rect:
    return Rect(foundation_x(SUITS.index(suit)), TOP_Y)


def tableau_slot_rect(column_index: int) -> Rect:
    return Rect(tableau_x(column_index), TABLEAU_Y)


def overlap_for_count(count: int) -> float:
    if count <= 1:
        return DEFAULT_OVERLAP_Y
    available = REFERENCE_HEIGHT - TABLEAU_Y - CARD_HEIGHT - BOTTOM_MARGIN
    return max(MIN_OVERLAP_Y, min(DEFAULT_OVERLAP_Y, available / max(1, count - 1)))


def tableau_card_rect(column_index: int, card_index: int, column_count: int) -> Rect:
    overlap = overlap_for_count(column_count)
    return Rect(tableau_x(column_index), TABLEAU_Y + card_index * overlap)


def locate_click(x: float, y: float, tableau_counts: list[int]) -> ClickTarget | None:
    for suit in SUITS:
        if foundation_rect(suit).contains(x, y):
            return ClickTarget("foundation", suit)
    if waste_rect().contains(x, y):
        return ClickTarget("waste")
    if stock_rect().contains(x, y):
        return ClickTarget("stock")
    for column_index, count in enumerate(tableau_counts):
        slot = tableau_slot_rect(column_index)
        if count == 0:
            if slot.contains(x, y):
                return ClickTarget("tableau", column_index, None)
            continue
        for card_index in reversed(range(count)):
            rect = tableau_card_rect(column_index, card_index, count)
            visible_height = CARD_HEIGHT if card_index == count - 1 else overlap_for_count(count)
            if Rect(rect.x, rect.y, rect.width, visible_height).contains(x, y):
                return ClickTarget("tableau", column_index, card_index)
    return None
