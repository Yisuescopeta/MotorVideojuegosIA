"""Temporary name-first compatibility boundary for scene callers."""

from __future__ import annotations

from dataclasses import dataclass

from engine.scenes.refs import EntityRef, OpenSceneRef
from engine.scenes.result import CommandError, CommandErrorCode, Err, Ok, Result


@dataclass
class NameFirstResolutionMetrics:
    """Process-local counters used to retire name-first consumers."""

    calls: int = 0
    resolved: int = 0
    not_found: int = 0
    ambiguous: int = 0

    def snapshot(self) -> dict[str, int]:
        return {
            "calls": self.calls,
            "resolved": self.resolved,
            "not_found": self.not_found,
            "ambiguous": self.ambiguous,
        }


class NameFirstSceneFacade:
    """Resolve a legacy entity name once, then expose only its stable ref."""

    def __init__(
        self,
        scene: object,
        scene_ref: OpenSceneRef,
        *,
        metrics: NameFirstResolutionMetrics | None = None,
    ) -> None:
        self._scene = scene
        self._scene_ref = scene_ref
        self._metrics = metrics or NameFirstResolutionMetrics()

    @property
    def metrics(self) -> NameFirstResolutionMetrics:
        return self._metrics

    def resolve_entity(self, entity_name: str) -> Result[EntityRef]:
        self._metrics.calls += 1
        normalized_name = str(entity_name or "").strip()
        if not normalized_name:
            self._metrics.not_found += 1
            return Err(
                CommandError(
                    CommandErrorCode.NOT_FOUND,
                    "Entity name must be non-empty.",
                    field="entity_name",
                )
            )

        views = tuple(
            view
            for view in self._scene.list_entity_views()
            if view.name == normalized_name
        )
        if not views:
            self._metrics.not_found += 1
            return Err(
                CommandError(
                    CommandErrorCode.NOT_FOUND,
                    f"Entity '{normalized_name}' was not found.",
                    field="entity_name",
                )
            )
        if len(views) > 1:
            self._metrics.ambiguous += 1
            return Err(
                CommandError(
                    CommandErrorCode.VALIDATION_FAILED,
                    f"Entity name '{normalized_name}' is ambiguous.",
                    technical_details="Name-first compatibility requires exactly one entity.",
                    field="entity_name",
                )
            )

        self._metrics.resolved += 1
        return Ok(EntityRef(self._scene_ref, views[0].entity_id))


__all__ = ["NameFirstResolutionMetrics", "NameFirstSceneFacade"]
