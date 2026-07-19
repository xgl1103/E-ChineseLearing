from __future__ import annotations

import re

from backend.app.schemas import PracticeClip, TranscriptSegment, Transcripts


CJK_RE = re.compile(r"[\u3400-\u9fff]")
CHINESE_REFERENCE_RE = re.compile(
    r"[\u3400-\u9fff\uff0c\u3002\uff01\uff1f\u3001\uff1b\uff1a\u201c\u201d\u2018\u2019]+"
)
REFERENCE_STRIP_CHARS = "\uff0c\u3002\uff01\uff1f\u3001\uff1b\uff1a\u201c\u201d\u2018\u2019,.!?;:\"' "


def extract_practice_clips(transcripts: Transcripts) -> list[PracticeClip]:
    clips: list[PracticeClip] = []
    teachers = sorted(transcripts.teacher, key=lambda segment: segment.start_time)
    students = sorted(transcripts.student, key=lambda segment: segment.start_time)

    for segment in students:
        duration = max(0.0, segment.end_time - segment.start_time)
        if not CJK_RE.search(segment.text):
            continue
        if duration <= 0 or duration > 20:
            continue
        if segment.asr_confidence < 0.6:
            continue

        reference_text, reference_source, reference_confidence = _reference_for_segment(
            segment,
            teachers,
        )
        clip_index = len(clips) + 1
        clips.append(
            PracticeClip(
                clip_id=f"clip_{clip_index:03d}",
                student_segment_id=segment.segment_id,
                audio_uri=(
                    f"mock://audio/generated/{segment.segment_id}_"
                    f"{round(segment.start_time * 1000):06d}_{round(segment.end_time * 1000):06d}.webm"
                ),
                clip_start=max(0.0, segment.start_time - 0.3),
                clip_end=segment.end_time + 0.5,
                reference_text=reference_text,
                reference_source=reference_source,
                reference_confidence=reference_confidence,
                should_assess_pronunciation=True,
            )
        )

    return clips


def _reference_for_segment(
    segment: TranscriptSegment,
    teachers: list[TranscriptSegment],
) -> tuple[str, str, str]:
    recent_teachers = [
        teacher
        for teacher in teachers
        if 0 <= segment.start_time - teacher.end_time <= 60
    ]
    for teacher in reversed(recent_teachers):
        chinese_parts = CHINESE_REFERENCE_RE.findall(teacher.text)
        reference = "".join(chinese_parts).strip(REFERENCE_STRIP_CHARS)
        if reference:
            return reference, "nearby_teacher_model_sentence", "medium"
    return segment.text, "student_transcript_fallback", "low"
