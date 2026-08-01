"""Epistemically separated effective relationship context for V2."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from .continuity_v2_models import ContinuityRelationshipContextV2
from .memory_ledger_models import MemoryTemporalBoundary
from .relationship_memory import RelationshipMemoryService
from .source_integrity import canonical_json, sha256_text
from .source_models import AuthenticatedScope


def build_relationship_context(
    repository: Any,
    scope: AuthenticatedScope,
    *,
    entity_id: str | None,
    valid_at: str,
    known_at: str,
    maximum_items: int,
) -> tuple[dict[str, list[dict[str, Any]]], str, dict[str, list[str]], list[dict[str, Any]]]:
    service = RelationshipMemoryService(repository, initialize=False)
    view = service.resolve_effective_relationships(
        scope,
        entity_id=entity_id,
        temporal_boundary=MemoryTemporalBoundary(valid_at=valid_at, known_at=known_at),
        include_conflicted=True,
    )
    open_by_relationship: dict[str, list[str]] = defaultdict(list)
    for conflict in view.open_conflicts:
        for relationship_id in conflict.get("relationship_ids", []):
            open_by_relationship[str(relationship_id)].append(str(conflict["conflict_id"]))
    collections = {
        "asserted_relationships": [],
        "derived_relationships": [],
        "tentative_relationships": [],
        "unknown_relationships": [],
        "conflicted_relationships": [],
    }
    by_entity: dict[str, list[str]] = defaultdict(list)
    for relationship in view.effective_relationships[:maximum_items]:
        status = relationship.epistemic_status
        if status == "explicit":
            target = "asserted_relationships"
        elif status == "derived":
            target = "derived_relationships"
        elif status == "inferred":
            target = "tentative_relationships"
        else:
            target = "unknown_relationships"
        conflict_ids = sorted(open_by_relationship.get(relationship.relationship_id, []))
        material = {
            "id": relationship.relationship_id,
            "subject": relationship.subject_entity_id,
            "type": relationship.relationship_type,
            "object": relationship.object_entity_id,
            "epistemic": status,
            "status": relationship.relationship_status,
            "valid_from": relationship.valid_from,
            "known_from": relationship.system_known_from,
            "conflicts": conflict_ids,
            "revision": "continuity_relationship_context_v1",
        }
        item = ContinuityRelationshipContextV2(
            relationship_id=relationship.relationship_id,
            subject_entity_id=relationship.subject_entity_id,
            relationship_type=relationship.relationship_type,
            object_entity_id=relationship.object_entity_id,
            epistemic_status=status,
            relationship_status=relationship.relationship_status,
            valid_from=relationship.valid_from,
            valid_until=relationship.valid_until,
            known_from=relationship.system_known_from,
            known_until=relationship.system_known_until,
            temporal_phase=None,
            conflict_ids=conflict_ids,
            superseded_by_relationship_id=None,
            evidence_completeness=(
                "complete" if relationship.originating_source_id else "legacy_without_source"
            ),
            provenance_references=[
                {
                    "source_id": relationship.originating_source_id,
                    "admission_id": relationship.originating_admission_id,
                }
            ],
            relationship_hash=sha256_text(canonical_json(material)),
        ).to_dict()
        collections[target].append(item)
        if conflict_ids or relationship.relationship_status == "conflicted":
            collections["conflicted_relationships"].append(dict(item))
        by_entity[relationship.subject_entity_id].append(relationship.relationship_id)
        by_entity[relationship.object_entity_id].append(relationship.relationship_id)
    for values in collections.values():
        values.sort(key=lambda item: item["relationship_id"])
    manifest = sha256_text(canonical_json({"collections": collections, "resolver": view.deterministic_relationship_manifest}))
    return collections, manifest, {key: sorted(set(value)) for key, value in by_entity.items()}, view.open_conflicts


__all__ = ["build_relationship_context"]
