"""GENERATE stage: author body content for planned sections."""

from __future__ import annotations

import json

from .groq_client import call_structured
from .json_schemas import OUTLINE_SCHEMA

SYSTEM_PROMPT = (
    "You are a document-writing assistant. You are given the original user "
    "request and a section plan (heading + guidance). Write the full body "
    "text for each listed section. Match the tone and level of detail "
    "implied by the original request. Return exactly one entry per section "
    "you were asked to write, in the same order. If a revision_instruction "
    "is present, it describes a specific problem with a previous draft — "
    "fix that problem."
)


def generate(
    user_request: str,
    sections_to_write: list[dict],
    request_id: str,
    extra_instruction: str | None = None,
) -> list[dict]:
    """Generate heading/body pairs for the requested section subset."""

    user_content: dict[str, object] = {
        "original_request": user_request,
        "sections": sections_to_write,
    }
    if extra_instruction:
        user_content["revision_instruction"] = extra_instruction

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(user_content)},
    ]
    result = call_structured(messages, "document_outline", OUTLINE_SCHEMA, request_id)
    return result["sections"]
