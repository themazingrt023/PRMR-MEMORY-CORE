"""Controlled-alpha HTTP-style API surface for PRMR Memory Core V0.71.

This module exposes local callable endpoint handlers. It is deployable-shaped,
but it is not a live hosted API unless separately deployed and smoke-tested.
"""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any
from uuid import uuid4

from prmr.product.api_key_lifecycle_v070 import PRMRAPIKeyLifecycle
from prmr.product.hosted_backend_foundation_v069 import utc_now


BOUNDARY_V071 = (
    "V0.71 is a local/deployable controlled-alpha API surface only. Unless "
    "actually hosted and smoke-tested, it is not live hosted API access, not "
    "production onboarding, not billing, not self-serve signup, not external "
    "validation, not bank approval, not compliance approval, not legal approval, "
    "not external security certification, and not real-world validation."
)

ENDPOINTS = [
    "POST /v1/events/ingest",
    "POST /v1/continuity/packet",
    "POST /v1/memory/reconstruct",
    "POST /v1/explain",
    "POST /v1/actions/least-harm",
    "GET /v1/reports/{report_id}",
    "GET /v1/usage",
]

PUBLIC_FORBIDDEN_TERMS = [
    "raw_api_key",
    "full_api_key",
    "private_internal",
    "key_hash",
    "validation_outcomes",
    "debug",
    "private_trace",
]

UNSAFE_PUBLIC_LANGUAGE = [
    "fraudster",
    "criminal",
    "guilty",
    "definitely fraud",
    "blacklist",
    "close account immediately",
]

UNSAFE_METADATA_TERMS = [
    "authorization",
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "token",
    "secret",
    "password",
    "credential",
    "private_key",
    "card_number",
    "payment_card",
    "database_url",
    "service_role",
    "file_contents",
    "raw_file",
    "file_path",
    "filepath",
    "local_path",
    "absolute_path",
    "raw_path",
]

ENTITY_SCOPE_FIELDS = [
    "application_reference",
    "actor_reference",
    "workspace_reference",
    "entity_reference",
    "session_reference",
]
USABLE_ENTITY_SCOPE_FIELDS = [
    "application_reference",
    "actor_reference",
    "workspace_reference",
    "entity_reference",
]
ALGORITHM_REVISION = "prmr_packet_entity_scope_v1"
PACKET_VERSION = "v1.entity_scope"


@dataclass
class APIRequestLog:
    timestamp: str
    endpoint: str
    client_id: str
    vault_id: str
    namespace: str
    status: str
    reason: str
    public_safe_message: str


