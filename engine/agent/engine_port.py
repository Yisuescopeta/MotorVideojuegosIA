from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from engine.api import EngineAPI
    from engine.project.project_service import ProjectService
    from engine.scenes.scene_manager import SceneManager


class AgentEnginePort(Protocol):
    def context_snapshot(self, args: dict[str, Any]) -> dict[str, Any]:
        ...

    def capabilities(self) -> dict[str, Any]:
        ...

    def authoring_execute(self, args: dict[str, Any]) -> dict[str, Any]:
        ...

    def validate(self, args: dict[str, Any], project_root: Path) -> dict[str, Any]:
        ...

    def verify(self, args: dict[str, Any], project_root: Path) -> dict[str, Any]:
        ...


class EngineAPIAgentEnginePort:
    def __init__(self, api: "EngineAPI") -> None:
        self.api = api

    def context_snapshot(self, args: dict[str, Any]) -> dict[str, Any]:
        from engine.workflows.ai_assist import build_project_context_snapshot

        snapshot = build_project_context_snapshot(
            self.api,
            snapshot_id=str(args.get("snapshot_id", "agent-context")),
        )
        return snapshot.to_dict()

    def capabilities(self) -> dict[str, Any]:
        from engine.ai import get_default_registry

        return get_default_registry().to_dict()

    def authoring_execute(self, args: dict[str, Any]) -> dict[str, Any]:
        from engine.workflows.ai_assist import AuthoringExecutionService
        from engine.workflows.ai_assist.types import (
            AuthoringEntityPropertyKind,
            AuthoringExecutionOperation,
            AuthoringExecutionOperationKind,
            AuthoringExecutionRequest,
        )

        allowed = {field.name for field in fields(AuthoringExecutionOperation)}
        operations = []
        for raw in args.get("operations", []):
            payload = {key: value for key, value in dict(raw).items() if key in allowed}
            payload["kind"] = AuthoringExecutionOperationKind(str(payload["kind"]))
            if payload.get("property_kind"):
                payload["property_kind"] = AuthoringEntityPropertyKind(str(payload["property_kind"]))
            operations.append(AuthoringExecutionOperation(**payload))
        request = AuthoringExecutionRequest(
            request_id=str(args.get("request_id", "agent-authoring")),
            label=str(args.get("label", "agent_authoring")),
            operations=operations,
            target_scene_ref=str(args.get("target_scene_ref", "")),
            metadata=dict(args.get("metadata", {})),
        )
        return AuthoringExecutionService(self.api).execute(request).to_dict()

    def validate(self, args: dict[str, Any], project_root: Path) -> dict[str, Any]:
        from engine.workflows.ai_assist import validate_scene_payload

        payload = args.get("scene_payload")
        if payload is None:
            path_value = args.get("path", "")
            if not path_value:
                try:
                    path_value = self.api.get_active_scene().get("path", "")
                except Exception:
                    path_value = ""
            path = _resolve_port_path(project_root, path_value, allow_missing=False)
            payload = json.loads(path.read_text(encoding="utf-8"))
        return validate_scene_payload(payload).to_dict()

    def verify(self, args: dict[str, Any], project_root: Path) -> dict[str, Any]:
        from engine.workflows.ai_assist import HeadlessVerificationService
        from engine.workflows.ai_assist.types import (
            HeadlessVerificationAssertion,
            HeadlessVerificationAssertionKind,
            HeadlessVerificationScenario,
        )

        scenario_data = dict(args.get("scenario", args))
        assertions = []
        for raw in scenario_data.get("assertions", []):
            payload = dict(raw)
            payload["kind"] = HeadlessVerificationAssertionKind(str(payload["kind"]))
            assertions.append(HeadlessVerificationAssertion(**payload))
        scenario_root = _resolve_port_path(
            project_root,
            scenario_data.get("project_root", "."),
            allow_missing=False,
        )
        if not scenario_root.is_dir():
            raise NotADirectoryError(scenario_root.as_posix())
        scenario = HeadlessVerificationScenario(
            scenario_id=str(scenario_data.get("scenario_id", "agent-verification")),
            project_root=scenario_root.as_posix(),
            scene_path=str(scenario_data.get("scene_path", "")),
            assertions=assertions,
            seed=scenario_data.get("seed"),
            play=bool(scenario_data.get("play", False)),
            step_frames=int(scenario_data.get("step_frames", 0)),
            recent_event_limit=int(scenario_data.get("recent_event_limit", 50)),
        )
        return HeadlessVerificationService().run(scenario).to_dict()


class EditorLiveAgentEnginePort:
    def __init__(self, *, game: Any, scene_manager: "SceneManager", project_service: "ProjectService") -> None:
        self.game = game
        self.scene_manager = scene_manager
        self.project_service = project_service
        self._api_port: EngineAPIAgentEnginePort | None = None

    def _port(self) -> EngineAPIAgentEnginePort:
        if self._api_port is None:
            from engine.api import EngineAPI
            from engine.api._runtime_bound import create_runtime_bound_engine_api

            api = create_runtime_bound_engine_api(
                EngineAPI,
                game=self.game,
                scene_manager=self.scene_manager,
                project_service=self.project_service,
            )
            self._api_port = EngineAPIAgentEnginePort(api)
        return self._api_port

    def context_snapshot(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._port().context_snapshot(args)

    def capabilities(self) -> dict[str, Any]:
        return self._port().capabilities()

    def authoring_execute(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._port().authoring_execute(args)

    def validate(self, args: dict[str, Any], project_root: Path) -> dict[str, Any]:
        return self._port().validate(args, project_root)

    def verify(self, args: dict[str, Any], project_root: Path) -> dict[str, Any]:
        return self._port().verify(args, project_root)


def _resolve_port_path(project_root: Path, path_value: Any, *, allow_missing: bool) -> Path:
    raw = str(path_value or ".").strip()
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = project_root / candidate
    resolved = candidate.expanduser().resolve()
    try:
        resolved.relative_to(project_root)
    except ValueError as exc:
        raise PermissionError(f"Path outside project root: {resolved.as_posix()}") from exc
    if not allow_missing and not resolved.exists():
        raise FileNotFoundError(resolved.as_posix())
    return resolved
