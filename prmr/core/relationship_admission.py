"""Controlled admission of evidence-backed relationship candidates."""

from __future__ import annotations

from dataclasses import replace
import json
import logging
from typing import Any

from .admission_models import AdmissionDecisionActor
from .entity_resolution import EntityResolver
from .entity_store import (
    initialize_entity_relationship_schema,
    json_value,
    payload_from_row,
    placeholder,
    scope_fingerprint,
    scope_params,
    table,
    utc,
    utc_now,
)
from .relationship_candidates import RelationshipCandidateEngine
from .relationship_models import (
    BUILTIN_RELATIONSHIP_TYPES,
    CAUSAL_OR_HIGH_RISK_RELATIONSHIPS,
    RELATIONSHIP_ADMISSION_REVISION,
    RELATIONSHIP_EVOLUTION_REVISION,
    RELATIONSHIP_MEMORY_SCHEMA_REVISION,
    RelationshipCandidate,
    RelationshipMemoryError,
    RelationshipRecord,
)
from .source_integrity import canonical_json, sha256_text
from .source_models import AuthenticatedScope


LOGGER = logging.getLogger("prmr.core.relationship_admission")
SAFE_RELATIONSHIP_AUTO_POLICY = "safe_relationship_auto_v1"


class RelationshipAdmissionService:
    def __init__(self, repository: Any, *, initialize: bool = True) -> None:
        self.repository = repository
        if initialize:
            initialize_entity_relationship_schema(repository)
        self.candidates = RelationshipCandidateEngine(
            repository, initialize=initialize
        )
        self.entities = EntityResolver(repository, initialize=False)
        self.relationship_table = table(repository, "prmr_relationships")
        self.admission_table = table(
            repository, "prmr_relationship_admission_decisions"
        )
        self.p = placeholder(repository)

    def admit_relationship_candidate(
        self,
        scope: AuthenticatedScope,
        relationship_candidate_id: str,
        decision_actor: AdmissionDecisionActor,
        *,
        subject_entity_id: str | None = None,
        object_entity_id: str | None = None,
        reason: str,
        idempotency_key: str | None = None,
        system_effective_at: str | None = None,
    ) -> dict[str, Any]:
        decision_actor.validate()
        candidate = self.candidates.get_candidate(
            scope, relationship_candidate_id
        )
        if candidate.candidate_status == "accepted":
            return self._accepted_result(scope, candidate)
        if candidate.candidate_status in {"rejected", "corrected", "invalidated"}:
            raise RelationshipMemoryError(
                "RELATIONSHIP_CANDIDATE_INVALID",
                "Relationship candidate is not eligible for admission.",
            )
        evidence = self.candidates.get_evidence(
            scope, relationship_candidate_id
        )
        if not evidence or not any(item.evidence_role == "primary" for item in evidence):
            raise RelationshipMemoryError(
                "RELATIONSHIP_EVIDENCE_INVALID",
                "Primary relationship evidence is required.",
            )
        if not self.candidates.ledger.verify_source_integrity(
            scope, candidate.source_id
        ).verified:
            raise RelationshipMemoryError(
                "RELATIONSHIP_EVIDENCE_INVALID", "Source integrity failed."
            )
        subject_id = subject_entity_id or candidate.subject_entity_id
        object_id = object_entity_id or candidate.object_entity_id
        if not subject_id or not object_id:
            raise RelationshipMemoryError(
                "RELATIONSHIP_ENDPOINT_UNRESOLVED",
                "Both relationship endpoints must resolve to canonical entities.",
            )
        subject = self.entities.get_entity(scope, subject_id, resolve_current=True)
        object_ = self.entities.get_entity(scope, object_id, resolve_current=True)
        if subject.entity_id == object_.entity_id:
            raise RelationshipMemoryError(
                "RELATIONSHIP_SELF_LINK_INVALID",
                "Unsupported self-relationship was rejected.",
            )
        if candidate.proposed_relationship_type == "unknown_relationship":
            raise RelationshipMemoryError(
                "RELATIONSHIP_TYPE_INVALID",
                "Unknown relationship cannot be admitted.",
            )
        valid_from = utc(
            candidate.proposed_valid_from,
            default=self.candidates.ledger.get_source(
                scope, candidate.source_id
            ).occurred_at,
        )
        valid_until = (
            utc(candidate.proposed_valid_until)
            if candidate.proposed_valid_until
            else None
        )
        if valid_until and valid_until <= valid_from:
            raise RelationshipMemoryError(
                "RELATIONSHIP_CANDIDATE_INVALID",
                "Relationship valid time is incoherent.",
            )
        idem = sha256_text(
            canonical_json(
                {
                    "scope": scope.memory_boundary(),
                    "candidate": candidate.relationship_candidate_id,
                    "subject": subject.entity_id,
                    "object": object_.entity_id,
                    "key": idempotency_key or "",
                    "revision": RELATIONSHIP_ADMISSION_REVISION,
                }
            )
        )
        replay = self._admission_by_idempotency(scope, idem)
        if replay:
            relationship = self.get_relationship(
                scope, str(replay["relationship_id"])
            )
            return {
                "relationship": relationship,
                "admission": replay,
                "created": False,
                "replayed": True,
            }
        fingerprint = sha256_text(
            canonical_json(
                {
                    "scope": scope.memory_boundary(),
                    "subject": subject.entity_id,
                    "relationship_type": candidate.proposed_relationship_type,
                    "object": object_.entity_id,
                    "valid_from": valid_from,
                    "candidate_fingerprint": (
                        candidate.relationship_candidate_fingerprint_sha256
                    ),
                    "revision": RELATIONSHIP_MEMORY_SCHEMA_REVISION,
                }
            )
        )
        relationship_id = f"rel_{fingerprint[:24]}"
        admission_id = f"radmit_{idem[:24]}"
        now = utc(system_effective_at) if system_effective_at else utc_now()
        relationship = RelationshipRecord(
            relationship_id=relationship_id,
            client_id=scope.client_id,
            vault_id=scope.vault_id,
            namespace=scope.namespace,
            subject_entity_id=subject.entity_id,
            relationship_type=candidate.proposed_relationship_type,
            object_entity_id=object_.entity_id,
            relationship_status="active",
            epistemic_status=candidate.epistemic_status,
            originating_relationship_candidate_id=(
                candidate.relationship_candidate_id
            ),
            originating_source_id=candidate.source_id,
            originating_admission_id=admission_id,
            valid_from=valid_from,
            valid_until=valid_until,
            system_known_from=now,
            system_known_until=None,
            relationship_fingerprint_sha256=fingerprint,
            evidence_manifest_hash_sha256=candidate.evidence_manifest_hash_sha256,
            relationship_schema_revision=RELATIONSHIP_MEMORY_SCHEMA_REVISION,
            relationship_admission_revision=RELATIONSHIP_ADMISSION_REVISION,
            relationship_evolution_revision=RELATIONSHIP_EVOLUTION_REVISION,
            created_at=now,
            updated_at=now,
        )
        admission = {
            "relationship_admission_id": admission_id,
            "relationship_candidate_id": candidate.relationship_candidate_id,
            "relationship_id": relationship.relationship_id,
            "decision_type": "accept",
            "decision_status": "completed",
            "actor_type": decision_actor.actor_type,
            "actor_reference": decision_actor.actor_reference,
            "reason": reason,
            "idempotency_digest": idem,
            "decided_at": now,
            "created_at": now,
            "relationship_admission_revision": RELATIONSHIP_ADMISSION_REVISION,
        }
        with self.repository.connect() as connection:
            connection.execute(
                f"INSERT INTO {self.relationship_table}("
                "relationship_id,client_id,vault_id,namespace,subject_entity_id,"
                "relationship_type,object_entity_id,relationship_status,"
                "epistemic_status,originating_relationship_candidate_id,"
                "originating_source_id,originating_admission_id,valid_from,valid_until,"
                "system_known_from,system_known_until,relationship_fingerprint_sha256,"
                "evidence_manifest_hash_sha256,created_at,updated_at,payload_json) VALUES("
                + ",".join([self.p] * 21)
                + ")",
                (
                    relationship.relationship_id,
                    *scope_params(scope),
                    relationship.subject_entity_id,
                    relationship.relationship_type,
                    relationship.object_entity_id,
                    relationship.relationship_status,
                    relationship.epistemic_status,
                    relationship.originating_relationship_candidate_id,
                    relationship.originating_source_id,
                    relationship.originating_admission_id,
                    relationship.valid_from,
                    relationship.valid_until,
                    relationship.system_known_from,
                    relationship.system_known_until,
                    relationship.relationship_fingerprint_sha256,
                    relationship.evidence_manifest_hash_sha256,
                    relationship.created_at,
                    relationship.updated_at,
                    json_value(self.repository, relationship.to_dict()),
                ),
            )
            self._insert_admission(connection, scope, admission)
        self.candidates.update_candidate(
            replace(candidate, candidate_status="accepted", updated_at=now)
        )
        self._log(
            "relationship_admitted",
            scope,
            relationship_id=relationship.relationship_id,
            relationship_type=relationship.relationship_type,
            status="active",
        )
        return {
            "relationship": relationship,
            "admission": admission,
            "created": True,
            "replayed": False,
        }

    def auto_admit_safe_candidates(
        self, scope: AuthenticatedScope
    ) -> dict[str, Any]:
        actor = AdmissionDecisionActor("engine_policy", SAFE_RELATIONSHIP_AUTO_POLICY)
        accepted, skipped, failures = [], [], []
        for candidate in self.candidates.list_candidates(
            scope, status="pending_review"
        ):
            source = self.candidates.ledger.get_source(scope, candidate.source_id)
            eligible = (
                candidate.epistemic_status == "explicit"
                and candidate.extraction_method in {
                    "structured_field",
                    "explicit_label",
                }
                and candidate.subject_entity_id is not None
                and candidate.object_entity_id is not None
                and candidate.proposed_relationship_type
                in BUILTIN_RELATIONSHIP_TYPES
                and candidate.proposed_relationship_type
                not in CAUSAL_OR_HIGH_RISK_RELATIONSHIPS
                and not candidate.normalisation_details.get("quoted_claim")
                and source.retention_policy == "standard"
            )
            if not eligible:
                skipped.append(candidate.relationship_candidate_id)
                continue
            try:
                result = self.admit_relationship_candidate(
                    scope,
                    candidate.relationship_candidate_id,
                    actor,
                    reason="Safe automatic admission of explicit structured relationship.",
                    idempotency_key=(
                        f"{SAFE_RELATIONSHIP_AUTO_POLICY}:"
                        f"{candidate.relationship_candidate_id}"
                    ),
                )
                accepted.append(result["relationship"].relationship_id)
            except RelationshipMemoryError as exc:
                failures.append(
                    {
                        "relationship_candidate_id": (
                            candidate.relationship_candidate_id
                        ),
                        "code": exc.code,
                    }
                )
        return {
            "policy_id": SAFE_RELATIONSHIP_AUTO_POLICY,
            "accepted_relationship_ids": accepted,
            "skipped_candidate_ids": skipped,
            "failures": failures,
        }

    def reject_relationship_candidate(
        self,
        scope: AuthenticatedScope,
        candidate_id: str,
        actor: AdmissionDecisionActor,
        reason: str,
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        return self._non_accept(
            scope, candidate_id, actor, "reject", "rejected", reason, idempotency_key
        )

    def defer_relationship_candidate(
        self,
        scope: AuthenticatedScope,
        candidate_id: str,
        actor: AdmissionDecisionActor,
        reason: str,
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        return self._non_accept(
            scope, candidate_id, actor, "defer", "deferred", reason, idempotency_key
        )

    def correct_relationship_candidate(
        self,
        scope: AuthenticatedScope,
        candidate_id: str,
        actor: AdmissionDecisionActor,
        *,
        relationship_type: str,
        reason: str,
        idempotency_key: str | None = None,
    ) -> RelationshipCandidate:
        actor.validate()
        original = self.candidates.get_candidate(scope, candidate_id)
        fingerprint = sha256_text(
            canonical_json(
                {
                    "original": original.relationship_candidate_id,
                    "relationship_type": relationship_type,
                    "key": idempotency_key or "",
                    "revision": RELATIONSHIP_ADMISSION_REVISION,
                }
            )
        )
        now = utc_now()
        replacement = replace(
            original,
            relationship_candidate_id=f"rcand_{fingerprint[:24]}",
            proposed_relationship_type=relationship_type,
            candidate_status="pending_review",
            relationship_candidate_fingerprint_sha256=fingerprint,
            normalisation_details={
                **original.normalisation_details,
                "corrected_from_relationship_candidate_id": original.relationship_candidate_id,
                "correction_reason_hash": sha256_text(reason),
            },
            created_at=now,
            updated_at=now,
        )
        evidence = self.candidates.get_evidence(scope, candidate_id)
        with self.repository.connect() as connection:
            connection.execute(
                f"INSERT INTO {self.candidates.candidate_table}("
                "relationship_candidate_id,extraction_run_id,source_id,client_id,"
                "vault_id,namespace,subject_entity_id,object_entity_id,"
                "proposed_relationship_type,candidate_status,"
                "relationship_candidate_fingerprint_sha256,"
                "evidence_manifest_hash_sha256,relationship_candidate_revision,"
                "created_at,updated_at,payload_json) VALUES("
                + ",".join([self.p] * 16)
                + ")",
                (
                    replacement.relationship_candidate_id,
                    replacement.extraction_run_id,
                    replacement.source_id,
                    replacement.client_id,
                    replacement.vault_id,
                    replacement.namespace,
                    replacement.subject_entity_id,
                    replacement.object_entity_id,
                    replacement.proposed_relationship_type,
                    replacement.candidate_status,
                    replacement.relationship_candidate_fingerprint_sha256,
                    replacement.evidence_manifest_hash_sha256,
                    replacement.relationship_candidate_revision,
                    replacement.created_at,
                    replacement.updated_at,
                    json_value(self.repository, replacement.to_dict()),
                ),
            )
            for index, item in enumerate(evidence):
                copied = replace(
                    item,
                    relationship_evidence_id=(
                        f"revid_{sha256_text(canonical_json({'candidate': replacement.relationship_candidate_id, 'index': index}))[:24]}"
                    ),
                    relationship_candidate_id=replacement.relationship_candidate_id,
                )
                connection.execute(
                    f"INSERT INTO {self.candidates.evidence_table}("
                    "relationship_evidence_id,relationship_candidate_id,source_id,"
                    "segment_id,evidence_role,sequence_index,evidence_text_hash_sha256,"
                    "segment_content_hash_sha256,created_at,payload_json) VALUES("
                    + ",".join([self.p] * 10)
                    + ")",
                    (
                        copied.relationship_evidence_id,
                        copied.relationship_candidate_id,
                        copied.source_id,
                        copied.segment_id,
                        copied.evidence_role,
                        copied.sequence_index,
                        copied.evidence_text_hash_sha256,
                        copied.segment_content_hash_sha256,
                        copied.created_at,
                        json_value(self.repository, copied.to_dict()),
                    ),
                )
        self.candidates.update_candidate(
            replace(original, candidate_status="corrected", updated_at=now)
        )
        return replacement

    def get_relationship(
        self, scope: AuthenticatedScope, relationship_id: str
    ) -> RelationshipRecord:
        with self.repository.connect() as connection:
            row = connection.execute(
                f"SELECT payload_json FROM {self.relationship_table} "
                f"WHERE relationship_id={self.p} AND client_id={self.p} "
                f"AND vault_id={self.p} AND namespace={self.p}",
                (relationship_id, *scope_params(scope)),
            ).fetchone()
        if not row:
            raise RelationshipMemoryError(
                "RELATIONSHIP_NOT_FOUND",
                "Relationship was not found in authenticated scope.",
            )
        return RelationshipRecord(**payload_from_row(row))

    def list_relationships(
        self, scope: AuthenticatedScope
    ) -> list[RelationshipRecord]:
        with self.repository.connect() as connection:
            rows = connection.execute(
                f"SELECT payload_json FROM {self.relationship_table} "
                f"WHERE client_id={self.p} AND vault_id={self.p} AND namespace={self.p} "
                "ORDER BY created_at,relationship_id",
                scope_params(scope),
            ).fetchall()
        return [RelationshipRecord(**payload_from_row(row)) for row in rows]

    def _non_accept(
        self,
        scope: AuthenticatedScope,
        candidate_id: str,
        actor: AdmissionDecisionActor,
        decision_type: str,
        status: str,
        reason: str,
        idempotency_key: str | None,
    ) -> dict[str, Any]:
        actor.validate()
        candidate = self.candidates.get_candidate(scope, candidate_id)
        idem = sha256_text(
            canonical_json(
                {
                    "scope": scope.memory_boundary(),
                    "candidate": candidate_id,
                    "decision": decision_type,
                    "key": idempotency_key or "",
                    "revision": RELATIONSHIP_ADMISSION_REVISION,
                }
            )
        )
        replay = self._admission_by_idempotency(scope, idem)
        if replay:
            return replay
        now = utc_now()
        admission = {
            "relationship_admission_id": f"radmit_{idem[:24]}",
            "relationship_candidate_id": candidate_id,
            "relationship_id": None,
            "decision_type": decision_type,
            "decision_status": "completed",
            "actor_type": actor.actor_type,
            "actor_reference": actor.actor_reference,
            "reason": reason,
            "idempotency_digest": idem,
            "decided_at": now,
            "created_at": now,
            "relationship_admission_revision": RELATIONSHIP_ADMISSION_REVISION,
        }
        with self.repository.connect() as connection:
            self._insert_admission(connection, scope, admission)
        self.candidates.update_candidate(
            replace(candidate, candidate_status=status, updated_at=now)
        )
        return admission

    def _insert_admission(
        self, connection: Any, scope: AuthenticatedScope, admission: dict[str, Any]
    ) -> None:
        connection.execute(
            f"INSERT INTO {self.admission_table}("
            "relationship_admission_id,relationship_candidate_id,relationship_id,"
            "client_id,vault_id,namespace,decision_type,decision_status,actor_type,"
            "actor_reference,reason,idempotency_digest,decided_at,created_at,payload_json"
            ") VALUES(" + ",".join([self.p] * 15) + ")",
            (
                admission["relationship_admission_id"],
                admission["relationship_candidate_id"],
                admission["relationship_id"],
                *scope_params(scope),
                admission["decision_type"],
                admission["decision_status"],
                admission["actor_type"],
                admission["actor_reference"],
                admission["reason"],
                admission["idempotency_digest"],
                admission["decided_at"],
                admission["created_at"],
                json_value(self.repository, admission),
            ),
        )

    def _admission_by_idempotency(
        self, scope: AuthenticatedScope, digest: str
    ) -> dict[str, Any] | None:
        with self.repository.connect() as connection:
            row = connection.execute(
                f"SELECT payload_json FROM {self.admission_table} "
                f"WHERE client_id={self.p} AND vault_id={self.p} "
                f"AND namespace={self.p} AND idempotency_digest={self.p}",
                (*scope_params(scope), digest),
            ).fetchone()
        return payload_from_row(row) if row else None

    def _accepted_result(
        self, scope: AuthenticatedScope, candidate: RelationshipCandidate
    ) -> dict[str, Any]:
        with self.repository.connect() as connection:
            row = connection.execute(
                f"SELECT payload_json FROM {self.admission_table} "
                f"WHERE relationship_candidate_id={self.p} AND client_id={self.p} "
                f"AND vault_id={self.p} AND namespace={self.p} "
                f"ORDER BY decided_at DESC LIMIT 1",
                (candidate.relationship_candidate_id, *scope_params(scope)),
            ).fetchone()
        if not row:
            raise RelationshipMemoryError(
                "RELATIONSHIP_INTEGRITY_FAILED",
                "Accepted relationship candidate has no admission.",
            )
        admission = payload_from_row(row)
        return {
            "relationship": self.get_relationship(
                scope, str(admission["relationship_id"])
            ),
            "admission": admission,
            "created": False,
            "replayed": True,
        }

    @staticmethod
    def _log(event: str, scope: AuthenticatedScope, **fields: Any) -> None:
        allowed = {"relationship_id", "relationship_type", "status"}
        LOGGER.info(
            "%s",
            json.dumps(
                {
                    "event": event,
                    "scope_fingerprint": scope_fingerprint(scope),
                    **{key: value for key, value in fields.items() if key in allowed},
                },
                sort_keys=True,
            ),
        )


__all__ = ["RelationshipAdmissionService", "SAFE_RELATIONSHIP_AUTO_POLICY"]
