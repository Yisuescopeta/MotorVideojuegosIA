"""Discriminated results for new scene application contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Generic, TypeAlias, TypeVar

from engine.scenes.refs import EntityRef

T = TypeVar("T")


class CommandErrorCode(str, Enum):
    NOT_FOUND = "NOT_FOUND"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    CONFLICT = "CONFLICT"
    PROJECTION_DIVERGED = "PROJECTION_DIVERGED"
    PREVIEW_ACTIVE = "PREVIEW_ACTIVE"
    PERSISTENCE_FAILED = "PERSISTENCE_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


@dataclass(frozen=True, slots=True)
class CommandError:
    code: CommandErrorCode
    user_message: str
    technical_details: str | None = None
    field: str | None = None


@dataclass(frozen=True, slots=True)
class MutationMetadata:
    changed_entities: tuple[EntityRef, ...] = ()
    history_entry_id: str | None = None
    scene_revision: int | None = None


@dataclass(frozen=True, slots=True)
class Ok(Generic[T]):
    value: T
    metadata: MutationMetadata = field(default_factory=MutationMetadata)


@dataclass(frozen=True, slots=True)
class Err:
    error: CommandError


Result: TypeAlias = Ok[T] | Err


__all__ = [
    "CommandError",
    "CommandErrorCode",
    "Err",
    "MutationMetadata",
    "Ok",
    "Result",
]
