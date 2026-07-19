from __future__ import annotations

from collections.abc import Callable

from backend.app.schemas import Evidence, EvidenceItem, Lesson, TranscriptSegment


def _timestamp(seconds: float | None) -> str:
    if seconds is None:
        return "unknown"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}:{secs:02d}"


def _contains_any(text: str, keywords: list[str]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def _find_first(
    segments: list[TranscriptSegment],
    predicate: Callable[[TranscriptSegment], bool],
) -> TranscriptSegment | None:
    return next((segment for segment in segments if predicate(segment)), None)


def _find_all(
    segments: list[TranscriptSegment],
    predicate: Callable[[TranscriptSegment], bool],
) -> list[TranscriptSegment]:
    return [segment for segment in segments if predicate(segment)]


def _find_after(
    segments: list[TranscriptSegment],
    after_seconds: float,
    predicate: Callable[[TranscriptSegment], bool],
) -> TranscriptSegment | None:
    return next(
        (
            segment
            for segment in segments
            if segment.start_time >= after_seconds and predicate(segment)
        ),
        None,
    )


def _ids(*segments: TranscriptSegment | None) -> list[str]:
    return [segment.segment_id for segment in segments if segment is not None]


def _evidence_confidence(segments: list[TranscriptSegment], fallback: str = "medium") -> str:
    if not segments:
        return "low"
    min_asr = min(segment.asr_confidence for segment in segments)
    if min_asr >= 0.9:
        return "high"
    if min_asr >= 0.82:
        return "medium"
    return fallback


def extract_evidence(lesson: Lesson) -> Lesson:
    teachers = lesson.transcripts.teacher
    students = lesson.transcripts.student
    segments_by_id = {
        segment.segment_id: segment
        for segment in [*teachers, *students]
    }

    ordering_segment = _find_first(
        teachers,
        lambda segment: _contains_any(segment.text, ["我想要"]),
    )
    measure_word_segments = _find_all(
        teachers,
        lambda segment: _contains_any(segment.text, ["一杯", "杯"]),
    )
    price_segments = _find_all(
        [*teachers, *students],
        lambda segment: _contains_any(segment.text, ["多少钱"]),
    )
    teacher_question_segments = _find_all(
        teachers,
        lambda segment: "?" in segment.text
        or _contains_any(segment.text, ["how do you say", "please repeat after me"]),
    )
    homework_segments = _find_all(
        teachers,
        lambda segment: _contains_any(
            segment.text,
            ["homework", "after class", "please record", "record yourself", "also review"],
        ),
    )
    correction_student = _find_first(
        students,
        lambda segment: _contains_any(segment.text, ["一个果汁"]),
    )
    correction_teacher = (
        _find_after(
            teachers,
            correction_student.start_time if correction_student else 0,
            lambda segment: _contains_any(segment.text, ["一杯果汁"]),
        )
        or _find_first(teachers, lambda segment: _contains_any(segment.text, ["一杯果汁"]))
    )
    student_question = _find_first(
        students,
        lambda segment: "?" in segment.text or _contains_any(segment.text, ["为什么"]),
    )

    knowledge: list[EvidenceItem] = []
    if ordering_segment:
        knowledge.append(
            EvidenceItem(
                evidence_id="ev_kp_001",
                type="knowledge_point",
                source_segment_ids=[ordering_segment.segment_id],
                timestamp=_timestamp(ordering_segment.start_time),
                claim="本节课学习餐厅点餐场景中的“我想要...”句型。",
                confidence=_evidence_confidence([ordering_segment]),
                speaker="teacher",
                text=ordering_segment.text,
            )
        )
    if measure_word_segments:
        source_segments = measure_word_segments[:2]
        knowledge.append(
            EvidenceItem(
                evidence_id="ev_kp_002",
                type="knowledge_point",
                source_segment_ids=[segment.segment_id for segment in source_segments],
                timestamp=_timestamp(source_segments[0].start_time),
                claim="本节课重点学习饮料量词“杯”，并对比“份”“碗”的使用。",
                confidence=_evidence_confidence(source_segments),
                speaker="teacher",
                text=" / ".join(segment.text for segment in source_segments),
            )
        )
    if price_segments:
        source_segments = price_segments[:2]
        knowledge.append(
            EvidenceItem(
                evidence_id="ev_kp_003",
                type="knowledge_point",
                source_segment_ids=[segment.segment_id for segment in source_segments],
                timestamp=_timestamp(source_segments[0].start_time),
                claim="学生开始练习询问价格“多少钱”。",
                confidence=_evidence_confidence(source_segments),
                text=" / ".join(segment.text for segment in source_segments),
            )
        )

    teacher_questions = [
        EvidenceItem(
            evidence_id=f"ev_tq_{index:03d}",
            type="teacher_question",
            source_segment_ids=[segment.segment_id],
            timestamp=_timestamp(segment.start_time),
            claim=f"老师提问或带读：{segment.text}",
            confidence=_evidence_confidence([segment]),
            speaker="teacher",
            text=segment.text,
        )
        for index, segment in enumerate(teacher_question_segments, start=1)
    ]

    homework: list[EvidenceItem] = []
    for index, segment in enumerate(homework_segments, start=1):
        if _contains_any(segment.text, ["record", "record yourself", "please record"]):
            claim = "老师布置录音作业：课后朗读目标句五遍。"
            mapped_homework = "Record the target ordering sentence five times."
        elif _contains_any(segment.text, ["review", "also review"]):
            claim = "老师布置词汇复习：杯、份、碗、果汁、面条、多少钱。"
            mapped_homework = "Review vocabulary: 杯, 份, 碗, 果汁, 面条, 多少钱."
        else:
            claim = "老师布置课后练习。"
            mapped_homework = segment.text
        homework.append(
            EvidenceItem(
                evidence_id=f"ev_hw_{index:03d}",
                type="homework",
                source_segment_ids=[segment.segment_id],
                timestamp=_timestamp(segment.start_time),
                claim=claim,
                confidence=_evidence_confidence([segment]),
                speaker="teacher",
                text=segment.text,
                mapped_homework=mapped_homework,
            )
        )

    corrections: list[EvidenceItem] = []
    if correction_student or correction_teacher:
        source_segments = [segment for segment in (correction_student, correction_teacher) if segment]
        corrections.append(
            EvidenceItem(
                evidence_id="ev_cr_001",
                type="correction",
                source_segment_ids=_ids(correction_student, correction_teacher),
                timestamp=_timestamp(
                    correction_student.start_time if correction_student else correction_teacher.start_time
                ),
                claim="学生把饮料量词说成“一个”，老师纠正为“一杯果汁”。",
                confidence=_evidence_confidence(source_segments),
                student_original=correction_student.text if correction_student else None,
                teacher_correction="一杯果汁" if correction_teacher else None,
                text=" / ".join(segment.text for segment in source_segments),
            )
        )

    student_questions: list[EvidenceItem] = []
    if student_question:
        student_questions.append(
            EvidenceItem(
                evidence_id="ev_sq_001",
                type="student_question",
                source_segment_ids=[student_question.segment_id],
                timestamp=_timestamp(student_question.start_time),
                claim="学生主动提问为什么用“杯”而不是“个”。",
                confidence=_evidence_confidence([student_question]),
                speaker="student",
                text=student_question.text,
            )
        )

    clips_by_id = {clip.clip_id: clip for clip in lesson.practice_clips}
    pronunciation: list[EvidenceItem] = []
    for index, assessment in enumerate(lesson.pronunciation_assessments, start=1):
        clip = clips_by_id.get(assessment.clip_id)
        source_segment = (
            segments_by_id.get(clip.student_segment_id)
            if clip is not None
            else None
        )
        related_ids = [assessment.assessment_id]
        if clip is not None:
            related_ids.append(clip.clip_id)
        low_words = ", ".join(word.word for word in assessment.low_score_words) or "none"
        pronunciation.append(
            EvidenceItem(
                evidence_id=f"ev_pr_{index:03d}",
                type="pronunciation",
                source_segment_ids=_ids(source_segment),
                timestamp=_timestamp(source_segment.start_time if source_segment else None),
                claim=(
                    f"发音评估片段“{assessment.reference_text}”的低分词：{low_words}。"
                    "具体发音原因需老师确认。"
                ),
                confidence=assessment.model_confidence,
                speaker="student",
                text=source_segment.text if source_segment else None,
                related_ids=related_ids,
            )
        )

    lesson.evidence = Evidence(
        knowledge_points=knowledge,
        teacher_questions=teacher_questions,
        homework=homework,
        corrections=corrections,
        student_questions=student_questions,
        pronunciation=pronunciation,
    )
    return lesson
