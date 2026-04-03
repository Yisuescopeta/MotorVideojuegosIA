from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from engine.components.scene_entry_point import SceneEntryPoint
from engine.serialization.schema import migrate_scene_data, validate_scene_data


def resolve_scene_transition_target_path(
    source_scene_path: str | None,
    target_scene_path: str,
) -> Path | None:
    normalized_target = str(target_scene_path or "").strip()
    if not normalized_target:
        return None
    candidate = Path(normalized_target)
    if candidate.is_absolute():
        return candidate
    if not source_scene_path:
        return None
    source_dir = Path(source_scene_path).resolve().parent
    relative_to_scene_dir = (source_dir / candidate).resolve()
    if relative_to_scene_dir.exists():
        return relative_to_scene_dir
    return (source_dir.parent / candidate).resolve()


def load_scene_transition_payload(scene_path: Path | None) -> dict[str, Any] | None:
    if scene_path is None or not scene_path.exists():
        return None
    try:
        raw = json.loads(scene_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return None
    try:
        return migrate_scene_data(raw)
    except ValueError:
        return None


def _iter_scene_transition_actions(payload: dict[str, Any]) -> list[tuple[int, dict[str, Any]]]:
    results: list[tuple[int, dict[str, Any]]] = []
    entities = payload.get("entities", [])
    if not isinstance(entities, list):
        return results
    for index, entity in enumerate(entities):
        if not isinstance(entity, dict):
            continue
        components = entity.get("components", {})
        if not isinstance(components, dict):
            continue
        action = components.get("SceneTransitionAction")
        if isinstance(action, dict):
            results.append((index, action))
    return results


def list_scene_entry_points_from_payload(payload: dict[str, Any]) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for entity in payload.get("entities", []):
        if not isinstance(entity, dict):
            continue
        components = entity.get("components", {})
        if not isinstance(components, dict):
            continue
        entry_point = components.get("SceneEntryPoint")
        if not isinstance(entry_point, dict) or not bool(entry_point.get("enabled", True)):
            continue
        entry_id = str(entry_point.get("entry_id", "") or "").strip()
        if not entry_id:
            continue
        results.append(
            {
                "entry_id": entry_id,
                "label": str(entry_point.get("label", "") or "").strip(),
                "entity_name": str(entity.get("name", "") or "").strip(),
            }
        )
    return results


def list_scene_entry_points(
    source_scene_path: str | None,
    target_scene_path: str,
) -> list[dict[str, str]]:
    resolved_path = resolve_scene_transition_target_path(source_scene_path, target_scene_path)
    payload = load_scene_transition_payload(resolved_path)
    if payload is None:
        return []
    return list_scene_entry_points_from_payload(payload)


def find_scene_entry_point_in_world(world: Any, entry_id: str) -> Any | None:
    normalized_entry_id = str(entry_id or "").strip()
    if not normalized_entry_id:
        return None
    for entity in world.get_all_entities():
        component = entity.get_component(SceneEntryPoint) if hasattr(entity, "get_component") else None
        if component is None or not bool(getattr(component, "enabled", True)):
            continue
        if str(getattr(component, "entry_id", "") or "").strip() == normalized_entry_id:
            return entity
    return None


def validate_scene_transition_references(
    scene_data: dict[str, Any],
    *,
    scene_path: str | None,
) -> list[str]:
    try:
        payload = migrate_scene_data(scene_data)
    except ValueError as exc:
        return [f"$.scene_transition_references: invalid source scene payload ({exc})"]

    source_errors = validate_scene_data(payload)
    if source_errors:
        return source_errors

    errors: list[str] = []
    for index, action in _iter_scene_transition_actions(payload):
        action_path = f"$.entities[{index}].components.SceneTransitionAction"
        target_scene_path = str(action.get("target_scene_path", "") or "").strip()
        target_entry_id = str(action.get("target_entry_id", "") or "").strip()
        if not target_scene_path:
            errors.append(f"{action_path}.target_scene_path: expected non-empty string")
            continue

        resolved_path = resolve_scene_transition_target_path(scene_path, target_scene_path)
        if resolved_path is None or not resolved_path.exists():
            errors.append(
                f"{action_path}.target_scene_path: target scene '{target_scene_path}' does not exist"
            )
            continue

        target_payload = load_scene_transition_payload(resolved_path)
        if target_payload is None:
            errors.append(
                f"{action_path}.target_scene_path: target scene '{target_scene_path}' is unreadable or invalid"
            )
            continue

        target_errors = validate_scene_data(target_payload)
        if target_errors:
            errors.append(
                f"{action_path}.target_scene_path: target scene '{target_scene_path}' failed validation"
            )
            continue

        if not target_entry_id:
            continue

        entry_points = list_scene_entry_points_from_payload(target_payload)
        if not any(item["entry_id"] == target_entry_id for item in entry_points):
            errors.append(
                f"{action_path}.target_entry_id: target entry point '{target_entry_id}' was not found in destination scene"
            )
    return errors


def collect_project_scene_transitions(project_service: Any, scene_manager: Any) -> dict[str, list[dict[str, Any]]]:
    scene_records = _collect_scene_transition_records(project_service, scene_manager)
    rows: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    target_payload_cache: dict[str, dict[str, Any] | None] = {}

    for record in scene_records:
        payload = record.get("payload")
        if not isinstance(payload, dict):
            issues.append(
                {
                    "source_scene_name": record["scene_name"],
                    "source_scene_path": record["scene_path"],
                    "source_scene_key": record["scene_key"],
                    "source_scene_ref": record["scene_ref"],
                    "status": "error",
                    "messages": ["Scene file is unreadable or invalid"],
                    "can_open_source": bool(record["scene_ref"]),
                }
            )
            continue

        try:
            migrated_payload = migrate_scene_data(copy.deepcopy(payload))
        except ValueError as exc:
            issues.append(
                {
                    "source_scene_name": record["scene_name"],
                    "source_scene_path": record["scene_path"],
                    "source_scene_key": record["scene_key"],
                    "source_scene_ref": record["scene_ref"],
                    "status": "error",
                    "messages": [f"Scene payload is invalid: {exc}"],
                    "can_open_source": bool(record["scene_ref"]),
                }
            )
            continue

        structural_errors = validate_scene_data(migrated_payload)
        if structural_errors:
            issues.append(
                {
                    "source_scene_name": record["scene_name"],
                    "source_scene_path": record["scene_path"],
                    "source_scene_key": record["scene_key"],
                    "source_scene_ref": record["scene_ref"],
                    "status": "error",
                    "messages": [str(error) for error in structural_errors],
                    "can_open_source": bool(record["scene_ref"]),
                }
            )

        rows.extend(
            _extract_scene_transition_rows(
                record,
                migrated_payload,
                project_service=project_service,
                target_payload_cache=target_payload_cache,
                workspace_records=scene_records,
            )
        )

    summaries = _build_scene_transition_summaries(rows=rows, issues=issues)
    return {
        "summaries": summaries,
        "rows": rows,
        "issues": issues,
    }


def collect_project_scene_links(project_service: Any, scene_manager: Any) -> dict[str, list[dict[str, Any]]]:
    snapshot = collect_project_scene_transitions(project_service, scene_manager)
    rows = []
    for row in snapshot.get("rows", []):
        row_copy = copy.deepcopy(row)
        row_copy["is_authoring_row"] = bool(row_copy.get("has_scene_link", False) or row_copy.get("is_runtime_only", False))
        row_copy["link_mode"] = str(row_copy.get("scene_link_mode", "") or "")
        rows.append(row_copy)
    return {
        "rows": rows,
        "issues": copy.deepcopy(snapshot.get("issues", [])),
    }


def collect_flow_graph_data(project_service: Any, scene_manager: Any) -> dict[str, list[dict[str, Any]]]:
    snapshot = collect_project_scene_links(project_service, scene_manager)
    sidebar_items: list[dict[str, Any]] = []
    canvas_nodes: list[dict[str, Any]] = []
    canvas_edges: list[dict[str, Any]] = []
    issues = copy.deepcopy(snapshot.get("issues", []))

    authoring_rows = [copy.deepcopy(row) for row in snapshot.get("rows", []) if bool(row.get("has_scene_link", False))]
    runtime_only_rows = [
        copy.deepcopy(row)
        for row in snapshot.get("rows", [])
        if bool(row.get("is_runtime_only", False)) and not bool(row.get("has_scene_link", False))
    ]

    source_lookup: dict[tuple[str, str], dict[str, Any]] = {}
    for row in authoring_rows:
        source_ref = str(row.get("source_scene_ref", "") or row.get("source_scene_path", "") or row.get("source_scene_key", "") or "")
        entity_name = str(row.get("source_entity_name", "") or "")
        row["sidebar_key"] = f"sidebar::{source_ref}::{entity_name}"
        row["node_key"] = f"entity::{source_ref}::{entity_name}"
        row["target_entity_name"] = str(row.get("target_entity_name", "") or "")
        row["connected"] = bool(str(row.get("target_scene_path", "") or "").strip())
        source_lookup[(source_ref, entity_name)] = row
        sidebar_items.append(row)

    for row in runtime_only_rows:
        row["sidebar_key"] = f"runtime::{row.get('source_scene_ref', '') or row.get('source_scene_path', '') or row.get('source_scene_key', '')}::{row.get('source_entity_name', '')}"

    for row in authoring_rows:
        source_ref = str(row.get("source_scene_ref", "") or row.get("source_scene_path", "") or row.get("source_scene_key", "") or "")
        scene_view_state = scene_manager.get_scene_view_state(source_ref) if scene_manager is not None and hasattr(scene_manager, "get_scene_view_state") else {}
        flow_layout = scene_view_state.get("flow_layout", {}) if isinstance(scene_view_state, dict) else {}
        node_positions = flow_layout.get("nodes", {}) if isinstance(flow_layout, dict) else {}
        stored_position = node_positions.get(str(row.get("source_entity_name", "") or ""), {}) if isinstance(node_positions, dict) else {}
        canvas_nodes.append(
            {
                "node_key": row["node_key"],
                "kind": "entity",
                "scene_ref": source_ref,
                "scene_name": row.get("source_scene_name", ""),
                "entity_name": row.get("source_entity_name", ""),
                "label": row.get("source_entity_name", ""),
                "link_mode": row.get("link_mode", ""),
                "status": row.get("status", "ok"),
                "x": float(stored_position.get("x", 0.0) or 0.0),
                "y": float(stored_position.get("y", 0.0) or 0.0),
                "has_stored_position": bool(stored_position),
                "messages": list(row.get("messages", [])),
            }
        )

    created_target_nodes: set[str] = set()
    for row in authoring_rows:
        source_ref = str(row.get("source_scene_ref", "") or row.get("source_scene_path", "") or row.get("source_scene_key", "") or "")
        source_node_key = str(row.get("node_key", "") or "")
        target_scene_ref = str(row.get("target_scene_ref", "") or row.get("target_scene_path", "") or "")
        target_entity_name = str(row.get("target_entity_name", "") or "")
        target_entry_id = str(row.get("target_entry_id", "") or "")
        target_scene_path = str(row.get("target_scene_path", "") or "")
        if not target_scene_path:
            continue

        target_row = source_lookup.get((target_scene_ref, target_entity_name)) if target_entity_name else None
        if target_row is not None:
            target_node_key = str(target_row.get("node_key", "") or "")
        else:
            target_node_key = f"target::{target_scene_ref or target_scene_path}::{target_entity_name}::{target_entry_id}"
            if target_node_key not in created_target_nodes:
                scene_view_state = scene_manager.get_scene_view_state(source_ref) if scene_manager is not None and hasattr(scene_manager, "get_scene_view_state") else {}
                flow_layout = scene_view_state.get("flow_layout", {}) if isinstance(scene_view_state, dict) else {}
                target_positions = flow_layout.get("targets", {}) if isinstance(flow_layout, dict) else {}
                stored_position = target_positions.get(target_node_key, {}) if isinstance(target_positions, dict) else {}
                target_label = target_entity_name or str(row.get("target_scene_name", "") or target_scene_path)
                if target_entry_id:
                    target_label = f"{target_label} [{target_entry_id}]"
                canvas_nodes.append(
                    {
                        "node_key": target_node_key,
                        "kind": "target",
                        "source_scene_ref": source_ref,
                        "scene_ref": target_scene_ref or target_scene_path,
                        "scene_name": row.get("target_scene_name", "") or target_scene_path,
                        "entity_name": target_entity_name,
                        "label": target_label,
                        "link_mode": "",
                        "status": row.get("status", "ok"),
                        "x": float(stored_position.get("x", 0.0) or 0.0),
                        "y": float(stored_position.get("y", 0.0) or 0.0),
                        "has_stored_position": bool(stored_position),
                        "messages": list(row.get("messages", [])),
                    }
                )
                created_target_nodes.add(target_node_key)

        reciprocal = False
        if target_row is not None:
            reciprocal = (
                str(target_row.get("target_scene_ref", "") or target_row.get("target_scene_path", "") or "") == source_ref
                and str(target_row.get("target_entity_name", "") or "") == str(row.get("source_entity_name", "") or "")
            )
        edge_key = f"{source_node_key}->{target_node_key}"
        if reciprocal:
            pair_key = tuple(sorted([source_node_key, target_node_key]))
            edge_key = f"two-way::{pair_key[0]}::{pair_key[1]}"
            if any(existing.get("edge_key") == edge_key for existing in canvas_edges):
                continue
        canvas_edges.append(
            {
                "edge_key": edge_key,
                "source_node_key": source_node_key,
                "target_node_key": target_node_key,
                "connection_type": "two_way" if reciprocal else "one_way",
                "color_key": "purple" if reciprocal else "orange",
                "source_scene_ref": source_ref,
                "source_entity_name": row.get("source_entity_name", ""),
                "target_scene_ref": target_scene_ref or target_scene_path,
                "target_entity_name": target_entity_name,
                "target_entry_id": target_entry_id,
                "status": row.get("status", "ok"),
                "messages": list(row.get("messages", [])),
            }
        )

    return {
        "sidebar_items": sidebar_items,
        "runtime_only_items": runtime_only_rows,
        "canvas_nodes": canvas_nodes,
        "canvas_edges": canvas_edges,
        "issues": issues,
    }


def _collect_scene_transition_records(project_service: Any, scene_manager: Any) -> list[dict[str, Any]]:
    records_by_ref: dict[str, dict[str, Any]] = {}

    if scene_manager is not None and hasattr(scene_manager, "list_open_scenes"):
        for open_scene in scene_manager.list_open_scenes():
            key = str(open_scene.get("key", "") or "")
            path = str(open_scene.get("path", "") or "")
            scene_ref = path or key
            if not scene_ref:
                continue
            entry = scene_manager.resolve_entry(scene_ref) if hasattr(scene_manager, "resolve_entry") else None
            payload = None
            scene_name = str(open_scene.get("name", "") or scene_ref)
            if entry is not None and getattr(entry, "scene", None) is not None:
                payload = copy.deepcopy(entry.scene.to_dict())
                scene_name = str(getattr(entry.scene, "name", "") or scene_name)
                path = str(getattr(entry.scene, "source_path", None) or path)
            records_by_ref[scene_ref] = {
                "scene_name": scene_name,
                "scene_path": _normalize_project_scene_path(project_service, path),
                "scene_abs_path": Path(path).resolve().as_posix() if path else "",
                "scene_key": key,
                "scene_ref": scene_ref,
                "payload": payload,
                "is_open": True,
                "is_active": bool(open_scene.get("is_active", False)),
                "dirty": bool(open_scene.get("dirty", False)),
            }

    if project_service is not None and getattr(project_service, "has_project", False):
        for project_scene in project_service.list_project_scenes():
            relative_path = str(project_scene.get("path", "") or "")
            absolute_path = str(project_scene.get("absolute_path", "") or "")
            normalized_abs = Path(absolute_path).resolve().as_posix() if absolute_path else ""
            existing = None
            if normalized_abs:
                for record in records_by_ref.values():
                    if record.get("scene_abs_path") == normalized_abs:
                        existing = record
                        break
            if existing is not None:
                existing["scene_path"] = relative_path or existing["scene_path"]
                existing["scene_name"] = str(project_scene.get("name", "") or existing["scene_name"])
                continue

            payload = load_scene_transition_payload(Path(absolute_path)) if absolute_path else None
            records_by_ref[relative_path or normalized_abs] = {
                "scene_name": str(project_scene.get("name", "") or relative_path or "Scene"),
                "scene_path": relative_path,
                "scene_abs_path": normalized_abs,
                "scene_key": "",
                "scene_ref": relative_path or normalized_abs,
                "payload": payload,
                "is_open": False,
                "is_active": False,
                "dirty": False,
            }

    return sorted(
        records_by_ref.values(),
        key=lambda item: (
            str(item.get("scene_name", "")).lower(),
            str(item.get("scene_path", "") or item.get("scene_key", "")).lower(),
        ),
    )


def _normalize_project_scene_path(project_service: Any, scene_path: str) -> str:
    normalized = str(scene_path or "").strip()
    if not normalized:
        return ""
    if project_service is None:
        return normalized
    try:
        return str(project_service.to_relative_path(normalized) or normalized)
    except Exception:
        return normalized


def _extract_scene_transition_rows(
    scene_record: dict[str, Any],
    payload: dict[str, Any],
    *,
    project_service: Any,
    target_payload_cache: dict[str, dict[str, Any] | None],
    workspace_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    entities = payload.get("entities", [])
    if not isinstance(entities, list):
        return rows

    for entity in entities:
        if not isinstance(entity, dict):
            continue
        entity_name = str(entity.get("name", "") or "").strip() or "(Unnamed)"
        components = entity.get("components", {})
        if not isinstance(components, dict):
            continue

        scene_link = components.get("SceneLink") if isinstance(components.get("SceneLink"), dict) else None
        scene_link_enabled = bool(scene_link.get("enabled", True)) if scene_link is not None else False
        action = components.get("SceneTransitionAction") if isinstance(components.get("SceneTransitionAction"), dict) else None
        action_enabled = bool(action.get("enabled", True)) if action is not None else False
        triggers = _detect_scene_transition_triggers(components)
        source_base = {
            "source_scene_name": scene_record["scene_name"],
            "source_scene_path": scene_record["scene_path"],
            "source_scene_key": scene_record["scene_key"],
            "source_scene_ref": scene_record["scene_ref"],
            "source_entity_name": entity_name,
        }

        if scene_link is not None and scene_link_enabled:
            rows.append(
                _build_scene_link_row(
                    source_base,
                    scene_link=scene_link,
                    action=action if action_enabled else None,
                    triggers=triggers,
                    scene_record=scene_record,
                    project_service=project_service,
                    target_payload_cache=target_payload_cache,
                    workspace_records=workspace_records,
                )
            )
            continue

        if action_enabled and not triggers:
            rows.append(
                _build_transition_row(
                    source_base,
                        trigger_label="Missing Trigger",
                        action=action,
                        scene_record=scene_record,
                        project_service=project_service,
                        target_payload_cache=target_payload_cache,
                        workspace_records=workspace_records,
                        extra_messages=["Scene transition action has no trigger"],
                        forced_status="warning",
                )
            )
            continue

        if triggers and not action_enabled:
            for trigger_label in triggers:
                rows.append(
                    _build_transition_row(
                        source_base,
                        trigger_label=trigger_label,
                        action=None,
                        scene_record=scene_record,
                        project_service=project_service,
                        target_payload_cache=target_payload_cache,
                        workspace_records=workspace_records,
                        extra_messages=["Trigger uses scene transition but entity has no SceneTransitionAction"],
                        forced_status="error",
                    )
                )
            continue

        if action_enabled and triggers:
            for trigger_label in triggers:
                rows.append(
                    _build_transition_row(
                        source_base,
                        trigger_label=trigger_label,
                        action=action,
                        scene_record=scene_record,
                        project_service=project_service,
                        target_payload_cache=target_payload_cache,
                        workspace_records=workspace_records,
                    )
                )
    return rows


def _build_scene_link_row(
    source_base: dict[str, Any],
    *,
    scene_link: dict[str, Any],
    action: dict[str, Any] | None,
    triggers: list[str],
    scene_record: dict[str, Any],
    project_service: Any,
    target_payload_cache: dict[str, dict[str, Any] | None],
    workspace_records: list[dict[str, Any]],
) -> dict[str, Any]:
    link_mode = str(scene_link.get("link_mode", "") or "").strip()
    target_scene_path = str(scene_link.get("target_path", "") or "").strip()
    target_entity_name = str(scene_link.get("target_entity_name", "") or "").strip()
    target_entry_id = str(scene_link.get("target_entry_id", "") or "").strip()
    preview_label = str(scene_link.get("preview_label", "") or "").strip()
    flow_key = str(scene_link.get("flow_key", "") or "").strip()
    messages: list[str] = []
    forced_status: str | None = None

    if not target_scene_path:
        messages.append("Target scene is required")
    if action is None:
        messages.append("SceneLink is not materialized to runtime yet")
        forced_status = "warning"
    if link_mode:
        trigger_label = _scene_link_mode_to_label(link_mode)
    elif triggers:
        trigger_label = triggers[0]
    else:
        trigger_label = "Missing Trigger"
        messages.append("SceneLink has no trigger preset")
        forced_status = "warning"

    row = _build_transition_row(
        source_base,
        trigger_label=trigger_label,
        action=(
            {
                "target_scene_path": target_scene_path,
                "target_entry_id": target_entry_id,
            }
            if target_scene_path or target_entry_id
            else None
        ),
        scene_record=scene_record,
        project_service=project_service,
        target_payload_cache=target_payload_cache,
        workspace_records=workspace_records,
        extra_messages=messages,
        forced_status=forced_status,
    )
    row["has_scene_link"] = True
    row["is_runtime_only"] = False
    row["scene_link_mode"] = link_mode
    row["scene_link_preview_label"] = preview_label
    row["scene_link_flow_key"] = flow_key
    row["target_scene_path"] = target_scene_path
    row["target_entity_name"] = target_entity_name
    row["target_entry_id"] = target_entry_id
    return row


def _scene_link_mode_to_label(link_mode: str) -> str:
    normalized = str(link_mode or "").strip()
    if normalized == "ui_button":
        return "UI Button"
    if normalized == "interact_near":
        return "Interact Near"
    if normalized == "trigger_enter":
        return "Touch / Trigger"
    if normalized == "collision":
        return "Collision"
    return "Missing Trigger"


def _detect_scene_transition_triggers(components: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    button = components.get("UIButton")
    if isinstance(button, dict):
        on_click = button.get("on_click")
        if isinstance(on_click, dict) and str(on_click.get("type", "") or "").strip() == "run_scene_transition":
            labels.append("UI Button")

    interact = components.get("SceneTransitionOnInteract")
    if isinstance(interact, dict) and bool(interact.get("enabled", True)):
        labels.append("Interact Near")

    contact = components.get("SceneTransitionOnContact")
    if isinstance(contact, dict) and bool(contact.get("enabled", True)):
        mode = str(contact.get("mode", "trigger_enter") or "trigger_enter").strip()
        labels.append("Collision" if mode == "collision" else "Trigger Enter")

    death = components.get("SceneTransitionOnPlayerDeath")
    if isinstance(death, dict) and bool(death.get("enabled", True)):
        labels.append("Player Death")
    return labels


def _build_transition_row(
    source_base: dict[str, Any],
    *,
    trigger_label: str,
    action: dict[str, Any] | None,
    scene_record: dict[str, Any],
    project_service: Any,
    target_payload_cache: dict[str, dict[str, Any] | None],
    workspace_records: list[dict[str, Any]],
    extra_messages: list[str] | None = None,
    forced_status: str | None = None,
) -> dict[str, Any]:
    messages = list(extra_messages or [])
    target_scene_path = ""
    target_entry_id = ""
    target_scene_name = ""
    target_scene_ref = ""
    can_open_target = False

    if action is not None:
        target_scene_path = str(action.get("target_scene_path", "") or "").strip()
        target_entry_id = str(action.get("target_entry_id", "") or "").strip()
        if not target_scene_path:
            messages.append("Target scene is required")
        else:
            resolved_target = resolve_scene_transition_target_path(scene_record.get("scene_abs_path") or None, target_scene_path)
            if resolved_target is None or not resolved_target.exists():
                messages.append(f"Target scene '{target_scene_path}' does not exist")
            else:
                can_open_target = True
                target_scene_ref = _normalize_project_scene_path(project_service, resolved_target.as_posix())
                target_payload = _resolve_target_payload(
                    resolved_target.as_posix(),
                    workspace_records=workspace_records,
                    target_payload_cache=target_payload_cache,
                )
                if target_payload is None:
                    messages.append(f"Target scene '{target_scene_path}' is unreadable or invalid")
                else:
                    target_scene_name = str(target_payload.get("name", "") or Path(target_scene_path).stem or target_scene_path)
                    target_errors = validate_scene_data(copy.deepcopy(target_payload))
                    if target_errors:
                        messages.append(f"Target scene '{target_scene_path}' failed validation")
                    elif target_entry_id:
                        entry_points = list_scene_entry_points_from_payload(target_payload)
                        if not any(item["entry_id"] == target_entry_id for item in entry_points):
                            messages.append(
                                f"Target entry point '{target_entry_id}' was not found in destination scene"
                            )

    resolved_status = _resolve_scene_transition_status(messages)
    if forced_status == "error":
        status = "error"
    elif forced_status == "warning" and resolved_status != "error":
        status = "warning"
    else:
        status = resolved_status
    if not target_scene_name and target_scene_path:
        target_scene_name = Path(target_scene_path).stem or target_scene_path

    return {
        **source_base,
        "trigger_label": trigger_label,
        "target_scene_path": target_scene_path,
        "target_scene_name": target_scene_name,
        "target_entity_name": "",
        "target_entry_id": target_entry_id,
        "target_scene_ref": target_scene_ref or target_scene_path,
        "status": status,
        "messages": messages,
        "can_open_target": bool(can_open_target and target_scene_path),
        "has_scene_link": False,
        "is_runtime_only": action is not None,
        "scene_link_mode": "",
        "scene_link_preview_label": "",
        "scene_link_flow_key": "",
    }


def _resolve_target_payload(
    resolved_target_path: str,
    *,
    workspace_records: list[dict[str, Any]],
    target_payload_cache: dict[str, dict[str, Any] | None],
) -> dict[str, Any] | None:
    normalized_target = Path(resolved_target_path).resolve().as_posix()
    for record in workspace_records:
        if record.get("scene_abs_path") == normalized_target and isinstance(record.get("payload"), dict):
            return copy.deepcopy(record["payload"])
    if normalized_target not in target_payload_cache:
        target_payload_cache[normalized_target] = load_scene_transition_payload(Path(normalized_target))
    payload = target_payload_cache[normalized_target]
    return copy.deepcopy(payload) if isinstance(payload, dict) else None


def _resolve_scene_transition_status(messages: list[str]) -> str:
    if not messages:
        return "ok"
    if any(
        "required" in message.lower()
        or "does not exist" in message.lower()
        or "not found" in message.lower()
        or "invalid" in message.lower()
        or "failed validation" in message.lower()
        for message in messages
    ):
        return "error"
    return "warning"


def _build_scene_transition_summaries(
    *,
    rows: list[dict[str, Any]],
    issues: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}

    for row in rows:
        key = (str(row.get("source_scene_path", "") or ""), str(row.get("source_scene_key", "") or ""))
        summary = grouped.setdefault(
            key,
            {
                "source_scene_name": row["source_scene_name"],
                "source_scene_path": row["source_scene_path"],
                "source_scene_key": row["source_scene_key"],
                "source_scene_ref": row.get("source_scene_ref", ""),
                "destination_labels": [],
                "transition_count": 0,
                "error_count": 0,
            },
        )
        summary["transition_count"] += 1
        if str(row.get("status", "")) == "error":
            summary["error_count"] += 1
        target_label = str(row.get("target_scene_name", "") or row.get("target_scene_path", "") or "").strip()
        if target_label and target_label not in summary["destination_labels"]:
            summary["destination_labels"].append(target_label)

    for issue in issues:
        key = (str(issue.get("source_scene_path", "") or ""), str(issue.get("source_scene_key", "") or ""))
        summary = grouped.setdefault(
            key,
            {
                "source_scene_name": issue["source_scene_name"],
                "source_scene_path": issue["source_scene_path"],
                "source_scene_key": issue["source_scene_key"],
                "source_scene_ref": issue.get("source_scene_ref", ""),
                "destination_labels": [],
                "transition_count": 0,
                "error_count": 0,
            },
        )
        summary["error_count"] += 1

    return sorted(
        grouped.values(),
        key=lambda item: (
            str(item.get("source_scene_name", "")).lower(),
            str(item.get("source_scene_path", "") or item.get("source_scene_key", "")).lower(),
        ),
    )
