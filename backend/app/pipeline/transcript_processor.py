from __future__ import annotations

from backend.app.schemas import Lesson


def process_transcripts(lesson: Lesson) -> Lesson:
    """Normalize transcript order and preserve ASR metadata."""
    lesson.transcripts.teacher.sort(key=lambda segment: segment.start_time)
    lesson.transcripts.student.sort(key=lambda segment: segment.start_time)
    return lesson

