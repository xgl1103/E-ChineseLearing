from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import ValidationError

from backend.app.llm.client import LLMCallError, LLMClient
from backend.app.llm.config import LLMConfig
from backend.app.llm.json_utils import JSONExtractionError, parse_json_object, repair_json_object
from backend.app.schemas import DraftReport, Lesson, ReviewResult


AgentMode = Literal["mock", "real_llm", "fallback"]


PROMPT_DIR = Path(__file__).resolve().parents[3] / "prompts"


@dataclass
class AgentRunResult:
    agent_name: str
    mode: AgentMode
    provider: str
    model: str
    schema_validation: Literal["pass", "fail", "skipped"]
    json_repair_attempted: bool = False
    fallback_reason: str = ""
    latency_ms: int | None = None
    output: DraftReport | ReviewResult | None = None
    trace: dict[str, Any] = field(default_factory=dict)


def _read_prompt(filename: str) -> str:
    return (PROMPT_DIR / filename).read_text(encoding="utf-8")


def _parse_or_repair(raw_text: str) -> tuple[dict[str, Any], bool]:
    try:
        return parse_json_object(raw_text), False
    except (JSONExtractionError, ValueError):
        return repair_json_object(raw_text), True


def _base_trace(result: AgentRunResult) -> dict[str, Any]:
    return {
        "agent": result.agent_name,
        "agent_mode": result.mode,
        "model_provider": result.provider,
        "model_name": result.model,
        "schema_validation": result.schema_validation,
        "json_repair_attempted": result.json_repair_attempted,
        "fallback_reason": result.fallback_reason,
        "latency_ms": result.latency_ms,
    }


def _fallback_result(
    *,
    agent_name: str,
    config: LLMConfig,
    reason: str,
    repair_attempted: bool = False,
) -> AgentRunResult:
    result = AgentRunResult(
        agent_name=agent_name,
        mode="fallback",
        provider=config.provider,
        model=config.model,
        schema_validation="fail" if repair_attempted else "skipped",
        json_repair_attempted=repair_attempted,
        fallback_reason=reason,
    )
    result.trace = _base_trace(result)
    return result


def _mock_result(agent_name: str, config: LLMConfig) -> AgentRunResult:
    result = AgentRunResult(
        agent_name=agent_name,
        mode="mock",
        provider=config.provider,
        model=config.model,
        schema_validation="skipped",
    )
    result.trace = _base_trace(result)
    return result


def _writer_payload(lesson: Lesson, revision_instruction: str) -> dict[str, Any]:
    return {
        "lesson": {
            "metadata": lesson.metadata.model_dump(),
            "transcripts": lesson.transcripts.model_dump(),
            "practice_clips": [item.model_dump() for item in lesson.practice_clips],
            "pronunciation_assessments": [
                item.model_dump() for item in lesson.pronunciation_assessments
            ],
            "evidence": lesson.evidence.model_dump(),
            "confidence_scores": dict(lesson.confidence_scores),
            "risk_highlights": [item.model_dump() for item in lesson.risk_highlights],
        },
        "revision_instruction": revision_instruction,
        "output_schema": "backend.app.schemas.DraftReport",
    }


def run_writer_agent(
    lesson: Lesson,
    *,
    requested_mode: Literal["mock", "real"],
    config: LLMConfig,
    revision_instruction: str = "",
) -> AgentRunResult:
    if requested_mode == "mock":
        return _mock_result("writer_agent", config)

    try:
        response = LLMClient(config).complete_json(
            system_prompt=_read_prompt("writer_prompt.md"),
            payload=_writer_payload(lesson, revision_instruction),
        )
        parsed, repair_attempted = _parse_or_repair(response.text)
        draft_report = DraftReport.model_validate(parsed)
    except (LLMCallError, JSONExtractionError, ValueError, ValidationError) as error:
        return _fallback_result(
            agent_name="writer_agent",
            config=config,
            reason=str(error),
            repair_attempted=not isinstance(error, LLMCallError),
        )

    result = AgentRunResult(
        agent_name="writer_agent",
        mode="real_llm",
        provider=config.provider,
        model=config.model,
        schema_validation="pass",
        json_repair_attempted=repair_attempted,
        latency_ms=response.latency_ms,
        output=draft_report,
    )
    result.trace = _base_trace(result)
    return result


def run_reviewer_agent(
    lesson: Lesson,
    *,
    requested_mode: Literal["mock", "real"],
    config: LLMConfig,
    revision_count: int,
) -> AgentRunResult:
    if requested_mode == "mock":
        return _mock_result("reviewer_agent", config)

    try:
        response = LLMClient(config).complete_json(
            system_prompt=_read_prompt("reviewer_prompt.md"),
            payload={
                "draft_report": lesson.draft_report.model_dump(),
                "evidence": lesson.evidence.model_dump(),
                "pronunciation_assessments": [
                    item.model_dump() for item in lesson.pronunciation_assessments
                ],
                "confidence_scores": lesson.confidence_scores,
                "risk_highlights": [item.model_dump() for item in lesson.risk_highlights],
                "rule_validation_result": lesson.rule_validation_result.model_dump(by_alias=True),
                "revision_count": revision_count,
                "output_schema": "backend.app.schemas.ReviewResult",
            },
        )
        parsed, repair_attempted = _parse_or_repair(response.text)
        parsed.setdefault("revision_count", revision_count)
        review_result = ReviewResult.model_validate(parsed)
    except (LLMCallError, JSONExtractionError, ValueError, ValidationError) as error:
        return _fallback_result(
            agent_name="reviewer_agent",
            config=config,
            reason=str(error),
            repair_attempted=not isinstance(error, LLMCallError),
        )

    result = AgentRunResult(
        agent_name="reviewer_agent",
        mode="real_llm",
        provider=config.provider,
        model=config.model,
        schema_validation="pass",
        json_repair_attempted=repair_attempted,
        latency_ms=response.latency_ms,
        output=review_result,
    )
    result.trace = _base_trace(result)
    return result
