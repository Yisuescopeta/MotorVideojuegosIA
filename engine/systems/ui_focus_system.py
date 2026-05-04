"""
engine/systems/ui_focus_system.py - UI focus management.

Gestiona foco entre elementos UI con RectTransform + focusable=True.
Emite eventos focus_entered / focus_exited via EventBus.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from engine.events.event_bus import EventBus


class UIFocusSystem:
    """Gestiona el foco de UI: focused_entity, navegacion, eventos focus."""

    def __init__(self, event_bus: Optional[EventBus] = None) -> None:
        self._event_bus = event_bus
        self._focused_entity_id: int | None = None

    def set_focus(self, entity_id: int | None) -> None:
        old = self._focused_entity_id
        if old == entity_id:
            return
        self._focused_entity_id = entity_id
        if self._event_bus:
            if old is not None:
                self._event_bus.emit("focus_exited", {"entity_id": old})
            if entity_id is not None:
                self._event_bus.emit("focus_entered", {"entity_id": entity_id})

    def get_focused_entity(self) -> int | None:
        return self._focused_entity_id

    def clear_focus(self) -> None:
        self.set_focus(None)
