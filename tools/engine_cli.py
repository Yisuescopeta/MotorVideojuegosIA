from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

from engine.project.project_service import ProjectService
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


def _run_buffered(func):
    buffered_stdout = io.StringIO()
    try:
        with contextlib.redirect_stdout(buffered_stdout):
            result = func()
        _flush_buffered_stdout(buffered_stdout)
        return result
    except Exception:
        _flush_buffered_stdout(buffered_stdout)
        raise


def _validate_assets(search: str = "") -> int:
    from engine.assets.asset_service import AssetService

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
    from engine.assets.asset_service import AssetService

    service = AssetService(ProjectService(os.getcwd()))
    report = service.build_asset_artifacts()
    print(f"[OK] artifacts built: {report['artifact_count']}")
    return 0


def _render_build_settings_summary(payload: dict) -> list[str]:
    return [
        f"[OK] build settings: {payload.get('product_name', '')}",
        f"[OK] target_platform: {payload.get('target_platform', '')}",
        f"[OK] startup_scene: {payload.get('startup_scene', '')}",
        f"[OK] scenes_in_build: {len(payload.get('scenes_in_build', []))}",
    ]


def _render_prebuild_summary(payload: dict) -> list[str]:
    selected = dict(payload.get("selected_content", {})) if isinstance(payload.get("selected_content", {}), dict) else {}
    blocking = list(payload.get("blocking_errors", [])) if isinstance(payload.get("blocking_errors", []), list) else []
    warnings = list(payload.get("warnings", [])) if isinstance(payload.get("warnings", []), list) else []
    lines = [
        (
            f"[OK] prebuild valid: {payload.get('startup_scene', '')}"
            if bool(payload.get("valid"))
            else f"[ERROR] prebuild invalid: {payload.get('startup_scene', '')}"
        ),
        f"[OK] scenes: {len(payload.get('scene_order', []))}",
        (
            "[OK] selected content: "
            f"scenes={len(selected.get('scenes', []))} "
            f"prefabs={len(selected.get('prefabs', []))} "
            f"scripts={len(selected.get('scripts', []))} "
            f"assets={len(selected.get('assets', []))} "
            f"metadata={len(selected.get('metadata', []))}"
        ),
        f"[OK] warnings: {len(warnings)}",
        f"[OK] blocking_errors: {len(blocking)}",
    ]
    for item in blocking:
        code = str(dict(item).get("code", "") or "")
        message = str(dict(item).get("message", "") or "")
        path = str(dict(item).get("path", "") or dict(item).get("reference", "") or "")
        suffix = f" [{path}]" if path else ""
        lines.append(f"[ERROR] {code}: {message}{suffix}")
    return lines


def _render_build_player_summary(payload: dict) -> list[str]:
    warnings = list(payload.get("warnings", [])) if isinstance(payload.get("warnings", []), list) else []
    errors = list(payload.get("errors", [])) if isinstance(payload.get("errors", []), list) else []
    lines = [
        (
            f"[OK] build-player status: {payload.get('status', '')}"
            if str(payload.get("status", "")) == "succeeded"
            else f"[ERROR] build-player status: {payload.get('status', '')}"
        ),
        f"[OK] target: {payload.get('target_platform', '') or 'unknown'}",
        f"[OK] output: {payload.get('output_path', '') or '(none)'}",
        f"[OK] startup_scene: {payload.get('startup_scene', '') or '(none)'}",
        f"[OK] warnings: {len(warnings)}",
        f"[OK] errors: {len(errors)}",
    ]
    for item in warnings:
        code = str(dict(item).get("code", "") or "")
        message = str(dict(item).get("message", "") or "")
        path = str(dict(item).get("path", "") or "")
        suffix = f" [{path}]" if path else ""
        lines.append(f"[WARNING] {code}: {message}{suffix}")
    for item in errors:
        code = str(dict(item).get("code", "") or "")
        message = str(dict(item).get("message", "") or "")
        path = str(dict(item).get("path", "") or "")
        suffix = f" [{path}]" if path else ""
        lines.append(f"[ERROR] {code}: {message}{suffix}")
    report_path = str(payload.get("report_path", "") or "").strip()
    if report_path:
        lines.append(f"[OK] report: {report_path}")
    return lines


