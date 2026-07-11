"""Groq SDK wrapper: strict response_format, primary/fallback models, and
defensive JSON parsing.

Two-model resilience ladder. Every pipeline stage calls call_structured();
no stage talks to the Groq client directly.

  1. GROQ_MODEL_PRIMARY (default openai/gpt-oss-120b) — up to 2 attempts,
     retrying once on the same model if it returns malformed/empty JSON.
  2. If the primary model raises an APIError (rate limit, decommissioned
     model, transient 5xx) or exhausts its malformed-JSON retry, fall back
     once to GROQ_MODEL_FALLBACK (default openai/gpt-oss-20b) with the same
     2-attempt policy.
  3. If both models fail, raise RuntimeError.

As of 2026-06-17 Groq deprecated llama-3.1-8b-instant and
llama-3.3-70b-versatile for free/developer-tier usage, recommending
openai/gpt-oss-20b and openai/gpt-oss-120b as replacements
(https://console.groq.com/docs/deprecations) — do not reintroduce the
llama-3.x model IDs here.
"""

from __future__ import annotations

import json
import logging
import os

from dotenv import load_dotenv
from groq import APIError, Groq

load_dotenv()

logger = logging.getLogger("agent.groq_client")

PRIMARY_MODEL = os.environ.get("GROQ_MODEL_PRIMARY", "openai/gpt-oss-120b")
FALLBACK_MODEL = os.environ.get("GROQ_MODEL_FALLBACK", "openai/gpt-oss-20b")

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


def _call_model(
    model: str,
    messages: list[dict],
    fmt: dict,
    schema_name: str,
    request_id: str,
    temperature: float,
    max_attempts: int = 2,
) -> dict:
    """Call a single model, retrying on the same model for malformed JSON.

    APIError is not retried here — it's re-raised immediately so the caller
    can decide whether to fall back to a different model. Returns the parsed
    dict on success; raises the last exception if every attempt fails.
    """

    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        logger.info(
            "[%s] calling %s for %s (attempt %d/%d)",
            request_id,
            model,
            schema_name,
            attempt,
            max_attempts,
        )
        try:
            completion = _client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                response_format=fmt,
            )
            raw = completion.choices[0].message.content
            return json.loads(raw)
        except APIError as exc:
            logger.warning("[%s] %s API error: %s", request_id, model, exc)
            raise
        except (json.JSONDecodeError, TypeError, IndexError) as exc:
            logger.warning(
                "[%s] %s returned malformed JSON on attempt %d: %s",
                request_id,
                model,
                attempt,
                exc,
            )
            last_error = exc

    raise RuntimeError(f"{model} exhausted retries: {last_error}") from last_error


def call_structured(
    messages: list[dict],
    schema_name: str,
    schema: dict,
    request_id: str,
    temperature: float = 0.3,
) -> dict:
    """Call Groq with the primary model, falling back once to the secondary
    model if the primary is unavailable or never returns valid JSON."""

    fmt = response_format(schema_name, schema)

    try:
        return _call_model(
            PRIMARY_MODEL, messages, fmt, schema_name, request_id, temperature
        )
    except Exception as primary_error:
        logger.warning(
            "[%s] primary model %s failed (%s); falling back to %s",
            request_id,
            PRIMARY_MODEL,
            primary_error,
            FALLBACK_MODEL,
        )

    try:
        return _call_model(
            FALLBACK_MODEL, messages, fmt, schema_name, request_id, temperature
        )
    except Exception as fallback_error:
        raise RuntimeError(
            f"Groq structured call failed on both {PRIMARY_MODEL} and "
            f"{FALLBACK_MODEL}: {fallback_error}"
        ) from fallback_error
