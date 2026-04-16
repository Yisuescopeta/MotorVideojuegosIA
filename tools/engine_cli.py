"""
tools/engine_cli.py - Legacy compatibility CLI.

This module keeps the deprecated entry point alive for existing scripts and
tests while the official CLI lives in motor.cli.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import sys
import warnings
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from engine.project.project_service import ProjectService
from motor import cli as _motor_cli
from motor import cli_core as _cli_core
from tools.ai_workflow_cli_helpers import (
    EXIT_RUNTIME_ERROR,
    load_json_file,
    parse_verification_scenario,
    render_context_summary,
    render_validation_summary,
    render_verification_summary,
    render_workflow_summary,
    run_context_pack,
    run_validation,
    run_verification,
    run_workflow,
    write_json_output,
)
from tools.schema_cli import migrate_path, validate_path

# Re-export command handlers from motor.cli_core for backward compatibility.
cmd_capabilities = _cli_core.cmd_capabilities
cmd_doctor = _cli_core.cmd_doctor
cmd_project_info = _cli_core.cmd_project_info
cmd_scene_list = _cli_core.cmd_scene_list
cmd_scene_create = _cli_core.cmd_scene_create
cmd_entity_create = _cli_core.cmd_entity_create
cmd_component_add = _cli_core.cmd_component_add
cmd_assets_list = _cli_core.cmd_assets_list
cmd_slices_list = _cli_core.cmd_slices_list
cmd_slices_grid = _cli_core.cmd_slices_grid
cmd_slices_auto = _cli_core.cmd_slices_auto
cmd_slices_manual = _cli_core.cmd_slices_manual
cmd_animator_info = _cli_core.cmd_animator_info
cmd_animator_set_sheet = _cli_core.cmd_animator_set_sheet
cmd_animator_upsert_state = _cli_core.cmd_animator_upsert_state
cmd_animator_remove_state = _cli_core.cmd_animator_remove_state
_output = _cli_core._output
_ensure_project = _cli_core._ensure_project
_init_engine = _cli_core._init_engine
_make_response = _cli_core._make_response
_print_json = _cli_core._print_json
EngineCLIError = _cli_core.EngineCLIError
ProjectNotFoundError = _cli_core.ProjectNotFoundError
EngineInitError = _cli_core.EngineInitError

# Re-export official CLI helpers for transition support.
run_motor_command = _motor_cli.run_motor_command
cli_main = _motor_cli.cli_main
main = _motor_cli.main
create_motor_parser = _motor_cli.create_motor_parser

# Legacy compatibility alias.
parse_args = create_motor_parser

__all__ = [
    "cmd_capabilities",
    "cmd_doctor",
    "cmd_project_info",
    "cmd_scene_list",
    "cmd_scene_create",
    "cmd_entity_create",
    "cmd_component_add",
    "cmd_assets_list",
    "cmd_slices_list",
    "cmd_slices_grid",
    "cmd_slices_auto",
    "cmd_slices_manual",
    "cmd_animator_info",
    "cmd_animator_set_sheet",
    "cmd_animator_upsert_state",
    "cmd_animator_remove_state",
    "_output",
    "_ensure_project",
    "_init_engine",
    "_make_response",
    "_print_json",
    "EngineCLIError",
    "ProjectNotFoundError",
    "EngineInitError",
    "run_motor_command",
    "cli_main",
    "main",
    "create_motor_parser",
    "parse_args",
]

_LEGACY_COMMANDS = {
    "validate",
    "migrate",
    "build-assets",
    "run-headless",
    "profile-run",
    "smoke",
    "ai-context",
    "ai-validate",
    "ai-verify",
    "ai-workflow",
}


def _emit_deprecation_warning() -> None:
    warnings.warn(
        "python -m tools.engine_cli is deprecated. Use 'motor' or 'python -m motor' instead.",
        DeprecationWarning,
        stacklevel=2,
    )


def _project_root(value: str) -> str:
    return Path(value or os.getcwd()).expanduser().resolve().as_posix()


def _validate_assets(search: str = "") -> int:
    from engine.assets.asset_service import AssetService

    service = AssetService(ProjectService(os.getcwd()))
    service.refresh_catalog()
    assets = service.list_assets(search=search)
    missing = [item["path"] for item in assets if not service.resolve_asset_path(item["path"]).exists()]
    if missing:
        for asset_path in missing:
            print(f"[ERROR] missing asset: {asset_path}")
        return 1
    print(f"[OK] assets validated: {len(assets)}")
    return 0


def _build_assets() -> int:
    from engine.assets.asset_service import AssetService

    service = AssetService(ProjectService(os.getcwd()))
    report = service.build_asset_artifacts()
    print(f"[OK] artifacts built: {report['artifact_count']}")
    return 0


def _run_headless(level: str, frames: int, seed: int | None, debug_dump: str = "") -> int:
    from cli.runner import CLIRunner

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
    from engine.api import EngineAPI

    api = EngineAPI(project_root=os.getcwd())
    api.load_level(scene)
    if seed is not None:
        api.set_seed(seed)
    api.reset_profiler(run_label=f"profile:{Path(scene).name}:{mode}")
    if api.game is not None:
        api.game.enable_runtime_metrics = True
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
    result = _run_headless(
        level=level,
        frames=frames,
        seed=seed,
        debug_dump=(out_root / "smoke_debug_dump.json").as_posix(),
    )
    if result != 0:
        return result
    return _profile_run(
        scene=level,
        frames=frames,
        out=(out_root / "smoke_profile.json").as_posix(),
        seed=seed,
        mode="play",
    )


def _print_or_emit(payload: dict[str, Any], *, as_json: bool, out_path: str, lines: list[str]) -> None:
    rendered = write_json_output(payload, out_path)
    if as_json:
        print(rendered)
        return
    for line in lines:
        print(line)
    if out_path:
        print(f"[OK] json report written: {Path(out_path).as_posix()}")


def _emit_setup_error(*, message: str, as_json: bool, out_path: str, code: str) -> None:
    payload = {
        "status": "failed",
        "error": {
            "code": code,
            "message": message,
        },
        "exit_code": EXIT_RUNTIME_ERROR,
    }
    rendered = write_json_output(payload, out_path)
    if as_json:
        print(rendered)
        return
    print(f"[ERROR] {message}")
    if out_path:
        print(f"[OK] json report written: {Path(out_path).as_posix()}")


def _flush_buffered_stdout(buffered_stdout: io.StringIO) -> None:
    noise = buffered_stdout.getvalue()
    if noise:
        sys.stderr.write(noise)


def _build_legacy_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Legacy compatibility CLI for AI workflow helpers.")
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

    smoke_parser = subparsers.add_parser(
        "smoke",
        help="Run validate, migrate, build-assets, run-headless, and profile-run in order",
    )
    smoke_parser.add_argument("--scene", default="levels/demo_level.json")
    smoke_parser.add_argument("--frames", type=int, default=5)
    smoke_parser.add_argument("--seed", type=int, default=123)
    smoke_parser.add_argument("--out-dir", default="artifacts/cli_smoke")

    ai_context_parser = subparsers.add_parser("ai-context", help="Generate the AI-assisted context pack")
    ai_context_parser.add_argument("--project-root", default="")
    ai_context_parser.add_argument("--json", action="store_true")

    ai_validate_parser = subparsers.add_parser(
        "ai-validate",
        help="Run structured validation for AI-assisted workflows",
    )
    ai_validate_parser.add_argument(
        "--target",
        choices=("active-scene", "scene-file", "prefab-file", "scene-transitions", "project"),
        required=True,
    )
    ai_validate_parser.add_argument("--path", default="")
    ai_validate_parser.add_argument("--project-root", default="")
    ai_validate_parser.add_argument("--json", action="store_true")

    ai_verify_parser = subparsers.add_parser("ai-verify", help="Run structured headless verification")
    ai_verify_parser.add_argument("--scenario", required=True)
    ai_verify_parser.add_argument("--project-root", default="")
    ai_verify_parser.add_argument("--json", action="store_true")
    ai_verify_parser.add_argument("--out", default="")

    ai_workflow_parser = subparsers.add_parser("ai-workflow", help="Run a thin AI-assisted workflow sequence")
    ai_workflow_parser.add_argument("--spec", required=True)
    ai_workflow_parser.add_argument("--project-root", default="")
    ai_workflow_parser.add_argument("--json", action="store_true")
    ai_workflow_parser.add_argument("--out", default="")

    return parser


def _dispatch_legacy_command(args: argparse.Namespace) -> int:
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
        from engine.assets.asset_service import AssetService

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

    if args.command == "ai-context":
        if not args.json:
            payload = run_context_pack(_project_root(args.project_root))
            _print_or_emit(payload, as_json=False, out_path="", lines=render_context_summary(payload))
            return 0

        buffered_stdout = io.StringIO()
        try:
            with contextlib.redirect_stdout(buffered_stdout):
                payload = run_context_pack(_project_root(args.project_root))
            _flush_buffered_stdout(buffered_stdout)
            _print_or_emit(payload, as_json=True, out_path="", lines=render_context_summary(payload))
            return 0
        except Exception as exc:
            _flush_buffered_stdout(buffered_stdout)
            _emit_setup_error(
                message=f"context generation failed: {exc}",
                as_json=True,
                out_path="",
                code="context.setup_failed",
            )
            return EXIT_RUNTIME_ERROR

    if args.command == "ai-validate":
        if not args.json:
            try:
                exit_code, payload = run_validation(
                    project_root=_project_root(args.project_root),
                    target=args.target,
                    path=args.path,
                )
                _print_or_emit(payload, as_json=False, out_path="", lines=render_validation_summary(payload))
                return exit_code
            except Exception as exc:
                _emit_setup_error(
                    message=f"validation setup failed: {exc}",
                    as_json=False,
                    out_path="",
                    code="validation.setup_failed",
                )
                return EXIT_RUNTIME_ERROR

        buffered_stdout = io.StringIO()
        try:
            with contextlib.redirect_stdout(buffered_stdout):
                exit_code, payload = run_validation(
                    project_root=_project_root(args.project_root),
                    target=args.target,
                    path=args.path,
                )
            _flush_buffered_stdout(buffered_stdout)
            _print_or_emit(payload, as_json=True, out_path="", lines=render_validation_summary(payload))
            return exit_code
        except Exception as exc:
            _flush_buffered_stdout(buffered_stdout)
            _emit_setup_error(
                message=f"validation setup failed: {exc}",
                as_json=True,
                out_path="",
                code="validation.setup_failed",
            )
            return EXIT_RUNTIME_ERROR

    if args.command == "ai-verify":
        if not args.json:
            try:
                scenario_data = load_json_file(args.scenario)
                scenario = parse_verification_scenario(
                    scenario_data,
                    default_project_root=_project_root(args.project_root),
                )
                exit_code, payload = run_verification(scenario)
                _print_or_emit(payload, as_json=False, out_path=args.out, lines=render_verification_summary(payload))
                return exit_code
            except Exception as exc:
                _emit_setup_error(
                    message=f"verification setup failed: {exc}",
                    as_json=False,
                    out_path=args.out,
                    code="verification.setup_failed",
                )
                return EXIT_RUNTIME_ERROR

        buffered_stdout = io.StringIO()
        try:
            with contextlib.redirect_stdout(buffered_stdout):
                scenario_data = load_json_file(args.scenario)
                scenario = parse_verification_scenario(
                    scenario_data,
                    default_project_root=_project_root(args.project_root),
                )
                exit_code, payload = run_verification(scenario)
            _flush_buffered_stdout(buffered_stdout)
            _print_or_emit(payload, as_json=True, out_path=args.out, lines=render_verification_summary(payload))
            return exit_code
        except Exception as exc:
            _flush_buffered_stdout(buffered_stdout)
            _emit_setup_error(
                message=f"verification setup failed: {exc}",
                as_json=True,
                out_path=args.out,
                code="verification.setup_failed",
            )
            return EXIT_RUNTIME_ERROR

    if args.command == "ai-workflow":
        if not args.json:
            try:
                spec = load_json_file(args.spec)
                project_root = _project_root(args.project_root or str(spec.get("project_root", "") or os.getcwd()))
                exit_code, payload = run_workflow(spec, project_root=project_root)
                _print_or_emit(payload, as_json=False, out_path=args.out, lines=render_workflow_summary(payload))
                return exit_code
            except Exception as exc:
                _emit_setup_error(
                    message=f"workflow setup failed: {exc}",
                    as_json=False,
                    out_path=args.out,
                    code="workflow.setup_failed",
                )
                return EXIT_RUNTIME_ERROR

        buffered_stdout = io.StringIO()
        try:
            with contextlib.redirect_stdout(buffered_stdout):
                spec = load_json_file(args.spec)
                project_root = _project_root(args.project_root or str(spec.get("project_root", "") or os.getcwd()))
                exit_code, payload = run_workflow(spec, project_root=project_root)
            _flush_buffered_stdout(buffered_stdout)
            _print_or_emit(payload, as_json=True, out_path=args.out, lines=render_workflow_summary(payload))
            return exit_code
        except Exception as exc:
            _flush_buffered_stdout(buffered_stdout)
            _emit_setup_error(
                message=f"workflow setup failed: {exc}",
                as_json=True,
                out_path=args.out,
                code="workflow.setup_failed",
            )
            return EXIT_RUNTIME_ERROR

    return 1


def deprecated_main() -> int:
    _emit_deprecation_warning()
    print(
        "[DEPRECATED] Using python -m tools.engine_cli is deprecated.\n"
        "[DEPRECATED] Please use: motor {}\n".format(" ".join(sys.argv[1:])),
        file=sys.stderr,
    )

    argv = sys.argv[1:]
    if argv and argv[0] in _LEGACY_COMMANDS:
        parser = _build_legacy_parser()
        args = parser.parse_args(argv)
        return _dispatch_legacy_command(args)

    return run_motor_command(argv)


if __name__ == "__main__":
    raise SystemExit(deprecated_main())
