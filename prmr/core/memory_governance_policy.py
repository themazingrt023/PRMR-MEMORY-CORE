"""Versioned governance, export, retention, and authorisation policies."""

from __future__ import annotations

from dataclasses import dataclass
import re

from .memory_governance_models import (
    GovernanceActor,
    MemoryGovernanceActionType,
    MemoryGovernanceActorType,
    MemoryGovernanceError,
)


SAFE_TEXT = re.compile(r"[^A-Za-z0-9 .,:;_/@()+-]")
RETENTION_MODES = {
    "standard",
    "ephemeral",
    "retain_until",
    "indefinite",
    "governed",
}


@dataclass(frozen=True)
class MemoryGovernancePolicy:
    policy_id: str
    requires_plan: bool
    requires_approval: bool
    requires_pre_integrity: bool
    requires_post_verification: bool
    blocks_active_holds: bool
    delete_shared_dependencies: bool
    recompute_supported_shared: bool
    invalidate_unsupported_derived: bool
    preserve_safe_tombstone: bool
    read_only: bool = False


POLICIES = {
    "strict_governance_v1": MemoryGovernancePolicy(
        "strict_governance_v1", True, True, True, True, True, False, True, True, True
    ),
    "retention_expiry_v1": MemoryGovernancePolicy(
        "retention_expiry_v1", True, True, True, True, True, False, True, True, True
    ),
    "full_tenant_erasure_v1": MemoryGovernancePolicy(
        "full_tenant_erasure_v1", True, True, True, True, True, True, False, True, True
    ),
    "subject_export_v1": MemoryGovernancePolicy(
        "subject_export_v1", True, True, True, False, False, False, False, False, False, True
    ),
    "full_scope_export_v1": MemoryGovernancePolicy(
        "full_scope_export_v1", True, True, True, False, False, False, False, False, False, True
    ),
}


def governance_policy(policy_id: str) -> MemoryGovernancePolicy:
    try:
        return POLICIES[policy_id]
    except KeyError as exc:
        raise MemoryGovernanceError(
            "GOVERNANCE_ACTION_INVALID", "Unknown governance policy."
        ) from exc


def sanitise_governance_text(value: str, *, maximum: int = 500) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MemoryGovernanceError(
            "GOVERNANCE_REQUEST_CONFLICT", "A non-empty safe reason is required."
        )
    return SAFE_TEXT.sub("", value).strip()[:maximum]


def validate_actor(actor: GovernanceActor) -> GovernanceActor:
    allowed = {item.value for item in MemoryGovernanceActorType}
    if actor.actor_type not in allowed:
        raise MemoryGovernanceError(
            "GOVERNANCE_SCOPE_DENIED", "Governance actor type is not authorised."
        )
    reference = sanitise_governance_text(actor.actor_reference, maximum=120)
    return GovernanceActor(actor.actor_type, reference)


def validate_action_policy(action_type: str, policy_id: str) -> MemoryGovernancePolicy:
    allowed = {item.value for item in MemoryGovernanceActionType}
    if action_type not in allowed:
        raise MemoryGovernanceError(
            "GOVERNANCE_ACTION_INVALID", "Unsupported governance action."
        )
    policy = governance_policy(policy_id)
    if action_type == "export" and not policy.read_only:
        raise MemoryGovernanceError(
            "GOVERNANCE_ACTION_INVALID", "Export requires an export policy."
        )
    if action_type != "export" and policy.read_only:
        raise MemoryGovernanceError(
            "GOVERNANCE_ACTION_INVALID", "Read-only export policy cannot mutate memory."
        )
    return policy


__all__ = [
    "MemoryGovernancePolicy",
    "POLICIES",
    "RETENTION_MODES",
    "governance_policy",
    "sanitise_governance_text",
    "validate_action_policy",
    "validate_actor",
]
