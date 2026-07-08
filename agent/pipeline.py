"""Deterministic pipeline: INTAKE & PLAN -> GENERATE -> REFLECT -> RENDER."""

from __future__ import annotations

import logging
from pathlib import Path

from .docx_builder import render_docx
from .generator import generate
from .planner import plan
from .reflector import reflect_and_repair

logger = logging.getLogger("agent.pipeline")

OUTPUT_DIR = Path("output")


def run_pipeline(user_request: str, request_id: str) -> dict:
    """Run the fixed autonomous document pipeline for one request."""

    logger.info("[%s] INTAKE & PLAN", request_id)
    document_plan = plan(user_request, request_id)

    logger.info("[%s] GENERATE", request_id)
    outline_sections = generate(user_request, document_plan["sections"], request_id)

    logger.info("[%s] REFLECT", request_id)
    final_sections, reflection_report = reflect_and_repair(
        user_request,
        document_plan,
        outline_sections,
        request_id,
    )

    logger.info("[%s] RENDER", request_id)
    output_path = OUTPUT_DIR / f"{request_id}.docx"
    render_docx(document_plan["title"], final_sections, output_path)

    return {
        "plan": document_plan,
        "reflection": reflection_report,
        "output_path": output_path,
    }
