from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from backend.app.mock_data import get_fallback_demo_lesson
from backend.app.asr.bailian import (
    is_bailian_configured,
    transcribe_file as transcribe_bailian_file,
)
from backend.app.asr.deepgram import (
    is_deepgram_configured,
    transcribe_file as transcribe_deepgram_file,
)
from backend.app.graph import run_analysis_graph, run_finalization_graph
from backend.app.llm.config import _load_local_env
from backend.app.pipeline.practice_clip_extractor import extract_practice_clips
from backend.app.pipeline.report_reviewer import review_report
from backend.app.pipeline.rule_validator import validate_rules
from backend.app.pronunciation.azure import (
    assess_clip,
    is_azure_pronunciation_configured,
)
from backend.app.schemas import (
    AnalyzeRequest,
    FinalizeRequest,
    Lesson,
    LowScoreWord,
    PronunciationAssessment,
    TeacherReview,
    TeacherReviewRequest,
    Transcripts,
    utc_now_iso,
)


ROOT_DIR = Path(__file__).resolve().parents[2]
_load_local_env()
DATA_DEMO_LESSON = ROOT_DIR / "data" / "demo_lesson.json"
UPLOAD_ROOT = ROOT_DIR / ".uploads" / "lessons"
ALLOW_DEMO_FALLBACK = os.getenv("ALLOW_DEMO_FALLBACK") == "1"
MAX_AUDIO_BYTES = int(os.getenv("MAX_AUDIO_BYTES", str(100 * 1024 * 1024)))

logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Lesson Recorder Mock Backend",
    version="0.1.0",
    description="Mock API for the eChineseLearning AI Lesson Recorder MVP.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

LESSON_STORE: dict[str, Lesson] = {}
LESSON_LOAD_INFO: dict[str, dict[str, Any]] = {}
LESSON_GRAPH_TRACE: dict[str, list[dict[str, Any]]] = {}
LESSON_WORKFLOW_SUMMARY: dict[str, dict[str, Any]] = {}

_RAW_DEMO_LESSON: Lesson | None = None


def _summarize_validation_error(error: ValidationError) -> list[dict[str, Any]]:
    return [
        {
            "path": ".".join(str(part) for part in item.get("loc", ())),
            "message": item.get("msg", ""),
            "type": item.get("type", ""),
        }
        for item in error.errors()[:8]
    ]


def _display_data_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT_DIR))
    except ValueError:
        return str(path)


def _load_demo_lesson_dict() -> tuple[dict[str, Any], dict[str, Any]]:
    if DATA_DEMO_LESSON.exists():
        with DATA_DEMO_LESSON.open("r", encoding="utf-8") as file:
            return json.load(file), {
                "data_source": _display_data_path(DATA_DEMO_LESSON),
                "data_validation_error_summary": None,
            }
    return get_fallback_demo_lesson(), {
        "data_source": "fallback",
        "data_validation_error_summary": "data/demo_lesson.json not found",
    }


def _get_raw_demo_lesson() -> Lesson:
    """Load and cache the original demo lesson from disk.

    Returns a deepcopy so callers (analyze, GET) can mutate freely without
    polluting subsequent requests.  This is intentionally separate from
    ``LESSON_STORE`` so that a previously-analyzed lesson is never fed back
    into a new analyze run.
    """
    global _RAW_DEMO_LESSON
    if _RAW_DEMO_LESSON is not None:
        return deepcopy(_RAW_DEMO_LESSON)

    lesson_data, load_info = _load_demo_lesson_dict()
    try:
        _RAW_DEMO_LESSON = Lesson.model_validate(lesson_data)
    except ValidationError as error:
        error_summary = _summarize_validation_error(error)
        logger.error(
            "data/demo_lesson.json failed Lesson validation: %s",
            error_summary,
        )
        if not ALLOW_DEMO_FALLBACK:
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "data/demo_lesson.json failed backend Lesson validation.",
                    "data_source": _display_data_path(DATA_DEMO_LESSON),
                    "validation_errors": error_summary,
                    "hint": (
                        "Fix data/demo_lesson.json or set ALLOW_DEMO_FALLBACK=1 "
                        "to use in-memory fallback data during local debugging."
                    ),
                },
            ) from error
        _RAW_DEMO_LESSON = Lesson.model_validate(get_fallback_demo_lesson())
        load_info = {
            "data_source": "fallback",
            "data_validation_error_summary": error_summary,
        }
        logger.warning("Using fallback demo lesson after validation failure.")
    LESSON_LOAD_INFO[_RAW_DEMO_LESSON.lesson_id] = load_info
    return deepcopy(_RAW_DEMO_LESSON)


