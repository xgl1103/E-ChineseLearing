from __future__ import annotations

from backend.app.schemas import (
    DraftReport,
    HomeworkItem,
    Lesson,
    PronunciationFeedback,
    ReportEntry,
    StudentAssessment,
)


def _entry_from_evidence(title: str, detail: str, evidence_ids: list[str], confidence: str) -> ReportEntry:
    return ReportEntry(
        title=title,
        detail=detail,
        source_evidence_ids=evidence_ids,
        confidence=confidence,
    )


def _evidence_ids_by_related_assessment(lesson: Lesson, assessment_id: str) -> list[str]:
    return [
        item.evidence_id
        for item in lesson.evidence.pronunciation
        if assessment_id in item.related_ids
    ]


def _first_evidence_id(items: list, default: str = "") -> str:
    return items[0].evidence_id if items else default


def write_report(lesson: Lesson) -> Lesson:
    student_name = lesson.metadata.student_name
    knowledge_points = [
        _entry_from_evidence(
            title=item.claim,
            detail=item.text or item.claim,
            evidence_ids=[item.evidence_id],
            confidence=item.confidence,
        )
        for item in lesson.evidence.knowledge_points
    ]

    teacher_questions = [
        _entry_from_evidence(
            title="Teacher practice prompt",
            detail=item.text or item.claim,
            evidence_ids=[item.evidence_id],
            confidence=item.confidence,
        )
        for item in lesson.evidence.teacher_questions
    ]

    student_questions = [
        _entry_from_evidence(
            title="Student clarification question",
            detail=item.text or item.claim,
            evidence_ids=[item.evidence_id],
            confidence=item.confidence,
        )
        for item in lesson.evidence.student_questions
    ]

    corrections = [
        _entry_from_evidence(
            title="Correction",
            detail=item.claim,
            evidence_ids=[item.evidence_id],
            confidence=item.confidence,
        )
        for item in lesson.evidence.corrections
    ]

    pronunciation_feedback: list[PronunciationFeedback] = []
    for assessment in lesson.pronunciation_assessments:
        evidence_ids = _evidence_ids_by_related_assessment(lesson, assessment.assessment_id)
        low_words = ", ".join(word.word for word in assessment.low_score_words) or "none"
        pronunciation_feedback.append(
            PronunciationFeedback(
                title="Pronunciation practice needs teacher confirmation",
                detail=(
                    f'Assessment score is {assessment.pronunciation_score}. '
                    f'Low-score words: {low_words}. '
                    "Treat this as AI feedback until the teacher confirms it."
                ),
                assessment_id=assessment.assessment_id,
                source_evidence_ids=evidence_ids,
                confidence=assessment.model_confidence,
                teacher_confirmation_required=assessment.teacher_confirmation_required,
            )
        )

    homework_items: list[HomeworkItem] = []
    for index, item in enumerate(lesson.evidence.homework, start=1):
        homework_items.append(
            HomeworkItem(
                homework_id=f"hw_{index:03d}",
                title="Homework",
                description=item.mapped_homework or item.claim,
                type="assignment",
                source_evidence_id=item.evidence_id,
                confidence="low" if item.confidence == "unknown" else item.confidence,
                teacher_confirmed=False,
                teacher_confirmation_required=item.confidence != "high",
                is_candidate=False,
            )
        )

    candidate_source_id = _first_evidence_id(lesson.evidence.knowledge_points[2:]) or _first_evidence_id(
        lesson.evidence.knowledge_points
    )
    if candidate_source_id:
        homework_items.append(
            HomeworkItem(
                homework_id=f"hw_{len(homework_items) + 1:03d}",
                title="Dialogue practice candidate",
                description='Use "我想要..." and "多少钱？" to complete one short ordering dialogue.',
                type="dialogue_practice",
                source_evidence_id=candidate_source_id,
                confidence="medium",
                teacher_confirmed=False,
                teacher_confirmation_required=True,
                is_candidate=True,
            )
        )

    assessment_evidence_ids = [
        item.evidence_id
        for group in (
            lesson.evidence.knowledge_points,
            lesson.evidence.teacher_questions,
            lesson.evidence.corrections,
            lesson.evidence.student_questions,
            lesson.evidence.pronunciation,
        )
        for item in group
    ]
    has_pronunciation = bool(pronunciation_feedback)
    lesson.draft_report = DraftReport(
        lesson_summary=(
            f"{student_name} practiced {lesson.metadata.lesson_topic}. "
            "The AI draft summarizes class content, evidence-backed corrections, "
            "pronunciation signals, and homework for teacher review."
        ),
        knowledge_points=knowledge_points,
        teacher_questions=teacher_questions,
        student_questions=student_questions,
        corrections=corrections,
        pronunciation_feedback=pronunciation_feedback,
        homework_items=homework_items,
        student_assessment=StudentAssessment(
            participation=(
                f"{student_name} participated in the practice and responded to teacher prompts."
            ),
            vocabulary="Vocabulary practice focused on restaurant ordering and measure words.",
            grammar='The sentence pattern "我想要..." is emerging; measure-word choice needs reinforcement.',
            pronunciation=(
                "Pronunciation assessment is available and requires teacher confirmation."
                if has_pronunciation
                else "No pronunciation assessment is available for this run."
            ),
            overall_note="AI initial assessment only. Teacher confirmation is required before sharing.",
            source_evidence_ids=assessment_evidence_ids,
        ),
        next_lesson_suggestions=[
            ReportEntry(
                title="Next lesson focus",
                detail="Review measure words, then run a short restaurant-ordering role play.",
                source_evidence_ids=assessment_evidence_ids[:3],
                confidence="medium" if lesson.risk_highlights else "high",
            )
        ],
    )
    return lesson
