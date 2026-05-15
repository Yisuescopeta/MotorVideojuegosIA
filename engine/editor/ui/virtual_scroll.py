"""Virtual scroll — only render visible rows for large lists."""

from __future__ import annotations


class VirtualScroll:
    """Tracks which rows are visible in a scrollable viewport.

    Usage:
        vs = VirtualScroll(row_height=18)
        vs.update(item_count=500, viewport_height=400, scroll_offset=sc)
        for i in range(vs.first_visible, vs.last_visible):
            render_row(i, y = vs.row_y(i))
    """

    def __init__(self, row_height: int = 18, buffer_rows: int = 2):
        self.row_height = max(1, row_height)
        self.buffer_rows = max(0, buffer_rows)
        self.first_visible: int = 0
        self.last_visible: int = 0
        self.total_items: int = 0
        self.viewport_height: float = 0.0
        self.scroll_offset: float = 0.0
        self._enabled: bool = True

    @property
    def threshold(self) -> int:
        """Number of items above which virtualization activates."""
        return 100

    @property
    def enabled(self) -> bool:
        return self._enabled

    def update(self, item_count: int, viewport_height: float, scroll_offset: float) -> None:
        self.total_items = max(0, item_count)
        self.viewport_height = max(0.0, viewport_height)
        self.scroll_offset = max(0.0, scroll_offset)

        if self.total_items < self.threshold:
            self._enabled = False
            self.first_visible = 0
            self.last_visible = self.total_items
            return

        self._enabled = True
        visible_count = int(self.viewport_height / self.row_height) + 1
        self.first_visible = max(0, int(self.scroll_offset / self.row_height) - self.buffer_rows)
        self.last_visible = min(self.total_items, self.first_visible + visible_count + self.buffer_rows * 2)

    def row_y(self, index: int) -> float:
        """Y position of a row relative to the scroll container top."""
        return float(index * self.row_height - self.scroll_offset)

    @property
    def total_height(self) -> float:
        return float(self.total_items * self.row_height)
