# Demo Script: AI Lesson Recorder

## Goal

Use this script for a 2-3 minute interview demo.

Core message:

> This is not ASR + GPT summarization. It is an evidence + confidence + review + teacher confirmation AI workflow.

## Setup

Open the teacher review workspace and load `data/demo_lesson.json`.

Demo lesson:

- Student: Alex Chen
- Level: YCT 3
- Topic: 餐厅点餐
- Key sentence: 我想要...
- Key correction: 我想要一个果汁 -> 我想要一杯果汁

## 2-3 Minute Walkthrough

### 1. Open The Teacher Review Workspace

Say:

```text
I would start from the teacher review workspace, because the product is designed as a teacher copilot, not an auto-send report generator. The AI can draft, but the teacher owns the final judgment.
```

Point out:

- lesson metadata
- pending teacher review status
- draft reports are not marked as final

### 2. Show Dual-Track Transcript

Say:

```text
The classroom is captured as dual-track audio. The teacher track is used for explanation, questions, corrections, and homework. The student track is used for answers, student questions, and pronunciation practice clips.
```

Show these transcript moments:

- Teacher explanation: `Please repeat after me: 我想要一杯果汁。`
- Student correct repeat: `我想要一杯果汁。`
- Student mistake: `我想要一个果汁。`
- Teacher correction: `一杯果汁, not 一个果汁`
- Student question: `为什么用“杯”？`
- Homework instruction: `record yourself reading 我想要一杯果汁和一份面条 five times`

### 3. Show Evidence Timestamp

Say:

```text
Before the LLM writes anything, we extract evidence with timestamps. The goal is that every important classroom conclusion can point back to where it happened.
```

Show:

- `ev_cr_001` for the correction
- `ev_sq_001` for the student question
- `ev_hw_001` and `ev_hw_002` for teacher-assigned homework

### 4. Show Correction Evidence

Say:

```text
Here the student says “我想要一个果汁”, and the teacher corrects it to “一杯果汁”. The report can state this because it has both the student segment and the teacher correction as evidence.
```

Product point:

```text
No evidence, no confirmed conclusion.
```

### 5. Show Pronunciation Assessment Boundary

Say:

```text
ASR tells us what the student said. It does not prove whether the pronunciation is standard. For pronunciation, the Writer Agent can only use pronunciation_assessments.
```

Show:

- `pa_001`: low-score word `果汁`
- `pa_003`: low-score word `面条`
- `pa_004`: `low_score_words` is empty
- `pa_002`: reference mismatch, because the student said `一个果汁` while the target was `一杯果汁`

Say:

```text
The important boundary is pa_002. The system should not call this a pronunciation mistake. It is mainly a measure-word correction case. This is why the risk highlight asks the teacher to review the reference instead of sending it as a confirmed pronunciation issue.
```

### 6. Show Risk Highlights

Say:

```text
Medium and low confidence content is not hidden inside the report. It is surfaced as risk highlights so the teacher can review the high-risk points first.
```

Show:

- `risk_001`: pronunciation needs teacher confirmation
- `risk_002`: system-generated candidate homework
- `risk_003`: AI student assessment needs confirmation
- `risk_004`: pronunciation boundary risk for reference mismatch

### 7. Teacher Confirms Homework And Risk

Say:

```text
The teacher can confirm the two explicit homework items from the lesson, and separately decide whether to keep the system-generated candidate homework. This prevents the AI from inventing homework and presenting it as if the teacher assigned it.
```

Show:

- `hw_001`: recording homework from teacher evidence
- `hw_002`: vocabulary review from teacher evidence
- `hw_003`: candidate dialogue practice, `teacher_confirmation_required: true`

### 8. Show Final Reports

Say:

```text
After teacher confirmation, the system can generate three versions. The teacher version keeps evidence and review notes. The student version focuses on what to practice. The parent version is positive, clear, and actionable.
```

Show:

- teacher report: classroom focus, correction, pronunciation points, next lesson suggestions
- student report: today learned, review focus, homework
- parent report: progress, practice focus, teacher confirmation note

All final reports use the same section shape:

```json
{
  "heading": "练习重点",
  "content": ["继续练习“一杯果汁”和“一份面条”。"]
}
```

### 9. Explain Real LLM Agent Mode

Say:

```text
In phase 5, Writer Agent and Reviewer Agent can call a real LLM, but the model is not allowed to own the workflow. The LLM output must be JSON, must match the backend schema, must pass Rule Validator, and still goes through teacher confirmation before anything reaches students or parents.
```

Then say:

```text
If the LLM is unavailable, returns invalid JSON, fails schema validation, or times out, the system falls back to the stable mock pipeline. So the product remains demoable and the teacher workflow still works even without an API key.
```

## Closing Line

Say:

```text
The core value is not saving a transcript, and it is not blindly trusting a model. It is turning a one-to-one class into a traceable feedback workflow: evidence first, confidence-aware reporting, schema-checked agents, automated review, and teacher confirmation before students or parents see the final report.
```

## Likely Interview Questions

### Why not just use ASR plus GPT?

```text
ASR plus GPT can produce a plausible summary, but education feedback needs stronger controls. Homework, correction, and pronunciation feedback should be evidence-linked, confidence-aware, reviewed, and teacher-confirmed.
```

### How do you avoid hallucination?

```text
The Writer Agent cannot write confirmed facts without evidence. Rule Validator blocks unsupported claims, unsupported pronunciation feedback, and low-confidence content that is not surfaced to the teacher.
```

### How do you evaluate pronunciation?

```text
Pronunciation is separate from ASR. ASR answers what the student said. Pronunciation Assessment evaluates a student audio clip against a reference text. If reference text is low-confidence or mismatched, the system must ask the teacher to confirm instead of making a strong claim.
```

### Why human-in-the-loop?

```text
The final report affects student practice and parent communication. AI can draft and flag risks, but the teacher remains responsible for final confirmation.
```

### What changes when real LLM is enabled?

```text
Only the Writer and Reviewer agents become model-backed. Evidence extraction, confidence handling, Rule Validator, schema validation, fallback, and teacher review remain control points around the model.
```

### What if the model fails?

```text
The system returns fallback output from the mock pipeline and exposes the fallback reason. That protects the demo and, more importantly, protects the teacher workflow.
```
