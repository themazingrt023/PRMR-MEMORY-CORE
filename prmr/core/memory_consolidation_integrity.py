"""Integrity verification for derived consolidation artifacts."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .admission_service import MemoryAdmissionService
from .memory_checkpoint import checkpoint_hash
from .memory_consolidation_membership import fast_authoritative_manifest
from .memory_consolidation_models import (
    MEMORY_CONSOLIDATION_INTEGRITY_REVISION,
    MemoryConsolidationIntegrityResult,
)
from .memory_consolidation_store import MemoryConsolidationStore
from .source_integrity import canonical_json, sha256_text
from .source_models import AuthenticatedScope


class MemoryConsolidationIntegrityVerifier:
    """Recompute identities and verify complete, scoped membership."""

    def __init__(self, repository: Any, *, initialize: bool = True) -> None:
        self.repository = repository
        self.store = MemoryConsolidationStore(repository, initialize=initialize)
        self.admission = MemoryAdmissionService(repository, initialize=initialize)

    def verify_consolidation_integrity(
        self, scope: AuthenticatedScope, consolidation_run_id: str
    ) -> MemoryConsolidationIntegrityResult:
        checks: dict[str, bool] = {}
        details: dict[str, Any] = {}
        run = self.store.get_run(scope, consolidation_run_id)
        checks["run_exists_and_scoped"] = run is not None
        if run is None:
            return MemoryConsolidationIntegrityResult(
                consolidation_run_id=consolidation_run_id,
                verified=False,
                checks=checks,
                failures=["run_exists_and_scoped"],
                details={},
            )
        plan = self.store.get_plan(scope, run.consolidation_plan_id)
        checks["plan_exists_and_scoped"] = plan is not None
        checkpoint = (
            self.store.get_checkpoint(scope, run.checkpoint_id)
            if run.checkpoint_id
            else None
        )
        checks["checkpoint_exists_and_scoped"] = checkpoint is not None
        checkpoint_memory_ids = set(
            checkpoint.deterministic_state_payload.get(
                "consolidated_memory_ids", []
            )
            if checkpoint
            else []
        )
        memories = [
            item
            for item in self.store.list_memories(
                scope, run_id=run.consolidation_run_id
            )
            if item.consolidated_memory_id in checkpoint_memory_ids
        ]
        members_by_memory: dict[str, list[Any]] = {}
        for member in self.store.list_members_for_scope(scope):
            if member.consolidated_memory_id in checkpoint_memory_ids:
                members_by_memory.setdefault(
                    member.consolidated_memory_id, []
                ).append(member)
        checks["completed_run_has_derived_items"] = bool(memories)
        events = {
            str(item.get("event_id")): item
            for item in self.admission._events_for_scope(scope)
        }

        memory_hashes_valid = True
        membership_hashes_valid = True
        membership_complete = True
        contributor_counts_valid = True
        member_objects_exist = True
        source_counts_valid = True
        epistemic_counts_valid = True
        conflict_sets_valid = True
        for memory in memories:
            material = {
                "type": memory.consolidation_type,
                "key": memory.consolidation_key,
                "events": memory.consolidation_payload.get(
                    "ordered_event_ids", []
                ),
                "payload": memory.consolidation_payload,
                "influence_summary": memory.influence_summary,
                "recurrence_summary": memory.recurrence_summary,
                "epistemic": {
                    key: value
                    for key, value in memory.contributor_epistemic_counts.items()
                    if value
                },
                "open_conflicts": memory.open_conflict_ids,
                "resolved_conflicts": memory.resolved_conflict_ids,
                "revisions": {
                    "schema": memory.memory_consolidation_schema_revision,
                    "policy": memory.memory_consolidation_policy_revision,
                },
            }
            memory_hashes_valid &= (
                sha256_text(canonical_json(material))
                == memory.consolidated_memory_hash_sha256
            )
            members = members_by_memory.get(memory.consolidated_memory_id, [])
            event_members = [item for item in members if item.member_type == "event"]
            expected_ids = memory.consolidation_payload.get("ordered_event_ids", [])
            actual_ids = [item.event_id for item in event_members]
            membership_complete &= actual_ids == expected_ids
            contributor_counts_valid &= (
                len(event_members) == memory.contributor_event_count
            )
            actual_sources = {item.source_id for item in event_members if item.source_id}
            source_counts_valid &= (
                len(actual_sources) == memory.contributor_source_count
            )
            actual_statuses = Counter(item.epistemic_status for item in event_members)
            normalised_statuses = Counter()
            for key, value in actual_statuses.items():
                normalised_statuses[
                    key if key in memory.contributor_epistemic_counts else "unknown"
                ] += value
            epistemic_counts_valid &= all(
                int(normalised_statuses.get(key, 0)) == int(value)
                for key, value in memory.contributor_epistemic_counts.items()
            )
            member_conflicts = {
                item.conflict_id for item in event_members if item.conflict_id
            }
            conflict_sets_valid &= member_conflicts.issubset(
                set(memory.open_conflict_ids) | set(memory.resolved_conflict_ids)
            )
            for member in event_members:
                event = events.get(str(member.event_id))
                member_objects_exist &= event is not None
                if event is None:
                    continue
                material = {
                    "consolidated_memory_id": memory.consolidated_memory_id,
                    "event_id": member.event_id,
                    "sequence_index": member.sequence_index,
                    "event_hash": sha256_text(canonical_json(event)),
                    "role": member.member_role,
                    "membership_revision": member.membership_revision,
                }
                membership_hashes_valid &= (
                    sha256_text(canonical_json(material))
                    == member.member_hash_sha256
                )
        checks["consolidated_memory_hashes_reproduce"] = memory_hashes_valid
        checks["membership_hashes_reproduce"] = membership_hashes_valid
        checks["membership_complete_and_ordered"] = membership_complete
        checks["contributor_counts_match"] = contributor_counts_valid
        checks["member_objects_exist_in_scope"] = member_objects_exist
        checks["source_counts_match"] = source_counts_valid
        checks["epistemic_distribution_preserved"] = epistemic_counts_valid
        checks["conflict_sets_preserved"] = conflict_sets_valid
        checks["derived_status_only"] = all(
            item.derived_epistemic_status == "derived" for item in memories
        )
        checks["no_generated_narrative"] = all(
            item.consolidation_payload.get("generated_narrative") is None
            for item in memories
        )
        checks["no_conflict_winner_selected"] = all(
            not item.consolidation_payload.get("winner_selected", False)
            for item in memories
        )

        if checkpoint:
            checks["checkpoint_hash_reproduces"] = (
                checkpoint_hash(checkpoint) == checkpoint.checkpoint_hash_sha256
            )
            memory_manifest = sha256_text(
                canonical_json(
                    sorted(
                        [
                        {
                            "id": item.consolidated_memory_id,
                            "hash": item.consolidated_memory_hash_sha256,
                        }
                        for item in memories
                        ],
                        key=lambda item: item["id"],
                    )
                )
            )
            checks["consolidation_manifest_reproduces"] = (
                memory_manifest == checkpoint.consolidated_memory_manifest_hash
                == run.consolidation_manifest_hash
            )
            current_manifest = fast_authoritative_manifest(
                self.repository, scope
            )["authoritative_manifest_hash"]
            checks["authoritative_manifest_current"] = (
                current_manifest == checkpoint.authoritative_event_manifest_hash
            )
            checks["no_future_event_leakage"] = all(
                str(item.get("timestamp") or item.get("occurred_at") or "")
                <= checkpoint.valid_at
                for item in events.values()
                if str(item.get("event_id"))
                in set(
                    checkpoint.deterministic_state_payload.get(
                        "effective_event_ids", []
                    )
                )
            )
            details["current_authoritative_manifest_hash"] = current_manifest
            details["stored_authoritative_manifest_hash"] = (
                checkpoint.authoritative_event_manifest_hash
            )
        else:
            checks["checkpoint_hash_reproduces"] = False
            checks["consolidation_manifest_reproduces"] = False
            checks["authoritative_manifest_current"] = False
            checks["no_future_event_leakage"] = False

        failures = [name for name, passed in checks.items() if not passed]
        details.update(
            {
                "consolidated_memory_count": len(memories),
                "checkpoint_id": run.checkpoint_id,
                "integrity_revision": MEMORY_CONSOLIDATION_INTEGRITY_REVISION,
            }
        )
        return MemoryConsolidationIntegrityResult(
            consolidation_run_id=consolidation_run_id,
            verified=not failures,
            checks=checks,
            failures=failures,
            details=details,
        )


__all__ = ["MemoryConsolidationIntegrityVerifier"]
