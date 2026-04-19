from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from engine.agent.types import AgentEventKind, new_id, utc_now_iso


CURRENT_SCHEMA_VERSION = 2


class AgentSessionMigrationError(ValueError):
    pass


@dataclass(frozen=True)
class AgentSessionMigrationResult:
    payload: dict[str, Any]
    migrated: bool
    event: dict[str, Any] | None = None


class AgentSessionMigrator:
    def migrate_payload(self, data: Any) -> AgentSessionMigrationResult:
        if not isinstance(data, dict):
            raise AgentSessionMigrationError("Agent session payload must be a JSON object.")
        version = int(data.get("schema_version", 1) or 1)
        if version == CURRENT_SCHEMA_VERSION:
            return AgentSessionMigrationResult(dict(data), migrated=False)
        if version > CURRENT_SCHEMA_VERSION:
            raise AgentSessionMigrationError(
                f"Unsupported future agent session schema_version={version}; current={CURRENT_SCHEMA_VERSION}."
            )
        if version != 1:
            raise AgentSessionMigrationError(f"Unsupported legacy agent session schema_version={version}.")

        payload = deepcopy(data)
        session_id = str(payload.get("session_id", ""))
        if not session_id:
            raise AgentSessionMigrationError("Legacy agent session is missing session_id.")
        messages = payload.get("messages", [])
        if not isinstance(messages, list):
            raise AgentSessionMigrationError("Legacy agent session messages must be a list.")

        for message in messages:
            if not isinstance(message, dict):
                raise AgentSessionMigrationError("Legacy agent session contains a non-object message.")
            self._migrate_message(message)

        provider_id = str(payload.get("provider_id", "fake") or "fake")
        payload["schema_version"] = CURRENT_SCHEMA_VERSION
        payload.setdefault("provider_id", provider_id)
        payload.setdefault("runtime_config", {"provider_id": provider_id, "max_iterations_per_turn": 8})
        if not isinstance(payload.get("runtime_config"), dict):
            payload["runtime_config"] = {"provider_id": provider_id, "max_iterations_per_turn": 8}
        payload["runtime_config"].setdefault("provider_id", provider_id)
        payload["runtime_config"].setdefault("max_iterations_per_turn", 8)
        payload["runtime_config"].setdefault("model", "")
        payload["runtime_config"].setdefault("temperature", None)
        payload["runtime_config"].setdefault("max_tokens", None)
        payload["runtime_config"].setdefault("stream", False)
        payload["runtime_config"].setdefault("compaction_message_budget", 24)
        payload.setdefault("provider_metadata", {})
        payload.setdefault("memory_summary", "")
        payload.setdefault("usage_records", [])
        payload.setdefault("events", [])
        if not isinstance(payload["events"], list):
            payload["events"] = []

        pending_actions = payload.get("pending_actions", [])
        if not isinstance(pending_actions, list):
            raise AgentSessionMigrationError("Legacy pending_actions must be a list.")
        pending = [action for action in pending_actions if isinstance(action, dict) and action.get("status", "pending") == "pending"]
        if pending:
            self._migrate_pending_action(payload, pending[0], pending_actions)
        else:
            payload["active_turn"] = payload.get("active_turn") if isinstance(payload.get("active_turn"), dict) else None
            payload["suspended_turn"] = payload.get("suspended_turn") if isinstance(payload.get("suspended_turn"), dict) else None

        event = {
            "event_id": new_id("event"),
            "kind": AgentEventKind.SESSION_MIGRATED.value,
            "created_at": utc_now_iso(),
            "data": {"from_schema_version": version, "to_schema_version": CURRENT_SCHEMA_VERSION},
        }
        payload["events"].append(event)
        return AgentSessionMigrationResult(payload, migrated=True, event=event)

    def _migrate_message(self, message: dict[str, Any]) -> None:
        message.setdefault("message_id", new_id("msg"))
        message.setdefault("created_at", utc_now_iso())
        if isinstance(message.get("content_blocks"), list) and message["content_blocks"]:
            return
        blocks: list[dict[str, Any]] = []
        content = str(message.get("content", ""))
        if content:
            blocks.append({"kind": "text", "text": content, "tool_use": None, "tool_result": None})
        for raw_call in message.get("tool_calls", []):
            if not isinstance(raw_call, dict):
                continue
            blocks.append(
                {
                    "kind": "tool_use",
                    "text": "",
                    "tool_use": {"tool_call": dict(raw_call)},
                    "tool_result": None,
                }
            )
        tool_result = message.get("tool_result")
        if isinstance(tool_result, dict):
            blocks.append(
                {
                    "kind": "tool_result",
                    "text": "",
                    "tool_use": None,
                    "tool_result": {"tool_result": dict(tool_result)},
                }
            )
        message["content_blocks"] = blocks

    def _migrate_pending_action(
        self,
        payload: dict[str, Any],
        first_pending: dict[str, Any],
        pending_actions: list[Any],
    ) -> None:
        turn_id = str(first_pending.get("turn_id", "")) or new_id("turn")
        for action in pending_actions:
            if isinstance(action, dict) and action.get("status", "pending") == "pending":
                action["turn_id"] = str(action.get("turn_id", "")) or turn_id
        action_id = str(first_pending.get("action_id", "")) or new_id("agent-action")
        first_pending["action_id"] = action_id
        first_pending["turn_id"] = turn_id
        tool_call = dict(first_pending.get("tool_call", {})) if isinstance(first_pending.get("tool_call"), dict) else {}
        payload["active_turn"] = {
            "turn_id": turn_id,
            "status": "suspended",
            "iteration": 0,
            "max_iterations": int(payload.get("runtime_config", {}).get("max_iterations_per_turn", 8)),
            "suspended_action_id": action_id,
            "created_at": utc_now_iso(),
            "updated_at": utc_now_iso(),
        }
        payload["suspended_turn"] = {
            "action_id": action_id,
            "turn_id": turn_id,
            "tool_call": tool_call,
            "reason": str(first_pending.get("reason", "Legacy pending action migrated.")),
            "preview": str(first_pending.get("preview", "")),
            "created_at": str(first_pending.get("created_at", "")) or utc_now_iso(),
        }
