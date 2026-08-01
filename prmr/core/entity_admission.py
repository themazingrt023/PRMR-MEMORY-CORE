"""Controlled admission from entity candidates to canonical entity records."""

from __future__ import annotations

from dataclasses import replace
import json
import logging
from typing import Any

from .admission_models import AdmissionDecisionActor
from .entity_candidates import EntityCandidateEngine
from .entity_models import (
    ENTITY_ADMISSION_REVISION,
    ENTITY_ALIAS_REVISION,
    ENTITY_IDENTITY_REVISION,
    ENTITY_MEMORY_SCHEMA_REVISION,
    ENTITY_MENTION_REVISION,
    ENTITY_RESOLUTION_REVISION,
    EntityAliasAssertion,
    EntityCandidate,
    EntityIdentifier,
    EntityMemoryError,
    EntityRecord,
    EntityResolutionDecision,
)
from .entity_resolution import EntityResolver
from .entity_store import (
    initialize_entity_relationship_schema,
    json_value,
    normalise_label,
    payload_from_row,
    placeholder,
    scope_fingerprint,
    scope_params,
    stable_id,
    table,
    utc,
    utc_now,
)
from .source_integrity import canonical_json, sha256_text
from .source_models import AuthenticatedScope


LOGGER = logging.getLogger("prmr.core.entity_admission")
SAFE_ENTITY_AUTO_POLICY = "safe_entity_auto_v1"


