from __future__ import annotations

from dataclasses import replace
from typing import Callable

from engine.agent.provider import AgentProviderRequest, AgentProviderResolver, LLMProvider
from engine.agent.tools import AgentToolContext, AgentToolRegistry
from engine.agent.types import (
    AgentActionRequest,
    AgentActionStatus,
    AgentContentBlock,
    AgentEvent,
    AgentEventKind,
    AgentMessage,
    AgentMessageRole,
    AgentPermissionMode,
    AgentRuntimeConfig,
    AgentSession,
    AgentSuspension,
    AgentToolCall,
    AgentToolResult,
    AgentTurnState,
    AgentTurnStatus,
    AgentUsageRecord,
    new_id,
    utc_now_iso,
)

AppendEvent = Callable[[AgentSession, AgentEventKind, dict], AgentEvent]


class AgentRuntime:
    def __init__(
        self,
        *,
        tools: AgentToolRegistry,
        provider_resolver: AgentProviderResolver,
        tool_context_factory: Callable[[], AgentToolContext],
        append_event: AppendEvent,
        max_iterations_per_turn: int = 8,
    ) -> None:
        self.tools = tools
        self.provider_resolver = provider_resolver
        self.tool_context_factory = tool_context_factory
        self.append_event = append_event
        self.max_iterations_per_turn = int(max(1, max_iterations_per_turn))

    def start_turn(self, session: AgentSession, content: str) -> None:
        turn = AgentTurnState(
            turn_id=new_id("turn"),
            max_iterations=session.runtime_config.max_iterations_per_turn or self.max_iterations_per_turn,
        )
        session.active_turn = turn
        session.suspended_turn = None
        session.messages.append(
            AgentMessage(
                new_id("msg"),
                AgentMessageRole.USER,
                content,
                content_blocks=[AgentContentBlock.text_block(content)],
            )
        )
        self.append_event(session, AgentEventKind.MESSAGE_ADDED, {"role": AgentMessageRole.USER.value, "turn_id": turn.turn_id})
        self.append_event(session, AgentEventKind.TURN_STARTED, {"turn_id": turn.turn_id})
        self.continue_turn(session)

    def continue_turn(self, session: AgentSession) -> None:
        if session.active_turn is None:
            session.active_turn = AgentTurnState(
                turn_id=new_id("turn"),
                max_iterations=session.runtime_config.max_iterations_per_turn or self.max_iterations_per_turn,
            )
        turn = session.active_turn
        if turn.status == AgentTurnStatus.SUSPENDED:
            turn.status = AgentTurnStatus.RUNNING
            turn.suspended_action_id = ""
        provider = self.provider_resolver.resolve(session.provider_id)
        provider_metadata = self.provider_resolver.metadata_for(provider.provider_id).to_dict()

        while not session.cancelled:
            if turn.iteration >= turn.max_iterations:
                turn.status = AgentTurnStatus.LIMIT_REACHED
                turn.updated_at = utc_now_iso()
                session.messages.append(
                    AgentMessage(
                        new_id("msg"),
                        AgentMessageRole.ASSISTANT,
                        "Agent turn stopped after reaching the iteration limit.",
                        content_blocks=[AgentContentBlock.text_block("Agent turn stopped after reaching the iteration limit.")],
                    )
                )
                self.append_event(session, AgentEventKind.TURN_LIMIT_REACHED, {"turn_id": turn.turn_id})
                session.active_turn = None
                session.suspended_turn = None
                return

            request = AgentProviderRequest(
                session_id=session.session_id,
                turn_id=turn.turn_id,
                messages=list(session.messages),
                available_tools=self.tools.list_specs(),
                iteration=turn.iteration,
            )
            self.append_event(
                session,
                AgentEventKind.PROVIDER_STARTED,
                {
                    "turn_id": turn.turn_id,
                    "provider_id": provider.provider_id,
                    "iteration": turn.iteration,
                    "provider": provider_metadata,
                },
            )
            try:
                runtime_config = self._runtime_config(session, provider)
                if runtime_config.stream and bool(provider_metadata.get("supports_streaming")) and hasattr(provider, "stream_turn"):
                    response = self._run_streaming_provider(session, turn, provider, request, runtime_config)
                else:
                    response = provider.run_turn(request, runtime_config)
            except Exception as exc:
                turn.status = AgentTurnStatus.FAILED
                turn.updated_at = utc_now_iso()
                self.append_event(session, AgentEventKind.PROVIDER_FAILED, {"turn_id": turn.turn_id, "error": str(exc)})
                session.active_turn = None
                raise

            turn.iteration += 1
            turn.updated_at = utc_now_iso()
            assistant_message = self._assistant_message(response.content, response.tool_calls, response.content_blocks)
            session.messages.append(assistant_message)
            self.append_event(
                session,
                AgentEventKind.PROVIDER_COMPLETED,
                {
                    "turn_id": turn.turn_id,
                    "provider_id": response.provider_id,
                    "stop_reason": response.stop_reason,
                    "tool_call_count": len(response.tool_calls),
                },
            )
            self._record_usage(session, response)
            self.append_event(
                session,
                AgentEventKind.MESSAGE_ADDED,
                {"role": AgentMessageRole.ASSISTANT.value, "turn_id": turn.turn_id},
            )

            if not response.tool_calls:
                turn.status = AgentTurnStatus.COMPLETED
                turn.updated_at = utc_now_iso()
                self.append_event(session, AgentEventKind.TURN_COMPLETED, {"turn_id": turn.turn_id})
                session.active_turn = None
                session.suspended_turn = None
                return

            if self._execute_or_suspend_tool_calls(session, turn, response.tool_calls):
                return

        turn.status = AgentTurnStatus.CANCELLED
        turn.updated_at = utc_now_iso()
        session.active_turn = None
        session.suspended_turn = None

    def resolve_action(self, session: AgentSession, action: AgentActionRequest, approved: bool) -> None:
        if session.active_turn is None:
            session.active_turn = AgentTurnState(
                turn_id=action.turn_id or new_id("turn"),
                max_iterations=session.runtime_config.max_iterations_per_turn or self.max_iterations_per_turn,
            )
        if action.turn_id and session.active_turn.turn_id != action.turn_id:
            session.active_turn = replace(session.active_turn, turn_id=action.turn_id)
        turn = session.active_turn
        turn.status = AgentTurnStatus.RUNNING
        turn.suspended_action_id = ""
        session.suspended_turn = None
        action.resolved_at = utc_now_iso()

        if not approved:
            action.status = AgentActionStatus.REJECTED
            result = AgentToolResult(
                action.tool_call.tool_call_id,
                action.tool_call.tool_name,
                False,
                error="Action rejected by user.",
                data={"rejected": True},
            )
            action.result = result
            self._append_tool_result_message(session, result, turn.turn_id)
            self.append_event(session, AgentEventKind.ACTION_REJECTED, {"action_id": action.action_id, "turn_id": turn.turn_id})
            if self._suspend_if_pending_actions(session, turn):
                return
            self.continue_turn(session)
            return

        action.status = AgentActionStatus.APPROVED
        self.append_event(session, AgentEventKind.ACTION_APPROVED, {"action_id": action.action_id, "turn_id": turn.turn_id})
        result = self.tools.execute(action.tool_call, self.tool_context_factory())
        action.result = result
        action.status = AgentActionStatus.EXECUTED if result.success else AgentActionStatus.FAILED
        self._append_tool_result_message(session, result, turn.turn_id)
        if self._suspend_if_pending_actions(session, turn):
            return
        self.continue_turn(session)

    def _execute_or_suspend_tool_calls(
        self,
        session: AgentSession,
        turn: AgentTurnState,
        calls: list[AgentToolCall],
    ) -> bool:
        context = self.tool_context_factory()
        require_confirmation = session.permission_mode == AgentPermissionMode.CONFIRM_ACTIONS
        created_pending = False
        for call in calls:
            prepared = self.tools.prepare(call, context, require_confirmation=require_confirmation)
            if prepared.blocked_result is not None:
                self._append_tool_result_message(session, prepared.blocked_result, turn.turn_id)
                continue
            if prepared.requires_approval:
                action = AgentActionRequest(
                    action_id=new_id("agent-action"),
                    tool_call=prepared.call,
                    reason=prepared.reason,
                    preview=prepared.preview,
                    turn_id=turn.turn_id,
                )
                session.pending_actions.append(action)
                created_pending = True
                self.append_event(
                    session,
                    AgentEventKind.ACTION_REQUESTED,
                    {"action_id": action.action_id, "tool_name": call.tool_name, "turn_id": turn.turn_id},
                )
                continue
            result = self.tools.execute(prepared.call, context)
            self._append_tool_result_message(session, result, turn.turn_id)
        return self._suspend_if_pending_actions(session, turn) if created_pending else False

    def _pending_actions_for_turn(self, session: AgentSession, turn_id: str) -> list[AgentActionRequest]:
        return [
            action
            for action in session.pending_actions
            if action.status == AgentActionStatus.PENDING and (not action.turn_id or action.turn_id == turn_id)
        ]

    def _suspend_if_pending_actions(self, session: AgentSession, turn: AgentTurnState) -> bool:
        pending = self._pending_actions_for_turn(session, turn.turn_id)
        if not pending:
            session.suspended_turn = None
            turn.suspended_action_id = ""
            turn.status = AgentTurnStatus.RUNNING
            turn.updated_at = utc_now_iso()
            return False
        action = pending[0]
        suspension = AgentSuspension(
            action_id=action.action_id,
            turn_id=turn.turn_id,
            tool_call=action.tool_call,
            reason=action.reason,
            preview=action.preview,
        )
        session.suspended_turn = suspension
        turn.status = AgentTurnStatus.SUSPENDED
        turn.suspended_action_id = action.action_id
        turn.updated_at = utc_now_iso()
        self.append_event(session, AgentEventKind.TURN_SUSPENDED, suspension.to_dict())
        return True

    def _run_streaming_provider(
        self,
        session: AgentSession,
        turn: AgentTurnState,
        provider: LLMProvider,
        request: AgentProviderRequest,
        config: AgentRuntimeConfig,
    ):
        self.append_event(
            session,
            AgentEventKind.PROVIDER_STREAM_STARTED,
            {"turn_id": turn.turn_id, "provider_id": provider.provider_id, "iteration": turn.iteration},
        )
        final_response = None
        try:
            stream = getattr(provider, "stream_turn")(request, config)
            for event in stream:
                kind = str(getattr(event, "kind", ""))
                if kind == "text_delta":
                    self.append_event(session, AgentEventKind.ASSISTANT_DELTA, {"turn_id": turn.turn_id, "delta": getattr(event, "delta", "")})
                elif kind == "tool_use_delta":
                    self.append_event(session, AgentEventKind.TOOL_USE_DELTA, {"turn_id": turn.turn_id, **dict(getattr(event, "data", {}))})
                elif kind == "completed":
                    final_response = getattr(event, "response", None)
                elif kind == "failed":
                    self.append_event(
                        session,
                        AgentEventKind.PROVIDER_STREAM_FAILED,
                        {"turn_id": turn.turn_id, **dict(getattr(event, "data", {}))},
                    )
            if final_response is None:
                raise RuntimeError("Streaming provider completed without a final response.")
            self.append_event(
                session,
                AgentEventKind.PROVIDER_STREAM_COMPLETED,
                {"turn_id": turn.turn_id, "provider_id": provider.provider_id},
            )
            return final_response
        except Exception as exc:
            self.append_event(
                session,
                AgentEventKind.PROVIDER_STREAM_FAILED,
                {"turn_id": turn.turn_id, "error": str(exc)},
            )
            raise

    def _append_tool_result_message(self, session: AgentSession, result: AgentToolResult, turn_id: str) -> None:
        session.messages.append(
            AgentMessage(
                new_id("msg"),
                AgentMessageRole.TOOL,
                result.output if result.success else result.error,
                tool_result=result,
                content_blocks=[AgentContentBlock.tool_result_block(result)],
            )
        )
        self.append_event(
            session,
            AgentEventKind.TOOL_CALLED,
            {"tool_name": result.tool_name, "success": result.success, "turn_id": turn_id},
        )
        self.append_event(
            session,
            AgentEventKind.TOOL_RESULT_ADDED,
            {"tool_name": result.tool_name, "tool_call_id": result.tool_call_id, "turn_id": turn_id},
        )

    def _assistant_message(
        self,
        content: str,
        calls: list[AgentToolCall],
        blocks: list[AgentContentBlock],
    ) -> AgentMessage:
        if not blocks:
            blocks = [AgentContentBlock.text_block(content)] if content else []
            blocks.extend(AgentContentBlock.tool_use_block(call) for call in calls)
        return AgentMessage(
            new_id("msg"),
            AgentMessageRole.ASSISTANT,
            content,
            tool_calls=list(calls),
            content_blocks=list(blocks),
        )

    def _record_usage(self, session: AgentSession, response) -> None:
        usage = dict(getattr(response, "usage", {})) if isinstance(getattr(response, "usage", {}), dict) else {}
        if not usage:
            return
        input_tokens = usage.get("input_tokens", usage.get("prompt_tokens"))
        output_tokens = usage.get("output_tokens", usage.get("completion_tokens"))
        total_tokens = usage.get("total_tokens")
        try:
            input_value = int(input_tokens) if input_tokens is not None else None
        except (TypeError, ValueError):
            input_value = None
        try:
            output_value = int(output_tokens) if output_tokens is not None else None
        except (TypeError, ValueError):
            output_value = None
        try:
            total_value = int(total_tokens) if total_tokens is not None else None
        except (TypeError, ValueError):
            total_value = None
        if total_value is None and (input_value is not None or output_value is not None):
            total_value = int(input_value or 0) + int(output_value or 0)
        record = AgentUsageRecord(
            usage_id=new_id("agent-usage"),
            provider_id=response.provider_id,
            model=str(getattr(response, "model", "")),
            input_tokens=input_value,
            output_tokens=output_value,
            total_tokens=total_value,
            estimated_cost=None,
            currency="",
            status="unknown",
            raw=usage,
        )
        session.usage_records.append(record)

    def _runtime_config(self, session: AgentSession, provider: LLMProvider) -> AgentRuntimeConfig:
        config = session.runtime_config
        if config.provider_id != provider.provider_id:
            return AgentRuntimeConfig(
                provider_id=provider.provider_id,
                max_iterations_per_turn=config.max_iterations_per_turn or self.max_iterations_per_turn,
            )
        return config
