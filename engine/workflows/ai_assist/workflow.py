from __future__ import annotations

from engine.workflows.ai_assist.types import (
    AuthoringPlan,
    AuthoringRequest,
    ProjectContextSnapshot,
    ValidationReport,
    ValidationStatus,
    VerificationReport,
    VerificationStatus,
    WorkflowResultSummary,
    WorkflowStatus,
)


def summarize_workflow_result(
    request: AuthoringRequest,
    *,
    context: ProjectContextSnapshot,
    validation: ValidationReport,
    verification: VerificationReport | None = None,
    plan: AuthoringPlan | None = None,
    changed_targets: list[str] | None = None,
) -> WorkflowResultSummary:
    verification_status = verification.status if verification is not None else VerificationStatus.NOT_RUN

    if validation.status == ValidationStatus.FAIL:
        status = WorkflowStatus.BLOCKED
        next_step = "Resolve blocking validation issues before authoring."
    elif verification is not None and verification.status == VerificationStatus.FAIL:
        status = WorkflowStatus.FAILED
        next_step = "Investigate verification failure and rerun evidence capture."
    elif verification is not None and verification.status == VerificationStatus.PASS:
        status = WorkflowStatus.VERIFIED
        next_step = "Workflow foundation reports verified evidence."
    else:
        status = WorkflowStatus.READY
        next_step = "Authoring workflow can proceed."

    return WorkflowResultSummary(
        workflow_id=request.workflow_id,
        status=status,
        context_snapshot_id=context.snapshot_id,
        plan_id=plan.plan_id if plan is not None else "",
        changed_targets=list(changed_targets or []),
        validation_status=validation.status,
        verification_status=verification_status,
        next_step=next_step,
    )
