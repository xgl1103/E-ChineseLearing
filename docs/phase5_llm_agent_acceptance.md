# Phase 5 LLM Agent Acceptance

## Goal

Phase 5 upgrades only the Writer Agent and Reviewer Agent from deterministic mock logic to an optional real LLM path.

The stable mock demo must remain intact.

```text
mock lesson data
  -> evidence and confidence controls
  -> optional real Writer / Reviewer LLM
  -> JSON schema validation
  -> Rule Validator
  -> fallback to mock when unsafe
  -> teacher review gate
```

Phase 5 does not implement real ASR, real audio upload, real VAD, or real pronunciation assessment.

## Modes

| Mode | Expected Behavior | Acceptance Signal |
|---|---|---|
| `mock` | Use the existing deterministic pipeline. | `agent_mode` is `mock` or omitted for backward compatibility. |
| `real` | Try real LLM Writer and Reviewer. | `agent_mode` is `real_llm` when both real calls and validation pass. |
| `fallback` | If real LLM is disabled, unavailable, invalid, slow, or unsafe, return mock output. | `agent_mode` is `fallback` and `fallback_reason` is present. |

Fallback is a success path for demo stability. It should be visible, not hidden.

## Environment Variables

Recommended backend variables:

```bash
LLM_ENABLE_REAL=0
LLM_PROVIDER=openai
LLM_MODEL=gpt-4.1-mini
OPENAI_API_KEY=
LLM_TIMEOUT_SECONDS=30
LLM_MAX_RETRIES=1
```

Behavior:

- `LLM_ENABLE_REAL=0`: `mode=real` must not crash; it should fallback to mock.
- Missing `OPENAI_API_KEY`: `mode=real` must fallback with a clear reason.
- Provider timeout, JSON parse failure, schema validation failure, or blocked rule validation must fallback or route to manual review.

## Prompt Contract

`prompts/writer_prompt.md` must produce only `DraftReport` JSON:

- no Markdown
- no prose outside JSON
- no `final_reports`
- no `review_result`
- no `teacher_review`
- factual items need `source_evidence_ids` or `source_evidence_id`
- pronunciation feedback must reference `pronunciation_assessments`

`prompts/reviewer_prompt.md` must produce only `ReviewResult` JSON:

- `pass`
- `score`
- `issues`
- `revision_instruction`
- `revision_count`
- `rubric_scores`

If `rule_validation_result.pass=false`, Reviewer must return `pass=false`.

## API Acceptance Requests

Start backend:

```bash
py -3.13 -m compileall backend
py -3.13 -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Mock mode:

```http
POST /api/lessons/demo/analyze
Content-Type: application/json

{
  "mode": "mock",
  "include_pronunciation": true
}
```

Real mode with pronunciation:

```http
POST /api/lessons/demo/analyze
Content-Type: application/json

{
  "mode": "real",
  "include_pronunciation": true
}
```

Real mode without pronunciation:

```http
POST /api/lessons/demo/analyze
Content-Type: application/json

{
  "mode": "real",
  "include_pronunciation": false
}
```

Teacher review:

```http
POST /api/lessons/demo_001/teacher-review
Content-Type: application/json

{
  "confirmed_homework_ids": ["hw_001", "hw_002"],
  "confirmed_risk_ids": ["risk_001", "risk_002"],
  "teacher_notes": "Confirmed explicit homework. Candidate dialogue practice should remain optional.",
  "report_edits": {}
}
```

Finalize:

```http
POST /api/lessons/demo_001/finalize
Content-Type: application/json

{
  "audiences": ["teacher", "student", "parent"]
}
```

## Success Path Acceptance

For `mode=mock`:

- Returns existing phase 3 fields.
- Existing teacher-review and finalize flow still works.
- No new LLM fields are required for backward compatibility.

For `mode=real` with working model:

- Response includes `agent_mode`.
- Response includes `model_provider` and `model_name`.
- Response includes `llm_trace` or equivalent graph trace metadata.
- Writer output validates as `DraftReport`.
- Reviewer output validates as `ReviewResult`.
- Rule Validator still runs before final teacher review.
- Final reports are not sent until teacher review.

## Failure Path Acceptance

These failures must not break the demo:

- no API key
- `LLM_ENABLE_REAL != 1`
- provider timeout
- invalid JSON from model
- JSON repair failed
- schema validation failed
- Reviewer returns fail
- Rule Validator has blocking issues

Expected response behavior:

- `agent_mode` should be `fallback` when mock output is used.
- `fallback_reason` should explain why.
- `schema_validation` should show pass/fail when available.
- Teacher review and finalize should remain usable.

## JSON Schema Validation Standard

Writer output must validate against backend `DraftReport`.

Reviewer output must validate against backend `ReviewResult`.

Additional recommendations:

- Reject or repair Markdown-wrapped JSON.
- Reject unsupported top-level fields from Writer output.
- Treat missing evidence IDs as validation or rule failures.
- Treat pronunciation claims without `assessment_id` as rule failures.
- Treat low-confidence items without teacher confirmation as rule failures.

## Interview Demo Talk Track

Use this 30-45 second explanation:

```text
In phase 5, I would allow the Writer and Reviewer agents to call a real LLM, but only inside the existing control system. The real model can improve language quality and reasoning, but it cannot bypass evidence grounding, Rule Validator, schema validation, or the teacher review gate.

If the model returns invalid JSON, fails schema validation, times out, or the API key is missing, the system falls back to the stable mock pipeline. That means the demo and teacher workflow remain reliable while we gradually introduce real model capability.
```

Short version:

```text
The real LLM is replaceable. The trustworthy workflow is the product.
```

## Final Checklist

- Prompts output JSON only.
- Writer prompt maps to `DraftReport`.
- Reviewer prompt maps to `ReviewResult`.
- Real mode can fallback safely.
- Fallback is visible to frontend and interviewer.
- Rule Validator remains deterministic.
- Teacher review gate remains mandatory.
- Mock mode still works without API keys.