class EntityAdmissionService:
    def __init__(self, repository: Any, *, initialize: bool = True) -> None:
        self.repository = repository
        if initialize:
            initialize_entity_relationship_schema(repository)
        self.candidates = EntityCandidateEngine(repository, initialize=initialize)
        self.resolver = EntityResolver(repository, initialize=False)
        self.entity_table = table(repository, "prmr_entities")
        self.identifier_table = table(repository, "prmr_entity_identifiers")
        self.resolution_table = table(repository, "prmr_entity_resolution_decisions")
        self.alias_table = table(repository, "prmr_entity_alias_assertions")
        self.p = placeholder(repository)

    def admit_entity_candidate(
        self,
        authenticated_scope: AuthenticatedScope,
        entity_candidate_id: str,
        decision_actor: AdmissionDecisionActor,
        resolution_type: str,
        selected_entity_id: str | None = None,
        reason: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        decision_actor.validate()
        candidate = self.candidates.get_candidate(
            authenticated_scope, entity_candidate_id
        )
        if candidate.candidate_status == "accepted":
            return self._accepted_result(authenticated_scope, candidate)
        if candidate.candidate_status in {"rejected", "invalidated", "corrected"}:
            raise EntityMemoryError(
                "ENTITY_CANDIDATE_INVALID",
                "Entity candidate is not eligible for admission.",
            )
        if resolution_type not in {
            "create_new_entity",
            "confirm_existing_entity",
            "confirm_alias",
        }:
            raise EntityMemoryError(
                "ENTITY_CANDIDATE_INVALID", "Admission resolution type is invalid."
            )
        evidence = self.candidates.get_evidence(
            authenticated_scope, entity_candidate_id
        )
        if not evidence or not any(item.evidence_role == "primary" for item in evidence):
            raise EntityMemoryError(
                "ENTITY_EVIDENCE_INVALID", "Primary entity evidence is required."
            )
        source_integrity = self.candidates.ledger.verify_source_integrity(
            authenticated_scope, candidate.source_id
        )
        if not source_integrity.verified:
            raise EntityMemoryError(
                "ENTITY_EVIDENCE_INVALID", "Source integrity verification failed."
            )
        existing_by_identifier = self._resolve_candidate_identifier(
            authenticated_scope, candidate
        )
        if existing_by_identifier.get("resolution_status") == "conflict":
            raise EntityMemoryError(
                "ENTITY_IDENTIFIER_CONFLICT",
                "Entity identifier conflicts with an existing entity type.",
            )
        if existing_by_identifier.get("resolution_status") == "ambiguous":
            raise EntityMemoryError(
                "ENTITY_RESOLUTION_AMBIGUOUS",
                "Entity identifier resolves ambiguously.",
            )

        selected: EntityRecord | None = None
        if selected_entity_id:
            selected = self.resolver.get_entity(
                authenticated_scope, selected_entity_id, resolve_current=True
            )
        elif existing_by_identifier.get("entity_id"):
            selected = self.resolver.get_entity(
                authenticated_scope,
                str(existing_by_identifier["entity_id"]),
                resolve_current=True,
            )
        if resolution_type in {"confirm_existing_entity", "confirm_alias"} and not selected:
            raise EntityMemoryError(
                "ENTITY_RESOLUTION_CONFLICT",
                "An existing scoped entity is required for this resolution.",
            )
        if resolution_type == "create_new_entity" and selected:
            resolution_type = "confirm_existing_entity"

        idem = self._decision_digest(
            authenticated_scope,
            candidate.entity_candidate_id,
            resolution_type,
            selected.entity_id if selected else None,
            idempotency_key,
        )
        replay = self._decision_by_idempotency(authenticated_scope, idem)
        if replay:
            entity = (
                self.resolver.get_entity(
                    authenticated_scope,
                    str(replay.selected_entity_id),
                    resolve_current=True,
                )
                if replay.selected_entity_id
                else None
            )
            return {
                "entity": entity,
                "resolution_decision": replay,
                "created": False,
                "replayed": True,
            }

        decided_at = utc_now()
        decision_id = f"eres_{idem[:24]}"
        entity = selected or self._build_entity(
            authenticated_scope,
            candidate,
            decision_id,
            evidence,
            decided_at,
            decision_actor.actor_type,
        )
        decision = EntityResolutionDecision(
            entity_resolution_decision_id=decision_id,
            entity_candidate_id=candidate.entity_candidate_id,
            entity_mention_id=None,
            selected_entity_id=entity.entity_id,
            resolution_type=resolution_type,
            resolution_status="completed",
            candidate_entity_ids=[entity.entity_id],
            decision_actor_type=decision_actor.actor_type,
            decision_actor_reference=decision_actor.actor_reference,
            decision_reason=reason or "Explicit entity candidate admission.",
            decision_evidence=[
                {
                    "entity_evidence_id": item.entity_evidence_id,
                    "source_id": item.source_id,
                    "segment_id": item.segment_id,
                }
                for item in evidence
            ],
            entity_resolution_revision=ENTITY_RESOLUTION_REVISION,
            idempotency_digest=idem,
            decided_at=decided_at,
            created_at=decided_at,
        )
        self._persist_admission(
            authenticated_scope,
            candidate,
            entity,
            decision,
            created=selected is None,
            evidence=evidence,
        )
        self._log(
            "entity_admitted",
            authenticated_scope,
            entity_id=entity.entity_id,
            entity_type=entity.canonical_entity_type,
            status="created" if selected is None else "resolved",
        )
        return {
            "entity": entity,
            "resolution_decision": decision,
            "created": selected is None,
            "replayed": False,
        }

    def auto_admit_safe_candidates(
        self, scope: AuthenticatedScope
    ) -> dict[str, Any]:
        actor = AdmissionDecisionActor("engine_policy", SAFE_ENTITY_AUTO_POLICY)
        accepted, skipped, failures = [], [], []
        for candidate in self.candidates.list_candidates(
            scope, status="pending_review"
        ):
            eligible = (
                candidate.epistemic_status == "explicit"
                and candidate.extraction_method == "structured_field"
                and bool(candidate.proposed_external_identifiers)
                and candidate.proposed_entity_type != "unknown"
            )
            if not eligible:
                skipped.append(candidate.entity_candidate_id)
                continue
            try:
                result = self.admit_entity_candidate(
                    scope,
                    candidate.entity_candidate_id,
                    actor,
                    "create_new_entity",
                    reason="Safe automatic admission from explicit structured identifier.",
                    idempotency_key=f"{SAFE_ENTITY_AUTO_POLICY}:{candidate.entity_candidate_id}",
                )
                accepted.append(result["entity"].entity_id)
            except EntityMemoryError as exc:
                failures.append(
                    {
                        "entity_candidate_id": candidate.entity_candidate_id,
                        "code": exc.code,
                    }
                )
        return {
            "policy_id": SAFE_ENTITY_AUTO_POLICY,
            "accepted_entity_ids": accepted,
            "skipped_candidate_ids": skipped,
            "failures": failures,
        }

    def reject_entity_candidate(
        self,
        scope: AuthenticatedScope,
        entity_candidate_id: str,
        actor: AdmissionDecisionActor,
        reason: str,
        *,
        idempotency_key: str | None = None,
    ) -> EntityResolutionDecision:
        return self._non_admission_decision(
            scope,
            entity_candidate_id,
            actor,
            "reject_entity_candidate",
            "rejected",
            reason,
            idempotency_key,
        )

    def defer_entity_candidate(
        self,
        scope: AuthenticatedScope,
        entity_candidate_id: str,
        actor: AdmissionDecisionActor,
        reason: str,
        *,
        idempotency_key: str | None = None,
    ) -> EntityResolutionDecision:
        return self._non_admission_decision(
            scope,
            entity_candidate_id,
            actor,
            "defer_resolution",
            "deferred",
            reason,
            idempotency_key,
        )

    def correct_entity_candidate(
        self,
        scope: AuthenticatedScope,
        entity_candidate_id: str,
        actor: AdmissionDecisionActor,
        *,
        proposed_entity_type: str | None = None,
        proposed_label: str | None = None,
        reason: str,
        idempotency_key: str | None = None,
    ) -> EntityCandidate:
        actor.validate()
        original = self.candidates.get_candidate(scope, entity_candidate_id)
        if original.candidate_status == "accepted":
            raise EntityMemoryError(
                "ENTITY_CANDIDATE_INVALID",
                "Accepted entity candidate cannot be edited in place.",
            )
        identity = {
            "original": original.entity_candidate_id,
            "type": proposed_entity_type or original.proposed_entity_type,
            "label": normalise_label(proposed_label or original.proposed_label),
            "key": idempotency_key or "",
            "revision": ENTITY_CANDIDATE_REVISION,
        }
        fingerprint = sha256_text(canonical_json(identity))
        now = utc_now()
        replacement = replace(
            original,
            entity_candidate_id=f"ecand_{fingerprint[:24]}",
            proposed_entity_type=proposed_entity_type or original.proposed_entity_type,
            proposed_label=proposed_label or original.proposed_label,
            candidate_status="pending_review",
            entity_candidate_fingerprint_sha256=fingerprint,
            normalisation_details={
                **original.normalisation_details,
                "corrected_from_entity_candidate_id": original.entity_candidate_id,
                "correction_reason_hash": sha256_text(reason),
            },
            created_at=now,
            updated_at=now,
        )
        # Correction is append-oriented: preserve the original and insert a new
        # candidate/evidence copy with deterministic IDs.
        evidence = self.candidates.get_evidence(scope, original.entity_candidate_id)
        with self.repository.connect() as connection:
            connection.execute(
                f"INSERT INTO {self.candidates.candidate_table}("
                "entity_candidate_id,extraction_run_id,source_id,client_id,vault_id,"
                "namespace,proposed_entity_type,proposed_label,candidate_status,"
                "entity_candidate_fingerprint_sha256,evidence_manifest_hash_sha256,"
                "entity_candidate_revision,entity_extractor_revision,created_at,updated_at,"
                "payload_json) VALUES(" + ",".join([self.p] * 16) + ")",
                (
                    replacement.entity_candidate_id,
                    replacement.extraction_run_id,
                    replacement.source_id,
                    replacement.client_id,
                    replacement.vault_id,
                    replacement.namespace,
                    replacement.proposed_entity_type,
                    replacement.proposed_label,
                    replacement.candidate_status,
                    replacement.entity_candidate_fingerprint_sha256,
                    replacement.evidence_manifest_hash_sha256,
                    replacement.entity_candidate_revision,
                    replacement.entity_extractor_revision,
                    replacement.created_at,
                    replacement.updated_at,
                    json_value(self.repository, replacement.to_dict()),
                ),
            )
            for index, item in enumerate(evidence):
                copied = replace(
                    item,
                    entity_evidence_id=stable_id(
                        "eevid",
                        {
                            "candidate": replacement.entity_candidate_id,
                            "source": item.source_id,
                            "segment": item.segment_id,
                            "index": index,
                        },
                    ),
                    entity_candidate_id=replacement.entity_candidate_id,
                )
                connection.execute(
                    f"INSERT INTO {self.candidates.evidence_table}("
                    "entity_evidence_id,entity_candidate_id,source_id,segment_id,"
                    "evidence_role,sequence_index,evidence_text_hash_sha256,"
                    "segment_content_hash_sha256,source_content_hash_sha256,created_at,"
                    "payload_json) VALUES(" + ",".join([self.p] * 11) + ")",
                    (
                        copied.entity_evidence_id,
                        copied.entity_candidate_id,
                        copied.source_id,
                        copied.segment_id,
                        copied.evidence_role,
                        copied.sequence_index,
                        copied.evidence_text_hash_sha256,
                        copied.segment_content_hash_sha256,
                        copied.source_content_hash_sha256,
                        copied.created_at,
                        json_value(self.repository, copied.to_dict()),
                    ),
                )
        self.candidates.update_candidate(
            replace(original, candidate_status="corrected", updated_at=now)
        )
        return replacement

    def _build_entity(
        self,
        scope: AuthenticatedScope,
        candidate: EntityCandidate,
        admission_id: str,
        evidence: list[Any],
        decided_at: str,
        decision_actor_type: str,
    ) -> EntityRecord:
        identifiers = sorted(
            candidate.proposed_external_identifiers,
            key=lambda item: (
                item["identifier_namespace"],
                item["identifier_value_digest"],
            ),
        )
        if identifiers:
            primary = identifiers[0]
            identity_payload = {
                "scope": scope.memory_boundary(),
                "entity_type": candidate.proposed_entity_type,
                "identifier_namespace": primary["identifier_namespace"],
                "identifier_digest": primary["identifier_value_digest"],
                "revision": ENTITY_IDENTITY_REVISION,
            }
            basis = "stable_external_identifier"
        else:
            identity_payload = {
                "scope": scope.memory_boundary(),
                "source_id": candidate.source_id,
                "evidence_ids": sorted(item.entity_evidence_id for item in evidence),
                "entity_type": candidate.proposed_entity_type,
                "decision_id": admission_id,
                "revision": ENTITY_IDENTITY_REVISION,
            }
            basis = (
                "manual_internal_confirmation"
                if decision_actor_type != "engine_policy"
                else "unresolved_label_only"
            )
        fingerprint = sha256_text(canonical_json(identity_payload))
        now = utc_now()
        return EntityRecord(
            entity_id=f"ent_{fingerprint[:24]}",
            client_id=scope.client_id,
            vault_id=scope.vault_id,
            namespace=scope.namespace,
            canonical_entity_type=candidate.proposed_entity_type,
            canonical_label=candidate.proposed_label,
            entity_status="active",
            originating_entity_candidate_id=candidate.entity_candidate_id,
            originating_source_id=candidate.source_id,
            originating_admission_id=admission_id,
            identity_fingerprint_sha256=fingerprint,
            identity_basis=basis,
            first_known_at=decided_at,
            first_valid_at=utc(
                self.candidates.ledger.get_source(scope, candidate.source_id).occurred_at,
                default=decided_at,
            ),
            retired_at=None,
            merged_into_entity_id=None,
            entity_schema_revision=ENTITY_MEMORY_SCHEMA_REVISION,
            entity_identity_revision=ENTITY_IDENTITY_REVISION,
            entity_resolution_revision=ENTITY_RESOLUTION_REVISION,
            created_at=now,
            updated_at=now,
        )

    def _persist_admission(
        self,
        scope: AuthenticatedScope,
        candidate: EntityCandidate,
        entity: EntityRecord,
        decision: EntityResolutionDecision,
        *,
        created: bool,
        evidence: list[Any],
    ) -> None:
        with self.repository.connect() as connection:
            if created:
                connection.execute(
                    f"INSERT INTO {self.entity_table}("
                    "entity_id,client_id,vault_id,namespace,canonical_entity_type,"
                    "canonical_label,entity_status,originating_entity_candidate_id,"
                    "originating_source_id,originating_admission_id,"
                    "identity_fingerprint_sha256,identity_basis,first_known_at,first_valid_at,"
                    "retired_at,merged_into_entity_id,entity_schema_revision,created_at,"
                    "updated_at,payload_json) VALUES(" + ",".join([self.p] * 20) + ")",
                    (
                        entity.entity_id,
                        *scope_params(scope),
                        entity.canonical_entity_type,
                        entity.canonical_label,
                        entity.entity_status,
                        entity.originating_entity_candidate_id,
                        entity.originating_source_id,
                        entity.originating_admission_id,
                        entity.identity_fingerprint_sha256,
                        entity.identity_basis,
                        entity.first_known_at,
                        entity.first_valid_at,
                        entity.retired_at,
                        entity.merged_into_entity_id,
                        entity.entity_schema_revision,
                        entity.created_at,
                        entity.updated_at,
                        json_value(self.repository, entity.to_dict()),
                    ),
                )
                for identifier in candidate.proposed_external_identifiers:
                    record = EntityIdentifier(
                        entity_identifier_id=stable_id(
                            "eid",
                            {
                                "scope": scope.memory_boundary(),
                                "entity": entity.entity_id,
                                "namespace": identifier["identifier_namespace"],
                                "digest": identifier["identifier_value_digest"],
                                "revision": ENTITY_IDENTITY_REVISION,
                            },
                        ),
                        entity_id=entity.entity_id,
                        identifier_namespace=identifier["identifier_namespace"],
                        identifier_value_digest=identifier["identifier_value_digest"],
                        identifier_display_hint=identifier.get(
                            "identifier_display_hint"
                        ),
                        identifier_type=identifier["identifier_type"],
                        source_id=candidate.source_id,
                        segment_id=evidence[0].segment_id if evidence else None,
                        epistemic_status=candidate.epistemic_status,
                        valid_from=entity.first_valid_at,
                        valid_until=None,
                        system_known_from=decision.decided_at,
                        system_known_until=None,
                        identifier_status="active",
                        entity_identity_revision=ENTITY_IDENTITY_REVISION,
                        created_at=decision.created_at,
                    )
                    connection.execute(
                        f"INSERT INTO {self.identifier_table}("
                        "entity_identifier_id,entity_id,client_id,vault_id,namespace,"
                        "identifier_namespace,identifier_value_digest,identifier_type,"
                        "source_id,valid_from,valid_until,system_known_from,"
                        "system_known_until,identifier_status,created_at,payload_json"
                        ") VALUES(" + ",".join([self.p] * 16) + ")",
                        (
                            record.entity_identifier_id,
                            record.entity_id,
                            *scope_params(scope),
                            record.identifier_namespace,
                            record.identifier_value_digest,
                            record.identifier_type,
                            record.source_id,
                            record.valid_from,
                            record.valid_until,
                            record.system_known_from,
                            record.system_known_until,
                            record.identifier_status,
                            record.created_at,
                            json_value(self.repository, record.to_dict()),
                        ),
                    )
            connection.execute(
                f"INSERT INTO {self.resolution_table}("
                "entity_resolution_decision_id,entity_candidate_id,entity_mention_id,"
                "selected_entity_id,client_id,vault_id,namespace,resolution_type,"
                "resolution_status,idempotency_digest,decided_at,created_at,payload_json"
                ") VALUES(" + ",".join([self.p] * 13) + ")",
                (
                    decision.entity_resolution_decision_id,
                    decision.entity_candidate_id,
                    decision.entity_mention_id,
                    decision.selected_entity_id,
                    *scope_params(scope),
                    decision.resolution_type,
                    decision.resolution_status,
                    decision.idempotency_digest,
                    decision.decided_at,
                    decision.created_at,
                    json_value(self.repository, decision.to_dict()),
                ),
            )
        updated = replace(
            candidate, candidate_status="accepted", updated_at=utc_now()
        )
        self.candidates.update_candidate(updated)
        for mention in self.candidates.get_mentions(
            scope, candidate_id=candidate.entity_candidate_id
        ):
            self.candidates.update_mention(
                replace(
                    mention,
                    entity_id=entity.entity_id,
                    resolution_status="resolved",
                    resolution_decision_id=decision.entity_resolution_decision_id,
                )
            )
        for alias_value in candidate.proposed_aliases:
            self._persist_candidate_alias(
                scope, entity, candidate, decision, alias_value, evidence
            )

    def _persist_candidate_alias(
        self,
        scope: AuthenticatedScope,
        entity: EntityRecord,
        candidate: EntityCandidate,
        decision: EntityResolutionDecision,
        alias_value: str,
        evidence: list[Any],
    ) -> None:
        normalised = normalise_label(alias_value)
        if not normalised or normalised == normalise_label(entity.canonical_label):
            return
        idem = sha256_text(
            canonical_json(
                {
                    "scope": scope.memory_boundary(),
                    "entity": entity.entity_id,
                    "alias": normalised,
                    "candidate": candidate.entity_candidate_id,
                    "revision": ENTITY_ALIAS_REVISION,
                }
            )
        )
        alias = EntityAliasAssertion(
            alias_assertion_id=f"alias_{idem[:24]}",
            entity_id=entity.entity_id,
            alias_value=alias_value,
            alias_normalised=normalised,
            alias_hash_sha256=sha256_text(normalised),
            source_id=candidate.source_id,
            segment_id=evidence[0].segment_id if evidence else None,
            evidence_manifest_hash_sha256=candidate.evidence_manifest_hash_sha256,
            epistemic_status=candidate.epistemic_status,
            assertion_actor_type=decision.decision_actor_type,
            assertion_actor_reference=decision.decision_actor_reference,
            assertion_reason="Explicit alias from admitted entity candidate.",
            valid_from=entity.first_valid_at,
            valid_until=None,
            system_effective_at=decision.decided_at,
            alias_status="active",
            entity_alias_revision=ENTITY_ALIAS_REVISION,
            idempotency_digest=idem,
            created_at=decision.created_at,
        )
        try:
            with self.repository.connect() as connection:
                connection.execute(
                    f"INSERT INTO {self.alias_table}("
                    "alias_assertion_id,entity_id,client_id,vault_id,namespace,"
                    "alias_normalised,alias_hash_sha256,source_id,valid_from,valid_until,"
                    "system_effective_at,alias_status,idempotency_digest,created_at,"
                    "payload_json) VALUES(" + ",".join([self.p] * 15) + ")",
                    (
                        alias.alias_assertion_id,
                        alias.entity_id,
                        *scope_params(scope),
                        alias.alias_normalised,
                        alias.alias_hash_sha256,
                        alias.source_id,
                        alias.valid_from,
                        alias.valid_until,
                        alias.system_effective_at,
                        alias.alias_status,
                        alias.idempotency_digest,
                        alias.created_at,
                        json_value(self.repository, alias.to_dict()),
                    ),
                )
        except Exception as exc:
            if "unique" not in str(exc).lower():
                raise

    def _non_admission_decision(
        self,
        scope: AuthenticatedScope,
        candidate_id: str,
        actor: AdmissionDecisionActor,
        resolution_type: str,
        status: str,
        reason: str,
        idempotency_key: str | None,
    ) -> EntityResolutionDecision:
        actor.validate()
        candidate = self.candidates.get_candidate(scope, candidate_id)
        idem = self._decision_digest(
            scope, candidate_id, resolution_type, None, idempotency_key
        )
        replay = self._decision_by_idempotency(scope, idem)
        if replay:
            return replay
        now = utc_now()
        decision = EntityResolutionDecision(
            entity_resolution_decision_id=f"eres_{idem[:24]}",
            entity_candidate_id=candidate_id,
            entity_mention_id=None,
            selected_entity_id=None,
            resolution_type=resolution_type,
            resolution_status="completed",
            candidate_entity_ids=[],
            decision_actor_type=actor.actor_type,
            decision_actor_reference=actor.actor_reference,
            decision_reason=reason,
            decision_evidence=[],
            entity_resolution_revision=ENTITY_RESOLUTION_REVISION,
            idempotency_digest=idem,
            decided_at=now,
            created_at=now,
        )
        with self.repository.connect() as connection:
            connection.execute(
                f"INSERT INTO {self.resolution_table}("
                "entity_resolution_decision_id,entity_candidate_id,entity_mention_id,"
                "selected_entity_id,client_id,vault_id,namespace,resolution_type,"
                "resolution_status,idempotency_digest,decided_at,created_at,payload_json"
                ") VALUES(" + ",".join([self.p] * 13) + ")",
                (
                    decision.entity_resolution_decision_id,
                    decision.entity_candidate_id,
                    None,
                    None,
                    *scope_params(scope),
                    decision.resolution_type,
                    decision.resolution_status,
                    decision.idempotency_digest,
                    decision.decided_at,
                    decision.created_at,
                    json_value(self.repository, decision.to_dict()),
                ),
            )
        self.candidates.update_candidate(
            replace(candidate, candidate_status=status, updated_at=now)
        )
        return decision

    def _resolve_candidate_identifier(
        self, scope: AuthenticatedScope, candidate: EntityCandidate
    ) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        for item in candidate.proposed_external_identifiers:
            with self.repository.connect() as connection:
                rows = connection.execute(
                    f"SELECT payload_json FROM {self.identifier_table} "
                    f"WHERE client_id={self.p} AND vault_id={self.p} "
                    f"AND namespace={self.p} AND identifier_namespace={self.p} "
                    f"AND identifier_value_digest={self.p} AND identifier_status={self.p}",
                    (
                        *scope_params(scope),
                        item["identifier_namespace"],
                        item["identifier_value_digest"],
                        "active",
                    ),
                ).fetchall()
            for row in rows:
                identifier = payload_from_row(row)
                entity = self.resolver.get_entity(scope, identifier["entity_id"])
                if not self.resolver.types_compatible(
                    entity.canonical_entity_type, candidate.proposed_entity_type
                ):
                    return {
                        "resolution_status": "conflict",
                        "basis": "type_conflict",
                    }
                results.append(
                    {
                        "resolution_status": "resolved",
                        "entity_id": self.resolver.resolve_canonical_entity_id(
                            scope, entity.entity_id
                        ),
                    }
                )
        ids = sorted(
            {
                str(item["entity_id"])
                for item in results
                if item.get("entity_id")
            }
        )
        if len(ids) == 1:
            return {"resolution_status": "resolved", "entity_id": ids[0]}
        if len(ids) > 1:
            return {"resolution_status": "ambiguous", "candidate_entity_ids": ids}
        return {"resolution_status": "unresolved", "entity_id": None}

    def _accepted_result(
        self, scope: AuthenticatedScope, candidate: EntityCandidate
    ) -> dict[str, Any]:
        with self.repository.connect() as connection:
            row = connection.execute(
                f"SELECT payload_json FROM {self.resolution_table} "
                f"WHERE entity_candidate_id={self.p} AND client_id={self.p} "
                f"AND vault_id={self.p} AND namespace={self.p} "
                f"ORDER BY decided_at DESC LIMIT 1",
                (candidate.entity_candidate_id, *scope_params(scope)),
            ).fetchone()
        if not row:
            raise EntityMemoryError(
                "ENTITY_INTEGRITY_FAILED",
                "Accepted candidate has no resolution decision.",
            )
        decision = EntityResolutionDecision(**payload_from_row(row))
        entity = self.resolver.get_entity(
            scope, str(decision.selected_entity_id), resolve_current=True
        )
        return {
            "entity": entity,
            "resolution_decision": decision,
            "created": False,
            "replayed": True,
        }

    def _decision_by_idempotency(
        self, scope: AuthenticatedScope, digest: str
    ) -> EntityResolutionDecision | None:
        with self.repository.connect() as connection:
            row = connection.execute(
                f"SELECT payload_json FROM {self.resolution_table} "
                f"WHERE client_id={self.p} AND vault_id={self.p} "
                f"AND namespace={self.p} AND idempotency_digest={self.p}",
                (*scope_params(scope), digest),
            ).fetchone()
        return EntityResolutionDecision(**payload_from_row(row)) if row else None

    @staticmethod
    def _decision_digest(
        scope: AuthenticatedScope,
        candidate_id: str,
        resolution_type: str,
        selected_entity_id: str | None,
        idempotency_key: str | None,
    ) -> str:
        return sha256_text(
            canonical_json(
                {
                    "scope": scope.memory_boundary(),
                    "candidate_id": candidate_id,
                    "resolution_type": resolution_type,
                    "selected_entity_id": selected_entity_id,
                    "key": idempotency_key or "",
                    "revision": ENTITY_ADMISSION_REVISION,
                }
            )
        )

    @staticmethod
    def _log(event: str, scope: AuthenticatedScope, **fields: Any) -> None:
        allowed = {"entity_id", "entity_type", "status"}
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


__all__ = ["EntityAdmissionService", "SAFE_ENTITY_AUTO_POLICY"]
