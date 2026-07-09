"""INTAKE & PLAN stage: turn the raw request into a structured document plan."""

from __future__ import annotations

from .groq_client import call_structured
from .json_schemas import PLAN_SCHEMA

SYSTEM_PROMPT = (
    "You are a planning assistant for a document-generation agent. Given a "
    "user's request for a document, produce: the document type, a title, an "
    "ordered list of sections (heading + one-sentence guidance on what each "
    "section should cover), and a list of assumptions you had to make "
    "because the request was ambiguous, incomplete, or self-contradictory. "
    "If the request is fully unambiguous, return an empty assumptions list. "
    "Do not write the document content itself — only plan its structure."
)


def plan(user_request: str, request_id: str) -> dict:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_request},
    ]
    return call_structured(messages, "document_plan", PLAN_SCHEMA, request_id)
