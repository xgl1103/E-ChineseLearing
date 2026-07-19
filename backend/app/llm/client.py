from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from backend.app.llm.config import LLMConfig


class LLMCallError(RuntimeError):
    pass


@dataclass
class LLMResponse:
    text: str
    latency_ms: int


class LLMClient:
    def __init__(self, config: LLMConfig) -> None:
        self.config = config

    def complete_json(self, *, system_prompt: str, payload: dict[str, Any]) -> LLMResponse:
        blocker = self.config.real_mode_blocker()
        if blocker:
            raise LLMCallError(blocker)
        if self.config.provider == "openai":
            return self._call_openai(system_prompt=system_prompt, payload=payload)
        if self.config.provider == "deepseek":
            return self._call_deepseek(system_prompt=system_prompt, payload=payload)
        raise LLMCallError(f"unsupported LLM_PROVIDER: {self.config.provider}")

    def _call_openai(self, *, system_prompt: str, payload: dict[str, Any]) -> LLMResponse:
        body = {
            "model": self.config.model,
            "input": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        "Return only valid JSON for the requested schema.\n\n"
                        + json.dumps(payload, ensure_ascii=False)
                    ),
                },
            ],
        }
        encoded = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=encoded,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
        )

        started = time.perf_counter()
        last_error: Exception | None = None
        for _ in range(max(1, self.config.max_retries + 1)):
            try:
                with urllib.request.urlopen(
                    request,
                    timeout=self.config.timeout_seconds,
                ) as response:
                    response_body = json.loads(response.read().decode("utf-8"))
                    return LLMResponse(
                        text=self._extract_response_text(response_body),
                        latency_ms=int((time.perf_counter() - started) * 1000),
                    )
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, LLMCallError) as error:
                last_error = error
        raise LLMCallError(str(last_error) if last_error else "OpenAI request failed")

    def _extract_response_text(self, response_body: dict[str, Any]) -> str:
        if isinstance(response_body.get("output_text"), str):
            return response_body["output_text"]

        fragments: list[str] = []
        for item in response_body.get("output", []):
            for content in item.get("content", []):
                if isinstance(content.get("text"), str):
                    fragments.append(content["text"])
        if fragments:
            return "\n".join(fragments)
        raise LLMCallError("OpenAI response did not contain output text")

    def _call_deepseek(self, *, system_prompt: str, payload: dict[str, Any]) -> LLMResponse:
        body = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        "Return only valid JSON for the requested schema.\n\n"
                        + json.dumps(payload, ensure_ascii=False)
                    ),
                },
            ],
            "stream": False,
            "response_format": {"type": "json_object"},
        }
        encoded = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            "https://api.deepseek.com/chat/completions",
            data=encoded,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
        )

        started = time.perf_counter()
        last_error: Exception | None = None
        for _ in range(max(1, self.config.max_retries + 1)):
            try:
                with urllib.request.urlopen(
                    request,
                    timeout=self.config.timeout_seconds,
                ) as response:
                    response_body = json.loads(response.read().decode("utf-8"))
                    return LLMResponse(
                        text=self._extract_chat_completion_text(response_body),
                        latency_ms=int((time.perf_counter() - started) * 1000),
                    )
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, LLMCallError) as error:
                last_error = error
        raise LLMCallError(str(last_error) if last_error else "DeepSeek request failed")

    def _extract_chat_completion_text(self, response_body: dict[str, Any]) -> str:
        choices = response_body.get("choices", [])
        if not choices:
            raise LLMCallError("Chat completion response did not contain choices")
        message = choices[0].get("message", {})
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content
        raise LLMCallError("Chat completion response did not contain message content")
