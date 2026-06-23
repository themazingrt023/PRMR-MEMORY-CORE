import json
import os
import sys
from copy import deepcopy

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from examples.demo_v0531_replay_pack import alpha_base_request, beta_base_request, fixture_scenarios
from prmr.product.alpha_api_sandbox_v0521 import (
    PRMRAlphaAPISandbox,
    contains_raw_sandbox_key,
    scan_public_forbidden_terms,
    scan_unsafe_public_language,
)


VERSION = "0.55"
BOUNDARY = "Synthetic data only. Local controlled-alpha demo. Not hosted production."

SCENARIO_ID_MAP = {
    "ai_agent_memory": "scenario_ai_agent_memory",
    "agent-memory": "scenario_ai_agent_memory",
    "scenario_ai_agent_memory": "scenario_ai_agent_memory",
    "support_history": "scenario_support_history",
    "support-history": "scenario_support_history",
    "scenario_support_history": "scenario_support_history",
    "risk_continuity": "scenario_risk_continuity",
    "risk-continuity": "scenario_risk_continuity",
    "scenario_risk_continuity": "scenario_risk_continuity",
}

PUBLIC_ACTION_MEANINGS = {
    "do_nothing": "No immediate action is suggested by the synthetic continuity state.",
    "warn": "Show a cautious notice while preserving user review and correction paths.",
    "request_evidence": "Ask for confirmation or supporting context before taking stronger action.",
    "human_review": "Route the synthetic case to human review before any consequential step.",
    "keep_dormant": "Keep the unresolved continuity shape available without taking stronger action.",
}


def available_scenarios():
    return [
        {
            "scenario_id": "ai_agent_memory",
            "scenario_name": "AI agent memory continuity",
            "description": "Synthetic agent context showing continuity across refreshed project state.",
        },
        {
            "scenario_id": "support_history",
            "scenario_name": "Customer support/user-history continuity",
            "description": "Synthetic support history showing current follow-up state without restricted traces.",
        },
        {
            "scenario_id": "risk_continuity",
            "scenario_name": "Fraud/risk continuity sandbox",
            "description": "Synthetic risk-review continuity with review-oriented language and no final decision.",
        },
    ]


def normalize_scenario_id(scenario_id):
    return SCENARIO_ID_MAP.get(str(scenario_id or "").strip())


def find_scenario(scenario_id):
    internal_id = normalize_scenario_id(scenario_id)
    for scenario in fixture_scenarios():
        if scenario["scenario_id"] == internal_id:
            return scenario
    return None


def summarize_events(events):
    return [
        {
            "event_id": event["event_id"],
            "from": event["state_before"],
            "to": event["state_after"],
            "status": event["status"],
            "signal": event["signal_type"],
        }
        for event in events
    ]


def public_error(code, message):
    return {
        "status": "error",
        "error": {
            "code": code,
            "message": message,
        },
        "synthetic_only": True,
        "boundary": BOUNDARY,
    }


