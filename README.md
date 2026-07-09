# FastAPI Autonomous Document Agent

A 60-minute-style FastAPI build that turns a natural-language document request into a `.docx` through a fixed autonomous pipeline:

```text
INTAKE & PLAN -> GENERATE -> REFLECT -> RENDER
```

The LLM stages use Groq strict JSON Schema structured outputs with a single configured model (`openai/gpt-oss-20b` by default). Rendering is pure Python via `python-docx`; there is no database, no LangGraph/CrewAI, and no generated JSON schemas.

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
GROQ_MODEL=openai/gpt-oss-20b
```

## API

Create a document:

```bash
curl -s -X POST http://localhost:8000/agent \
  -H "Content-Type: application/json" \
  -d '{"request": "Write a 3-section internal onboarding guide for new backend engineers joining the payments team: environment setup, codebase orientation, and first-week expectations."}' | jq .
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

## Notes

- `GROQ_API_KEY` is required; startup fails immediately if it is missing.
- `GROQ_MODEL` defaults to `openai/gpt-oss-20b`.
- The Groq client retries malformed/empty JSON once on the same model.
- Download paths validate `request_id` as a UUID before resolving `output/{uuid}.docx`.
- Runtime output lives in `output/`, which is gitignored.