def _build_settings_show(project_root: str, *, as_json: bool, out_path: str) -> int:
    try:
        settings = ProjectService(project_root).load_build_settings()
        payload = settings.to_dict()
        _print_or_emit(payload, as_json=as_json, out_path=out_path, lines=_render_build_settings_summary(payload))
        return 0
    except Exception as exc:
        _emit_setup_error(
            message=f"build settings load failed: {exc}",
            as_json=as_json,
            out_path=out_path,
            code="build_settings.load_failed",
        )
        return EXIT_RUNTIME_ERROR


def _build_settings_set(args: argparse.Namespace) -> int:
    try:
        project_root = _project_root(args.project_root)
        service = ProjectService(project_root)
        payload = service.load_build_settings().to_dict()
        if args.product_name is not None:
            payload["product_name"] = args.product_name
        if args.company_name is not None:
            payload["company_name"] = args.company_name
        if args.startup_scene is not None:
            payload["startup_scene"] = args.startup_scene
        if args.scene is not None:
            payload["scenes_in_build"] = list(args.scene)
        if args.target_platform is not None:
            payload["target_platform"] = args.target_platform
        if args.output_name is not None:
            payload["output_name"] = args.output_name
        if args.development_build is not None:
            payload["development_build"] = bool(args.development_build)
        if args.include_logs is not None:
            payload["include_logs"] = bool(args.include_logs)
        if args.include_profiler is not None:
            payload["include_profiler"] = bool(args.include_profiler)
        service.save_build_settings(payload)
        saved = service.load_build_settings()
        response = saved.to_dict()
        _print_or_emit(response, as_json=args.json, out_path=args.out, lines=_render_build_settings_summary(response))
        return 0
    except Exception as exc:
        _emit_setup_error(
            message=f"build settings update failed: {exc}",
            as_json=bool(args.json),
            out_path=str(args.out or ""),
            code="build_settings.update_failed",
        )
        return EXIT_RUNTIME_ERROR


def _prebuild_check(project_root: str, *, as_json: bool, out_path: str) -> int:
    from engine.assets.asset_service import AssetService
    from engine.project import BuildPrebuildService

    try:
        def _generate():
            service = ProjectService(project_root)
            asset_service = AssetService(service)
            report = BuildPrebuildService(service, asset_service).generate_report()
            return report.to_dict()

        payload = _run_buffered(_generate)
        _print_or_emit(payload, as_json=as_json, out_path=out_path, lines=_render_prebuild_summary(payload))
        return 0 if bool(payload.get("valid")) else 2
    except Exception as exc:
        _emit_setup_error(
            message=f"prebuild setup failed: {exc}",
            as_json=as_json,
            out_path=out_path,
            code="prebuild.setup_failed",
        )
        return EXIT_RUNTIME_ERROR


def _build_player(project_root: str, output_root: str, *, as_json: bool, report_out: str) -> int:
    from engine.project import BuildPlayerOptions, BuildPlayerService

    try:
        payload = _run_buffered(
            lambda: BuildPlayerService(ProjectService(project_root))
            .build_player(BuildPlayerOptions(output_root=output_root))
            .to_dict()
        )
        _print_or_emit(payload, as_json=as_json, out_path=report_out, lines=_render_build_player_summary(payload))
        return 0 if str(payload.get("status", "")) == "succeeded" else 1
    except Exception as exc:
        _emit_setup_error(
            message=f"build-player setup failed: {exc}",
            as_json=as_json,
            out_path=report_out,
            code="build_player.setup_failed",
        )
        return EXIT_RUNTIME_ERROR


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


def _project_root(value: str) -> str:
    return Path(value or os.getcwd()).expanduser().resolve().as_posix()


def _print_or_emit(payload: dict, *, as_json: bool, out_path: str, lines: list[str]) -> None:
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


