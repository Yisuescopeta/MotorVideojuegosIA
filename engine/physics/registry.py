from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from engine.physics.backend import PhysicsBackend, PhysicsBackendInfo, PhysicsBackendSelection

LEGACY_PHYSICS_BACKEND = "legacy_aabb"


@dataclass
class _PhysicsBackendRecord:
    name: str
    backend: Optional[PhysicsBackend] = None
    unavailable_reason: Optional[str] = None

    @property
    def available(self) -> bool:
        return self.backend is not None

    def to_info(self) -> PhysicsBackendInfo:
        return {
            "name": self.name,
            "available": self.available,
            "unavailable_reason": self.unavailable_reason,
        }


@dataclass
class ResolvedPhysicsBackend:
    backend: Optional[PhysicsBackend]
    selection: PhysicsBackendSelection

    @property
    def requested_backend(self) -> str:
        return str(self.selection["requested_backend"])

    @property
    def effective_backend(self) -> Optional[str]:
        value = self.selection.get("effective_backend")
        return None if value is None else str(value)


class PhysicsBackendRegistry:
    """Catalogo y resolvedor central para backends de fisica."""

    def __init__(self, default_backend_name: str = LEGACY_PHYSICS_BACKEND) -> None:
        self._default_backend_name = str(default_backend_name or LEGACY_PHYSICS_BACKEND).strip() or LEGACY_PHYSICS_BACKEND
        self._records: dict[str, _PhysicsBackendRecord] = {}

    @property
    def default_backend_name(self) -> str:
        return self._default_backend_name

    def register_backend(self, backend: PhysicsBackend, backend_name: Optional[str] = None) -> None:
        normalized_name = self._normalize_backend_name(backend_name or getattr(backend, "backend_name", ""))
        self._records[normalized_name] = _PhysicsBackendRecord(
            name=normalized_name,
            backend=backend,
            unavailable_reason=None,
        )

    def mark_backend_unavailable(self, backend_name: str, reason: Optional[str] = None) -> None:
        normalized_name = self._normalize_backend_name(backend_name)
        normalized_reason = str(reason or "").strip() or None
        record = self._records.get(normalized_name)
        if record is None:
            self._records[normalized_name] = _PhysicsBackendRecord(
                name=normalized_name,
                backend=None,
                unavailable_reason=normalized_reason,
            )
            return
        record.backend = None
        record.unavailable_reason = normalized_reason

    def knows_backend(self, backend_name: str) -> bool:
        return self._normalize_backend_name(backend_name) in self._records

    def has_available_backend(self, backend_name: str) -> bool:
        record = self._records.get(self._normalize_backend_name(backend_name))
        return bool(record is not None and record.available)

    def get_backend(self, backend_name: str) -> Optional[PhysicsBackend]:
        record = self._records.get(self._normalize_backend_name(backend_name))
        return None if record is None else record.backend

    def list_backends(self) -> list[PhysicsBackendInfo]:
        return [self._records[name].to_info() for name in sorted(self._records)]

    def iter_available_backends(self) -> list[PhysicsBackend]:
        return [record.backend for _, record in sorted(self._records.items()) if record.backend is not None]

    def resolve(self, world: Any = None, *, default_backend_name: Optional[str] = None) -> ResolvedPhysicsBackend:
        requested_backend = self._requested_backend_name(world, default_backend_name=default_backend_name)
        requested_record = self._records.get(requested_backend)
        if requested_record is not None and requested_record.available:
            return ResolvedPhysicsBackend(
                backend=requested_record.backend,
                selection={
                    "requested_backend": requested_backend,
                    "effective_backend": requested_backend,
                    "used_fallback": False,
                    "fallback_reason": None,
                    "unavailable_reason": None,
                },
            )

        unavailable_reason = self._build_unavailable_reason(requested_backend, requested_record)
        fallback_record = self._records.get(LEGACY_PHYSICS_BACKEND)
        if requested_backend != LEGACY_PHYSICS_BACKEND and fallback_record is not None and fallback_record.available:
            return ResolvedPhysicsBackend(
                backend=fallback_record.backend,
                selection={
                    "requested_backend": requested_backend,
                    "effective_backend": LEGACY_PHYSICS_BACKEND,
                    "used_fallback": True,
                    "fallback_reason": f"Requested physics backend '{requested_backend}' unavailable; using '{LEGACY_PHYSICS_BACKEND}'",
                    "unavailable_reason": unavailable_reason,
                },
            )

        return ResolvedPhysicsBackend(
            backend=None,
            selection={
                "requested_backend": requested_backend,
                "effective_backend": None,
                "used_fallback": False,
                "fallback_reason": None,
                "unavailable_reason": unavailable_reason,
            },
        )

    def _requested_backend_name(self, world: Any = None, *, default_backend_name: Optional[str] = None) -> str:
        fallback = self._normalize_backend_name(default_backend_name or self._default_backend_name)
        metadata = getattr(world, "feature_metadata", {}) if world is not None else {}
        if not isinstance(metadata, dict):
            return fallback
        physics_2d = metadata.get("physics_2d", {})
        if not isinstance(physics_2d, dict):
            return fallback
        requested = str(physics_2d.get("backend", "") or "").strip()
        return self._normalize_backend_name(requested or fallback)

    def _build_unavailable_reason(
        self,
        requested_backend: str,
        requested_record: Optional[_PhysicsBackendRecord],
    ) -> str:
        if requested_record is None:
            return f"Physics backend '{requested_backend}' is not registered in this runtime"
        if requested_record.unavailable_reason:
            return requested_record.unavailable_reason
        return f"Physics backend '{requested_backend}' is not available in this runtime"

    def _normalize_backend_name(self, backend_name: str) -> str:
        return str(backend_name or "").strip() or self._default_backend_name
