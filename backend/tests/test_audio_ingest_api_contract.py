from __future__ import annotations

import time

from fastapi.testclient import TestClient
import pytest

from backend.app.main import ANALYSIS_JOBS, ANALYSIS_JOB_LOCK, app


client = TestClient(app)


@pytest.fixture(autouse=True)
def disable_real_audio_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASR_PROVIDER", "")
    monkeypatch.setenv("PRON_PROVIDER", "")
    with ANALYSIS_JOB_LOCK:
        ANALYSIS_JOBS.clear()


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


def test_background_audio_analysis_job_reports_progress_and_result() -> None:
    response = client.post(
        "/api/lessons/demo/audio-ingest/jobs",
        data={
            "mode": "mock",
            "agent_mode": "mock",
            "input_source": "sample",
            "use_sample": "true",
            "sample_id": "standard",
            "lesson_metadata": '{"studentName":"Async Student","topic":"Async Demo"}',
        },
    )

    assert response.status_code == 202
    queued = response.json()
    assert queued["job_id"].startswith("job_")
    assert queued["lesson_id"].startswith("lesson_")
    assert queued["status"] in {"queued", "running"}

    job_id = queued["job_id"]
    deadline = time.monotonic() + 5
    job = queued
    while time.monotonic() < deadline and job["status"] not in {"completed", "failed"}:
        time.sleep(0.02)
        job_response = client.get(f"/api/analysis-jobs/{job_id}")
        assert job_response.status_code == 200
        job = job_response.json()

    assert job["status"] == "completed"
    assert job["progress"] == 100
    assert job["result"]["lesson_id"] == queued["lesson_id"]
    assert job["result"]["metadata"]["student_name"] == "Async Student"

    jobs_response = client.get("/api/analysis-jobs")
    assert jobs_response.status_code == 200
    listed = jobs_response.json()["jobs"]
    assert listed[0]["job_id"] == job_id
    assert "result" not in listed[0]
