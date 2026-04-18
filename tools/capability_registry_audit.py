from __future__ import annotations

import argparse
import ast
from pathlib import Path
from typing import Any

from engine.ai import get_default_registry
from engine.levels.component_registry import create_default_registry
from motor.cli import create_motor_parser
from tools._tooling_common import DEFAULT_REPO_ROOT, ExitCode, make_response, print_json

FUTURE_CLI_SCOPES = {"runtime", "undo", "redo", "status", "physics"}
COMPONENT_ARG_KEYS = {"component_name", "component"}
API_METHOD_COMPATIBILITY_ALIASES = {
    "SceneWorkspaceAPI.list_project_scenes": "ProjectService.list_project_scenes",
}


def _iter_python_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.py") if path.is_file())


def _collect_symbols(paths: list[Path]) -> tuple[dict[str, set[str]], set[str]]:
    class_methods: dict[str, set[str]] = {}
    functions: set[str] = set()

    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith("_"):
                    functions.add(node.name)
                continue

            if isinstance(node, ast.ClassDef):
                methods = class_methods.setdefault(node.name, set())
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and not item.name.startswith("_"):
                        methods.add(item.name)

    return class_methods, functions


def _available_cli_scopes() -> set[str]:
    parser = create_motor_parser()
    scopes: set[str] = set()
    for action in parser._actions:
        if hasattr(action, "choices") and action.choices:
            scopes.update(action.choices.keys())
    return scopes


def _component_issues() -> list[str]:
    registry = get_default_registry()
    available_components = set(create_default_registry().list_registered())
    issues: list[str] = []

    for capability in registry.list_all():
        for api_call in capability.example.api_calls:
            args = api_call.get("args", {})
            for key in COMPONENT_ARG_KEYS:
                value = args.get(key)
                if isinstance(value, str) and value not in available_components:
                    issues.append(f"{capability.id}: unknown component referenced in example args: {value}")

    return issues


def _api_method_findings() -> tuple[list[str], list[str], dict[str, int]]:
    registry = get_default_registry()
    symbol_roots = [
        DEFAULT_REPO_ROOT / "engine" / "api",
        DEFAULT_REPO_ROOT / "engine" / "project",
        DEFAULT_REPO_ROOT / "motor",
    ]
    class_methods, functions = _collect_symbols(
        [path for root in symbol_roots for path in _iter_python_files(root)]
    )

    issues: list[str] = []
    warnings: list[str] = []
    for capability in registry.list_all():
        for method_ref in capability.api_methods:
            if "." not in method_ref:
                if method_ref not in functions:
                    issues.append(f"{capability.id}: unresolved function reference {method_ref}")
                continue

            class_name, method_name = method_ref.rsplit(".", 1)
            if method_name in class_methods.get(class_name, set()):
                continue
            if class_name == "CapabilityRegistry" and method_name in functions:
                continue
            alias_target = API_METHOD_COMPATIBILITY_ALIASES.get(method_ref)
            if alias_target:
                alias_class, alias_method = alias_target.rsplit(".", 1)
                if alias_method in class_methods.get(alias_class, set()):
                    warnings.append(
                        f"{capability.id}: compatibility alias {method_ref} currently resolves via {alias_target}"
                    )
                    continue
            issues.append(f"{capability.id}: unresolved api_method reference {method_ref}")

    counts = {
        "classes": len(class_methods),
        "functions": len(functions),
    }
    return issues, warnings, counts


def _cli_command_issues() -> tuple[list[str], dict[str, int]]:
    registry = get_default_registry()
    available_scopes = _available_cli_scopes()
    issues: list[str] = []

    for capability in registry.list_all():
        cli_command = capability.cli_command
        if not cli_command.startswith("motor "):
            issues.append(f"{capability.id}: cli_command must start with 'motor ': {cli_command}")
            continue
        if "tools.engine_cli" in cli_command:
            issues.append(f"{capability.id}: cli_command references deprecated tools.engine_cli")
            continue
        parts = cli_command.split()
        if len(parts) < 2:
            issues.append(f"{capability.id}: cli_command is incomplete: {cli_command}")
            continue
        scope = parts[1]
        if scope not in available_scopes and scope not in FUTURE_CLI_SCOPES:
            issues.append(f"{capability.id}: unknown CLI scope '{scope}'")

    return issues, {"available_scopes": len(available_scopes)}


def _registry_contract_issues() -> list[str]:
    registry = get_default_registry()
    return registry.validate()


def _mode_issues() -> list[str]:
    registry = get_default_registry()
    issues: list[str] = []
    for capability in registry.list_all():
        if capability.mode == "both" and capability.id.startswith("component:remove"):
            issues.append(f"{capability.id}: destructive component mutation should not be both-mode")
    return issues


def build_audit_report() -> dict[str, Any]:
    registry = get_default_registry()
    registry_issues = _registry_contract_issues()
    component_issues = _component_issues()
    mode_issues = _mode_issues()
    api_issues, api_warnings, symbol_counts = _api_method_findings()
    cli_issues, cli_counts = _cli_command_issues()
    checks = [
        {
            "name": "registry-contract",
            "passed": not registry_issues,
            "issues": registry_issues,
            "warnings": [],
        },
        {
            "name": "api-methods",
            "passed": not api_issues,
            "issues": api_issues,
            "warnings": api_warnings,
        },
        {
            "name": "cli-commands",
            "passed": not cli_issues,
            "issues": cli_issues,
            "warnings": [],
        },
        {
            "name": "component-examples",
            "passed": not component_issues,
            "issues": component_issues,
            "warnings": [],
        },
        {
            "name": "mode-consistency",
            "passed": not mode_issues,
            "issues": mode_issues,
            "warnings": [],
        },
    ]

    issues = [issue for check in checks for issue in check["issues"]]
    warnings = [warning for check in checks for warning in check["warnings"]]
    success = not issues
    return make_response(
        success,
        (
            "Capability registry audit passed"
            if success and not warnings
            else "Capability registry audit passed with warnings"
            if success
            else "Capability registry audit found issues"
        ),
        {
            "capability_count": len(registry.list_all()),
            "checks": checks,
            "issue_count": len(issues),
            "warning_count": len(warnings),
            "issues": issues,
            "warnings": warnings,
            "symbol_counts": symbol_counts,
            "cli_counts": cli_counts,
            "registered_component_count": len(create_default_registry().list_registered()),
        },
    )


def _render_text(payload: dict[str, Any]) -> str:
    lines = [payload["message"]]
    data = payload["data"]
    lines.append(f"Capabilities: {data['capability_count']}")
    for check in data["checks"]:
        status = "PASS" if check["passed"] else "FAIL"
        lines.append(f"- {check['name']}: {status} ({len(check['issues'])} issues)")
        for issue in check["issues"]:
            lines.append(f"  {issue}")
        for warning in check["warnings"]:
            lines.append(f"  warning: {warning}")
    return "\n".join(lines)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit capability registry references and CLI alignment.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    payload = build_audit_report()
    if args.json:
        print_json(payload)
    else:
        print(_render_text(payload))
    return int(ExitCode.OK if payload["success"] else ExitCode.FAILED)


if __name__ == "__main__":
    raise SystemExit(main())
