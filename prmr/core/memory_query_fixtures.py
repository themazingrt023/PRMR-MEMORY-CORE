"""Durable synthetic fixtures for deterministic memory-query proofs."""

from __future__ import annotations

from dataclasses import replace
import json
from typing import Any

from .admission_models import AdmissionDecisionActor
from .admission_service import MemoryAdmissionService
from .candidate_engine import CandidateMemoryEngine
from .entity_admission import EntityAdmissionService
from .entity_candidates import EntityCandidateEngine
from .relationship_admission import RelationshipAdmissionService
from .relationship_candidates import RelationshipCandidateEngine
from .source_ledger import SourceLedger
from .source_models import AuthenticatedScope, SourceInput


QUERY_FIXTURE_ACTOR = AdmissionDecisionActor("test_runner", "core-sprint-7")


def query_fixture_scope(name: str) -> AuthenticatedScope:
    return AuthenticatedScope(
        f"client_query_{name}",
        f"vault_query_{name}",
        "default",
        application_reference=f"app_query_{name}",
        actor_reference=f"actor_query_{name}",
        workspace_reference=f"workspace_query_{name}",
        session_reference=f"session_query_{name}",
    )


def admit_query_source(
    repository: Any,
    scope: AuthenticatedScope,
    source_input: SourceInput,
    *,
    key_suffix: str,
) -> dict[str, Any]:
    source_input = replace(
        source_input,
        application_reference=scope.application_reference,
        actor_reference=scope.actor_reference,
        workspace_reference=scope.workspace_reference,
        session_reference=scope.session_reference,
        idempotency_key=f"{source_input.idempotency_key}:{key_suffix}",
    )
    source = SourceLedger(repository).ingest_source(scope, source_input).source
    candidates = CandidateMemoryEngine(repository).extract_candidates(
        scope, source.source_id
    ).candidates
    if not candidates:
        raise RuntimeError("Memory-query fixture produced no candidate memory.")
    admitted = MemoryAdmissionService(repository).accept_candidate(
        scope,
        candidates[0].candidate_id,
        QUERY_FIXTURE_ACTOR,
        "Admit controlled synthetic Core Sprint 7 fixture.",
        f"query-admit:{key_suffix}",
    )
    return {
        "source": source,
        "candidate": candidates[0],
        "admission": admitted.admission,
        "event": admitted.admitted_event,
    }


def admit_query_entity(
    repository: Any,
    scope: AuthenticatedScope,
    source_input: SourceInput,
    *,
    key_suffix: str,
) -> dict[str, Any]:
    source = SourceLedger(repository).ingest_source(
        scope,
        replace(
            source_input,
            idempotency_key=f"{source_input.idempotency_key}:{key_suffix}",
        ),
    ).source
    candidates = EntityCandidateEngine(repository).extract_source_entities(
        scope, source.source_id
    )
    if not candidates:
        raise RuntimeError("Memory-query fixture produced no entity candidate.")
    admitted = EntityAdmissionService(repository).admit_entity_candidate(
        scope,
        candidates[0].entity_candidate_id,
        QUERY_FIXTURE_ACTOR,
        "create_new_entity",
        reason="Admit controlled synthetic Core Sprint 7 entity.",
        idempotency_key=f"query-entity:{key_suffix}",
    )
    return {"source": source, "candidate": candidates[0], **admitted}


def admit_query_relationship(
    repository: Any,
    scope: AuthenticatedScope,
    source_input: SourceInput,
    *,
    key_suffix: str,
) -> dict[str, Any]:
    source = SourceLedger(repository).ingest_source(
        scope,
        replace(
            source_input,
            idempotency_key=f"{source_input.idempotency_key}:{key_suffix}",
        ),
    ).source
    candidates = RelationshipCandidateEngine(repository).extract_source_relationships(
        scope, source.source_id
    )
    if not candidates:
        raise RuntimeError("Memory-query fixture produced no relationship candidate.")
    admitted = RelationshipAdmissionService(repository).admit_relationship_candidate(
        scope,
        candidates[0].relationship_candidate_id,
        QUERY_FIXTURE_ACTOR,
        reason="Admit controlled synthetic Core Sprint 7 relationship.",
        idempotency_key=f"query-relationship:{key_suffix}",
    )
    return {"source": source, "candidate": candidates[0], **admitted}


def insert_legacy_query_event(
    repository: Any,
    scope: AuthenticatedScope,
    *,
    event_id: str = "evt_legacy_query_fixture",
) -> dict[str, Any]:
    event = {
        "event_id": event_id,
        "user_id": "synthetic_user",
        "type": "observation.recorded",
        "content": "Legacy synthetic event without SourceLedger provenance.",
        "timestamp": "2025-01-15T00:00:00Z",
        "timestamp_index": 1,
        "synthetic": True,
        "application_reference": scope.application_reference or "",
        "actor_reference": scope.actor_reference or "",
        "workspace_reference": scope.workspace_reference or "",
        "entity_reference": "",
        "session_reference": scope.session_reference or "",
        "external_metadata": {"metadata": {"synthetic": True}},
    }
    key = MemoryAdmissionService(repository).bridge.scope_key(scope)
    with repository.connect() as connection:
        row = connection.execute(
            "SELECT payload_json FROM events WHERE scope_key=?",
            (key,),
        ).fetchone()
        events = (
            MemoryAdmissionService(repository).bridge.event_list_from_storage(
                row["payload_json"]
            )
            if row
            else []
        )
        events.append(event)
        connection.execute(
            "INSERT INTO events(scope_key,payload_json) VALUES(?,?) "
            "ON CONFLICT(scope_key) DO UPDATE SET payload_json=excluded.payload_json",
            (key, json.dumps(events, sort_keys=True)),
        )
    return event


__all__ = [
    "QUERY_FIXTURE_ACTOR",
    "admit_query_entity",
    "admit_query_relationship",
    "admit_query_source",
    "insert_legacy_query_event",
    "query_fixture_scope",
]
