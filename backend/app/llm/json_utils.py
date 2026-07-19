from __future__ import annotations

import json
import re
from typing import Any


class JSONExtractionError(ValueError):
    pass


def _strip_markdown_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
        stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


def _extract_balanced_json(text: str) -> str:
    stripped = _strip_markdown_fence(text)
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped

    start = stripped.find("{")
    if start < 0:
        raise JSONExtractionError("No JSON object found in LLM output.")

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(stripped)):
        char = stripped[index]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return stripped[start : index + 1]

    raise JSONExtractionError("Unbalanced JSON object in LLM output.")


def parse_json_object(text: str) -> dict[str, Any]:
    payload = _extract_balanced_json(text)
    parsed = json.loads(payload)
    if not isinstance(parsed, dict):
        raise JSONExtractionError("LLM output JSON root must be an object.")
    return parsed


def repair_json_object(text: str) -> dict[str, Any]:
    payload = _extract_balanced_json(text)
    payload = re.sub(r",\s*([}\]])", r"\1", payload)
    parsed = json.loads(payload)
    if not isinstance(parsed, dict):
        raise JSONExtractionError("Repaired JSON root must be an object.")
    return parsed
