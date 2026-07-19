from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from backend.app.schemas import TranscriptSegment


Speaker = Literal["teacher", "student"]


@dataclass(frozen=True)
class DeepgramConfig:
    api_key: str
    model: str = "nova-3"

    @classmethod
    def from_env(cls) -> "DeepgramConfig | None":
        if os.getenv("ASR_PROVIDER", "").lower() != "deepgram":
            return None
        api_key = os.getenv("DEEPGRAM_API_KEY", "").strip()
        if not api_key:
            return None
        return cls(api_key=api_key, model=os.getenv("DEEPGRAM_MODEL", "nova-3"))


def is_deepgram_configured() -> bool:
    return DeepgramConfig.from_env() is not None


def transcribe_file(
    *,
    audio_path: Path,
    content_type: str,
    speaker: Speaker,
    segment_prefix: str,
) -> list[TranscriptSegment]:
    config = DeepgramConfig.from_env()
    if config is None:
        raise RuntimeError("Deepgram is not configured.")

    params = urllib.parse.urlencode(
        {
            "model": config.model,
            "smart_format": "true",
            "utterances": "true",
            "punctuate": "true",
            "detect_language": "true",
        }
    )
    request = urllib.request.Request(
        f"https://api.deepgram.com/v1/listen?{params}",
        data=audio_path.read_bytes(),
        headers={
            "Authorization": f"Token {config.api_key}",
            "Content-Type": content_type or "application/octet-stream",
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=90) as response:
        payload = json.loads(response.read().decode("utf-8"))

    return normalize_deepgram_response(
        payload=payload,
        speaker=speaker,
        segment_prefix=segment_prefix,
    )


def normalize_deepgram_response(
    *,
    payload: dict[str, Any],
    speaker: Speaker,
    segment_prefix: str,
) -> list[TranscriptSegment]:
    utterances = payload.get("results", {}).get("utterances") or []
    if utterances:
        return [
            TranscriptSegment(
                segment_id=f"{segment_prefix}_{index:03d}",
                speaker=speaker,
                start_time=float(item.get("start") or 0),
                end_time=float(item.get("end") or item.get("start") or 0),
                text=str(item.get("transcript") or "").strip(),
                language_tags=_language_tags(item),
                asr_confidence=float(item.get("confidence") or 0),
            )
            for index, item in enumerate(utterances, start=1)
            if str(item.get("transcript") or "").strip()
        ]

    alternatives = (
        payload.get("results", {})
        .get("channels", [{}])[0]
        .get("alternatives", [{}])
    )
    best = alternatives[0] if alternatives else {}
    transcript = str(best.get("transcript") or "").strip()
    if not transcript:
        return []
    words = best.get("words") or []
    start = float(words[0].get("start", 0)) if words else 0.0
    end = float(words[-1].get("end", start)) if words else start
    confidence = float(best.get("confidence") or 0)
    return [
        TranscriptSegment(
            segment_id=f"{segment_prefix}_001",
            speaker=speaker,
            start_time=start,
            end_time=end,
            text=transcript,
            language_tags=_language_tags(best),
            asr_confidence=confidence,
        )
    ]


def _language_tags(item: dict[str, Any]) -> list[str]:
    language = item.get("language") or item.get("detected_language")
    if isinstance(language, str) and language:
        return [language]
    return ["en", "zh-CN"]
