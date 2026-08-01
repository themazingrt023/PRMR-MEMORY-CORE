"""Validation and deterministic planning for typed memory queries."""

from __future__ import annotations

import base64
from dataclasses import replace
from datetime import datetime, timezone
import json
from typing import Any

from .memory_query_models import (
    MEMORY_QUERY_PAGINATION_REVISION,
    MEMORY_QUERY_PLANNER_REVISION,
    ENTITY_TARGET_PATTERN,
    QUERY_ID_PATTERN,
    SIGNAL_KEY_PATTERN,
    MemoryQueryError,
    MemoryQueryMode,
    MemoryQueryPlan,
    MemoryQueryPolicy,
    MemoryQueryRequest,
    MemoryQueryType,
)
from .memory_query_policy import strict_query_policy
from .source_integrity import canonical_json, sha256_text
from .source_models import AuthenticatedScope


PHASES = frozenset({"active", "latent", "dormant", "decayed"})
EPISTEMIC_STATUSES = frozenset(
    {"explicit", "derived", "inferred", "unknown", "legacy_unclassified"}
)
REQUIRES_EVENT = frozenset({MemoryQueryType.EVIDENCE_FOR_EVENT.value})
REQUIRES_SIGNAL = frozenset({MemoryQueryType.SIGNAL_HISTORY.value})
REQUIRES_ENTITY = frozenset(
    {MemoryQueryType.ENTITY_STATE.value, MemoryQueryType.ENTITY_HISTORY.value}
)
REQUIRES_RELATIONSHIP = frozenset({MemoryQueryType.RELATIONSHIP_HISTORY.value})
REQUIRES_BOTH_BOUNDARIES = frozenset({MemoryQueryType.CHANGES_BETWEEN.value})
REQUIRES_VALID_AT = frozenset(
    {MemoryQueryType.STATE_AT_VALID_TIME.value, MemoryQueryType.BITEMPORAL_STATE.value}
)
REQUIRES_KNOWN_AT = frozenset(
    {MemoryQueryType.STATE_AS_KNOWN_AT.value, MemoryQueryType.BITEMPORAL_STATE.value}
)


