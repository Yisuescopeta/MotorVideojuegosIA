#!/usr/bin/env python3
"""Validate a Queen subagent JSON result using only the standard library."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "references" / "result_schemas.json"


class ContractError(ValueError):
    """Raised when a result does not satisfy its Queen contract."""


def load_contracts(path: Path = SCHEMA_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_result_text(text: str) -> Any:
    if not text or not text.strip():
        raise ContractError("missing_subagent_result: empty result")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ContractError(f"missing_subagent_result: invalid JSON: {exc.msg}") from exc


def _matches_type(value: Any, expected: str) -> bool:
    checks = {
        "object": lambda item: isinstance(item, dict),
        "array": lambda item: isinstance(item, list),
        "string": lambda item: isinstance(item, str),
        "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
        "number": lambda item: isinstance(item, (int, float)) and not isinstance(item, bool),
        "boolean": lambda item: isinstance(item, bool),
        "null": lambda item: item is None,
    }
    return checks[expected](value)


def validate_value(value: Any, schema: dict[str, Any], path: str = "$") -> None:
    expected = schema.get("type")
    if expected is not None:
        expected_types = [expected] if isinstance(expected, str) else expected
        if not any(_matches_type(value, item) for item in expected_types):
            raise ContractError(f"{path}: expected type {expected_types}")

    if "enum" in schema and value not in schema["enum"]:
        raise ContractError(f"{path}: value {value!r} not in {schema['enum']!r}")

    if isinstance(value, str) and len(value) < schema.get("minLength", 0):
        raise ContractError(f"{path}: string shorter than minLength")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            raise ContractError(f"{path}: array shorter than minItems")
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(value):
                validate_value(item, item_schema, f"{path}[{index}]")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            raise ContractError(f"{path}: below minimum")
        if "maximum" in schema and value > schema["maximum"]:
            raise ContractError(f"{path}: above maximum")
    if isinstance(value, dict):
        if len(value) < schema.get("minProperties", 0):
            raise ContractError(f"{path}: object has fewer than minProperties")
        missing = [name for name in schema.get("required", []) if name not in value]
        if missing:
            raise ContractError(f"{path}: missing required fields: {', '.join(missing)}")
        properties = schema.get("properties", {})
        for name, child_schema in properties.items():
            if name in value:
                validate_value(value[name], child_schema, f"{path}.{name}")
        additional = schema.get("additionalProperties")
        if additional is False:
            extras = sorted(set(value) - set(properties))
            if extras:
                raise ContractError(f"{path}: unexpected fields: {', '.join(extras)}")
        elif isinstance(additional, dict):
            for name in sorted(set(value) - set(properties)):
                validate_value(value[name], additional, f"{path}.{name}")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(f"semantic_contract: {message}")


def _has_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_semantics(agent_type: str, result: dict[str, Any]) -> None:
    """Reject structurally valid but contradictory or evidence-free results."""
    phase = result.get("phase_status")

    if agent_type == "context_recon":
        status = result["status"]
        if status == "completed":
            _require(phase == "completed", "completed recon requires completed phase")
            _require(bool(result["files_reviewed"]), "completed recon requires files_reviewed evidence")
            _require(result["blocked_reason"] is None, "completed recon cannot have blocked_reason")
        elif status == "partial":
            _require(phase == "blocked" and _has_text(result["blocked_reason"]), "partial recon requires blocked phase and reason")
        else:
            _require(phase == status and _has_text(result["blocked_reason"]), f"{status} recon requires matching phase and reason")

    elif agent_type == "test_strategist":
        verdict = result["verdict"]
        if verdict == "sufficient":
            _require(phase == "completed", "sufficient TEST CONTRACT requires completed phase")
            _require(bool(result["minimum_focused_commands"]), "sufficient TEST CONTRACT requires focused commands")
            _require(bool(result["acceptance_criteria"]), "sufficient TEST CONTRACT requires acceptance criteria")
            _require(bool(result["existing_tests_authority"] or result["new_or_modified_tests_required"]), "sufficient TEST CONTRACT requires authority or new tests")
        elif verdict == "insufficient":
            _require(phase == "blocked", "insufficient TEST CONTRACT requires blocked phase")
        else:
            _require(phase == "not_applicable", "not_applicable TEST CONTRACT requires not_applicable phase")
            _require(result["task_type"] == "docs_only", "not_applicable TEST CONTRACT only valid for docs_only")

    elif agent_type == "planner":
        if result["mode"] == "blocked":
            _require(phase == "blocked" and bool(result["risks"]), "blocked plan requires blocked phase and risk")
        else:
            _require(phase == "completed", "executable plan requires completed phase")
            _require(result["test_contract_verdict"] in {"sufficient", "not_applicable"}, "executable plan requires usable TEST CONTRACT")
            _require(bool(result["steps"] and result["allowed_files"]), "executable plan requires steps and allowed_files")
            _require(bool(result["minimum_focused_commands"]), "executable plan requires focused commands")

    elif agent_type == "builder":
        status = result["status"]
        if status == "completed":
            _require(phase == "completed", "completed builder requires completed phase")
            _require(bool(result["files_changed"] and result["commands_run"]), "completed builder requires files and command evidence")
            _require(not result["write_scope_violations"], "completed builder cannot report scope violations")
        elif status == "partial":
            _require(phase == "blocked" and bool(result["risks"]), "partial builder requires blocked phase and risk")
        else:
            _require(phase == status and bool(result["risks"]), f"{status} builder requires matching phase and risk")

    elif agent_type == "documenter":
        status = result["status"]
        if status == "completed":
            _require(phase == "completed" and bool(result["docs_changed"]), "completed documenter requires docs_changed")
        elif status == "not_applicable":
            _require(phase == "not_applicable" and not result["docs_changed"] and _has_text(result["reason"]), "not_applicable documenter requires reason and no docs")
        else:
            _require(phase == status and bool(result["risks"]), f"{status} documenter requires matching phase and risk")

    elif agent_type == "validator":
        status = result["results"]
        if status == "pass":
            _require(phase == "completed", "validator pass requires completed phase")
            _require(result["minimum_commands_status"] == "pass", "validator pass requires minimum commands pass")
            _require(bool(result["commands_run"]), "validator pass requires command evidence")
            _require(not result["failures"] and not result["missing_expected_tests"], "validator pass cannot contain failures or missing tests")
            _require(not result["relaxed_tests_risk"], "validator pass cannot carry relaxed test risk")
            _require(result["blocked_reason"] is None, "validator pass cannot have blocked_reason")
        elif status == "fail":
            _require(phase == "failed" and bool(result["failures"]), "validator fail requires failed phase and failures")
        elif status == "blocked":
            _require(phase == "blocked" and _has_text(result["blocked_reason"]), "blocked validator requires reason")
        else:
            _require(phase == "blocked" and _has_text(result["risk_assessment"]), f"validator {status} requires blocked phase and risk")

    elif agent_type == "code_reviewer":
        must_fix = [item for item in result["findings"] if item["must_fix"]]
        verdict = result["verdict"]
        if verdict == "approved":
            _require(phase == "completed" and not must_fix, "approved review requires completed phase and zero must_fix")
            _require(result["test_results"] != "fail", "approved review cannot report failed tests")
        elif verdict == "changes_requested":
            _require(phase == "blocked" and bool(must_fix), "changes_requested requires blocked phase and must_fix")
        else:
            _require(phase == "failed" and bool(must_fix), "rejected review requires failed phase and must_fix")

    elif agent_type == "ai_friendliness":
        if not result["applicable"]:
            _require(phase == "not_applicable", "non-applicable AI audit requires not_applicable phase")
            _require(result["tier"] == "not_applicable" and _has_text(result["not_applicable_reason"]), "non-applicable AI audit requires tier and reason")
            _require(result["scores"] is None and result["total_score"] is None, "non-applicable AI audit cannot compute scores")
        else:
            _require(phase == "completed", "applicable AI audit requires completed phase")
            _require(result["not_applicable_reason"] is None and isinstance(result["scores"], dict), "applicable AI audit requires scores and no not_applicable reason")
            total = sum(result["scores"][name]["score"] for name in ("serialization", "public_api", "documentation", "compliance"))
            _require(total == result["total_score"], "AI audit total_score must equal dimension sum")
            expected_tier = "excellent" if total >= 90 else "good" if total >= 70 else "needs_work" if total >= 50 else "not_ready"
            _require(result["tier"] == expected_tier, "AI audit tier must match total_score")

    elif agent_type == "committer":
        status = result["status"]
        if status == "ok":
            _require(phase == "completed", "successful commit requires completed phase")
            _require(_has_text(result["commit_hash"]) and re.fullmatch(r"[0-9a-fA-F]{7,40}", result["commit_hash"]) is not None, "successful commit requires git hash")
            _require(_has_text(result["message"]) and bool(result["files_committed"]), "successful commit requires message and files")
            _require(result["blocked_reason"] is None, "successful commit cannot have blocked_reason")
        else:
            expected_phase = "blocked" if status == "blocked" else "failed"
            _require(phase == expected_phase and _has_text(result["blocked_reason"]), f"{status} commit requires matching phase and reason")
            _require(not result["files_committed"], f"{status} commit cannot report committed files")

    elif agent_type == "godot_source_analyzer" and phase == "completed":
        _require(_has_text(result["godot_source_path"]), "completed Godot source analysis requires source path")
        _require(bool(result["subsystems_analyzed"]), "completed Godot source analysis requires subsystems")
        _require(result["total_features"] == len(result["features"]), "Godot total_features must match features")
        _require(sum(result["priorities"].values()) == result["total_features"], "Godot priorities must sum to total_features")

    elif agent_type == "godot_gap_analyzer" and phase == "completed":
        _require(bool(result["catalog_source"] and result["recommended_order"]), "completed Godot gap analysis requires source and order")
        _require(sum(result["priority_summary"].values()) == len(result["gaps"]), "Godot priority summary must match gaps")

    elif agent_type == "godot_adapter":
        status = result["status"]
        if status == "completed":
            _require(phase == "completed", "completed Godot adapter requires completed phase")
            _require(bool(result["files_changed"] and result["commands_run"]), "completed Godot adapter requires files and commands")
            _require(not result["write_scope_violations"], "completed Godot adapter cannot have scope violations")
        else:
            expected = "blocked" if status in {"partial", "blocked"} else "failed"
            _require(phase == expected and bool(result["risks"]), f"{status} Godot adapter requires risk and matching phase")

    elif agent_type == "queen_task_result" and result["task_status"] == "completed":
        _require(result["cycles_used"] >= 1, "completed Queen task requires at least one cycle")


def validate_result(agent_type: str, result: Any, contracts: dict[str, Any] | None = None) -> None:
    contracts = contracts or load_contracts()
    normalized = agent_type.strip().replace("-", "_")
    normalized = contracts.get("aliases", {}).get(normalized, normalized)
    schema = contracts.get("agent_types", {}).get(normalized)
    if schema is None:
        known = ", ".join(sorted(contracts.get("agent_types", {})))
        raise ContractError(f"unknown agent type {agent_type!r}; expected one of: {known}")
    validate_value(result, schema)
    validate_semantics(normalized, result)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("agent_type", help="Agent type or fast/deep alias")
    parser.add_argument("--input", type=Path, help="JSON file; stdin when omitted")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        text = args.input.read_text(encoding="utf-8") if args.input else sys.stdin.read()
        result = parse_result_text(text)
        validate_result(args.agent_type, result)
    except (OSError, ContractError, json.JSONDecodeError) as exc:
        print(f"invalid: {exc}", file=sys.stderr)
        return 2
    print("valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
