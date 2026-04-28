"""Read-only AI-native project compliance diagnostics."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from engine.levels.component_registry import create_default_registry
from engine.project.project_service import MOTOR_AI_FILE, START_HERE_FILE, ProjectService
from engine.serialization.schema import (
    CURRENT_SCENE_SCHEMA_VERSION,
    migrate_scene_data,
    validate_scene_data,
)


@dataclass(frozen=True)
class ComplianceFinding:
    code: str
    message: str
    path: str = ""

    def to_dict(self) -> dict[str, str]:
        data = {"code": self.code, "message": self.message}
        if self.path:
            data["path"] = self.path
        return data


_SKIP_SCAN_DIRS = {
    ".git",
    ".motor",
    ".mypy_cache",
    ".ruff_cache",
    "__pycache__",
    "build",
    "engine",
    "motor",
    "motorvideojuegosia.egg-info",
    "pyray",
    "tests",
    "tools",
}

_WINDOW_LOOP_PATTERNS = [
    re.compile(r"\bwhile\s+not\s+pyray\.window_should_close\s*\(", re.IGNORECASE),
    re.compile(r"\bwhile\s+not\s+raylib\.window_should_close\s*\(", re.IGNORECASE),
    re.compile(r"\bwhile\s+not\s+WindowShouldClose\s*\(", re.IGNORECASE),
    re.compile(r"\bwhile\s+not\s+rl\.window_should_close\s*\(", re.IGNORECASE),
]

_RENDER_LOOP_PATTERNS = [
    re.compile(r"\bpyray\.(init_window|begin_drawing|end_drawing)\s*\(", re.IGNORECASE),
    re.compile(r"\braylib\.(init_window|begin_drawing|end_drawing)\s*\(", re.IGNORECASE),
    re.compile(r"\b(init_window|begin_drawing|end_drawing|InitWindow|BeginDrawing|EndDrawing)\s*\(", re.IGNORECASE),
]


def run_ai_compliance(project_root: str | Path, *, strict: bool = False) -> dict[str, Any]:
    """Return read-only compliance diagnostics for an AI-authored project."""
    root = Path(project_root).expanduser().resolve()
    problems: list[ComplianceFinding] = []
    warnings: list[ComplianceFinding] = []
    checks: dict[str, Any] = {
        "project_path": root.as_posix(),
        "strict": strict,
    }

    project_service = _load_project_service(root, problems, checks)
    if project_service is not None:
        _check_bootstrap_files(root, warnings, checks)
        scenes = _discover_scenes(project_service, warnings, checks)
        selected_scene = _select_scene(project_service, scenes, warnings, checks)
        _check_scene_contract(root, selected_scene, problems, warnings, checks)
    else:
        scenes = []

    blocking_findings, warning_findings = _detect_external_runtime(root)
    checks["external_runtime_blocking_findings"] = [finding.to_dict() for finding in blocking_findings]
    checks["external_runtime_warning_findings"] = [finding.to_dict() for finding in warning_findings]
    external_runtime_detected = bool(blocking_findings or warning_findings)
    external_runtime_blocking = bool(blocking_findings)
    external_runtime_warnings = bool(warning_findings)
    if strict:
        problems.extend(blocking_findings)
    else:
        warnings.extend(blocking_findings)
    warnings.extend(warning_findings)

    native_scene_valid = bool(checks.get("selected_scene_valid"))
    if strict and not native_scene_valid:
        problems.append(
            ComplianceFinding(
                "native_scene_required",
                "strict mode requires at least one loadable native serialized scene",
            )
        )

    strict_pass = not problems and native_scene_valid and not external_runtime_blocking
    command_success = bool(checks.get("project_initializable")) and (strict_pass if strict else True)
    native_score = _calculate_native_score(checks, external_runtime_detected)

    recommended_next_actions = _recommend_actions(
        checks=checks,
        strict=strict,
        external_runtime_detected=external_runtime_detected,
        native_scene_valid=native_scene_valid,
    )

    return {
        "success": command_success,
        "native_score": native_score,
        "strict_pass": strict_pass,
        "external_runtime_detected": external_runtime_detected,
        "external_runtime_blocking": external_runtime_blocking,
        "external_runtime_warnings": external_runtime_warnings,
        "problems": [problem.to_dict() for problem in _dedupe_findings(problems)],
        "warnings": [warning.to_dict() for warning in _dedupe_findings(warnings)],
        "recommended_next_actions": recommended_next_actions,
        "checks": checks,
    }


def _load_project_service(
    root: Path,
    problems: list[ComplianceFinding],
    checks: dict[str, Any],
) -> ProjectService | None:
    checks["project_manifest_exists"] = (root / ProjectService.PROJECT_FILE).exists()
    if not checks["project_manifest_exists"]:
        problems.append(ComplianceFinding("project_manifest_missing", "project.json not found"))
        checks["project_initializable"] = False
        return None
    try:
        service = ProjectService(project_root=root, auto_ensure=False, read_only=True)
    except Exception as exc:
        problems.append(ComplianceFinding("project_init_failed", f"project is not initializable: {exc}"))
        checks["project_initializable"] = False
        return None
    checks["project_initializable"] = True
    checks["project_name"] = service.manifest.name if service.has_project else ""
    return service


def _check_bootstrap_files(root: Path, warnings: list[ComplianceFinding], checks: dict[str, Any]) -> None:
    motor_ai_path = root / MOTOR_AI_FILE
    start_here_path = root / START_HERE_FILE
    checks["motor_ai_exists"] = motor_ai_path.exists()
    checks["motor_ai_regenerable"] = True
    checks["start_here_exists"] = start_here_path.exists()
    checks["start_here_regenerable"] = True
    if not motor_ai_path.exists():
        warnings.append(
            ComplianceFinding(
                "motor_ai_missing",
                "motor_ai.json is missing but can be regenerated with motor project bootstrap-ai",
                MOTOR_AI_FILE,
            )
        )
    if not start_here_path.exists():
        warnings.append(
            ComplianceFinding(
                "start_here_missing",
                "START_HERE_AI.md is missing but can be regenerated with motor project bootstrap-ai",
                START_HERE_FILE,
            )
        )


def _discover_scenes(
    project_service: ProjectService,
    warnings: list[ComplianceFinding],
    checks: dict[str, Any],
) -> list[dict[str, str]]:
    levels_root = project_service.get_project_path("levels")
    scenes: list[dict[str, str]] = []
    if levels_root.exists():
        for path in sorted(levels_root.rglob("*.json")):
            if path.name.endswith(".meta.json"):
                continue
            rel_path = project_service.to_relative_path(path)
            scenes.append({"name": path.stem, "path": rel_path, "absolute_path": path.as_posix()})
    checks["scenes_detectable"] = bool(scenes)
    checks["scene_count"] = len(scenes)
    checks["detected_scenes"] = [{"name": item["name"], "path": item["path"]} for item in scenes]
    if not scenes:
        warnings.append(ComplianceFinding("no_scenes_detected", "no scene JSON files were found in the levels path"))
    return scenes


def _select_scene(
    project_service: ProjectService,
    scenes: list[dict[str, str]],
    warnings: list[ComplianceFinding],
    checks: dict[str, Any],
) -> dict[str, str] | None:
    candidates: list[str] = []
    editor_state = project_service.load_editor_state()
    for key in ("active_scene", "last_scene"):
        value = str(editor_state.get(key, "") or "").strip()
        if value:
            candidates.append(value)
    settings = project_service.load_project_settings()
    startup_scene = str(settings.get("startup_scene", "") or "").strip()
    if startup_scene:
        candidates.append(startup_scene)
    candidates.extend(scene["path"] for scene in scenes)

    seen: set[str] = set()
    scene_by_path = {scene["path"].replace("\\", "/"): scene for scene in scenes}
    for candidate in candidates:
        normalized = candidate.replace("\\", "/")
        if normalized in seen:
            continue
        seen.add(normalized)
        path = project_service.resolve_path(normalized)
        if path.exists():
            selected = scene_by_path.get(normalized) or {
                "name": path.stem,
                "path": project_service.to_relative_path(path),
                "absolute_path": path.as_posix(),
            }
            checks["selected_scene_path"] = selected["path"]
            return selected

    warnings.append(ComplianceFinding("no_active_scene_loadable", "no active, startup or fallback scene is loadable"))
    checks["selected_scene_path"] = ""
    return None


def _check_scene_contract(
    root: Path,
    selected_scene: dict[str, str] | None,
    problems: list[ComplianceFinding],
    warnings: list[ComplianceFinding],
    checks: dict[str, Any],
) -> None:
    if selected_scene is None:
        checks["selected_scene_valid"] = False
        return

    scene_path = Path(selected_scene["absolute_path"])
    rel_path = _relative_path(root, scene_path)
    try:
        raw_data = json.loads(scene_path.read_text(encoding="utf-8"))
        if not isinstance(raw_data, dict):
            raise ValueError("scene JSON root must be an object")
        migrated = migrate_scene_data(raw_data)
        schema_errors = validate_scene_data(migrated)
    except Exception as exc:
        checks["selected_scene_valid"] = False
        problems.append(ComplianceFinding("scene_not_loadable", f"selected scene is not loadable: {exc}", rel_path))
        return

    entities = migrated.get("entities", [])
    registered_components = set(create_default_registry().list_registered())
    unknown_components = sorted(
        {
            component_name
            for entity in entities
            if isinstance(entity, dict)
            for component_name in (entity.get("components", {}) or {}).keys()
            if component_name not in registered_components
        }
    )

    checks["selected_scene_valid"] = not schema_errors
    checks["scene_schema_version"] = migrated.get("schema_version")
    checks["scene_schema_supported"] = migrated.get("schema_version") == CURRENT_SCENE_SCHEMA_VERSION
    checks["serialized_entities_present"] = isinstance(entities, list) and bool(entities)
    checks["entity_count"] = len(entities) if isinstance(entities, list) else 0
    checks["unknown_components"] = unknown_components
    checks["scene_is_persistent_source"] = isinstance(entities, list) and all(
        isinstance(entity, dict) and isinstance(entity.get("components", {}), dict)
        for entity in entities
    )

    if schema_errors:
        problems.append(
            ComplianceFinding(
                "scene_schema_invalid",
                "selected scene does not satisfy the current scene schema: " + "; ".join(schema_errors[:3]),
                rel_path,
            )
        )
    if not checks["serialized_entities_present"]:
        problems.append(ComplianceFinding("serialized_entities_missing", "selected scene has no serialized entities", rel_path))
    if not checks["scene_is_persistent_source"]:
        problems.append(
            ComplianceFinding(
                "scene_source_contract_invalid",
                "selected scene does not expose entities/components as the persistent source of truth",
                rel_path,
            )
        )
    for component_name in unknown_components:
        warnings.append(
            ComplianceFinding(
                "unknown_component",
                f"component '{component_name}' is not registered in the public component registry",
                rel_path,
            )
        )


def _is_demo_or_legacy_path(rel_path: str) -> bool:
    lower = rel_path.lower().replace("\\", "/")
    return lower.startswith("demo/") or lower.startswith("examples/") or lower.startswith("docs/archive/")


def _is_demo_named(path: Path) -> bool:
    return "demo" in path.stem.lower()


def _detect_external_runtime(root: Path) -> tuple[list[ComplianceFinding], list[ComplianceFinding]]:
    blocking: list[ComplianceFinding] = []
    warnings: list[ComplianceFinding] = []
    for path in _iter_candidate_files(root):
        rel_path = _relative_path(root, path)
        lower_name = path.name.lower()
        content = _read_text(path)
        is_demo_path = _is_demo_or_legacy_path(rel_path)

        if lower_name == "run_game.py":
            finding = ComplianceFinding("external_runtime_run_game", "run_game.py suggests an alternate runtime entrypoint", rel_path)
            (warnings if is_demo_path else blocking).append(finding)

        if path.suffix.lower() == ".py":
            is_demo_py = is_demo_path or _is_demo_named(path)

            if any(pattern.search(content) for pattern in _WINDOW_LOOP_PATTERNS) or (
                "while " in content and any(pattern.search(content) for pattern in _RENDER_LOOP_PATTERNS)
            ):
                finding = ComplianceFinding(
                    "external_runtime_loop",
                    "python script appears to own a window/render loop outside the motor runtime",
                    rel_path,
                )
                (warnings if is_demo_py else blocking).append(finding)

            if re.search(r"^\s*(import|from)\s+(pyray|raylib)\b", content, re.MULTILINE):
                finding = ComplianceFinding(
                    "external_runtime_raylib",
                    "python script imports pyray/raylib directly outside the motor runtime",
                    rel_path,
                )
                (warnings if is_demo_py else blocking).append(finding)

            if re.search(r"\b(main\.py|HeadlessGame)\b", content) and "EngineAPI" not in content and "motor " not in content:
                finding = ComplianceFinding(
                    "external_runtime_internal_entrypoint",
                    "script invokes main.py or HeadlessGame without going through the public CLI/API",
                    rel_path,
                )
                (warnings if is_demo_py else blocking).append(finding)

        if path.suffix.lower() in {".bat", ".cmd"}:
            bat_lower = content.lower()
            if any(token in bat_lower for token in ("run_game.py", "main.py", "demo", "headlessgame")) and "motor " not in bat_lower:
                finding = ComplianceFinding(
                    "external_runtime_batch",
                    "batch script appears to launch an external demo/runtime as the main flow",
                    rel_path,
                )
                (warnings if is_demo_path else blocking).append(finding)

    return _dedupe_findings(blocking), _dedupe_findings(warnings)


def _iter_candidate_files(root: Path) -> list[Path]:
    result: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            rel = path.relative_to(root)
            rel_parts = rel.parts
            rel_str = rel.as_posix()
        except ValueError:
            continue
        # Skip docs/ except docs/archive/
        if rel_str.startswith("docs/") and not rel_str.startswith("docs/archive/"):
            continue
        if any(part in _SKIP_SCAN_DIRS for part in rel_parts[:-1]):
            continue
        if path.suffix.lower() in {".py", ".bat", ".cmd"}:
            result.append(path)
    return sorted(result)


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _relative_path(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _calculate_native_score(checks: dict[str, Any], external_runtime_detected: bool) -> int:
    score = 100
    penalties = [
        (not checks.get("project_initializable"), 25),
        (not checks.get("motor_ai_exists"), 5),
        (not checks.get("start_here_exists"), 5),
        (not checks.get("scenes_detectable"), 20),
        (not checks.get("selected_scene_valid"), 20),
        (not checks.get("scene_schema_supported"), 10),
        (not checks.get("serialized_entities_present"), 15),
        (not checks.get("scene_is_persistent_source"), 15),
        (bool(checks.get("unknown_components")), 5),
        (external_runtime_detected, 25),
    ]
    for applies, penalty in penalties:
        if applies:
            score -= penalty
    return max(0, min(100, score))


def _recommend_actions(
    *,
    checks: dict[str, Any],
    strict: bool,
    external_runtime_detected: bool,
    native_scene_valid: bool,
) -> list[str]:
    actions: list[str] = []
    if not checks.get("motor_ai_exists") or not checks.get("start_here_exists"):
        actions.append("Run 'motor project bootstrap-ai --project .' to regenerate AI bootstrap files.")
    if not checks.get("scenes_detectable"):
        actions.append("Create or restore a native scene under the configured levels path.")
    elif not native_scene_valid:
        actions.append("Fix the selected scene so it migrates to the supported serialized scene schema.")
    if not checks.get("serialized_entities_present"):
        actions.append("Represent gameplay objects as serialized Scene entities with registered components.")
    if checks.get("unknown_components"):
        actions.append("Register public components in engine/levels/component_registry.py or replace unknown component names.")
    if external_runtime_detected:
        actions.append("Route the playable flow through the public motor CLI or EngineAPI and keep external runtime scripts non-primary.")
    if strict and not actions:
        actions.append("No strict compliance action required.")
    return actions


def _dedupe_findings(findings: list[ComplianceFinding]) -> list[ComplianceFinding]:
    seen: set[tuple[str, str, str]] = set()
    result: list[ComplianceFinding] = []
    for finding in findings:
        key = (finding.code, finding.message, finding.path)
        if key in seen:
            continue
        seen.add(key)
        result.append(finding)
    return result
