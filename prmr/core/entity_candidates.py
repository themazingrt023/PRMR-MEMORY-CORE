"""Durable evidence-backed entity candidate extraction."""

from __future__ import annotations

from dataclasses import replace
import json
import logging
import time
from typing import Any

from .entity_extraction_rules import ExtractedEntity, extract_entities
from .entity_models import (
    ENTITY_CANDIDATE_REVISION,
    ENTITY_EXTRACTOR_REVISION,
    ENTITY_MENTION_REVISION,
    ENTITY_RESOLUTION_REVISION,
    EntityCandidate,
    EntityEvidence,
    EntityMemoryError,
    EntityMention,
)
from .entity_store import (
    digest_identifier,
    initialize_entity_relationship_schema,
    json_value,
    normalise_label,
    payload_from_row,
    placeholder,
    safe_display,
    scope_fingerprint,
    scope_params,
    stable_id,
    table,
    utc_now,
)
from .source_integrity import canonical_json, sha256_text
from .source_ledger import SourceLedger
from .source_models import AuthenticatedScope, SourceSegment


LOGGER = logging.getLogger("prmr.core.entity_candidates")


class EntityCandidateEngine:
    def __init__(self, repository: Any, *, initialize: bool = True) -> None:
        self.repository = repository
        self.ledger = SourceLedger(repository, initialize=initialize)
        if initialize:
            initialize_entity_relationship_schema(repository)
        self.candidate_table = table(repository, "prmr_entity_candidates")
        self.evidence_table = table(repository, "prmr_entity_evidence")
        self.mention_table = table(repository, "prmr_entity_mentions")
        self.p = placeholder(repository)

    def extract_source_entities(
        self, authenticated_scope: AuthenticatedScope, source_id: str
    ) -> list[EntityCandidate]:
        started = time.perf_counter()
        source = self.ledger.get_source(authenticated_scope, source_id)
        integrity = self.ledger.verify_source_integrity(authenticated_scope, source_id)
        if not integrity.verified:
            raise EntityMemoryError(
                "ENTITY_EVIDENCE_INVALID", "Source integrity verification failed."
            )
        segments = self._all_segments(authenticated_scope, source_id)
        extracted = extract_entities(source.sanitised_payload, source.source_type)
        candidates: list[EntityCandidate] = []
        pending: list[tuple[EntityCandidate, EntityEvidence, EntityMention]] = []
        existing_by_fingerprint = self._candidates_by_fingerprint(
            authenticated_scope
        )
        for item in extracted:
            candidate, evidence, mention = self._materialise(
                authenticated_scope, source, segments, item
            )
            existing = existing_by_fingerprint.get(
                candidate.entity_candidate_fingerprint_sha256
            )
            if existing:
                candidates.append(existing)
                continue
            pending.append((candidate, evidence, mention))
            candidates.append(candidate)
            existing_by_fingerprint[
                candidate.entity_candidate_fingerprint_sha256
            ] = candidate
        if pending:
            self._persist_many(pending)
        for candidate, _, _ in pending:
            self._safe_log(
                "entity_candidate_created",
                authenticated_scope,
                entity_candidate_id=candidate.entity_candidate_id,
                entity_type=candidate.proposed_entity_type,
                status=candidate.candidate_status,
                duration_ms=round((time.perf_counter() - started) * 1000, 3),
            )
        return candidates

    def get_candidate(
        self, scope: AuthenticatedScope, entity_candidate_id: str
    ) -> EntityCandidate:
        with self.repository.connect() as connection:
            row = connection.execute(
                f"SELECT payload_json FROM {self.candidate_table} "
                f"WHERE entity_candidate_id={self.p} AND client_id={self.p} "
                f"AND vault_id={self.p} AND namespace={self.p}",
                (entity_candidate_id, *scope_params(scope)),
            ).fetchone()
        if not row:
            raise EntityMemoryError(
                "ENTITY_CANDIDATE_NOT_FOUND",
                "Entity candidate was not found in authenticated scope.",
            )
        return EntityCandidate(**payload_from_row(row))

    def list_candidates(
        self, scope: AuthenticatedScope, *, status: str | None = None
    ) -> list[EntityCandidate]:
        where = ""
        params: tuple[Any, ...] = ()
        if status:
            where = f" AND candidate_status={self.p}"
            params = (status,)
        with self.repository.connect() as connection:
            rows = connection.execute(
                f"SELECT payload_json FROM {self.candidate_table} "
                f"WHERE client_id={self.p} AND vault_id={self.p} AND namespace={self.p}"
                f"{where} ORDER BY created_at,entity_candidate_id",
                (*scope_params(scope), *params),
            ).fetchall()
        return [EntityCandidate(**payload_from_row(row)) for row in rows]

    def get_evidence(
        self, scope: AuthenticatedScope, entity_candidate_id: str
    ) -> list[EntityEvidence]:
        self.get_candidate(scope, entity_candidate_id)
        with self.repository.connect() as connection:
            rows = connection.execute(
                f"SELECT payload_json FROM {self.evidence_table} "
                f"WHERE entity_candidate_id={self.p} ORDER BY sequence_index",
                (entity_candidate_id,),
            ).fetchall()
        return [EntityEvidence(**payload_from_row(row)) for row in rows]

    def get_mentions(
        self, scope: AuthenticatedScope, *, candidate_id: str | None = None
    ) -> list[EntityMention]:
        extra, params = "", ()
        if candidate_id:
            extra, params = f" AND entity_candidate_id={self.p}", (candidate_id,)
        with self.repository.connect() as connection:
            rows = connection.execute(
                f"SELECT payload_json FROM {self.mention_table} "
                f"WHERE client_id={self.p} AND vault_id={self.p} AND namespace={self.p}"
                f"{extra} ORDER BY created_at,entity_mention_id",
                (*scope_params(scope), *params),
            ).fetchall()
        return [EntityMention(**payload_from_row(row)) for row in rows]

    def update_candidate(self, candidate: EntityCandidate) -> None:
        with self.repository.connect() as connection:
            connection.execute(
                f"UPDATE {self.candidate_table} SET candidate_status={self.p},"
                f"updated_at={self.p},payload_json={self.p} "
                f"WHERE entity_candidate_id={self.p}",
                (
                    candidate.candidate_status,
                    candidate.updated_at,
                    json_value(self.repository, candidate.to_dict()),
                    candidate.entity_candidate_id,
                ),
            )

    def update_mention(self, mention: EntityMention) -> None:
        with self.repository.connect() as connection:
            connection.execute(
                f"UPDATE {self.mention_table} SET entity_id={self.p},"
                f"resolution_status={self.p},payload_json={self.p} "
                f"WHERE entity_mention_id={self.p}",
                (
                    mention.entity_id,
                    mention.resolution_status,
                    json_value(self.repository, mention.to_dict()),
                    mention.entity_mention_id,
                ),
            )

    def _materialise(
        self,
        scope: AuthenticatedScope,
        source: Any,
        segments: list[SourceSegment],
        item: ExtractedEntity,
    ) -> tuple[EntityCandidate, EntityEvidence, EntityMention]:
        segment = self._evidence_segment(segments, item)
        identifiers = [
            {
                "identifier_namespace": namespace,
                "identifier_value_digest": digest_identifier(namespace, raw),
                "identifier_display_hint": self._identifier_hint(raw),
                "identifier_type": identifier_type,
            }
            for namespace, raw, identifier_type in item.identifiers
            if namespace not in {"client", "vault", "namespace", "api_key", "token"}
        ]
        normalisation = {
            "normalised_label": normalise_label(item.label),
            "identifier_count": len(identifiers),
            "alias_count": len(item.aliases),
            "label_only": bool(item.label and not identifiers),
            "scope_fields_ignored": True,
        }
        candidate_identity = {
            "scope": scope.memory_boundary(),
            "source_id": source.source_id,
            "entity_type": item.entity_type,
            "label": normalisation["normalised_label"],
            "identifiers": identifiers,
            "aliases": sorted(normalise_label(alias) for alias in item.aliases),
            "rule": item.primary_rule_id,
            "json_pointer": item.json_pointer,
            "revision": ENTITY_CANDIDATE_REVISION,
        }
        fingerprint = sha256_text(canonical_json(candidate_identity))
        candidate_id = f"ecand_{fingerprint[:24]}"
        evidence_identity = {
            "candidate_id": candidate_id,
            "source_id": source.source_id,
            "segment_id": segment.segment_id,
            "segment_hash": segment.content_hash_sha256,
            "rule": item.primary_rule_id,
        }
        evidence_manifest = sha256_text(canonical_json([evidence_identity]))
        now = utc_now()
        candidate = EntityCandidate(
            entity_candidate_id=candidate_id,
            extraction_run_id=stable_id(
                "erun", {"source_id": source.source_id, "revision": ENTITY_EXTRACTOR_REVISION}
            ),
            source_id=source.source_id,
            client_id=scope.client_id,
            vault_id=scope.vault_id,
            namespace=scope.namespace,
            application_reference=source.application_reference,
            actor_reference=source.actor_reference,
            workspace_reference=source.workspace_reference,
            session_reference=source.session_reference,
            proposed_entity_type=item.entity_type,
            proposed_label=item.label,
            proposed_external_identifiers=identifiers,
            proposed_aliases=sorted(set(item.aliases)),
            epistemic_status=item.epistemic_status,
            extraction_confidence=item.extraction_confidence,
            confidence_basis=item.confidence_basis,
            extraction_method=item.extraction_method,
            primary_rule_id=item.primary_rule_id,
            matched_rule_ids=item.matched_rule_ids or [item.primary_rule_id],
            candidate_status="pending_review",
            entity_candidate_fingerprint_sha256=fingerprint,
            evidence_manifest_hash_sha256=evidence_manifest,
            normalisation_details=normalisation,
            entity_candidate_revision=ENTITY_CANDIDATE_REVISION,
            entity_extractor_revision=ENTITY_EXTRACTOR_REVISION,
            entity_resolution_revision=ENTITY_RESOLUTION_REVISION,
            created_at=now,
            updated_at=now,
        )
        evidence = EntityEvidence(
            entity_evidence_id=stable_id("eevid", evidence_identity),
            entity_candidate_id=candidate_id,
            source_id=source.source_id,
            segment_id=segment.segment_id,
            evidence_role="primary",
            sequence_index=0,
            source_start_offset=segment.start_offset,
            source_end_offset=segment.end_offset,
            segment_start_offset=0,
            segment_end_offset=len(segment.content),
            start_line=segment.start_line,
            end_line=segment.end_line,
            json_pointer=item.json_pointer or segment.json_pointer,
            evidence_text_hash_sha256=sha256_text(segment.content),
            segment_content_hash_sha256=segment.content_hash_sha256,
            source_content_hash_sha256=source.content_hash_sha256,
            extraction_rule_id=item.primary_rule_id,
            created_at=now,
        )
        display = safe_display(item.label or item.source_text or "unlabelled entity")
        mention = EntityMention(
            entity_mention_id=stable_id(
                "ement",
                {
                    "candidate_id": candidate_id,
                    "segment_id": segment.segment_id,
                    "role": item.mention_role,
                    "pointer": item.json_pointer,
                },
            ),
            entity_id=None,
            entity_candidate_id=candidate_id,
            source_id=source.source_id,
            segment_id=segment.segment_id,
            client_id=scope.client_id,
            vault_id=scope.vault_id,
            namespace=scope.namespace,
            mention_text_hash_sha256=sha256_text(display),
            safe_display_text=display,
            mention_start_offset=segment.start_offset,
            mention_end_offset=segment.end_offset,
            json_pointer=item.json_pointer or segment.json_pointer,
            speaker=item.speaker,
            occurred_at=item.occurred_at or segment.occurred_at or source.occurred_at,
            mention_role=item.mention_role,
            epistemic_status=item.epistemic_status,
            resolution_status="unresolved",
            resolution_decision_id=None,
            entity_mention_revision=ENTITY_MENTION_REVISION,
            created_at=now,
        )
        return candidate, evidence, mention

    def _persist(
        self,
        candidate: EntityCandidate,
        evidence: EntityEvidence,
        mention: EntityMention,
    ) -> None:
        self._persist_many([(candidate, evidence, mention)])

    def _persist_many(
        self,
        records: list[tuple[EntityCandidate, EntityEvidence, EntityMention]],
    ) -> None:
        with self.repository.connect() as connection:
            for candidate, evidence, mention in records:
                self._insert_record(connection, candidate, evidence, mention)

    def _insert_record(
        self,
        connection: Any,
        candidate: EntityCandidate,
        evidence: EntityEvidence,
        mention: EntityMention,
    ) -> None:
            connection.execute(
                f"INSERT INTO {self.candidate_table}("
                "entity_candidate_id,extraction_run_id,source_id,client_id,vault_id,"
                "namespace,proposed_entity_type,proposed_label,candidate_status,"
                "entity_candidate_fingerprint_sha256,evidence_manifest_hash_sha256,"
                "entity_candidate_revision,entity_extractor_revision,created_at,updated_at,"
                "payload_json) VALUES("
                + ",".join([self.p] * 16)
                + ")",
                (
                    candidate.entity_candidate_id,
                    candidate.extraction_run_id,
                    candidate.source_id,
                    candidate.client_id,
                    candidate.vault_id,
                    candidate.namespace,
                    candidate.proposed_entity_type,
                    candidate.proposed_label,
                    candidate.candidate_status,
                    candidate.entity_candidate_fingerprint_sha256,
                    candidate.evidence_manifest_hash_sha256,
                    candidate.entity_candidate_revision,
                    candidate.entity_extractor_revision,
                    candidate.created_at,
                    candidate.updated_at,
                    json_value(self.repository, candidate.to_dict()),
                ),
            )
            connection.execute(
                f"INSERT INTO {self.evidence_table}("
                "entity_evidence_id,entity_candidate_id,source_id,segment_id,evidence_role,"
                "sequence_index,evidence_text_hash_sha256,segment_content_hash_sha256,"
                "source_content_hash_sha256,created_at,payload_json) VALUES("
                + ",".join([self.p] * 11)
                + ")",
                (
                    evidence.entity_evidence_id,
                    evidence.entity_candidate_id,
                    evidence.source_id,
                    evidence.segment_id,
                    evidence.evidence_role,
                    evidence.sequence_index,
                    evidence.evidence_text_hash_sha256,
                    evidence.segment_content_hash_sha256,
                    evidence.source_content_hash_sha256,
                    evidence.created_at,
                    json_value(self.repository, evidence.to_dict()),
                ),
            )
            connection.execute(
                f"INSERT INTO {self.mention_table}("
                "entity_mention_id,entity_id,entity_candidate_id,source_id,segment_id,"
                "client_id,vault_id,namespace,resolution_status,occurred_at,created_at,"
                "payload_json) VALUES("
                + ",".join([self.p] * 12)
                + ")",
                (
                    mention.entity_mention_id,
                    mention.entity_id,
                    mention.entity_candidate_id,
                    mention.source_id,
                    mention.segment_id,
                    mention.client_id,
                    mention.vault_id,
                    mention.namespace,
                    mention.resolution_status,
                    mention.occurred_at,
                    mention.created_at,
                    json_value(self.repository, mention.to_dict()),
                ),
            )

    def _candidate_by_fingerprint(
        self, scope: AuthenticatedScope, fingerprint: str
    ) -> EntityCandidate | None:
        with self.repository.connect() as connection:
            row = connection.execute(
                f"SELECT payload_json FROM {self.candidate_table} "
                f"WHERE client_id={self.p} AND vault_id={self.p} AND namespace={self.p} "
                f"AND entity_candidate_fingerprint_sha256={self.p}",
                (*scope_params(scope), fingerprint),
            ).fetchone()
        return EntityCandidate(**payload_from_row(row)) if row else None

    def _candidates_by_fingerprint(
        self, scope: AuthenticatedScope
    ) -> dict[str, EntityCandidate]:
        with self.repository.connect() as connection:
            rows = connection.execute(
                f"SELECT payload_json FROM {self.candidate_table} "
                f"WHERE client_id={self.p} AND vault_id={self.p} "
                f"AND namespace={self.p}",
                scope_params(scope),
            ).fetchall()
        candidates = [EntityCandidate(**payload_from_row(row)) for row in rows]
        return {
            item.entity_candidate_fingerprint_sha256: item for item in candidates
        }

    def _all_segments(
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
    def _evidence_segment(
        segments: list[SourceSegment], item: ExtractedEntity
    ) -> SourceSegment:
        if item.json_pointer:
            exact = next(
                (
                    segment
                    for segment in segments
                    if segment.json_pointer
                    and (
                        segment.json_pointer == item.json_pointer
                        or item.json_pointer.startswith(segment.json_pointer.rstrip("/") + "/")
                    )
                ),
                None,
            )
            if exact:
                return exact
        label = normalise_label(item.label)
        if label:
            containing = next(
                (
                    segment
                    for segment in segments
                    if label in normalise_label(segment.content)
                ),
                None,
            )
            if containing:
                return containing
        if not segments:
            raise EntityMemoryError(
                "ENTITY_EVIDENCE_INVALID", "Entity candidate has no source segment."
            )
        return segments[0]

    @staticmethod
    def _identifier_hint(raw: str) -> str:
        value = str(raw)
        if len(value) <= 4:
            return f"{value[:1]}***"
        return f"{value[:2]}...{value[-2:]}"

    @staticmethod
    def _safe_log(
        event: str, scope: AuthenticatedScope, **fields: Any
    ) -> None:
        allowed = {
            "entity_candidate_id",
            "entity_type",
            "status",
            "duration_ms",
        }
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


__all__ = ["EntityCandidateEngine"]
