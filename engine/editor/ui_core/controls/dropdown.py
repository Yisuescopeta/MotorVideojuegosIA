"""Pure dropdown and combobox models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from engine.editor.ui_core.controls.popup import PopupModel


@dataclass
class DropdownOption:
    """Serializable dropdown option."""

    id: str
    label: str
    value: object | None = None
    enabled: bool = True
    schema_version: int = 1


@dataclass
class DropdownModel:
    """Serializable dropdown state with pure filtering and selection logic."""

    options: list[DropdownOption] = field(default_factory=list)
    selected_index: int = -1
    popup: PopupModel = field(default_factory=PopupModel)
    item_height: float = 22.0
    width: float = 160.0
    editable: bool = False
    query: str = ""
    placeholder: str = "Select..."
    max_visible_items: int | None = None
    scroll_offset: int = 0
    schema_version: int = 1

    @property
    def selected_option(self) -> DropdownOption | None:
        if 0 <= self.selected_index < len(self.options):
            return self.options[self.selected_index]
        return None

    @property
    def selected_id(self) -> str | None:
        option = self.selected_option
        return option.id if option is not None else None

    @property
    def display_label(self) -> str:
        if self.editable and self.query:
            return self.query
        option = self.selected_option
        return option.label if option is not None else self.placeholder

    @property
    def filtered_options(self) -> list[DropdownOption]:
        if not self.editable or not self.query:
            return list(self.options)
        needle = self.query.casefold()
        return [option for option in self.options if needle in option.label.casefold()]

    @property
    def visible_options(self) -> list[DropdownOption]:
        options = self.filtered_options
        start = self._clamped_scroll_offset(len(options))
        end = start + self.visible_item_count(len(options))
        return options[start:end]

    def open(self, x: float, y: float) -> None:
        """Open option popup at position."""

        self.scroll_offset = self._clamped_scroll_offset(len(self.filtered_options))
        self.popup.open((float(x), float(y), self.width, self.preferred_height()))

    def close(self) -> None:
        self.popup.close()

    def toggle(self, x: float = 0.0, y: float = 0.0) -> None:
        if self.popup.visible:
            self.close()
        else:
            self.open(x, y)

    def preferred_height(self) -> float:
        return max(0.0, self.visible_item_count(len(self.filtered_options)) * self.item_height)

    def visible_item_count(self, option_count: int | None = None) -> int:
        count = len(self.filtered_options) if option_count is None else max(0, int(option_count))
        if self.max_visible_items is None:
            return count
        return min(count, max(0, int(self.max_visible_items)))

    def scroll_by(self, delta: int) -> int:
        """Scroll visible option window and return clamped offset."""

        self.scroll_offset = self._clamped_scroll_offset(len(self.filtered_options), self.scroll_offset + int(delta))
        return self.scroll_offset

    def set_query(self, query: str) -> None:
        if self.editable:
            self.query = str(query)
            self.scroll_offset = self._clamped_scroll_offset(len(self.filtered_options))

    def option_at(self, x: float, y: float) -> DropdownOption | None:
        if not self.popup.contains_point(x, y) or self.item_height <= 0:
            return None
        _, py, _, _ = self.popup.rect
        index = self.scroll_offset + int((y - py) // self.item_height)
        options = self.filtered_options
        if 0 <= index < len(options):
            return options[index]
        return None

    def select_index(self, index: int) -> bool:
        """Select enabled option by source index."""

        if not (0 <= index < len(self.options)):
            return False
        if not self.options[index].enabled:
            return False
        self.selected_index = index
        self.query = ""
        self.close()
        return True

    def select_id(self, option_id: str) -> bool:
        for idx, option in enumerate(self.options):
            if option.id == option_id:
                return self.select_index(idx)
        return False

    def select_at(self, x: float, y: float) -> str | None:
        """Select enabled option under point and return its id."""

        option = self.option_at(x, y)
        if option is None or not option.enabled:
            return None
        if self.select_id(option.id):
            return option.id
        return None

    def to_dict(self) -> dict[str, object]:
        """Serialize dropdown state to JSON-compatible primitives."""

        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "DropdownModel":
        """Build dropdown state from a `to_dict()` payload."""

        payload: dict[str, Any] = dict(data)
        payload["options"] = [DropdownOption(**dict(option)) for option in payload.get("options", [])]
        popup = payload.get("popup")
        payload["popup"] = PopupModel.from_dict(popup) if isinstance(popup, dict) else PopupModel()
        return cls(**payload)

    def _clamped_scroll_offset(self, option_count: int, value: int | None = None) -> int:
        offset = self.scroll_offset if value is None else value
        visible = self.visible_item_count(option_count)
        max_offset = max(0, option_count - visible)
        return max(0, min(int(offset), max_offset))


@dataclass
class ComboBoxModel(DropdownModel):
    """Editable dropdown model for combobox-style controls."""

    editable: bool = True
