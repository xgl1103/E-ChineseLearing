# Backend Mock API

## Start

```powershell
cd F:\code\e-chineselearing
py -3.13 -m pip install -r backend\requirements.txt
py -3.13 -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

If your default `python` already points to a compatible Python 3.11+ environment,
the same commands can be run with `python -m ...`.

Swagger UI:

```text
http://127.0.0.1:8000/docs
```

## Demo Data Validation

`data/demo_lesson.json` is validated against `backend.app.schemas.Lesson` at load
time. In development, validation errors return a clear `500` response with the
source file and error summary.

Fallback demo data is disabled by default. To debug the API with in-memory mock
data after a validation failure, opt in explicitly:

```powershell
$env:ALLOW_DEMO_FALLBACK="1"
py -3.13 -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Fallback responses include `data_source: fallback` and a validation error
summary when fallback was caused by invalid demo data.

## Phase 3 Graph Runner

The phase 3 workflow is implemented locally under `backend/app/graph/` and does
not require the external `langgraph` package.

The analyze path runs:

```text
transcript_processor -> evidence_extractor -> writer_agent
  -> confidence_scorer -> rule_validator -> reviewer_agent
  -> conditional_edge -> teacher_review_gate
```

If validation or review fails, the conditional edge routes back to
`writer_agent` until the revision count reaches 2. API responses include
`graph_trace` so the node order, route, and revision count are visible during
demo and debugging.

## Phase 4 Audio Ingest Demo

`POST /api/lessons/demo/audio-ingest` accepts multipart form data and maps the
audio input to the lesson transcript, evidence, lesson report, and pronunciation
assessment pipeline.

Supported form fields:

- `teacher_audio`: optional teacher audio file.
- `student_audio`: optional student audio file.
- `use_sample`: optional boolean. When `true`, or when both audio files are
  omitted, the API uses built-in demo sample tracks.
- `sample_id`: optional `standard` or `extended`. `extended` returns the longer
  demo lesson with 32 transcript segments and 7 pronunciation assessments.
- `input_source`: optional `sample`, `upload`, or `record`.
- `lesson_metadata`: optional JSON string with new lesson form fields.
- `mode`: currently only `mock` is supported.
- `agent_mode`: optional `mock` or `real`. `real` runs the configured LLM
  Writer/Reviewer agents after audio ingest; if the LLM is unavailable the
  response falls back with trace metadata.
- `include_pronunciation`: whether to include mock pronunciation assessments.

Without provider keys this path proves the product workflow through deterministic
mock processing: dual-track input -> LessonObject -> Writer/Reviewer workflow
-> teacher review. With provider keys it attempts real ASR and pronunciation
assessment while preserving mock fallback.

Recorded or uploaded audio is saved under `.uploads/lessons/{lesson_id}/` before
processing. If `ASR_PROVIDER=bailian` and `BAILIAN_API_KEY` are configured, the
backend attempts real Alibaba Cloud Model Studio/Bailian Fun-ASR transcription
for teacher and student tracks. `ASR_PROVIDER=deepgram` remains available as an
alternative provider.
If Azure pronunciation assessment is configured, the backend uses `ffmpeg` to
cut student Chinese practice clips into 16 kHz mono WAV files before sending only
those short clips to Azure. If real ASR, `ffmpeg`, or pronunciation assessment is
unavailable, the endpoint falls back to the deterministic mock path and reports
the reason in `audio_ingest`. The backend first looks for system `ffmpeg`; if it
is not on `PATH`, it falls back to the bundled executable provided by
`imageio-ffmpeg`.

Optional real audio environment variables:

```powershell
$env:ASR_PROVIDER="bailian"
$env:BAILIAN_API_KEY="..."
$env:BAILIAN_ASR_MODEL="fun-asr-flash-2026-06-15"

# Optional. Without this, the backend uses the DashScope-compatible endpoint.
$env:BAILIAN_WORKSPACE_ID="..."
$env:BAILIAN_ASR_BASE_URL="https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"

# Alternative ASR provider:
$env:ASR_PROVIDER="deepgram"
$env:DEEPGRAM_API_KEY="..."
$env:DEEPGRAM_MODEL="nova-3"

$env:PRON_PROVIDER="azure"
$env:AZURE_SPEECH_KEY="..."
$env:AZURE_SPEECH_REGION="eastasia"
$env:AZURE_PRON_LANGUAGE="zh-CN"
```

## Phase 5 LLM Agent Mode

`POST /api/lessons/demo/analyze` supports:

- `mode: "mock"`: force deterministic local writer/reviewer.
- `mode: "real"`: try the configured LLM provider for Writer and Reviewer, then
  fallback to deterministic mock on missing key, timeout, JSON parse failure, or
  schema validation failure.

Real LLM mode is opt-in:

```powershell
$env:LLM_ENABLE_REAL="1"
$env:LLM_PROVIDER="openai"
$env:OPENAI_API_KEY="..."
$env:LLM_MODEL="gpt-4.1-mini"
$env:LLM_TIMEOUT_SECONDS="20"
$env:LLM_MAX_RETRIES="1"
py -3.13 -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

DeepSeek can also be used through the OpenAI-compatible Chat Completions path:

```powershell
$env:LLM_ENABLE_REAL="1"
$env:LLM_PROVIDER="deepseek"
$env:DEEPSEEK_API_KEY="..."
$env:LLM_MODEL="deepseek-v4-flash"
py -3.13 -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

The backend also loads `backend/.env` and `.env` automatically for local demo
configuration. Environment variables already set in the shell take precedence.

No API key is required for the demo. If real mode is unavailable, analyze still
returns `200` with `agent_mode: fallback`, `fallback_reason`, `llm_trace`, and
schema validation metadata.

## Tests

```powershell
py -3.13 -m pytest backend\tests
```

The recording pipeline contract tests cover Deepgram response normalization,
student Chinese practice clip extraction, Azure-compatible WAV slicing, Azure
SDK import, and mock pronunciation fallback.

## Endpoints

- `GET /api/lessons/demo`
- `POST /api/lessons/demo/audio-ingest`
- `POST /api/lessons/demo/analyze`
- `POST /api/lessons/{lesson_id}/teacher-review`
- `POST /api/lessons/{lesson_id}/finalize`
