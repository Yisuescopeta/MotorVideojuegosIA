from __future__ import annotations

from dataclasses import dataclass
import json
from typing import TYPE_CHECKING, Any

from engine.agent.types import (
    AgentActionStatus,
    AgentEventKind,
    AgentMessage,
    AgentMessageRole,
    AgentPermissionMode,
    AgentRuntimeConfig,
    AgentSession,
    AgentToolCall,
    AgentTurnStatus,
    new_id,
    utc_now_iso,
)

if TYPE_CHECKING:
    from engine.agent.session_service import AgentSessionService


_CATEGORY_ORDER = {
    "ayuda": 0,
    "sesion": 1,
    "proveedor": 2,
    "permisos": 3,
    "memoria": 4,
    "workspace": 5,
    "motor": 6,
}


@dataclass(frozen=True)
class AgentSlashCommandSpec:
    name: str
    category: str
    short_description: str
    help_text: str
    argument_hint: str = ""
    aliases: tuple[str, ...] = ()
    visible: bool = True
    handler_name: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "slash_name": f"/{self.name}",
            "category": self.category,
            "short_description": self.short_description,
            "help_text": self.help_text,
            "argument_hint": self.argument_hint,
            "aliases": list(self.aliases),
            "visible": self.visible,
            "insert_text": f"/{self.name}" + (" " if self.argument_hint else ""),
        }


@dataclass(frozen=True)
class AgentSlashParsedCommand:
    raw_input: str
    raw_name: str
    name: str
    args: str


