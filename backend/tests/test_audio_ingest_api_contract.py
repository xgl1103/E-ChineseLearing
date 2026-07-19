from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from backend.app.main import app


client = TestClient(app)


@pytest.fixture(autouse=True)
def disable_real_audio_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASR_PROVIDER", "")
    monkeypatch.setenv("PRON_PROVIDER", "")


def test_audio_ingest_sample_extended() -> None:
    response = client.post(
        "/api/lessons/demo/audio-ingest",
        data={
            "mode": "mock",
            "input_source": "sample",
            "use_sample": "true",
            "sample_id": "extended",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["audio_ingest"]["input_source"] == "sample"
    assert payload["audio_ingest"]["tracks"]["teacher"]["status"] == "sample_loaded"
    assert len(payload["transcripts"]["teacher"]) == 20
    assert len(payload["transcripts"]["student"]) == 12
    assert len(payload["practice_clips"]) == 7
    assert len(payload["pronunciation_assessments"]) == 7


def test_audio_ingest_record_persists_both_tracks() -> None:
    response = client.post(
        "/api/lessons/demo/audio-ingest",
        data={
            "mode": "mock",
            "input_source": "record",
            "lesson_metadata": '{"studentName":"API Record","topic":"Contract Test","duration":10}',
        },
        files={
            "teacher_audio": ("teacher.webm", b"teacher bytes", "audio/webm"),
            "student_audio": ("student.webm", b"student bytes", "audio/webm"),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    ingest = payload["audio_ingest"]
    assert ingest["input_source"] == "record"
    assert ingest["asr_mode"] == "mock"
    assert "ASR provider" in ingest["fallback_reason"]
    assert ingest["tracks"]["teacher"]["status"] == "received"
    assert ingest["tracks"]["student"]["status"] == "received"
    assert ingest["tracks"]["teacher"]["local_path"]
    assert ingest["tracks"]["student"]["local_path"]
    assert payload["metadata"]["student_name"] == "API Record"


def test_audio_ingest_rejects_missing_single_track() -> None:
    response = client.post(
        "/api/lessons/demo/audio-ingest",
        data={"mode": "mock", "input_source": "record"},
        files={
            "teacher_audio": ("teacher.webm", b"teacher bytes", "audio/webm"),
        },
    )

    assert response.status_code == 400
    assert "student_audio" in response.json()["detail"]


def test_audio_ingest_rejects_non_audio_file() -> None:
    response = client.post(
        "/api/lessons/demo/audio-ingest",
        data={"mode": "mock", "input_source": "record"},
        files={
            "teacher_audio": ("teacher.txt", b"not audio", "text/plain"),
            "student_audio": ("student.webm", b"student bytes", "audio/webm"),
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "teacher_audio must be an audio file."
