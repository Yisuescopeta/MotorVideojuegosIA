from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

from tools._tooling_common import (
    DEFAULT_REPO_ROOT,
    ExitCode,
    format_command,
    make_response,
    print_json,
    resolve_git_root,
    run_command,
)

TOOLING_FOUNDATION_TESTS = (
    "tests.test_repository_governance",
    "tests.test_tooling_portability",
    "tests.test_agent_workflow",
    "tests.test_benchmark_run",
)

REPO_CONTRACT_TESTS = (
    "tests.test_repository_governance",
    "tests.test_motor_cli_contract",
    "tests.test_start_here_ai_coherence",
    "tests.test_official_contract_regression",
    "tests.test_parser_registry_alignment",
    "tests.test_motor_interface_coherence",
    "tests.test_motor_registry_consistency",
)


@dataclass(frozen=True)
class CheckCommand:
    suite: str
    label: str
    command: tuple[str, ...]
    cwd: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "suite": self.suite,
            "label": self.label,
            "command": list(self.command),
            "command_text": format_command(self.command),
            "cwd": self.cwd,
        }


@dataclass(frozen=True)
class SuiteDefinition:
    name: str
    description: str
    builder: Callable[[Path], list[CheckCommand]]


def _python_module_command(suite: str, label: str, repo_root: Path, *module_args: str) -> CheckCommand:
    return CheckCommand(
        suite=suite,
        label=label,
        command=(sys.executable, "-m", *module_args),
        cwd=repo_root.as_posix(),
    )


def _build_tooling_foundation(repo_root: Path) -> list[CheckCommand]:
    return [
        _python_module_command(
            "tooling-foundation",
            "unittest",
            repo_root,
            "unittest",
            *TOOLING_FOUNDATION_TESTS,
            "-v",
        )
    ]


def _build_repo_contracts(repo_root: Path) -> list[CheckCommand]:
    return [
        _python_module_command(
            "repo-contracts",
            "unittest",
            repo_root,
            "unittest",
            *REPO_CONTRACT_TESTS,
            "-v",
        )
    ]


def _build_doctor(repo_root: Path) -> list[CheckCommand]:
    return [
        _python_module_command(
            "doctor",
            "motor-doctor",
            repo_root,
            "motor",
            "doctor",
            "--project",
            repo_root.as_posix(),
            "--json",
        )
    ]


def _build_registry_audit(repo_root: Path) -> list[CheckCommand]:
    return [
        _python_module_command(
            "registry-audit",
            "capability-registry-audit",
            repo_root,
            "tools.capability_registry_audit",
            "--json",
        )
    ]


SUITE_DEFINITIONS: dict[str, SuiteDefinition] = {
    "tooling-foundation": SuiteDefinition(
        name="tooling-foundation",
        description="Focused governance and tooling regression checks for this foundation layer.",
        builder=_build_tooling_foundation,
    ),
    "repo-contracts": SuiteDefinition(
        name="repo-contracts",
        description="Focused contract and governance checks for repo-facing interfaces.",
        builder=_build_repo_contracts,
    ),
    "doctor": SuiteDefinition(
        name="doctor",
        description="Runs the official project diagnostic against the selected repo root.",
        builder=_build_doctor,
    ),
    "registry-audit": SuiteDefinition(
        name="registry-audit",
        description="Audits capability registry references and CLI alignment.",
        builder=_build_registry_audit,
    ),
}


def list_suites() -> list[dict[str, str]]:
    return [
        {
            "name": suite.name,
            "description": suite.description,
        }
        for suite in sorted(SUITE_DEFINITIONS.values(), key=lambda item: item.name)
    ]


def resolve_repo_root(repo_root_arg: str) -> Path:
    requested = Path(repo_root_arg).expanduser().resolve() if repo_root_arg else DEFAULT_REPO_ROOT
    return resolve_git_root(requested) or DEFAULT_REPO_ROOT


