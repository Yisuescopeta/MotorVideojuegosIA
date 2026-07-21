"""Canonical evidence for the Scene -> EditWorld projection."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from engine.ecs.world import World
    from engine.scenes.scene import Scene


class ProjectionFingerprintError(ValueError):
    """Raised when a projection boundary cannot be canonicalized safely."""


@dataclass(frozen=True, slots=True)
class ProjectionIntegrityEvidence:
    scene_revision: int
    projected_world_version: int
    canonical_fingerprint: str
    projection_schema_version: int


class AuthoringProjectionFingerprintService:
    """Build deterministic fingerprints for the persistent projection domain."""

    PROJECTION_SCHEMA_VERSION = 1
    FLOAT_PRECISION = 9

    def __init__(self, project_scene_to_world: Callable[["Scene"], "World"] | None = None) -> None:
        self._project_scene_to_world = project_scene_to_world

    def build_evidence(
        self,
        scene: "Scene",
        world: "World",
        *,
        scene_revision: int,
    ) -> ProjectionIntegrityEvidence:
        return ProjectionIntegrityEvidence(
            scene_revision=scene_revision,
            projected_world_version=world.version,
            canonical_fingerprint=self.fingerprint_scene(scene),
            projection_schema_version=self.PROJECTION_SCHEMA_VERSION,
        )

    def fingerprint_scene(self, scene: "Scene") -> str:
        if self._project_scene_to_world is not None:
            return self.fingerprint_payload(
                self.world_payload(scene, self._project_scene_to_world(scene))
            )
        return self.fingerprint_payload(self.scene_payload(scene))

    def fingerprint_world(self, scene: "Scene", world: "World") -> str:
        return self.fingerprint_payload(self.world_payload(scene, world))

    def scene_matches_world(self, scene: "Scene", world: "World") -> bool:
        return self.fingerprint_scene(scene) == self.fingerprint_world(scene, world)

    def scene_payload(self, scene: "Scene") -> dict[str, Any]:
        snapshot = scene.to_snapshot_dict()
        return self._canonicalize_domain_payload(
            entities=snapshot.get("entities", []),
            rules=snapshot.get("rules", []),
            feature_metadata=snapshot.get("feature_metadata", {}),
        )

    def world_payload(self, scene: "Scene", world: "World") -> dict[str, Any]:
        snapshot = world.serialize()
        entities = snapshot.get("entities", [])
        if not isinstance(entities, list):
            raise ProjectionFingerprintError("World snapshot entities must be a list")
        entities_with_ids = []
        for index, entity_payload in enumerate(entities):
            if not isinstance(entity_payload, dict):
                raise ProjectionFingerprintError(f"World snapshot entity {index} must be an object")
            entity_name = entity_payload.get("name")
            if not isinstance(entity_name, str) or not entity_name.strip():
                raise ProjectionFingerprintError(f"World snapshot entity {index} has an invalid name")
            entity = world.get_entity_by_name(entity_name)
            if entity is None:
                raise ProjectionFingerprintError(
                    f"World snapshot entity '{entity_name}' is missing from its source World"
                )
            enriched = dict(entity_payload)
            serialized_id = entity.serialized_id
            if serialized_id:
                enriched["id"] = serialized_id
            else:
                enriched.pop("id", None)
            entities_with_ids.append(enriched)
        return self._canonicalize_domain_payload(
            entities=entities_with_ids,
            rules=scene.rules_data,
            feature_metadata=world.feature_metadata,
        )

    @classmethod
    def fingerprint_payload(cls, payload: dict[str, Any]) -> str:
        canonical = cls._canonicalize(payload)
        try:
            serialized = json.dumps(
                canonical,
                ensure_ascii=True,
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            )
        except (TypeError, ValueError) as exc:
            raise ProjectionFingerprintError(f"Projection payload is not canonical JSON: {exc}") from exc
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @classmethod
    def _canonicalize_domain_payload(
        cls,
        *,
        entities: Any,
        rules: Any,
        feature_metadata: Any,
    ) -> dict[str, Any]:
        return cls._canonicalize(
            {
                "entities": entities,
                "rules": rules,
                "feature_metadata": feature_metadata,
            }
        )

    @classmethod
    def _canonicalize(cls, value: Any) -> Any:
        if value is None or isinstance(value, (bool, int, str)):
            return value
        if isinstance(value, float):
            if not math.isfinite(value):
                raise ProjectionFingerprintError("Projection payload contains a non-finite float")
            return round(value, cls.FLOAT_PRECISION)
        if isinstance(value, dict):
            return {
                str(key): cls._canonicalize(item)
                for key, item in sorted(value.items(), key=lambda item: str(item[0]))
            }
        if isinstance(value, (list, tuple)):
            return [cls._canonicalize(item) for item in value]
        raise ProjectionFingerprintError(
            f"Projection payload contains unsupported value type {type(value).__name__}"
        )
