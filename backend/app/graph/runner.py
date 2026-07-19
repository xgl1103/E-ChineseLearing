from __future__ import annotations

from copy import deepcopy
from typing import Literal

from backend.app.graph.nodes import (
    confidence_node,
    evidence_node,
    final_report_node,
    reviewer_node,
    route_after_review,
    rule_validator_node,
    teacher_review_gate_node,
    transcript_node,
    writer_node,
)
from backend.app.graph.state import GraphState
from backend.app.schemas import FinalReport, FinalReportSection, FinalReports, Lesson


MANUAL_REVIEW_STATUS = "manual_review_required"


def _mark_final_reports_manual_review_required(state: GraphState) -> None:
    state.lesson.final_reports = FinalReports(
        teacher=FinalReport(
            title="Teacher Report - Manual Review Required",
            audience="teacher",
            status=MANUAL_REVIEW_STATUS,
            sections=[
                FinalReportSection(
                    heading="Manual Review Required",
                    content=(
                        "The writer-reviewer loop reached its revision limit. "
                        "A teacher or operator must review the draft before final reports can be generated."
                    ),
                )
            ],
        ),
        student=FinalReport(
            title="Student Report - Pending",
            audience="student",
            status=MANUAL_REVIEW_STATUS,
            sections=[
                FinalReportSection(
                    heading="Pending Teacher Review",
                    content="This report is not ready to send.",
                )
            ],
        ),
        parent=FinalReport(
            title="Parent Report - Pending",
            audience="parent",
            status=MANUAL_REVIEW_STATUS,
            sections=[
                FinalReportSection(
                    heading="Pending Teacher Review",
                    content="This report is not ready to send.",
                )
            ],
        ),
    )


def run_analysis_graph(
    lesson: Lesson,
    *,
    include_pronunciation: bool = True,
    requested_agent_mode: Literal["mock", "real"] = "mock",
    max_revisions: int = 2,
) -> GraphState:
    state = GraphState(
        lesson=deepcopy(lesson),
        include_pronunciation=include_pronunciation,
        requested_agent_mode=requested_agent_mode,
        max_revisions=max_revisions,
    )

    state.add_event(
        "graph_start",
        "Analysis graph started.",
        status="pending",
        metadata={
            "include_pronunciation": include_pronunciation,
            "requested_agent_mode": requested_agent_mode,
            "max_revisions": max_revisions,
        },
    )
    for node in (transcript_node, evidence_node):
        state = node(state)

    while True:
        state = writer_node(state)
        state = confidence_node(state)
        state = rule_validator_node(state)
        state = reviewer_node(state)
        state = route_after_review(state)

        if state.route == "writer_revision":
            continue
        break

    if state.route == "teacher_review_gate":
        state = teacher_review_gate_node(state)
    elif state.route == "manual_review":
        state.add_event(
            "manual_review",
            "Workflow stopped for human review after revision loop limit.",
            route="manual_review",
            status="failed",
            metadata={"stopped_reason": state.stopped_reason},
        )

    state.add_event(
        "graph_end",
        "Analysis graph ended.",
        status="failed" if state.stopped_reason else "pending" if state.lesson.teacher_review.status != "confirmed" else "passed",
        metadata={
            "final_route": state.route,
            "revision_count": state.revision_count,
            "stopped_reason": state.stopped_reason,
            "rule_pass": state.lesson.rule_validation_result.pass_,
            "review_pass": state.lesson.review_result.pass_,
        },
    )
    return state


def run_finalization_graph(
    lesson: Lesson,
    *,
    audiences: list[str] | None = None,
    include_pronunciation: bool = True,
    requested_agent_mode: Literal["mock", "real"] = "mock",
    max_revisions: int = 2,
) -> GraphState:
    if not lesson.draft_report.lesson_summary:
        state = run_analysis_graph(
            lesson,
            include_pronunciation=include_pronunciation,
            requested_agent_mode=requested_agent_mode,
            max_revisions=max_revisions,
        )
    else:
        state = GraphState(
            lesson=deepcopy(lesson),
            include_pronunciation=include_pronunciation,
            requested_agent_mode=requested_agent_mode,
            max_revisions=max_revisions,
            revision_count=lesson.review_result.revision_count,
        )
        state.add_event(
            "graph_start",
            "Finalization graph started from existing analyzed lesson.",
            status="pending",
            metadata={
                "teacher_review_status": lesson.teacher_review.status,
                "audiences": audiences or ["teacher", "student", "parent"],
            },
        )
        if (
            not lesson.rule_validation_result.pass_
            or not lesson.review_result.pass_
        ) and lesson.review_result.revision_count >= max_revisions:
            state.stopped_reason = "max_revision_loop_reached"
            state.route = "manual_review"

    if state.stopped_reason or state.route == "manual_review":
        _mark_final_reports_manual_review_required(state)
        state.add_event(
            "manual_review",
            "Finalization stopped because analysis requires manual review.",
            route="manual_review",
            status="failed",
            metadata={"stopped_reason": state.stopped_reason},
        )
    else:
        state = teacher_review_gate_node(state)

    if state.route == "final_report":
        state = final_report_node(state, audiences=audiences)
    elif state.route == "end":
        state.lesson = final_report_node(state, audiences=audiences).lesson
        state.add_event(
            "conditional_edge",
            "Final reports were generated as drafts because teacher review is pending.",
            route="end",
            status="pending",
        )

    state.add_event(
        "graph_end",
        "Finalization graph ended.",
        status="failed" if state.stopped_reason else "pending" if state.lesson.teacher_review.status != "confirmed" else "passed",
        metadata={
            "teacher_review_status": state.lesson.teacher_review.status,
            "final_report_statuses": {
                "teacher": state.lesson.final_reports.teacher.status,
                "student": state.lesson.final_reports.student.status,
                "parent": state.lesson.final_reports.parent.status,
            },
        },
    )
    return state
