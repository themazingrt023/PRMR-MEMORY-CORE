"""Fail-closed quality policy and corpus distribution for Core Sprint 12."""

from __future__ import annotations


MEMORY_QUALITY_POLICY_REVISION = "memory_quality_policy_v1"
MEMORY_QUALITY_CORPUS_REVISION = "memory_quality_corpus_v1"
MEMORY_QUALITY_METRICS_REVISION = "memory_quality_metrics_v1"
MEMORY_QUALITY_ADVERSARIAL_REVISION = "memory_quality_adversarial_v1"
MEMORY_QUALITY_MUTATION_REVISION = "memory_quality_mutation_v1"
MEMORY_QUALITY_BACKEND_PARITY_REVISION = "memory_quality_backend_parity_v1"
MEMORY_QUALITY_INTEGRITY_REVISION = "memory_quality_integrity_v1"
MEMORY_QUALITY_REPORT_REVISION = "memory_quality_report_v1"

DOMAIN_MINIMUMS = {
    "source_fidelity": 15,
    "candidate_memory": 25,
    "epistemic_safety": 30,
    "admission": 15,
    "bitemporal_reconstruction": 25,
    "temporal_dynamics": 20,
    "entity_identity": 25,
    "relationships": 25,
    "query_and_evidence": 25,
    "consolidation": 15,
    "interpretation": 20,
    "governance": 20,
    "runtime_backend_parity": 10,
}

CRITICAL_MUTATIONS = (
    "disable_tenant_scope_check",
    "ignore_negation",
    "promote_inferred_to_explicit",
    "convert_unknown_to_observation",
    "include_events_after_known_at",
    "select_open_conflict_winner",
    "merge_entities_by_label_only",
    "admit_inferred_relationship",
    "activate_pending_canonical_mapping",
    "trust_stale_consolidation",
    "skip_evidence_hash_validation",
    "omit_consolidation_member",
    "leave_query_artifact_after_erasure",
    "permit_stale_governance_plan",
    "duplicate_job_effect",
    "accept_old_lease_token",
    "skip_source_sanitisation",
    "fabricate_legacy_provenance",
)

PUBLIC_FORBIDDEN_PATTERNS = (
    "postgresql://", "postgres://", "authorization:", "bearer ",
    "prmr_live_", "prmr_alpha_", "github_pat_", "ghp_", "private key",
)

REQUIRED_FINAL_STATEMENT = (
    "Core Sprint 12 establishes the PRMR Memory Quality Benchmark and Reproducible "
    "Validation Framework. The complete Source Ledger, Candidate Memory, Admission, "
    "Bitemporal Evolution, Temporal Dynamics, Entity and Relationship Memory, "
    "Deterministic Query, Consolidation, Bounded Interpretation, Governance and "
    "PostgreSQL Runtime layers are now evaluated against a versioned independent "
    "gold corpus with explicit per-capability metrics, adversarial cases, backend "
    "parity and mutation sensitivity. The benchmark does not collapse memory quality "
    "into one intelligence score. Critical safety properties—including provenance, "
    "unknown preservation, conflict preservation, identity separation, temporal "
    "isolation, governance erasure and tenant isolation—are evaluated independently. "
    "These results remain internal engineering evidence rather than external "
    "scientific validation."
)


__all__ = [
    "CRITICAL_MUTATIONS", "DOMAIN_MINIMUMS", "MEMORY_QUALITY_ADVERSARIAL_REVISION",
    "MEMORY_QUALITY_BACKEND_PARITY_REVISION", "MEMORY_QUALITY_CORPUS_REVISION",
    "MEMORY_QUALITY_INTEGRITY_REVISION", "MEMORY_QUALITY_METRICS_REVISION",
    "MEMORY_QUALITY_MUTATION_REVISION", "MEMORY_QUALITY_POLICY_REVISION",
    "MEMORY_QUALITY_REPORT_REVISION", "PUBLIC_FORBIDDEN_PATTERNS",
    "REQUIRED_FINAL_STATEMENT",
]
