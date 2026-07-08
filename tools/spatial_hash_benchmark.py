from __future__ import annotations

import argparse
import json
import math
import platform
import statistics
import time
from pathlib import Path
from typing import Any, Callable

from engine.physics.spatial_hash import AABB, SpatialHash2D

SPATIAL_HASH_BENCHMARK_VERSION = 1


def _elapsed_ms(start: float) -> float:
    return (time.perf_counter() - start) * 1000.0


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = max(0, min(len(ordered) - 1, math.ceil(percentile * len(ordered)) - 1))
    return ordered[index]


def _normalize_count(value: int, *, minimum: int) -> int:
    return max(minimum, int(value))


def _normalize_float(value: float, *, minimum: float) -> float:
    return max(minimum, float(value))


def _mix_checksum(current: int, value: int) -> int:
    return ((current * 1315423911) ^ int(value)) & 0xFFFFFFFFFFFFFFFF


def _set_checksum(entity_ids: set[int]) -> int:
    checksum = len(entity_ids)
    for entity_id in sorted(entity_ids):
        checksum = _mix_checksum(checksum, entity_id)
    return checksum


def _measure_repeated(callback: Callable[[], int], *, warmup: int, repeats: int) -> dict[str, Any]:
    for _ in range(max(0, int(warmup))):
        callback()
    samples: list[float] = []
    checksums: list[int] = []
    for _ in range(max(1, int(repeats))):
        started = time.perf_counter()
        checksum = int(callback())
        samples.append(_elapsed_ms(started))
        checksums.append(checksum)
    return {
        "ms": statistics.median(samples),
        "median_ms": statistics.median(samples),
        "p95_ms": _percentile(samples, 0.95),
        "samples_ms": samples,
        "checksum": checksums[-1] if checksums else 0,
        "stable_checksum": len(set(checksums)) <= 1,
    }


