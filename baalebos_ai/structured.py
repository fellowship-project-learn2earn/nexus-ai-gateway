"""
Structured (JSON) output helper.

The gateway's contract is one prompt string in, raw text out: there is no
system-prompt field, and no guarantee that whichever of the fallback
providers answers will obey "return only JSON". So this module (1) folds
your instructions into the prompt text and (2) extracts a JSON object
leniently from whatever comes back -- bare, fenced, surrounded by chatter,
or sitting next to unrelated {braces}.
"""
from __future__ import annotations

import json
import re
from typing import List, Optional

from .exceptions import BaalebosStructuredOutputError

__all__ = ["BaalebosStructuredOutputError", "build_structured_prompt", "extract_json", "parse_structured_response"]


def build_structured_prompt(system_instructions: str, user_content: str) -> str:
    return (
        f"{system_instructions.strip()}\n\n"
        f"{user_content.strip()}\n\n"
        "Respond with ONLY the JSON object described above. No markdown fences, "
        "no commentary before or after it."
    )


def _balanced_candidates(text: str) -> List[str]:
    """Every balanced {...} substring, in order of appearance. Braces inside
    quoted strings (and escaped quotes) don't affect the count."""
    candidates = []
    n = len(text)
    i = 0
    while i < n:
        if text[i] != "{":
            i += 1
            continue
        depth = 0
        in_string = False
        escaped = False
        for j in range(i, n):
            ch = text[j]
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = not in_string
            elif not in_string:
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        candidates.append(text[i : j + 1])
                        break
        i += 1
    return candidates


def extract_json(raw_text: str) -> dict:
    """Extract the first JSON *object* found in raw_text, or raise BaalebosStructuredOutputError."""
    if not raw_text or not raw_text.strip():
        raise BaalebosStructuredOutputError("The response was empty; there is nothing to parse.")

    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_text.strip(), flags=re.MULTILINE)

    try:
        value = json.loads(cleaned)
        if isinstance(value, dict):
            return value
    except ValueError:
        pass

    for candidate in _balanced_candidates(cleaned):
        try:
            value = json.loads(candidate)
        except ValueError:
            continue
        if isinstance(value, dict):
            return value

    raise BaalebosStructuredOutputError(
        f"Could not find a JSON object in the response. It began: {raw_text[:200]!r}"
    )


def parse_structured_response(raw_text: str, required_keys: Optional[List[str]] = None) -> dict:
    """extract_json plus optional validation that required_keys are all present."""
    parsed = extract_json(raw_text)
    if required_keys:
        missing = [k for k in required_keys if k not in parsed]
        if missing:
            raise BaalebosStructuredOutputError(
                f"The response is missing required fields {missing}; it has {sorted(parsed)}."
            )
    return parsed