class AgentSlashCommandRegistry:
    def __init__(self, service: "AgentSessionService") -> None:
        self.service = service
        self._specs = self._build_specs()
        self._spec_index: dict[str, AgentSlashCommandSpec] = {}
        for spec in self._specs:
            self._spec_index[spec.name] = spec
            for alias in spec.aliases:
                self._spec_index[alias] = spec

    def list_commands(self) -> list[dict[str, Any]]:
        return [spec.to_dict() for spec in self._visible_specs()]

    def is_command_query(self, input_text: str) -> bool:
        text = str(input_text or "").lstrip()
        if not text.startswith("/") or "\n" in text:
            return False
        body = text[1:]
        return not any(char.isspace() for char in body)

    def suggest(self, input_text: str) -> list[dict[str, Any]]:
        if not self.is_command_query(input_text):
            return []
        query = str(input_text or "").lstrip()[1:].lower()
        suggestions: list[tuple[tuple[int, int, int, str], dict[str, Any]]] = []
        for spec in self._visible_specs():
            ranking = self._match_ranking(spec, query)
            if ranking is None:
                continue
            suggestions.append(
                (
                    ranking,
                    {
                        **spec.to_dict(),
                        "insert_text": f"/{spec.name} ",
                        "alias_display": ", ".join(f"/{alias}" for alias in spec.aliases),
                    },
                )
            )
        suggestions.sort(key=lambda item: item[0])
        return [item[1] for item in suggestions]

    def handle(self, session: AgentSession, content: str) -> dict[str, Any] | None:
        parsed = self.parse(content)
        if parsed is None:
            return None
        if not parsed.name:
            return self._build_response(
                session,
                parsed.raw_input,
                self._format_help_overview(),
            )
        spec = self._spec_index.get(parsed.name)
        if spec is None:
            return self._build_response(
                session,
                parsed.raw_input,
                f"Unknown command: /{parsed.raw_name}. Usa /help.",
            )
        handler = getattr(self, spec.handler_name)
        return handler(spec, session, parsed)

    def parse(self, content: str) -> AgentSlashParsedCommand | None:
        raw_input = str(content or "").strip()
        if not raw_input.startswith("/"):
            return None
        body = raw_input[1:]
        parts = body.split(maxsplit=1)
        raw_name = parts[0].strip().lower() if parts else ""
        args = parts[1].strip() if len(parts) > 1 else ""
        return AgentSlashParsedCommand(
            raw_input=raw_input,
            raw_name=raw_name,
            name=self._normalize_command_name(raw_name),
            args=args,
        )

    def _build_specs(self) -> tuple[AgentSlashCommandSpec, ...]:
        return (
            AgentSlashCommandSpec(
                name="help",
                category="ayuda",
                short_description="Muestra ayuda general o detallada.",
                help_text="Usa /help para ver el catalogo o /help <comando> para ver detalle.",
                argument_hint="[comando]",
                aliases=("h", "?"),
                handler_name="_handle_help",
            ),
            AgentSlashCommandSpec(
                name="status",
                category="sesion",
                short_description="Inspecciona la sesion activa.",
                help_text="Muestra provider, modelo, permisos, pendientes y estado de la sesion.",
                aliases=("estado",),
                handler_name="_handle_status",
            ),
            AgentSlashCommandSpec(
                name="new",
                category="sesion",
                short_description="Crea una sesion nueva conservando la configuracion activa.",
                help_text="Cancela la sesion actual y crea una nueva con el mismo provider, modelo y streaming.",
                aliases=("nueva",),
                handler_name="_handle_new",
            ),
            AgentSlashCommandSpec(
                name="clear",
                category="sesion",
                short_description="Limpia transcript y aprobaciones pendientes.",
                help_text="Borra mensajes y acciones pendientes de la sesion actual.",
                aliases=("cls",),
                handler_name="_handle_clear",
            ),
            AgentSlashCommandSpec(
                name="providers",
                category="proveedor",
                short_description="Lista providers disponibles.",
                help_text="Muestra providers registrados, estado de auth y si estan online.",
                aliases=("proveedores",),
                handler_name="_handle_providers",
            ),
            AgentSlashCommandSpec(
                name="provider",
                category="proveedor",
                short_description="Cambia o consulta el provider activo.",
                help_text="Sin argumentos muestra el provider activo. Con un id lo establece como predeterminado y actualiza la sesion si esta listo.",
                argument_hint="[provider_id]",
                aliases=("use",),
                handler_name="_handle_provider",
            ),
            AgentSlashCommandSpec(
                name="model",
                category="proveedor",
                short_description="Cambia o consulta el modelo activo.",
                help_text="Sin argumentos muestra el modelo. Con un valor lo aplica a la sesion actual.",
                argument_hint="[modelo]",
                aliases=("modelo",),
                handler_name="_handle_model",
            ),
            AgentSlashCommandSpec(
                name="login",
                category="proveedor",
                short_description="Inicia login seguro del provider.",
                help_text="Abre el flujo de login de Codex para OpenAI o pide API key segura para providers compatibles.",
                argument_hint="[provider]",
                aliases=("signin",),
                handler_name="_handle_login",
            ),
            AgentSlashCommandSpec(
                name="logout",
                category="proveedor",
                short_description="Cierra sesion del provider configurado.",
                help_text="Elimina credenciales del provider y vuelve la sesion actual a fake.",
                argument_hint="[provider]",
                aliases=("signout",),
                handler_name="_handle_logout",
            ),
            AgentSlashCommandSpec(
                name="permissions",
                category="permisos",
                short_description="Consulta o cambia el modo de permisos.",
                help_text="Permite alternar entre confirm_actions y full_access.",
                argument_hint="[confirm_actions|full_access]",
                aliases=("perms",),
                handler_name="_handle_permissions",
            ),
            AgentSlashCommandSpec(
                name="approvals",
                category="permisos",
                short_description="Lista aprobaciones pendientes.",
                help_text="Muestra acciones en espera de confirmacion y sus motivos.",
                aliases=("pending",),
                handler_name="_handle_approvals",
            ),
            AgentSlashCommandSpec(
                name="memory",
                category="memoria",
                short_description="Consulta la memoria compactada de la sesion.",
                help_text="Carga el resumen almacenado de la sesion actual.",
                aliases=("mem",),
                handler_name="_handle_memory",
            ),
            AgentSlashCommandSpec(
                name="compact",
                category="memoria",
                short_description="Compacta la sesion actual.",
                help_text="Genera un resumen persistente de la sesion y actualiza memory_summary.",
                aliases=("summary",),
                handler_name="_handle_compact",
            ),
            AgentSlashCommandSpec(
                name="cost",
                category="memoria",
                short_description="Muestra uso y coste estimado de la sesion.",
                help_text="Devuelve el agregado de tokens y coste estimado disponible.",
                aliases=("usage",),
                handler_name="_handle_cost",
            ),
            AgentSlashCommandSpec(
                name="tools",
                category="workspace",
                short_description="Lista las tools expuestas al runtime.",
                help_text="Muestra las tools registradas con el runtime del agente.",
                aliases=("herramientas",),
                handler_name="_handle_tools",
            ),
            AgentSlashCommandSpec(
                name="diff",
                category="workspace",
                short_description="Muestra git diff del proyecto o de una ruta.",
                help_text="Ejecuta la tool git_diff sobre todo el proyecto o sobre la ruta indicada.",
                argument_hint="[ruta]",
                aliases=("changes",),
                handler_name="_handle_diff",
            ),
            AgentSlashCommandSpec(
                name="context",
                category="motor",
                short_description="Captura el contexto del motor para IA.",
                help_text="Usa el engine port para generar un snapshot del proyecto y la escena activa.",
                argument_hint="[snapshot_id]",
                aliases=("ctx",),
                handler_name="_handle_context",
            ),
            AgentSlashCommandSpec(
                name="engine",
                category="motor",
                short_description="Lista capacidades expuestas por el motor.",
                help_text="Consulta el registro de capacidades AI-facing disponible en el engine port.",
                aliases=("caps",),
                handler_name="_handle_engine",
            ),
            AgentSlashCommandSpec(
                name="verify",
                category="motor",
                short_description="Ejecuta una verificacion headless minima.",
                help_text="Corre una verificacion headless sobre la escena activa o la ruta indicada.",
                argument_hint="[scene_path]",
                aliases=("check",),
                handler_name="_handle_verify",
            ),
            AgentSlashCommandSpec(
                name="review",
                category="workspace",
                short_description="Resumen minimo de cambios.",
                help_text="Compatibilidad legacy: orienta al uso de /diff para revisar cambios actuales.",
                visible=False,
                handler_name="_handle_review",
            ),
        )

    def _visible_specs(self) -> list[AgentSlashCommandSpec]:
        return sorted(
            [spec for spec in self._specs if spec.visible],
            key=lambda spec: (_CATEGORY_ORDER.get(spec.category, 99), spec.name),
        )

    def _match_ranking(self, spec: AgentSlashCommandSpec, query: str) -> tuple[int, int, int, str] | None:
        if not query:
            return (_CATEGORY_ORDER.get(spec.category, 99), 0, len(spec.name), spec.name)
        name = spec.name.lower()
        aliases = tuple(alias.lower() for alias in spec.aliases)
        description = spec.short_description.lower()
        if query == name:
            return (0, 0, len(name), name)
        if query in aliases:
            return (0, 1, len(name), name)
        if name.startswith(query):
            return (1, 0, len(name), name)
        if any(alias.startswith(query) for alias in aliases):
            return (1, 1, len(name), name)
        if query in name:
            return (2, 0, len(name), name)
        if any(query in alias for alias in aliases):
            return (2, 1, len(name), name)
        if query in description:
            return (3, 0, len(name), name)
        return None

    def _normalize_command_name(self, raw_name: str) -> str:
        return str(raw_name or "").strip().lstrip("/").lower()

    def _normalize_provider_id(self, provider_id: str) -> str:
        normalized = str(provider_id or "").strip().lower()
        if normalized in {"opencode", "opencodego", "go"}:
            return "opencode-go"
        return normalized

    def _build_response(
        self,
        session: AgentSession,
        raw_input: str,
        body: str,
        *,
        command_result: dict[str, Any] | None = None,
        record_transcript: bool = True,
        response_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if record_transcript:
            session.messages.append(AgentMessage(new_id("msg"), AgentMessageRole.USER, raw_input))
            if body:
                session.messages.append(AgentMessage(new_id("msg"), AgentMessageRole.ASSISTANT, body))
        session.active_turn = None
        session.suspended_turn = None
        session.updated_at = utc_now_iso()
        response = response_data if response_data is not None else session.to_dict()
        if command_result:
            response["command_result"] = command_result
        return response

    def _format_help_overview(self) -> str:
        grouped: dict[str, list[str]] = {}
        for spec in self._visible_specs():
            suffix = f" {spec.argument_hint}" if spec.argument_hint else ""
            grouped.setdefault(spec.category, []).append(
                f"/{spec.name}{suffix} - {spec.short_description}"
            )
        lines: list[str] = []
        for category, items in grouped.items():
            lines.append(f"[{category}]")
            lines.extend(items)
        return "\n".join(lines)

    def _format_command_help(self, spec: AgentSlashCommandSpec) -> str:
        lines = [f"/{spec.name} {spec.argument_hint}".rstrip(), spec.help_text]
        if spec.aliases:
            lines.append("Aliases: " + ", ".join(f"/{alias}" for alias in spec.aliases))
        lines.append(f"Categoria: {spec.category}")
        return "\n".join(lines)

    def _execute_tool(self, tool_name: str, args: dict[str, Any]) -> tuple[bool, str]:
        result = self.service.tools.execute(
            AgentToolCall(new_id("tool"), tool_name, args),
            self.service._tool_context(),
        )
        return result.success, result.output if result.success else result.error

    def _recommended_model_for_status(self, status: dict[str, Any]) -> str:
        return str(status.get("default_model", "") or "")

    def _handle_help(self, spec: AgentSlashCommandSpec, session: AgentSession, parsed: AgentSlashParsedCommand) -> dict[str, Any]:
        target_name = self._normalize_command_name(parsed.args.split()[0]) if parsed.args else ""
        target = self._spec_index.get(target_name) if target_name else None
        body = self._format_command_help(target) if target is not None else self._format_help_overview()
        return self._build_response(session, parsed.raw_input, body)

    def _handle_status(self, spec: AgentSlashCommandSpec, session: AgentSession, parsed: AgentSlashParsedCommand) -> dict[str, Any]:
        pending_count = len([action for action in session.pending_actions if action.status == AgentActionStatus.PENDING])
        provider = session.provider_metadata or self.service.provider_resolver.metadata_for(session.provider_id).to_dict()
        body = (
            f"Session {session.session_id} | mode={session.permission_mode.value} | "
            f"pending={pending_count} | provider={provider.get('provider_id', session.provider_id)} | "
            f"model={session.runtime_config.model or 'default'} | "
            f"kind={provider.get('provider_kind', 'unknown')} | offline={provider.get('offline', True)} | "
            f"test_only={provider.get('test_only', False)}"
        )
        return self._build_response(session, parsed.raw_input, body)

    def _handle_new(self, spec: AgentSlashCommandSpec, session: AgentSession, parsed: AgentSlashParsedCommand) -> dict[str, Any]:
        session.cancelled = True
        if session.active_turn is not None:
            session.active_turn.status = AgentTurnStatus.CANCELLED
        self.service._append_event(session, AgentEventKind.SESSION_CANCELLED, {"reason": "slash_new"})
        new_session = self.service.create_session(
            permission_mode=session.permission_mode.value,
            title=session.title or "Agent Session",
            provider_id=session.provider_id or "fake",
            model=session.runtime_config.model,
            temperature=session.runtime_config.temperature,
            max_tokens=session.runtime_config.max_tokens,
            stream=session.runtime_config.stream,
        )
        return self._build_response(
            session,
            parsed.raw_input,
            "",
            command_result={
                "action": "new_session",
                "previous_session_id": session.session_id,
                "session_id": new_session["session_id"],
                "message": "Nueva sesion creada.",
            },
            record_transcript=False,
            response_data=new_session,
        )

    def _handle_clear(self, spec: AgentSlashCommandSpec, session: AgentSession, parsed: AgentSlashParsedCommand) -> dict[str, Any]:
        session.messages.clear()
        session.pending_actions.clear()
        body = "Session messages and pending actions cleared."
        return self._build_response(session, parsed.raw_input, body)

    def _handle_providers(self, spec: AgentSlashCommandSpec, session: AgentSession, parsed: AgentSlashParsedCommand) -> dict[str, Any]:
        default_provider_id = str(self.service.get_provider_status().get("default_provider_id", "fake") or "fake")
        lines = []
        for provider in self.service.list_providers():
            marker = "*" if provider["provider_id"] == default_provider_id else "-"
            lines.append(
                f"{marker} {provider['provider_id']} kind={provider['provider_kind']} online={provider['online']} auth={provider.get('auth_status', 'missing')}"
            )
        return self._build_response(session, parsed.raw_input, "\n".join(lines))

    def _handle_provider(self, spec: AgentSlashCommandSpec, session: AgentSession, parsed: AgentSlashParsedCommand) -> dict[str, Any]:
        if not parsed.args:
            default_provider_id = str(self.service.get_provider_status().get("default_provider_id", "fake") or "fake")
            body = f"Provider actual: {session.provider_id} | default={default_provider_id}."
            return self._build_response(session, parsed.raw_input, body)
        provider_id = self._normalize_provider_id(parsed.args.split()[0])
        status = self.service._provider_metadata(provider_id)
        model = self._recommended_model_for_status(status)
        self.service.set_default_provider(provider_id, model=model)
        status = self.service._provider_metadata(provider_id)
        if provider_id == "fake" or bool(status.get("runtime_ready", False)) or bool(status.get("test_only", False)):
            session.provider_id = provider_id
            session.provider_metadata = status
            session.runtime_config = AgentRuntimeConfig(
                provider_id=provider_id,
                max_iterations_per_turn=session.runtime_config.max_iterations_per_turn,
                model=model or session.runtime_config.model,
                temperature=session.runtime_config.temperature,
                max_tokens=session.runtime_config.max_tokens,
                stream=bool(session.runtime_config.stream and status.get("supports_streaming", False)),
                compaction_message_budget=session.runtime_config.compaction_message_budget,
            )
            body = f"Provider set to {provider_id}."
        else:
            body = f"Provider {provider_id} guardado como predeterminado, pero requiere login antes de usarse."
        return self._build_response(session, parsed.raw_input, body)

    def _handle_model(self, spec: AgentSlashCommandSpec, session: AgentSession, parsed: AgentSlashParsedCommand) -> dict[str, Any]:
        if parsed.args:
            session.runtime_config = AgentRuntimeConfig(
                provider_id=session.runtime_config.provider_id,
                max_iterations_per_turn=session.runtime_config.max_iterations_per_turn,
                model=parsed.args,
                temperature=session.runtime_config.temperature,
                max_tokens=session.runtime_config.max_tokens,
                stream=session.runtime_config.stream,
                compaction_message_budget=session.runtime_config.compaction_message_budget,
            )
            body = f"Model set to {session.runtime_config.model}."
        else:
            body = f"Model: {session.runtime_config.model or 'default'}."
        return self._build_response(session, parsed.raw_input, body)

    def _handle_login(self, spec: AgentSlashCommandSpec, session: AgentSession, parsed: AgentSlashParsedCommand) -> dict[str, Any]:
        parts = [item.strip().lower() for item in parsed.args.split() if item.strip()]
        provider_id = self._normalize_provider_id(parts[0]) if parts else "opencode-go"
        mode = parts[1] if len(parts) > 1 else ""
        if provider_id == "status":
            return self._build_response(
                session,
                parsed.raw_input,
                _json_dump_line(self.service.get_provider_status()),
            )
        if provider_id == "openai" and mode not in {"api-key", "apikey", "key"}:
            result = self.service.prepare_managed_provider_login(
                provider_id,
                device_auth=mode in {"device", "device-auth", "code", "headless"},
            )
            return self._build_response(
                session,
                parsed.raw_input,
                "",
                command_result=result,
                record_transcript=False,
            )
        self.service.provider_resolver.resolve(provider_id)
        status = self.service._provider_metadata(provider_id)
        result = {
            "action": "open_login",
            "provider_id": provider_id,
            "provider": status,
            "message": f"Enter API key for {provider_id} in the secure login input.",
        }
        return self._build_response(
            session,
            parsed.raw_input,
            "",
            command_result=result,
            record_transcript=False,
        )

    def _handle_logout(self, spec: AgentSlashCommandSpec, session: AgentSession, parsed: AgentSlashParsedCommand) -> dict[str, Any]:
        provider_id = parsed.args.strip() or str(self.service.provider_settings_store.load().get("default_provider_id", "opencode-go"))
        result = self.service.logout_provider(provider_id)
        session.provider_id = "fake"
        session.runtime_config = AgentRuntimeConfig(
            provider_id="fake",
            max_iterations_per_turn=session.runtime_config.max_iterations_per_turn,
            model="fake",
            stream=False,
            compaction_message_budget=session.runtime_config.compaction_message_budget,
        )
        session.provider_metadata = self.service._provider_metadata("fake")
        payload = dict(result)
        payload["message"] = f"Provider {provider_id} desconectado."
        return self._build_response(
            session,
            parsed.raw_input,
            "",
            command_result=payload,
            record_transcript=False,
        )

    def _handle_permissions(self, spec: AgentSlashCommandSpec, session: AgentSession, parsed: AgentSlashParsedCommand) -> dict[str, Any]:
        if parsed.args:
            session.permission_mode = AgentPermissionMode(parsed.args)
            body = f"Permission mode set to {session.permission_mode.value}."
        else:
            body = f"Permission mode: {session.permission_mode.value}."
        return self._build_response(session, parsed.raw_input, body)

    def _handle_approvals(self, spec: AgentSlashCommandSpec, session: AgentSession, parsed: AgentSlashParsedCommand) -> dict[str, Any]:
        pending = [action for action in session.pending_actions if action.status == AgentActionStatus.PENDING]
        if not pending:
            return self._build_response(session, parsed.raw_input, "No pending approvals.")
        lines = [
            f"{action.tool_call.tool_name} ({action.action_id}) - {action.reason}"
            for action in pending
        ]
        return self._build_response(session, parsed.raw_input, "\n".join(lines))

    def _handle_memory(self, spec: AgentSlashCommandSpec, session: AgentSession, parsed: AgentSlashParsedCommand) -> dict[str, Any]:
        snapshot = self.service.memory_store.load_session_summary(session.session_id)
        if snapshot.errors:
            body = _json_dump_line({"memory": snapshot.to_dict(), "status": "memory_error"})
        else:
            body = snapshot.session_summary or "No session memory stored."
        return self._build_response(session, parsed.raw_input, body)

    def _handle_compact(self, spec: AgentSlashCommandSpec, session: AgentSession, parsed: AgentSlashParsedCommand) -> dict[str, Any]:
        result = self.service.compaction.compact(session)
        self.service._append_event(session, AgentEventKind.MESSAGE_ADDED, {"role": "system", "compaction": result})
        body = _json_dump_line({"compact": result})
        return self._build_response(session, parsed.raw_input, body)

    def _handle_cost(self, spec: AgentSlashCommandSpec, session: AgentSession, parsed: AgentSlashParsedCommand) -> dict[str, Any]:
        return self._build_response(
            session,
            parsed.raw_input,
            _json_dump_line(self.service.get_usage_from_session(session)),
        )

    def _handle_tools(self, spec: AgentSlashCommandSpec, session: AgentSession, parsed: AgentSlashParsedCommand) -> dict[str, Any]:
        lines = []
        for tool in self.service.list_tools():
            scope = str(tool.get("permission_scope", ""))
            suffix = f" [{scope}]" if scope else ""
            lines.append(f"{tool['name']}{suffix}")
        return self._build_response(session, parsed.raw_input, "\n".join(lines))

    def _handle_diff(self, spec: AgentSlashCommandSpec, session: AgentSession, parsed: AgentSlashParsedCommand) -> dict[str, Any]:
        success, body = self._execute_tool("git_diff", {"path": parsed.args})
        return self._build_response(session, parsed.raw_input, body if success else body)

    def _handle_context(self, spec: AgentSlashCommandSpec, session: AgentSession, parsed: AgentSlashParsedCommand) -> dict[str, Any]:
        args = {"snapshot_id": parsed.args} if parsed.args else {"snapshot_id": "agent-context"}
        success, body = self._execute_tool("engine_context", args)
        return self._build_response(session, parsed.raw_input, body)

    def _handle_engine(self, spec: AgentSlashCommandSpec, session: AgentSession, parsed: AgentSlashParsedCommand) -> dict[str, Any]:
        _success, body = self._execute_tool("engine_capabilities", {})
        return self._build_response(session, parsed.raw_input, body)

    def _handle_verify(self, spec: AgentSlashCommandSpec, session: AgentSession, parsed: AgentSlashParsedCommand) -> dict[str, Any]:
        if self.service.engine_port is None:
            return self._build_response(
                session,
                parsed.raw_input,
                "Engine port is not attached to this agent session.",
            )
        scene_path = parsed.args.strip()
        if not scene_path:
            snapshot = self.service.engine_port.context_snapshot({"snapshot_id": "agent-verify"})
            scene_path = str(snapshot.get("current_scene_path", "") or "")
        if not scene_path:
            return self._build_response(
                session,
                parsed.raw_input,
                "No active scene available for /verify.",
            )
        _success, body = self._execute_tool(
            "engine_verify",
            {
                "scenario_id": "agent-verify",
                "project_root": ".",
                "scene_path": scene_path,
                "assertions": [
                    {
                        "assertion_id": "scene-selected",
                        "kind": "selected_scene_is",
                        "expected_scene_path": scene_path,
                    },
                    {
                        "assertion_id": "engine-status",
                        "kind": "engine_status_sanity",
                        "expected_state": "EDIT",
                        "min_entity_count": 0,
                    },
                ],
            },
        )
        return self._build_response(session, parsed.raw_input, body)

    def _handle_review(self, spec: AgentSlashCommandSpec, session: AgentSession, parsed: AgentSlashParsedCommand) -> dict[str, Any]:
        return self._build_response(
            session,
            parsed.raw_input,
            "Review baseline: use /diff for current changes; automated review heuristics are not expanded in this iteration.",
        )


def _json_dump_line(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=True, sort_keys=True)