class PRMRControlledAlphaAPI:
    """Local HTTP-style controlled-alpha API surface."""

    def __init__(self) -> None:
        self.lifecycle = PRMRAPIKeyLifecycle()
        self.events: dict[str, list[dict[str, Any]]] = {}
        self.packets: dict[str, dict[str, Any]] = {}
        self.public_reports: dict[str, dict[str, Any]] = {}
        self.private_reports: dict[str, dict[str, Any]] = {}
        self.api_request_log: list[APIRequestLog] = []

    def scope_key(self, client_id: str, vault_id: str, namespace: str) -> str:
        return f"{client_id}::{vault_id}::{namespace}"

    def setup_synthetic_client(
        self,
        *,
        client_id: str = "client_v071_synthetic_alpha",
        vault_id: str = "vault_v071_alpha",
        namespace: str = "default",
        usage_limit_id: str = "limit_v071_alpha",
    ) -> dict[str, Any]:
        client = self.lifecycle.create_client(
            organisation="Synthetic V0.71 Alpha Client",
            contact_email="synthetic-v071@example.test",
            client_id=client_id,
        )
        limit = self.lifecycle.create_usage_limit(
            usage_limit_id=usage_limit_id,
            max_events_per_day=3,
            max_packets_per_day=4,
            max_reports_per_day=3,
            alpha_limit_reason="V0.71 local controlled-alpha API usage limit.",
        )
        vault = self.lifecycle.create_vault(client.client_id, vault_id=vault_id)
        namespace_record = self.lifecycle.create_namespace(client.client_id, vault.vault_id, namespace=namespace)
        issue = self.lifecycle.issue_alpha_key(
            client_id=client.client_id,
            vault_id=vault.vault_id,
            namespace=namespace_record.namespace,
            usage_limit_id=limit.usage_limit_id,
            operator_id="operator_v071_founder",
            approval_reason="approved for synthetic controlled-alpha API test",
        )
        return {
            "client": client,
            "vault": vault,
            "namespace": namespace_record,
            "usage_limit": limit,
            "issue": issue,
            "raw_api_key": issue["raw_api_key"],
        }

    def auth_context(self, request_payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "client_id": str(request_payload.get("client_id", "")),
            "vault_id": str(request_payload.get("vault_id", "")),
            "namespace": str(request_payload.get("namespace", "")),
            "raw_api_key": request_payload.get("api_key"),
        }

    def response(self, status_code: int, payload: dict[str, Any]) -> dict[str, Any]:
        return {"status_code": status_code, "body": payload}

    def public_error(self, decision: Any, endpoint: str, context: dict[str, Any]) -> dict[str, Any]:
        self.api_request_log.append(
            APIRequestLog(
                timestamp=utc_now(),
                endpoint=endpoint,
                client_id=context.get("client_id", ""),
                vault_id=context.get("vault_id", ""),
                namespace=context.get("namespace", ""),
                status="blocked",
                reason=decision.reason,
                public_safe_message=decision.public_safe_message,
            )
        )
        return self.response(
            decision.status_code,
            {
                "status": "error",
                "error": {
                    "code": decision.reason,
                    "message": decision.public_safe_message,
                },
                "public_safe": True,
                "boundary": BOUNDARY_V071,
            },
        )

    def public_ok(self, endpoint: str, context: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        self.api_request_log.append(
            APIRequestLog(
                timestamp=utc_now(),
                endpoint=endpoint,
                client_id=context["client_id"],
                vault_id=context["vault_id"],
                namespace=context["namespace"],
                status="ok",
                reason="allowed",
                public_safe_message="Request completed for scoped controlled-alpha client.",
            )
        )
        return self.response(
            200,
            {
                "status": "ok",
                "client_id": context["client_id"],
                "vault_id": context["vault_id"],
                "namespace": context["namespace"],
                "public_safe": True,
                **payload,
            },
        )

    def require_access(self, endpoint: str, request_payload: dict[str, Any], operation: str, count: int = 1):
        context = self.auth_context(request_payload)
        decision = self.lifecycle.validate_key(
            client_id=context["client_id"],
            raw_api_key=context["raw_api_key"],
            vault_id=context["vault_id"],
            namespace=context["namespace"],
            operation=operation,
            count=count,
        )
        if not decision.allowed:
            return context, self.public_error(decision, endpoint, context)
        return context, None

    def events_ingest(self, request_payload: dict[str, Any]) -> dict[str, Any]:
        endpoint = "POST /v1/events/ingest"
        events = self.event_batch_from_payload(request_payload)
        count = len(events) if isinstance(events, list) else 1
        context, error = self.require_access(endpoint, request_payload, "events_ingest", count=count)
        if error:
            return error
        if not isinstance(events, list) or not events:
            return self.response(400, {"status": "error", "error": {"code": "payload_invalid", "message": "events must be a non-empty list."}, "public_safe": True})

        scope = self.scope_key(context["client_id"], context["vault_id"], context["namespace"])
        existing_event_ids = {str(event.get("event_id", "")) for event in self.events.get(scope, [])}
        safe_events = []
        duplicate_events = []
        for index, event in enumerate(events):
            if not isinstance(event, dict):
                return self.response(400, {"status": "error", "error": {"code": "payload_invalid", "message": "each event must be an object."}, "public_safe": True})
            normalized, normalize_error = self.normalize_event(event, index)
            if normalize_error:
                return self.response(400, {"status": "error", "error": {"code": "payload_invalid", "message": normalize_error}, "public_safe": True})
            if str(normalized.get("event_id", "")) in existing_event_ids:
                duplicate_events.append(
                    {
                        "event_id": str(normalized.get("event_id", "")),
                        "status": "duplicate_ignored",
                        "reason": "idempotency_key_or_event_id_already_exists_in_authorized_scope",
                    }
                )
                continue
            existing_event_ids.add(str(normalized.get("event_id", "")))
            safe_events.append(normalized)
        self.events.setdefault(scope, []).extend(safe_events)
        return self.public_ok(
            endpoint,
            context,
            {
                "accepted_event_count": len(safe_events),
                "duplicate_event_count": len(duplicate_events),
                "duplicates": duplicate_events[:50],
                "total_event_count": len(self.events[scope]),
                "summary": "Events accepted into the scoped PRMR namespace.",
            },
        )

    def event_batch_from_payload(self, request_payload: dict[str, Any]) -> Any:
        events = request_payload.get("events")
        if isinstance(events, list):
            return events
        external_keys = {
            "event_type",
            "signal",
            "metadata",
            "occurred_at",
            "application_reference",
            "actor_reference",
            "workspace_reference",
            "entity_reference",
            "session_reference",
            "idempotency_key",
            "summary",
            "type",
            "content",
        }
        if any(key in request_payload for key in external_keys):
            return [
                {
                    key: value
                    for key, value in request_payload.items()
                    if key not in {"api_key", "client_id", "vault_id", "namespace"}
                }
            ]
        return events

    def normalize_event(self, event: dict[str, Any], index: int) -> tuple[dict[str, Any], str | None]:
        event_type = event.get("event_type")
        signal = event.get("signal")
        occurred_at = event.get("occurred_at")
        application_reference = event.get("application_reference")
        actor_reference = event.get("actor_reference")
        workspace_reference = event.get("workspace_reference")
        entity_reference = event.get("entity_reference")
        session_reference = event.get("session_reference")
        idempotency_key = event.get("idempotency_key")
        raw_timestamp_index = event.get("timestamp_index", index + 1)
        try:
            timestamp_index = int(raw_timestamp_index)
        except (TypeError, ValueError):
            return {}, "timestamp_index must be an integer when provided."

        external_metadata = self.safe_external_metadata(event)
        normalized = {
            "event_id": str(event.get("event_id") or idempotency_key or f"evt_{uuid4().hex[:12]}")[:120],
            "user_id": str(event.get("user_id") or actor_reference or "synthetic_user")[:120],
            "type": str(event.get("type") or event_type or "memory_event")[:120],
            "content": str(event.get("content") or signal or event.get("summary") or "")[:1200],
            "timestamp": str(event.get("timestamp") or occurred_at or utc_now())[:120],
            "timestamp_index": timestamp_index,
            "synthetic": True,
            "application_reference": self.clean_scope_reference(application_reference),
            "actor_reference": self.clean_scope_reference(actor_reference),
            "workspace_reference": self.clean_scope_reference(workspace_reference),
            "entity_reference": self.clean_scope_reference(entity_reference),
            "session_reference": self.clean_scope_reference(session_reference),
        }
        if external_metadata:
            normalized["external_metadata"] = external_metadata
        return normalized, None

    def safe_external_metadata(self, event: dict[str, Any]) -> dict[str, Any]:
        preserved: dict[str, Any] = {}
        for source_key, target_key in [
            ("metadata", "metadata"),
            ("source_app", "source_app"),
            ("application_reference", "application_reference"),
            ("workspace_reference", "workspace_reference"),
            ("actor_reference", "actor_reference"),
            ("entity_reference", "entity_reference"),
            ("session_reference", "session_reference"),
            ("idempotency_key", "idempotency_key"),
            ("event_type", "external_event_type"),
            ("occurred_at", "occurred_at"),
        ]:
            if source_key in event:
                preserved[target_key] = self.sanitize_metadata_value(event[source_key])
        unknown = {
            key: value
            for key, value in event.items()
            if key
            not in {
                "event_id",
                "user_id",
                "type",
                "content",
                "timestamp",
                "timestamp_index",
                "synthetic",
                "metadata",
                "source_app",
                "application_reference",
                "workspace_reference",
                "actor_reference",
                "entity_reference",
                "session_reference",
                "idempotency_key",
                "event_type",
                "occurred_at",
                "signal",
                "summary",
            }
        }
        if unknown:
            preserved["unknown_fields"] = self.sanitize_metadata_value(unknown)
        return preserved

    def sanitize_metadata_value(self, value: Any, depth: int = 0) -> Any:
        if depth > 4:
            return "[redacted_depth_limit]"
        if isinstance(value, dict):
            safe: dict[str, Any] = {}
            for key, item in value.items():
                clean_key = str(key)[:120]
                if self.unsafe_metadata_key(clean_key):
                    safe[clean_key] = "[redacted]"
                else:
                    safe[clean_key] = self.sanitize_metadata_value(item, depth + 1)
            return safe
        if isinstance(value, list):
            return [self.sanitize_metadata_value(item, depth + 1) for item in value[:50]]
        if isinstance(value, (str, int, float, bool)) or value is None:
            if isinstance(value, str):
                if self.looks_sensitive_metadata_value(value):
                    return "[redacted]"
                return value[:500]
            return value
        return str(value)[:500]

    def unsafe_metadata_key(self, key: str) -> bool:
        lowered = key.lower()
        return any(term in lowered for term in UNSAFE_METADATA_TERMS)

    def looks_sensitive_metadata_value(self, value: str) -> bool:
        lowered = value.lower()
        if "authorization:" in lowered or "bearer " in lowered:
            return True
        if "postgres://" in lowered or "postgresql://" in lowered:
            return True
        if "sk-" in value or "github_pat_" in value or "ghp_" in value:
            return True
        if "prmr_alpha_" in value or "prmr_live_" in value:
            return True
        return False

    def clean_scope_reference(self, value: Any) -> str:
        if value is None:
            return ""
        text = " ".join(str(value).split()).strip()
        if not text or self.looks_sensitive_metadata_value(text):
            return ""
        return text[:160]

    def continuity_packet(self, request_payload: dict[str, Any]) -> dict[str, Any]:
        endpoint = "POST /v1/continuity/packet"
        context, error = self.require_access(endpoint, request_payload, "continuity_packet")
        if error:
            return error
        return self.create_continuity_packet_response(endpoint, context, request_payload)

    def create_continuity_packet_response(
        self,
        endpoint: str,
        context: dict[str, Any],
        request_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        scope = self.scope_key(context["client_id"], context["vault_id"], context["namespace"])
        namespace_events = self.events.get(scope, [])
        entity_scope = self.requested_entity_scope(request_payload or {})
        filtered_events, excluded_events, scope_error = self.events_for_requested_scope(
            namespace_events,
            entity_scope,
            allow_broad_scope=bool((request_payload or {}).get("allow_broad_scope")),
        )
        if scope_error:
            return self.response(
                400,
                {
                    "status": "error",
                    "error": {
                        "code": "entity_scope_required",
                        "message": scope_error,
                        "fields": {
                            "application_reference": "Optional but recommended application scope.",
                            "actor_reference": "Provide to request an actor-scoped packet.",
                            "workspace_reference": "Provide to request a workspace-scoped packet.",
                            "entity_reference": "Provide to request an entity-scoped packet.",
                        },
                        "retryable": False,
                    },
                    "public_safe": True,
                    "packet_version": PACKET_VERSION,
                    "algorithm_revision": ALGORITHM_REVISION,
                },
            )

        previous_packet = self.previous_packet_for_scope(context, entity_scope)
        packet_id = self.deterministic_packet_id(context, entity_scope, filtered_events)
        packet = {
            **self.build_theory_packet(filtered_events),
            "packet_id": packet_id,
            "report_id": f"report_{packet_id.removeprefix('packet_')}",
            "client_id": context["client_id"],
            "vault_id": context["vault_id"],
            "namespace": context["namespace"],
            **entity_scope,
            "scope_mode": self.scope_mode(entity_scope, namespace_events),
            "source_event_count": len(filtered_events),
            "first_event_at": str(filtered_events[0].get("timestamp", "")) if filtered_events else None,
            "packet_version": PACKET_VERSION,
            "algorithm_revision": ALGORITHM_REVISION,
            "provenance": self.packet_provenance(
                filtered_events,
                excluded_events,
                entity_scope,
                previous_packet,
            ),
            "public_safe": True,
        }
        packet["report_id"] = str(packet["report_id"])
        packet["provenance"]["packet_reproducible"] = True
        packet["provenance"]["deterministic_packet_hash"] = packet_id.removeprefix("packet_")
        self.packets[packet_id] = packet
        report_id = packet["report_id"]
        public_report = {
            "report_id": report_id,
            "packet_id": packet_id,
            "client_id": context["client_id"],
            "vault_id": context["vault_id"],
            "namespace": context["namespace"],
            **entity_scope,
            "summary": "Public-safe continuity report generated from scoped application events.",
            "event_count": len(filtered_events),
            "source_event_count": len(filtered_events),
            "packet_version": PACKET_VERSION,
            "algorithm_revision": ALGORITHM_REVISION,
            "public_safe": True,
            "boundary": BOUNDARY_V071,
        }
        private_report = {
            **public_report,
            "public_safe": False,
            "event_trace": filtered_events,
            "excluded_event_summary": self.safe_excluded_event_summary(excluded_events),
            "private_note": "Private report contains scoped sanitized event trace only; no raw API keys are persisted.",
        }
        self.public_reports[report_id] = public_report
        self.private_reports[report_id] = private_report
        return self.public_ok(
            endpoint,
            context,
            {
                "packet_id": packet_id,
                "report_id": report_id,
                "summary": packet["summary"],
                **packet,
                "packet": packet,
            },
        )

    def requested_entity_scope(self, request_payload: dict[str, Any]) -> dict[str, str]:
        return {
            field: self.clean_scope_reference(request_payload.get(field))
            for field in ENTITY_SCOPE_FIELDS
        }

    def event_has_any_scope(self, event: dict[str, Any]) -> bool:
        return any(str(event.get(field, "")).strip() for field in USABLE_ENTITY_SCOPE_FIELDS)

    def event_matches_scope(self, event: dict[str, Any], entity_scope: dict[str, str]) -> bool:
        for field, requested in entity_scope.items():
            if requested and str(event.get(field, "")) != requested:
                return False
        return True

    def events_for_requested_scope(
        self,
        events: list[dict[str, Any]],
        entity_scope: dict[str, str],
        *,
        allow_broad_scope: bool = False,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str | None]:
        has_requested_scope = any(entity_scope.get(field) for field in USABLE_ENTITY_SCOPE_FIELDS)
        has_scoped_events = any(self.event_has_any_scope(event) for event in events)
        if not has_requested_scope:
            if has_scoped_events:
                return [], self.safe_excluded_event_summary(events), (
                    "At least one of application_reference, actor_reference, workspace_reference, "
                    "or entity_reference is required when scoped application events exist. "
                    "Namespace-wide packet generation is disabled to avoid accidental global memory mixing."
                )
            return list(events), [], None

        included = [event for event in events if self.event_matches_scope(event, entity_scope)]
        excluded = [
            {
                "event_id": str(event.get("event_id", "")),
                "event_type": self.event_signal(event),
                "reason": self.exclusion_reason(event, entity_scope),
            }
            for event in events
            if not self.event_matches_scope(event, entity_scope)
        ]
        broad_fields = [
            field
            for field in ["actor_reference", "workspace_reference", "entity_reference"]
            if not entity_scope.get(field)
            and len({str(event.get(field, "")) for event in included if str(event.get(field, "")).strip()}) > 1
        ]
        if broad_fields and not allow_broad_scope:
            return [], excluded, (
                "The requested scope matches multiple "
                f"{', '.join(broad_fields)} values. Set allow_broad_scope=true to explicitly request this broader packet."
            )
        return included, excluded, None

    def exclusion_reason(self, event: dict[str, Any], entity_scope: dict[str, str]) -> str:
        mismatches = [
            field
            for field, requested in entity_scope.items()
            if requested and str(event.get(field, "")) != requested
        ]
        return "scope_mismatch:" + ",".join(mismatches) if mismatches else "not_excluded"

    def scope_mode(self, entity_scope: dict[str, str], namespace_events: list[dict[str, Any]]) -> str:
        if any(entity_scope.get(field) for field in USABLE_ENTITY_SCOPE_FIELDS):
            return "entity_scoped"
        if any(self.event_has_any_scope(event) for event in namespace_events):
            return "blocked_global_scope"
        return "legacy_namespace_scope"

    def deterministic_packet_id(
        self,
        context: dict[str, Any],
        entity_scope: dict[str, str],
        events: list[dict[str, Any]],
    ) -> str:
        material = {
            "algorithm_revision": ALGORITHM_REVISION,
            "client_id": context["client_id"],
            "vault_id": context["vault_id"],
            "namespace": context["namespace"],
            "entity_scope": entity_scope,
            "source_event_ids": [str(event.get("event_id", "")) for event in events],
            "source_event_versions": [
                [
                    str(event.get("event_id", "")),
                    str(event.get("type", "")),
                    str(event.get("timestamp", "")),
                    str(event.get("timestamp_index", "")),
                    str(event.get("content", "")),
                ]
                for event in events
            ],
        }
        digest = hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        return f"packet_{digest[:24]}"

    def previous_packet_for_scope(self, context: dict[str, Any], entity_scope: dict[str, str]) -> dict[str, Any] | None:
        candidates = [
            packet
            for packet in self.packets.values()
            if packet.get("client_id") == context["client_id"]
            and packet.get("vault_id") == context["vault_id"]
            and packet.get("namespace") == context["namespace"]
            and all(str(packet.get(field, "")) == str(entity_scope.get(field, "")) for field in ENTITY_SCOPE_FIELDS)
        ]
        if not candidates:
            return None
        return sorted(candidates, key=lambda item: str(item.get("last_updated") or ""))[-1]

    def packet_provenance(
        self,
        events: list[dict[str, Any]],
        excluded_events: list[dict[str, Any]],
        entity_scope: dict[str, str],
        previous_packet: dict[str, Any] | None,
    ) -> dict[str, Any]:
        ordered = sorted(
            events,
            key=lambda item: (
                int(item.get("timestamp_index", 0)),
                str(item.get("timestamp", "")),
                str(item.get("event_id", "")),
            ),
        )
        event_count = len(ordered)
        horizon_window_size = min(5, max(1, event_count))
        recent = ordered[-horizon_window_size:] if ordered else []
        historical = ordered[:-horizon_window_size] if event_count > horizon_window_size else ordered
        signal_counts = Counter(self.event_signal(event) for event in ordered)
        recent_set = {self.event_signal(event) for event in recent}
        historical_set = {self.event_signal(event) for event in historical}
        current_signals = sorted(signal_counts)
        previous_signals = sorted((previous_packet or {}).get("causal_signature", {}).get("signal_frequency_distribution", {}).keys())
        transition_sequence = [
            {
                "from_event_id": str(previous.get("event_id", "")),
                "to_event_id": str(current.get("event_id", "")),
                "transition": f"{self.event_signal(previous)} -> {self.event_signal(current)}",
            }
            for previous, current in zip(ordered, ordered[1:])
        ]
        return {
            "source_event_ids": [str(event.get("event_id", "")) for event in ordered],
            "normalized_event_types": [self.event_signal(event) for event in ordered],
            "events_included": [
                {
                    "event_id": str(event.get("event_id", "")),
                    "event_type": self.event_signal(event),
                    "occurred_at": str(event.get("timestamp", "")),
                    "application_reference": str(event.get("application_reference", "")),
                    "actor_reference": str(event.get("actor_reference", "")),
                    "workspace_reference": str(event.get("workspace_reference", "")),
                    "entity_reference": str(event.get("entity_reference", "")),
                }
                for event in ordered
            ],
            "events_excluded": self.excluded_event_summary(excluded_events),
            "recent_horizon_boundary": str(recent[0].get("timestamp", "")) if recent else None,
            "historical_horizon_boundary": str(historical[-1].get("timestamp", "")) if historical else None,
            "active_classification_basis": "signals present inside the recent deterministic horizon",
            "latent_classification_basis": "historical signals absent from the recent deterministic horizon",
            "lineage_classification_basis": "signals with repeated occurrences across ordered event history",
            "coherence_factor_breakdown": self.coherence_factor_breakdown(ordered, recent_set, historical_set, signal_counts),
            "recoverability_factor_breakdown": self.recoverability_factor_breakdown(ordered),
            "transition_sequence": transition_sequence,
            "previous_packet_id": previous_packet.get("packet_id") if previous_packet else None,
            "diff_from_previous_packet": {
                "added_signals": sorted(set(current_signals) - set(previous_signals)),
                "removed_signals": sorted(set(previous_signals) - set(current_signals)),
                "current_state_changed": (
                    previous_packet.get("current_state") != (ordered[-1].get("content") if ordered else "")
                    if previous_packet
                    else True
                ),
            },
            "entity_scope": entity_scope,
            "algorithm_revision": ALGORITHM_REVISION,
        }

    def excluded_event_summary(self, excluded_events: list[dict[str, Any]]) -> dict[str, Any]:
        reasons = Counter(str(event.get("reason", "excluded"))[:160] for event in excluded_events)
        return {
            "excluded_event_count": len(excluded_events),
            "reason_counts": dict(sorted(reasons.items())),
            "scope_values_exposed": False,
            "event_ids_exposed": False,
            "note": "Excluded events are counted only so scoped packets do not reveal other actors, workspaces, or entities.",
        }

    def safe_excluded_event_summary(self, excluded_events: list[dict[str, Any]]) -> dict[str, Any]:
        return self.excluded_event_summary(excluded_events)

    def build_theory_packet(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        ordered = sorted(
            events,
            key=lambda item: (
                int(item.get("timestamp_index", 0)),
                str(item.get("timestamp", "")),
                str(item.get("event_id", "")),
            ),
        )
        event_count = len(ordered)
        latest = ordered[-1] if ordered else {}
        horizon_window_size = min(5, max(1, event_count))
        recent = ordered[-horizon_window_size:] if ordered else []
        historical = ordered[:-horizon_window_size] if event_count > horizon_window_size else ordered
        all_signals = [self.event_signal(event) for event in ordered]
        recent_signals = [self.event_signal(event) for event in recent]
        historical_signals = [self.event_signal(event) for event in historical]
        signal_counts = Counter(all_signals)
        recent_set = set(recent_signals)
        historical_set = set(historical_signals)
        latent_set = historical_set - recent_set
        decayed_set = latent_set
        repeated_signals = sorted(signal for signal, count in signal_counts.items() if count > 1)
        lineage_information = self.lineage_information(ordered, signal_counts)
        repeated_patterns = self.repeated_patterns(ordered, signal_counts)
        transition_pairs = self.transition_pairs(ordered)
        source_distribution = Counter(
            str((event.get("external_metadata") or {}).get("metadata", {}).get("source_app")
                or (event.get("external_metadata") or {}).get("source_app")
                or "unknown")
            for event in ordered
        )
        active_information = [
            {
                "signal": signal,
                "recent_count": recent_signals.count(signal),
                "total_count": signal_counts[signal],
                "latest_content": self.latest_content_for_signal(recent, signal),
                "last_seen": self.last_seen_for_signal(ordered, signal),
            }
            for signal in sorted(recent_set)
        ]
        latent_information = [
            {
                "signal": signal,
                "historical_count": signal_counts[signal],
                "last_seen": self.last_seen_for_signal(ordered, signal),
                "decay_reason": "historically present but absent from recent horizon",
            }
            for signal in sorted(latent_set)
        ]
        packet = {
            "current_state": str(latest.get("content", "")) if latest else "",
            "active_information": active_information,
            "latent_information": latent_information,
            "lineage_information": lineage_information,
            "causal_signature": {
                "top_event_types": [signal for signal, _ in signal_counts.most_common(5)],
                "recurring_signal_names": repeated_signals,
                "signal_frequency_distribution": dict(sorted(signal_counts.items())),
                "first_seen_last_seen_by_signal": self.first_last_by_signal(ordered),
                "transition_pairs": transition_pairs,
                "stable_repeated_patterns": repeated_patterns,
                "metadata_source_app_distribution": dict(sorted(source_distribution.items())),
                "application_continuity_markers": self.safe_sorted_refs(ordered, "application_reference"),
                "actor_continuity_markers": self.safe_sorted_refs(ordered, "actor_reference"),
                "workspace_continuity_markers": self.safe_sorted_refs(ordered, "workspace_reference"),
                "entity_continuity_markers": self.safe_sorted_refs(ordered, "entity_reference"),
            },
            "recursive_horizon": {
                "short_horizon_event_count": len(recent),
                "long_horizon_event_count": len(historical),
                "horizon_window_size": horizon_window_size,
                "recent_signal_set": sorted(recent_set),
                "historical_signal_set": sorted(historical_set),
                "overlapping_signals": sorted(recent_set & historical_set),
                "decayed_or_missing_signals": sorted(decayed_set),
            },
            "coherence_score": self.coherence_score(ordered, recent_set, historical_set, signal_counts),
            "recoverability_score": self.recoverability_score(ordered, lineage_information),
            "re_emergence_signals": self.re_emergence_signals(ordered),
            "decayed_signals": sorted(decayed_set),
            "repeated_patterns": repeated_patterns,
            "state_transition_summary": self.state_transition_summary(ordered),
            "event_count": event_count,
            "last_updated": str(latest.get("timestamp", "")) if latest else None,
            "summary": "Continuity packet generated deterministically from scoped events.",
            "active_signals": sorted(recent_set),
            "stale_signals": sorted(decayed_set),
        }
        if event_count == 0:
            packet["summary"] = "Empty continuity packet generated for scoped namespace with no events."
        return packet

    def event_signal(self, event: dict[str, Any]) -> str:
        return str(event.get("type") or "memory_event")[:120]

    def latest_content_for_signal(self, events: list[dict[str, Any]], signal: str) -> str:
        for event in reversed(events):
            if self.event_signal(event) == signal:
                return str(event.get("content", ""))[:300]
        return ""

    def last_seen_for_signal(self, events: list[dict[str, Any]], signal: str) -> str | None:
        for event in reversed(events):
            if self.event_signal(event) == signal:
                return str(event.get("timestamp", ""))
        return None

    def first_last_by_signal(self, events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        output: dict[str, dict[str, Any]] = {}
        for event in events:
            signal = self.event_signal(event)
            row = output.setdefault(
                signal,
                {
                    "first_seen": str(event.get("timestamp", "")),
                    "last_seen": str(event.get("timestamp", "")),
                    "count": 0,
                },
            )
            row["last_seen"] = str(event.get("timestamp", ""))
            row["count"] += 1
        return dict(sorted(output.items()))

    def lineage_information(self, events: list[dict[str, Any]], signal_counts: Counter[str]) -> list[dict[str, Any]]:
        lineage = []
        for signal in sorted(signal for signal, count in signal_counts.items() if count > 1):
            signal_events = [event for event in events if self.event_signal(event) == signal]
            lineage.append(
                {
                    "signal": signal,
                    "count": len(signal_events),
                    "first_event_id": str(signal_events[0].get("event_id", "")),
                    "latest_event_id": str(signal_events[-1].get("event_id", "")),
                    "first_seen": str(signal_events[0].get("timestamp", "")),
                    "last_seen": str(signal_events[-1].get("timestamp", "")),
                    "timestamp_indexes": [event.get("timestamp_index") for event in signal_events],
                }
            )
        return lineage

    def transition_pairs(self, events: list[dict[str, Any]]) -> dict[str, int]:
        pairs: Counter[str] = Counter()
        for previous, current in zip(events, events[1:]):
            pairs[f"{self.event_signal(previous)} -> {self.event_signal(current)}"] += 1
        return dict(sorted(pairs.items()))

    def repeated_patterns(self, events: list[dict[str, Any]], signal_counts: Counter[str]) -> list[dict[str, Any]]:
        patterns = [
            {
                "pattern": signal,
                "count": count,
                "basis": "repeated signal type",
            }
            for signal, count in sorted(signal_counts.items())
            if count > 1
        ]
        for pair, count in self.transition_pairs(events).items():
            if count > 1:
                patterns.append({"pattern": pair, "count": count, "basis": "repeated transition pair"})
        return patterns

    def safe_sorted_refs(self, events: list[dict[str, Any]], key: str) -> list[str]:
        refs = set()
        for event in events:
            value = event.get(key)
            if isinstance(value, str) and value and value != "[redacted]":
                refs.add(value[:160])
            metadata = event.get("external_metadata") or {}
            metadata_value = metadata.get(key)
            if isinstance(metadata_value, str) and metadata_value and metadata_value != "[redacted]":
                refs.add(metadata_value[:160])
        return sorted(refs)

    def coherence_factor_breakdown(
        self,
        events: list[dict[str, Any]],
        recent_set: set[str],
        historical_set: set[str],
        signal_counts: Counter[str],
    ) -> dict[str, Any]:
        if not events:
            return {
                "repeated_ratio": 0.0,
                "overlap_ratio": 0.0,
                "workspace_consistency": 0.0,
                "actor_consistency": 0.0,
                "event_volume_factor": 0.0,
                "weights": {
                    "repeated_ratio": 0.35,
                    "overlap_ratio": 0.25,
                    "workspace_consistency": 0.15,
                    "actor_consistency": 0.10,
                    "event_volume_factor": 0.15,
                },
            }
        repeated_ratio = sum(count for count in signal_counts.values() if count > 1) / len(events)
        overlap_ratio = len(recent_set & historical_set) / max(1, len(recent_set | historical_set))
        workspace_refs = self.safe_sorted_refs(events, "workspace_reference")
        actor_refs = self.safe_sorted_refs(events, "actor_reference")
        return {
            "repeated_ratio": round(repeated_ratio, 4),
            "overlap_ratio": round(overlap_ratio, 4),
            "workspace_consistency": 1.0 if len(workspace_refs) == 1 else 0.5 if workspace_refs else 0.0,
            "actor_consistency": 1.0 if len(actor_refs) == 1 else 0.5 if actor_refs else 0.0,
            "event_volume_factor": round(min(1.0, len(events) / 8), 4),
            "weights": {
                "repeated_ratio": 0.35,
                "overlap_ratio": 0.25,
                "workspace_consistency": 0.15,
                "actor_consistency": 0.10,
                "event_volume_factor": 0.15,
            },
        }

    def recoverability_factor_breakdown(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        if not events:
            return {
                "has_content_ratio": 0.0,
                "has_order_ratio": 0.0,
                "has_anchor_ratio": 0.0,
                "has_timestamp_ratio": 0.0,
                "event_volume_factor": 0.0,
            }
        signal_count = len({self.event_signal(event) for event in events})
        lineage = self.lineage_information(events, Counter(self.event_signal(event) for event in events))
        return {
            "has_content_ratio": round(sum(1 for event in events if str(event.get("content", "")).strip()) / len(events), 4),
            "has_order_ratio": round(sum(1 for event in events if isinstance(event.get("timestamp_index"), int)) / len(events), 4),
            "has_anchor_ratio": round(sum(1 for event in events if str(event.get("event_id", "")).strip()) / len(events), 4),
            "has_timestamp_ratio": round(sum(1 for event in events if str(event.get("timestamp", "")).strip()) / len(events), 4),
            "lineage_factor": round(min(1.0, len(lineage) / max(1, signal_count)), 4),
            "event_volume_factor": round(min(1.0, len(events) / 6), 4),
            "weights": {
                "has_content_ratio": 0.25,
                "has_order_ratio": 0.20,
                "has_anchor_ratio": 0.20,
                "has_timestamp_ratio": 0.15,
                "lineage_factor": 0.10,
                "event_volume_factor": 0.10,
            },
        }

    def coherence_score(
        self,
        events: list[dict[str, Any]],
        recent_set: set[str],
        historical_set: set[str],
        signal_counts: Counter[str],
    ) -> float:
        if not events:
            return 0.0
        factors = self.coherence_factor_breakdown(events, recent_set, historical_set, signal_counts)
        score = (
            factors["repeated_ratio"] * 0.35
            + factors["overlap_ratio"] * 0.25
            + factors["workspace_consistency"] * 0.15
            + factors["actor_consistency"] * 0.10
            + factors["event_volume_factor"] * 0.15
        )
        return round(max(0.0, min(1.0, score)), 4)

    def recoverability_score(self, events: list[dict[str, Any]], lineage: list[dict[str, Any]]) -> float:
        if not events:
            return 0.0
        factors = self.recoverability_factor_breakdown(events)
        score = (
            factors["has_content_ratio"] * 0.25
            + factors["has_order_ratio"] * 0.20
            + factors["has_anchor_ratio"] * 0.20
            + factors["has_timestamp_ratio"] * 0.15
            + min(1.0, len(lineage) / max(1, len({self.event_signal(event) for event in events}))) * 0.10
            + factors["event_volume_factor"] * 0.10
        )
        return round(max(0.0, min(1.0, score)), 4)

    def re_emergence_signals(self, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        positions: dict[str, list[int]] = {}
        for index, event in enumerate(events):
            positions.setdefault(self.event_signal(event), []).append(index)
        output = []
        for signal, indexes in sorted(positions.items()):
            gaps = [right - left for left, right in zip(indexes, indexes[1:])]
            max_gap = max(gaps) if gaps else 0
            if len(indexes) >= 2 and max_gap >= 3:
                output.append(
                    {
                        "signal": signal,
                        "gap_event_count": max_gap - 1,
                        "first_position": indexes[0],
                        "latest_position": indexes[-1],
                    }
                )
        return output

    def state_transition_summary(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        if not events:
            return {
                "previous_state": None,
                "current_state": "",
                "changed": False,
                "transition": "no_events",
            }
        current = str(events[-1].get("content", ""))
        previous = str(events[-2].get("content", "")) if len(events) > 1 else None
        return {
            "previous_state": previous,
            "current_state": current,
            "changed": previous != current if previous is not None else True,
            "previous_signal": self.event_signal(events[-2]) if len(events) > 1 else None,
            "current_signal": self.event_signal(events[-1]),
            "transition": (
                f"{self.event_signal(events[-2])} -> {self.event_signal(events[-1])}"
                if len(events) > 1
                else f"start -> {self.event_signal(events[-1])}"
            ),
        }

    def memory_reconstruct(self, request_payload: dict[str, Any]) -> dict[str, Any]:
        endpoint = "POST /v1/memory/reconstruct"
        context, error = self.require_access(endpoint, request_payload, "memory_reconstruct")
        if error:
            return error
        packet = self.packets.get(str(request_payload.get("packet_id", "")))
        if not packet or not self.packet_owned_by(packet, context):
            return self.response(404, {"status": "error", "error": {"code": "packet_not_found", "message": "Packet was not found in the authorized scope."}, "public_safe": True})
        return self.public_ok(
            endpoint,
            context,
            {
                "packet_id": packet["packet_id"],
                "reconstructable_state": {
                    "current_state": packet["current_state"],
                    "active_signals": packet["active_signals"],
                    "stale_signals": packet["stale_signals"],
                },
                "summary": "Current state reconstructed from scoped synthetic continuity events.",
            },
        )

    def explain(self, request_payload: dict[str, Any]) -> dict[str, Any]:
        endpoint = "POST /v1/explain"
        context, error = self.require_access(endpoint, request_payload, "explain")
        if error:
            return error
        packet = self.packets.get(str(request_payload.get("packet_id", "")))
        if not packet or not self.packet_owned_by(packet, context):
            return self.response(404, {"status": "error", "error": {"code": "packet_not_found", "message": "Packet was not found in the authorized scope."}, "public_safe": True})
        return self.public_ok(
            endpoint,
            context,
            {
                "packet_id": packet["packet_id"],
                "explanation": {
                    "summary": "This state reflects the latest synthetic continuity event in the scoped namespace.",
                    "review_boundary": "This is controlled-alpha review support, not a final decision.",
                    "sensitive_details_included": False,
                },
            },
        )

    def least_harm_action(self, request_payload: dict[str, Any]) -> dict[str, Any]:
        endpoint = "POST /v1/actions/least-harm"
        context, error = self.require_access(endpoint, request_payload, "least_harm_action")
        if error:
            return error
        packet = self.packets.get(str(request_payload.get("packet_id", "")))
        if not packet or not self.packet_owned_by(packet, context):
            return self.response(404, {"status": "error", "error": {"code": "packet_not_found", "message": "Packet was not found in the authorized scope."}, "public_safe": True})
        return self.public_ok(
            endpoint,
            context,
            {
                "packet_id": packet["packet_id"],
                "recommended_action": "human_review",
                "allowed_actions": ["do_nothing", "request_evidence", "human_review", "keep_dormant"],
                "not_final_decision": True,
                "summary": "Use proportionate review before taking action.",
            },
        )

    def get_report(self, request_payload: dict[str, Any], report_id: str) -> dict[str, Any]:
        endpoint = "GET /v1/reports/{report_id}"
        context, error = self.require_access(endpoint, request_payload, "report_read")
        if error:
            return error
        report = self.public_reports.get(report_id)
        if not report or not self.report_owned_by(report, context):
            return self.response(404, {"status": "error", "error": {"code": "report_not_found", "message": "Report was not found in the authorized scope."}, "public_safe": True})
        return self.public_ok(endpoint, context, {"report": report})

    def get_usage(self, request_payload: dict[str, Any]) -> dict[str, Any]:
        endpoint = "GET /v1/usage"
        context, error = self.require_access(endpoint, request_payload, "report_read")
        if error:
            return error
        return self.public_ok(endpoint, context, {"usage": self.lifecycle.get_client_usage(context["client_id"])})

    def packet_owned_by(self, packet: dict[str, Any], context: dict[str, Any]) -> bool:
        return packet.get("client_id") == context["client_id"] and packet.get("vault_id") == context["vault_id"] and packet.get("namespace") == context["namespace"]

    def report_owned_by(self, report: dict[str, Any], context: dict[str, Any]) -> bool:
        return report.get("client_id") == context["client_id"] and report.get("vault_id") == context["vault_id"] and report.get("namespace") == context["namespace"]

    def request_log_report(self) -> dict[str, Any]:
        return {
            "version": "0.71",
            "boundary": BOUNDARY_V071,
            "request_log": [asdict(item) for item in self.api_request_log],
            "foundation_request_log": [asdict(item) for item in self.lifecycle.foundation.request_log],
        }

    def usage_summary_report(self) -> dict[str, Any]:
        return {
            "version": "0.71",
            "boundary": BOUNDARY_V071,
            "usage": self.lifecycle.foundation.usage_summary(),
        }

    def public_status_report(self, checks: list[dict[str, Any]]) -> dict[str, Any]:
        passed = sum(1 for check in checks if check.get("passed"))
        total = len(checks)
        return {
            "company": "Afternum Industries",
            "product": "PRMR Memory Core",
            "version": "0.71",
            "title": "Hosted Controlled-Alpha API Surface",
            "result": "PASS" if passed == total else "NEEDS_WORK",
            "checks_passed": passed,
            "checks_total": total,
            "public_safe": True,
            "boundary": BOUNDARY_V071,
            "endpoint_coverage": ENDPOINTS,
            "safe_response_summary": {
                "valid_flow_public_safe": True,
                "blocked_flow_public_safe": True,
                "credential_values_in_public_report": False,
                "restricted_details_in_public_report": False,
            },
            "usage_summary": self.lifecycle.foundation.usage_summary(),
        }

    def private_status_report(self, checks: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            **self.public_status_report(checks),
            "public_safe": False,
            "title": "Controlled-Alpha API Surface Private Synthetic Trace",
            "checks": checks,
            "synthetic_clients": {
                client_id: asdict(client)
                for client_id, client in self.lifecycle.foundation.clients.items()
            },
            "synthetic_vaults": {
                vault_id: asdict(vault)
                for vault_id, vault in self.lifecycle.foundation.vaults.items()
            },
            "synthetic_namespaces": {
                namespace_id: asdict(namespace)
                for namespace_id, namespace in self.lifecycle.foundation.namespaces.items()
            },
            "synthetic_packets": self.packets,
            "synthetic_public_reports": self.public_reports,
            "synthetic_private_reports": self.private_reports,
            "api_request_log": [asdict(item) for item in self.api_request_log],
            "validation_outcomes": self.lifecycle.validation_outcomes,
            "private_note": "Private report contains synthetic traces only; raw API keys are not persisted.",
        }


def scan_forbidden_public_terms(obj: Any) -> list[str]:
    text = json.dumps(obj, sort_keys=True).lower()
    return [term for term in PUBLIC_FORBIDDEN_TERMS if term.lower() in text]


def scan_unsafe_public_language(obj: Any) -> list[str]:
    text = json.dumps(obj, sort_keys=True).lower()
    return [term for term in UNSAFE_PUBLIC_LANGUAGE if term.lower() in text]
