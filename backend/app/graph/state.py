from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from backend.app.llm.config import LLMConfig
from backend.app.schemas import Lesson


GraphStatus = Literal["passed", "warning", "failed", "pending"]
GraphRoute = Literal[
    "continue",
    "writer_revision",
    "teacher_review_gate",
    "final_report",
    "manual_review",
    "end",
]


@dataclass
class GraphEvent:
    node: str
    route: GraphRoute
    revision_count: int
    status: GraphStatus
    summary: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def model_dump(self) -> dict[str, Any]:
        return {
            "node": self.node,
            "route": self.route,
            "revision_count": self.revision_count,
            "status": self.status,
            "summary": self.summary,
            "metadata": self.metadata,
        }


@dataclass
class GraphState:
    lesson: Lesson
    include_pronunciation: bool = True
    requested_agent_mode: Literal["mock", "real"] = "mock"
    llm_config: LLMConfig = field(default_factory=LLMConfig.from_env)
    revision_count: int = 0
    max_revisions: int = 2
    route: GraphRoute = "continue"
    revision_instruction: str = ""
    stopped_reason: str = ""
    agent_mode: Literal["mock", "real_llm", "fallback"] = "mock"
    fallback_reason: str = ""
    schema_validation: dict[str, str] = field(default_factory=dict)
    llm_trace: list[dict[str, Any]] = field(default_factory=list)
    history: list[GraphEvent] = field(default_factory=list)

    def add_event(
        self,
        node: str,
        summary: str,
        *,
        route: GraphRoute | None = None,
        status: GraphStatus = "passed",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if route is not None:
            self.route = route
        self.history.append(
            GraphEvent(
                node=node,
                route=self.route,
                revision_count=self.revision_count,
                status=status,
                summary=summary,
                metadata=metadata or {},
            )
        )

    def trace(self) -> list[dict[str, Any]]:
        return [event.model_dump() for event in self.history]

    def revision_history(self) -> list[dict[str, Any]]:
        return [
            event.model_dump()
            for event in self.history
            if (
                event.route == "writer_revision"
                or event.revision_count > 0
                or (
                    event.node == "writer_agent"
                    and event.metadata.get("revision_instruction")
                )
            )
        ]

    def workflow_summary(self) -> dict[str, Any]:
        return {
            "workflow_trace": self.trace(),
            "graph_trace": self.trace(),
            "revision_count": self.revision_count,
            "revision_history": self.revision_history(),
            "stop_reason": self.stopped_reason,
            "agent_mode": self.agent_mode,
            "model_provider": self.llm_config.provider,
            "model_name": self.llm_config.model,
            "llm_trace": self.llm_trace,
            "schema_validation": dict(self.schema_validation),
            "fallback_reason": self.fallback_reason,
        }

    def record_llm_trace(self, trace: dict[str, Any]) -> None:
        self.llm_trace.append(trace)
        agent_mode = trace.get("agent_mode")
        agent = str(trace.get("agent", "unknown_agent"))
        if agent_mode == "real_llm" and self.agent_mode != "fallback":
            self.agent_mode = "real_llm"
        elif agent_mode == "fallback":
            self.agent_mode = "fallback"
            reason = str(trace.get("fallback_reason") or "")
            if reason and not self.fallback_reason:
                self.fallback_reason = reason
        self.schema_validation[agent] = str(trace.get("schema_validation", "skipped"))