def _get_or_create_demo_lesson() -> Lesson:
    """Return the analyzed demo lesson if stored, otherwise a fresh raw copy.

    Used by ``_get_lesson`` as a fallback when the demo lesson is not yet in
    the store (i.e. analyze has not been called).  In that case the raw demo
    is also stored so that subsequent ``_get_lesson`` calls are consistent.
    """
    lesson = LESSON_STORE.get("demo_001")
    if lesson is not None:
        return lesson

    lesson = _get_raw_demo_lesson()
    LESSON_STORE[lesson.lesson_id] = lesson
    return lesson


def _get_lesson(lesson_id: str) -> Lesson:
    if lesson_id == "demo":
        lesson_id = "demo_001"
    lesson = LESSON_STORE.get(lesson_id)
    if lesson is None and lesson_id == "demo_001":
        return _get_or_create_demo_lesson()
    if lesson is None:
        raise HTTPException(status_code=404, detail=f"Lesson {lesson_id} not found")
    return lesson


def _run_mock_analysis(
    lesson: Lesson,
    include_pronunciation: bool = True,
    requested_agent_mode: str = "mock",
) -> Lesson:
    graph_state = run_analysis_graph(
        lesson,
        include_pronunciation=include_pronunciation,
        requested_agent_mode="real" if requested_agent_mode == "real" else "mock",
    )
    analyzed = graph_state.lesson
    LESSON_STORE[analyzed.lesson_id] = analyzed
    LESSON_GRAPH_TRACE[analyzed.lesson_id] = graph_state.trace()
    LESSON_WORKFLOW_SUMMARY[analyzed.lesson_id] = graph_state.workflow_summary()
    return analyzed


def _safe_filename(filename: str, fallback: str) -> str:
    suffix = Path(filename).suffix.lower() or ".webm"
    stem = Path(filename).stem or fallback
    stem = re.sub(r"[^a-zA-Z0-9_-]+", "_", stem).strip("_") or fallback
    return f"{stem[:48]}{suffix}"


async def _uploaded_file_summary(
    file: UploadFile | None,
    track: str,
    *,
    lesson_id: str,
    input_source: str,
) -> dict[str, Any]:
    if file is None:
        return {
            "track": track,
            "filename": "",
            "content_type": "",
            "size_bytes": 0,
            "status": "missing",
            "source": "",
        }
    content = await file.read()
    if len(content) > MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"{track}_audio exceeds the {MAX_AUDIO_BYTES} byte limit.",
        )
    content_type = file.content_type or "application/octet-stream"
    if not (content_type.startswith("audio/") or content_type == "application/octet-stream"):
        raise HTTPException(
            status_code=400,
            detail=f"{track}_audio must be an audio file.",
        )

    lesson_dir = UPLOAD_ROOT / lesson_id
    lesson_dir.mkdir(parents=True, exist_ok=True)
    filename = _safe_filename(file.filename or "", f"{track}_audio")
    target = lesson_dir / f"{track}_{filename}"
    target.write_bytes(content)
    return {
        "track": track,
        "filename": file.filename or "",
        "content_type": content_type,
        "size_bytes": len(content),
        "status": "received",
        "source": "uploaded_file",
        "input_source": input_source,
        "local_path": _display_data_path(target),
        "uri": f"file://{_display_data_path(target)}",
    }


def _sample_file_summary(track: str, sample_id: str) -> dict[str, Any]:
    prefix = "demo_extended" if sample_id == "extended" else "demo"
    sample_names = {
        "teacher": f"{prefix}_teacher_track.wav",
        "student": f"{prefix}_student_track.wav",
    }
    return {
        "track": track,
        "filename": sample_names.get(track, f"demo_{track}_track.wav"),
        "content_type": "audio/wav",
        "size_bytes": 0,
        "status": "sample_loaded",
        "source": "demo_sample",
        "sample_id": sample_id,
        "uri": f"mock://audio/demo_001/{sample_id}/{track}_sample.wav",
    }


