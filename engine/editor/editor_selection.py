from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(slots=True)
class EditorSelectionState:
    """Ephemeral editor selection cache shared across editor surfaces."""

    entity_name: Optional[str] = None

    @staticmethod
    def normalize(entity_name: Any) -> Optional[str]:
        if entity_name is None:
            return None
        normalized = str(entity_name).strip()
        return normalized or None

    def set(self, entity_name: Any) -> Optional[str]:
        self.entity_name = self.normalize(entity_name)
        return self.entity_name

    def clear(self) -> None:
        self.entity_name = None

    def sync_from_world(self, world: Any) -> Optional[str]:
        if world is None:
            return self.entity_name
        return self.set(getattr(world, "selected_entity_name", None))

    def apply_to_world(self, world: Any) -> Optional[str]:
        if world is not None:
            world.selected_entity_name = self.entity_name
        return self.entity_name
