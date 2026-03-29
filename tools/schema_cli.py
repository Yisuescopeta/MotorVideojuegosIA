from __future__ import annotations

import argparse
import json
from pathlib import Path

from engine.serialization.schema import (
    detect_payload_kind,
    migrate_prefab_data,
    migrate_scene_data,
    validate_prefab_data,
    validate_scene_data,
)


def _load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _save_json(path: str, payload: dict) -> None:
    Path(path).write_text(json.dumps(payload, indent=4), encoding="utf-8")


def validate_path(path: str) -> int:
    raw = _load_json(path)
    kind = detect_payload_kind(path)
    payload = migrate_prefab_data(raw) if kind == "prefab" else migrate_scene_data(raw)
    errors = validate_prefab_data(payload) if kind == "prefab" else validate_scene_data(payload)
    if errors:
        for error in errors:
            print(error)
        return 1
    print(f"[OK] {kind} valido: {path}")
    return 0


def migrate_path(path: str, output: str | None) -> int:
    raw = _load_json(path)
    kind = detect_payload_kind(path)
    payload = migrate_prefab_data(raw) if kind == "prefab" else migrate_scene_data(raw)
    target = output or path
    _save_json(target, payload)
    print(f"[OK] {kind} migrado a schema actual: {target}")
    return 0


def validate_all(root: str) -> int:
    base = Path(root)
    failures = 0
    for path in sorted(base.rglob("*.json")) + sorted(base.rglob("*.prefab")):
        failures += validate_path(path.as_posix())
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validacion y migracion de schema")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate_scene")
    validate_parser.add_argument("path")

    validate_all_parser = subparsers.add_parser("validate_all")
    validate_all_parser.add_argument("root", nargs="?", default=".")

    migrate_parser = subparsers.add_parser("migrate_scene")
    migrate_parser.add_argument("path")
    migrate_parser.add_argument("--output", default="")

    args = parser.parse_args()
    if args.command == "validate_scene":
        return validate_path(args.path)
    if args.command == "validate_all":
        return validate_all(args.root)
    if args.command == "migrate_scene":
        return migrate_path(args.path, args.output or None)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