def _get_extended_demo_lesson() -> Lesson:
    lesson_data = _get_raw_demo_lesson().model_dump(by_alias=True)
    lesson_data["metadata"].update(
        {
            "lesson_topic": "餐厅点餐进阶",
            "lesson_duration_minutes": 60,
        }
    )
    lesson_data["transcripts"]["teacher"].extend(
        [
            {
                "segment_id": "t_010",
                "speaker": "teacher",
                "start_time": 190.0,
                "end_time": 202.8,
                "text": "Let's extend the restaurant role play. This time you will greet the server, order, ask about spice level, and pay in Chinese.",
                "language_tags": ["en", "zh-CN"],
                "asr_confidence": 0.96,
            },
            {
                "segment_id": "t_011",
                "speaker": "teacher",
                "start_time": 218.0,
                "end_time": 229.4,
                "text": "The server asks: 你要辣的吗？ How would you answer if you do not want spicy food?",
                "language_tags": ["en", "zh-CN"],
                "asr_confidence": 0.94,
            },
            {
                "segment_id": "t_012",
                "speaker": "teacher",
                "start_time": 245.0,
                "end_time": 257.6,
                "text": "Good. Say 我不要辣的, or 请不要放辣. Both are natural ways to make the request clear.",
                "language_tags": ["en", "zh-CN"],
                "asr_confidence": 0.95,
            },
            {
                "segment_id": "t_013",
                "speaker": "teacher",
                "start_time": 275.0,
                "end_time": 289.3,
                "text": "Yes. 少放一点辣 means use less chili. Please repeat: 请少放一点辣，谢谢。",
                "language_tags": ["en", "zh-CN"],
                "asr_confidence": 0.93,
            },
            {
                "segment_id": "t_014",
                "speaker": "teacher",
                "start_time": 312.0,
                "end_time": 324.5,
                "text": "Now ask for the total price and whether you can pay by card: 一共多少钱？可以刷卡吗？",
                "language_tags": ["en", "zh-CN"],
                "asr_confidence": 0.96,
            },
            {
                "segment_id": "t_015",
                "speaker": "teacher",
                "start_time": 345.0,
                "end_time": 359.2,
                "text": "Listen to the rhythm in 一共多少钱 and keep 刷卡 as two clear syllables. Please repeat both expressions.",
                "language_tags": ["en", "zh-CN"],
                "asr_confidence": 0.92,
            },
            {
                "segment_id": "t_016",
                "speaker": "teacher",
                "start_time": 386.0,
                "end_time": 400.4,
                "text": "Final challenge: complete the whole order without my help. Include a drink, noodles, the spice request, and the price question.",
                "language_tags": ["en", "zh-CN"],
                "asr_confidence": 0.94,
            },
            {
                "segment_id": "t_017",
                "speaker": "teacher",
                "start_time": 435.0,
                "end_time": 449.8,
                "text": "Very good. Your sentence order was clear. Next, slow down slightly when saying 一共多少钱 and make the tone change in 不要 easier to hear.",
                "language_tags": ["en", "zh-CN"],
                "asr_confidence": 0.93,
            },
            {
                "segment_id": "t_018",
                "speaker": "teacher",
                "start_time": 462.0,
                "end_time": 478.0,
                "text": "After class, please record the complete restaurant dialogue twice: once as the customer and once as the server.",
                "language_tags": ["en"],
                "asr_confidence": 0.95,
            },
            {
                "segment_id": "t_019",
                "speaker": "teacher",
                "start_time": 480.0,
                "end_time": 495.5,
                "text": "Also review these expressions: 不要辣, 少放一点辣, 一共多少钱, and 可以刷卡吗。",
                "language_tags": ["en", "zh-CN"],
                "asr_confidence": 0.94,
            },
            {
                "segment_id": "t_020",
                "speaker": "teacher",
                "start_time": 510.0,
                "end_time": 524.6,
                "text": "Next lesson, we will practice making a reservation and telling the restaurant how many people are coming.",
                "language_tags": ["en"],
                "asr_confidence": 0.96,
            },
        ]
    )
    lesson_data["transcripts"]["student"].extend(
        [
            {
                "segment_id": "s_006",
                "speaker": "student",
                "start_time": 207.0,
                "end_time": 213.8,
                "text": "服务员，你好，我想点菜。",
                "language_tags": ["zh-CN"],
                "asr_confidence": 0.9,
            },
            {
                "segment_id": "s_007",
                "speaker": "student",
                "start_time": 233.0,
                "end_time": 239.2,
                "text": "我不辣，谢谢。",
                "language_tags": ["zh-CN"],
                "asr_confidence": 0.84,
            },
            {
                "segment_id": "s_008",
                "speaker": "student",
                "start_time": 261.0,
                "end_time": 267.5,
                "text": "可以说少放辣吗？",
                "language_tags": ["zh-CN"],
                "asr_confidence": 0.88,
            },
            {
                "segment_id": "s_009",
                "speaker": "student",
                "start_time": 294.0,
                "end_time": 302.2,
                "text": "请少放一点辣，谢谢。",
                "language_tags": ["zh-CN"],
                "asr_confidence": 0.9,
            },
            {
                "segment_id": "s_010",
                "speaker": "student",
                "start_time": 329.0,
                "end_time": 337.4,
                "text": "一共多少钱？可以刷卡吗？",
                "language_tags": ["zh-CN"],
                "asr_confidence": 0.87,
            },
            {
                "segment_id": "s_011",
                "speaker": "student",
                "start_time": 365.0,
                "end_time": 374.1,
                "text": "一共多少钱？可以刷卡吗？",
                "language_tags": ["zh-CN"],
                "asr_confidence": 0.91,
            },
            {
                "segment_id": "s_012",
                "speaker": "student",
                "start_time": 410.0,
                "end_time": 425.8,
                "text": "服务员，你好。我想要一杯果汁和一碗牛肉面，请不要放辣。一共多少钱？",
                "language_tags": ["zh-CN"],
                "asr_confidence": 0.89,
            },
        ]
    )
    lesson_data["practice_clips"].extend(
        [
            {
                "clip_id": "clip_005",
                "student_segment_id": "s_009",
                "audio_uri": "mock://audio/demo_001/extended/student_294000_302200.wav",
                "clip_start": 293.7,
                "clip_end": 302.7,
                "reference_text": "请少放一点辣，谢谢",
                "reference_source": "teacher_model_sentence",
                "reference_confidence": "high",
                "should_assess_pronunciation": True,
            },
            {
                "clip_id": "clip_006",
                "student_segment_id": "s_011",
                "audio_uri": "mock://audio/demo_001/extended/student_365000_374100.wav",
                "clip_start": 364.7,
                "clip_end": 374.6,
                "reference_text": "一共多少钱？可以刷卡吗？",
                "reference_source": "teacher_repeat_instruction",
                "reference_confidence": "high",
                "should_assess_pronunciation": True,
            },
            {
                "clip_id": "clip_007",
                "student_segment_id": "s_012",
                "audio_uri": "mock://audio/demo_001/extended/student_410000_425800.wav",
                "clip_start": 409.7,
                "clip_end": 426.3,
                "reference_text": "我想要一杯果汁和一碗牛肉面，请不要放辣",
                "reference_source": "role_play_target",
                "reference_confidence": "medium",
                "should_assess_pronunciation": True,
            },
        ]
    )
    lesson_data["pronunciation_assessments"].extend(
        [
            {
                "assessment_id": "pa_005",
                "clip_id": "clip_005",
                "reference_text": "请少放一点辣，谢谢",
                "pronunciation_score": 78,
                "accuracy_score": 76,
                "fluency_score": 82,
                "completeness_score": 100,
                "prosody_score": 74,
                "low_score_words": [{"word": "少放", "accuracy_score": 64, "error_type": "Tone"}],
                "model_confidence": "medium",
                "teacher_confirmation_required": True,
            },
            {
                "assessment_id": "pa_006",
                "clip_id": "clip_006",
                "reference_text": "一共多少钱？可以刷卡吗？",
                "pronunciation_score": 85,
                "accuracy_score": 84,
                "fluency_score": 88,
                "completeness_score": 100,
                "prosody_score": 82,
                "low_score_words": [{"word": "刷卡", "accuracy_score": 72, "error_type": "Initial"}],
                "model_confidence": "medium",
                "teacher_confirmation_required": True,
            },
            {
                "assessment_id": "pa_007",
                "clip_id": "clip_007",
                "reference_text": "完整餐厅点餐对话",
                "pronunciation_score": 81,
                "accuracy_score": 79,
                "fluency_score": 86,
                "completeness_score": 96,
                "prosody_score": 78,
                "low_score_words": [{"word": "牛肉面", "accuracy_score": 69, "error_type": "Tone"}],
                "model_confidence": "medium",
                "teacher_confirmation_required": True,
            },
        ]
    )
    lesson_data["teacher_review"] = {"status": "pending"}
    lesson_data["teacher_edit_log"] = []
    return Lesson.model_validate(lesson_data)


