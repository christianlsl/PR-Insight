"""Parse structured responses from AI models."""

from __future__ import annotations

import json
import re


def parse_json_response(text: str) -> dict:
    """Extract JSON from AI response text.

    Handles responses that may contain markdown code blocks or extra text
    around the JSON payload.
    """
    # Try direct parse first
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code block
    code_block = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if code_block:
        try:
            return json.loads(code_block.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Try finding first { ... } or [ ... ]
    for pattern in [r"\{.*\}", r"\[.*\]"]:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                continue

    # Fallback: wrap raw text in a dict
    return {"raw_text": text, "parse_error": "Could not extract structured JSON"}