def run_frontend_demo(scenario_id):
    scenario = find_scenario(scenario_id)
    if not scenario:
        return public_error("scenario_not_found", "The requested synthetic demo scenario is not available.")

    api = PRMRAlphaAPISandbox()
    alpha_base = alpha_base_request()
    beta_base = beta_base_request()

    ingest = api.events_ingest({**alpha_base, "events": scenario["events"]})
    if not ingest.get("ok"):
        return public_error("ingest_failed", "The synthetic demo events could not be ingested.")

    packet_result = api.continuity_packet({**alpha_base, "entity_id": scenario["entity_id"]})
    packet = packet_result.get("data", {}).get("packet", {}) if packet_result.get("ok") else {}
    if not packet:
        return public_error("packet_failed", "The continuity packet could not be generated.")

    reconstruct = api.memory_reconstruct({**alpha_base, "packet_id": packet.get("packet_id")})
    explanation = api.explain({**alpha_base, "packet_id": packet.get("packet_id"), "audience": "customer_safe"})
    action = api.least_harm_action({**alpha_base, "packet_id": packet.get("packet_id")})
    report_id = packet_result.get("data", {}).get("public_report_id")
    owner_report = api.get_report({**alpha_base, "report_id": report_id})
    wrong_key = api.get_report({**alpha_base, "api_key": "wrong_v055_demo_key", "report_id": report_id})
    cross_client = api.get_report({**beta_base, "report_id": report_id})

    public_explanation = explanation.get("data", {}).get("explanation", {}) if explanation.get("ok") else {}
    action_data = action.get("data", {}) if action.get("ok") else {}
    reconstructed_state = reconstruct.get("data", {}).get("reconstructable_state", {}) if reconstruct.get("ok") else {}
    public_report = owner_report.get("data", {}).get("report", {}) if owner_report.get("ok") else {}
    recommended = action_data.get("recommended_action") or "human_review"

    response = {
        "status": "ok",
        "version": VERSION,
        "scenario_id": next(item["scenario_id"] for item in available_scenarios() if normalize_scenario_id(item["scenario_id"]) == scenario["scenario_id"]),
        "scenario_name": scenario["name"],
        "synthetic_only": True,
        "boundary": BOUNDARY,
        "events_summary": summarize_events(scenario["events"]),
        "continuity_packet": {
            "current_state": packet.get("current_state") or "",
            "active_signals": packet.get("active_signals", []),
            "stale_signals": packet.get("stale_signals", []),
            "evidence": [
                item.get("summary", "")
                for item in packet.get("evidence_summary", [])
                if item.get("summary")
            ],
            "summary": packet.get("continuity_summary") or "",
        },
        "reconstruction": {
            "state": reconstructed_state.get("current_state") or "",
            "confidence_label": "synthetic_demo",
            "active_signals": reconstructed_state.get("active_signals", []),
            "stale_signals": reconstructed_state.get("stale_signals", []),
        },
        "explanation": {
            "public_safe_summary": public_explanation.get("summary") or "",
            "review_boundary": public_explanation.get("review_boundary") or "This is a review step, not a final conclusion.",
            "next_step": public_explanation.get("customer_next_step") or "",
        },
        "least_harm_action": {
            "label": recommended,
            "meaning": PUBLIC_ACTION_MEANINGS.get(recommended, "Review-oriented support only; no final decision is made here."),
            "allowed_actions": [
                item
                for item in action_data.get("allowed_actions", [])
                if item in {"do_nothing", "warn", "request_evidence", "human_review", "release_cleared_funds", "mark_false_positive", "keep_dormant"}
            ],
            "not_final_decision": action_data.get("not_final_decision") is True,
        },
        "report_preview": {
            "report_id": public_report.get("report_id") or report_id or "",
            "public_summary": public_report.get("summary") or "Public-safe controlled-alpha continuity report generated.",
            "owner_access": "allowed" if owner_report.get("ok") else "denied",
            "public_safe": True,
        },
        "denial_path": {
            "wrong_key_denied": wrong_key.get("ok") is False,
            "cross_client_denied": cross_client.get("ok") is False,
            "wrong_key_result": wrong_key.get("error", {}).get("code", "denied"),
            "cross_client_result": cross_client.get("error", {}).get("code", "denied"),
        },
    }

    assert_public_safe(response)
    return response


def report_preview(scenario_id):
    result = run_frontend_demo(scenario_id)
    if result.get("status") != "ok":
        return result
    return {
        "status": "ok",
        "scenario_id": result["scenario_id"],
        "scenario_name": result["scenario_name"],
        "synthetic_only": True,
        "boundary": BOUNDARY,
        "report_preview": deepcopy(result["report_preview"]),
    }


def assert_public_safe(payload):
    text = json.dumps(payload, sort_keys=True)
    restricted = scan_public_forbidden_terms(payload)
    unsafe = scan_unsafe_public_language(payload)
    if contains_raw_sandbox_key(payload) or restricted or unsafe or any(term in text.lower() for term in ["new_api_key", "raw_api_key"]):
        raise ValueError("V0.55 bridge attempted to return unsafe public demo content.")


def cli(argv=None):
    argv = argv or sys.argv[1:]
    if not argv or argv[0] == "scenarios":
        payload = {
            "status": "ok",
            "version": VERSION,
            "synthetic_only": True,
            "boundary": BOUNDARY,
            "scenarios": available_scenarios(),
        }
    elif argv[0] == "run":
        payload = run_frontend_demo(argv[1] if len(argv) > 1 else "")
    elif argv[0] == "report":
        payload = report_preview(argv[1] if len(argv) > 1 else "")
    elif argv[0] == "health":
        payload = {
            "status": "ok",
            "version": VERSION,
            "synthetic_only": True,
            "boundary": BOUNDARY,
            "bridge": "local_frontend_demo_bridge",
        }
    else:
        payload = public_error("unknown_command", "The requested local bridge command is not available.")

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(cli())
