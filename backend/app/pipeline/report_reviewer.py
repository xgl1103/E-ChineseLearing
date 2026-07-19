from __future__ import annotations

from backend.app.schemas import Lesson, ReviewResult


def _score_floor(value: float) -> float:
    return max(0.0, min(100.0, value))


def review_report(lesson: Lesson, revision_count: int = 0) -> Lesson:
    issues = list(lesson.rule_validation_result.blocking_issues)
    warnings = list(lesson.rule_validation_result.warnings)

    completeness = 100.0
    if not lesson.evidence.knowledge_points:
        completeness -= 15
        issues.append("No knowledge point evidence found.")
    if not lesson.evidence.teacher_questions:
        completeness -= 10
        issues.append("No teacher question evidence found.")
    if not lesson.evidence.student_questions:
        completeness -= 10
        issues.append("No student question evidence found.")
    if not lesson.evidence.corrections:
        completeness -= 15
        issues.append("No correction evidence found.")
    if not lesson.evidence.homework:
        completeness -= 15
        issues.append("No homework evidence found.")
    if not lesson.evidence.pronunciation:
        completeness -= 10
        issues.append("No pronunciation evidence found.")

    evidence_grounding = 100.0 - 20.0 * len(lesson.rule_validation_result.blocking_issues)
    pronunciation_boundary = 95.0
    if any("tone-level" in issue for issue in issues):
        pronunciation_boundary = 55.0
    if lesson.confidence_scores.get("pronunciation_feedback") in {"medium", "low"}:
        pronunciation_boundary -= 8

    homework_actionability = 95.0
    if any(item.is_candidate for item in lesson.draft_report.homework_items):
        homework_actionability -= 8
    if lesson.confidence_scores.get("homework_extraction") in {"medium", "low"}:
        homework_actionability -= 8

    parent_friendliness = 88.0
    safety_and_privacy = 92.0
    if lesson.teacher_review.status != "confirmed":
        safety_and_privacy -= 5

    rubric_scores = {
        "completeness": _score_floor(completeness),
        "evidence_grounding": _score_floor(evidence_grounding),
        "pronunciation_boundary": _score_floor(pronunciation_boundary),
        "homework_actionability": _score_floor(homework_actionability),
        "parent_friendliness": _score_floor(parent_friendliness),
        "safety_and_privacy": _score_floor(safety_and_privacy),
    }

    score = sum(rubric_scores.values()) / len(rubric_scores)
    score -= 3 * len(warnings)
    score = _score_floor(score)

    if revision_count > 2:
        issues.append("Writer-Reviewer loop exceeded the maximum of 2 revisions.")

    passes = lesson.rule_validation_result.pass_ and not issues and revision_count <= 2
    if not lesson.rule_validation_result.pass_:
        passes = False
        score = min(score, 65.0)

    instruction = ""
    if not passes:
        instruction = (
            "Revise the draft so every factual claim has source evidence, "
            "pronunciation comments only use pronunciation_assessments, "
            "low-confidence content is visible in risk_highlights, and teacher-only "
            "confirmation gates remain explicit."
        )

    lesson.review_result = ReviewResult(
        pass_=passes,
        score=score if passes else min(score, 65.0),
        issues=list(dict.fromkeys(issues)),
        revision_instruction=instruction,
        revision_count=revision_count,
        rubric_scores=rubric_scores,
    )
    return lesson
