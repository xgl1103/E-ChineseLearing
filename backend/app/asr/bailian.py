from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from backend.app.schemas import TranscriptSegment


Speaker = Literal["teacher", "student"]
SUPPORTED_AUDIO_SUFFIXES = {".wav", ".mp3", ".aac", ".opus"}


@dataclass(frozen=True)
class BailianASRConfig:
    api_key: str
    model: str = "fun-asr-flash-2026-06-15"
    base_url: str = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"

    @classmethod
    def from_env(cls) -> "BailianASRConfig | None":
        provider = os.getenv("ASR_PROVIDER", "").strip().lower()
        if provider not in {"bailian", "aliyun", "dashscope", "fun_asr_flash"}:
            return None
        api_key = (
            os.getenv("BAILIAN_API_KEY", "").strip()
            or os.getenv("DASHSCOPE_API_KEY", "").strip()
        )
        if not api_key:
            return None
        base_url = os.getenv("BAILIAN_ASR_BASE_URL", "").strip()
        if not base_url:
            workspace_id = os.getenv("BAILIAN_WORKSPACE_ID", "").strip()
            if workspace_id:
                base_url = (
                    f"https://{workspace_id}.dashscope.aliyuncs.com"
                    "/api/v1/services/aigc/multimodal-generation/generation"
                )
            else:
                base_url = cls.base_url
        return cls(
            api_key=api_key,
            model=os.getenv("BAILIAN_ASR_MODEL", cls.model).strip() or cls.model,
            base_url=base_url,
        )


def is_bailian_configured() -> bool:
    return BailianASRConfig.from_env() is not None


def transcribe_file(
    *,
    audio_path: Path,
    content_type: str,
    speaker: Speaker,
    segment_prefix: str,
) -> list[TranscriptSegment]:
    config = BailianASRConfig.from_env()
    if config is None:
        raise RuntimeError("Bailian Fun-ASR is not configured.")

    prepared_audio_path, prepared_content_type = _prepare_audio(audio_path, content_type)
    data_uri = _audio_data_uri(prepared_audio_path, prepared_content_type)
    body = {
        "model": config.model,
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": data_uri,
                            }
                        }
                    ],
                }
            ]
        },
        "parameters": {
            "format": _format_for_content_type(prepared_content_type),
            "sample_rate": "16000",
        },
    }
    request = urllib.request.Request(
        config.base_url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
            "X-DashScope-SSE": "disable",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {error.code}: {detail}") from error

    return normalize_bailian_response(
        payload=payload,
        speaker=speaker,
        segment_prefix=segment_prefix,
        fallback_duration_seconds=_audio_duration_seconds(prepared_audio_path),
    )


def normalize_bailian_response(
    *,
    payload: dict[str, Any],
    speaker: Speaker,
    segment_prefix: str,
    fallback_duration_seconds: float = 0.0,
) -> list[TranscriptSegment]:
    sentence = _nested_get(payload, ["output", "output", "sentence"])
    if isinstance(sentence, dict):
        text = str(sentence.get("text") or "").strip()
        if text:
            start_time = _milliseconds_to_seconds(sentence.get("begin_time"), default=0.0)
            end_time = _milliseconds_to_seconds(
                sentence.get("end_time"),
                default=fallback_duration_seconds,
            )
            return [
                TranscriptSegment(
                    segment_id=f"{segment_prefix}_001",
                    speaker=speaker,
                    start_time=start_time,
                    end_time=max(end_time, start_time),
                    text=text,
                    language_tags=_language_tags(text),
                    asr_confidence=float(sentence.get("confidence") or 0.85),
                )
            ]

    sentences = _nested_get(payload, ["output", "output", "sentences"])
    if isinstance(sentences, list):
        segments: list[TranscriptSegment] = []
        for index, item in enumerate(sentences, start=1):
            if not isinstance(item, dict):
                continue
            text = str(item.get("text") or item.get("sentence") or "").strip()
            if not text:
                continue
            start_time = _milliseconds_to_seconds(item.get("begin_time"), default=0.0)
            end_time = _milliseconds_to_seconds(item.get("end_time"), default=start_time)
            segments.append(
                TranscriptSegment(
                    segment_id=f"{segment_prefix}_{index:03d}",
                    speaker=speaker,
                    start_time=start_time,
                    end_time=max(end_time, start_time),
                    text=text,
                    language_tags=_language_tags(text),
                    asr_confidence=float(item.get("confidence") or 0.85),
                )
            )
        if segments:
            return segments

    text = _extract_text(payload)
    if not text:
        return []
    return [
        TranscriptSegment(
            segment_id=f"{segment_prefix}_001",
            speaker=speaker,
            start_time=0.0,
            end_time=max(0.0, fallback_duration_seconds),
            text=text,
            language_tags=_language_tags(text),
            asr_confidence=0.85,
        )
    ]


def _prepare_audio(audio_path: Path, content_type: str) -> tuple[Path, str]:
    suffix = audio_path.suffix.lower()
    if suffix in SUPPORTED_AUDIO_SUFFIXES:
        return audio_path, _content_type_for_suffix(suffix, content_type)

    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        return audio_path, content_type or "application/octet-stream"

    output = audio_path.with_suffix(".bailian-asr.wav")
    command = [
        ffmpeg,
        "-y",
        "-i",
        str(audio_path),
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
        timeout=60,
        check=False,
    )
    if result.returncode != 0 or not output.exists():
        return audio_path, content_type or "application/octet-stream"
    return output, "audio/wav"


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
        return None


def _audio_data_uri(audio_path: Path, content_type: str) -> str:
    encoded = base64.b64encode(audio_path.read_bytes()).decode("ascii")
    return f"data:{content_type or 'application/octet-stream'};base64,{encoded}"


def _audio_duration_seconds(audio_path: Path) -> float:
    if audio_path.suffix.lower() != ".wav":
        return 0.0
    try:
        with wave.open(str(audio_path), "rb") as wav:
            frame_rate = wav.getframerate() or 1
            return wav.getnframes() / frame_rate
    except wave.Error:
        return 0.0


def _content_type_for_suffix(suffix: str, fallback: str) -> str:
    return {
        ".wav": "audio/wav",
        ".mp3": "audio/mpeg",
        ".aac": "audio/aac",
        ".opus": "audio/opus",
    }.get(suffix, fallback or "application/octet-stream")


def _format_for_content_type(content_type: str) -> str:
    normalized = content_type.lower()
    if "wav" in normalized:
        return "wav"
    if "mpeg" in normalized or "mp3" in normalized:
        return "mp3"
    if "aac" in normalized:
        return "aac"
    if "opus" in normalized:
        return "opus"
    return "wav"


def _nested_get(payload: dict[str, Any], path: list[str]) -> Any:
    current: Any = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _extract_text(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("text", "transcript"):
            item = value.get(key)
            if isinstance(item, str) and item.strip():
                return item.strip()
        for item in value.values():
            text = _extract_text(item)
            if text:
                return text
    if isinstance(value, list):
        fragments = [_extract_text(item) for item in value]
        return "\n".join(fragment for fragment in fragments if fragment).strip()
    return ""


def _language_tags(text: str) -> list[str]:
    if any("\u3400" <= char <= "\u9fff" for char in text):
        return ["zh-CN", "en"]
    return ["en"]


def _milliseconds_to_seconds(value: Any, *, default: float) -> float:
    try:
        return float(value) / 1000
    except (TypeError, ValueError):
        return default
