from __future__ import annotations

import argparse
import os
import sys

sys.path.append(os.getcwd())

from engine.assets.asset_service import AssetService
from engine.project.project_service import ProjectService


def main() -> int:
    parser = argparse.ArgumentParser(description="Asset pipeline CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("build-assets")
    subparsers.add_parser("bundle")
    validate_parser = subparsers.add_parser("validate-assets")
    validate_parser.add_argument("--search", default="")

    args = parser.parse_args()
    service = AssetService(ProjectService(os.getcwd()))

    if args.command == "build-assets":
        report = service.build_asset_artifacts()
        print(f"[OK] artifacts built: {report['artifact_count']}")
        return 0
    if args.command == "bundle":
        report = service.create_bundle()
        print(f"[OK] bundle created: {report['bundle_path']}")
        return 0
    if args.command == "validate-assets":
        assets = service.list_assets(search=args.search)
        missing = [item["path"] for item in assets if not service.resolve_asset_path(item["path"]).exists()]
        if missing:
            for path in missing:
                print(f"[ERROR] missing asset: {path}")
            return 1
        print(f"[OK] assets validated: {len(assets)}")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
