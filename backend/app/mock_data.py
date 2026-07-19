from __future__ import annotations

from copy import deepcopy


FALLBACK_DEMO_LESSON: dict = {
    "lesson_id": "demo_001",
    "metadata": {
        "student_name": "Alex Chen",
        "student_age": 10,
        "student_level": "YCT 3",
        "course_type": "Kids Chinese",
        "lesson_topic": "Restaurant ordering",
        "lesson_duration_minutes": 45,
        "teacher_name": "Ms. Lin",
        "lesson_date": "2026-07-09",
    },
    "transcripts": {
        "teacher": [
            {
                "segment_id": "t_001",
                "speaker": "teacher",
                "start_time": 12.4,
                "end_time": 18.7,
                "text": "Today we are practicing how to order food in Chinese. Please repeat after me: 我想要一杯果汁。",
                "language_tags": ["en", "zh-CN"],
                "asr_confidence": 0.94,
            },
            {
                "segment_id": "t_002",
                "speaker": "teacher",
                "start_time": 25.0,
                "end_time": 32.5,
                "text": "Good try. For drinks we say 一杯果汁, not 一个果汁.",
                "language_tags": ["en", "zh-CN"],
                "asr_confidence": 0.92,
            },
            {
                "segment_id": "t_003",
                "speaker": "teacher",
                "start_time": 60.0,
                "end_time": 67.0,
                "text": "How do you ask the price? You can say 多少钱?",
                "language_tags": ["en", "zh-CN"],
                "asr_confidence": 0.9,
            },
            {
                "segment_id": "t_004",
                "speaker": "teacher",
                "start_time": 2100.0,
                "end_time": 2107.0,
                "text": "For homework, please record yourself reading 我想要一杯果汁 five times, and review 杯, 份, 碗.",
                "language_tags": ["en", "zh-CN"],
                "asr_confidence": 0.88,
            },
        ],
        "student": [
            {
                "segment_id": "s_001",
                "speaker": "student",
                "start_time": 19.1,
                "end_time": 22.4,
                "text": "我想要一个果汁。",
                "language_tags": ["zh-CN"],
                "asr_confidence": 0.86,
            },
            {
                "segment_id": "s_002",
                "speaker": "student",
                "start_time": 33.0,
                "end_time": 36.8,
                "text": "Why use 杯?",
                "language_tags": ["en", "zh-CN"],
                "asr_confidence": 0.9,
            },
            {
                "segment_id": "s_003",
                "speaker": "student",
                "start_time": 68.0,
                "end_time": 70.5,
                "text": "多少钱?",
                "language_tags": ["zh-CN"],
                "asr_confidence": 0.82,
            },
        ],
    },
    "practice_clips": [
        {
            "clip_id": "clip_001",
            "student_segment_id": "s_001",
            "audio_uri": "/mock/student_19100_22400.wav",
            "clip_start": 18.8,
            "clip_end": 22.9,
            "reference_text": "我想要一杯果汁",
            "reference_source": "teacher_repeat_instruction",
            "reference_confidence": "medium",
            "should_assess_pronunciation": True,
        }
    ],
    "pronunciation_assessments": [
        {
            "assessment_id": "pa_001",
            "clip_id": "clip_001",
            "reference_text": "我想要一杯果汁",
            "pronunciation_score": 78,
            "accuracy_score": 74,
            "fluency_score": 82,
            "completeness_score": 92,
            "prosody_score": 76,
            "low_score_words": [
                {
                    "word": "果汁",
                    "accuracy_score": 58,
                    "error_type": "Mispronunciation",
                }
            ],
            "model_confidence": "medium",
            "teacher_confirmation_required": True,
        }
    ],
    "evidence": {
        "knowledge_points": [],
        "homework": [],
        "corrections": [],
        "student_questions": [],
        "pronunciation": [],
    },
    "confidence_scores": {},
    "draft_report": {
        "lesson_summary": "",
        "knowledge_points": [],
        "teacher_questions": [],
        "student_questions": [],
        "corrections": [],
        "pronunciation_feedback": [],
        "homework_items": [],
        "student_assessment": {},
        "next_lesson_suggestions": [],
    },
    "rule_validation_result": {
        "pass": False,
        "blocking_issues": [],
        "warnings": [],
    },
    "review_result": {
        "pass": False,
        "score": 0,
        "issues": [],
        "revision_instruction": "",
        "revision_count": 0,
    },
    "risk_highlights": [],
    "teacher_review": {
        "status": "pending",
        "reviewed_at": None,
        "confirmed_homework_ids": [],
        "edited_homework_items": [],
        "confirmed_risk_ids": [],
        "teacher_notes": "",
        "report_edits": {},
    },
    "final_reports": {
        "teacher": {"title": "", "audience": "", "sections": []},
        "student": {"title": "", "audience": "", "sections": []},
        "parent": {"title": "", "audience": "", "sections": []},
    },
    "teacher_edit_log": [],
}


def get_fallback_demo_lesson() -> dict:
    return deepcopy(FALLBACK_DEMO_LESSON)

