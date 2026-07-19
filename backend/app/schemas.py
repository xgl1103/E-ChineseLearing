from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


Confidence = Literal["high", "medium", "low", "unknown"]
RiskLevel = Literal["high", "medium", "low"]
Speaker = Literal["teacher", "student"]


class Metadata(BaseModel):
    student_name: str
    student_age: int
    student_level: str
    course_type: str
    lesson_topic: str
    lesson_duration_minutes: int
    teacher_name: str
    lesson_date: str


class TranscriptSegment(BaseModel):
    segment_id: str
    speaker: Speaker
    start_time: float
    end_time: float
    text: str
    language_tags: list[str]
    asr_confidence: float


class Transcripts(BaseModel):
    teacher: list[TranscriptSegment] = Field(default_factory=list)
    student: list[TranscriptSegment] = Field(default_factory=list)


class PracticeClip(BaseModel):
    clip_id: str
    student_segment_id: str
    audio_uri: str
    clip_start: float
    clip_end: float
    reference_text: str
    reference_source: str
    reference_confidence: Literal["high", "medium", "low"]
    should_assess_pronunciation: bool


class LowScoreWord(BaseModel):
    word: str
    accuracy_score: float
    error_type: str


class PronunciationAssessment(BaseModel):
    assessment_id: str
    clip_id: str
    reference_text: str
    pronunciation_score: float
    accuracy_score: float
    fluency_score: float
    completeness_score: float
    prosody_score: float
    low_score_words: list[LowScoreWord] = Field(default_factory=list)
    model_confidence: Literal["high", "medium", "low"]
    teacher_confirmation_required: bool


class EvidenceItem(BaseModel):
    evidence_id: str
    type: str
    source_segment_ids: list[str]
    timestamp: str
    claim: str
    confidence: Confidence
    speaker: str | None = None
    text: str | None = None
    student_original: str | None = None
    teacher_correction: str | None = None
    mapped_homework: str | None = None
    related_ids: list[str] = Field(default_factory=list)


class Evidence(BaseModel):
    knowledge_points: list[EvidenceItem] = Field(default_factory=list)
    teacher_questions: list[EvidenceItem] = Field(default_factory=list)
    homework: list[EvidenceItem] = Field(default_factory=list)
    corrections: list[EvidenceItem] = Field(default_factory=list)
    student_questions: list[EvidenceItem] = Field(default_factory=list)
    pronunciation: list[EvidenceItem] = Field(default_factory=list)


class HomeworkItem(BaseModel):
    homework_id: str
    title: str
    description: str
    type: str
    source_evidence_id: str
    confidence: Literal["high", "medium", "low"]
    teacher_confirmed: bool = False
    teacher_confirmation_required: bool = False
    is_candidate: bool = False


