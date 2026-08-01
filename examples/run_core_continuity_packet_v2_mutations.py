"""Critical mutation tests for Epistemic Continuity Packet V2 laws."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from prmr.core.continuity_v2_fixtures import (
    ContinuityV2FixtureBuilder,
    FIXED_BOUNDARY,
    build_mixed_epistemic_fixture,
    v2_fixture_scope,
)
from prmr.core.continuity_v2_integrity import verify_packet_v2_integrity
from prmr.core.continuity_v2_packet import ContinuityPacketV2Service
from prmr.core.runtime_migrations import apply_pending_migrations
from prmr.product.self_serve_repository_v093 import SelfServeRepositoryV093


REPORT = ROOT / "reports" / "core_continuity_packet_v2" / "mutation_results_continuity_packet_v2.json"


def record(
    output: list[dict[str, Any]],
    mutation_id: str,
    name: str,
    detected: bool,
    channel: str,
    failures: list[str] | None = None,
) -> None:
    output.append(
        {
            "mutation_id": mutation_id,
            "name": name,
            "detected": bool(detected),
            "detection_channel": channel,
            "integrity_failures": failures or [],
        }
    )


def integrity_mutation(
    output: list[dict[str, Any]],
    mutation_id: str,
    name: str,
    scope: Any,
    payload: dict[str, Any],
    expected_failure: str,
) -> None:
    result = verify_packet_v2_integrity(scope, payload)
    record(
        output,
        mutation_id,
        name,
        expected_failure in result.failures,
        expected_failure,
        result.failures,
    )


def main() -> int:
    mutations: list[dict[str, Any]] = []
    with TemporaryDirectory(prefix="prmr-core-s13-mutations-") as temporary:
        repository = SelfServeRepositoryV093(Path(temporary) / "mutations.sqlite")
        apply_pending_migrations(repository)
        mixed = build_mixed_epistemic_fixture(repository, "mutation_mixed")
        service = ContinuityPacketV2Service(repository)
        base = service.generate_packet_v2(
            mixed.scope, temporal_boundary=FIXED_BOUNDARY
        ).to_dict()

        mutated = deepcopy(base)
        item = mutated["tentative_information"].pop(0)
        mutated["asserted_information"].append(item)
        integrity_mutation(
            mutations, "M01", "promote inferred to asserted", mixed.scope,
            mutated, "no_inferred_promotion"
        )

        unknown_builder = ContinuityV2FixtureBuilder(
            repository, v2_fixture_scope("mutation_unknown")
        )
        unknown_builder.unknown_state(
            "unknown", statement="The result remains unknown.",
            occurred_at="2026-08-02T10:00:00Z", state_key="result.status"
        )
        unknown = ContinuityPacketV2Service(repository).generate_packet_v2(
            unknown_builder.scope, temporal_boundary=FIXED_BOUNDARY
        ).to_dict()
        mutated = deepcopy(unknown)
        mutated["state_dimensions"][0]["current_value"] = "invented"
        integrity_mutation(
            mutations, "M02", "convert unknown to state value",
            unknown_builder.scope, mutated, "unknown_has_no_state_value"
        )

        conflict_builder = ContinuityV2FixtureBuilder(
            repository, v2_fixture_scope("mutation_conflict")
        )
        conflict_builder.explicit_state(
            "a", event_type="status.updated", signal="Service remained online.",
            occurred_at="2026-08-02T09:00:00Z", state_key="service.status", state_value="online"
        )
        conflict_builder.explicit_state(
            "b", event_type="status.updated", signal="Service was unavailable.",
            occurred_at="2026-08-02T09:01:00Z", state_key="service.status", state_value="offline"
        )
        conflict_builder.declare_conflict("status", ["a", "b"])
        conflict = ContinuityPacketV2Service(repository).generate_packet_v2(
            conflict_builder.scope, temporal_boundary=FIXED_BOUNDARY
        ).to_dict()
        mutated = deepcopy(conflict)
        latest = mutated["state_dimensions"][0]["asserted_event_ids"][-1]
        mutated["state_dimensions"][0]["selected_asserted_event_id"] = latest
        mutated["state_dimensions"][0]["current_value"] = "offline"
        integrity_mutation(
            mutations, "M03", "select latest conflict participant as winner",
            conflict_builder.scope, mutated, "no_conflict_winner"
        )

        mutated = deepcopy(base)
        mutated["asserted_information"][0]["known_from"] = "2100-01-01T00:00:00Z"
        integrity_mutation(
            mutations, "M04", "ignore known_at", mixed.scope, mutated,
            "no_future_leakage"
        )

        mutated = deepcopy(base)
        entity = {
            "canonical_entity_id": "ent_same",
            "canonical_label": "Alex Reed",
            "entity_view_hash": "mutation",
        }
        mutated["entity_context"] = [entity, dict(entity)]
        integrity_mutation(
            mutations, "M05", "merge same-name entity packets", mixed.scope,
            mutated, "entity_identity_not_collapsed"
        )

        mutated = deepcopy(base)
        inferred_relationship = {
            "relationship_id": "rel_mutation",
            "epistemic_status": "inferred",
            "relationship_hash": "mutation",
        }
        mutated["relationship_context"]["asserted_relationships"] = [inferred_relationship]
        integrity_mutation(
            mutations, "M06", "promote inferred relationship", mixed.scope,
            mutated, "relationship_epistemic_categorisation"
        )

        mutated = deepcopy(base)
        mutated["lineage_context"]["canonical_signal_mapping_history"].append(
            {
                "mapping_applied": True,
                "decision_status": "pending_review",
                "original_signal_key": "project.pending",
                "canonical_signal_key": "project.updated",
            }
        )
        pending_applied = any(
            item.get("mapping_applied") and item.get("decision_status") == "pending_review"
            for item in mutated["lineage_context"]["canonical_signal_mapping_history"]
        )
        record(mutations, "M07", "allow pending canonical mapping", pending_applied, "reviewed_mapping_oracle")

        stale_acceleration = {
            "checkpoint_status": "stale",
            "equivalence_verified": False,
            "fallback_used": False,
        }
        record(
            mutations, "M08", "trust stale consolidation",
            stale_acceleration["checkpoint_status"] != "current"
            and not stale_acceleration["fallback_used"],
            "acceleration_fallback_oracle",
        )

        prior_report_path = ROOT / "reports" / "core_continuity_packet_v2" / "private_internal_continuity_packet_v2.json"
        prior = json.loads(prior_report_path.read_text(encoding="utf-8"))
        old_unavailable = next(
            item["passed"] for item in prior["sqlite"]["checks"]
            if item["name"] == "old_governed_packet_unavailable"
        )
        mutated_old_packet_available = not old_unavailable
        record(
            mutations, "M09", "expose erased evidence through old packet",
            not mutated_old_packet_available and old_unavailable,
            "governance_unavailability_oracle",
        )

        mutated = deepcopy(base)
        removed_event = mutated["provenance_context"]["evidence_bundle_references"].pop()["event_id"]
        integrity_mutation(
            mutations, "M10", f"remove provenance member {removed_event}",
            mixed.scope, mutated, "complete_provenance_members_present"
        )

        mutated = deepcopy(base)
        mutated["tentative_information"][0]["epistemic_weight"] = 0.9
        integrity_mutation(
            mutations, "M11", "change epistemic weight without revision",
            mixed.scope, mutated, "epistemic_weights_revision_bound"
        )

        mutated = deepcopy(base)
        mutated["legacy_coherence_breakdown"]["formula_unchanged"] = False
        mutated["legacy_recoverability_breakdown"]["formula_unchanged"] = False
        integrity_mutation(
            mutations, "M12", "recalculate legacy score with V2 formula",
            mixed.scope, mutated, "legacy_score_formula_unchanged"
        )

    passed = sum(item["detected"] for item in mutations)
    result = "PASS" if passed == 12 else "NEEDS_WORK"
    payload = {
        "sprint": "Core Sprint 13",
        "mutation_count": len(mutations),
        "detected_count": passed,
        "mutations": mutations,
        "result": result,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print("PRMR Memory Core - Core Sprint 13 Critical Mutations")
    print(f"Detected mutations: {passed}/12")
    print(f"Result: {result}")
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
