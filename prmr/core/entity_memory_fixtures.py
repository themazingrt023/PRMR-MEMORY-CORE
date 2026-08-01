"""Synthetic deterministic fixtures for Core Sprint 6 proofs."""

from __future__ import annotations

from .source_models import SourceInput


def entity_memory_fixtures() -> dict[str, SourceInput]:
    return {
        "alex_person_one": SourceInput(
            "json",
            {
                "entity_id": "person_alex_001",
                "entity_type": "person",
                "name": "Alex Reed",
            },
            occurred_at="2025-01-01T09:00:00Z",
            idempotency_key="s6-alex-1",
        ),
        "alex_person_two": SourceInput(
            "json",
            {
                "entity_id": "person_alex_002",
                "entity_type": "person",
                "name": "Alex Reed",
            },
            occurred_at="2025-01-02T09:00:00Z",
            idempotency_key="s6-alex-2",
        ),
        "project_aurora": SourceInput(
            "json",
            {
                "entity_id": "project_aurora",
                "entity_type": "project",
                "name": "Project Aurora",
                "aliases": ["Project Dawn"],
            },
            occurred_at="2025-01-03T09:00:00Z",
            idempotency_key="s6-aurora",
        ),
        "auth_service": SourceInput(
            "json",
            {
                "entity_id": "service_auth",
                "entity_type": "software_system",
                "name": "Authentication Service",
            },
            occurred_at="2025-01-04T09:00:00Z",
            idempotency_key="s6-auth-service",
        ),
        "legacy_service": SourceInput(
            "json",
            {
                "entity_id": "service_legacy",
                "entity_type": "software_system",
                "name": "Legacy Service",
            },
            occurred_at="2025-01-05T09:00:00Z",
            idempotency_key="s6-legacy-service",
        ),
        "memory_service": SourceInput(
            "json",
            {
                "entity_id": "service_memory",
                "entity_type": "software_system",
                "name": "Memory Service",
            },
            occurred_at="2025-01-06T09:00:00Z",
            idempotency_key="s6-memory-service",
        ),
        "platform_group": SourceInput(
            "json",
            {
                "entity_id": "org_platform",
                "entity_type": "organisation",
                "name": "Platform Group",
            },
            occurred_at="2025-01-07T09:00:00Z",
            idempotency_key="s6-platform",
        ),
        "conversation": SourceInput(
            "conversation",
            [
                {
                    "speaker": "Ari",
                    "speaker_id": "speaker_ari",
                    "speaker_type": "character",
                    "content": "Project Aurora is ready.",
                    "occurred_at": "2025-02-01T10:00:00Z",
                },
                {
                    "speaker": "Ari",
                    "speaker_id": "speaker_ari",
                    "speaker_type": "character",
                    "content": "Memory Service is active.",
                    "occurred_at": "2025-02-01T10:01:00Z",
                },
            ],
            occurred_at="2025-02-01T10:00:00Z",
            idempotency_key="s6-conversation",
        ),
        "relationship_depends_auth": SourceInput(
            "json",
            {
                "subject": "project_aurora",
                "relationship": "depends_on",
                "object": "service_auth",
                "valid_from": "2025-03-01T00:00:00Z",
            },
            occurred_at="2025-03-01T00:00:00Z",
            idempotency_key="s6-rel-auth",
        ),
        "relationship_depends_legacy": SourceInput(
            "json",
            {
                "subject": "project_aurora",
                "relationship": "depends_on",
                "object": "service_legacy",
                "valid_from": "2025-03-02T00:00:00Z",
            },
            occurred_at="2025-03-02T00:00:00Z",
            idempotency_key="s6-rel-legacy",
        ),
        "relationship_depends_memory": SourceInput(
            "json",
            {
                "subject": "project_aurora",
                "relationship": "depends_on",
                "object": "service_memory",
                "valid_from": "2025-04-01T00:00:00Z",
            },
            occurred_at="2025-04-01T00:00:00Z",
            idempotency_key="s6-rel-memory",
        ),
        "relationship_owner_alex": SourceInput(
            "json",
            {
                "subject": "person_alex_001",
                "relationship": "owns",
                "object": "project_aurora",
                "valid_from": "2025-03-01T00:00:00Z",
            },
            occurred_at="2025-03-01T00:00:00Z",
            idempotency_key="s6-owner-alex",
        ),
        "relationship_owner_platform": SourceInput(
            "json",
            {
                "subject": "org_platform",
                "relationship": "owns",
                "object": "project_aurora",
                "valid_from": "2025-03-05T00:00:00Z",
            },
            occurred_at="2025-03-05T00:00:00Z",
            idempotency_key="s6-owner-platform",
        ),
        "negated_relationship": SourceInput(
            "plain_text",
            "Project Aurora does not depend on Legacy Service.",
            occurred_at="2025-03-10T00:00:00Z",
            idempotency_key="s6-negated",
        ),
        "inferred_relationship": SourceInput(
            "plain_text",
            "Project Aurora may depend on archival index.",
            occurred_at="2025-03-11T00:00:00Z",
            idempotency_key="s6-inferred",
        ),
        "unlabelled_capitals": SourceInput(
            "plain_text",
            "Tomorrow River Copper Horizon meets Tuesday.",
            occurred_at="2025-03-12T00:00:00Z",
            idempotency_key="s6-capitals",
        ),
    }


__all__ = ["entity_memory_fixtures"]
