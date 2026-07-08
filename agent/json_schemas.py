"""Strict-mode JSON schemas for the three LLM-authored pipeline stages.

Hand-written flat dicts: Groq strict mode requires additionalProperties: false
and every property listed in required at every nesting level. Do not generate
these from Pydantic models.
"""

PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "doc_type": {"type": "string"},
        "title": {"type": "string"},
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "heading": {"type": "string"},
                    "guidance": {"type": "string"},
                },
                "required": ["heading", "guidance"],
                "additionalProperties": False,
            },
        },
        "assumptions": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["doc_type", "title", "sections", "assumptions"],
    "additionalProperties": False,
}

OUTLINE_SCHEMA = {
    "type": "object",
    "properties": {
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "heading": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["heading", "body"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["sections"],
    "additionalProperties": False,
}

REFLECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "overall_assessment": {"type": "string"},
        "issues_found": {"type": "boolean"},
        "flagged_sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "heading": {"type": "string"},
                    "issue": {"type": "string"},
                },
                "required": ["heading", "issue"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["overall_assessment", "issues_found", "flagged_sections"],
    "additionalProperties": False,
}
