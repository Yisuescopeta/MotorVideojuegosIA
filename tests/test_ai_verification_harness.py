import json
import tempfile
import unittest
from pathlib import Path

from engine.api import EngineAPI
from engine.serialization.schema import migrate_scene_data
from engine.workflows.ai_assist import (
    HeadlessVerificationAssertion,
    HeadlessVerificationAssertionKind,
    HeadlessVerificationScenario,
    HeadlessVerificationService,
    VerificationStatus,
)


def _transform(x: float = 10.0, y: float = 20.0) -> dict[str, float | bool]:
    return {
        "enabled": True,
        "x": x,
        "y": y,
        "rotation": 0.0,
        "scale_x": 1.0,
        "scale_y": 1.0,
    }


def _scene_payload(
    name: str,
    entities: list[dict[str, object]],
    *,
    feature_metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "name": name,
        "entities": entities,
        "rules": [],
        "feature_metadata": feature_metadata or {},
    }


class HeadlessVerificationHarnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self._temp_dir.name)
        self.project_root = self.root / "project"
        self.api = EngineAPI(project_root=self.project_root.as_posix())
        self.service = HeadlessVerificationService()

    def tearDown(self) -> None:
        self.api.shutdown()
        self._temp_dir.cleanup()

    def _write_scene(self, relative_path: str, payload: dict[str, object]) -> Path:
        path = self.project_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(migrate_scene_data(payload), indent=2), encoding="utf-8")
        return path

    def test_successful_verification_reports_pass_and_machine_friendly_results(self) -> None:
        self._write_scene(
            "levels/verification_scene.json",
            _scene_payload(
                "Verification Scene",
                [
                    {
                        "name": "Player",
                        "active": True,
                        "tag": "Player",
                        "layer": "Gameplay",
                        "components": {"Transform": _transform(10.0, 20.0)},
                    }
                ],
            ),
        )
        scenario = HeadlessVerificationScenario(
            scenario_id="scenario-pass",
            project_root=self.project_root.as_posix(),
            scene_path="levels/verification_scene.json",
            assertions=[
                HeadlessVerificationAssertion(
                    assertion_id="assert-entity",
                    kind=HeadlessVerificationAssertionKind.ENTITY_EXISTS,
                    entity_name="Player",
                ),
                HeadlessVerificationAssertion(
                    assertion_id="assert-component",
                    kind=HeadlessVerificationAssertionKind.COMPONENT_EXISTS,
                    entity_name="Player",
                    component_name="Transform",
                ),
                HeadlessVerificationAssertion(
                    assertion_id="assert-field",
                    kind=HeadlessVerificationAssertionKind.COMPONENT_FIELD_EQUALS,
                    entity_name="Player",
                    component_name="Transform",
                    field_path="x",
                    expected_value=10.0,
                ),
                HeadlessVerificationAssertion(
                    assertion_id="assert-scene",
                    kind=HeadlessVerificationAssertionKind.SELECTED_SCENE_IS,
                    expected_scene_path="levels/verification_scene.json",
                ),
                HeadlessVerificationAssertion(
                    assertion_id="assert-status",
                    kind=HeadlessVerificationAssertionKind.ENGINE_STATUS_SANITY,
                    expected_state="EDIT",
                    min_entity_count=1,
                    max_entity_count=1,
                ),
            ],
        )

        report = self.service.run(scenario)

        self.assertEqual(report.status, VerificationStatus.PASS)
        self.assertEqual(report.failure_summary, "")
        self.assertTrue(all(result.success for result in report.assertion_results))
        self.assertEqual(report.final_active_scene["path"], "levels/verification_scene.json")
        json.dumps(report.to_dict(), sort_keys=True)

    def test_failed_assertion_marks_report_failed_and_keeps_details(self) -> None:
        self._write_scene(
            "levels/failure_scene.json",
            _scene_payload(
                "Failure Scene",
                [
                    {
                        "name": "Player",
                        "active": True,
                        "tag": "Player",
                        "layer": "Gameplay",
                        "components": {"Transform": _transform(10.0, 20.0)},
                    }
                ],
            ),
        )
        scenario = HeadlessVerificationScenario(
            scenario_id="scenario-fail",
            project_root=self.project_root.as_posix(),
            scene_path="levels/failure_scene.json",
            assertions=[
                HeadlessVerificationAssertion(
                    assertion_id="assert-wrong-field",
                    kind=HeadlessVerificationAssertionKind.COMPONENT_FIELD_EQUALS,
                    entity_name="Player",
                    component_name="Transform",
                    field_path="x",
                    expected_value=99.0,
                ),
                HeadlessVerificationAssertion(
                    assertion_id="assert-still-runs",
                    kind=HeadlessVerificationAssertionKind.ENTITY_EXISTS,
                    entity_name="Player",
                ),
            ],
        )

        report = self.service.run(scenario)

        self.assertEqual(report.status, VerificationStatus.FAIL)
        self.assertEqual(len(report.assertion_results), 2)
        self.assertFalse(report.assertion_results[0].success)
        self.assertTrue(report.assertion_results[1].success)
        self.assertIn("Expected 'Transform.x' to equal", report.failure_summary)

    def test_scene_load_failure_stops_before_assertions(self) -> None:
        scenario = HeadlessVerificationScenario(
            scenario_id="scenario-missing-scene",
            project_root=self.project_root.as_posix(),
            scene_path="levels/missing_scene.json",
            assertions=[
                HeadlessVerificationAssertion(
                    assertion_id="assert-never-runs",
                    kind=HeadlessVerificationAssertionKind.ENTITY_EXISTS,
                    entity_name="Player",
                )
            ],
        )

        report = self.service.run(scenario)

        self.assertEqual(report.status, VerificationStatus.FAIL)
        self.assertEqual(report.assertion_results, [])
        self.assertTrue(any(result.step == "load_scene" and not result.success for result in report.setup_results))
        self.assertIn("Failed to load scene", report.failure_summary)

    def test_play_step_and_inspect_workflow(self) -> None:
        self._write_scene(
            "levels/play_scene.json",
            _scene_payload(
                "Play Scene",
                [
                    {
                        "name": "Player",
                        "active": True,
                        "tag": "Player",
                        "layer": "Gameplay",
                        "components": {"Transform": _transform(15.0, 25.0)},
                    }
                ],
            ),
        )
        scenario = HeadlessVerificationScenario(
            scenario_id="scenario-play",
            project_root=self.project_root.as_posix(),
            scene_path="levels/play_scene.json",
            play=True,
            step_frames=5,
            assertions=[
                HeadlessVerificationAssertion(
                    assertion_id="assert-play-status",
                    kind=HeadlessVerificationAssertionKind.ENGINE_STATUS_SANITY,
                    expected_state="PLAY",
                    min_frame=5,
                    min_entity_count=1,
                ),
                HeadlessVerificationAssertion(
                    assertion_id="assert-play-event",
                    kind=HeadlessVerificationAssertionKind.RECENT_EVENT_EXISTS,
                    event_name="on_play",
                ),
                HeadlessVerificationAssertion(
                    assertion_id="assert-transform",
                    kind=HeadlessVerificationAssertionKind.COMPONENT_FIELD_EQUALS,
                    entity_name="Player",
                    component_name="Transform",
                    field_path="y",
                    expected_value=25.0,
                ),
            ],
        )

        report = self.service.run(scenario)

        self.assertEqual(report.status, VerificationStatus.PASS)
        self.assertEqual(report.final_engine_status["frame"], 5)
        self.assertEqual(report.final_engine_status["state"], "PLAY")
        self.assertTrue(any(event["name"] == "on_play" for event in report.recent_events))

    def test_scene_flow_smoke_verification_uses_isolated_sub_run(self) -> None:
        self._write_scene(
            "levels/source_scene.json",
            _scene_payload(
                "Source Scene",
                [
                    {
                        "name": "Player",
                        "active": True,
                        "tag": "Player",
                        "layer": "Gameplay",
                        "components": {"Transform": _transform()},
                    }
                ],
                feature_metadata={"scene_flow": {"next_scene": "levels/target_scene.json"}},
            ),
        )
        self._write_scene(
            "levels/target_scene.json",
            _scene_payload(
                "Target Scene",
                [
                    {
                        "name": "TargetPlayer",
                        "active": True,
                        "tag": "Player",
                        "layer": "Gameplay",
                        "components": {"Transform": _transform(30.0, 40.0)},
                    }
                ],
            ),
        )
        good_scenario = HeadlessVerificationScenario(
            scenario_id="scenario-flow-pass",
            project_root=self.project_root.as_posix(),
            scene_path="levels/source_scene.json",
            assertions=[
                HeadlessVerificationAssertion(
                    assertion_id="assert-flow-load",
                    kind=HeadlessVerificationAssertionKind.SCENE_FLOW_TARGET_CAN_BE_LOADED,
                    scene_flow_key="next_scene",
                ),
                HeadlessVerificationAssertion(
                    assertion_id="assert-source-still-active",
                    kind=HeadlessVerificationAssertionKind.SELECTED_SCENE_IS,
                    expected_scene_path="levels/source_scene.json",
                ),
            ],
        )

        good_report = self.service.run(good_scenario)

        self.assertEqual(good_report.status, VerificationStatus.PASS)
        self.assertEqual(good_report.assertion_results[0].actual, "levels/target_scene.json")
        self.assertEqual(good_report.final_active_scene["path"], "levels/source_scene.json")

        bad_scenario = HeadlessVerificationScenario(
            scenario_id="scenario-flow-fail",
            project_root=self.project_root.as_posix(),
            scene_path="levels/source_scene.json",
            assertions=[
                HeadlessVerificationAssertion(
                    assertion_id="assert-flow-missing",
                    kind=HeadlessVerificationAssertionKind.SCENE_FLOW_TARGET_CAN_BE_LOADED,
                    scene_flow_key="menu_scene",
                )
            ],
        )

        bad_report = self.service.run(bad_scenario)

        self.assertEqual(bad_report.status, VerificationStatus.FAIL)
        self.assertFalse(bad_report.assertion_results[0].success)
        self.assertIn("not configured", bad_report.assertion_results[0].message)


if __name__ == "__main__":
    unittest.main()