def utc(value: str | None, *, default: str | None = None) -> str:
    raw = value or default
    if raw is None:
        raw = datetime.now(timezone.utc).isoformat()
    try:
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise MemoryQueryError(
            "MEMORY_QUERY_TEMPORAL_BOUNDARY_INVALID",
            "A temporal boundary is invalid.",
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def scope_fingerprint(scope: AuthenticatedScope) -> str:
    return sha256_text(canonical_json(scope.memory_boundary()))[:24]


def _cursor_signature(payload: dict[str, Any]) -> str:
    return sha256_text(
        canonical_json(
            {
                **payload,
                "pagination_revision": MEMORY_QUERY_PAGINATION_REVISION,
            }
        )
    )


def encode_query_cursor(
    scope: AuthenticatedScope,
    query_type: str,
    base_query_hash: str,
    offset: int,
) -> str:
    payload = {
        "scope_fingerprint": scope_fingerprint(scope),
        "query_type": query_type,
        "base_query_hash": base_query_hash,
        "offset": int(offset),
        "revision": MEMORY_QUERY_PAGINATION_REVISION,
    }
    envelope = {"payload": payload, "signature": _cursor_signature(payload)}
    return base64.urlsafe_b64encode(canonical_json(envelope).encode("utf-8")).decode(
        "ascii"
    )


def decode_query_cursor(
    cursor: str,
    scope: AuthenticatedScope,
    query_type: str,
    base_query_hash: str,
) -> int:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
        envelope = json.loads(raw)
        payload = dict(envelope["payload"])
        signature = str(envelope["signature"])
        offset = int(payload["offset"])
    except (ValueError, TypeError, KeyError, json.JSONDecodeError, UnicodeError) as exc:
        raise MemoryQueryError(
            "MEMORY_QUERY_CURSOR_INVALID", "The query cursor is invalid."
        ) from exc
    if signature != _cursor_signature(payload) or offset < 0:
        raise MemoryQueryError(
            "MEMORY_QUERY_CURSOR_INVALID", "The query cursor is invalid."
        )
    if payload.get("scope_fingerprint") != scope_fingerprint(scope):
        raise MemoryQueryError(
            "MEMORY_QUERY_CURSOR_SCOPE_MISMATCH",
            "The query cursor does not belong to the authenticated scope.",
        )
    if (
        payload.get("query_type") != query_type
        or payload.get("base_query_hash") != base_query_hash
        or payload.get("revision") != MEMORY_QUERY_PAGINATION_REVISION
    ):
        raise MemoryQueryError(
            "MEMORY_QUERY_CURSOR_INVALID", "The query cursor does not match this query."
        )
    return offset


class MemoryQueryPlanner:
    """Produce a deterministic, read-only execution plan."""

    def plan(
        self,
        authenticated_scope: AuthenticatedScope,
        query_request: MemoryQueryRequest,
        *,
        policy: MemoryQueryPolicy | None = None,
        frozen_now: str | None = None,
    ) -> tuple[MemoryQueryRequest, MemoryQueryPolicy, MemoryQueryPlan]:
        if not isinstance(authenticated_scope, AuthenticatedScope) or not all(
            authenticated_scope.memory_boundary()
        ):
            raise MemoryQueryError(
                "MEMORY_QUERY_SCOPE_DENIED", "Authenticated memory scope is required."
            )
        try:
            query_type = MemoryQueryType(query_request.query_type).value
        except ValueError as exc:
            raise MemoryQueryError(
                "MEMORY_QUERY_TYPE_INVALID", "The memory query type is not supported."
            ) from exc
        if query_request.query_mode != MemoryQueryMode.DETERMINISTIC_STRICT_V1.value:
            raise MemoryQueryError(
                "MEMORY_QUERY_SEMANTIC_MODE_UNAVAILABLE",
                "Only deterministic_strict_v1 is available in this sprint.",
            )
        self._assert_scope(authenticated_scope, query_request)
        selected_policy = strict_query_policy(query_request, policy)
        self._validate_required(query_type, query_request)
        self._validate_filters(query_request)

        now = utc(frozen_now)
        valid_at = utc(query_request.valid_at, default=now)
        known_at = utc(query_request.known_at, default=now)
        first = self._boundary(query_request.first_temporal_boundary)
        second = self._boundary(query_request.second_temporal_boundary)
        if query_type in REQUIRES_BOTH_BOUNDARIES:
            if not first or not second:
                raise MemoryQueryError(
                    "MEMORY_QUERY_REQUEST_INVALID",
                    "changes_between requires two temporal boundaries.",
                )
            if (first["valid_at"], first["known_at"]) > (
                second["valid_at"],
                second["known_at"],
            ):
                raise MemoryQueryError(
                    "MEMORY_QUERY_TEMPORAL_BOUNDARY_INVALID",
                    "The first boundary must not be later than the second boundary.",
                )
        resolved = replace(
            query_request.resolved_scope(*authenticated_scope.memory_boundary()),
            query_type=query_type,
            application_reference=(
                authenticated_scope.application_reference
                or query_request.application_reference
            ),
            actor_reference=(
                authenticated_scope.actor_reference or query_request.actor_reference
            ),
            workspace_reference=(
                authenticated_scope.workspace_reference
                or query_request.workspace_reference
            ),
            session_reference=(
                authenticated_scope.session_reference
                or query_request.session_reference
            ),
            valid_at=valid_at,
            known_at=known_at,
            first_temporal_boundary=first,
            second_temporal_boundary=second,
        )
        normalised = resolved.to_dict()
        normalised["cursor"] = None
        normalised["maximum_results"] = selected_policy.maximum_results
        normalised["maximum_evidence_items"] = selected_policy.maximum_evidence_items
        normalised["include_evidence"] = selected_policy.include_evidence
        normalised["include_safe_evidence_preview"] = (
            selected_policy.include_safe_evidence_preview
        )
        normalised["include_packet"] = selected_policy.include_packet
        normalised["include_explanation"] = selected_policy.include_explanation
        normalised["include_conflicted"] = selected_policy.include_conflicted
        normalised = _normalise_lists(normalised)
        base_query_hash = sha256_text(
            canonical_json(
                {
                    "scope": authenticated_scope.memory_boundary(),
                    "query": normalised,
                    "policy": selected_policy.to_dict(),
                    "pagination_revision": MEMORY_QUERY_PAGINATION_REVISION,
                }
            )
        )
        offset = (
            decode_query_cursor(
                query_request.cursor,
                authenticated_scope,
                query_type,
                base_query_hash,
            )
            if query_request.cursor
            else 0
        )
        normalised["cursor_offset"] = offset
        normalised["base_query_hash"] = base_query_hash
        required_services = self._services(query_type, selected_policy)
        steps = self._steps(query_type, required_services, selected_policy)
        plan_material = {
            "query_type": query_type,
            "query_mode": resolved.query_mode,
            "policy": selected_policy.to_dict(),
            "normalised_query_payload": normalised,
            "required_services": required_services,
            "steps": steps,
            "planner_revision": MEMORY_QUERY_PLANNER_REVISION,
        }
        plan_hash = sha256_text(canonical_json(plan_material))
        plan = MemoryQueryPlan(
            query_type=query_type,
            query_mode=resolved.query_mode,
            query_policy_id=selected_policy.policy_id,
            valid_at=valid_at,
            known_at=known_at,
            required_services=required_services,
            integrity_dependencies=self._integrity_dependencies(required_services),
            evidence_required=selected_policy.include_evidence,
            explanation_required=selected_policy.include_explanation,
            packet_required=(
                selected_policy.include_packet
                or query_type
                in {
                    MemoryQueryType.CURRENT_STATE.value,
                    MemoryQueryType.RECOVERABILITY_EXPLANATION.value,
                    MemoryQueryType.CONTINUITY_PACKET.value,
                }
            ),
            maximum_results=selected_policy.maximum_results,
            maximum_evidence_items=selected_policy.maximum_evidence_items,
            cursor_offset=offset,
            plan_steps=steps,
            normalised_query_payload=normalised,
            query_plan_hash_sha256=plan_hash,
        )
        return resolved, selected_policy, plan

    @staticmethod
    def _assert_scope(scope: AuthenticatedScope, request: MemoryQueryRequest) -> None:
        for asserted, actual in (
            (request.client_id, scope.client_id),
            (request.vault_id, scope.vault_id),
            (request.namespace, scope.namespace),
            (request.application_reference, scope.application_reference),
            (request.actor_reference, scope.actor_reference),
            (request.workspace_reference, scope.workspace_reference),
            (request.session_reference, scope.session_reference),
        ):
            if asserted is not None and actual is not None and asserted != actual:
                raise MemoryQueryError(
                    "MEMORY_QUERY_SCOPE_DENIED",
                    "Requested scope conflicts with authenticated scope.",
                )

    @staticmethod
    def _validate_required(query_type: str, request: MemoryQueryRequest) -> None:
        if query_type in REQUIRES_EVENT and not request.event_id:
            raise MemoryQueryError(
                "MEMORY_QUERY_REQUEST_INVALID", "This query requires event_id."
            )
        if query_type in REQUIRES_SIGNAL and not request.signal_key:
            raise MemoryQueryError(
                "MEMORY_QUERY_REQUEST_INVALID", "This query requires signal_key."
            )
        if query_type in REQUIRES_ENTITY and not request.entity_id:
            raise MemoryQueryError(
                "MEMORY_QUERY_REQUEST_INVALID", "This query requires entity_id."
            )
        if query_type in REQUIRES_RELATIONSHIP and not request.relationship_id:
            raise MemoryQueryError(
                "MEMORY_QUERY_REQUEST_INVALID", "This query requires relationship_id."
            )
        if query_type in REQUIRES_VALID_AT and not request.valid_at:
            raise MemoryQueryError(
                "MEMORY_QUERY_REQUEST_INVALID", "This query requires valid_at."
            )
        if query_type in REQUIRES_KNOWN_AT and not request.known_at:
            raise MemoryQueryError(
                "MEMORY_QUERY_REQUEST_INVALID", "This query requires known_at."
            )
        if query_type == MemoryQueryType.MEMORY_BY_PHASE.value:
            if not request.memory_phase_filter:
                raise MemoryQueryError(
                    "MEMORY_QUERY_REQUEST_INVALID",
                    "memory_by_phase requires a phase filter.",
                )
        if query_type == MemoryQueryType.RELATIONSHIP_STATE.value and not (
            request.relationship_id
            or request.entity_id
            or request.relationship_type_filter
        ):
            raise MemoryQueryError(
                "MEMORY_QUERY_REQUEST_INVALID",
                "relationship_state requires a relationship or entity target.",
            )

    @staticmethod
    def _validate_filters(request: MemoryQueryRequest) -> None:
        if request.entity_id and not ENTITY_TARGET_PATTERN.fullmatch(
            request.entity_id
        ):
            raise MemoryQueryError(
                "MEMORY_QUERY_REQUEST_INVALID",
                "A query target identifier is invalid.",
            )
        for value, code in (
            (request.event_id, "MEMORY_QUERY_REQUEST_INVALID"),
            (request.relationship_id, "MEMORY_QUERY_REQUEST_INVALID"),
            (request.conflict_id, "MEMORY_QUERY_REQUEST_INVALID"),
            (request.source_id, "MEMORY_QUERY_REQUEST_INVALID"),
            (request.candidate_id, "MEMORY_QUERY_REQUEST_INVALID"),
            (request.admission_id, "MEMORY_QUERY_REQUEST_INVALID"),
            (request.packet_id, "MEMORY_QUERY_REQUEST_INVALID"),
            (request.reconstruction_id, "MEMORY_QUERY_REQUEST_INVALID"),
            (request.dynamics_snapshot_id, "MEMORY_QUERY_REQUEST_INVALID"),
        ):
            if value and not QUERY_ID_PATTERN.fullmatch(value):
                raise MemoryQueryError(code, "A query target identifier is invalid.")
        if request.signal_key and not SIGNAL_KEY_PATTERN.fullmatch(request.signal_key):
            raise MemoryQueryError(
                "MEMORY_QUERY_SIGNAL_INVALID", "The exact signal key is invalid."
            )
        if any(item not in PHASES for item in request.memory_phase_filter):
            raise MemoryQueryError(
                "MEMORY_QUERY_REQUEST_INVALID", "A memory phase filter is invalid."
            )
        if any(
            item not in EPISTEMIC_STATUSES
            for item in request.epistemic_status_filter
        ):
            raise MemoryQueryError(
                "MEMORY_QUERY_REQUEST_INVALID", "An epistemic filter is invalid."
            )

    @staticmethod
    def _boundary(value: dict[str, str | None] | None) -> dict[str, str] | None:
        if value is None:
            return None
        if not isinstance(value, dict) or not value.get("valid_at") or not value.get(
            "known_at"
        ):
            raise MemoryQueryError(
                "MEMORY_QUERY_TEMPORAL_BOUNDARY_INVALID",
                "A complete temporal boundary requires valid_at and known_at.",
            )
        return {"valid_at": utc(value["valid_at"]), "known_at": utc(value["known_at"])}

    @staticmethod
    def _services(query_type: str, policy: MemoryQueryPolicy) -> list[str]:
        services = ["MemoryStateResolver"]
        if query_type not in {
            MemoryQueryType.EVIDENCE_FOR_EVENT.value,
            MemoryQueryType.PROVENANCE_TRACE.value,
        }:
            services.append("MemoryDynamicsEngine")
        if query_type in {
            MemoryQueryType.CHANGES_BETWEEN.value,
            MemoryQueryType.STATE_AS_KNOWN_AT.value,
            MemoryQueryType.STATE_AT_VALID_TIME.value,
            MemoryQueryType.BITEMPORAL_STATE.value,
        }:
            services.append("MemoryReconstructionService")
        if query_type in {
            MemoryQueryType.ENTITY_STATE.value,
            MemoryQueryType.ENTITY_HISTORY.value,
        }:
            services.extend(["EntityResolver", "EntityMemoryService"])
        if query_type in {
            MemoryQueryType.RELATIONSHIP_STATE.value,
            MemoryQueryType.RELATIONSHIP_HISTORY.value,
            MemoryQueryType.OPEN_CONFLICTS.value,
            MemoryQueryType.RESOLVED_CONFLICTS.value,
        }:
            services.append("RelationshipMemoryService")
        if policy.include_evidence or query_type.startswith("evidence_"):
            services.extend(["MemoryAdmissionService", "SourceLedger"])
        return sorted(set(services))

    @staticmethod
    def _integrity_dependencies(services: list[str]) -> list[str]:
        mapping = {
            "MemoryStateResolver": "resolved_event_manifest",
            "MemoryDynamicsEngine": "dynamics_snapshot",
            "MemoryReconstructionService": "reconstruction",
            "EntityResolver": "entity_identity",
            "EntityMemoryService": "entity_view",
            "RelationshipMemoryService": "relationship_manifest",
            "MemoryAdmissionService": "admission_origin",
            "SourceLedger": "source_integrity",
        }
        return [mapping[item] for item in services if item in mapping]

    @staticmethod
    def _steps(
        query_type: str, services: list[str], policy: MemoryQueryPolicy
    ) -> list[dict[str, Any]]:
        return [
            {
                "step_type": "scope_resolved",
                "revision": MEMORY_QUERY_PLANNER_REVISION,
                "reason": "Authenticated scope is authoritative.",
            },
            {
                "step_type": "temporal_boundary_applied",
                "revision": MEMORY_QUERY_PLANNER_REVISION,
                "reason": "One valid-time and known-time boundary is frozen.",
            },
            {
                "step_type": "effective_events_resolved",
                "revision": MEMORY_QUERY_PLANNER_REVISION,
                "reason": f"Authoritative services selected for {query_type}.",
                "services": services,
            },
            {
                "step_type": "evidence_loaded",
                "revision": MEMORY_QUERY_PLANNER_REVISION,
                "reason": (
                    "Exact provenance requested."
                    if policy.include_evidence
                    else "Evidence loading disabled by policy."
                ),
            },
        ]


def _normalise_lists(payload: dict[str, Any]) -> dict[str, Any]:
    output = dict(payload)
    for key in (
        "memory_phase_filter",
        "epistemic_status_filter",
        "event_type_filter",
        "relationship_type_filter",
    ):
        output[key] = sorted(set(str(item) for item in output.get(key, [])))
    return output


__all__ = [
    "MemoryQueryPlanner",
    "decode_query_cursor",
    "encode_query_cursor",
    "scope_fingerprint",
    "utc",
]
