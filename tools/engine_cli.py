from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.append(os.getcwd())

from cli.runner import CLIRunner
from engine.api import EngineAPI
from engine.assets.asset_service import AssetService
from engine.integrations.opencode import (
    OpenCodeBridge,
    OpenCodeClient,
    OpenCodeClientError,
    OpenCodeHTTPError,
    OpenCodeServerProcess,
    OpenCodeUnavailableError,
    ensure_opencode_artifact_dir,
    write_json_artifact,
)
from engine.project.project_service import ProjectService
from tools.schema_cli import migrate_path, validate_all, validate_path


def _validate_assets(search: str = "") -> int:
    service = AssetService(ProjectService(os.getcwd()))
    service.refresh_catalog()
    assets = service.list_assets(search=search)
    missing = [item["path"] for item in assets if not service.resolve_asset_path(item["path"]).exists()]
    if missing:
        for path in missing:
            print(f"[ERROR] missing asset: {path}")
        return 1
    print(f"[OK] assets validated: {len(assets)}")
    return 0


def _build_assets() -> int:
    service = AssetService(ProjectService(os.getcwd()))
    report = service.build_asset_artifacts()
    print(f"[OK] artifacts built: {report['artifact_count']}")
    return 0


def _run_headless(level: str, frames: int, seed: int | None, debug_dump: str = "") -> int:
    args = SimpleNamespace(
        level=level,
        frames=frames,
        seed=seed,
        script="",
        golden_output="",
        golden_compare="",
        capture_every=1,
        debug_colliders=False,
        debug_labels=False,
        debug_tile_chunks=False,
        debug_camera=False,
        debug_dump=debug_dump,
    )
    CLIRunner().run(args)
    return 0


def _profile_run(scene: str, frames: int, out: str, seed: int | None, mode: str) -> int:
    api = EngineAPI(project_root=os.getcwd())
    api.load_level(scene)
    if seed is not None:
        api.set_seed(seed)
    api.reset_profiler(run_label=f"profile:{Path(scene).name}:{mode}")
    if mode == "play":
        api.play()
    api.step(frames=max(1, int(frames)))
    output = Path(out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(api.get_profiler_report(), indent=2, ensure_ascii=True), encoding="utf-8")
    print(f"[OK] profile written: {output.as_posix()}")
    return 0


