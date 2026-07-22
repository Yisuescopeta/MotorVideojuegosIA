"""Generate the reproducible G0 editor-migration inventory.

The inventory is intentionally read-only with respect to source code. It uses
the Python AST for import and public-surface data, then records conservative
textual candidates that need manual review before G0.5 closes legacy routes.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[1]
ENGINE_ROOT = "engine"
SOURCE_SUFFIX = ".py"
LEGACY_METHODS = frozenset(
    {
        "mark_edit_world_dirty",
        "sync_from_edit_world",
    }
)
INTEGRITY_BOUNDARY_METHODS = frozenset({"prepare_for_save"})
MUTATION_CALLS = frozenset(
    {
        "add_component",
        "create_entity",
        "destroy_entity",
        "remove_component",
        "remove_entity",
        "replace_component_data",
        "set_feature_metadata",
        "update_component",
        "update_component_properties",
    }
)
DIRECT_MUTATION_PATTERN = re.compile(
    r"\b(?:edit_world|active_world|world)\b[^=\n]*\.[A-Za-z_]\w*\s*"
    r"(?:\+=|-=|\*=|/=|(?<![=!<>])=(?!=))"
)
SCENE_MUTABLE_NAMES = frozenset(
    {
        "data",
        "entities_data",
        "feature_metadata",
        "find_entity",
        "find_entity_by_id",
        "find_entities",
        "rules_data",
    }
)


@dataclass(frozen=True)
class ImportEdge:
    source: str
    target: str
    line: int


@dataclass(frozen=True)
class SurfaceRecord:
    path: str
    line: int
    name: str
    kind: str
    mutable_candidate: bool
    reason: str


@dataclass(frozen=True)
class ConsumerRecord:
    path: str
    line: int
    category: str
    symbol: str
    evidence: str


def _python_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.joinpath(ENGINE_ROOT).rglob(f"*{SOURCE_SUFFIX}")
        if "__pycache__" not in path.parts
    )


def _relative_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _module_name(path: Path, root: Path) -> str:
    relative = path.relative_to(root).with_suffix("")
    return ".".join(relative.parts)


def _dotted_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _dotted_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def _decorator_name(node: ast.AST) -> str:
    if isinstance(node, ast.Call):
        return _dotted_name(node.func)
    return _dotted_name(node)


def _has_property_decorator(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return any(_decorator_name(decorator) == "property" for decorator in node.decorator_list)


def _scene_surface_records(tree: ast.AST, path: str) -> list[SurfaceRecord]:
    records: list[SurfaceRecord] = []
    for class_node in (node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)):
        if class_node.name != "Scene":
            continue
        for child in class_node.body:
            if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) or child.name.startswith("_"):
                continue
            is_property = _has_property_decorator(child)
            mutable = child.name in SCENE_MUTABLE_NAMES
            if is_property:
                reason = "public property; inspect returned value for mutability"
                kind = "property"
            else:
                reason = "public method; inspect returned or accepted payload"
                kind = "method"
            if child.name in {"data", "entities_data", "rules_data", "feature_metadata"}:
                mutable = True
                reason = "returns internal serializable container"
            elif child.name in SCENE_MUTABLE_NAMES:
                mutable = True
                reason = "returns or resolves internal entity/payload data"
            records.append(
                SurfaceRecord(
                    path=path,
                    line=child.lineno,
                    name=child.name,
                    kind=kind,
                    mutable_candidate=mutable,
                    reason=reason,
                )
            )
    return records


def _imports(tree: ast.AST, path: str, root: Path) -> list[ImportEdge]:
    source = _module_name(root.joinpath(path), root)
    edges: list[ImportEdge] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            edges.extend(ImportEdge(source, alias.name, node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            edges.append(ImportEdge(source, node.module, node.lineno))
    return edges


def _consumer_records(tree: ast.AST, path: str, source_lines: list[str]) -> list[ConsumerRecord]:
    records: list[ConsumerRecord] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            symbol = node.func.attr
            if symbol in LEGACY_METHODS:
                records.append(
                    ConsumerRecord(
                        path=path,
                        line=node.lineno,
                        category="legacy_sync_api",
                        symbol=symbol,
                        evidence=source_lines[node.lineno - 1].strip(),
                    )
                )
            elif symbol in INTEGRITY_BOUNDARY_METHODS:
                records.append(
                    ConsumerRecord(
                        path=path,
                        line=node.lineno,
                        category="integrity_boundary_api",
                        symbol=symbol,
                        evidence=source_lines[node.lineno - 1].strip(),
                    )
                )
            elif symbol in MUTATION_CALLS:
                records.append(
                    ConsumerRecord(
                        path=path,
                        line=node.lineno,
                        category="world_mutation_call_candidate",
                        symbol=symbol,
                        evidence=source_lines[node.lineno - 1].strip(),
                    )
                )
    for line_number, line in enumerate(source_lines, start=1):
        if DIRECT_MUTATION_PATTERN.search(line):
            records.append(
                ConsumerRecord(
                    path=path,
                    line=line_number,
                    category="direct_world_assignment_candidate",
                    symbol="attribute_assignment",
                    evidence=line.strip(),
                )
            )
    return records


def _parse(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8-sig"), filename=path.as_posix())


def build_inventory(repo_root: Path) -> dict[str, object]:
    files = _python_files(repo_root)
    imports: list[ImportEdge] = []
    surfaces: list[SurfaceRecord] = []
    consumers: list[ConsumerRecord] = []
    parse_errors: list[dict[str, str]] = []

    for path in files:
        relative = _relative_path(path, repo_root)
        source_lines = path.read_text(encoding="utf-8-sig").splitlines()
        try:
            tree = _parse(path)
        except SyntaxError as error:
            parse_errors.append(
                {
                    "path": relative,
                    "error": f"{error.msg} at line {error.lineno}",
                }
            )
            continue
        imports.extend(_imports(tree, relative, repo_root))
        surfaces.extend(_scene_surface_records(tree, relative))
        consumers.extend(_consumer_records(tree, relative, source_lines))

    category_counts = Counter(record.category for record in consumers)
    package_counts = Counter(edge.source.split(".")[0] for edge in imports)
    mutable_surfaces = [record for record in surfaces if record.mutable_candidate]
    boundary_edges = [
        edge
        for edge in imports
        if edge.source.startswith("engine.runtime")
        and (edge.target.startswith("engine.editor") or edge.target.startswith("engine.inspector"))
    ]

    return {
        "schema_version": 1,
        "inventory": "editor_migration_g0",
        "repository_root": repo_root.as_posix(),
        "scope": {
            "python_files": "engine/**/*.py",
            "ast_imports": True,
            "textual_candidates": True,
            "runtime_editor_boundary": True,
        },
        "metrics": {
            "python_files": len(files),
            "import_edges": len(imports),
            "scene_public_surfaces": len(surfaces),
            "scene_mutable_surface_candidates": len(mutable_surfaces),
            "legacy_sync_consumers": category_counts["legacy_sync_api"],
            "world_mutation_call_candidates": category_counts["world_mutation_call_candidate"],
            "direct_world_assignment_candidates": category_counts["direct_world_assignment_candidate"],
            "runtime_to_editor_boundary_edges": len(boundary_edges),
            "parse_errors": len(parse_errors),
        },
        "scene_mutable_surfaces": [record.__dict__ for record in mutable_surfaces],
        "scene_public_surfaces": [record.__dict__ for record in surfaces],
        "world_to_scene_consumers": [record.__dict__ for record in consumers],
        "runtime_to_editor_boundary_edges": [edge.__dict__ for edge in boundary_edges],
        "import_graph": [edge.__dict__ for edge in imports],
        "parse_errors": parse_errors,
        "package_import_counts": dict(sorted(package_counts.items())),
    }


def render_markdown(inventory: dict[str, object]) -> str:
    metrics = inventory["metrics"]
    assert isinstance(metrics, dict)
    lines = [
        "# OpenGame editor migration v4 — G0 baseline inventory",
        "",
        "Generated by `tools/editor_migration_inventory.py`.",
        "",
        "## Scope",
        "",
        "- AST inventory of `engine/**/*.py`.",
        "- Import graph and runtime-to-editor boundary candidates.",
        "- Public and mutable `Scene` surface candidates.",
        "- Conservative `World -> Scene` and direct-world-mutation candidates.",
        "",
        "## Metrics",
        "",
        "| Metric | Count |",
        "|---|---:|",
    ]
    for key, value in metrics.items():
        lines.append(f"| `{key}` | {value} |")

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "This report is an inventory, not an authority decision. Candidate records require owner, allowed scope, gate and removal condition before G0.5. Textual candidates are intentionally conservative and must be confirmed by focused tests.",
            "",
            "## Mutable `Scene` surfaces",
            "",
            "| Path | Line | Name | Reason |",
            "|---|---:|---|---|",
        ]
    )
    surfaces = inventory["scene_mutable_surfaces"]
    assert isinstance(surfaces, list)
    for record in surfaces:
        assert isinstance(record, dict)
        lines.append(
            f"| `{record['path']}` | {record['line']} | `{record['name']}` | {record['reason']} |"
        )

    lines.extend(
        [
            "",
            "## Consumer candidates",
            "",
            "| Path | Line | Category | Symbol | Evidence |",
            "|---|---:|---|---|---|",
        ]
    )
    consumers = inventory["world_to_scene_consumers"]
    assert isinstance(consumers, list)
    for record in consumers:
        assert isinstance(record, dict)
        evidence = str(record["evidence"]).replace("|", "\\|")
        lines.append(
            f"| `{record['path']}` | {record['line']} | `{record['category']}` | `{record['symbol']}` | `{evidence}` |"
        )
    lines.append("")
    return "\n".join(lines)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the G0 editor migration inventory.")
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--markdown-out", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    repo_root = args.repo_root.resolve()
    inventory = build_inventory(repo_root)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(inventory, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.markdown_out.write_text(render_markdown(inventory), encoding="utf-8")
    print(json.dumps(inventory["metrics"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