def parse_args() -> argparse.Namespace:
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

    build_settings_parser = subparsers.add_parser("build-settings", help="Inspect or update project build settings")
    build_settings_subparsers = build_settings_parser.add_subparsers(dest="build_settings_command", required=True)

    build_settings_show_parser = build_settings_subparsers.add_parser("show", help="Show normalized project build settings")
    build_settings_show_parser.add_argument("--project-root", default="")
    build_settings_show_parser.add_argument("--json", action="store_true")
    build_settings_show_parser.add_argument("--out", default="")

    build_settings_set_parser = build_settings_subparsers.add_parser("set", help="Update and save project build settings")
    build_settings_set_parser.add_argument("--project-root", default="")
    build_settings_set_parser.add_argument("--product-name", default=None)
    build_settings_set_parser.add_argument("--company-name", default=None)
    build_settings_set_parser.add_argument("--startup-scene", default=None)
    build_settings_set_parser.add_argument("--scene", action="append", default=None, help="Append a scene path; repeat to define scenes_in_build order.")
    build_settings_set_parser.add_argument("--target-platform", choices=("windows_desktop",), default=None)
    build_settings_set_parser.add_argument("--output-name", default=None)
    build_settings_set_parser.add_argument("--development-build", action=argparse.BooleanOptionalAction, default=None)
    build_settings_set_parser.add_argument("--include-logs", action=argparse.BooleanOptionalAction, default=None)
    build_settings_set_parser.add_argument("--include-profiler", action=argparse.BooleanOptionalAction, default=None)
    build_settings_set_parser.add_argument("--json", action="store_true")
    build_settings_set_parser.add_argument("--out", default="")

    prebuild_parser = subparsers.add_parser("prebuild-check", help="Run build prevalidation and content selection")
    prebuild_parser.add_argument("--project-root", default="")
    prebuild_parser.add_argument("--json", action="store_true")
    prebuild_parser.add_argument("--out", default="")

    build_player_parser = subparsers.add_parser("build-player", help="Build a folder-based Windows desktop player export")
    build_player_parser.add_argument("--project-root", default="", help="Project root to build. Defaults to the current working directory.")
    build_player_parser.add_argument("--out", default="", help="Optional output folder override for the exported player.")
    build_player_parser.add_argument("--json", action="store_true", help="Emit the build report as JSON.")
    build_player_parser.add_argument("--report-out", default="", help="Optional path to also write the build report JSON.")

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

    ai_context_parser = subparsers.add_parser("ai-context", help="Generate the AI-assisted context pack")
    ai_context_parser.add_argument("--project-root", default="")
    ai_context_parser.add_argument("--json", action="store_true")

    ai_validate_parser = subparsers.add_parser("ai-validate", help="Run structured validation for AI-assisted workflows")
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

    return parser.parse_args()


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
        from engine.assets.asset_service import AssetService

        service = AssetService(ProjectService(os.getcwd()))
        report = service.create_bundle()
        print(f"[OK] bundle created: {report['bundle_path']}")
        return 0
    if args.command == "build-settings":
        if args.build_settings_command == "show":
            return _build_settings_show(_project_root(args.project_root), as_json=args.json, out_path=args.out)
        if args.build_settings_command == "set":
            return _build_settings_set(args)
    if args.command == "build-player":
        return _build_player(_project_root(args.project_root), args.out, as_json=args.json, report_out=args.report_out)
    if args.command == "prebuild-check":
        return _prebuild_check(_project_root(args.project_root), as_json=args.json, out_path=args.out)
    if args.command == "run-headless":
        return _run_headless(args.scene, args.frames, args.seed, args.debug_dump)
    if args.command == "profile-run":
        return _profile_run(args.scene, args.frames, args.out, args.seed, args.mode)
    if args.command == "smoke":
        return _smoke(args.scene, args.frames, args.seed, args.out_dir)
    if args.command == "ai-context":
        if not args.json:
            try:
                payload = run_context_pack(_project_root(args.project_root))
                _print_or_emit(payload, as_json=False, out_path="", lines=render_context_summary(payload))
                return 0
            except Exception as exc:
                _emit_setup_error(
                    message=f"context generation failed: {exc}",
                    as_json=False,
                    out_path="",
                    code="context.setup_failed",
                )
                return EXIT_RUNTIME_ERROR

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


if __name__ == "__main__":
    raise SystemExit(main())
