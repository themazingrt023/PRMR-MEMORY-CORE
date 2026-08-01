"""Exact available provenance and opaque governance-loss context for V2."""

from __future__ import annotations

from typing import Any

from .continuity_v2_models import (
    CONTINUITY_V2_GOVERNANCE_REVISION,
    ContinuityGovernanceContext,
    ContinuityProvenanceContextV2,
)
from .entity_store import placeholder, table
from .memory_governance_store import MemoryGovernanceStore
from .source_integrity import canonical_json, sha256_text
from .source_models import AuthenticatedScope


def _payload(value: Any) -> dict[str, Any]:
    import json

    return dict(value) if isinstance(value, dict) else json.loads(value)


def build_provenance_context(
    repository: Any,
    scope: AuthenticatedScope,
    event_ids: list[str],
) -> tuple[ContinuityProvenanceContextV2, dict[str, dict[str, Any]]]:
    p = placeholder(repository)
    link_table = table(repository, "prmr_admitted_memory_links")
    source_table = table(repository, "prmr_sources")
    segment_table = table(repository, "prmr_source_segments")
    candidate_table = table(repository, "prmr_candidate_memories")
    admission_table = table(repository, "prmr_memory_admission_decisions")
    links: dict[str, dict[str, Any]] = {}
    with repository.connect() as connection:
        rows = connection.execute(
            f"SELECT * FROM {link_table} WHERE client_id={p} AND vault_id={p} AND namespace={p}",
            scope.memory_boundary(),
        ).fetchall()
        for row in rows:
            mapping = dict(row)
            links[str(mapping["admitted_event_id"])] = mapping
        source_ids = sorted({str(links[eid]["source_id"]) for eid in event_ids if eid in links})
        candidate_ids = sorted({str(links[eid]["candidate_id"]) for eid in event_ids if eid in links})
        admission_ids = sorted({str(links[eid]["admission_id"]) for eid in event_ids if eid in links})
        def count_rows(table_name: str, id_name: str, values: list[str]) -> int:
            if not values:
                return 0
            marks = ",".join([p] * len(values))
            row = connection.execute(
                f"SELECT COUNT(*) AS n FROM {table_name} WHERE client_id={p} AND vault_id={p} AND namespace={p} AND {id_name} IN ({marks})",
                (*scope.memory_boundary(), *values),
            ).fetchone()
            return int(row["n"])
        source_count = count_rows(source_table, "source_id", source_ids)
        candidate_count = count_rows(candidate_table, "candidate_id", candidate_ids)
        admission_count = count_rows(admission_table, "admission_id", admission_ids)
        if source_ids:
            marks = ",".join([p] * len(source_ids))
            row = connection.execute(
                f"SELECT COUNT(*) AS n FROM {segment_table} WHERE source_id IN ({marks})",
                tuple(source_ids),
            ).fetchone()
            segment_count = int(row["n"])
        else:
            segment_count = 0
    by_event: dict[str, dict[str, Any]] = {}
    complete = partial = legacy = 0
    references: list[dict[str, Any]] = []
    for event_id in sorted(event_ids):
        link = links.get(event_id)
        if not link:
            legacy += 1
            by_event[event_id] = {"status": "legacy_without_source", "references": []}
            continue
        available = all(link.get(key) for key in ("source_id", "candidate_id", "admission_id"))
        status = "complete" if available else "partial"
        complete += int(available)
        partial += int(not available)
        reference = {
            "event_id": event_id,
            "source_id": str(link.get("source_id")),
            "candidate_id": str(link.get("candidate_id")),
            "admission_id": str(link.get("admission_id")),
            "admitted_memory_link_id": str(link.get("admitted_memory_link_id")),
        }
        references.append(reference)
        by_event[event_id] = {"status": status, "references": [reference]}
    eligible = len(event_ids)
    rate = complete / eligible if eligible else 0.0
    material = {
        "events": sorted(event_ids),
        "references": references,
        "complete": complete,
        "partial": partial,
        "legacy": legacy,
        "revision": "continuity_provenance_v2",
    }
    context = ContinuityProvenanceContextV2(
        source_count=source_count,
        segment_count=segment_count,
        candidate_count=candidate_count,
        admission_count=admission_count,
        event_count=eligible,
        complete_event_count=complete,
        partial_event_count=partial,
        legacy_event_count=legacy,
        governance_erased_event_count=0,
        integrity_failed_event_count=0,
        evidence_bundle_references=references,
        provenance_coverage_rate={
            "numerator": complete,
            "denominator": eligible,
            "decimal": round(rate, 8),
            "percentage": round(rate * 100.0, 4),
        },
        provenance_manifest_hash=sha256_text(canonical_json(material)),
    )
    return context, by_event


def build_governance_context(
    repository: Any,
    scope: AuthenticatedScope,
    provenance: ContinuityProvenanceContextV2,
) -> ContinuityGovernanceContext:
    store = MemoryGovernanceStore(repository, initialize=False)
    tombstones = store.manifest_rows("tombstone", scope.memory_boundary())
    opaque = sorted(
        "govref_" + sha256_text(str(item.get("memory_erasure_tombstone_id", "")))[:20]
        for item in tombstones
    )
    erased_count = 0
    for item in tombstones:
        erased_count += sum(int(value) for value in item.get("erased_counts", {}).values())
    if tombstones:
        status = "evidence_unavailable_due_to_governance_erasure"
    elif provenance.legacy_event_count or provenance.partial_event_count:
        status = "partial"
    else:
        status = "complete"
    material = {
        "scope": scope.memory_boundary(),
        "opaque": opaque,
        "erased_count": erased_count,
        "partial": provenance.partial_event_count + provenance.legacy_event_count,
        "status": status,
        "revision": CONTINUITY_V2_GOVERNANCE_REVISION,
    }
    return ContinuityGovernanceContext(
        governance_erasure_present=bool(tombstones),
        erasure_tombstone_count=len(tombstones),
        opaque_tombstone_references=opaque,
        erased_dependency_count=erased_count,
        partial_provenance_count=provenance.partial_event_count + provenance.legacy_event_count,
        historically_unrecoverable_item_count=erased_count,
        invalidated_packet_count=0,
        governance_policy_revisions=sorted({str(item.get("memory_governance_policy_revision", "memory_governance_policy_v1")) for item in tombstones}),
        recoverability_limitation_status=status,
        governance_context_hash=sha256_text(canonical_json(material)),
    )


__all__ = ["build_governance_context", "build_provenance_context"]