def _smoke(level: str, frames: int, seed: int | None, out_dir: str) -> int:
    out_root = Path(out_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    result = validate_path(level)
    if result != 0:
        return result
    result = _validate_assets()
    if result != 0:
        return result
    migrated_scene = out_root / "smoke_migrated_scene.json"
    result = migrate_path(level, migrated_scene.as_posix())
    if result != 0:
        return result
    result = _build_assets()
    if result != 0:
        return result
    result = _run_headless(level=level, frames=frames, seed=seed, debug_dump=(out_root / "smoke_debug_dump.json").as_posix())
    if result != 0:
        return result
    return _profile_run(
        scene=level,
        frames=frames,
        out=(out_root / "smoke_profile.json").as_posix(),
        seed=seed,
        mode="play",
    )


def _ensure_opencode_artifact_dir(session_id: str, out_dir: str = "") -> Path:
    return ensure_opencode_artifact_dir(session_id, out_dir=out_dir, project_root=os.getcwd())


def _write_json(path: Path, payload: object) -> None:
    write_json_artifact(path, payload)


def _load_prompt_text(prompt: str = "", prompt_file: str = "") -> str:
    if prompt_file:
        return Path(prompt_file).read_text(encoding="utf-8")
    return str(prompt or "")


def _opencode_start() -> int:
    result = OpenCodeBridge(project_root=os.getcwd()).ensure_server()
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0


def _opencode_status() -> int:
    snapshot = OpenCodeBridge(project_root=os.getcwd()).connect()
    print(json.dumps(snapshot, indent=2, ensure_ascii=True))
    return 0


def _opencode_stop() -> int:
    result = OpenCodeBridge(project_root=os.getcwd()).stop_server()
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0


def _opencode_new_session(title: str) -> int:
    bridge = OpenCodeBridge(project_root=os.getcwd())
    snapshot = bridge.ensure_server()
    session = bridge.create_and_select_session(title=title) if snapshot.get("connection_status", {}).get("healthy") else snapshot
    print(json.dumps(session, indent=2, ensure_ascii=True))
    return 0


def _opencode_ask(session_id: str, agent: str, prompt: str, prompt_file: str, out_dir: str, model: str = "") -> int:
    prompt_text = _load_prompt_text(prompt=prompt, prompt_file=prompt_file)
    manifest = OpenCodeBridge(project_root=os.getcwd()).send_prompt(
        session_id=session_id,
        text=prompt_text,
        agent=agent,
        model=model or None,
        out_dir=out_dir,
    )
    print(f"[OK] opencode response written: {manifest['artifact_dir']}")
    return 0


def _opencode_diff(session_id: str, message_id: str, out_dir: str) -> int:
    manifest = OpenCodeBridge(project_root=os.getcwd()).export_diff_artifact(
        session_id,
        message_id=message_id or None,
        out_dir=out_dir,
    )
    print(f"[OK] diff written: {manifest['diff_path']}")
    return 0


def _opencode_approvals(session_id: str, permission_id: str, response: str, remember: bool, out_dir: str) -> int:
    bridge = OpenCodeBridge(project_root=os.getcwd())
    output_dir = _ensure_opencode_artifact_dir(session_id, out_dir)
    if permission_id and response:
        payload = bridge.respond_permission(session_id, permission_id, response=response, remember=remember)
        _write_json(output_dir / "approval_response.json", payload)
        print(json.dumps(payload, indent=2, ensure_ascii=True))
        return 0
    approvals = bridge.list_pending_permissions(session_id)
    _write_json(output_dir / "approvals.json", approvals)
    print(json.dumps(approvals, indent=2, ensure_ascii=True))
    return 0


def _opencode_sessions(out_dir: str = "") -> int:
    bridge = OpenCodeBridge(project_root=os.getcwd())
    snapshot = bridge.connect()
    sessions = bridge.list_sessions() if snapshot.get("connection_status", {}).get("healthy") else []
    if out_dir:
        output_dir = Path(out_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        _write_json(output_dir / "sessions.json", sessions)
    print(json.dumps(sessions if sessions else snapshot, indent=2, ensure_ascii=True))
    return 0


def _opencode_messages(session_id: str, limit: int, out_dir: str) -> int:
    bridge = OpenCodeBridge(project_root=os.getcwd())
    if out_dir:
        manifest = bridge.export_messages_artifact(session_id, limit=limit, out_dir=out_dir)
        print(f"[OK] transcript written: {manifest['transcript_path']}")
        return 0
    messages = bridge.get_messages(session_id, limit=limit)
    print(json.dumps(messages, indent=2, ensure_ascii=True))
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Unified local CLI for validation, migration, assets, headless runs, and profiling.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="Validate scenes, assets, or both")
    validate_parser.add_argument("--target", choices=("scene", "assets", "all"), default="all")
    validate_parser.add_argument("--path", default="levels/demo_level.json")
    validate_parser.add_argument("--search", default="")

    migrate_parser = subparsers.add_parser("migrate", help="Migrate a scene or prefab payload")
    migrate_parser.add_argument("path")
    migrate_parser.add_argument("--output", required=True)

    build_assets_parser = subparsers.add_parser("build-assets", help="Build deterministic asset artifacts")
    build_assets_parser.add_argument("--bundle", action="store_true", help="Also create a content bundle")

    run_parser = subparsers.add_parser("run-headless", help="Execute a scene headlessly for N frames")
    run_parser.add_argument("scene")
    run_parser.add_argument("--frames", type=int, default=60)
    run_parser.add_argument("--seed", type=int, default=None)
    run_parser.add_argument("--debug-dump", default="")

    profile_parser = subparsers.add_parser("profile-run", help="Run a scene and export a versioned profiler report")
    profile_parser.add_argument("scene")
    profile_parser.add_argument("--frames", type=int, default=600)
    profile_parser.add_argument("--out", required=True)
    profile_parser.add_argument("--seed", type=int, default=None)
    profile_parser.add_argument("--mode", choices=("play", "edit"), default="play")

    smoke_parser = subparsers.add_parser("smoke", help="Run validate, migrate, build-assets, run-headless, and profile-run in order")
    smoke_parser.add_argument("--scene", default="levels/demo_level.json")
    smoke_parser.add_argument("--frames", type=int, default=5)
    smoke_parser.add_argument("--seed", type=int, default=123)
    smoke_parser.add_argument("--out-dir", default="artifacts/cli_smoke")

    opencode_parser = subparsers.add_parser("opencode", help="Manage a local OpenCode server and project sessions")
    opencode_subparsers = opencode_parser.add_subparsers(dest="opencode_command", required=True)

    opencode_subparsers.add_parser("start", help="Start the local OpenCode HTTP backend in the background")
    opencode_subparsers.add_parser("status", help="Check OpenCode server health")
    opencode_subparsers.add_parser("stop", help="Stop the local OpenCode server")
    sessions_parser = opencode_subparsers.add_parser("sessions", help="List OpenCode sessions")
    sessions_parser.add_argument("--out", default="")

    new_session_parser = opencode_subparsers.add_parser("new-session", help="Create a new OpenCode session")
    new_session_parser.add_argument("--title", required=True)

    messages_parser = opencode_subparsers.add_parser("messages", help="List or export session messages")
    messages_parser.add_argument("--session", required=True)
    messages_parser.add_argument("--limit", type=int, default=100)
    messages_parser.add_argument("--out", default="")

    ask_parser = opencode_subparsers.add_parser("ask", help="Send a prompt to an OpenCode session and persist artifacts")
    ask_parser.add_argument("--session", required=True)
    ask_parser.add_argument("--agent", choices=("plan", "build"), default="plan")
    ask_parser.add_argument("--prompt", default="")
    ask_parser.add_argument("--prompt-file", default="")
    ask_parser.add_argument("--model", default="")
    ask_parser.add_argument("--out", default="")

    diff_parser = opencode_subparsers.add_parser("diff", help="Fetch the latest or message-scoped OpenCode diff")
    diff_parser.add_argument("--session", required=True)
    diff_parser.add_argument("--message-id", default="")
    diff_parser.add_argument("--out", default="")

    approvals_parser = opencode_subparsers.add_parser("approvals", help="List pending permissions or respond to one explicitly")
    approvals_parser.add_argument("--session", required=True)
    approvals_parser.add_argument("--permission-id", default="")
    approvals_parser.add_argument("--response", choices=("allow", "deny"), default="")
    approvals_parser.add_argument("--remember", action="store_true")
    approvals_parser.add_argument("--out", default="")

    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()
    if args.command == "validate":
        if args.target == "scene":
            return validate_path(args.path)
        if args.target == "assets":
            return _validate_assets(args.search)
        scene_result = validate_path(args.path)
        if scene_result != 0:
            return scene_result
        return _validate_assets(args.search)
    if args.command == "migrate":
        return migrate_path(args.path, args.output)
    if args.command == "build-assets":
        result = _build_assets()
        if result != 0 or not args.bundle:
            return result
        service = AssetService(ProjectService(os.getcwd()))
        report = service.create_bundle()
        print(f"[OK] bundle created: {report['bundle_path']}")
        return 0
    if args.command == "run-headless":
        return _run_headless(args.scene, args.frames, args.seed, args.debug_dump)
    if args.command == "profile-run":
        return _profile_run(args.scene, args.frames, args.out, args.seed, args.mode)
    if args.command == "smoke":
        return _smoke(args.scene, args.frames, args.seed, args.out_dir)
    if args.command == "opencode":
        try:
            if args.opencode_command == "start":
                return _opencode_start()
            if args.opencode_command == "status":
                return _opencode_status()
            if args.opencode_command == "stop":
                return _opencode_stop()
            if args.opencode_command == "new-session":
                return _opencode_new_session(args.title)
            if args.opencode_command == "sessions":
                return _opencode_sessions(args.out)
            if args.opencode_command == "messages":
                return _opencode_messages(args.session, args.limit, args.out)
            if args.opencode_command == "ask":
                return _opencode_ask(
                    session_id=args.session,
                    agent=args.agent,
                    prompt=args.prompt,
                    prompt_file=args.prompt_file,
                    out_dir=args.out,
                    model=args.model,
                )
            if args.opencode_command == "diff":
                return _opencode_diff(args.session, args.message_id, args.out)
            if args.opencode_command == "approvals":
                return _opencode_approvals(args.session, args.permission_id, args.response, args.remember, args.out)
        except (OpenCodeClientError, OpenCodeHTTPError, OpenCodeUnavailableError) as exc:
            print(f"[ERROR] {exc}")
            return 1
        except FileNotFoundError as exc:
            print(f"[ERROR] {exc}")
            return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
