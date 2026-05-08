"""PhysicsMaterial — friction, bounce, and surface properties.

Adaptado de Godot PhysicsMaterial. Define propiedades de interacción entre
superficies: fricción (friction), rebote (bounce), rugosidad (rough) y
absorción (absorbent).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

_physics_material_cache: dict[str, PhysicsMaterial | None] = {}


class PhysicsMaterialData(TypedDict, total=False):
    """Typed representation of a PhysicsMaterial serialized payload.
    
    Keys are optional to support legacy payloads missing fields.
    schema_version may be absent in pre-v1 payloads.
    """

    resource_id: str
    resource_name: str
    friction: float
    bounce: float
    rough: bool
    absorbent: bool
    schema_version: int


@dataclass
class PhysicsMaterial:
    """Physics material defining surface interaction properties.

    Attributes:
        resource_id: Unique identifier for the resource.
        resource_name: Human-readable name.
        friction: Surface friction (0 = ice, 1 = normal).
        bounce: Restitution coefficient (0 = no bounce, 1 = perfect bounce).
        rough: If True, friction becomes infinite (never slide).
        absorbent: If True, bounce is always 0 regardless of bounce value.
        schema_version: Serialization format version (1 = current).
    """

    resource_id: str = ""
    resource_name: str = "default"

    friction: float = 1.0
    bounce: float = 0.0
    rough: bool = False
    absorbent: bool = False
    schema_version: int = 1

    def get_effective_friction(self) -> float:
        """Return effective friction: infinite if rough, else friction value."""
        if self.rough:
            return float('inf')
        return self.friction

    def get_effective_bounce(self) -> float:
        """Return effective bounce: 0 if absorbent, else bounce value."""
        if self.absorbent:
            return 0.0
        return self.bounce

    def to_dict(self) -> PhysicsMaterialData:
        return {
            "resource_id": self.resource_id,
            "resource_name": self.resource_name,
            "friction": self.friction,
            "bounce": self.bounce,
            "rough": self.rough,
            "absorbent": self.absorbent,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, data: PhysicsMaterialData) -> PhysicsMaterial:
        return cls(
            resource_id=str(data.get("resource_id", "")),
            resource_name=str(data.get("resource_name", "default")),
            friction=float(data.get("friction", 1.0)),
            bounce=float(data.get("bounce", 0.0)),
            rough=bool(data.get("rough", False)),
            absorbent=bool(data.get("absorbent", False)),
            schema_version=int(data.get("schema_version", 1)),
        )


def load_physics_material(path_str: str) -> PhysicsMaterial | None:
    """Load a PhysicsMaterial from a JSON file path.

    Supports absolute and relative paths. Uses pathlib + json.loads only —
    no shell, no eval. Returns None if path is empty, file doesn't exist,
    JSON is invalid, or data doesn't match PhysicsMaterial schema.

    Results are cached: repeated loads for the same resolved path return
    the cached instance (or cached None for failed loads).
    """
    if not path_str or not path_str.strip():
        return None

    resolved = Path(path_str)
    if not resolved.is_absolute():
        resolved = resolved.resolve()

    cache_key = str(resolved)
    if cache_key in _physics_material_cache:
        return _physics_material_cache[cache_key]

    try:
        raw = resolved.read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            _physics_material_cache[cache_key] = None
            return None
        mat = PhysicsMaterial.from_dict(data)
        _physics_material_cache[cache_key] = mat
        return mat
    except (OSError, ValueError, TypeError):
        _physics_material_cache[cache_key] = None
        return None


def clear_physics_material_cache() -> None:
    """Clear the material cache (useful for tests)."""
    _physics_material_cache.clear()