class ReportEntry(BaseModel):
    title: str = ""
    detail: str = ""
    source_evidence_ids: list[str] = Field(default_factory=list)
    confidence: Confidence = "unknown"

    @model_validator(mode="before")
    @classmethod
    def normalize_entry(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        if not normalized.get("title"):
            normalized["title"] = (
                normalized.get("question")
                or normalized.get("student_original")
                or normalized.get("id")
                or "Report item"
            )
        if not normalized.get("detail"):
            if normalized.get("teacher_correction"):
                normalized["detail"] = (
                    f"{normalized.get('student_original', '')} -> "
                    f"{normalized.get('teacher_correction', '')}. "
                    f"{normalized.get('explanation', '')}"
                ).strip()
            else:
                normalized["detail"] = normalized.get("text") or normalized.get("claim") or ""
        source_id = normalized.get("source_evidence_id")
        if source_id and not normalized.get("source_evidence_ids"):
            normalized["source_evidence_ids"] = [source_id]
        return normalized


class PronunciationFeedback(BaseModel):
    title: str = ""
    detail: str = ""
    assessment_id: str | None = None
    source_evidence_ids: list[str] = Field(default_factory=list)
    confidence: Confidence = "unknown"
    teacher_confirmation_required: bool = False

    @model_validator(mode="before")
    @classmethod
    def normalize_feedback(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        normalized.setdefault("title", normalized.get("id") or "Pronunciation feedback")
        normalized.setdefault("detail", normalized.get("text") or "")
        source_id = normalized.get("source_evidence_id")
        if source_id and not normalized.get("source_evidence_ids"):
            normalized["source_evidence_ids"] = [source_id]
        return normalized


class StudentAssessment(BaseModel):
    participation: str
    vocabulary: str
    grammar: str
    pronunciation: str
    overall_note: str
    source_evidence_ids: list[str] = Field(default_factory=list)


class DraftReport(BaseModel):
    lesson_summary: str = ""
    knowledge_points: list[ReportEntry] = Field(default_factory=list)
    teacher_questions: list[ReportEntry] = Field(default_factory=list)
    student_questions: list[ReportEntry] = Field(default_factory=list)
    corrections: list[ReportEntry] = Field(default_factory=list)
    pronunciation_feedback: list[PronunciationFeedback] = Field(default_factory=list)
    homework_items: list[HomeworkItem] = Field(default_factory=list)
    student_assessment: StudentAssessment | dict[str, Any] = Field(default_factory=dict)
    next_lesson_suggestions: list[ReportEntry] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def normalize_report_lists(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        for key in (
            "knowledge_points",
            "teacher_questions",
            "student_questions",
            "corrections",
            "next_lesson_suggestions",
        ):
            normalized[key] = [
                item
                if isinstance(item, (dict, BaseModel))
                else {"title": str(item), "detail": str(item), "confidence": "unknown"}
                for item in normalized.get(key, [])
            ]
        return normalized


class RuleValidationResult(BaseModel):
    pass_: bool = Field(alias="pass")
    blocking_issues: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def normalize_messages(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        for key in ("blocking_issues", "warnings"):
            normalized[key] = [
                item if isinstance(item, str) else str(item)
                for item in normalized.get(key, [])
            ]
        return normalized

    class Config:
        populate_by_name = True


class ReviewResult(BaseModel):
    pass_: bool = Field(alias="pass")
    score: float
    issues: list[str] = Field(default_factory=list)
    revision_instruction: str = ""
    revision_count: int = 0
    rubric_scores: dict[str, float] = Field(default_factory=dict)

    class Config:
        populate_by_name = True


class RiskHighlight(BaseModel):
    risk_id: str
    level: RiskLevel
    module: str
    message: str
    related_ids: list[str] = Field(default_factory=list)
    teacher_action: str


class TeacherReview(BaseModel):
    status: str = "pending"
    reviewed_at: str | None = None
    confirmed_homework_ids: list[str] = Field(default_factory=list)
    edited_homework_items: list[dict[str, Any]] = Field(default_factory=list)
    confirmed_risk_ids: list[str] = Field(default_factory=list)
    teacher_notes: str = ""
    report_edits: dict[str, Any] = Field(default_factory=dict)


class FinalReportSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    heading: str
    content: Any = None

    @model_validator(mode="before")
    @classmethod
    def normalize_section(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        if "content" not in normalized and "items" in normalized:
            normalized["content"] = normalized["items"]
        normalized.pop("items", None)
        return normalized


class FinalReport(BaseModel):
    title: str = ""
    audience: str = ""
    status: str = "draft_waiting_teacher_confirmation"
    sections: list[FinalReportSection] = Field(default_factory=list)


class FinalReports(BaseModel):
    teacher: FinalReport = Field(default_factory=FinalReport)
    student: FinalReport = Field(default_factory=FinalReport)
    parent: FinalReport = Field(default_factory=FinalReport)


class Lesson(BaseModel):
    lesson_id: str
    metadata: Metadata
    transcripts: Transcripts
    practice_clips: list[PracticeClip] = Field(default_factory=list)
    pronunciation_assessments: list[PronunciationAssessment] = Field(default_factory=list)
    evidence: Evidence = Field(default_factory=Evidence)
    confidence_scores: dict[str, Confidence] = Field(default_factory=dict)
    draft_report: DraftReport = Field(default_factory=DraftReport)
    rule_validation_result: RuleValidationResult = Field(
        default_factory=lambda: RuleValidationResult(pass_=False)
    )
    review_result: ReviewResult = Field(
        default_factory=lambda: ReviewResult(pass_=False, score=0, revision_count=0)
    )
    risk_highlights: list[RiskHighlight] = Field(default_factory=list)
    teacher_review: TeacherReview = Field(default_factory=TeacherReview)
    final_reports: FinalReports = Field(default_factory=FinalReports)
    teacher_edit_log: list[dict[str, Any]] = Field(default_factory=list)


class AnalyzeRequest(BaseModel):
    mode: Literal["mock", "real"] = "mock"
    include_pronunciation: bool = True


class TeacherReviewRequest(BaseModel):
    confirmed_homework_ids: list[str] = Field(default_factory=list)
    edited_homework_items: list[dict[str, Any]] = Field(default_factory=list)
    confirmed_risk_ids: list[str] = Field(default_factory=list)
    teacher_notes: str = ""
    report_edits: dict[str, Any] = Field(default_factory=dict)


class FinalizeRequest(BaseModel):
    audiences: list[Literal["teacher", "student", "parent"]] = Field(
        default_factory=lambda: ["teacher", "student", "parent"]
    )


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