def build_suite_plan(suite_names: Sequence[str], repo_root: Path) -> list[CheckCommand]:
    commands: list[CheckCommand] = []
    seen: set[str] = set()
    for suite_name in suite_names:
        if suite_name in seen:
            continue
        seen.add(suite_name)
        definition = SUITE_DEFINITIONS[suite_name]
        commands.extend(definition.builder(repo_root))
    return commands


def run_suite_plan(commands: Sequence[CheckCommand]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for command in commands:
        result = run_command(command.command, cwd=command.cwd)
        results.append(
            {
                **command.to_dict(),
                "result": result.to_dict(),
            }
        )
    return results


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run focused repo-local tooling and governance checks.")
    parser.add_argument(
        "--suite",
        action="append",
        default=[],
        help="Named suite to run. Can be provided multiple times.",
    )
    parser.add_argument("--list-suites", action="store_true", help="List available suites and exit.")
    parser.add_argument("--repo-root", default="", help="Repo root or any path inside the target repo.")
    parser.add_argument("--dry-run", action="store_true", help="Print the planned commands without executing them.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")
    return parser.parse_args()


def _render_text(payload: dict[str, Any]) -> str:
    data = payload["data"]
    if data.get("available_suites") and not data.get("unknown_suites"):
        lines = ["Available suites:"]
        for suite in data["available_suites"]:
            lines.append(f"- {suite['name']}: {suite['description']}")
        return "\n".join(lines)

    lines = [payload["message"]]
    for planned in data.get("planned_commands", []):
        lines.append(f"[{planned['suite']}] {planned['command_text']}")

    for result in data.get("results", []):
        command_result = result["result"]
        status = "PASS" if command_result["passed"] else "FAIL"
        lines.append(f"[{status}] {result['suite']} :: {result['command_text']}")
    return "\n".join(lines)


def main() -> int:
    args = _parse_args()

    if args.list_suites:
        payload = make_response(
            True,
            f"{len(SUITE_DEFINITIONS)} suites available",
            {
                "available_suites": list_suites(),
            },
        )
        if args.json:
            print_json(payload)
        else:
            print(_render_text(payload))
        return int(ExitCode.OK)

    if not args.suite:
        raise SystemExit("At least one --suite is required unless --list-suites is used.")

    unknown_suites = sorted({name for name in args.suite if name not in SUITE_DEFINITIONS})
    if unknown_suites:
        payload = make_response(
            False,
            f"Unknown suite(s): {', '.join(unknown_suites)}",
            {
                "unknown_suites": unknown_suites,
                "available_suites": list_suites(),
            },
        )
        if args.json:
            print_json(payload)
        else:
            print(_render_text(payload))
        return int(ExitCode.INVALID)

    repo_root = resolve_repo_root(args.repo_root)
    planned_commands = [command.to_dict() for command in build_suite_plan(args.suite, repo_root)]

    if args.dry_run:
        payload = make_response(
            True,
            f"Dry run: {len(planned_commands)} commands planned across {len(set(args.suite))} suites",
            {
                "repo_root": repo_root.as_posix(),
                "requested_suites": list(dict.fromkeys(args.suite)),
                "dry_run": True,
                "planned_commands": planned_commands,
            },
        )
        if args.json:
            print_json(payload)
        else:
            print(_render_text(payload))
        return int(ExitCode.OK)

    results = run_suite_plan(build_suite_plan(args.suite, repo_root))
    success = all(item["result"]["passed"] for item in results)
    payload = make_response(
        success,
        "All requested suites passed" if success else "One or more requested suites failed",
        {
            "repo_root": repo_root.as_posix(),
            "requested_suites": list(dict.fromkeys(args.suite)),
            "dry_run": False,
            "planned_commands": planned_commands,
            "results": results,
        },
    )
    if args.json:
        print_json(payload)
    else:
        print(_render_text(payload))
    return int(ExitCode.OK if success else ExitCode.FAILED)


if __name__ == "__main__":
    raise SystemExit(main())