def _audio_ingest_metadata(
    *,
    teacher_file: dict[str, Any],
    student_file: dict[str, Any],
    lesson: Lesson,
    mode: str,
    use_sample: bool,
    sample_id: str,
    input_source: str,
    asr_mode: str,
    pronunciation_mode: str,
    fallback_reason: str = "",
) -> dict[str, Any]:
    source = "demo_sample" if use_sample else input_source
    asr_step = {
        "mock": "mock_asr",
        "deepgram": "deepgram_asr",
        "bailian": "bailian_asr",
    }.get(asr_mode, f"{asr_mode}_asr")
    pronunciation_step = {
        "mock": "mock_pronunciation_assessment",
        "azure": "azure_pronunciation_assessment",
        "skipped": "pronunciation_skipped",
    }.get(pronunciation_mode, f"{pronunciation_mode}_pronunciation_assessment")
    max_end_time = max(
        [
            segment.end_time
            for segment in [*lesson.transcripts.teacher, *lesson.transcripts.student]
        ],
        default=0,
    )
    return {
        "mode": mode,
        "source": source,
        "input_source": input_source,
        "sample_id": sample_id if use_sample else None,
        "sample_label": "extended_lesson" if sample_id == "extended" else "standard_lesson",
        "status": "mock_processed" if asr_mode == "mock" else "processed",
        "asr_mode": asr_mode,
        "pronunciation_mode": pronunciation_mode,
        "fallback_reason": fallback_reason,
        "pipeline": [
            {"step": "upload", "status": "passed"},
            {"step": "dual_track_binding", "status": "passed"},
            {"step": asr_step, "status": "passed"},
            {"step": pronunciation_step, "status": "passed"},
            {"step": "lesson_object_mapping", "status": "passed"},
        ],
        "tracks": {
            "teacher": teacher_file,
            "student": student_file,
        },
        "mock_outputs": {
            "teacher_segments": len(lesson.transcripts.teacher),
            "student_segments": len(lesson.transcripts.student),
            "practice_clips": len(lesson.practice_clips),
            "pronunciation_assessments": len(lesson.pronunciation_assessments),
            "duration_seconds": round(max_end_time, 1),
        },
        "note": (
            "Demo mode: audio input is accepted and mapped to the existing "
            "mock transcript, evidence, and pronunciation assessment pipeline."
        ),
    }


