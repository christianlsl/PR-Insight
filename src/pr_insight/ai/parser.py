"""Parse structured responses from AI models."""

from __future__ import annotations

import json
import re
from typing import Any


class ResponseParseError(Exception):
    """Raised when AI response cannot be parsed as structured JSON."""


EXPECTED_TOP_LEVEL_KEYS = {
    "purpose",
    "impact",
    "tech_details",
    "risk_areas",
    "risks",
    "suggestions",
    "issues",
}


def _looks_like_task_payload(value: Any) -> bool:
    """Return True when a decoded JSON value matches one of our task schemas."""
    if isinstance(value, dict):
        return bool(EXPECTED_TOP_LEVEL_KEYS.intersection(value))
    if isinstance(value, list):
        return bool(value) and all(isinstance(item, dict) for item in value)
    return False


def _iter_balanced_json_candidates(text: str) -> list[str]:
    """Find balanced JSON object/array substrings without regex greediness.

    AI responses often contain prose before the final payload. A simple
    ``{.*}`` regex can swallow too much text or stop at braces inside strings,
    so scan with basic JSON string/escape awareness instead.
    """
    candidates: list[str] = []
    pairs = {"{": "}", "[": "]"}

    for start, char in enumerate(text):
        if char not in pairs:
            continue

        stack = [pairs[char]]
        in_string = False
        escaped = False

        for pos in range(start + 1, len(text)):
            current = text[pos]

            if in_string:
                if escaped:
                    escaped = False
                elif current == "\\":
                    escaped = True
                elif current == '"':
                    in_string = False
                continue

            if current == '"':
                in_string = True
            elif current in pairs:
                stack.append(pairs[current])
            elif current in ("}", "]"):
                if not stack or current != stack[-1]:
                    break
                stack.pop()
                if not stack:
                    candidates.append(text[start:pos + 1])
                    break

    return candidates


def _decode_best_candidate(candidates: list[str]) -> Any | None:
    """Decode candidates, preferring payloads shaped like PR-Insight results."""
    decoded: list[Any] = []
    for candidate in candidates:
        try:
            value = json.loads(candidate.strip())
        except json.JSONDecodeError:
            continue
        if _looks_like_task_payload(value):
            return value
        decoded.append(value)

    return decoded[0] if decoded else None


def parse_json_response(text: str) -> Any:
    """Extract JSON from AI response text.

    Handles responses that may contain markdown code blocks or extra text
    around the JSON payload.

    Raises ResponseParseError if no valid JSON can be extracted.
    """
    # Try direct parse first
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code blocks. Some models emit variants like
    # ```JSON or ``` json, so accept optional whitespace and case differences.
    code_blocks = re.findall(r"```\s*(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL | re.IGNORECASE)
    best_from_blocks = _decode_best_candidate(code_blocks)
    if best_from_blocks is not None:
        return best_from_blocks

    # Try balanced JSON snippets in the full response. This handles prose such
    # as "分析如下... {final payload}" and ignores braces inside JSON strings.
    best_from_text = _decode_best_candidate(_iter_balanced_json_candidates(text))
    if best_from_text is not None:
        return best_from_text

    raise ResponseParseError(
        f"Could not extract structured JSON from response: {text[:200]}..."
    )
