from __future__ import annotations

from backend.app.schemas import Confidence, EvidenceItem, Lesson, RiskHighlight


def _combine_confidence(values: list[Confidence]) -> Confidence:
    if not values:
        return "low"
    if "low" in values:
        return "low"
    if "medium" in values or "unknown" in values:
        return "medium"
    return "high"


def _segment_confidence(lesson: Lesson, evidence_items: list[EvidenceItem]) -> Confidence:
    segments = {
        segment.segment_id: segment
        for segment in [*lesson.transcripts.teacher, *lesson.transcripts.student]
    }
    source_ids = [
        source_id
        for item in evidence_items
        for source_id in item.source_segment_ids
    ]
    if not evidence_items or not source_ids:
        return "low"
    if any(source_id not in segments for source_id in source_ids):
        return "low"
    min_asr = min(segments[source_id].asr_confidence for source_id in source_ids)
    if min_asr >= 0.9:
        return "high"
    if min_asr >= 0.82:
        return "medium"
    return "low"


def _evidence_completeness(evidence_items: list[EvidenceItem]) -> Confidence:
    if not evidence_items:
        return "low"
    for item in evidence_items:
        if (
            not item.evidence_id
            or not item.type
            or not item.source_segment_ids
            or not item.timestamp
            or item.timestamp == "unknown"
            or not item.claim
            or item.confidence in {"low", "unknown"}
        ):
            return "low"
        if item.confidence == "medium":
            return "medium"
    return "high"


def _evidence_score(lesson: Lesson, evidence_items: list[EvidenceItem]) -> Confidence:
    return _combine_confidence(
        [
            _evidence_completeness(evidence_items),
            _segment_confidence(lesson, evidence_items),
        ]
    )


def _related_ids_for_evidence(items: list[EvidenceItem]) -> list[str]:
    related: list[str] = []
    for item in items:
        related.append(item.evidence_id)
        related.extend(item.related_ids)
    return list(dict.fromkeys(related))


def _add_risk(
    risks: list[RiskHighlight],
    *,
    risk_id: str,
    confidence: Confidence,
    module: str,
    message: str,
    related_ids: list[str],
    teacher_action: str = "confirm_or_edit",
) -> None:
    if confidence not in {"medium", "low"}:
        return
    risks.append(
        RiskHighlight(
            risk_id=risk_id,
            level="high" if confidence == "low" else "medium",
            module=module,
            message=message,
            related_ids=related_ids,
            teacher_action=teacher_action,
        )
    )


def score_confidence(lesson: Lesson) -> Lesson:
    homework_confidence = _evidence_score(lesson, lesson.evidence.homework)
    student_question_confidence = _evidence_score(lesson, lesson.evidence.student_questions)
    correction_confidence = _evidence_score(lesson, lesson.evidence.corrections)

    pronunciation_reference = _combine_confidence(
        [clip.reference_confidence for clip in lesson.practice_clips if clip.should_assess_pronunciation]
    )
    pronunciation_feedback = _combine_confidence(
        [
            _evidence_score(lesson, lesson.evidence.pronunciation),
            _combine_confidence(
                [assessment.model_confidence for assessment in lesson.pronunciation_assessments]
            ),
        ]
    )

    candidate_homework = [
        item for item in lesson.draft_report.homework_items if item.is_candidate
    ]
    if candidate_homework:
        homework_confidence = _combine_confidence([homework_confidence, "medium"])

    key_scores: dict[str, Confidence] = {
        "homework_extraction": homework_confidence,
        "student_question_extraction": student_question_confidence,
        "pronunciation_reference_text": pronunciation_reference,
        "pronunciation_feedback": pronunciation_feedback,
        "correction_extraction": correction_confidence,
    }
    lesson.confidence_scores = {
        **key_scores,
        "overall_report_reliability": _combine_confidence(list(key_scores.values())),
    }

    risks: list[RiskHighlight] = []
    _add_risk(
        risks,
        risk_id="risk_homework",
        confidence=homework_confidence,
        module="homework",
        message=(
            "Homework extraction includes inferred or non-high-confidence content; "
            "teacher must confirm assignments before final reports are sent."
        ),
        related_ids=[
            *[item.homework_id for item in candidate_homework],
            *_related_ids_for_evidence(lesson.evidence.homework),
        ],
        teacher_action="confirm_or_remove",
    )
    _add_risk(
        risks,
        risk_id="risk_student_question",
        confidence=student_question_confidence,
        module="student_questions",
        message="Student question extraction is not high confidence; teacher should verify the wording.",
        related_ids=_related_ids_for_evidence(lesson.evidence.student_questions),
    )
    _add_risk(
        risks,
        risk_id="risk_corrections",
        confidence=correction_confidence,
        module="corrections",
        message="Correction extraction is not high confidence; teacher should verify before sharing.",
        related_ids=_related_ids_for_evidence(lesson.evidence.corrections),
    )
    _add_risk(
        risks,
        risk_id="risk_pronunciation_reference",
        confidence=pronunciation_reference,
        module="pronunciation",
        message="Pronunciation reference text is not uniformly high confidence; teacher should confirm.",
        related_ids=[
            clip.clip_id
            for clip in lesson.practice_clips
            if clip.reference_confidence in {"medium", "low"}
        ],
    )
    _add_risk(
        risks,
        risk_id="risk_pronunciation_feedback",
        confidence=pronunciation_feedback,
        module="pronunciation",
        message=(
            "Pronunciation feedback uses non-high-confidence model output or evidence; "
            "teacher should confirm before sending."
        ),
        related_ids=_related_ids_for_evidence(lesson.evidence.pronunciation),
    )
    _add_risk(
        risks,
        risk_id="risk_overall_report_reliability",
        confidence=lesson.confidence_scores["overall_report_reliability"],
        module="overall_report",
        message=(
            "Overall report reliability is not high because one or more upstream "
            "modules are medium or low confidence."
        ),
        related_ids=[risk.risk_id for risk in risks],
    )

    lesson.risk_highlights = risks
    return lesson
