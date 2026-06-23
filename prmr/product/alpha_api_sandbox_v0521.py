import hashlib
import json
from copy import deepcopy
from datetime import datetime
from uuid import uuid4


ALPHA_SANDBOX_KEYS = {
    "client_alpha": "prmr_v0521_alpha_seed_key",
    "client_beta": "prmr_v0521_beta_seed_key",
}

ALPHA_BOUNDARY = {
    "mode": "controlled_alpha_sandbox",
    "hosted_production_api": False,
    "billing_enabled": False,
    "real_sensitive_data_allowed_by_default": False,
    "requires_approved_dataset_for_sensitive_data": True,
    "bank_certification": False,
    "compliance_approval": False,
    "external_security_certification": False,
    "final_punitive_decisions_allowed": False,
    "human_review_required_for_sensitive_actions": True,
}


PUBLIC_FORBIDDEN_TERMS = [
    "truth_private",
    "private_truth",
    "private_packets",
    "private_classifications",
    "private_explanations",
    "private_harm_packets",
    "private_prmr_labels",
    "private_rule_labels",
    "private_rule_actions",
    "private_reconstruction_results",
    "private_checks",
    "private_internal",
    "protected_note",
    "compressed_package",
    "reconstructed_rows",
    "engine_result_snapshot",
    "internal_rule_data",
    "raw_api_key",
    "api_key",
    "do_not_share",
    "do_not_leak",
    "local_test",
]

UNSAFE_PUBLIC_LANGUAGE = [
    "criminal",
    "fraudster",
    "guilty",
    "definitely fraud",
    "blacklist",
    "close account immediately",
]


