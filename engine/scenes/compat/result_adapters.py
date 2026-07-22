"""Translate discriminated scene results for legacy bool/optional callers."""

from __future__ import annotations

from typing import TypeVar

from engine.scenes.result import Err, Result

T = TypeVar("T")


class LegacyResultAdapter:
    @staticmethod
    def to_bool(result: Result[object]) -> bool:
        return not isinstance(result, Err)

    @staticmethod
    def to_optional(result: Result[T]) -> T | None:
        return None if isinstance(result, Err) else result.value


__all__ = ["LegacyResultAdapter"]