def _build_entries(
    *,
    entity_count: int,
    columns: int,
    spacing: float,
    aabb_size: float,
    oversized_count: int,
) -> list[tuple[int, AABB]]:
    normalized_columns = _normalize_count(columns, minimum=1)
    normalized_spacing = _normalize_float(spacing, minimum=1.0)
    normalized_aabb_size = _normalize_float(aabb_size, minimum=1.0)
    rows = max(1, math.ceil(max(1, entity_count) / normalized_columns))
    half_columns = normalized_columns / 2.0
    half_rows = rows / 2.0

    entries: list[tuple[int, AABB]] = []
    for index in range(max(0, int(entity_count))):
        width = normalized_aabb_size + float(index % 5)
        height = normalized_aabb_size + float((index * 3) % 7)
        x = (float(index % normalized_columns) - half_columns) * normalized_spacing
        y = (float(index // normalized_columns) - half_rows) * normalized_spacing
        entries.append((index + 1, (x, y, x + width, y + height)))

    for index in range(max(0, int(oversized_count))):
        extent = normalized_spacing * float(max(normalized_columns, rows, 1) * 4)
        entity_id = entity_count + index + 1
        entries.append((entity_id, (-extent, -extent, extent, extent)))

    return entries


def _build_queries(*, query_count: int, columns: int, rows: int, spacing: float) -> list[AABB]:
    normalized_columns = _normalize_count(columns, minimum=1)
    normalized_rows = _normalize_count(rows, minimum=1)
    normalized_spacing = _normalize_float(spacing, minimum=1.0)
    half_columns = normalized_columns / 2.0
    half_rows = normalized_rows / 2.0

    queries: list[AABB] = []
    for index in range(max(0, int(query_count))):
        column = (index * 37) % normalized_columns
        row = (index * 17) % normalized_rows
        left = (float(column) - half_columns) * normalized_spacing - normalized_spacing * 0.5
        top = (float(row) - half_rows) * normalized_spacing - normalized_spacing * 0.5
        queries.append((left, top, left + normalized_spacing * 2.0, top + normalized_spacing * 2.0))
    return queries


def _normalize_direction(dx: float, dy: float) -> tuple[float, float]:
    length = math.hypot(dx, dy)
    if length <= 0.0:
        return 0.0, 0.0
    return dx / length, dy / length


def _build_rays(
    *,
    ray_count: int,
    columns: int,
    rows: int,
    spacing: float,
) -> list[tuple[float, float, float, float, float]]:
    normalized_columns = _normalize_count(columns, minimum=1)
    normalized_rows = _normalize_count(rows, minimum=1)
    normalized_spacing = _normalize_float(spacing, minimum=1.0)
    half_columns = normalized_columns / 2.0
    half_rows = normalized_rows / 2.0
    directions = (
        (1.0, 0.0),
        (0.0, 1.0),
        (-1.0, 0.0),
        (0.0, -1.0),
        (1.0, 1.0),
        (-1.0, 1.0),
        (1.0, -1.0),
        (-1.0, -1.0),
    )

    rays: list[tuple[float, float, float, float, float]] = []
    for index in range(max(0, int(ray_count))):
        column = (index * 29) % normalized_columns
        row = (index * 13) % normalized_rows
        dx, dy = _normalize_direction(*directions[index % len(directions)])
        origin_x = (float(column) - half_columns) * normalized_spacing
        origin_y = (float(row) - half_rows) * normalized_spacing
        rays.append((origin_x, origin_y, dx, dy, normalized_spacing * 8.0))
    return rays


def _build_grid(entries: list[tuple[int, AABB]], *, cell_size: float, max_cells_per_entry: int) -> SpatialHash2D:
    grid = SpatialHash2D(cell_size=cell_size, max_cells_per_entry=max_cells_per_entry)
    for entity_id, aabb in entries:
        grid.insert(entity_id, aabb)
    return grid


def _query_checksum(grid: SpatialHash2D, queries: list[AABB]) -> int:
    checksum = len(queries)
    for query in queries:
        checksum = _mix_checksum(checksum, _set_checksum(grid.query(query)))
    return checksum


def _query_into_checksum(grid: SpatialHash2D, queries: list[AABB]) -> int:
    output: set[int] = set()
    checksum = len(queries)
    for query in queries:
        checksum = _mix_checksum(checksum, _set_checksum(grid.query_into(query, output)))
    return checksum


def _ray_checksum(grid: SpatialHash2D, rays: list[tuple[float, float, float, float, float]]) -> int:
    checksum = len(rays)
    for ox, oy, dx, dy, max_distance in rays:
        checksum = _mix_checksum(checksum, _set_checksum(grid.query_ray_candidates(ox, oy, dx, dy, max_distance)))
    return checksum


def run_spatial_hash_benchmark(
    *,
    entity_count: int = 10000,
    query_count: int = 1000,
    ray_count: int = 500,
    cell_size: float = 64.0,
    columns: int = 100,
    spacing: float = 24.0,
    aabb_size: float = 16.0,
    max_cells_per_entry: int = 256,
    oversized_count: int = 0,
    warmup: int = 1,
    repeats: int = 5,
) -> dict[str, Any]:
    normalized_entity_count = _normalize_count(entity_count, minimum=1)
    normalized_query_count = _normalize_count(query_count, minimum=1)
    normalized_ray_count = _normalize_count(ray_count, minimum=1)
    normalized_columns = _normalize_count(columns, minimum=1)
    normalized_spacing = _normalize_float(spacing, minimum=1.0)
    normalized_cell_size = _normalize_float(cell_size, minimum=1.0)
    normalized_aabb_size = _normalize_float(aabb_size, minimum=1.0)
    normalized_max_cells_per_entry = _normalize_count(max_cells_per_entry, minimum=1)
    normalized_oversized_count = max(0, int(oversized_count))
    rows = max(1, math.ceil(normalized_entity_count / normalized_columns))

    entries = _build_entries(
        entity_count=normalized_entity_count,
        columns=normalized_columns,
        spacing=normalized_spacing,
        aabb_size=normalized_aabb_size,
        oversized_count=normalized_oversized_count,
    )
    queries = _build_queries(
        query_count=normalized_query_count,
        columns=normalized_columns,
        rows=rows,
        spacing=normalized_spacing,
    )
    rays = _build_rays(
        ray_count=normalized_ray_count,
        columns=normalized_columns,
        rows=rows,
        spacing=normalized_spacing,
    )
    grid = _build_grid(
        entries,
        cell_size=normalized_cell_size,
        max_cells_per_entry=normalized_max_cells_per_entry,
    )

    operations = {
        "insert": _measure_repeated(
            lambda: _build_grid(
                entries,
                cell_size=normalized_cell_size,
                max_cells_per_entry=normalized_max_cells_per_entry,
            ).reference_count,
            warmup=warmup,
            repeats=repeats,
        ),
        "query": _measure_repeated(lambda: _query_checksum(grid, queries), warmup=warmup, repeats=repeats),
        "query_into": _measure_repeated(lambda: _query_into_checksum(grid, queries), warmup=warmup, repeats=repeats),
        "ray_candidates": _measure_repeated(lambda: _ray_checksum(grid, rays), warmup=warmup, repeats=repeats),
    }
    checksum = grid.cell_count
    for operation in operations.values():
        checksum = _mix_checksum(checksum, int(operation["checksum"]))

    return {
        "benchmark_version": SPATIAL_HASH_BENCHMARK_VERSION,
        "parameters": {
            "entity_count": normalized_entity_count,
            "query_count": normalized_query_count,
            "ray_count": normalized_ray_count,
            "cell_size": normalized_cell_size,
            "columns": normalized_columns,
            "spacing": normalized_spacing,
            "aabb_size": normalized_aabb_size,
            "max_cells_per_entry": normalized_max_cells_per_entry,
            "oversized_count": normalized_oversized_count,
            "warmup": max(0, int(warmup)),
            "repeats": max(1, int(repeats)),
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "operations": operations,
        "counts": {
            "total_entries": len(entries),
            "cell_count": grid.cell_count,
            "reference_count": grid.reference_count,
            "oversized_entry_count": grid.oversized_entry_count,
        },
        "checksum": checksum,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run isolated SpatialHash2D Python benchmark.")
    parser.add_argument("--entity-count", type=int, default=10000)
    parser.add_argument("--query-count", type=int, default=1000)
    parser.add_argument("--ray-count", type=int, default=500)
    parser.add_argument("--cell-size", type=float, default=64.0)
    parser.add_argument("--columns", type=int, default=100)
    parser.add_argument("--spacing", type=float, default=24.0)
    parser.add_argument("--aabb-size", type=float, default=16.0)
    parser.add_argument("--max-cells-per-entry", type=int, default=256)
    parser.add_argument("--oversized-count", type=int, default=0)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--out", type=str, default="", help="Optional JSON output path.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_spatial_hash_benchmark(
        entity_count=args.entity_count,
        query_count=args.query_count,
        ray_count=args.ray_count,
        cell_size=args.cell_size,
        columns=args.columns,
        spacing=args.spacing,
        aabb_size=args.aabb_size,
        max_cells_per_entry=args.max_cells_per_entry,
        oversized_count=args.oversized_count,
        warmup=args.warmup,
        repeats=args.repeats,
    )
    payload = json.dumps(report, indent=2, ensure_ascii=True)
    if args.out:
        output_path = Path(args.out)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload, encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
