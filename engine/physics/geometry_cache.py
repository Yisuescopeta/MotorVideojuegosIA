from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable, Hashable
from dataclasses import dataclass, field
from typing import Any, TypeVar

from engine.components.collider import Collider
from engine.components.collision_shape_set_2d import CollisionShape2DDef
from engine.components.transform import Transform

AABB = tuple[float, float, float, float]
T = TypeVar("T")


def _points_signature(points: Any) -> tuple[tuple[float, ...], ...]:
    return tuple(tuple(float(value) for value in point) for point in (points or ()))


def collider_geometry_signature(collider: Collider) -> tuple[Any, ...]:
    return (
        bool(collider.enabled),
        bool(collider.is_trigger),
        str(collider.shape_type or "box"),
        float(collider.width),
        float(collider.height),
        float(collider.radius),
        float(collider.capsule_height),
        float(collider.offset_x),
        float(collider.offset_y),
        _points_signature(collider.points),
    )


def shape_def_geometry_signature(shape: CollisionShape2DDef) -> tuple[Any, ...]:
    return (
        bool(shape.disabled),
        bool(shape.is_trigger),
        str(shape.shape_type or "box"),
        float(shape.width),
        float(shape.height),
        float(shape.radius),
        float(shape.capsule_height),
        float(shape.offset_x),
        float(shape.offset_y),
        _points_signature(shape.points),
    )


def shape_set_geometry_signature(shapes: list[CollisionShape2DDef]) -> tuple[Any, ...]:
    return tuple(shape_def_geometry_signature(shape) for shape in shapes)


def transform_pose_signature(transform: Transform) -> tuple[Any, ...]:
    x = float(transform.x)
    y = float(transform.y)
    return (
        x,
        y,
        float(transform.rotation),
        float(transform.scale_x),
        float(transform.scale_y),
        bool(getattr(transform, "enabled", True)),
        int(getattr(transform, "_global_cache_revision", 0)),
    )


@dataclass
class _CacheBucket:
    geometry_signature: tuple[Any, ...]
    values: OrderedDict[tuple[Any, ...], Any] = field(default_factory=OrderedDict)
    last_seen_frame: int = 0


class VersionedGeometryCache:
    """Runtime cache keyed by geometry version with two retained poses per shape."""

    def __init__(self, *, max_positions: int = 2, stale_after_frames: int = 2) -> None:
        self._max_positions = max(1, int(max_positions))
        self._stale_after_frames = max(1, int(stale_after_frames))
        self._world_token: int | None = None
        self._frame = 0
        self._aabb_buckets: dict[Hashable, _CacheBucket] = {}
        self._shape_buckets: dict[Hashable, _CacheBucket] = {}

    def begin_frame(self, world: object) -> None:
        world_token = id(world)
        if world_token != self._world_token:
            self.clear()
            self._world_token = world_token
        self._frame += 1
        minimum_frame = self._frame - self._stale_after_frames
        self._prune(self._aabb_buckets, minimum_frame)
        self._prune(self._shape_buckets, minimum_frame)

    def clear(self) -> None:
        self._aabb_buckets.clear()
        self._shape_buckets.clear()
        self._frame = 0

    def invalidate(self, key: Hashable) -> None:
        self._aabb_buckets.pop(key, None)
        self._shape_buckets.pop(key, None)

    def get_aabb(
        self,
        key: Hashable,
        geometry_signature: tuple[Any, ...],
        pose_signature: tuple[Any, ...],
        builder: Callable[[], AABB],
    ) -> tuple[AABB, bool]:
        value, hit = self._get(
            self._aabb_buckets,
            key,
            geometry_signature,
            pose_signature,
            builder,
        )
        return value, hit

    def get_shape(
        self,
        key: Hashable,
        geometry_signature: tuple[Any, ...],
        pose_signature: tuple[Any, ...],
        builder: Callable[[], T],
    ) -> tuple[T, bool]:
        value, hit = self._get(
            self._shape_buckets,
            key,
            geometry_signature,
            pose_signature,
            builder,
        )
        return value, hit

    @property
    def aabb_entry_count(self) -> int:
        return sum(len(bucket.values) for bucket in self._aabb_buckets.values())

    @property
    def shape_entry_count(self) -> int:
        return sum(len(bucket.values) for bucket in self._shape_buckets.values())

    def _get(
        self,
        buckets: dict[Hashable, _CacheBucket],
        key: Hashable,
        geometry_signature: tuple[Any, ...],
        pose_signature: tuple[Any, ...],
        builder: Callable[[], T],
    ) -> tuple[T, bool]:
        bucket = buckets.get(key)
        if bucket is None or bucket.geometry_signature != geometry_signature:
            bucket = _CacheBucket(geometry_signature=geometry_signature)
            buckets[key] = bucket
        bucket.last_seen_frame = self._frame

        if pose_signature in bucket.values:
            cached = bucket.values.pop(pose_signature)
            bucket.values[pose_signature] = cached
            return cached, True

        value = builder()
        bucket.values[pose_signature] = value
        while len(bucket.values) > self._max_positions:
            bucket.values.popitem(last=False)
        return value, False

    @staticmethod
    def _prune(buckets: dict[Hashable, _CacheBucket], minimum_frame: int) -> None:
        stale_keys = [
            key
            for key, bucket in buckets.items()
            if bucket.last_seen_frame < minimum_frame
        ]
        for key in stale_keys:
            del buckets[key]