def _path_from_summary(summary: dict[str, Any]) -> Path | None:
    local_path = summary.get("local_path")
    if not isinstance(local_path, str) or not local_path:
        return None
    path = ROOT_DIR / local_path
    return path if path.exists() else None


def _mock_pronunciation_for_clips(lesson: Lesson) -> list[PronunciationAssessment]:
    assessments: list[PronunciationAssessment] = []
    for index, clip in enumerate(lesson.practice_clips, start=1):
        confidence = "medium" if clip.reference_confidence != "low" else "low"
        base_score = 84 if clip.reference_confidence == "high" else 76
        assessments.append(
            PronunciationAssessment(
                assessment_id=f"pa_{index:03d}",
                clip_id=clip.clip_id,
                reference_text=clip.reference_text,
                pronunciation_score=base_score,
                accuracy_score=max(60, base_score - 3),
                fluency_score=min(95, base_score + 4),
                completeness_score=100,
                prosody_score=max(60, base_score - 5),
                low_score_words=[
                    LowScoreWord(
                        word=clip.reference_text[:4] or "片段",
                        accuracy_score=max(55, base_score - 14),
                        error_type="NeedsTeacherReview",
                    )
                ]
                if confidence != "high"
                else [],
                model_confidence=confidence,
                teacher_confirmation_required=True,
            )
        )
    return assessments


def _find_ffmpeg() -> str | None:
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
    try:
        import imageio_ffmpeg  # type: ignore
    except ImportError:
        return None
    try:
        return str(imageio_ffmpeg.get_ffmpeg_exe())
    except Exception:
        logger.exception("Unable to locate ffmpeg through imageio-ffmpeg.")
        return None


def _slice_practice_clips(
    *,
    lesson: Lesson,
    student_audio_path: Path,
) -> dict[str, Path]:
    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        return {}
    clips_dir = student_audio_path.parent / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    clip_paths: dict[str, Path] = {}
    for clip in lesson.practice_clips:
        output = clips_dir / f"{clip.clip_id}.wav"
        duration = max(0.1, clip.clip_end - clip.clip_start)
        command = [
            ffmpeg,
            "-y",
            "-ss",
            str(max(0.0, clip.clip_start)),
            "-t",
            str(duration),
            "-i",
            str(student_audio_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(output),
        ]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode == 0 and output.exists():
            clip.audio_uri = f"file://{_display_data_path(output)}"
            clip_paths[clip.clip_id] = output
    return clip_paths


def _apply_lesson_metadata(lesson: Lesson, metadata_json: str | None) -> Lesson:
    if not metadata_json:
        return lesson
    try:
        metadata = json.loads(metadata_json)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="lesson_metadata must be valid JSON.")
    if not isinstance(metadata, dict):
        raise HTTPException(status_code=400, detail="lesson_metadata must be a JSON object.")

    mapping = {
        "studentName": "student_name",
        "studentAge": "student_age",
        "studentLevel": "student_level",
        "teacherName": "teacher_name",
        "topic": "lesson_topic",
        "date": "lesson_date",
        "duration": "lesson_duration_minutes",
    }
    lesson_data = lesson.model_dump(by_alias=True)
    for source_key, target_key in mapping.items():
        if source_key in metadata and metadata[source_key] not in (None, ""):
            lesson_data["metadata"][target_key] = metadata[source_key]
    return Lesson.model_validate(lesson_data)


def _configured_asr_provider() -> str | None:
    provider = os.getenv("ASR_PROVIDER", "").strip().lower()
    if provider == "deepgram" and is_deepgram_configured():
        return "deepgram"
    if provider in {"bailian", "aliyun", "dashscope", "fun_asr_flash"} and is_bailian_configured():
        return "bailian"
    return None


def _transcribe_with_provider(
    *,
    provider: str,
    audio_path: Path,
    content_type: str,
    speaker: str,
    segment_prefix: str,
):
    if provider == "deepgram":
        return transcribe_deepgram_file(
            audio_path=audio_path,
            content_type=content_type,
            speaker=speaker,  # type: ignore[arg-type]
            segment_prefix=segment_prefix,
        )
    if provider == "bailian":
        return transcribe_bailian_file(
            audio_path=audio_path,
            content_type=content_type,
            speaker=speaker,  # type: ignore[arg-type]
            segment_prefix=segment_prefix,
        )
    raise RuntimeError(f"Unsupported ASR provider: {provider}")


