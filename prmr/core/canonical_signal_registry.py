"""Append-only canonical signal proposal, decision, and alias registry."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone
import json
import logging
from typing import Any

from .canonical_signal_models import (
    CANONICAL_SIGNAL_DECISION_REVISION,
    CANONICAL_SIGNAL_MANIFEST_REVISION,
    CANONICAL_SIGNAL_PROJECTION_REVISION,
    CANONICAL_SIGNAL_PROPOSAL_REVISION,
    CANONICAL_SIGNAL_REGISTRY_REVISION,
    CANONICAL_SIGNAL_SCHEMA_REVISION,
    CanonicalSignalAliasAssertion,
    CanonicalSignalDecision,
    CanonicalSignalDefinition,
    CanonicalSignalError,
    CanonicalSignalProposal,
    CanonicalSignalResolution,
    validate_signal_key,
)
from .entity_store import (
    initialize_entity_relationship_schema,
    json_value,
    placeholder,
    scope_params,
    table,
)
from .source_integrity import canonical_json, sha256_text
from .source_models import AuthenticatedScope


LOGGER = logging.getLogger("prmr.core.canonical_signal")
PROPOSAL_METHODS = {
    "explicit_mapping_source",
    "manual_internal",
    "deterministic_alias_rule",
    "model_assisted",
    "observed_exact_alias",
    "legacy_migration",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def initialize_canonical_signal_schema(repository: Any) -> None:
    initialize_entity_relationship_schema(repository)
    prefix = "prmr_self_serve." if str(getattr(repository, "backend_name", "sqlite")) == "postgres" else ""
    pkey = "TEXT PRIMARY KEY"
    json_type = "JSONB" if prefix else "TEXT"
    statements = [
        f"""CREATE TABLE IF NOT EXISTS {prefix}prmr_canonical_signal_definitions (
            canonical_signal_id {pkey}, client_id TEXT NOT NULL, vault_id TEXT NOT NULL,
            namespace TEXT NOT NULL, canonical_signal_key TEXT NOT NULL,
            signal_status TEXT NOT NULL, valid_from TEXT NOT NULL, valid_until TEXT,
            system_known_from TEXT NOT NULL, system_known_until TEXT,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL, payload_json {json_type} NOT NULL,
            UNIQUE(client_id,vault_id,namespace,canonical_signal_key,system_known_from)
        )""",
        f"""CREATE TABLE IF NOT EXISTS {prefix}prmr_canonical_signal_proposals (
            canonical_signal_proposal_id {pkey}, client_id TEXT NOT NULL, vault_id TEXT NOT NULL,
            namespace TEXT NOT NULL, original_signal_key TEXT NOT NULL,
            proposed_canonical_signal_key TEXT NOT NULL, proposal_status TEXT NOT NULL,
            interpretation_response_record_id TEXT, evidence_manifest_hash TEXT NOT NULL,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL, payload_json {json_type} NOT NULL,
            UNIQUE(client_id,vault_id,namespace,evidence_manifest_hash,canonical_signal_proposal_id)
        )""",
        f"""CREATE TABLE IF NOT EXISTS {prefix}prmr_canonical_signal_decisions (
            canonical_signal_decision_id {pkey}, canonical_signal_proposal_id TEXT NOT NULL,
            client_id TEXT NOT NULL, vault_id TEXT NOT NULL, namespace TEXT NOT NULL,
            decision_type TEXT NOT NULL, decision_idempotency_digest TEXT NOT NULL,
            system_effective_at TEXT NOT NULL, created_at TEXT NOT NULL, payload_json {json_type} NOT NULL,
            UNIQUE(client_id,vault_id,namespace,decision_idempotency_digest)
        )""",
        f"""CREATE TABLE IF NOT EXISTS {prefix}prmr_canonical_signal_alias_assertions (
            signal_alias_assertion_id {pkey}, client_id TEXT NOT NULL, vault_id TEXT NOT NULL,
            namespace TEXT NOT NULL, original_signal_key TEXT NOT NULL,
            canonical_signal_id TEXT NOT NULL, assertion_status TEXT NOT NULL,
            valid_from TEXT NOT NULL, valid_until TEXT, system_known_from TEXT NOT NULL,
            system_known_until TEXT, alias_fingerprint_sha256 TEXT NOT NULL,
            created_at TEXT NOT NULL, payload_json {json_type} NOT NULL
        )""",
        f"""CREATE TABLE IF NOT EXISTS {prefix}prmr_canonical_artifact_invalidations (
            invalidation_id {pkey}, client_id TEXT NOT NULL, vault_id TEXT NOT NULL,
            namespace TEXT NOT NULL, mapping_decision_id TEXT NOT NULL,
            invalidation_type TEXT NOT NULL, created_at TEXT NOT NULL, payload_json {json_type} NOT NULL
        )""",
        f"""CREATE TABLE IF NOT EXISTS {prefix}prmr_canonical_signal_artifacts (
            canonical_artifact_id {pkey}, client_id TEXT NOT NULL,
            vault_id TEXT NOT NULL, namespace TEXT NOT NULL, artifact_type TEXT NOT NULL,
            valid_at TEXT NOT NULL, known_at TEXT NOT NULL,
            mapping_manifest_hash TEXT NOT NULL, artifact_hash TEXT NOT NULL,
            artifact_status TEXT NOT NULL, created_at TEXT NOT NULL,
            payload_json {json_type} NOT NULL
        )""",
    ]
    with repository.connect() as connection:
        for statement in statements:
            connection.execute(statement)
        indexes = [
            ("prmr_csig_def_scope_idx", "prmr_canonical_signal_definitions(client_id,vault_id,namespace,canonical_signal_key)"),
            ("prmr_csig_prop_scope_idx", "prmr_canonical_signal_proposals(client_id,vault_id,namespace,proposal_status)"),
            ("prmr_csig_alias_scope_idx", "prmr_canonical_signal_alias_assertions(client_id,vault_id,namespace,original_signal_key,assertion_status)"),
        ]
        for name, expression in indexes:
            connection.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {prefix}{expression}")


class CanonicalSignalRegistry:
    def __init__(self, repository: Any, *, initialize: bool = True) -> None:
        self.repository = repository
        if initialize:
            initialize_canonical_signal_schema(repository)
        self.p = placeholder(repository)
        self.definitions = table(repository, "prmr_canonical_signal_definitions")
        self.proposals = table(repository, "prmr_canonical_signal_proposals")
        self.decisions = table(repository, "prmr_canonical_signal_decisions")
        self.aliases = table(repository, "prmr_canonical_signal_alias_assertions")
        self.invalidations = table(repository, "prmr_canonical_artifact_invalidations")
        self.artifacts = table(repository, "prmr_canonical_signal_artifacts")

    def propose_signal_mapping(
        self,
        scope: AuthenticatedScope,
        *,
        original_signal_key: str,
        proposed_canonical_signal_key: str,
        proposal_basis: str,
        proposal_method: str,
        source_ids: tuple[str, ...] = (),
        event_ids: tuple[str, ...] = (),
        candidate_ids: tuple[str, ...] = (),
        interpretation_response_record_id: str | None = None,
        epistemic_status: str = "inferred",
        proposal_confidence: float = 0.5,
        evidence_manifest_hash: str | None = None,
        created_at: str | None = None,
    ) -> CanonicalSignalProposal:
        original = validate_signal_key(original_signal_key)
        canonical = validate_signal_key(proposed_canonical_signal_key)
        if proposal_method not in PROPOSAL_METHODS:
            raise CanonicalSignalError(
                "CANONICAL_SIGNAL_INVALID", "Signal proposal method is invalid."
            )
        if not 0.0 <= proposal_confidence <= 1.0:
            raise CanonicalSignalError(
                "CANONICAL_SIGNAL_INVALID", "Signal proposal confidence is invalid."
            )
        now = created_at or utc_now()
        evidence_hash = evidence_manifest_hash or sha256_text(
            canonical_json(
                {
                    "sources": sorted(source_ids),
                    "events": sorted(event_ids),
                    "candidates": sorted(candidate_ids),
                    "response": interpretation_response_record_id,
                }
            )
        )
        identity = {
            "scope": scope.memory_boundary(),
            "original": original,
            "canonical": canonical,
            "method": proposal_method,
            "evidence": evidence_hash,
            "response": interpretation_response_record_id,
            "revision": CANONICAL_SIGNAL_PROPOSAL_REVISION,
        }
        proposal_id = f"csprop_{sha256_text(canonical_json(identity))[:24]}"
        existing = self._proposal(scope, proposal_id)
        if existing:
            return existing
        proposal = CanonicalSignalProposal(
            canonical_signal_proposal_id=proposal_id,
            client_id=scope.client_id,
            vault_id=scope.vault_id,
            namespace=scope.namespace,
            original_signal_key=original,
            proposed_canonical_signal_key=canonical,
            proposal_basis=proposal_basis[:500],
            proposal_method=proposal_method,
            source_ids=tuple(sorted(set(source_ids))),
            event_ids=tuple(sorted(set(event_ids))),
            candidate_ids=tuple(sorted(set(candidate_ids))),
            interpretation_response_record_id=interpretation_response_record_id,
            epistemic_status=epistemic_status,
            proposal_confidence=proposal_confidence,
            evidence_manifest_hash=evidence_hash,
            proposal_status="pending_review",
            canonical_signal_proposal_revision=CANONICAL_SIGNAL_PROPOSAL_REVISION,
            created_at=now,
            updated_at=now,
        )
        with self.repository.connect() as connection:
            connection.execute(
                f"INSERT INTO {self.proposals}(canonical_signal_proposal_id,client_id,"
                f"vault_id,namespace,original_signal_key,proposed_canonical_signal_key,"
                f"proposal_status,interpretation_response_record_id,evidence_manifest_hash,"
                f"created_at,updated_at,payload_json) VALUES({','.join([self.p]*12)})",
                (
                    proposal_id,
                    scope.client_id,
                    scope.vault_id,
                    scope.namespace,
                    original,
                    canonical,
                    proposal.proposal_status,
                    interpretation_response_record_id,
                    evidence_hash,
                    now,
                    now,
                    json_value(self.repository, proposal.to_dict()),
                ),
            )
        self._log("canonical_signal_proposed", scope, proposal_id=proposal_id)
        return proposal

    def approve_signal_mapping(
        self,
        scope: AuthenticatedScope,
        proposal_id: str,
        *,
        actor_type: str,
        actor_reference: str,
        reason: str,
        idempotency_key: str,
        valid_from: str,
        system_effective_at: str | None = None,
    ) -> CanonicalSignalDecision:
        proposal = self.get_proposal(scope, proposal_id)
        if proposal.proposal_status == "approved":
            prior = self._latest_decision(scope, proposal_id, "approve")
            if prior:
                return prior
        if proposal.proposal_status not in {"pending_review", "deferred"}:
            raise CanonicalSignalError(
                "CANONICAL_SIGNAL_DECISION_INVALID",
                "Signal proposal cannot be approved from its current state.",
            )
        effective_at = system_effective_at or utc_now()
        active_edges = self._active_edges(
            scope, valid_at=valid_from, known_at=effective_at
        )
        if proposal.original_signal_key in active_edges:
            raise CanonicalSignalError(
                "CANONICAL_SIGNAL_MAPPING_CONFLICT",
                "An approved mapping is already active for the original signal.",
            )
        self._ensure_acyclic(
            scope,
            proposal.original_signal_key,
            proposal.proposed_canonical_signal_key,
        )
        try:
            return self._decide(
                scope,
                proposal,
                "approve",
                actor_type,
                actor_reference,
                reason,
                idempotency_key,
                valid_from,
                effective_at,
            )
        except Exception as exc:
            if getattr(exc, "sqlstate", None) != "23505" and (
                "unique constraint" not in str(exc).lower()
            ):
                raise
            replay = self._latest_decision(scope, proposal_id, "approve")
            if replay:
                return replay
            raise

    def apply_canonical_signal_decisions_batch(
        self,
        scope: AuthenticatedScope,
        decisions: list[dict[str, str]],
    ) -> list[CanonicalSignalDecision]:
        """Apply reviewed approvals in one outer database transaction."""

        if not decisions:
            return []
        required = {
            "proposal_id",
            "actor_type",
            "actor_reference",
            "reason",
            "idempotency_key",
            "valid_from",
        }
        for item in decisions:
            if not isinstance(item, dict) or not required.issubset(item):
                raise CanonicalSignalError(
                    "CANONICAL_SIGNAL_DECISION_INVALID",
                    "Batch decision is missing required reviewed fields.",
                )
        with self.repository.connect() as connection:
            bound = _BoundConnectionRepository(self.repository, connection)
            registry = CanonicalSignalRegistry(bound, initialize=False)
            return [
                registry.approve_signal_mapping(
                    scope,
                    item["proposal_id"],
                    actor_type=item["actor_type"],
                    actor_reference=item["actor_reference"],
                    reason=item["reason"],
                    idempotency_key=item["idempotency_key"],
                    valid_from=item["valid_from"],
                    system_effective_at=item.get("system_effective_at"),
                )
                for item in decisions
            ]

    def reject_signal_mapping(self, scope: AuthenticatedScope, proposal_id: str, **kwargs: Any) -> CanonicalSignalDecision:
        return self._review_decision(scope, proposal_id, "reject", **kwargs)

    def defer_signal_mapping(self, scope: AuthenticatedScope, proposal_id: str, **kwargs: Any) -> CanonicalSignalDecision:
        return self._review_decision(scope, proposal_id, "defer", **kwargs)

    def retract_signal_mapping(self, scope: AuthenticatedScope, proposal_id: str, **kwargs: Any) -> CanonicalSignalDecision:
        proposal = self.get_proposal(scope, proposal_id)
        if proposal.proposal_status != "approved":
            raise CanonicalSignalError(
                "CANONICAL_SIGNAL_DECISION_INVALID",
                "Only an approved signal mapping can be retracted.",
            )
        return self._decide(
            scope,
            proposal,
            "retract",
            kwargs["actor_type"],
            kwargs["actor_reference"],
            kwargs["reason"],
            kwargs["idempotency_key"],
            kwargs["valid_from"],
            kwargs.get("system_effective_at") or utc_now(),
        )

    def correct_signal_mapping(self, scope: AuthenticatedScope, proposal_id: str, **kwargs: Any) -> CanonicalSignalDecision:
        return self._review_decision(scope, proposal_id, "correct", **kwargs)

    def get_proposal(self, scope: AuthenticatedScope, proposal_id: str) -> CanonicalSignalProposal:
        found = self._proposal(scope, proposal_id)
        if not found:
            raise CanonicalSignalError(
                "CANONICAL_SIGNAL_PROPOSAL_NOT_FOUND",
                "Signal proposal was not found in authenticated scope.",
            )
        return found

    def list_signal_mappings(self, scope: AuthenticatedScope) -> list[CanonicalSignalProposal]:
        with self.repository.connect() as connection:
            rows = connection.execute(
                f"SELECT payload_json FROM {self.proposals} WHERE client_id={self.p} "
                f"AND vault_id={self.p} AND namespace={self.p} ORDER BY created_at,"
                "canonical_signal_proposal_id",
                scope_params(scope),
            ).fetchall()
        return [CanonicalSignalProposal(**self._decode(row["payload_json"], tuple_keys=("source_ids", "event_ids", "candidate_ids"))) for row in rows]

    def resolve_canonical_signal(
        self,
        scope: AuthenticatedScope,
        original_signal_key: str,
        *,
        valid_at: str,
        known_at: str,
    ) -> CanonicalSignalResolution:
        original = validate_signal_key(original_signal_key)
        edges = self._active_edges(scope, valid_at=valid_at, known_at=known_at)
        current = original
        chain = [current]
        assertions: list[str] = []
        decisions: list[str] = []
        visited = {current}
        while current in edges:
            target, alias_id, decision_id = edges[current]
            if target in visited:
                raise CanonicalSignalError(
                    "CANONICAL_SIGNAL_MAPPING_CYCLE_DETECTED",
                    "Canonical signal mapping cycle was detected.",
                )
            current = target
            visited.add(current)
            chain.append(current)
            assertions.append(alias_id)
            decisions.append(decision_id)
        manifest = sha256_text(
            canonical_json(
                {
                    "scope": scope.memory_boundary(),
                    "original": original,
                    "canonical": current,
                    "chain": chain,
                    "assertions": assertions,
                    "decisions": decisions,
                    "valid_at": valid_at,
                    "known_at": known_at,
                    "revision": CANONICAL_SIGNAL_MANIFEST_REVISION,
                }
            )
        )
        return CanonicalSignalResolution(
            original_signal_key=original,
            canonical_signal_key=current,
            mapping_applied=current != original,
            alias_assertion_ids=tuple(assertions),
            mapping_decision_ids=tuple(decisions),
            mapping_chain=tuple(chain),
            manifest_hash_sha256=manifest,
        )

    def mapping_manifest(
        self, scope: AuthenticatedScope, *, valid_at: str, known_at: str
    ) -> dict[str, Any]:
        edges = self._active_edges(scope, valid_at=valid_at, known_at=known_at)
        items = [
            {
                "original_signal_key": key,
                "canonical_signal_key": value[0],
                "alias_assertion_id": value[1],
                "mapping_decision_id": value[2],
            }
            for key, value in sorted(edges.items())
        ]
        return {
            "items": items,
            "manifest_hash_sha256": sha256_text(
                canonical_json(
                    {
                        "items": items,
                        "valid_at": valid_at,
                        "known_at": known_at,
                        "revision": CANONICAL_SIGNAL_MANIFEST_REVISION,
                    }
                )
            ),
            "revision": CANONICAL_SIGNAL_MANIFEST_REVISION,
        }

    def _review_decision(self, scope: AuthenticatedScope, proposal_id: str, decision_type: str, **kwargs: Any) -> CanonicalSignalDecision:
        proposal = self.get_proposal(scope, proposal_id)
        if proposal.proposal_status == "approved":
            raise CanonicalSignalError(
                "CANONICAL_SIGNAL_DECISION_INVALID",
                "Approved mapping requires retraction or supersession.",
            )
        return self._decide(
            scope,
            proposal,
            decision_type,
            kwargs["actor_type"],
            kwargs["actor_reference"],
            kwargs["reason"],
            kwargs["idempotency_key"],
            kwargs["valid_from"],
            kwargs.get("system_effective_at") or utc_now(),
        )

    def _decide(
        self,
        scope: AuthenticatedScope,
        proposal: CanonicalSignalProposal,
        decision_type: str,
        actor_type: str,
        actor_reference: str,
        reason: str,
        idempotency_key: str,
        valid_from: str,
        system_effective_at: str,
    ) -> CanonicalSignalDecision:
        digest = sha256_text(
            canonical_json(
                {
                    "scope": scope.memory_boundary(),
                    "idempotency_key": idempotency_key,
                    "decision_type": decision_type,
                }
            )
        )
        existing = self._decision_by_digest(scope, digest)
        if existing:
            if existing.canonical_signal_proposal_id != proposal.canonical_signal_proposal_id:
                raise CanonicalSignalError(
                    "CANONICAL_SIGNAL_REVISION_CONFLICT",
                    "Decision idempotency key conflicts.",
                )
            return existing
        material = {
            "proposal": proposal.canonical_signal_proposal_id,
            "type": decision_type,
            "digest": digest,
            "revision": CANONICAL_SIGNAL_DECISION_REVISION,
        }
        decision_id = f"csdec_{sha256_text(canonical_json(material))[:24]}"
        now = system_effective_at
        decision = CanonicalSignalDecision(
            canonical_signal_decision_id=decision_id,
            canonical_signal_proposal_id=proposal.canonical_signal_proposal_id,
            decision_type=decision_type,
            decision_actor_type=actor_type,
            decision_actor_reference=actor_reference,
            decision_reason=reason[:500],
            original_signal_key=proposal.original_signal_key,
            canonical_signal_key=proposal.proposed_canonical_signal_key,
            valid_from=valid_from,
            system_effective_at=system_effective_at,
            decision_idempotency_digest=digest,
            canonical_signal_decision_revision=CANONICAL_SIGNAL_DECISION_REVISION,
            created_at=now,
        )
        target_status = {
            "approve": "approved",
            "reject": "rejected",
            "defer": "deferred",
            "retract": "invalidated",
            "correct": "invalidated",
            "supersede": "invalidated",
        }[decision_type]
        with self.repository.connect() as connection:
            connection.execute(
                f"INSERT INTO {self.decisions}(canonical_signal_decision_id,"
                f"canonical_signal_proposal_id,client_id,vault_id,namespace,decision_type,"
                f"decision_idempotency_digest,system_effective_at,created_at,payload_json)"
                f" VALUES({','.join([self.p]*10)})",
                (
                    decision_id,
                    proposal.canonical_signal_proposal_id,
                    scope.client_id,
                    scope.vault_id,
                    scope.namespace,
                    decision_type,
                    digest,
                    system_effective_at,
                    now,
                    json_value(self.repository, decision.to_dict()),
                ),
            )
            updated = replace(proposal, proposal_status=target_status, updated_at=now)
            connection.execute(
                f"UPDATE {self.proposals} SET proposal_status={self.p},updated_at={self.p},"
                f"payload_json={self.p} WHERE canonical_signal_proposal_id={self.p}",
                (
                    target_status,
                    now,
                    json_value(self.repository, updated.to_dict()),
                    proposal.canonical_signal_proposal_id,
                ),
            )
            if decision_type == "approve":
                definition = self._definition_payload(scope, proposal, decision)
                existing_definition = connection.execute(
                    f"SELECT canonical_signal_id FROM {self.definitions} "
                    f"WHERE client_id={self.p} AND vault_id={self.p} AND namespace={self.p} "
                    f"AND canonical_signal_key={self.p} AND signal_status='active' "
                    "ORDER BY system_known_from LIMIT 1",
                    (*scope_params(scope), definition.canonical_signal_key),
                ).fetchone()
                if existing_definition:
                    definition = replace(
                        definition,
                        canonical_signal_id=str(
                            existing_definition["canonical_signal_id"]
                        ),
                    )
                else:
                    connection.execute(
                        f"INSERT INTO {self.definitions}(canonical_signal_id,client_id,vault_id,"
                        f"namespace,canonical_signal_key,signal_status,valid_from,valid_until,"
                        f"system_known_from,system_known_until,created_at,updated_at,payload_json)"
                        f" VALUES({','.join([self.p]*13)})",
                        (
                            definition.canonical_signal_id,
                            scope.client_id,
                            scope.vault_id,
                            scope.namespace,
                            definition.canonical_signal_key,
                            "active",
                            valid_from,
                            None,
                            system_effective_at,
                            None,
                            now,
                            now,
                            json_value(self.repository, definition.to_dict()),
                        ),
                    )
                assertion = self._assertion_payload(
                    scope, proposal, decision, definition.canonical_signal_id
                )
                connection.execute(
                    f"INSERT INTO {self.aliases}(signal_alias_assertion_id,client_id,"
                    f"vault_id,namespace,original_signal_key,canonical_signal_id,"
                    f"assertion_status,valid_from,valid_until,system_known_from,"
                    f"system_known_until,alias_fingerprint_sha256,created_at,payload_json)"
                    f" VALUES({','.join([self.p]*14)})",
                    (
                        assertion.signal_alias_assertion_id,
                        scope.client_id,
                        scope.vault_id,
                        scope.namespace,
                        assertion.original_signal_key,
                        assertion.canonical_signal_id,
                        assertion.assertion_status,
                        assertion.valid_from,
                        None,
                        assertion.system_known_from,
                        None,
                        assertion.alias_fingerprint_sha256,
                        now,
                        json_value(self.repository, assertion.to_dict()),
                    ),
                )
            elif decision_type in {"retract", "correct", "supersede"}:
                rows = connection.execute(
                    f"SELECT signal_alias_assertion_id,payload_json FROM {self.aliases} "
                    f"WHERE client_id={self.p} AND vault_id={self.p} AND namespace={self.p} "
                    f"AND original_signal_key={self.p} AND assertion_status='active'",
                    (*scope_params(scope), proposal.original_signal_key),
                ).fetchall()
                for row in rows:
                    payload = self._decode(row["payload_json"])
                    payload.update(
                        {
                            "assertion_status": (
                                "retracted" if decision_type == "retract" else "superseded"
                            ),
                            "valid_until": valid_from,
                            "system_known_until": system_effective_at,
                        }
                    )
                    connection.execute(
                        f"UPDATE {self.aliases} SET assertion_status={self.p},"
                        f"valid_until={self.p},system_known_until={self.p},payload_json={self.p} "
                        f"WHERE signal_alias_assertion_id={self.p}",
                        (
                            payload["assertion_status"],
                            valid_from,
                            system_effective_at,
                            json_value(self.repository, payload),
                            row["signal_alias_assertion_id"],
                        ),
                    )
            if decision_type in {"approve", "retract", "correct", "supersede"}:
                invalidation = {
                    "scope": list(scope.memory_boundary()),
                    "mapping_decision_id": decision_id,
                    "identity_mode": "canonical_signal_v1",
                    "exact_signal_artifacts_affected": False,
                }
                invalidation_id = f"csinv_{sha256_text(canonical_json(invalidation))[:24]}"
                connection.execute(
                    f"INSERT INTO {self.invalidations}(invalidation_id,client_id,vault_id,"
                    f"namespace,mapping_decision_id,invalidation_type,created_at,payload_json)"
                    f" VALUES({','.join([self.p]*8)})",
                    (
                        invalidation_id,
                        scope.client_id,
                        scope.vault_id,
                        scope.namespace,
                        decision_id,
                        "canonical_signal_mapping_changed",
                        now,
                        json_value(self.repository, invalidation),
                    ),
                )
                connection.execute(
                    f"UPDATE {self.artifacts} SET artifact_status={self.p} "
                    f"WHERE client_id={self.p} AND vault_id={self.p} "
                    f"AND namespace={self.p} AND artifact_status={self.p}",
                    (
                        "stale_mapping_revision",
                        scope.client_id,
                        scope.vault_id,
                        scope.namespace,
                        "current",
                    ),
                )
        self._log(f"canonical_signal_{decision_type}d", scope, decision_id=decision_id)
        return decision

    def _definition_payload(self, scope: AuthenticatedScope, proposal: CanonicalSignalProposal, decision: CanonicalSignalDecision) -> CanonicalSignalDefinition:
        identity = {
            "scope": scope.memory_boundary(),
            "key": proposal.proposed_canonical_signal_key,
            "decision": decision.canonical_signal_decision_id,
            "revision": CANONICAL_SIGNAL_SCHEMA_REVISION,
        }
        signal_id = f"csig_{sha256_text(canonical_json(identity))[:24]}"
        return CanonicalSignalDefinition(
            canonical_signal_id=signal_id,
            client_id=scope.client_id,
            vault_id=scope.vault_id,
            namespace=scope.namespace,
            canonical_signal_key=proposal.proposed_canonical_signal_key,
            display_label=None,
            description=None,
            signal_status="active",
            originating_decision_id=decision.canonical_signal_decision_id,
            valid_from=decision.valid_from,
            valid_until=None,
            system_known_from=decision.system_effective_at,
            system_known_until=None,
            canonical_signal_schema_revision=CANONICAL_SIGNAL_SCHEMA_REVISION,
            canonical_signal_registry_revision=CANONICAL_SIGNAL_REGISTRY_REVISION,
            created_at=decision.created_at,
            updated_at=decision.created_at,
        )

    def _assertion_payload(self, scope: AuthenticatedScope, proposal: CanonicalSignalProposal, decision: CanonicalSignalDecision, signal_id: str) -> CanonicalSignalAliasAssertion:
        material = {
            "scope": scope.memory_boundary(),
            "original": proposal.original_signal_key,
            "canonical_signal_id": signal_id,
            "decision": decision.canonical_signal_decision_id,
            "revision": CANONICAL_SIGNAL_PROJECTION_REVISION,
        }
        digest = sha256_text(canonical_json(material))
        return CanonicalSignalAliasAssertion(
            signal_alias_assertion_id=f"csalias_{digest[:24]}",
            client_id=scope.client_id,
            vault_id=scope.vault_id,
            namespace=scope.namespace,
            original_signal_key=proposal.original_signal_key,
            canonical_signal_id=signal_id,
            assertion_status="active",
            assertion_basis=proposal.proposal_method,
            proposal_id=proposal.canonical_signal_proposal_id,
            decision_id=decision.canonical_signal_decision_id,
            valid_from=decision.valid_from,
            valid_until=None,
            system_known_from=decision.system_effective_at,
            system_known_until=None,
            alias_fingerprint_sha256=digest,
            canonical_signal_projection_revision=CANONICAL_SIGNAL_PROJECTION_REVISION,
            created_at=decision.created_at,
        )

    def _active_edges(self, scope: AuthenticatedScope, *, valid_at: str, known_at: str) -> dict[str, tuple[str, str, str]]:
        with self.repository.connect() as connection:
            rows = connection.execute(
                f"SELECT a.payload_json AS alias_payload,d.payload_json AS def_payload "
                f"FROM {self.aliases} a JOIN {self.definitions} d "
                "ON a.canonical_signal_id=d.canonical_signal_id "
                f"WHERE a.client_id={self.p} AND a.vault_id={self.p} AND a.namespace={self.p}",
                scope_params(scope),
            ).fetchall()
        edges: dict[str, tuple[str, str, str]] = {}
        for row in rows:
            alias = self._decode(row["alias_payload"])
            definition = self._decode(row["def_payload"])
            if (
                alias["valid_from"] <= valid_at
                and (alias.get("valid_until") is None or valid_at < alias["valid_until"])
                and alias["system_known_from"] <= known_at
                and (
                    alias.get("system_known_until") is None
                    or known_at < alias["system_known_until"]
                )
            ):
                edges[alias["original_signal_key"]] = (
                    definition["canonical_signal_key"],
                    alias["signal_alias_assertion_id"],
                    alias["decision_id"],
                )
        return edges

    def _ensure_acyclic(self, scope: AuthenticatedScope, original: str, canonical: str) -> None:
        edges = self._active_edges(
            scope, valid_at="9999-12-31T23:59:59Z", known_at="9999-12-31T23:59:59Z"
        )
        edges[original] = (canonical, "pending", "pending")
        node = original
        seen: set[str] = set()
        while node in edges:
            if node in seen:
                self._log("canonical_signal_cycle_rejected", scope)
                raise CanonicalSignalError(
                    "CANONICAL_SIGNAL_MAPPING_CYCLE_DETECTED",
                    "Canonical signal mapping would create a cycle.",
                )
            seen.add(node)
            node = edges[node][0]
        if node == original:
            raise CanonicalSignalError(
                "CANONICAL_SIGNAL_MAPPING_CYCLE_DETECTED",
                "Canonical signal mapping would create a cycle.",
            )

    def _proposal(self, scope: AuthenticatedScope, proposal_id: str) -> CanonicalSignalProposal | None:
        with self.repository.connect() as connection:
            row = connection.execute(
                f"SELECT payload_json FROM {self.proposals} WHERE "
                f"canonical_signal_proposal_id={self.p} AND client_id={self.p} "
                f"AND vault_id={self.p} AND namespace={self.p}",
                (proposal_id, *scope_params(scope)),
            ).fetchone()
        return (
            CanonicalSignalProposal(
                **self._decode(
                    row["payload_json"],
                    tuple_keys=("source_ids", "event_ids", "candidate_ids"),
                )
            )
            if row
            else None
        )

    def _decision_by_digest(self, scope: AuthenticatedScope, digest: str) -> CanonicalSignalDecision | None:
        with self.repository.connect() as connection:
            row = connection.execute(
                f"SELECT payload_json FROM {self.decisions} WHERE client_id={self.p} "
                f"AND vault_id={self.p} AND namespace={self.p} "
                f"AND decision_idempotency_digest={self.p}",
                (*scope_params(scope), digest),
            ).fetchone()
        return CanonicalSignalDecision(**self._decode(row["payload_json"])) if row else None

    def _latest_decision(self, scope: AuthenticatedScope, proposal_id: str, decision_type: str) -> CanonicalSignalDecision | None:
        with self.repository.connect() as connection:
            row = connection.execute(
                f"SELECT payload_json FROM {self.decisions} WHERE client_id={self.p} "
                f"AND vault_id={self.p} AND namespace={self.p} "
                f"AND canonical_signal_proposal_id={self.p} AND decision_type={self.p} "
                "ORDER BY created_at DESC LIMIT 1",
                (*scope_params(scope), proposal_id, decision_type),
            ).fetchone()
        return CanonicalSignalDecision(**self._decode(row["payload_json"])) if row else None

    @staticmethod
    def _decode(value: Any, *, tuple_keys: tuple[str, ...] = ()) -> dict[str, Any]:
        payload = value if isinstance(value, dict) else json.loads(value)
        for key in tuple_keys:
            payload[key] = tuple(payload.get(key, []))
        return payload

    @staticmethod
    def _log(event: str, scope: AuthenticatedScope, **fields: Any) -> None:
        LOGGER.info(
            "%s",
            json.dumps(
                {
                    "event": event,
                    "scope_fingerprint": sha256_text(
                        canonical_json(scope.memory_boundary())
                    )[:16],
                    **fields,
                },
                sort_keys=True,
            ),
        )


class _BoundConnectionRepository:
    """Expose one outer transaction through the repository protocol."""

    def __init__(self, repository: Any, connection: Any) -> None:
        self._repository = repository
        self._connection = connection

    @property
    def backend_name(self) -> str:
        return str(getattr(self._repository, "backend_name", "sqlite"))

    @contextmanager
    def connect(self):
        yield self._connection


def apply_canonical_signal_decisions_batch(
    registry: CanonicalSignalRegistry,
    scope: AuthenticatedScope,
    decisions: list[dict[str, str]],
) -> list[CanonicalSignalDecision]:
    return registry.apply_canonical_signal_decisions_batch(scope, decisions)


__all__ = [
    "CanonicalSignalRegistry",
    "apply_canonical_signal_decisions_batch",
    "initialize_canonical_signal_schema",
    "utc_now",
]
