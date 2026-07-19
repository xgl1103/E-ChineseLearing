# Rule Validator Specification

## Purpose

The Rule Validator runs before the LLM Reviewer Agent. It checks hard constraints that should not depend on subjective LLM judgment.

Input:

- `draft_report`
- `evidence`
- `pronunciation_assessments`
- `confidence_scores`
- `risk_highlights`
- `revision_count`

Output:

```json
{
  "pass": true,
  "blocking_issues": [],
  "warnings": []
}
```

## Hard Rules

### RV-001: Evidence Required For Factual Claims

Any factual item in these fields must include a valid `source_evidence_id`:

- `knowledge_points`
- `teacher_questions`
- `student_questions`
- `corrections`
- `homework_items`
- `next_lesson_suggestions`

Blocking issue if:

- `source_evidence_id` is missing
- referenced evidence id does not exist

### RV-002: Pronunciation Feedback Requires Assessment

Every item in `pronunciation_feedback` must include:

- `assessment_id`
- valid related `pronunciation_assessment`
- `teacher_confirmation_required`

Blocking issue if:

- pronunciation feedback exists without assessment
- assessment id is invalid
- feedback claims tone-level error without tone-level evidence

Warning if:

- assessment model confidence is `medium` or `low`
- reference confidence is not `high`
- `low_score_words` is empty and the report still tries to create a word-level pronunciation issue
- reference text appears to mismatch the student transcript; route this as a boundary warning unless the report states it as fact

### RV-003: ASR Text Cannot Prove Pronunciation

Blocking issue if pronunciation feedback uses phrases equivalent to:

- “ASR 识别正确，所以发音正确”
- “学生发音标准” without assessment support
- specific tone error without tone-level evidence
- “学生发音错误” when the only evidence is a grammar or vocabulary mismatch in ASR text

### RV-004: Homework Must Be Evidence-Backed Or Candidate

Each homework item must have:

- `source_evidence_id`
- `confidence`
- `teacher_confirmed`

Blocking issue if:

- no source evidence and no candidate flag
- candidate homework is sent as confirmed homework
- candidate homework lacks `teacher_confirmation_required: true`

Warning if:

- confidence is `medium` and item is not in `risk_highlights`
- candidate homework is not clearly worded as system-generated or teacher-pending

### RV-005: Low Confidence Must Be Highlighted

Any medium or low confidence content in these modules must appear in `risk_highlights`:

- pronunciation
- homework
- student assessment
- student question extraction

Blocking issue if:

- confidence is `low` and no risk highlight exists
- low-confidence content appears in student or parent final report as a confirmed conclusion

Warning if:

- confidence is `medium` and no risk highlight exists
- medium-confidence content is included without a teacher confirmation note

### RV-006: Teacher Confirmation Required

Reports cannot be marked final unless:

- `teacher_review.status = confirmed`
- all required risk items are confirmed or edited
- homework items intended for students are teacher-confirmed

Blocking issue if final reports are marked sent or confirmed before teacher review.

### RV-007: Revision Loop Limit

Blocking issue if:

- `revision_count > 2`

Action:

- stop Writer-Reviewer loop
- route to teacher/manual review

### RV-008: Parent Report Safety

Blocking issue if parent-facing content includes:

- harsh labels
- absolute AI scores as final judgment
- unconfirmed pronunciation claims
- internal model confidence details

Warning if parent-facing content is too technical.

## Warning Examples

```json
{
  "rule_id": "RV-002",
  "severity": "warning",
  "message": "Pronunciation feedback for “果汁” has medium model confidence and should be confirmed by the teacher.",
  "related_ids": ["pa_001"]
}
```

## Blocking Issue Examples

```json
{
  "rule_id": "RV-003",
  "severity": "blocking",
  "message": "The report claims a specific tone error, but no tone-level evidence exists in pronunciation_assessments.",
  "related_ids": ["pf_001"]
}
```

## Final Routing

If blocking issues exist:

```json
{
  "pass": false,
  "route": "writer_revision"
}
```

If only warnings exist:

```json
{
  "pass": true,
  "route": "reviewer_agent"
}
```

If no issues exist:

```json
{
  "pass": true,
  "route": "reviewer_agent"
}
```

## Final Instruction

Return only the structured rule validation JSON object. Do not include Markdown, comments, code fences, or explanatory prose outside JSON.

Minimum output shape:

```json
{
  "pass": true,
  "blocking_issues": [],
  "warnings": []
}
```