class PRMRAlphaAPISandbox:
    """
    V0.52.1 local controlled-alpha API sandbox.

    This is a function-level API simulation, not a hosted production API.
    """

    def __init__(self):
        self.clients = {
            "client_alpha": {
                "active_key_hashes": set(),
                "revoked_key_hashes": set(),
                "vaults": {"alpha_vault"},
                "namespaces": {"default", "research"},
                "status": "active",
            },
            "client_beta": {
                "active_key_hashes": set(),
                "revoked_key_hashes": set(),
                "vaults": {"beta_vault"},
                "namespaces": {"default"},
                "status": "active",
            },
        }

        for client_id, raw_key in ALPHA_SANDBOX_KEYS.items():
            self.clients[client_id]["active_key_hashes"].add(self.hash_key(raw_key))

        self.events = {}
        self.packets = {}
        self.public_reports = {}
        self.restricted_debug_reports = {}
        self.usage = {}
        self.audit_events = []

    def hash_key(self, raw_key):
        return hashlib.sha256(str(raw_key).encode("utf-8")).hexdigest()

    def key_fingerprint(self, raw_key):
        return self.hash_key(raw_key)[:12]

    def scope_key(self, client_id, vault_id, namespace):
        return f"{client_id}::{vault_id}::{namespace}"

    def safe_error(self, code, message):
        return {
            "ok": False,
            "error": {
                "code": code,
                "message": message,
            },
            "data": None,
        }

    def ok(self, data):
        return {
            "ok": True,
            "error": None,
            "data": data,
        }

    def authorize(self, request):
        client_id = request.get("client_id")
        raw_key = request.get("api_key")
        vault_id = request.get("vault_id")
        namespace = request.get("namespace")

        if not raw_key:
            return False, "missing_auth"

        if client_id not in self.clients:
            return False, "invalid_key"

        client = self.clients[client_id]
        key_hash = self.hash_key(raw_key)

        if key_hash in client["revoked_key_hashes"]:
            return False, "revoked_key"

        if key_hash not in client["active_key_hashes"]:
            return False, "invalid_key"

        if client.get("status") != "active":
            return False, "client_inactive"

        if vault_id not in client["vaults"]:
            return False, "vault_denied"

        if namespace not in client["namespaces"]:
            return False, "namespace_denied"

        return True, "authorized"

    def require_authorized(self, request):
        authorized, reason = self.authorize(request)
        if not authorized:
            return None, self.safe_error(reason, "Request is not authorized.")

        context = {
            "client_id": request.get("client_id"),
            "vault_id": request.get("vault_id"),
            "namespace": request.get("namespace"),
        }
        return context, None

    def increment_usage(self, context, endpoint, amount=1):
        scope = self.scope_key(context["client_id"], context["vault_id"], context["namespace"])
        self.usage.setdefault(scope, {
            "client_id": context["client_id"],
            "vault_id": context["vault_id"],
            "namespace": context["namespace"],
            "events_ingested": 0,
            "packets_generated": 0,
            "reconstructions": 0,
            "explanations": 0,
            "least_harm_actions": 0,
            "reports_created": 0,
            "reports_read": 0,
            "key_rotations": 0,
            "key_revocations": 0,
        })
        self.usage[scope][endpoint] += amount

    def validate_events(self, events):
        if not isinstance(events, list):
            return False, "payload_invalid", []

        if len(events) > 500:
            return False, "payload_too_large", []

        required = [
            "event_id",
            "entity_id",
            "entity_type",
            "timestamp",
            "event_type",
            "state_before",
            "state_after",
            "signal_type",
            "status",
            "trust_level",
        ]

        safe_events = []

        for index, event in enumerate(events):
            if not isinstance(event, dict):
                return False, "payload_invalid", []

            missing = [field for field in required if field not in event]
            if missing:
                return False, "payload_invalid", []

            safe_event = {
                "event_id": str(event["event_id"])[:120],
                "entity_id": str(event["entity_id"])[:120],
                "entity_type": str(event["entity_type"])[:80],
                "timestamp": str(event["timestamp"])[:80],
                "event_type": str(event["event_type"])[:80],
                "state_before": str(event["state_before"])[:1000],
                "state_after": str(event["state_after"])[:1000],
                "signal_type": str(event["signal_type"])[:80],
                "status": str(event["status"])[:80],
                "trust_level": str(event["trust_level"])[:80],
                "evidence": deepcopy(event.get("evidence", [])) if isinstance(event.get("evidence", []), list) else [],
                "counter_evidence": deepcopy(event.get("counter_evidence", [])) if isinstance(event.get("counter_evidence", []), list) else [],
                "tags": deepcopy(event.get("tags", [])) if isinstance(event.get("tags", []), list) else [],
                "timestamp_index": int(event.get("timestamp_index", index + 1)),
            }
            safe_events.append(safe_event)

        return True, "events_valid", safe_events

    def events_ingest(self, request):
        context, error = self.require_authorized(request)
        if error:
            return error

        metadata = request.get("metadata", {})
        dataset_type = str(metadata.get("dataset_type", "synthetic_or_approved"))

        if dataset_type not in {"synthetic_or_approved", "synthetic", "approved"}:
            return self.safe_error("alpha_boundary_violation", "Controlled alpha accepts synthetic or approved datasets only.")

        valid, reason, safe_events = self.validate_events(request.get("events"))
        if not valid:
            return self.safe_error(reason, "Payload failed validation.")

        scope = self.scope_key(context["client_id"], context["vault_id"], context["namespace"])
        scoped_events = []

        for event in safe_events:
            scoped = dict(event)
            scoped.update(context)
            scoped_events.append(scoped)

        self.events.setdefault(scope, [])
        self.events[scope].extend(scoped_events)
        self.increment_usage(context, "events_ingested", len(scoped_events))

        return self.ok({
            **context,
            "accepted_event_count": len(scoped_events),
            "total_event_count": len(self.events[scope]),
            "alpha_boundary": public_alpha_boundary(),
        })

    def scoped_events(self, context, entity_id=None):
        scope = self.scope_key(context["client_id"], context["vault_id"], context["namespace"])
        rows = self.events.get(scope, [])
        if entity_id is None:
            return list(rows)
        return [event for event in rows if event.get("entity_id") == entity_id]

    def build_packet(self, context, entity_id):
        rows = sorted(self.scoped_events(context, entity_id), key=lambda item: item.get("timestamp_index", 0))

        active_rows = [row for row in rows if row.get("status") == "active"]
        stale_rows = [row for row in rows if row.get("status") == "stale"]
        current_rows = [row for row in active_rows if row.get("event_type") in {"current_state", "state_change"}]
        current = current_rows[-1]["state_after"] if current_rows else (active_rows[-1]["state_after"] if active_rows else None)
        previous = current_rows[-1]["state_before"] if current_rows else (rows[0]["state_before"] if rows else None)
        evidence = []

        for row in rows:
            for item in row.get("evidence", []):
                if isinstance(item, dict):
                    evidence.append({
                        "evidence_id": str(item.get("evidence_id", "evidence"))[:120],
                        "summary": str(item.get("summary", ""))[:500],
                        "supports": item.get("supports", []),
                    })

        active_signals = sorted({
            row.get("signal_type")
            for row in active_rows
            if row.get("signal_type")
        })
        stale_signals = sorted({
            row.get("signal_type")
            for row in stale_rows
            if row.get("signal_type")
        })

        return {
            "packet_id": "pkt_" + uuid4().hex[:16],
            **context,
            "entity_id": entity_id,
            "current_state": current,
            "previous_state": previous,
            "meaningful_changes": [
                f"{row['state_before']} -> {row['state_after']}"
                for row in active_rows
                if row.get("state_before") != row.get("state_after")
            ],
            "active_signals": active_signals,
            "stale_signals": stale_signals,
            "counter_evidence": [
                item
                for row in rows
                for item in row.get("counter_evidence", [])
            ],
            "evidence_summary": evidence,
            "continuity_summary": "Current state preserves active signals, stale signals, and review evidence for this scoped entity.",
            "recommended_next_step": "human_review",
            "human_review_required": True,
        }

    def continuity_packet(self, request):
        context, error = self.require_authorized(request)
        if error:
            return error

        entity_id = request.get("entity_id")
        if not entity_id:
            return self.safe_error("payload_invalid", "entity_id is required.")

        packet = self.build_packet(context, entity_id)
        self.packets[packet["packet_id"]] = packet
        public_report = self.build_public_report(context, packet)
        restricted_report = self.build_restricted_report(context, packet)
        self.public_reports[public_report["report_id"]] = public_report
        self.restricted_debug_reports[public_report["report_id"]] = restricted_report
        self.increment_usage(context, "packets_generated")
        self.increment_usage(context, "reports_created")

        return self.ok({
            "packet": packet,
            "public_report_id": public_report["report_id"],
        })

    def memory_reconstruct(self, request):
        context, error = self.require_authorized(request)
        if error:
            return error

        packet = self.packets.get(request.get("packet_id"))
        if not packet:
            return self.safe_error("payload_invalid", "packet_id was not found.")

        if not self.packet_owned_by(packet, context):
            return self.safe_error("vault_denied", "Packet is outside the authorized scope.")

        rows = self.scoped_events(context, packet["entity_id"])
        self.increment_usage(context, "reconstructions")

        return self.ok({
            **context,
            "entity_id": packet["entity_id"],
            "reconstruction_match": len(rows) > 0,
            "reconstructable_state": {
                "current_state": packet["current_state"],
                "previous_state": packet["previous_state"],
                "active_signals": packet["active_signals"],
                "stale_signals": packet["stale_signals"],
            },
            "event_count": len(rows),
        })

    def explain(self, request):
        context, error = self.require_authorized(request)
        if error:
            return error

        packet = self.packets.get(request.get("packet_id"))
        if not packet:
            return self.safe_error("payload_invalid", "packet_id was not found.")

        if not self.packet_owned_by(packet, context):
            return self.safe_error("vault_denied", "Packet is outside the authorized scope.")

        audience = request.get("audience", "customer_safe")
        self.increment_usage(context, "explanations")

        if audience == "internal":
            explanation = {
                "explanation_id": "exp_" + uuid4().hex[:12],
                "packet_id": packet["packet_id"],
                "supporting_evidence": [item.get("evidence_id") for item in packet["evidence_summary"]],
                "counter_evidence": packet["counter_evidence"],
                "reasoning_summary": f"State moved from {packet['previous_state']} to {packet['current_state']}.",
                "review_boundary": "This explanation supports review only and is not a final punitive decision.",
                "sensitive_details_allowed": True,
            }
        else:
            explanation = {
                "explanation_id": "exp_" + uuid4().hex[:12],
                "packet_id": packet["packet_id"],
                "summary": "We noticed activity that may need review before continuing.",
                "customer_next_step": "Please confirm whether you recognize the change.",
                "review_boundary": "This is a review step, not a final conclusion.",
                "sensitive_details_allowed": False,
            }

        return self.ok({"explanation": explanation})

    def least_harm_action(self, request):
        context, error = self.require_authorized(request)
        if error:
            return error

        packet = self.packets.get(request.get("packet_id"))
        if not packet:
            return self.safe_error("payload_invalid", "packet_id was not found.")

        if not self.packet_owned_by(packet, context):
            return self.safe_error("vault_denied", "Packet is outside the authorized scope.")

        if packet["counter_evidence"]:
            recommended = "request_evidence"
        elif packet["active_signals"]:
            recommended = "human_review"
        else:
            recommended = "do_nothing"

        self.increment_usage(context, "least_harm_actions")

        return self.ok({
            "action_id": "act_" + uuid4().hex[:12],
            "packet_id": packet["packet_id"],
            "recommended_action": recommended,
            "allowed_actions": [
                "do_nothing",
                "warn",
                "request_evidence",
                "pause_suspicious_funds",
                "protect_victim",
                "human_review",
                "release_cleared_funds",
                "mark_false_positive",
                "keep_dormant",
            ],
            "human_review_required": recommended != "do_nothing",
            "not_final_decision": True,
            "safety_boundary": "Proportionate review support only; no final punitive decision.",
        })

    def get_report(self, request):
        context, error = self.require_authorized(request)
        if error:
            return error

        report = self.public_reports.get(request.get("report_id"))
        if not report:
            return self.safe_error("report_not_found", "Report was not found.")

        if not self.report_owned_by(report, context):
            return self.safe_error("vault_denied", "Report is outside the authorized scope.")

        self.increment_usage(context, "reports_read")
        return self.ok({"report": report})

    def get_usage(self, request):
        context, error = self.require_authorized(request)
        if error:
            return error

        scope = self.scope_key(context["client_id"], context["vault_id"], context["namespace"])
        usage = self.usage.get(scope, {
            **context,
            "events_ingested": 0,
            "packets_generated": 0,
            "reconstructions": 0,
            "explanations": 0,
            "least_harm_actions": 0,
            "reports_created": 0,
            "reports_read": 0,
            "key_rotations": 0,
            "key_revocations": 0,
        })
        return self.ok({"usage": dict(usage)})

    def rotate_key(self, request):
        context, error = self.require_authorized(request)
        if error:
            return error

        client = self.clients[context["client_id"]]
        old_key = request.get("api_key")
        old_hash = self.hash_key(old_key)
        new_key = request.get("new_api_key") or ("prmr_v0521_rotated_" + uuid4().hex)
        new_hash = self.hash_key(new_key)

        client["active_key_hashes"].discard(old_hash)
        client["revoked_key_hashes"].add(old_hash)
        client["active_key_hashes"].add(new_hash)
        self.increment_usage(context, "key_rotations")

        return self.ok({
            **context,
            "rotated": True,
            "old_key_status": "revoked",
            "new_key_delivery": "show_once_for_local_sandbox",
            "new_api_key": new_key,
            "new_key_fingerprint": self.key_fingerprint(new_key),
        })

    def revoke_key(self, request):
        context, error = self.require_authorized(request)
        if error:
            return error

        key_to_revoke = request.get("key_to_revoke") or request.get("api_key")
        key_hash = self.hash_key(key_to_revoke)
        client = self.clients[context["client_id"]]

        client["active_key_hashes"].discard(key_hash)
        client["revoked_key_hashes"].add(key_hash)
        self.increment_usage(context, "key_revocations")

        return self.ok({
            **context,
            "revoked": True,
            "revoked_key_fingerprint": self.key_fingerprint(key_to_revoke),
        })

    def packet_owned_by(self, packet, context):
        return (
            packet.get("client_id") == context["client_id"]
            and packet.get("vault_id") == context["vault_id"]
            and packet.get("namespace") == context["namespace"]
        )

    def report_owned_by(self, report, context):
        return (
            report.get("client_id") == context["client_id"]
            and report.get("vault_id") == context["vault_id"]
            and report.get("namespace") == context["namespace"]
        )

    def build_public_report(self, context, packet):
        return {
            "company": "Afternum Industries",
            "product": "PRMR Memory Core",
            "version": "0.52.1",
            "report_id": "rep_" + uuid4().hex[:16],
            "report_type": "alpha_sandbox_public_continuity_report",
            "public_safe": True,
            "timestamp": datetime.now().isoformat(),
            **context,
            "entity_id": packet["entity_id"],
            "current_state_present": packet["current_state"] is not None,
            "active_signal_count": len(packet["active_signals"]),
            "stale_signal_count": len(packet["stale_signals"]),
            "human_review_required": packet["human_review_required"],
            "summary": "Continuity packet generated for controlled alpha review.",
            "alpha_boundary": public_alpha_boundary(),
        }

    def build_restricted_report(self, context, packet):
        return {
            "company": "Afternum Industries",
            "product": "PRMR Memory Core",
            "version": "0.52.1",
            "report_type": "restricted_alpha_sandbox_debug_report",
            "public_safe": False,
            "timestamp": datetime.now().isoformat(),
            **context,
            "packet_debug": deepcopy(packet),
            "event_debug": self.scoped_events(context, packet["entity_id"]),
            "restricted_note": "Restricted debug report includes scoped event and packet details for internal validation.",
        }


def public_alpha_boundary():
    return {
        "controlled_alpha_only": True,
        "hosted_production_api": False,
        "billing_enabled": False,
        "synthetic_or_approved_data_only": True,
        "no_real_sensitive_data_unless_approved": True,
        "no_bank_certification": True,
        "no_compliance_approval": True,
        "no_external_security_certification": True,
        "no_final_punitive_decisions": True,
        "human_review_required_for_sensitive_actions": True,
    }


def scan_public_forbidden_terms(obj):
    text = json.dumps(obj, sort_keys=True).lower()
    return [term for term in PUBLIC_FORBIDDEN_TERMS if term.lower() in text]


def scan_unsafe_public_language(obj):
    text = json.dumps(obj, sort_keys=True).lower()
    return [term for term in UNSAFE_PUBLIC_LANGUAGE if term.lower() in text]


def contains_raw_sandbox_key(obj):
    text = json.dumps(obj, sort_keys=True)
    return any(raw_key in text for raw_key in ALPHA_SANDBOX_KEYS.values())
