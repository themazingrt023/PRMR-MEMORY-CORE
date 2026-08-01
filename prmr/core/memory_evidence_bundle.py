"""Exact, scope-bound evidence retrieval for deterministic memory queries."""

from __future__ import annotations

import logging
from typing import Any

from .memory_query_models import (
    MEMORY_EVIDENCE_BUNDLE_REVISION,
    EvidenceCompletenessStatus,
    MemoryEvidenceBundle,
    MemoryEvidenceItem,
    MemoryQueryPolicy,
)
from .memory_query_planner import utc
from .memory_query_store import placeholder, table
from .source_integrity import canonical_json, sha256_text
from .source_ledger import SourceLedger
from .source_models import AuthenticatedScope


LOGGER = logging.getLogger("prmr.core.memory_evidence")


class MemoryEvidenceBundleBuilder:
    """Build evidence bundles without loading unrelated source bodies."""

    def __init__(self, repository: Any) -> None:
        self.repository = repository
        self.p = placeholder(repository)
        self.links = table(repository, "prmr_admitted_memory_links")
        self.evidence = table(repository, "prmr_candidate_evidence")
        self.segments = table(repository, "prmr_source_segments")
        self.sources = table(repository, "prmr_sources")
        self.entity_evidence = table(repository, "prmr_entity_evidence")
        self.relationship_evidence = table(repository, "prmr_relationship_evidence")
        self.source_ledger = SourceLedger(repository, initialize=False)

    def build(
        self,
        scope: AuthenticatedScope,
        query_run_id: str,
        *,
        event_ids: list[str],
        entity_ids: list[str] | None = None,
        relationship_ids: list[str] | None = None,
        evolution_ids: list[str] | None = None,
        dynamics_snapshot_ids: list[str] | None = None,
        conflict_ids: list[str] | None = None,
        packet_ids: list[str] | None = None,
        reconstruction_ids: list[str] | None = None,
        policy: MemoryQueryPolicy,
    ) -> MemoryEvidenceBundle:
        requested_events = sorted(set(event_ids))
        entity_ids = sorted(set(entity_ids or []))
        relationship_ids = sorted(set(relationship_ids or []))
        rows = self._event_rows(scope, requested_events)
        rows.extend(self._entity_rows(scope, entity_ids))
        rows.extend(self._relationship_rows(scope, relationship_ids))
        rows = sorted(
            rows,
            key=lambda row: (
                str(row["source_id"]),
                str(row.get("segment_id") or ""),
                str(row.get("event_id") or ""),
                int(row.get("evidence_sequence", 0)),
            ),
        )
        integrity_by_source: dict[str, bool] = {}
        items: list[MemoryEvidenceItem] = []
        for sequence_index, row in enumerate(rows[: policy.maximum_evidence_items]):
            source_id = str(row["source_id"])
            if source_id not in integrity_by_source:
                try:
                    integrity_by_source[source_id] = self.source_ledger.verify_source_integrity(
                        scope, source_id
                    ).verified
                except Exception:
                    integrity_by_source[source_id] = False
            content = self._evidence_text(row)
            content_hash = str(row.get("evidence_text_hash_sha256") or "")
            text_matches = bool(content_hash) and sha256_text(content) == content_hash
            integrity = integrity_by_source[source_id] and text_matches
            identity = {
                "query_run_id": query_run_id,
                "source_id": source_id,
                "segment_id": row.get("segment_id"),
                "event_id": row.get("event_id"),
                "entity_id": row.get("entity_id"),
                "relationship_id": row.get("relationship_id"),
                "sequence_index": sequence_index,
                "content_hash": content_hash,
                "revision": MEMORY_EVIDENCE_BUNDLE_REVISION,
            }
            items.append(
                MemoryEvidenceItem(
                    evidence_item_id=f"qev_{sha256_text(canonical_json(identity))[:24]}",
                    evidence_type=str(row.get("evidence_type") or "candidate_evidence"),
                    source_id=source_id,
                    segment_id=_optional(row.get("segment_id")),
                    event_id=_optional(row.get("event_id")),
                    entity_id=_optional(row.get("entity_id")),
                    relationship_id=_optional(row.get("relationship_id")),
                    candidate_id=_optional(row.get("candidate_id")),
                    admission_id=_optional(row.get("admission_id")),
                    source_start_offset=_integer(row.get("source_start_offset")),
                    source_end_offset=_integer(row.get("source_end_offset")),
                    segment_start_offset=_integer(row.get("segment_start_offset")),
                    segment_end_offset=_integer(row.get("segment_end_offset")),
                    start_line=_integer(row.get("start_line")),
                    end_line=_integer(row.get("end_line")),
                    json_pointer=_optional(row.get("json_pointer")),
                    content_hash_sha256=content_hash,
                    safe_preview=(
                        content[: policy.maximum_safe_preview_characters]
                        if policy.include_safe_evidence_preview and integrity
                        else None
                    ),
                    epistemic_status=str(
                        row.get("epistemic_status") or "legacy_unclassified"
                    ),
                    evidence_role=str(row.get("evidence_role") or "supporting"),
                    integrity_status="verified" if integrity else "integrity_failed",
                    sequence_index=sequence_index,
                )
            )
        found_events = {
            str(row["event_id"]) for row in rows if row.get("event_id") is not None
        }
        legacy = bool(set(requested_events) - found_events)
        truncated = len(rows) > policy.maximum_evidence_items
        failed = any(item.integrity_status != "verified" for item in items)
        if truncated:
            completeness = EvidenceCompletenessStatus.TRUNCATED.value
        elif failed:
            completeness = EvidenceCompletenessStatus.INTEGRITY_FAILED.value
        elif legacy and items:
            completeness = EvidenceCompletenessStatus.PARTIAL.value
        elif legacy:
            completeness = EvidenceCompletenessStatus.LEGACY_WITHOUT_SOURCE.value
        elif items:
            completeness = EvidenceCompletenessStatus.COMPLETE.value
        else:
            completeness = EvidenceCompletenessStatus.UNAVAILABLE.value
        manifest_items = [
            {
                "evidence_item_id": item.evidence_item_id,
                "content_hash_sha256": item.content_hash_sha256,
                "integrity_status": item.integrity_status,
                "sequence_index": item.sequence_index,
            }
            for item in items
        ]
        manifest = sha256_text(canonical_json(manifest_items))
        bundle_identity = {
            "query_run_id": query_run_id,
            "manifest": manifest,
            "completeness": completeness,
            "revision": MEMORY_EVIDENCE_BUNDLE_REVISION,
        }
        bundle = MemoryEvidenceBundle(
            evidence_bundle_id=f"ebun_{sha256_text(canonical_json(bundle_identity))[:24]}",
            query_run_id=query_run_id,
            client_id=scope.client_id,
            vault_id=scope.vault_id,
            namespace=scope.namespace,
            source_ids=sorted({item.source_id for item in items}),
            segment_ids=sorted(
                {item.segment_id for item in items if item.segment_id is not None}
            ),
            candidate_ids=sorted(
                {item.candidate_id for item in items if item.candidate_id is not None}
            ),
            admission_ids=sorted(
                {item.admission_id for item in items if item.admission_id is not None}
            ),
            event_ids=requested_events,
            evolution_ids=sorted(set(evolution_ids or [])),
            dynamics_snapshot_ids=sorted(set(dynamics_snapshot_ids or [])),
            entity_ids=entity_ids,
            relationship_ids=relationship_ids,
            conflict_ids=sorted(set(conflict_ids or [])),
            packet_ids=sorted(set(packet_ids or [])),
            reconstruction_ids=sorted(set(reconstruction_ids or [])),
            evidence_items=items,
            evidence_item_count=len(items),
            completeness_status=completeness,
            truncated=truncated,
            evidence_manifest_hash_sha256=manifest,
            memory_evidence_bundle_revision=MEMORY_EVIDENCE_BUNDLE_REVISION,
            created_at=utc(None),
        )
        LOGGER.info(
            "memory_evidence_bundle_created query_run_id=%s evidence_count=%s",
            query_run_id,
            len(items),
        )
        return bundle

    def _event_rows(
        self, scope: AuthenticatedScope, event_ids: list[str]
    ) -> list[dict[str, Any]]:
        if not event_ids:
            return []
        markers = ",".join([self.p] * len(event_ids))
        sql = (
            "SELECT l.source_id,l.admitted_event_id AS event_id,l.candidate_id,"
            "l.admission_id,l.epistemic_status,e.segment_id,e.evidence_role,"
            "e.sequence_index AS evidence_sequence,e.source_start_offset,"
            "e.source_end_offset,e.segment_start_offset,e.segment_end_offset,"
            "e.start_line,e.end_line,e.json_pointer,e.evidence_text_hash_sha256,"
            "s.content AS segment_content,'candidate_evidence' AS evidence_type "
            f"FROM {self.links} l JOIN {self.evidence} e ON e.candidate_id=l.candidate_id "
            f"JOIN {self.segments} s ON s.segment_id=e.segment_id "
            f"WHERE l.client_id={self.p} AND l.vault_id={self.p} "
            f"AND l.namespace={self.p} AND l.admitted_event_id IN ({markers})"
        )
        with self.repository.connect() as connection:
            rows = connection.execute(
                sql, (*scope.memory_boundary(), *event_ids)
            ).fetchall()
        return [dict(row) for row in rows]

    def _entity_rows(
        self, scope: AuthenticatedScope, entity_ids: list[str]
    ) -> list[dict[str, Any]]:
        if not entity_ids:
            return []
        entities = table(self.repository, "prmr_entities")
        markers = ",".join([self.p] * len(entity_ids))
        sql = (
            "SELECT ee.payload_json,e.entity_id,s.content AS segment_content "
            f"FROM {entities} e JOIN {self.entity_evidence} ee "
            "ON ee.entity_candidate_id=e.originating_entity_candidate_id "
            f"JOIN {self.segments} s ON s.segment_id=ee.segment_id "
            f"WHERE e.client_id={self.p} AND e.vault_id={self.p} "
            f"AND e.namespace={self.p} AND e.entity_id IN ({markers})"
        )
        with self.repository.connect() as connection:
            rows = connection.execute(
                sql, (*scope.memory_boundary(), *entity_ids)
            ).fetchall()
        return [
            {
                **_payload(row["payload_json"]),
                "entity_id": row["entity_id"],
                "segment_content": row["segment_content"],
                "candidate_id": _payload(row["payload_json"]).get(
                    "entity_candidate_id"
                ),
                "evidence_sequence": _payload(row["payload_json"]).get(
                    "sequence_index", 0
                ),
                "evidence_type": "entity_evidence",
                "epistemic_status": "explicit",
            }
            for row in rows
        ]

    def _relationship_rows(
        self, scope: AuthenticatedScope, relationship_ids: list[str]
    ) -> list[dict[str, Any]]:
        if not relationship_ids:
            return []
        relationships = table(self.repository, "prmr_relationships")
        markers = ",".join([self.p] * len(relationship_ids))
        sql = (
            "SELECT re.payload_json,r.relationship_id,r.epistemic_status,"
            "s.content AS segment_content "
            f"FROM {relationships} r JOIN {self.relationship_evidence} re "
            "ON re.relationship_candidate_id=r.originating_relationship_candidate_id "
            f"JOIN {self.segments} s ON s.segment_id=re.segment_id "
            f"WHERE r.client_id={self.p} AND r.vault_id={self.p} "
            f"AND r.namespace={self.p} AND r.relationship_id IN ({markers})"
        )
        with self.repository.connect() as connection:
            rows = connection.execute(
                sql, (*scope.memory_boundary(), *relationship_ids)
            ).fetchall()
        return [
            {
                **_payload(row["payload_json"]),
                "relationship_id": row["relationship_id"],
                "segment_content": row["segment_content"],
                "candidate_id": _payload(row["payload_json"]).get(
                    "relationship_candidate_id"
                ),
                "evidence_sequence": _payload(row["payload_json"]).get(
                    "sequence_index", 0
                ),
                "evidence_type": "relationship_evidence",
                "epistemic_status": row["epistemic_status"],
            }
            for row in rows
        ]

    @staticmethod
    def _evidence_text(row: dict[str, Any]) -> str:
        content = str(row.get("segment_content") or "")
        start = _integer(row.get("segment_start_offset"))
        end = _integer(row.get("segment_end_offset"))
        if start is not None and end is not None and 0 <= start <= end <= len(content):
            return content[start:end]
        return content


def _optional(value: Any) -> str | None:
    return None if value in (None, "") else str(value)


def _integer(value: Any) -> int | None:
    return None if value is None else int(value)


def _payload(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        import json

        return json.loads(value)
    return dict(value or {})


__all__ = ["MemoryEvidenceBundleBuilder"]
