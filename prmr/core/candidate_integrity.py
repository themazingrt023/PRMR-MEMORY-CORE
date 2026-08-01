"""Deterministic candidate fingerprint and manifest helpers."""

from __future__ import annotations

from typing import Any

from .candidate_models import ADMISSION_COMPATIBLE_CANDIDATE_MANIFEST_REVISION, CandidateMemory
from .candidate_rules import EvidenceSpec, RuleMatch
from .candidate_evidence import evidence_identity
from .source_integrity import canonical_json, sha256_text


def canonical_signal(value: str) -> str:
    return " ".join(value.split()).strip()


def candidate_fingerprint(
    *,
    source_id: str,
    match: RuleMatch,
    evidence: list[EvidenceSpec],
    candidate_rule_revision: str,
    candidate_extractor_revision: str,
) -> str:
    payload = {
        "source_id": source_id,
        "proposed_event_type": match.proposed_event_type,
        "canonical_proposed_signal": canonical_signal(match.proposed_signal),
        "proposed_occurred_at": match.proposed_occurred_at,
        "epistemic_status": match.epistemic_status,
        "ordered_evidence_identities": [evidence_identity(item) for item in evidence],
        "candidate_rule_revision": candidate_rule_revision,
        "candidate_extractor_revision": candidate_extractor_revision,
    }
    return sha256_text(canonical_json(payload))


def candidate_manifest_payload(candidates: list[CandidateMemory]) -> list[dict[str, Any]]:
    return [
        {
            "candidate_id": item.candidate_id,
            "candidate_fingerprint_sha256": item.candidate_fingerprint_sha256,
            "proposed_event_type": item.proposed_event_type,
            "signal_hash_sha256": sha256_text(item.proposed_signal),
            "epistemic_status": item.epistemic_status,
            "evidence_manifest_hash_sha256": item.evidence_manifest_hash_sha256,
            "primary_rule_id": item.primary_rule_id,
            "candidate_schema_revision": item.candidate_schema_revision,
            "candidate_extractor_revision": item.candidate_extractor_revision,
            "candidate_rule_revision": item.candidate_rule_revision,
            "epistemic_policy_revision": item.epistemic_policy_revision,
            "candidate_manifest_revision": ADMISSION_COMPATIBLE_CANDIDATE_MANIFEST_REVISION,
            "mutable_admission_state_excluded": True,
        }
        for item in candidates
    ]


def candidate_manifest_hash(candidates: list[CandidateMemory]) -> str:
    return sha256_text(canonical_json(candidate_manifest_payload(candidates)))


__all__ = [
    "candidate_fingerprint",
    "candidate_manifest_hash",
    "candidate_manifest_payload",
    "canonical_signal",
]
