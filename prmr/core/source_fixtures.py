"""Deterministic internal fixtures for Source Ledger V1."""

from __future__ import annotations

from typing import Any

from .source_models import SourceInput


PLAIN_STORY = """Mara opened the observatory before sunrise.
The instruments were still calibrated from the previous night.

At noon, Ivo said, \"The northern sensor has changed direction.\"
Mara recorded the change but made no claim about its cause.

The team decided to repeat the measurement. A blocked access road delayed them.

Three days later, the replacement measurement was completed and logged as a milestone."""

MARKDOWN_NOTE = """# Project North

The observation remains under review.

- Repeat the measurement
- Preserve the original reading

> No cause has been confirmed.

```text
do_not_execute("source content")
```
"""

CONVERSATION: list[dict[str, Any]] = [
    {"speaker": "Mara", "content": "The sensor moved.", "timestamp": "2026-07-01T09:00:00Z"},
    {"speaker": "Ivo", "content": "I will check the mount.", "timestamp": "2026-07-01T09:01:00Z"},
    {"speaker": "Mara", "content": "Keep the first reading unchanged.", "timestamp": "2026-07-01T09:02:00Z"},
]

JSON_DOCUMENT: dict[str, Any] = {
    "project": {"name": "North", "status": "review", "city": "Malmö"},
    "records": [
        {"id": 1, "value": "α"},
        {"id": 2, "value": "β"},
    ],
    "version": 1,
}

TIMELINE: list[dict[str, Any]] = [
    {"timestamp": "2026-07-01T09:00:00Z", "label": "start", "content": "Observation began."},
    {"timestamp": "2026-07-02T11:00:00Z", "label": "change", "content": "Sensor direction changed."},
    {"timestamp": "2026-07-04T16:00:00Z", "label": "milestone", "content": "Repeat reading completed."},
]

STRUCTURED_LOG: list[dict[str, Any]] = [
    {
        "timestamp": "2026-07-01T09:00:00Z",
        "level": "INFO",
        "component": "collector",
        "message": "Collector started.",
    },
    {
        "timestamp": "2026-07-01T09:00:01Z",
        "level": "WARN",
        "component": "collector",
        "message": "Authorization: Bearer fixture_token_1234567890 was rejected.",
    },
]


def supported_source_fixtures() -> dict[str, SourceInput]:
    return {
        "plain_text": SourceInput("plain_text", PLAIN_STORY, idempotency_key="fixture-plain-v1"),
        "markdown": SourceInput("markdown", MARKDOWN_NOTE, idempotency_key="fixture-markdown-v1"),
        "conversation": SourceInput("conversation", CONVERSATION, idempotency_key="fixture-conversation-v1"),
        "json": SourceInput("json", JSON_DOCUMENT, idempotency_key="fixture-json-v1"),
        "timeline": SourceInput("timeline", TIMELINE, idempotency_key="fixture-timeline-v1"),
        "log": SourceInput("log", STRUCTURED_LOG, idempotency_key="fixture-log-v1"),
    }


__all__ = [
    "CONVERSATION",
    "JSON_DOCUMENT",
    "MARKDOWN_NOTE",
    "PLAIN_STORY",
    "STRUCTURED_LOG",
    "TIMELINE",
    "supported_source_fixtures",
]
