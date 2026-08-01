"""Durable evidence-backed relationship candidate extraction."""

from __future__ import annotations

import json
import logging
from typing import Any

from .entity_candidates import EntityCandidateEngine
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
    utc_now,
)
from .relationship_models import (
    RELATIONSHIP_CANDIDATE_REVISION,
    RELATIONSHIP_EXTRACTOR_REVISION,
    RelationshipCandidate,
    RelationshipEvidence,
    RelationshipMemoryError,
)
from .relationship_rules import ExtractedRelationship, extract_relationships
from .source_integrity import canonical_json, sha256_text
from .source_ledger import SourceLedger
from .source_models import AuthenticatedScope, SourceSegment


LOGGER = logging.getLogger("prmr.core.relationship_candidates")


class RelationshipCandidateEngine:
    def __init__(self, repository: Any, *, initialize: bool = True) -> None:
        self.repository = repository
        self.ledger = SourceLedger(repository, initialize=initialize)
        if initialize:
            initialize_entity_relationship_schema(repository)
        self.entities = EntityCandidateEngine(repository, initialize=False)
        self.resolver = EntityResolver(repository, initialize=False)
        self.candidate_table = table(repository, "prmr_relationship_candidates")
        self.evidence_table = table(repository, "prmr_relationship_evidence")
        self.p = placeholder(repository)

    def extract_source_relationships(
        self, scope: AuthenticatedScope, source_id: str
    ) -> list[RelationshipCandidate]:
        source = self.ledger.get_source(scope, source_id)
        if not self.ledger.verify_source_integrity(scope, source_id).verified:
            raise RelationshipMemoryError(
                "RELATIONSHIP_EVIDENCE_INVALID", "Source integrity failed."
            )
        segments = self._segments(scope, source_id)
        results: list[RelationshipCandidate] = []
        for extracted in extract_relationships(source.sanitised_payload, source.source_type):
            candidate, evidence = self._materialise(
                scope, source, segments, extracted
            )
            existing = self._by_fingerprint(
                scope, candidate.relationship_candidate_fingerprint_sha256
            )
            if existing:
                results.append(existing)
                continue
            self._persist(candidate, evidence)
            results.append(candidate)
            self._log(
                "relationship_candidate_created",
                scope,
                relationship_candidate_id=candidate.relationship_candidate_id,
                relationship_type=candidate.proposed_relationship_type,
                status=candidate.candidate_status,
            )
        return results

    def get_candidate(
        self, scope: AuthenticatedScope, candidate_id: str
    ) -> RelationshipCandidate:
        with self.repository.connect() as connection:
            row = connection.execute(
                f"SELECT payload_json FROM {self.candidate_table} "
                f"WHERE relationship_candidate_id={self.p} AND client_id={self.p} "
                f"AND vault_id={self.p} AND namespace={self.p}",
                (candidate_id, *scope_params(scope)),
            ).fetchone()
        if not row:
            raise RelationshipMemoryError(
                "RELATIONSHIP_CANDIDATE_NOT_FOUND",
                "Relationship candidate was not found in authenticated scope.",
            )
        return RelationshipCandidate(**payload_from_row(row))

    def list_candidates(
        self, scope: AuthenticatedScope, *, status: str | None = None
    ) -> list[RelationshipCandidate]:
        extra, params = "", ()
        if status:
            extra, params = f" AND candidate_status={self.p}", (status,)
        with self.repository.connect() as connection:
            rows = connection.execute(
                f"SELECT payload_json FROM {self.candidate_table} "
                f"WHERE client_id={self.p} AND vault_id={self.p} AND namespace={self.p}"
                f"{extra} ORDER BY created_at,relationship_candidate_id",
                (*scope_params(scope), *params),
            ).fetchall()
        return [RelationshipCandidate(**payload_from_row(row)) for row in rows]

    def get_evidence(
        self, scope: AuthenticatedScope, candidate_id: str
    ) -> list[RelationshipEvidence]:
        self.get_candidate(scope, candidate_id)
        with self.repository.connect() as connection:
            rows = connection.execute(
                f"SELECT payload_json FROM {self.evidence_table} "
                f"WHERE relationship_candidate_id={self.p} ORDER BY sequence_index",
                (candidate_id,),
            ).fetchall()
        return [RelationshipEvidence(**payload_from_row(row)) for row in rows]

    def update_candidate(self, candidate: RelationshipCandidate) -> None:
        with self.repository.connect() as connection:
            connection.execute(
                f"UPDATE {self.candidate_table} SET candidate_status={self.p},"
                f"updated_at={self.p},payload_json={self.p} "
                f"WHERE relationship_candidate_id={self.p}",
                (
                    candidate.candidate_status,
                    candidate.updated_at,
                    json_value(self.repository, candidate.to_dict()),
                    candidate.relationship_candidate_id,
                ),
            )

    def _materialise(
        self,
        scope: AuthenticatedScope,
        source: Any,
        segments: list[SourceSegment],
        extracted: ExtractedRelationship,
    ) -> tuple[RelationshipCandidate, RelationshipEvidence]:
        subject = self._resolve_reference(scope, extracted.subject_reference)
        object_ = self._resolve_reference(scope, extracted.object_reference)
        segment = self._segment(segments, extracted)
        identity = {
            "scope": scope.memory_boundary(),
            "source_id": source.source_id,
            "subject_reference_hash": sha256_text(extracted.subject_reference),
            "subject_entity_id": subject.get("entity_id"),
            "relationship_type": extracted.relationship_type,
            "object_reference_hash": sha256_text(extracted.object_reference),
            "object_entity_id": object_.get("entity_id"),
            "valid_from": extracted.proposed_valid_from,
            "rule": extracted.primary_rule_id,
            "revision": RELATIONSHIP_CANDIDATE_REVISION,
        }
        fingerprint = sha256_text(canonical_json(identity))
        candidate_id = f"rcand_{fingerprint[:24]}"
        evidence_identity = {
            "candidate_id": candidate_id,
            "source_id": source.source_id,
            "segment_id": segment.segment_id,
            "segment_hash": segment.content_hash_sha256,
            "rule": extracted.primary_rule_id,
        }
        evidence_manifest = sha256_text(canonical_json([evidence_identity]))
        now = utc_now()
        candidate = RelationshipCandidate(
            relationship_candidate_id=candidate_id,
            extraction_run_id=stable_id(
                "rrun",
                {
                    "source_id": source.source_id,
                    "revision": RELATIONSHIP_EXTRACTOR_REVISION,
                },
            ),
            source_id=source.source_id,
            client_id=scope.client_id,
            vault_id=scope.vault_id,
            namespace=scope.namespace,
            subject_entity_candidate_id=None,
            subject_entity_id=subject.get("entity_id"),
            object_entity_candidate_id=None,
            object_entity_id=object_.get("entity_id"),
            proposed_relationship_type=extracted.relationship_type,
            proposed_valid_from=extracted.proposed_valid_from,
            proposed_valid_until=extracted.proposed_valid_until,
            epistemic_status=extracted.epistemic_status,
            extraction_confidence=extracted.extraction_confidence,
            extraction_method=extracted.extraction_method,
            primary_rule_id=extracted.primary_rule_id,
            matched_rule_ids=extracted.matched_rule_ids,
            candidate_status="pending_review",
            relationship_candidate_fingerprint_sha256=fingerprint,
            evidence_manifest_hash_sha256=evidence_manifest,
            normalisation_details={
                "subject_resolution": subject,
                "object_resolution": object_,
                "subject_reference_hash": sha256_text(extracted.subject_reference),
                "object_reference_hash": sha256_text(extracted.object_reference),
                "quoted_claim": extracted.quoted_claim,
                "future_or_planned": extracted.future_or_planned,
                "negation_checked": True,
            },
            relationship_candidate_revision=RELATIONSHIP_CANDIDATE_REVISION,
            relationship_extractor_revision=RELATIONSHIP_EXTRACTOR_REVISION,
            created_at=now,
            updated_at=now,
        )
        evidence = RelationshipEvidence(
            relationship_evidence_id=stable_id("revid", evidence_identity),
            relationship_candidate_id=candidate_id,
            source_id=source.source_id,
            segment_id=segment.segment_id,
            evidence_role="primary",
            sequence_index=0,
            source_start_offset=segment.start_offset,
            source_end_offset=segment.end_offset,
            segment_start_offset=0,
            segment_end_offset=len(segment.content),
            json_pointer=extracted.json_pointer or segment.json_pointer,
            evidence_text_hash_sha256=sha256_text(segment.content),
            segment_content_hash_sha256=segment.content_hash_sha256,
            subject_entity_evidence_id=None,
            object_entity_evidence_id=None,
            extraction_rule_id=extracted.primary_rule_id,
            created_at=now,
        )
        return candidate, evidence

    def _resolve_reference(
        self, scope: AuthenticatedScope, reference: str
    ) -> dict[str, Any]:
        if reference.startswith("ent_"):
            try:
                entity = self.resolver.get_entity(scope, reference, resolve_current=True)
                return {
                    "resolution_status": "resolved",
                    "entity_id": entity.entity_id,
                    "basis": "canonical_entity_id",
                }
            except Exception:
                pass
        for namespace in (
            "entity",
            "external",
            "actor",
            "user",
            "account",
            "project",
            "device",
            "character",
            "organisation",
            "document",
            "software_system",
        ):
            result = self.resolver.resolve_identifier(scope, namespace, reference)
            if result["resolution_status"] == "resolved":
                return result
            if result["resolution_status"] in {"ambiguous", "conflict"}:
                return result
        return self.resolver.resolve_alias_or_label(scope, reference)

    def _persist(
        self, candidate: RelationshipCandidate, evidence: RelationshipEvidence
    ) -> None:
        with self.repository.connect() as connection:
            connection.execute(
                f"INSERT INTO {self.candidate_table}("
                "relationship_candidate_id,extraction_run_id,source_id,client_id,"
                "vault_id,namespace,subject_entity_id,object_entity_id,"
                "proposed_relationship_type,candidate_status,"
                "relationship_candidate_fingerprint_sha256,"
                "evidence_manifest_hash_sha256,relationship_candidate_revision,"
                "created_at,updated_at,payload_json) VALUES("
                + ",".join([self.p] * 16)
                + ")",
                (
                    candidate.relationship_candidate_id,
                    candidate.extraction_run_id,
                    candidate.source_id,
                    candidate.client_id,
                    candidate.vault_id,
                    candidate.namespace,
                    candidate.subject_entity_id,
                    candidate.object_entity_id,
                    candidate.proposed_relationship_type,
                    candidate.candidate_status,
                    candidate.relationship_candidate_fingerprint_sha256,
                    candidate.evidence_manifest_hash_sha256,
                    candidate.relationship_candidate_revision,
                    candidate.created_at,
                    candidate.updated_at,
                    json_value(self.repository, candidate.to_dict()),
                ),
            )
            connection.execute(
                f"INSERT INTO {self.evidence_table}("
                "relationship_evidence_id,relationship_candidate_id,source_id,"
                "segment_id,evidence_role,sequence_index,evidence_text_hash_sha256,"
                "segment_content_hash_sha256,created_at,payload_json) VALUES("
                + ",".join([self.p] * 10)
                + ")",
                (
                    evidence.relationship_evidence_id,
                    evidence.relationship_candidate_id,
                    evidence.source_id,
                    evidence.segment_id,
                    evidence.evidence_role,
                    evidence.sequence_index,
                    evidence.evidence_text_hash_sha256,
                    evidence.segment_content_hash_sha256,
                    evidence.created_at,
                    json_value(self.repository, evidence.to_dict()),
                ),
            )

    def _by_fingerprint(
        self, scope: AuthenticatedScope, fingerprint: str
    ) -> RelationshipCandidate | None:
        with self.repository.connect() as connection:
            row = connection.execute(
                f"SELECT payload_json FROM {self.candidate_table} "
                f"WHERE client_id={self.p} AND vault_id={self.p} AND namespace={self.p} "
                f"AND relationship_candidate_fingerprint_sha256={self.p}",
                (*scope_params(scope), fingerprint),
            ).fetchone()
        return RelationshipCandidate(**payload_from_row(row)) if row else None

    def _segments(
        self, scope: AuthenticatedScope, source_id: str
    ) -> list[SourceSegment]:
        items: list[SourceSegment] = []
        cursor = None
        while True:
            page = self.ledger.list_source_segments(scope, source_id, cursor, 1000)
            items.extend(page.items)
            if page.next_cursor is None:
                return items
            cursor = page.next_cursor

    @staticmethod
    def _segment(
        segments: list[SourceSegment], extracted: ExtractedRelationship
    ) -> SourceSegment:
        if extracted.json_pointer:
            match = next(
                (
                    segment
                    for segment in segments
                    if segment.json_pointer
                    and extracted.json_pointer.startswith(segment.json_pointer)
                ),
                None,
            )
            if match:
                return match
        for segment in segments:
            if (
                normalise_label(extracted.subject_reference)
                in normalise_label(segment.content)
                and normalise_label(extracted.object_reference)
                in normalise_label(segment.content)
            ):
                return segment
        if not segments:
            raise RelationshipMemoryError(
                "RELATIONSHIP_EVIDENCE_INVALID",
                "Relationship candidate has no source segment.",
            )
        return segments[0]

    @staticmethod
    def _log(event: str, scope: AuthenticatedScope, **fields: Any) -> None:
        allowed = {"relationship_candidate_id", "relationship_type", "status"}
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


__all__ = ["RelationshipCandidateEngine"]
