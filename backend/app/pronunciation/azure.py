from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from backend.app.schemas import PracticeClip, PronunciationAssessment


@dataclass(frozen=True)
class AzurePronunciationConfig:
    key: str
    region: str
    language: str = "zh-CN"

    @classmethod
    def from_env(cls) -> "AzurePronunciationConfig | None":
        if os.getenv("PRON_PROVIDER", "").lower() != "azure":
            return None
        key = os.getenv("AZURE_SPEECH_KEY", "").strip()
        region = os.getenv("AZURE_SPEECH_REGION", "").strip()
        if not key or not region:
            return None
        return cls(
            key=key,
            region=region,
            language=os.getenv("AZURE_PRON_LANGUAGE", "zh-CN"),
        )


def is_azure_pronunciation_configured() -> bool:
    return AzurePronunciationConfig.from_env() is not None


def assess_clip(
    *,
    clip: PracticeClip,
    audio_path: Path,
    assessment_id: str,
) -> PronunciationAssessment:
    """Assess a clip through Azure Speech SDK when installed.

    The SDK is imported lazily so local demo and CI remain usable without Azure
    credentials or optional packages. If the SDK is absent, callers should fall
    back to deterministic mock assessment.
    """
    config = AzurePronunciationConfig.from_env()
    if config is None:
        raise RuntimeError("Azure pronunciation assessment is not configured.")

    try:
        import azure.cognitiveservices.speech as speechsdk  # type: ignore
    except ImportError as error:
        raise RuntimeError(
            "azure-cognitiveservices-speech is not installed."
        ) from error

    speech_config = speechsdk.SpeechConfig(subscription=config.key, region=config.region)
    speech_config.speech_recognition_language = config.language
    audio_config = speechsdk.audio.AudioConfig(filename=str(audio_path))
    pronunciation_config = speechsdk.PronunciationAssessmentConfig(
        reference_text=clip.reference_text,
        grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
        granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
        enable_miscue=True,
    )
    recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config,
        audio_config=audio_config,
    )
    pronunciation_config.apply_to(recognizer)
    result = recognizer.recognize_once()
    assessment = speechsdk.PronunciationAssessmentResult(result)

    low_score_words = []
    for word in getattr(assessment, "words", []) or []:
        accuracy = float(getattr(word, "accuracy_score", 0) or 0)
        if accuracy < 75:
            low_score_words.append(
                {
                    "word": getattr(word, "word", ""),
                    "accuracy_score": accuracy,
                    "error_type": getattr(word, "error_type", "") or "LowScore",
                }
            )

    return PronunciationAssessment(
        assessment_id=assessment_id,
        clip_id=clip.clip_id,
        reference_text=clip.reference_text,
        pronunciation_score=float(assessment.pronunciation_score),
        accuracy_score=float(assessment.accuracy_score),
        fluency_score=float(assessment.fluency_score),
        completeness_score=float(assessment.completeness_score),
        prosody_score=float(getattr(assessment, "prosody_score", 0) or 0),
        low_score_words=low_score_words,
        model_confidence="medium",
        teacher_confirmation_required=True,
    )
