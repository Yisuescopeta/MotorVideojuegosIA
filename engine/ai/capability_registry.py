"""
engine/ai/capability_registry.py - Central AI-facing capability registry for MotorVideojuegosIA

Single source of truth for:
- motor_ai.json generation
- CLI headless capabilities
- Structured help for AI assistants

Naming conventions:
- Capability IDs: ``scope:action`` (lowercase, colon-separated)
  Examples: ``scene:load``, ``entity:create``, ``asset:slice_grid``
- CLI commands: ``motor <scope> <action>`` (snake_case for multi-word actions)
  Examples: ``motor scene load``, ``motor entity create``
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class CapabilityParam:
    """Parameter description for a capability example or API method."""
    name: str
    type: str
    description: str = ""
    required: bool = True
    default: Any = None


@dataclass(frozen=True)
class CapabilityExample:
    """Minimal working example demonstrating a capability."""
    description: str
    api_calls: List[Dict[str, Any]]
    expected_outcome: str = ""


@dataclass(frozen=True)
class Capability:
    """
    Describes a single operational capability of the motor.

    A capability represents a coherent unit of functionality that an AI assistant
    can invoke, spanning one or more API methods across potentially multiple subsystems.

    Status:
        - "implemented": Fully implemented and available for use
        - "planned": Planned for future implementation (not yet available)
        - "deprecated": Deprecated, will be removed in future versions
    """
    id: str
    summary: str
    mode: str
    api_methods: List[str]
    cli_command: str
    example: CapabilityExample
    notes: str = ""
    tags: List[str] = field(default_factory=list)
    status: str = "implemented"  # "implemented" | "planned" | "deprecated"

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("Capability id cannot be empty")
        if ":" not in self.id:
            raise ValueError(f"Capability id must use 'scope:action' format, got {self.id!r}")
        if self.mode not in {"edit", "play", "both"}:
            raise ValueError(f"Capability mode must be 'edit', 'play', or 'both', got {self.mode!r}")
        if self.status not in {"implemented", "planned", "deprecated"}:
            raise ValueError(f"Capability status must be 'implemented', 'planned', or 'deprecated', got {self.status!r}")
        if not isinstance(self.api_methods, list) or not self.api_methods:
            raise ValueError("Capability must have at least one api_method")
        if not isinstance(self.example, CapabilityExample):
            raise ValueError("Capability must have a CapabilityExample")


@dataclass
class CapabilityRegistry:
    """
    Registry of all AI-facing capabilities.
    """
    schema_version: int = 1
    engine_name: str = "MotorVideojuegosIA"
    engine_version: str = ""
    _capabilities: Dict[str, Capability] = field(default_factory=dict)
    _index_by_mode: Dict[str, List[str]] = field(default_factory=lambda: {"edit": [], "play": [], "both": []})

    def register(self, capability: Capability) -> None:
        if capability.id in self._capabilities:
            raise ValueError(f"Duplicate capability id: {capability.id}")
        self._capabilities[capability.id] = capability
        self._index_by_mode[capability.mode].append(capability.id)

    def get(self, capability_id: str) -> Optional[Capability]:
        return self._capabilities.get(capability_id)

    def list_all(self) -> List[Capability]:
        return list(self._capabilities.values())

    def list_by_mode(self, mode: str) -> List[Capability]:
        if mode not in self._index_by_mode:
            return []
        return [self._capabilities[cid] for cid in self._index_by_mode[mode]]

    def list_by_tag(self, tag: str) -> List[Capability]:
        return [cap for cap in self._capabilities.values() if tag in cap.tags]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "engine": {
                "name": self.engine_name,
                "version": self.engine_version,
            },
            "capabilities": [
                {
                    "id": cap.id,
                    "summary": cap.summary,
                    "mode": cap.mode,
                    "status": cap.status,
                    "api_methods": cap.api_methods,
                    "cli_command": cap.cli_command,
                    "example": {
                        "description": cap.example.description,
                        "api_calls": cap.example.api_calls,
                        "expected_outcome": cap.example.expected_outcome,
                    },
                    "notes": cap.notes,
                    "tags": cap.tags,
                }
                for cap in sorted(self._capabilities.values(), key=lambda c: c.id)
            ],
        }

    def list_implemented(self) -> List[Capability]:
        """Return only implemented capabilities."""
        return [cap for cap in self._capabilities.values() if cap.status == "implemented"]

    def list_planned(self) -> List[Capability]:
        """Return only planned capabilities."""
        return [cap for cap in self._capabilities.values() if cap.status == "planned"]

    def list_deprecated(self) -> List[Capability]:
        """Return only deprecated capabilities."""
        return [cap for cap in self._capabilities.values() if cap.status == "deprecated"]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CapabilityRegistry":
        registry = cls(
            schema_version=int(data.get("schema_version", 1)),
            engine_name=str(data.get("engine_name", data.get("engine", {}).get("name", "MotorVideojuegosIA"))),
            engine_version=str(data.get("engine_version", data.get("engine", {}).get("version", ""))),
        )
        for cap_data in data.get("capabilities", []):
            example = CapabilityExample(
                description=str(cap_data.get("example", {}).get("description", "")),
                api_calls=cap_data.get("example", {}).get("api_calls", []),
                expected_outcome=str(cap_data.get("example", {}).get("expected_outcome", "")),
            )
            capability = Capability(
                id=str(cap_data["id"]),
                summary=str(cap_data["summary"]),
                mode=str(cap_data["mode"]),
                api_methods=list(cap_data["api_methods"]),
                cli_command=str(cap_data["cli_command"]),
                example=example,
                notes=str(cap_data.get("notes", "")),
                tags=list(cap_data.get("tags", [])),
                status=str(cap_data.get("status", "implemented")),
            )
            registry.register(capability)
        return registry

    def validate(self) -> List[str]:
        """Validate registry contract: unique ids, required fields, consistent modes."""
        errors: List[str] = []

        if self.schema_version < 1:
            errors.append("schema_version must be >= 1")

        ids_seen: set[str] = set()
        for cap in self._capabilities.values():
            if cap.id in ids_seen:
                errors.append(f"Duplicate capability id: {cap.id}")
            ids_seen.add(cap.id)

            if not cap.id.strip():
                errors.append("Empty capability id found")
            if ":" not in cap.id:
                errors.append(f"Capability id missing scope:action format: {cap.id}")
            if cap.mode not in {"edit", "play", "both"}:
                errors.append(f"Invalid mode for {cap.id}: {cap.mode}")
            if not cap.api_methods:
                errors.append(f"Capability {cap.id} has no api_methods")
            if not isinstance(cap.api_methods, list):
                errors.append(f"Capability {cap.id} api_methods is not a list")
            if not isinstance(cap.example, CapabilityExample):
                errors.append(f"Capability {cap.id} missing valid example")

        return errors
