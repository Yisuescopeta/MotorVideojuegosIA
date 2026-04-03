from __future__ import annotations

from pathlib import Path
from typing import Any

from engine.api import EngineAPI
from engine.project.project_service import ProjectService
from engine.workflows.ai_assist.types import (
    HeadlessVerificationAssertion,
    HeadlessVerificationAssertionKind,
    HeadlessVerificationAssertionResult,
    HeadlessVerificationReport,
    HeadlessVerificationScenario,
    HeadlessVerificationSetupResult,
    VerificationStatus,
)


class HeadlessVerificationService:
    """Runs deterministic verification scenarios against a fresh headless engine instance."""

    def run(self, scenario: HeadlessVerificationScenario) -> HeadlessVerificationReport:
        setup_results: list[HeadlessVerificationSetupResult] = []
        assertion_results: list[HeadlessVerificationAssertionResult] = []
        final_status: dict[str, Any] = {}
        final_active_scene: dict[str, Any] = {}
        recent_events: list[dict[str, Any]] = []
        failure_summary = ""

        project_root = Path(scenario.project_root).expanduser().resolve()
        if not self._project_exists(project_root):
            failure_summary = f"Project not found or invalid: {project_root.as_posix()}"
            setup_results.append(
                HeadlessVerificationSetupResult(
                    step="validate_project",
                    success=False,
                    message=failure_summary,
                    data={"project_root": project_root.as_posix()},
                )
            )
            return HeadlessVerificationReport(
                scenario_id=scenario.scenario_id,
                status=VerificationStatus.FAIL,
                project_root=project_root.as_posix(),
                scene_path=scenario.scene_path,
                setup_results=setup_results,
                assertion_results=assertion_results,
                final_engine_status=final_status,
                final_active_scene=final_active_scene,
                recent_events=recent_events,
                failure_summary=failure_summary,
            )

        setup_results.append(
            HeadlessVerificationSetupResult(
                step="validate_project",
                success=True,
                message="Project manifest is valid.",
                data={"project_root": project_root.as_posix()},
            )
        )

        api = EngineAPI(project_root=project_root.as_posix())
        try:
            setup_results.append(
                HeadlessVerificationSetupResult(
                    step="initialize_engine",
                    success=True,
                    message="Headless engine initialized.",
                )
            )

            if scenario.seed is not None:
                seed_result = api.set_seed(scenario.seed)
                setup_results.append(
                    HeadlessVerificationSetupResult(
                        step="set_seed",
                        success=bool(seed_result.get("success")),
                        message=str(seed_result.get("message") or ""),
                        data={"seed": scenario.seed},
                    )
                )

            load_result = self._load_scene(api, scenario.scene_path)
            setup_results.append(load_result)
            if not load_result.success:
                failure_summary = load_result.message
                return HeadlessVerificationReport(
                    scenario_id=scenario.scenario_id,
                    status=VerificationStatus.FAIL,
                    project_root=project_root.as_posix(),
                    scene_path=scenario.scene_path,
                    setup_results=setup_results,
                    assertion_results=assertion_results,
                    final_engine_status=final_status,
                    final_active_scene=final_active_scene,
                    recent_events=recent_events,
                    failure_summary=failure_summary,
                )

            if scenario.play:
                try:
                    api.play()
                    setup_results.append(
                        HeadlessVerificationSetupResult(
                            step="play",
                            success=True,
                            message="Runtime entered play mode.",
                        )
                    )
                except Exception as exc:
                    message = f"Failed to enter play mode: {exc}"
                    setup_results.append(
                        HeadlessVerificationSetupResult(
                            step="play",
                            success=False,
                            message=message,
                        )
                    )
                    failure_summary = message
                    return HeadlessVerificationReport(
                        scenario_id=scenario.scenario_id,
                        status=VerificationStatus.FAIL,
                        project_root=project_root.as_posix(),
                        scene_path=scenario.scene_path,
                        setup_results=setup_results,
                        assertion_results=assertion_results,
                        final_engine_status=final_status,
                        final_active_scene=final_active_scene,
                        recent_events=recent_events,
                        failure_summary=failure_summary,
                    )

            if scenario.step_frames > 0:
                try:
                    api.step(scenario.step_frames)
                    setup_results.append(
                        HeadlessVerificationSetupResult(
                            step="step",
                            success=True,
                            message=f"Advanced runtime by {scenario.step_frames} frame(s).",
                            data={"frames": scenario.step_frames},
                        )
                    )
                except Exception as exc:
                    message = f"Failed to step runtime: {exc}"
                    setup_results.append(
                        HeadlessVerificationSetupResult(
                            step="step",
                            success=False,
                            message=message,
                            data={"frames": scenario.step_frames},
                        )
                    )
                    failure_summary = message
                    return HeadlessVerificationReport(
                        scenario_id=scenario.scenario_id,
                        status=VerificationStatus.FAIL,
                        project_root=project_root.as_posix(),
                        scene_path=scenario.scene_path,
                        setup_results=setup_results,
                        assertion_results=assertion_results,
                        final_engine_status=final_status,
                        final_active_scene=final_active_scene,
                        recent_events=recent_events,
                        failure_summary=failure_summary,
                    )

            final_status = api.get_status()
            final_active_scene = self._normalized_active_scene(api)
            recent_events = api.get_recent_events(scenario.recent_event_limit)
            context = {
                "status": final_status,
                "active_scene": final_active_scene,
                "recent_events": recent_events,
            }

            for assertion in scenario.assertions:
                assertion_results.append(
                    self._evaluate_assertion(
                        api=api,
                        scenario=scenario,
                        assertion=assertion,
                        context=context,
                    )
                )

            failed_assertions = [result for result in assertion_results if not result.success]
            if failed_assertions and not failure_summary:
                failure_summary = failed_assertions[0].message

            return HeadlessVerificationReport(
                scenario_id=scenario.scenario_id,
                status=VerificationStatus.PASS if not failed_assertions else VerificationStatus.FAIL,
                project_root=project_root.as_posix(),
                scene_path=scenario.scene_path,
                setup_results=setup_results,
                assertion_results=assertion_results,
                final_engine_status=final_status,
                final_active_scene=final_active_scene,
                recent_events=recent_events,
                failure_summary=failure_summary,
            )
        finally:
            api.shutdown()

    def _project_exists(self, project_root: Path) -> bool:
        if not project_root.exists():
            return False
        validator = ProjectService(project_root.as_posix(), auto_ensure=False)
        return validator.validate_project(project_root.as_posix())

    def _load_scene(self, api: EngineAPI, scene_path: str) -> HeadlessVerificationSetupResult:
        try:
            api.load_level(scene_path)
        except Exception as exc:
            return HeadlessVerificationSetupResult(
                step="load_scene",
                success=False,
                message=f"Failed to load scene '{scene_path}': {exc}",
                data={"scene_path": scene_path},
            )
        return HeadlessVerificationSetupResult(
            step="load_scene",
            success=True,
            message="Scene loaded successfully.",
            data={"scene_path": scene_path, "active_scene": api.get_active_scene()},
        )

    def _evaluate_assertion(
        self,
        *,
        api: EngineAPI,
        scenario: HeadlessVerificationScenario,
        assertion: HeadlessVerificationAssertion,
        context: dict[str, Any],
    ) -> HeadlessVerificationAssertionResult:
        if assertion.kind == HeadlessVerificationAssertionKind.ENTITY_EXISTS:
            return self._assert_entity_exists(api, assertion, should_exist=True)
        if assertion.kind == HeadlessVerificationAssertionKind.ENTITY_NOT_EXISTS:
            return self._assert_entity_exists(api, assertion, should_exist=False)
        if assertion.kind == HeadlessVerificationAssertionKind.COMPONENT_EXISTS:
            return self._assert_component_exists(api, assertion, should_exist=True)
        if assertion.kind == HeadlessVerificationAssertionKind.COMPONENT_NOT_EXISTS:
            return self._assert_component_exists(api, assertion, should_exist=False)
        if assertion.kind == HeadlessVerificationAssertionKind.COMPONENT_FIELD_EQUALS:
            return self._assert_component_field_equals(api, assertion)
        if assertion.kind == HeadlessVerificationAssertionKind.SELECTED_SCENE_IS:
            return self._assert_selected_scene_is(api, assertion)
        if assertion.kind == HeadlessVerificationAssertionKind.SCENE_FLOW_TARGET_CAN_BE_LOADED:
            return self._assert_scene_flow_target_can_be_loaded(scenario, assertion)
        if assertion.kind == HeadlessVerificationAssertionKind.RECENT_EVENT_EXISTS:
            return self._assert_recent_event_exists(assertion, context["recent_events"])
        if assertion.kind == HeadlessVerificationAssertionKind.ENGINE_STATUS_SANITY:
            return self._assert_engine_status_sanity(assertion, context["status"])
        return HeadlessVerificationAssertionResult(
            assertion_id=assertion.assertion_id,
            kind=assertion.kind,
            success=False,
            message=f"Unsupported assertion kind: {assertion.kind}",
        )

    def _assert_entity_exists(
        self,
        api: EngineAPI,
        assertion: HeadlessVerificationAssertion,
        *,
        should_exist: bool,
    ) -> HeadlessVerificationAssertionResult:
        entity = self._get_entity(api, assertion.entity_name)
        exists = entity is not None
        success = exists if should_exist else not exists
        message = (
            f"Entity '{assertion.entity_name}' exists."
            if success and should_exist
            else f"Entity '{assertion.entity_name}' does not exist."
            if success
            else f"Expected entity '{assertion.entity_name}' to exist."
            if should_exist
            else f"Expected entity '{assertion.entity_name}' to be absent."
        )
        return HeadlessVerificationAssertionResult(
            assertion_id=assertion.assertion_id,
            kind=assertion.kind,
            success=success,
            message=message,
            expected=should_exist,
            actual=exists,
        )

    def _assert_component_exists(
        self,
        api: EngineAPI,
        assertion: HeadlessVerificationAssertion,
        *,
        should_exist: bool,
    ) -> HeadlessVerificationAssertionResult:
        entity = self._get_entity(api, assertion.entity_name)
        component_exists = False
        if entity is not None:
            component_exists = assertion.component_name in entity.get("components", {})
        success = component_exists if should_exist else not component_exists
        if entity is None:
            message = f"Entity '{assertion.entity_name}' was not found."
        elif success and should_exist:
            message = f"Component '{assertion.component_name}' exists on '{assertion.entity_name}'."
        elif success:
            message = f"Component '{assertion.component_name}' is absent from '{assertion.entity_name}'."
        elif should_exist:
            message = f"Expected component '{assertion.component_name}' on '{assertion.entity_name}'."
        else:
            message = f"Expected component '{assertion.component_name}' to be absent from '{assertion.entity_name}'."
        return HeadlessVerificationAssertionResult(
            assertion_id=assertion.assertion_id,
            kind=assertion.kind,
            success=success,
            message=message,
            expected=should_exist,
            actual=component_exists,
        )

    def _assert_component_field_equals(
        self,
        api: EngineAPI,
        assertion: HeadlessVerificationAssertion,
    ) -> HeadlessVerificationAssertionResult:
        entity = self._get_entity(api, assertion.entity_name)
        if entity is None:
            return HeadlessVerificationAssertionResult(
                assertion_id=assertion.assertion_id,
                kind=assertion.kind,
                success=False,
                message=f"Entity '{assertion.entity_name}' was not found.",
                expected=assertion.expected_value,
                actual=None,
            )
        component = entity.get("components", {}).get(assertion.component_name)
        if not isinstance(component, dict):
            return HeadlessVerificationAssertionResult(
                assertion_id=assertion.assertion_id,
                kind=assertion.kind,
                success=False,
                message=f"Component '{assertion.component_name}' was not found on '{assertion.entity_name}'.",
                expected=assertion.expected_value,
                actual=None,
            )
        try:
            actual = self._resolve_field_path(component, assertion.field_path)
        except KeyError as exc:
            return HeadlessVerificationAssertionResult(
                assertion_id=assertion.assertion_id,
                kind=assertion.kind,
                success=False,
                message=f"Field path '{assertion.field_path}' was not found: {exc}",
                expected=assertion.expected_value,
                actual=None,
            )
        success = actual == assertion.expected_value
        return HeadlessVerificationAssertionResult(
            assertion_id=assertion.assertion_id,
            kind=assertion.kind,
            success=success,
            message=(
                f"Component field '{assertion.component_name}.{assertion.field_path}' matched expected value."
                if success
                else f"Expected '{assertion.component_name}.{assertion.field_path}' to equal the requested value."
            ),
            expected=assertion.expected_value,
            actual=actual,
        )

    def _assert_selected_scene_is(
        self,
        api: EngineAPI,
        assertion: HeadlessVerificationAssertion,
    ) -> HeadlessVerificationAssertionResult:
        active_scene = api.get_active_scene()
        actual = self._normalize_scene_path(api, str(active_scene.get("path", "") or ""))
        expected = self._normalize_scene_path(api, assertion.expected_scene_path)
        success = actual == expected
        return HeadlessVerificationAssertionResult(
            assertion_id=assertion.assertion_id,
            kind=assertion.kind,
            success=success,
            message=(
                f"Active scene matched '{expected}'."
                if success
                else f"Expected active scene '{expected}', got '{actual}'."
            ),
            expected=expected,
            actual=actual,
        )

    def _assert_scene_flow_target_can_be_loaded(
        self,
        scenario: HeadlessVerificationScenario,
        assertion: HeadlessVerificationAssertion,
    ) -> HeadlessVerificationAssertionResult:
        project_root = Path(scenario.project_root).expanduser().resolve()
        api = EngineAPI(project_root=project_root.as_posix())
        try:
            try:
                api.load_level(scenario.scene_path)
            except Exception as exc:
                return HeadlessVerificationAssertionResult(
                    assertion_id=assertion.assertion_id,
                    kind=assertion.kind,
                    success=False,
                    message=f"Failed to load source scene for flow check: {exc}",
                    expected=assertion.scene_flow_key,
                    actual="",
                )
            result = api.load_scene_flow_target(assertion.scene_flow_key)
            active_scene = api.get_active_scene()
            actual = self._normalize_scene_path(api, str(active_scene.get("path", "") or ""))
            return HeadlessVerificationAssertionResult(
                assertion_id=assertion.assertion_id,
                kind=assertion.kind,
                success=bool(result.get("success")),
                message=str(result.get("message") or ""),
                expected=assertion.scene_flow_key,
                actual=actual,
            )
        finally:
            api.shutdown()

    def _assert_recent_event_exists(
        self,
        assertion: HeadlessVerificationAssertion,
        recent_events: list[dict[str, Any]],
    ) -> HeadlessVerificationAssertionResult:
        matching_event = next(
            (
                event
                for event in recent_events
                if str(event.get("name", "") or "") == assertion.event_name
                and self._dict_subset(assertion.event_data_subset, event.get("data", {}))
            ),
            None,
        )
        success = matching_event is not None
        return HeadlessVerificationAssertionResult(
            assertion_id=assertion.assertion_id,
            kind=assertion.kind,
            success=success,
            message=(
                f"Recent event '{assertion.event_name}' was found."
                if success
                else f"Expected recent event '{assertion.event_name}'."
            ),
            expected={
                "name": assertion.event_name,
                "data_subset": dict(assertion.event_data_subset),
            },
            actual=matching_event,
        )

    def _assert_engine_status_sanity(
        self,
        assertion: HeadlessVerificationAssertion,
        status: dict[str, Any],
    ) -> HeadlessVerificationAssertionResult:
        problems: list[str] = []
        if assertion.expected_state and str(status.get("state", "")) != assertion.expected_state:
            problems.append(f"state={status.get('state')!r}")
        if assertion.min_frame is not None and int(status.get("frame", 0)) < assertion.min_frame:
            problems.append(f"frame={status.get('frame')!r}")
        if assertion.min_entity_count is not None and int(status.get("entity_count", 0)) < assertion.min_entity_count:
            problems.append(f"entity_count={status.get('entity_count')!r}")
        if assertion.max_entity_count is not None and int(status.get("entity_count", 0)) > assertion.max_entity_count:
            problems.append(f"entity_count={status.get('entity_count')!r}")
        success = not problems
        expected = {
            key: value
            for key, value in {
                "state": assertion.expected_state,
                "min_frame": assertion.min_frame,
                "min_entity_count": assertion.min_entity_count,
                "max_entity_count": assertion.max_entity_count,
            }.items()
            if value not in ("", None)
        }
        return HeadlessVerificationAssertionResult(
            assertion_id=assertion.assertion_id,
            kind=assertion.kind,
            success=success,
            message="Engine status satisfied sanity checks." if success else f"Engine status failed sanity checks: {', '.join(problems)}",
            expected=expected,
            actual=dict(status),
        )

    def _get_entity(self, api: EngineAPI, entity_name: str) -> dict[str, Any] | None:
        try:
            return api.get_entity(entity_name)
        except Exception:
            return None

    def _resolve_field_path(self, payload: dict[str, Any], field_path: str) -> Any:
        current: Any = payload
        for segment in [part for part in str(field_path or "").split(".") if part]:
            if not isinstance(current, dict) or segment not in current:
                raise KeyError(segment)
            current = current[segment]
        return current

    def _normalize_scene_path(self, api: EngineAPI, scene_path: str) -> str:
        normalized = str(scene_path or "").strip()
        if not normalized:
            return ""
        project_service = getattr(api, "project_service", None)
        if project_service is None:
            return normalized.replace("\\", "/")
        try:
            return project_service.to_relative_path(normalized)
        except Exception:
            return normalized.replace("\\", "/")

    def _normalized_active_scene(self, api: EngineAPI) -> dict[str, Any]:
        active_scene = dict(api.get_active_scene())
        if "path" in active_scene:
            active_scene["path"] = self._normalize_scene_path(api, str(active_scene.get("path", "") or ""))
        return active_scene

    def _dict_subset(self, expected: dict[str, Any], actual: Any) -> bool:
        if not expected:
            return True
        if not isinstance(actual, dict):
            return False
        for key, value in expected.items():
            if key not in actual:
                return False
            if isinstance(value, dict):
                if not self._dict_subset(value, actual[key]):
                    return False
            elif actual[key] != value:
                return False
        return True