def _maybe_apply_real_audio_pipeline(
    *,
    lesson: Lesson,
    teacher_file: dict[str, Any],
    student_file: dict[str, Any],
    include_pronunciation: bool,
) -> tuple[Lesson, str, str, str]:
    teacher_path = _path_from_summary(teacher_file)
    student_path = _path_from_summary(student_file)
    fallback_reasons: list[str] = []
    asr_provider = _configured_asr_provider()

    if not teacher_path or not student_path or not asr_provider:
        if (teacher_path or student_path) and not asr_provider:
            requested_provider = os.getenv("ASR_PROVIDER", "").strip() or "unset"
            fallback_reasons.append(
                f"ASR provider {requested_provider} is not configured; using mock transcript."
            )
        return lesson, "mock", "mock", " ".join(fallback_reasons)

    try:
        teacher_segments = _transcribe_with_provider(
            provider=asr_provider,
            audio_path=teacher_path,
            content_type=str(teacher_file.get("content_type") or "application/octet-stream"),
            speaker="teacher",
            segment_prefix="t",
        )
        student_segments = _transcribe_with_provider(
            provider=asr_provider,
            audio_path=student_path,
            content_type=str(student_file.get("content_type") or "application/octet-stream"),
            speaker="student",
            segment_prefix="s",
        )
    except Exception as error:
        logger.exception("%s ASR failed; falling back to mock transcript.", asr_provider)
        fallback_reasons.append(f"{asr_provider} ASR failed: {error}")
        return lesson, "mock", "mock", " ".join(fallback_reasons)

    if not teacher_segments and not student_segments:
        fallback_reasons.append(f"{asr_provider} returned no transcript segments; using mock transcript.")
        return lesson, "mock", "mock", " ".join(fallback_reasons)

    lesson.transcripts = Transcripts(teacher=teacher_segments, student=student_segments)
    lesson.practice_clips = extract_practice_clips(lesson.transcripts)
    lesson.pronunciation_assessments = []

    if not include_pronunciation or not lesson.practice_clips:
        return lesson, asr_provider, "skipped", " ".join(fallback_reasons)

    clip_paths = _slice_practice_clips(lesson=lesson, student_audio_path=student_path)
    if is_azure_pronunciation_configured() and clip_paths:
        assessments: list[PronunciationAssessment] = []
        try:
            for index, clip in enumerate(lesson.practice_clips, start=1):
                clip_path = clip_paths.get(clip.clip_id)
                if clip_path is None:
                    continue
                assessments.append(
                    assess_clip(
                        clip=clip,
                        audio_path=clip_path,
                        assessment_id=f"pa_{index:03d}",
                    )
                )
            lesson.pronunciation_assessments = assessments
            return lesson, asr_provider, "azure", " ".join(fallback_reasons)
        except Exception as error:
            logger.exception("Azure pronunciation assessment failed; using mock assessment.")
            fallback_reasons.append(f"Azure pronunciation assessment failed: {error}")
    elif is_azure_pronunciation_configured() and not clip_paths:
        fallback_reasons.append("ffmpeg clip slicing unavailable; using mock pronunciation assessment.")
    else:
        fallback_reasons.append("Azure pronunciation assessment not configured; using mock assessment.")

    lesson.pronunciation_assessments = _mock_pronunciation_for_clips(lesson)
    return lesson, asr_provider, "mock", " ".join(fallback_reasons)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/lessons/demo")
def get_demo_lesson() -> dict[str, Any]:
    lesson = _get_raw_demo_lesson()
    load_info = LESSON_LOAD_INFO.get(lesson.lesson_id, {})
    return {"lesson": lesson.model_dump(by_alias=True), **load_info}


@app.post("/api/lessons/demo/analyze")
def analyze_demo_lesson(request: AnalyzeRequest | None = None) -> dict[str, Any]:
    request = request or AnalyzeRequest()

    lesson = _get_raw_demo_lesson()
    analyzed = _run_mock_analysis(
        lesson,
        include_pronunciation=request.include_pronunciation,
        requested_agent_mode=request.mode,
    )
    workflow = LESSON_WORKFLOW_SUMMARY.get(analyzed.lesson_id, {})
    return {
        "lesson_id": analyzed.lesson_id,
        **LESSON_LOAD_INFO.get(analyzed.lesson_id, {}),
        "agent_mode": workflow.get("agent_mode", "mock"),
        "model_provider": workflow.get("model_provider", "mock"),
        "model_name": workflow.get("model_name", ""),
        "llm_trace": workflow.get("llm_trace", []),
        "schema_validation": workflow.get("schema_validation", {}),
        "fallback_reason": workflow.get("fallback_reason", ""),
        "revision_count": workflow.get("revision_count", analyzed.review_result.revision_count),
        "revision_history": workflow.get("revision_history", []),
        "stop_reason": workflow.get("stop_reason", ""),
        "draft_report": analyzed.draft_report.model_dump(),
        "evidence": analyzed.evidence.model_dump(),
        "confidence_scores": analyzed.confidence_scores,
        "risk_highlights": [
            item.model_dump() for item in analyzed.risk_highlights
        ],
        "rule_validation_result": analyzed.rule_validation_result.model_dump(by_alias=True),
        "review_result": analyzed.review_result.model_dump(by_alias=True),
        "workflow_trace": workflow.get("workflow_trace", LESSON_GRAPH_TRACE.get(analyzed.lesson_id, [])),
        "graph_trace": workflow.get("graph_trace", LESSON_GRAPH_TRACE.get(analyzed.lesson_id, [])),
    }


