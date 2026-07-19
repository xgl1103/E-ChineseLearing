from __future__ import annotations

from typing import Any

from backend.app.schemas import Lesson, ReportEntry, RuleValidationResult


MAX_REVIEW_LOOPS = 2


CONFIDENCE_MODULES = {
    "homework_extraction": "homework",
    "student_question_extraction": "student_questions",
    "pronunciation_reference_text": "pronunciation",
    "pronunciation_feedback": "pronunciation",
    "correction_extraction": "corrections",
    "overall_report_reliability": "overall_report",
}

FINALIZED_STATUSES = {"sent", "confirmed", "final", "ready_to_send"}
TONE_CLAIM_MARKERS = [
    "tone error",
    "wrong tone",
    "third tone",
    "fourth tone",
    "声调错误",
    "声调不准",
    "三声",
    "四声",
]


def _all_evidence_ids(lesson: Lesson) -> set[str]:
    return {
        item.evidence_id
        for group in (
            lesson.evidence.knowledge_points,
            lesson.evidence.teacher_questions,
            lesson.evidence.homework,
            lesson.evidence.corrections,
            lesson.evidence.student_questions,
            lesson.evidence.pronunciation,
        )
        for item in group
    }


def _all_report_entries(lesson: Lesson) -> list[tuple[str, ReportEntry]]:
    return [
        *[(f"knowledge_points[{index}]", item) for index, item in enumerate(lesson.draft_report.knowledge_points)],
        *[(f"teacher_questions[{index}]", item) for index, item in enumerate(lesson.draft_report.teacher_questions)],
        *[(f"student_questions[{index}]", item) for index, item in enumerate(lesson.draft_report.student_questions)],
        *[(f"corrections[{index}]", item) for index, item in enumerate(lesson.draft_report.corrections)],
        *[
            (f"next_lesson_suggestions[{index}]", item)
            for index, item in enumerate(lesson.draft_report.next_lesson_suggestions)
        ],
    ]


def _student_assessment_source_ids(value: Any) -> list[str]:
    if hasattr(value, "source_evidence_ids"):
        return list(value.source_evidence_ids)
    if isinstance(value, dict):
        direct = value.get("source_evidence_ids")
        if isinstance(direct, list):
            return [str(item) for item in direct]
        nested: list[str] = []
        for item in value.values():
            if isinstance(item, dict) and isinstance(item.get("source_evidence_ids"), list):
                nested.extend(str(source_id) for source_id in item["source_evidence_ids"])
        return nested
    return []


def _has_tone_level_evidence(assessment: object) -> bool:
    return any(
        hasattr(assessment, attribute)
        for attribute in ("tone_scores", "tone_errors", "tone_level_results")
    )


def validate_rules(lesson: Lesson, revision_count: int = 0) -> Lesson:
    blocking: list[str] = []
    warnings: list[str] = []
    evidence_ids = _all_evidence_ids(lesson)

    required_evidence_groups = {
        "knowledge_points": lesson.evidence.knowledge_points,
        "teacher_questions": lesson.evidence.teacher_questions,
        "student_questions": lesson.evidence.student_questions,
        "corrections": lesson.evidence.corrections,
        "homework": lesson.evidence.homework,
        "pronunciation": lesson.evidence.pronunciation,
    }
    for group_name, items in required_evidence_groups.items():
        if not items:
            warnings.append(f"Evidence extractor produced no {group_name} evidence.")
        for item in items:
            missing_fields = [
                field
                for field in ("evidence_id", "type", "source_segment_ids", "timestamp", "claim", "confidence")
                if not getattr(item, field)
            ]
            if missing_fields:
                blocking.append(
                    f"Evidence item {item.evidence_id or '<missing id>'} is missing: {', '.join(missing_fields)}."
                )

    assessments_by_id = {
        assessment.assessment_id: assessment
        for assessment in lesson.pronunciation_assessments
    }
    for index, feedback in enumerate(lesson.draft_report.pronunciation_feedback):
        if not feedback.assessment_id or feedback.assessment_id not in assessments_by_id:
            blocking.append(
                "Pronunciation feedback must reference an existing pronunciation assessment."
            )
            continue
        if not feedback.source_evidence_ids or not set(feedback.source_evidence_ids) <= evidence_ids:
            blocking.append(
                f"Pronunciation feedback[{index}] must reference existing pronunciation evidence."
            )
        assessment = assessments_by_id[feedback.assessment_id]
        detail = feedback.detail.lower()
        if any(marker in detail for marker in TONE_CLAIM_MARKERS) and not _has_tone_level_evidence(assessment):
            blocking.append(
                f"Pronunciation feedback[{index}] makes a tone-level claim without tone-level evidence."
            )

    homework_evidence_ids = {item.evidence_id for item in lesson.evidence.homework}
    confirmed_homework = set(lesson.teacher_review.confirmed_homework_ids)
    for homework in lesson.draft_report.homework_items:
        has_homework_evidence = homework.source_evidence_id in homework_evidence_ids
        has_any_evidence = homework.source_evidence_id in evidence_ids
        is_confirmed = homework.homework_id in confirmed_homework or homework.teacher_confirmed
        if not has_any_evidence and not is_confirmed:
            blocking.append(
                f"Homework item {homework.homework_id} must have evidence or teacher confirmation."
            )
        if not has_homework_evidence and not homework.is_candidate:
            blocking.append(
                f"Homework item {homework.homework_id} uses non-homework evidence but is not marked as candidate."
            )
        if homework.is_candidate and homework.confidence == "high" and not homework.teacher_confirmation_required:
            blocking.append(
                f"Candidate homework {homework.homework_id} must be medium/low confidence or require teacher confirmation."
            )

    for label, entry in _all_report_entries(lesson):
        if not entry.source_evidence_ids:
            blocking.append(f"Draft report factual item {label} must reference source_evidence_ids.")
        elif not set(entry.source_evidence_ids) <= evidence_ids:
            blocking.append(f"Draft report factual item {label} references unknown evidence.")

    assessment_source_ids = _student_assessment_source_ids(lesson.draft_report.student_assessment)
    if lesson.draft_report.student_assessment and not assessment_source_ids:
        blocking.append("Student assessment must reference source_evidence_ids.")
    elif assessment_source_ids and not set(assessment_source_ids) <= evidence_ids:
        blocking.append("Student assessment references unknown evidence.")

    low_confidence_keys = [
        key for key, value in lesson.confidence_scores.items() if value in {"medium", "low"}
    ]
    if low_confidence_keys and not lesson.risk_highlights:
        blocking.append("Low-confidence content must appear in risk_highlights.")
    elif low_confidence_keys:
        covered_modules = {risk.module for risk in lesson.risk_highlights}
        for key in low_confidence_keys:
            module = CONFIDENCE_MODULES.get(key)
            if module is not None and module not in covered_modules:
                blocking.append(
                    f"Low-confidence {key} must appear in risk_highlights as module {module}."
                )

    if revision_count > MAX_REVIEW_LOOPS:
        blocking.append("Writer-Reviewer loop exceeded the maximum of 2 revisions.")

    if lesson.teacher_review.status != "confirmed":
        for audience, report in lesson.final_reports.model_dump().items():
            status = str(report.get("status", "")).lower()
            if status in FINALIZED_STATUSES:
                blocking.append(
                    f"Final report {audience} cannot be marked {status} before teacher confirmation."
                )

    if not lesson.draft_report.student_assessment:
        warnings.append("Student assessment is empty.")

    lesson.rule_validation_result = RuleValidationResult(
        pass_=not blocking,
        blocking_issues=blocking,
        warnings=warnings,
    )
    return lesson
