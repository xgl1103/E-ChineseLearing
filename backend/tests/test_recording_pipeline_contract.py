from __future__ import annotations

import math
import wave
from pathlib import Path

from backend.app.asr.bailian import normalize_bailian_response
from backend.app.asr.deepgram import normalize_deepgram_response
from backend.app.pipeline.practice_clip_extractor import extract_practice_clips
from backend.app.schemas import PracticeClip, TranscriptSegment, Transcripts
import backend.app.main as app_main


def _write_test_wav(path: Path, duration_seconds: float = 4.0) -> None:
    sample_rate = 16000
    frame_count = int(sample_rate * duration_seconds)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        frames = bytearray()
        for index in range(frame_count):
            value = int(9000 * math.sin(2 * math.pi * 440 * index / sample_rate))
            frames.extend(value.to_bytes(2, byteorder="little", signed=True))
        wav.writeframes(bytes(frames))


def test_deepgram_normalization() -> None:
    zh_order = "\u4f60\u597d\uff0c\u6211\u60f3\u70b9\u83dc\u3002"
    payload = {
        "results": {
            "utterances": [
                {
                    "start": 1.2,
                    "end": 3.4,
                    "transcript": zh_order,
                    "confidence": 0.91,
                    "language": "zh-CN",
                },
                {
                    "start": 4.0,
                    "end": 5.5,
                    "transcript": "Can I pay by card?",
                    "confidence": 0.87,
                    "language": "en",
                },
            ]
        }
    }

    segments = normalize_deepgram_response(
        payload=payload,
        speaker="student",
        segment_prefix="s",
    )

    assert [segment.segment_id for segment in segments] == ["s_001", "s_002"]
    assert all(segment.speaker == "student" for segment in segments)
    assert segments[0].text == zh_order
    assert segments[0].language_tags == ["zh-CN"]


def test_bailian_fun_asr_normalization() -> None:
    zh_order = "\u4f60\u597d\uff0c\u6211\u60f3\u70b9\u83dc\u3002"
    payload = {
        "output": {
            "output": {
                "sentence": {
                    "begin_time": 1200,
                    "end_time": 3400,
                    "text": zh_order,
                }
            }
        }
    }

    segments = normalize_bailian_response(
        payload=payload,
        speaker="student",
        segment_prefix="s",
        fallback_duration_seconds=5.0,
    )

    assert len(segments) == 1
    assert segments[0].segment_id == "s_001"
    assert segments[0].speaker == "student"
    assert segments[0].start_time == 1.2
    assert segments[0].end_time == 3.4
    assert segments[0].text == zh_order
    assert "zh-CN" in segments[0].language_tags


def test_practice_clip_extraction_from_student_chinese() -> None:
    zh_order = "\u4f60\u597d\uff0c\u6211\u60f3\u70b9\u83dc\u3002"
    zh_long = "\u6211\u60f3\u8981\u4e00\u4e2a\u82f9\u679c\u3002"
    transcripts = Transcripts(
        teacher=[
            TranscriptSegment(
                segment_id="t_001",
                speaker="teacher",
                start_time=0,
                end_time=1,
                text=f"Please repeat: {zh_order}",
                language_tags=["en", "zh-CN"],
                asr_confidence=0.95,
            )
        ],
        student=[
            TranscriptSegment(
                segment_id="s_001",
                speaker="student",
                start_time=2,
                end_time=5,
                text=zh_order,
                language_tags=["zh-CN"],
                asr_confidence=0.9,
            ),
            TranscriptSegment(
                segment_id="s_002",
                speaker="student",
                start_time=6,
                end_time=8,
                text="I have a question.",
                language_tags=["en"],
                asr_confidence=0.9,
            ),
            TranscriptSegment(
                segment_id="s_003",
                speaker="student",
                start_time=9,
                end_time=35,
                text=zh_long,
                language_tags=["zh-CN"],
                asr_confidence=0.9,
            ),
        ],
    )

    clips = extract_practice_clips(transcripts)

    assert len(clips) == 1
    assert clips[0].clip_id == "clip_001"
    assert clips[0].student_segment_id == "s_001"
    assert clips[0].reference_source == "nearby_teacher_model_sentence"
    assert clips[0].reference_confidence == "medium"
    assert clips[0].should_assess_pronunciation is True


def test_practice_clip_slicing_outputs_azure_compatible_wav(tmp_path: Path) -> None:
    source = tmp_path / "student.wav"
    _write_test_wav(source)
    lesson = app_main._get_raw_demo_lesson()
    lesson.practice_clips = [
        PracticeClip(
            clip_id="clip_001",
            student_segment_id="s_001",
            audio_uri="mock://audio/generated/s_001.wav",
            clip_start=0.5,
            clip_end=2.5,
            reference_text="\u4f60\u597d",
            reference_source="test",
            reference_confidence="medium",
            should_assess_pronunciation=True,
        )
    ]

    clip_paths = app_main._slice_practice_clips(
        lesson=lesson,
        student_audio_path=source,
    )

    output = clip_paths["clip_001"]
    assert output.suffix == ".wav"
    assert output.exists()
    assert lesson.practice_clips[0].audio_uri.endswith("clip_001.wav")

    with wave.open(str(output), "rb") as wav:
        assert wav.getnchannels() == 1
        assert wav.getframerate() == 16000
        assert wav.getsampwidth() == 2


def test_azure_sdk_import_and_mock_pronunciation_fallback() -> None:
    import azure.cognitiveservices.speech as speechsdk

    assert speechsdk is not None
    lesson = app_main._get_raw_demo_lesson()
    lesson.practice_clips = [
        PracticeClip(
            clip_id="clip_001",
            student_segment_id="s_001",
            audio_uri="mock://audio/generated/s_001.wav",
            clip_start=0,
            clip_end=1,
            reference_text="\u4f60\u597d",
            reference_source="student_transcript_fallback",
            reference_confidence="low",
            should_assess_pronunciation=True,
        )
    ]

    assessments = app_main._mock_pronunciation_for_clips(lesson)

    assert len(assessments) == 1
    assert assessments[0].clip_id == "clip_001"
    assert assessments[0].teacher_confirmation_required is True


def test_audio_ingest_metadata_marks_skipped_pronunciation() -> None:
    lesson = app_main._get_raw_demo_lesson()

    metadata = app_main._audio_ingest_metadata(
        teacher_file={"status": "received"},
        student_file={"status": "received"},
        lesson=lesson,
        mode="mock",
        use_sample=False,
        sample_id="standard",
        input_source="upload",
        asr_mode="bailian",
        pronunciation_mode="skipped",
    )

    assert metadata["asr_mode"] == "bailian"
    assert [item["step"] for item in metadata["pipeline"]] == [
        "upload",
        "dual_track_binding",
        "bailian_asr",
        "pronunciation_skipped",
        "lesson_object_mapping",
    ]