@app.post("/api/lessons/demo/audio-ingest")
async def ingest_demo_audio(
    teacher_audio: UploadFile | None = File(default=None),
    student_audio: UploadFile | None = File(default=None),
    mode: str = Form(default="mock"),
    agent_mode: str = Form(default="mock"),
    include_pronunciation: bool = Form(default=True),
    use_sample: bool = Form(default=False),
    sample_id: str = Form(default="standard"),
    input_source: str = Form(default="upload"),
    lesson_metadata: str | None = Form(default=None),
) -> dict[str, Any]:
    if mode != "mock":
        raise HTTPException(
            status_code=400,
            detail="Only mock audio ingest is implemented in this demo stage.",
        )
    if sample_id not in {"standard", "extended"}:
        raise HTTPException(
            status_code=400,
            detail="sample_id must be either 'standard' or 'extended'.",
        )
    if input_source not in {"sample", "upload", "record"}:
        raise HTTPException(
            status_code=400,
            detail="input_source must be one of: sample, upload, record.",
        )
    if agent_mode not in {"mock", "real"}:
        raise HTTPException(
            status_code=400,
            detail="agent_mode must be either 'mock' or 'real'.",
        )

    use_sample = use_sample or (teacher_audio is None and student_audio is None)
    input_source = "sample" if use_sample else input_source
    if not use_sample and (teacher_audio is None or student_audio is None):
        missing_tracks = [
            track
            for track, file in (("teacher_audio", teacher_audio), ("student_audio", student_audio))
            if file is None
        ]
        raise HTTPException(
            status_code=400,
            detail=f"Missing required audio track(s): {', '.join(missing_tracks)}.",
        )
    lesson = _get_extended_demo_lesson() if use_sample and sample_id == "extended" else _get_raw_demo_lesson()
    lesson = _apply_lesson_metadata(lesson, lesson_metadata)
    teacher_file = (
        _sample_file_summary("teacher", sample_id)
        if use_sample and teacher_audio is None
        else await _uploaded_file_summary(
            teacher_audio,
            "teacher",
            lesson_id=lesson.lesson_id,
            input_source=input_source,
        )
    )
    student_file = (
        _sample_file_summary("student", sample_id)
        if use_sample and student_audio is None
        else await _uploaded_file_summary(
            student_audio,
            "student",
            lesson_id=lesson.lesson_id,
            input_source=input_source,
        )
    )
    lesson, asr_mode, pronunciation_mode, fallback_reason = _maybe_apply_real_audio_pipeline(
        lesson=lesson,
        teacher_file=teacher_file,
        student_file=student_file,
        include_pronunciation=include_pronunciation,
    )
    lesson.teacher_edit_log.append(
        {
            "event": "mock_audio_ingest",
            "created_at": utc_now_iso(),
            "teacher_audio": teacher_file,
            "student_audio": student_file,
            "include_pronunciation": include_pronunciation,
            "use_sample": use_sample,
            "sample_id": sample_id if use_sample else None,
            "input_source": input_source,
            "asr_mode": asr_mode,
            "pronunciation_mode": pronunciation_mode,
            "fallback_reason": fallback_reason,
            "agent_mode": agent_mode,
        }
    )
    analyzed = _run_mock_analysis(
        lesson,
        include_pronunciation=include_pronunciation,
        requested_agent_mode=agent_mode,
    )
    workflow = LESSON_WORKFLOW_SUMMARY.get(analyzed.lesson_id, {})
    audio_ingest = _audio_ingest_metadata(
        teacher_file=teacher_file,
        student_file=student_file,
        lesson=analyzed,
        mode=mode,
        use_sample=use_sample,
        sample_id=sample_id,
        input_source=input_source,
        asr_mode=asr_mode,
        pronunciation_mode=pronunciation_mode,
        fallback_reason=fallback_reason,
    )
    lesson_payload = analyzed.model_dump(by_alias=True)
    return {
        **lesson_payload,
        **LESSON_LOAD_INFO.get(analyzed.lesson_id, {}),
        "audio_ingest": audio_ingest,
        "agent_mode": workflow.get("agent_mode", "mock"),
        "model_provider": workflow.get("model_provider", "mock"),
        "model_name": workflow.get("model_name", ""),
        "llm_trace": workflow.get("llm_trace", []),
        "schema_validation": workflow.get("schema_validation", {}),
        "fallback_reason": workflow.get("fallback_reason", ""),
        "revision_count": workflow.get("revision_count", analyzed.review_result.revision_count),
        "revision_history": workflow.get("revision_history", []),
        "stop_reason": workflow.get("stop_reason", ""),
        "rule_validation_result": analyzed.rule_validation_result.model_dump(by_alias=True),
        "review_result": analyzed.review_result.model_dump(by_alias=True),
        "workflow_trace": workflow.get("workflow_trace", LESSON_GRAPH_TRACE.get(analyzed.lesson_id, [])),
        "graph_trace": workflow.get("graph_trace", LESSON_GRAPH_TRACE.get(analyzed.lesson_id, [])),
    }


