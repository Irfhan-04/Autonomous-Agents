"""FastAPI entrypoint for the autonomous document agent."""

from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .pipeline import OUTPUT_DIR, run_pipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent.main")

app = FastAPI(title="Autonomous Document Agent")


class AgentRequest(BaseModel):
    request: str


class AgentResponse(BaseModel):
    request_id: str
    doc_type: str
    title: str
    assumptions: list[str]
    reflection_summary: str
    issues_found: bool
    download_url: str


@app.post("/agent", response_model=AgentResponse)
def run_agent(payload: AgentRequest) -> AgentResponse:
    request_id = str(uuid.uuid4())
    logger.info("[%s] received request", request_id)
    try:
        result = run_pipeline(payload.request, request_id)
    except Exception:
        logger.exception("[%s] pipeline failed", request_id)
        raise HTTPException(status_code=500, detail="Agent pipeline failed.")

    plan = result["plan"]
    reflection = result["reflection"]
    return AgentResponse(
        request_id=request_id,
        doc_type=plan["doc_type"],
        title=plan["title"],
        assumptions=plan["assumptions"],
        reflection_summary=reflection["overall_assessment"],
        issues_found=reflection["issues_found"],
        download_url=f"/agent/download/{request_id}",
    )


@app.get("/agent/download/{request_id}")
def download(request_id: str) -> FileResponse:
    try:
        uuid.UUID(request_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="File not found.")

    path = OUTPUT_DIR / f"{request_id}.docx"
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found.")

    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=path.name,
    )
