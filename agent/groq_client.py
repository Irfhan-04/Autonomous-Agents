"""Groq SDK wrapper: strict response_format and defensive JSON parsing.

Single free-tier model only. No paid-tier primary model and no cross-model
fallback. Every pipeline stage calls call_structured(); no stage talks to the
Groq client directly.
"""

from __future__ import annotations

import json
import logging
import os

from dotenv import load_dotenv
from groq import APIError, Groq

load_dotenv()

logger = logging.getLogger("agent.groq_client")

MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")

_api_key = os.environ.get("GROQ_API_KEY")
if not _api_key:
    raise RuntimeError("GROQ_API_KEY is not set (check .env).")

_client = Groq(api_key=_api_key)


def response_format(name: str, schema: dict) -> dict:
    """Build a strict-mode json_schema response_format block."""

    return {
        "type": "json_schema",
        "json_schema": {"name": name, "strict": True, "schema": schema},
    }


def call_structured(
    messages: list[dict],
    schema_name: str,
    schema: dict,
    request_id: str,
    temperature: float = 0.3,
) -> dict:
    """Call Groq chat completions with one same-model retry for malformed JSON."""

    fmt = response_format(schema_name, schema)
    last_error: Exception | None = None

    for attempt in (1, 2):
        try:
            logger.info(
                "[%s] calling %s for %s (attempt %d)",
                request_id,
                MODEL,
                schema_name,
                attempt,
            )
            completion = _client.chat.completions.create(
                model=MODEL,
                messages=messages,
                temperature=temperature,
                response_format=fmt,
            )
            raw = completion.choices[0].message.content
            return json.loads(raw)
        except APIError as exc:
            logger.warning("[%s] %s API error: %s", request_id, MODEL, exc)
            last_error = exc
            break
        except (json.JSONDecodeError, TypeError, IndexError) as exc:
            logger.warning(
                "[%s] %s returned malformed JSON on attempt %d: %s",
                request_id,
                MODEL,
                attempt,
                exc,
            )
            last_error = exc

    raise RuntimeError(f"Groq structured call failed: {last_error}") from last_error
