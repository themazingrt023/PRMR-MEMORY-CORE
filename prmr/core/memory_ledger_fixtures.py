"""Deterministic source fixtures for bitemporal memory-ledger proofs."""

from __future__ import annotations

from dataclasses import dataclass

from .source_models import SourceInput


@dataclass(frozen=True)
class MemoryLedgerFixture:
    name: str
    source: SourceInput


def memory_ledger_fixtures() -> dict[str, MemoryLedgerFixture]:
    values = {
        "correction_original": (
            "status.updated",
            "The archive contains 1,200 verified records.",
            "2025-07-01T09:00:00Z",
        ),
        "correction_replacement": (
            "status.updated",
            "Correction: The verified count is 1,150 records, not 1,200.",
            "2025-07-02T09:00:00Z",
        ),
        "supersession_original": (
            "status.updated",
            "Launch date: 1 August.",
            "2025-07-03T09:00:00Z",
        ),
        "supersession_successor": (
            "status.updated",
            "The launch date moved from 1 August to 15 August.",
            "2025-08-15T00:00:00Z",
        ),
        "retraction_original": (
            "observation.recorded",
            "The backup completed successfully.",
            "2025-07-04T09:00:00Z",
        ),
        "conflict_online": (
            "status.updated",
            "The service remained online during the incident.",
            "2025-07-05T09:00:00Z",
        ),
        "conflict_outage": (
            "status.updated",
            "The service was unavailable for twelve minutes during the incident.",
            "2025-07-05T09:05:00Z",
        ),
        "conflict_resolution": (
            "observation.recorded",
            "Monitoring records confirm a twelve-minute outage.",
            "2025-07-05T10:00:00Z",
        ),
        "late_arrival": (
            "observation.recorded",
            "A maintenance checkpoint occurred on 1 July.",
            "2025-07-01T12:00:00Z",
        ),
    }
    return {
        name: MemoryLedgerFixture(
            name,
            SourceInput(
                "json",
                {
                    "event_type": event_type,
                    "signal": signal,
                    "occurred_at": occurred_at,
                    "metadata": {"fixture": name, "synthetic": True},
                },
                occurred_at=occurred_at,
                idempotency_key=f"memory-ledger-v2:{name}",
            ),
        )
        for name, (event_type, signal, occurred_at) in values.items()
    }


__all__ = ["MemoryLedgerFixture", "memory_ledger_fixtures"]