@app.post("/api/lessons/{lesson_id}/teacher-review")
def submit_teacher_review(
    lesson_id: str,
    request: TeacherReviewRequest,
) -> dict[str, Any]:
    lesson = _get_lesson(lesson_id)

    teacher_review = TeacherReview(
        status="confirmed",
        reviewed_at=utc_now_iso(),
        confirmed_homework_ids=request.confirmed_homework_ids,
        edited_homework_items=request.edited_homework_items,
        confirmed_risk_ids=request.confirmed_risk_ids,
        teacher_notes=request.teacher_notes,
        report_edits=request.report_edits,
    )
    lesson.teacher_review = teacher_review

    confirmed = set(request.confirmed_homework_ids)
    for homework in lesson.draft_report.homework_items:
        if homework.homework_id in confirmed:
            homework.teacher_confirmed = True

    edit_log = {
        "event": "teacher_review_submitted",
        "created_at": teacher_review.reviewed_at,
        "confirmed_homework_ids": request.confirmed_homework_ids,
        "confirmed_risk_ids": request.confirmed_risk_ids,
        "teacher_notes": request.teacher_notes,
        "edited_homework_count": len(request.edited_homework_items),
    }
    lesson.teacher_edit_log.append(edit_log)

    lesson = validate_rules(lesson, revision_count=lesson.review_result.revision_count)
    lesson = review_report(lesson, revision_count=lesson.review_result.revision_count)
    LESSON_STORE[lesson.lesson_id] = lesson
    LESSON_GRAPH_TRACE.setdefault(lesson.lesson_id, []).append(
        {
            "node": "teacher_review_gate",
            "route": "final_report"
            if lesson.teacher_review.status == "confirmed"
            else "end",
            "revision_count": lesson.review_result.revision_count,
            "status": "passed"
            if lesson.teacher_review.status == "confirmed"
            else "pending",
            "summary": "Teacher review submitted through API.",
            "metadata": {
                "teacher_review_status": lesson.teacher_review.status,
                "confirmed_homework_ids": request.confirmed_homework_ids,
                "confirmed_risk_ids": request.confirmed_risk_ids,
            },
        }
    )

    return {
        **LESSON_LOAD_INFO.get(lesson.lesson_id, {}),
        "teacher_review": lesson.teacher_review.model_dump(),
        "teacher_edit_log": lesson.teacher_edit_log,
        "rule_validation_result": lesson.rule_validation_result.model_dump(by_alias=True),
        "review_result": lesson.review_result.model_dump(by_alias=True),
        "workflow_trace": LESSON_GRAPH_TRACE.get(lesson.lesson_id, []),
        "graph_trace": LESSON_GRAPH_TRACE.get(lesson.lesson_id, []),
    }


@app.post("/api/lessons/{lesson_id}/finalize")
def finalize_lesson(
    lesson_id: str,
    request: FinalizeRequest | None = None,
) -> dict[str, Any]:
    request = request or FinalizeRequest()
    lesson = _get_lesson(lesson_id)

    graph_state = run_finalization_graph(
        lesson,
        audiences=request.audiences,
    )
    lesson = graph_state.lesson
    LESSON_STORE[lesson.lesson_id] = lesson
    LESSON_GRAPH_TRACE[lesson.lesson_id] = graph_state.trace()
    LESSON_WORKFLOW_SUMMARY[lesson.lesson_id] = graph_state.workflow_summary()
    workflow = graph_state.workflow_summary()

    return {
        **LESSON_LOAD_INFO.get(lesson.lesson_id, {}),
        "revision_count": workflow["revision_count"],
        "revision_history": workflow["revision_history"],
        "stop_reason": workflow["stop_reason"],
        "final_reports": lesson.final_reports.model_dump(),
        "workflow_trace": workflow["workflow_trace"],
        "graph_trace": workflow["graph_trace"],
    }
