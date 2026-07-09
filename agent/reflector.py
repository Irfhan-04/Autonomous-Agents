"""REFLECT stage: check generated sections and retry flagged sections once."""

from __future__ import annotations

import json
import logging

from .generator import generate
from .groq_client import call_structured
from .json_schemas import REFLECTION_SCHEMA

logger = logging.getLogger("agent.reflector")

SYSTEM_PROMPT = (
    "You are a quality-check assistant. Compare the drafted document "
    "sections against the ORIGINAL user request — not against any plan or "
    "outline that produced them. Flag any section that omits something the "
    "user asked for, contradicts the request, or is too thin to be usable. "
    "If everything satisfies the request, return issues_found: false and an "
    "empty flagged_sections list."
)


def reflect_and_repair(
    user_request: str,
    document_plan: dict,
    outline_sections: list[dict],
    request_id: str,
) -> tuple[list[dict], dict]:
    """Return final sections plus the reflection report after one scoped repair."""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": json.dumps(
                {"original_request": user_request, "drafted_sections": outline_sections}
            ),
        },
    ]
    report = call_structured(messages, "reflection_report", REFLECTION_SCHEMA, request_id)

    if not report.get("issues_found") or not report.get("flagged_sections"):
        return outline_sections, report

    flagged_headings = {flagged["heading"] for flagged in report["flagged_sections"]}
    logger.info(
        "[%s] reflection flagged %d section(s): %s",
        request_id,
        len(flagged_headings),
        flagged_headings,
    )

    plan_by_heading = {section["heading"]: section for section in document_plan["sections"]}
    sections_to_redo = [
        plan_by_heading[heading]
        for heading in flagged_headings
        if heading in plan_by_heading
    ]
    if not sections_to_redo:
        return outline_sections, report

    issue_summary = "; ".join(flagged["issue"] for flagged in report["flagged_sections"])
    revised = generate(
        user_request,
        sections_to_redo,
        request_id,
        extra_instruction=issue_summary,
    )
    revised_by_heading = {section["heading"]: section for section in revised}

    final_sections = [
        revised_by_heading.get(section["heading"], section) for section in outline_sections
    ]
    return final_sections, report
