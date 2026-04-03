from __future__ import annotations

from typing import Any

from cli.script_executor import ScriptExecutor
from engine.api import EngineAPI
from engine.debug.golden_run import capture_headless_run
from engine.workflows.ai_assist.types import (
    VerificationEvidence,
    VerificationReport,
    VerificationStatus,
)


def verify_headless_capture(
    api: EngineAPI,
    *,
    frames: int,
    capture_every: int = 1,
    dt: float = 1.0 / 60.0,
) -> VerificationReport:
    if api.game is None or api.game.world is None:
        return VerificationReport(
            status=VerificationStatus.FAIL,
            executed_checks=["headless_capture"],
            evidences=[],
            runtime_details={},
            failure_summary="No active runtime world is available for headless capture.",
        )

    was_in_edit_mode = bool(getattr(api.game, "is_edit_mode", False))
    try:
        if was_in_edit_mode:
            api.play()
        report = capture_headless_run(api.game, frames=frames, capture_every=capture_every, dt=dt)
    except Exception as exc:
        return VerificationReport(
            status=VerificationStatus.FAIL,
            executed_checks=["headless_capture"],
            evidences=[],
            runtime_details={},
            failure_summary=f"Headless capture failed: {exc}",
        )
    finally:
        if was_in_edit_mode:
            api.stop()

    evidence = VerificationEvidence(
        kind="headless_capture",
        summary=f"Captured {len(report.get('captures', []))} state snapshots across {frames} frames.",
        details=report,
    )
    return VerificationReport(
        status=VerificationStatus.PASS,
        executed_checks=["headless_capture"],
        evidences=[evidence],
        runtime_details={
            "final_world_hash": report.get("final_world_hash", ""),
            "final_frame": report.get("final_frame", 0),
            "seed": report.get("seed"),
        },
        failure_summary="",
    )


def verify_script_commands(api: EngineAPI, commands: list[dict[str, Any]]) -> VerificationReport:
    if api.game is None:
        return VerificationReport(
            status=VerificationStatus.FAIL,
            executed_checks=["script_commands"],
            evidences=[],
            runtime_details={},
            failure_summary="Engine runtime is not initialized.",
        )

    executor = ScriptExecutor(api.game)
    executor.commands = [dict(command) for command in commands]
    success = executor.run_all()
    if not success:
        failure_message = str(executor.last_error) if executor.last_error is not None else "Script execution failed."
        return VerificationReport(
            status=VerificationStatus.FAIL,
            executed_checks=["script_commands"],
            evidences=[],
            runtime_details={"command_count": len(commands)},
            failure_summary=failure_message,
        )

    evidence = VerificationEvidence(
        kind="script_commands",
        summary=f"Executed {len(commands)} verification script commands successfully.",
        details={"command_count": len(commands)},
    )
    return VerificationReport(
        status=VerificationStatus.PASS,
        executed_checks=["script_commands"],
        evidences=[evidence],
        runtime_details={"command_count": len(commands)},
        failure_summary="",
    )

