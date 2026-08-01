"""Deterministic internal fixtures for Memory Admission V1."""

from __future__ import annotations

from .candidate_fixtures import RICH_STORY
from .source_models import SourceInput


CORRECTION_SOURCE = "Observation: Use the local deployment."

POLICY_STRUCTURED = {
    "event_type": "decision.recorded",
    "signal": "Use the verified source ledger.",
    "occurred_at": "2026-07-21T09:00:00Z",
    "previous_state": "unverified input",
    "current_state": "verified source ledger",
}

POLICY_LABELLED = """Goal: Prove conservative memory admission.
Decision: Preserve exact provenance."""

POLICY_LEXICAL = "The team decided to review the candidate later."
POLICY_INFERRED = "It seemed that a stale index may have caused the failure."
POLICY_UNKNOWN = "The original cause remains unknown."
POLICY_QUOTED = 'Alice said, "The server was fixed."'


def story_admission_fixture() -> SourceInput:
    return SourceInput(
        "plain_text",
        RICH_STORY,
        occurred_at="2026-07-20T08:00:00Z",
        idempotency_key="memory-admission-story-v1",
    )


def correction_fixture() -> SourceInput:
    return SourceInput(
        "plain_text",
        CORRECTION_SOURCE,
        occurred_at="2026-07-21T08:00:00Z",
        idempotency_key="memory-admission-correction-v1",
    )


def admission_policy_fixtures() -> dict[str, SourceInput]:
    return {
        "structured": SourceInput(
            "json", POLICY_STRUCTURED, idempotency_key="admission-policy-structured-v1"
        ),
        "labelled": SourceInput(
            "markdown", POLICY_LABELLED, idempotency_key="admission-policy-labelled-v1"
        ),
        "lexical": SourceInput(
            "plain_text", POLICY_LEXICAL, idempotency_key="admission-policy-lexical-v1"
        ),
        "inferred": SourceInput(
            "plain_text", POLICY_INFERRED, idempotency_key="admission-policy-inferred-v1"
        ),
        "unknown": SourceInput(
            "plain_text", POLICY_UNKNOWN, idempotency_key="admission-policy-unknown-v1"
        ),
        "quoted": SourceInput(
            "plain_text", POLICY_QUOTED, idempotency_key="admission-policy-quoted-v1"
        ),
        "ephemeral": SourceInput(
            "json",
            POLICY_STRUCTURED,
            retention_policy="ephemeral",
            expires_at="2099-01-01T00:00:00Z",
            idempotency_key="admission-policy-ephemeral-v1",
        ),
    }


__all__ = [
    "CORRECTION_SOURCE",
    "POLICY_INFERRED",
    "POLICY_LABELLED",
    "POLICY_LEXICAL",
    "POLICY_QUOTED",
    "POLICY_STRUCTURED",
    "POLICY_UNKNOWN",
    "admission_policy_fixtures",
    "correction_fixture",
    "story_admission_fixture",
]
