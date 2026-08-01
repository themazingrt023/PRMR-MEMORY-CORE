"""Versioned strict policy for Epistemic Continuity Packet V2."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .continuity_v2_models import ContinuityPacketV2Error


CONTINUITY_V2_POLICY_REVISION = "epistemic_continuity_policy_v1"
CONTINUITY_V2_POLICY_ID = "epistemic_strict_v1"
PACKET_MODES = ("legacy_continuity_v1", "epistemic_continuity_v2")
SIGNAL_IDENTITY_MODES = ("exact_signal_v1", "canonical_signal_v1")
STATE_ROLES = {
    "state_assertion",
    "state_transition",
    "milestone",
    "decision",
    "goal",
    "blocker",
    "observation",
    "statement",
    "unknown",
    "non_state",
}
STATE_ROLE_BY_EVENT_TYPE = {
    "state.changed": "state_transition",
    "status.updated": "state_assertion",
    "milestone.completed": "milestone",
    "decision.recorded": "decision",
    "goal.created": "goal",
    "blocker.detected": "blocker",
    "blocker.resolved": "blocker",
    "observation.recorded": "observation",
    "statement.recorded": "statement",
    "information.unknown": "unknown",
}
EPISTEMIC_WEIGHTS = {"explicit": 1.0, "derived": 0.85, "inferred": 0.5, "unknown": 0.0}


@dataclass(frozen=True)
class ContinuityPacketV2Policy:
    policy_id: str = CONTINUITY_V2_POLICY_ID
    packet_mode: str = "epistemic_continuity_v2"
    dynamics_mode: str = "temporal_memory_v1"
    signal_identity_mode: str = "exact_signal_v1"
    state_dimension_policy: str = "trusted_state_key_or_signal_v1"
    epistemic_weight_policy: str = "continuity_epistemic_weights_v1"
    provenance_policy: str = "exact_available_provenance_v2"
    conflict_policy: str = "preserve_open_no_winner_v1"
    entity_context_policy: str = "scope_linked_entities_only_v1"
    relationship_context_policy: str = "effective_scoped_relationships_v1"
    include_evidence_references: bool = True
    include_safe_evidence_previews: bool = False
    include_legacy_scores: bool = True
    include_temporal_metrics: bool = True
    include_governance_context: bool = True
    use_verified_consolidation: bool = True
    verify_accelerated_equivalence: bool = True
    maximum_packet_items: int = 10_000
    maximum_conflict_items: int = 1_000
    maximum_entity_items: int = 1_000
    maximum_relationship_items: int = 1_000
    policy_revision: str = CONTINUITY_V2_POLICY_REVISION

    def validate(self) -> None:
        if self.packet_mode not in PACKET_MODES:
            raise ContinuityPacketV2Error("CONTINUITY_V2_POLICY_INVALID", "Packet mode is invalid.")
        if self.signal_identity_mode not in SIGNAL_IDENTITY_MODES:
            raise ContinuityPacketV2Error("CONTINUITY_V2_POLICY_INVALID", "Signal identity mode is invalid.")
        for value in (
            self.maximum_packet_items,
            self.maximum_conflict_items,
            self.maximum_entity_items,
            self.maximum_relationship_items,
        ):
            if value < 1 or value > 100_000:
                raise ContinuityPacketV2Error("CONTINUITY_V2_POLICY_INVALID", "Packet item limit is invalid.")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def state_role(event_type: str, metadata: dict[str, object]) -> str:
    trusted = str(metadata.get("state_role") or "")
    if trusted in STATE_ROLES:
        return trusted
    return STATE_ROLE_BY_EVENT_TYPE.get(event_type, "non_state")


def epistemic_weight(status: str) -> float:
    return EPISTEMIC_WEIGHTS.get(status, 1.0 if status == "legacy_unclassified" else 0.0)


__all__ = [
    "CONTINUITY_V2_POLICY_ID",
    "CONTINUITY_V2_POLICY_REVISION",
    "ContinuityPacketV2Policy",
    "EPISTEMIC_WEIGHTS",
    "PACKET_MODES",
    "SIGNAL_IDENTITY_MODES",
    "STATE_ROLES",
    "epistemic_weight",
    "state_role",
]
