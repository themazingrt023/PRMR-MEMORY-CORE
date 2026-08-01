"""Deterministic source-ledger fixtures for Epistemic Continuity Packet V2."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .admission_models import AdmissionDecisionActor
from .admission_service import MemoryAdmissionService
from .candidate_engine import CandidateMemoryEngine
from .canonical_signal_registry import CanonicalSignalRegistry
from .entity_admission import EntityAdmissionService
from .entity_candidates import EntityCandidateEngine
from .entity_identity_service import EntityIdentityService
from .memory_ledger_models import MemoryTemporalBoundary
from .memory_ledger_service import MemoryLedgerService
from .relationship_admission import RelationshipAdmissionService
from .relationship_candidates import RelationshipCandidateEngine
from .source_ledger import SourceLedger
from .source_models import AuthenticatedScope, SourceInput


FIXED_VALID_AT = "2026-08-02T12:00:00Z"
FIXED_KNOWN_AT = "2099-01-01T00:00:00Z"
FIXED_BOUNDARY = MemoryTemporalBoundary(
    valid_at=FIXED_VALID_AT,
    known_at=FIXED_KNOWN_AT,
)
FIXTURE_ACTOR = AdmissionDecisionActor("test_runner", "core-sprint-13")


@dataclass
class ContinuityV2FixtureState:
    scope: AuthenticatedScope
    events: dict[str, dict[str, Any]] = field(default_factory=dict)
    sources: dict[str, str] = field(default_factory=dict)
    candidates: dict[str, str] = field(default_factory=dict)
    admissions: dict[str, str] = field(default_factory=dict)
    entities: dict[str, str] = field(default_factory=dict)
    relationships: dict[str, str] = field(default_factory=dict)
    conflicts: dict[str, str] = field(default_factory=dict)
    canonical_proposals: dict[str, str] = field(default_factory=dict)


class ContinuityV2FixtureBuilder:
    """Build V2 histories through the authoritative source/admission services."""

    def __init__(self, repository: Any, scope: AuthenticatedScope) -> None:
        self.repository = repository
        self.scope = scope
        self.ledger = SourceLedger(repository)
        self.candidates = CandidateMemoryEngine(repository)
        self.admission = MemoryAdmissionService(repository)
        self.memory = MemoryLedgerService(repository)
        self.entities = EntityIdentityService(repository)
        self.canonical = CanonicalSignalRegistry(repository)
        self.state = ContinuityV2FixtureState(scope)

    def admit(
        self,
        name: str,
        *,
        source_type: str,
        payload: Any,
        occurred_at: str,
        epistemic_status: str,
        event_type: str | None = None,
        state_key: str | None = None,
        state_role: str | None = None,
        state_value: str | None = None,
        entity_id: str | None = None,
    ) -> dict[str, Any]:
        metadata = {
            key: value
            for key, value in {
                "state_key": state_key,
                "state_role": state_role,
                "state_value": state_value,
            }.items()
            if value is not None
        }
        source = self.ledger.ingest_source(
            self.scope,
            SourceInput(
                source_type,
                payload,
                occurred_at=occurred_at,
                application_reference=self.scope.application_reference,
                actor_reference=self.scope.actor_reference,
                workspace_reference=self.scope.workspace_reference,
                entity_references=[entity_id] if entity_id else [],
                session_reference=self.scope.session_reference,
                metadata=metadata,
                idempotency_key=f"s13:{self.scope.client_id}:{name}",
            ),
        ).source
        extracted = self.candidates.extract_candidates(
            self.scope, source.source_id
        ).candidates
        matches = [
            item
            for item in extracted
            if item.epistemic_status == epistemic_status
            and (event_type is None or item.proposed_event_type == event_type)
        ]
        if not matches:
            observed = [
                (item.proposed_event_type, item.epistemic_status)
                for item in extracted
            ]
            raise RuntimeError(
                f"Fixture {name!r} did not yield {epistemic_status}/{event_type}; "
                f"observed {observed}."
            )
        candidate = sorted(matches, key=lambda item: item.candidate_id)[0]
        accepted = self.admission.accept_candidate(
            self.scope,
            candidate.candidate_id,
            FIXTURE_ACTOR,
            "Controlled synthetic Epistemic Continuity Packet V2 fixture.",
            f"s13-admit:{self.scope.client_id}:{name}",
            frozen_decision_time="2026-08-01T02:00:00Z",
        )
        event = dict(accepted.admitted_event or {})
        self.state.events[name] = event
        self.state.sources[name] = source.source_id
        self.state.candidates[name] = candidate.candidate_id
        self.state.admissions[name] = accepted.admission.admission_id
        if entity_id:
            self.entities.link_event_to_entity(
                self.scope,
                str(event["event_id"]),
                entity_id,
                "primary_subject",
                epistemic_status,
                FIXTURE_ACTOR,
                "Explicit stable entity reference in the controlled fixture.",
                source_id=source.source_id,
                candidate_id=candidate.candidate_id,
                admission_id=accepted.admission.admission_id,
                link_method="explicit_event_reference",
                idempotency_key=f"s13-link:{self.scope.client_id}:{name}",
            )
        return event

    def explicit_state(
        self,
        name: str,
        *,
        event_type: str,
        signal: str,
        occurred_at: str,
        state_key: str,
        state_value: str,
        state_role: str | None = None,
        entity_id: str | None = None,
    ) -> dict[str, Any]:
        return self.admit(
            name,
            source_type="json",
            payload={
                "event_type": event_type,
                "signal": signal,
                "occurred_at": occurred_at,
            },
            occurred_at=occurred_at,
            epistemic_status="explicit",
            event_type=event_type,
            state_key=state_key,
            state_role=state_role,
            state_value=state_value,
            entity_id=entity_id,
        )

    def derived_transition(
        self,
        name: str,
        *,
        previous_state: str,
        current_state: str,
        occurred_at: str,
        state_key: str,
        entity_id: str | None = None,
    ) -> dict[str, Any]:
        return self.admit(
            name,
            source_type="json",
            payload={
                "event_type": "status.updated",
                "signal": f"Status recorded as {current_state}.",
                "occurred_at": occurred_at,
                "previous_state": previous_state,
                "current_state": current_state,
            },
            occurred_at=occurred_at,
            epistemic_status="derived",
            event_type="state.changed",
            state_key=state_key,
            state_role="state_transition",
            state_value=current_state,
            entity_id=entity_id,
        )

    def inferred_state(
        self,
        name: str,
        *,
        statement: str,
        occurred_at: str,
        state_key: str,
        state_value: str,
        entity_id: str | None = None,
    ) -> dict[str, Any]:
        return self.admit(
            name,
            source_type="plain_text",
            payload=statement,
            occurred_at=occurred_at,
            epistemic_status="inferred",
            state_key=state_key,
            state_role="observation",
            state_value=state_value,
            entity_id=entity_id,
        )

    def unknown_state(
        self,
        name: str,
        *,
        statement: str,
        occurred_at: str,
        state_key: str,
        entity_id: str | None = None,
    ) -> dict[str, Any]:
        return self.admit(
            name,
            source_type="plain_text",
            payload=statement,
            occurred_at=occurred_at,
            epistemic_status="unknown",
            event_type="information.unknown",
            state_key=state_key,
            state_role="unknown",
            state_value=statement,
            entity_id=entity_id,
        )

    def create_entity(
        self,
        name: str,
        *,
        stable_id: str,
        entity_type: str,
        label: str,
        aliases: list[str] | None = None,
        occurred_at: str = "2026-01-01T00:00:00Z",
    ) -> str:
        source = self.ledger.ingest_source(
            self.scope,
            SourceInput(
                "json",
                {
                    "entity_id": stable_id,
                    "entity_type": entity_type,
                    "name": label,
                    "aliases": aliases or [],
                },
                occurred_at=occurred_at,
                idempotency_key=f"s13-entity:{self.scope.client_id}:{name}",
            ),
        ).source
        candidates = EntityCandidateEngine(self.repository).extract_source_entities(
            self.scope, source.source_id
        )
        if not candidates:
            raise RuntimeError(f"Entity fixture {name!r} created no candidate.")
        admitted = EntityAdmissionService(self.repository).admit_entity_candidate(
            self.scope,
            candidates[0].entity_candidate_id,
            FIXTURE_ACTOR,
            "create_new_entity",
            reason="Controlled synthetic V2 entity fixture.",
            idempotency_key=f"s13-entity-admit:{self.scope.client_id}:{name}",
        )
        entity_id = admitted["entity"].entity_id
        self.state.entities[name] = entity_id
        return entity_id

    def create_relationship(
        self,
        name: str,
        *,
        subject_entity_id: str,
        relationship_type: str,
        object_entity_id: str,
        occurred_at: str,
        inferred: bool = False,
        subject_label: str = "Project Alpha",
        object_label: str = "Authentication Service",
    ) -> str:
        payload: Any
        source_type: str
        if inferred:
            source_type = "plain_text"
            payload = f"{subject_label} may {relationship_type.replace('_', ' ')} {object_label}."
        else:
            source_type = "json"
            payload = {
                "subject": subject_entity_id,
                "relationship": relationship_type,
                "object": object_entity_id,
                "valid_from": occurred_at,
            }
        source = self.ledger.ingest_source(
            self.scope,
            SourceInput(
                source_type,
                payload,
                occurred_at=occurred_at,
                idempotency_key=f"s13-relationship:{self.scope.client_id}:{name}",
            ),
        ).source
        candidates = RelationshipCandidateEngine(
            self.repository
        ).extract_source_relationships(self.scope, source.source_id)
        matches = [
            item
            for item in candidates
            if item.proposed_relationship_type == relationship_type
            and item.epistemic_status == ("inferred" if inferred else "explicit")
        ]
        if not matches:
            raise RuntimeError(
                f"Relationship fixture {name!r} created no matching candidate."
            )
        admitted = RelationshipAdmissionService(
            self.repository
        ).admit_relationship_candidate(
            self.scope,
            matches[0].relationship_candidate_id,
            FIXTURE_ACTOR,
            subject_entity_id=subject_entity_id,
            object_entity_id=object_entity_id,
            reason="Controlled synthetic V2 relationship fixture.",
            idempotency_key=f"s13-relationship-admit:{self.scope.client_id}:{name}",
            system_effective_at="2026-08-01T03:00:00Z",
        )
        relationship_id = admitted["relationship"].relationship_id
        self.state.relationships[name] = relationship_id
        return relationship_id

    def declare_conflict(
        self,
        name: str,
        event_names: list[str],
        *,
        conflict_type: str = "state_conflict",
    ) -> str:
        conflict = self.memory.declare_memory_contradiction(
            self.scope,
            [str(self.state.events[item]["event_id"]) for item in event_names],
            conflict_type,
            FIXTURE_ACTOR,
            "Controlled synthetic unresolved V2 conflict.",
            system_effective_at="2026-08-01T04:00:00Z",
            idempotency_key=f"s13-conflict:{self.scope.client_id}:{name}",
        )
        self.state.conflicts[name] = conflict.conflict_id
        return conflict.conflict_id

    def resolve_conflict(self, name: str, resolution_event_name: str) -> str:
        conflict_id = self.state.conflicts[name]
        conflict = self.memory.resolve_memory_contradiction(
            self.scope,
            conflict_id,
            str(self.state.events[resolution_event_name]["event_id"]),
            FIXTURE_ACTOR,
            "Controlled synthetic evidence resolved the conflict.",
            system_effective_at="2026-08-01T05:00:00Z",
            idempotency_key=f"s13-resolve:{self.scope.client_id}:{name}",
        )
        return conflict.conflict_id

    def propose_canonical(
        self,
        name: str,
        original: str,
        canonical: str,
        *,
        approve: bool,
    ) -> str:
        proposal = self.canonical.propose_signal_mapping(
            self.scope,
            original_signal_key=original,
            proposed_canonical_signal_key=canonical,
            proposal_basis="Controlled synthetic alias fixture.",
            proposal_method="manual_internal",
            epistemic_status="inferred",
            proposal_confidence=0.5,
            created_at="2026-08-01T00:00:00Z",
        )
        self.state.canonical_proposals[name] = proposal.canonical_signal_proposal_id
        if approve:
            self.canonical.approve_signal_mapping(
                self.scope,
                proposal.canonical_signal_proposal_id,
                actor_type="human",
                actor_reference="core-sprint-13-reviewer",
                reason="Controlled fixture review approved exact alias semantics.",
                idempotency_key=f"s13-canonical:{self.scope.client_id}:{name}",
                valid_from="2026-01-01T00:00:00Z",
                system_effective_at="2026-08-01T01:00:00Z",
            )
        return proposal.canonical_signal_proposal_id


def v2_fixture_scope(name: str) -> AuthenticatedScope:
    return AuthenticatedScope(
        f"client_continuity_v2_{name}",
        f"vault_continuity_v2_{name}",
        "default",
        application_reference=f"app_continuity_v2_{name}",
        actor_reference=f"actor_continuity_v2_{name}",
        workspace_reference=f"workspace_continuity_v2_{name}",
        session_reference=f"session_continuity_v2_{name}",
    )


def build_mixed_epistemic_fixture(
    repository: Any, name: str = "mixed"
) -> ContinuityV2FixtureState:
    builder = ContinuityV2FixtureBuilder(repository, v2_fixture_scope(name))
    builder.explicit_state(
        "explicit_status",
        event_type="status.updated",
        signal="Project status is active.",
        occurred_at="2026-07-01T09:00:00Z",
        state_key="project.status",
        state_value="active",
    )
    builder.derived_transition(
        "derived_transition",
        previous_state="planned",
        current_state="active",
        occurred_at="2026-07-02T09:00:00Z",
        state_key="project.lifecycle",
    )
    builder.inferred_state(
        "inferred_cause",
        statement="It seemed that a stale index may have caused the delay.",
        occurred_at="2026-07-03T09:00:00Z",
        state_key="project.delay_cause",
        state_value="possible stale index",
    )
    builder.unknown_state(
        "unknown_cause",
        statement="The original cause remains unknown.",
        occurred_at="2026-07-04T09:00:00Z",
        state_key="project.original_cause",
    )
    builder.explicit_state(
        "milestone",
        event_type="milestone.completed",
        signal="The verified reconstruction milestone was completed.",
        occurred_at="2026-08-02T11:00:00Z",
        state_key="project.latest_milestone",
        state_value="verified reconstruction completed",
        state_role="milestone",
    )
    return builder.state


__all__ = [
    "ContinuityV2FixtureBuilder",
    "ContinuityV2FixtureState",
    "FIXED_BOUNDARY",
    "FIXED_KNOWN_AT",
    "FIXED_VALID_AT",
    "build_mixed_epistemic_fixture",
    "v2_fixture_scope",
]
