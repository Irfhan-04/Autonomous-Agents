# FastAPI Autonomous Document Agent

A 60-minute-style FastAPI build that turns a natural-language document request into a `.docx` through a fixed autonomous pipeline:

```text
INTAKE & PLAN -> GENERATE -> REFLECT -> RENDER
```

The LLM stages use Groq strict JSON Schema structured outputs with a primary/fallback model pair — `openai/gpt-oss-120b` by default, falling back to `openai/gpt-oss-20b` if the primary model errors out or never returns valid JSON. Rendering is pure Python via `python-docx`; there is no database, no LangGraph/CrewAI, and no generated JSON schemas.

## Setup

```bash
uv sync
cp .env.example .env
# edit .env and set GROQ_API_KEY
uv run uvicorn agent.main:app --reload --port 8000
```

`.env.example`:

```env
GROQ_API_KEY=
GROQ_MODEL_PRIMARY=openai/gpt-oss-120b
GROQ_MODEL_FALLBACK=openai/gpt-oss-20b
```

## API

Two test inputs — one standard, one complex/ambiguous:

```bash
# Standard business request
curl -s -X POST http://localhost:8000/agent \
  -H "Content-Type: application/json" \
  -d '{"request": "Write a 3-section internal onboarding guide for new backend engineers joining the payments team: environment setup, codebase orientation, and first-week expectations."}' | jq .

# Complex / ambiguous request (dual audience, unspecified length — forces the
# planner to state assumptions instead of silently picking one)
curl -s -X POST http://localhost:8000/agent \
  -H "Content-Type: application/json" \
  -d '{"request": "We need something for the board about the new fraud-detection feature but also make it usable as an engineering handoff doc, not sure how long it should be"}' | jq .
```

Example response shape:

```json
{
  "request_id": "uuid",
  "doc_type": "internal onboarding guide",
  "title": "Backend Engineer Onboarding Guide",
  "assumptions": [],
  "reflection_summary": "The draft satisfies the request.",
  "issues_found": false,
  "download_url": "/agent/download/uuid"
}
```

Download the generated Word document:

```bash
curl -s -o out.docx http://localhost:8000/agent/download/<request_id>
```

## Pipeline

1. **INTAKE & PLAN**: Creates `doc_type`, `title`, planned sections, and assumptions.
2. **GENERATE**: Writes full section bodies for the planned sections.
3. **REFLECT**: Compares the draft against the original request, not against the plan.
4. **REPAIR**: If reflection flags sections, regenerates only those sections once.
5. **RENDER**: Writes `output/{request_id}.docx` with built-in Word styles.

## Engineering improvement: Reflection / self-check

**What was implemented.** After GENERATE, a REFLECT stage (`agent/reflector.py`) sends the drafted sections and the *original user request* — not the plan — to the LLM with strict-schema output, asking it to flag any section that omits something requested, contradicts the request, or is too thin to use. If anything is flagged, the flagged sections (and only those) go through one REPAIR pass in `generator.py` with the specific issue as a revision instruction, then get spliced back into the final document. Bounded to one repair pass — no loop.

**Why this one, over the other seven options** (conversation memory, RAG, tool calling, multi-step planning, error handling & recovery, request validation, retry/fallback logic): the agent's single biggest failure mode is an LLM silently dropping or misreading part of a multi-part request during GENERATE — worse on the ambiguous test case, where the planner already had to guess at scope. Reflection is the option that directly targets *output correctness* rather than infrastructure robustness, and it does so by re-grounding against the request instead of the plan, which catches a class of bug the other options don't touch: the plan itself being subtly wrong. It's also the cheapest to implement correctly within a 60-minute build — no new state, no new tool surface, no new external dependency — which mattered given the time box.

**How it improves the agent.** Without it, a bad GENERATE output ships as-is. With it, the pipeline gets one automated correctness pass, using the same structured-output machinery already in place, at the cost of at most one extra LLM round-trip per request.

## Debugging insight

**Issue:** on review, `agent/groq_client.py` was calling a single hardcoded-default model (`openai/gpt-oss-20b`) with no cross-model fallback — and its own docstring said so explicitly ("No paid-tier primary model and no cross-model fallback"). That's a real reliability gap: if that one model gets rate-limited or its ID is deprecated, every pipeline stage fails outright.

**Root cause:** the client had been built for a single-model constraint early on, and when the project's actual target became a primary (`openai/gpt-oss-120b`) + fallback (`openai/gpt-oss-20b`) setup, the client code and its docstring were never updated to match — the mismatch was documented rather than hidden, which is what made it catchable on review instead of surfacing later as a production incident.

**Fix:** refactored the per-model call into a shared `_call_model()` helper (attempt, retry once on the same model for malformed JSON, otherwise raise), then had `call_structured()` call it against the primary model first and fall back once to the secondary model on any failure — API error or exhausted retries. Verified with a mocked Groq client covering all four paths (immediate success, API-error fallback, malformed-JSON fallback, total failure) since there's no way to force a real rate-limit or model decommission on demand.

## Tradeoff discussion

**Fail-fast vs. retry-same-model, on API errors.** A rate limit or a decommissioned model ID won't resolve by calling the *same* model again within the same request — retrying wastes latency the user is waiting on. Malformed JSON is different: often a one-off decoding hiccup worth one same-model retry before falling back. This is a **speed vs. functionality** tradeoff: burn one extra round-trip only where there's a real chance it helps, not reflexively.

**120B primary despite being slower and more expensive than 20B.** Planning and reflection quality benefit from the larger model's reasoning — that's exactly where ambiguity gets caught and assumptions get made correctly, which matters most on the complex test case. 20B as fallback keeps the pipeline alive under a primary outage rather than hard-failing, at the cost of a quality dip on whichever call needed it. This is **accuracy vs. availability**: optimizing the common path for quality, the failure path for uptime.

## Notes

- `GROQ_API_KEY` is required; startup fails immediately if it is missing.
- `GROQ_MODEL_PRIMARY` defaults to `openai/gpt-oss-120b`, `GROQ_MODEL_FALLBACK` to `openai/gpt-oss-20b`.
- Retry & fallback logic: every stage's Groq call first retries the primary model once on the same model if it returns malformed/empty JSON; if the primary model errors out (rate limit, decommissioned model ID, transient 5xx) or exhausts that retry, `call_structured` falls back once to the secondary model with the same retry policy. Only if both models fail does the pipeline raise.
- Groq deprecated `llama-3.1-8b-instant` and `llama-3.3-70b-versatile` for free/developer-tier usage on 2026-06-17 in favor of the `gpt-oss` pair used here — see [console.groq.com/docs/deprecations](https://console.groq.com/docs/deprecations).
- Download paths validate `request_id` as a UUID before resolving `output/{uuid}.docx`.
- Runtime output lives in `output/`, which is gitignored.
