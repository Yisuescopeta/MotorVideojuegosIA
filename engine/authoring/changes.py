from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from typing import Any


@dataclass
class Change:
    kind: str
    entity: str = ""
    component: str = ""
    field: str = ""
    value: Any = None
    data: dict[str, Any] = dataclass_field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "kind": self.kind,
            "entity": self.entity,
            "component": self.component,
            "field": self.field,
            "value": self.value,
            "data": self.data,
        }
        return {key: value for key, value in payload.items() if value not in ("", None, {})}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Change":
        return cls(
            kind=str(payload.get("kind", "")),
            entity=str(payload.get("entity", "")),
            component=str(payload.get("component", "")),
            field=str(payload.get("field", "")),
            value=payload.get("value"),
            data=dict(payload.get("data", {})),
        )
