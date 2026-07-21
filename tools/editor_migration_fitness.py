"""Run G0 fitness rules against the approved editor-migration inventory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

from tools.editor_migration_inventory import build_inventory

DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[1]


def _record_key(record: dict[str, object], fields: Iterable[str]) -> tuple[str, ...]:
    return tuple(str(record.get(field, "")) for field in fields)


def _new_records(
    current: list[dict[str, object]],
    baseline: list[dict[str, object]],
    fields: tuple[str, ...],
) -> list[dict[str, object]]:
    baseline_keys = {_record_key(record, fields) for record in baseline}
    return [record for record in current if _record_key(record, fields) not in baseline_keys]


def evaluate_fitness(current: dict[str, object], baseline: dict[str, object]) -> dict[str, object]:
    current_surfaces = current.get("scene_mutable_surfaces", [])
    baseline_surfaces = baseline.get("scene_mutable_surfaces", [])
    current_consumers = current.get("world_to_scene_consumers", [])
    baseline_consumers = baseline.get("world_to_scene_consumers", [])
    current_edges = current.get("runtime_to_editor_boundary_edges", [])
    baseline_edges = baseline.get("runtime_to_editor_boundary_edges", [])
    current_parse_errors = current.get("parse_errors", [])

    assert isinstance(current_surfaces, list)
    assert isinstance(baseline_surfaces, list)
    assert isinstance(current_consumers, list)
    assert isinstance(baseline_consumers, list)
    assert isinstance(current_edges, list)
    assert isinstance(baseline_edges, list)
    assert isinstance(current_parse_errors, list)

    new_surfaces = _new_records(
        current_surfaces,
        baseline_surfaces,
        ("path", "name", "kind"),
    )
    new_consumers = _new_records(
        current_consumers,
        baseline_consumers,
        ("path", "category", "symbol", "evidence"),
    )
    new_edges = _new_records(
        current_edges,
        baseline_edges,
        ("source", "target"),
    )
    violations: list[dict[str, object]] = []
    if new_surfaces:
        violations.append(
            {
                "rule": "no_new_mutable_scene_surfaces",
                "records": new_surfaces,
            }
        )
    if new_consumers:
        violations.append(
            {
                "rule": "no_new_world_to_scene_consumers",
                "records": new_consumers,
            }
        )
    if new_edges:
        violations.append(
            {
                "rule": "runtime_cannot_import_editor_or_inspector",
                "records": new_edges,
            }
        )
    if current_parse_errors:
        violations.append(
            {
                "rule": "all_scoped_python_files_parse",
                "records": current_parse_errors,
            }
        )

    return {
        "schema_version": 1,
        "fitness": "editor_migration_g0",
        "passed": not violations,
        "baseline_metrics": baseline.get("metrics", {}),
        "current_metrics": current.get("metrics", {}),
        "violations": violations,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run editor migration G0 fitness rules.")
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--json-out", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    current = build_inventory(args.repo_root.resolve())
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    report = evaluate_fitness(current, baseline)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"passed": report["passed"], "violations": len(report["violations"])}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
