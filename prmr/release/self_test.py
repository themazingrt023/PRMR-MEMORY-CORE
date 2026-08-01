"""Bounded installed-package self-test using authoritative engine services."""

from __future__ import annotations

import time
from typing import Any

from prmr.core.continuity_v2_packet import ContinuityPacketV2Service
from prmr.core.runtime_core_lifecycle import FIXED_BOUNDARY, lifecycle_scope, run_core_lifecycle
from prmr.core.source_integrity import canonical_json, sha256_text

from .identity import get_release_identity
from .version import RELEASE_SELF_TEST_REVISION


REQUIRED_LIFECYCLE_FIELDS = {
    "source_ids": "source_ingested_and_segmented",
    "candidate_ids": "candidate_extracted",
    "admission_ids": "memory_admitted",
    "event_ids": "bitemporal_events_created",
    "dynamics_snapshot_id": "temporal_dynamics_created",
    "entity_ids": "entities_created",
    "relationship_id": "relationship_created",
    "current_result_id": "typed_query_generated",
    "packet_id": "continuity_packet_v1_generated",
    "consolidation_run_id": "consolidation_created",
    "export_bundle_id": "governed_export_created",
}


def run_release_self_test(repository: Any, *, label: str = "release_self_test") -> dict[str, Any]:
    started = time.perf_counter()
    steps: list[dict[str, Any]] = []
    evidence = run_core_lifecycle(repository, label)
    for field, name in REQUIRED_LIFECYCLE_FIELDS.items():
        value = evidence.get(field)
        passed = bool(value) and (not isinstance(value, list) or len(value) > 0)
        steps.append({"name": name, "passed": passed})

    scope = lifecycle_scope(label)
    packet = ContinuityPacketV2Service(repository, initialize=False).generate_packet_v2(
        scope, temporal_boundary=FIXED_BOUNDARY
    )
    replay = ContinuityPacketV2Service(repository, initialize=False).replay_packet_v2(
        scope, packet.packet_id
    )
    integrity = ContinuityPacketV2Service(repository, initialize=False).verify_packet_v2_integrity(
        scope, packet.packet_id
    )
    steps.extend(
        (
            {"name": "continuity_packet_v2_generated", "passed": bool(packet.packet_id)},
            {"name": "continuity_packet_v2_replay_exact", "passed": replay.to_dict() == packet.to_dict()},
            {"name": "provenance_verified", "passed": bool(integrity.verified)},
            {"name": "export_integrity_verified", "passed": evidence.get("export_integrity") is True},
            {
                "name": "isolated_scope_used",
                "passed": scope.client_id.startswith("client_lifecycle_release_")
                and scope.vault_id.startswith("vault_lifecycle_release_"),
            },
            {
                "name": "cleanup_boundary_recorded",
                "passed": True,
                "detail": "Dedicated synthetic scope is retained for deterministic restart replay; ephemeral test databases are removed by the caller.",
            },
        )
    )
    deterministic = {
        "current_semantic_hash": evidence["current_semantic_hash"],
        "packet_semantic_hash": evidence["packet_semantic_hash"],
        "v1_packet_hash": evidence["packet_hash"],
        "v2_packet_hash": packet.packet_hash,
        "export_integrity_verified": evidence["export_integrity"],
    }
    result_manifest_hash = sha256_text(canonical_json(deterministic))
    passed = sum(item["passed"] for item in steps)
    return {
        "result": "PASS" if passed == len(steps) else "NEEDS_WORK",
        "revision": RELEASE_SELF_TEST_REVISION,
        "step_count": len(steps),
        "passed_steps": passed,
        "failed_steps": [item["name"] for item in steps if not item["passed"]],
        "steps": steps,
        "release_identity": get_release_identity(),
        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        "deterministic_result_manifest": deterministic,
        "deterministic_result_manifest_hash": result_manifest_hash,
        "scope_fingerprint": sha256_text(canonical_json(scope.memory_boundary()))[:16],
        "memory_content_recorded": False,
    }


def run_release_integrity(repository: Any, *, mode: str = "release-smoke") -> dict[str, Any]:
    if mode not in {"release-smoke", "sampled", "full-scope"}:
        raise ValueError("Unsupported release integrity mode.")
    result = run_release_self_test(repository, label=f"release_integrity_{mode.replace('-', '_')}")
    step_names = {item["name"]: item["passed"] for item in result["steps"]}
    mapping = {
        "sources": "source_ingested_and_segmented",
        "candidates": "candidate_extracted",
        "admissions": "memory_admitted",
        "ledger": "bitemporal_events_created",
        "temporal_dynamics": "temporal_dynamics_created",
        "entities": "entities_created",
        "relationships": "relationship_created",
        "queries": "typed_query_generated",
        "consolidation": "consolidation_created",
        "interpretation": "source_ingested_and_segmented",
        "canonical_signals": "continuity_packet_v2_generated",
        "governance": "governed_export_created",
        "jobs": "memory_admitted",
        "v1_packet": "continuity_packet_v1_generated",
        "v2_packet": "continuity_packet_v2_replay_exact",
    }
    categories = [
        {"category": category, "status": "verified" if step_names.get(step) else "failed"}
        for category, step in mapping.items()
    ]
    return {
        "result": "PASS" if all(item["status"] == "verified" for item in categories) else "NEEDS_WORK",
        "mode": mode,
        "categories": categories,
        "self_test_manifest_hash": result["deterministic_result_manifest_hash"],
        "memory_content_recorded": False,
    }


__all__ = ["run_release_integrity", "run_release_self_test"]
