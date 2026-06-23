import json
import os
import subprocess
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from prmr.product.alpha_api_sandbox_v0521 import (
    ALPHA_SANDBOX_KEYS,
    PRMRAlphaAPISandbox,
    contains_raw_sandbox_key,
    scan_public_forbidden_terms,
    scan_unsafe_public_language,
)


REPORT_DIR = Path("reports/v0522")
REPORT_DIR.mkdir(parents=True, exist_ok=True)

PUBLIC_PATH = REPORT_DIR / "public_alpha_api_sandbox_integrity_v0522.json"
PRIVATE_PATH = REPORT_DIR / "private_internal_alpha_api_sandbox_integrity_v0522.json"
SCORECARD_PATH = REPORT_DIR / "scorecard_v0522.md"


ROTATED_KEY_PUBLIC_TERMS = [
    "new_api_key",
    "raw_api_key",
    "old_key_status",
    "new_key_fingerprint",
    "revoked_key_fingerprint",
    "key_fingerprint",
    "active_key_hashes",
    "revoked_key_hashes",
    "show_once_for_local_sandbox",
]

CERTIFICATION_CLAIMS = [
    "hosted api",
    "hosted production api",
    "production certified",
    "bank approved",
    "bank approval",
    "compliance approved",
    "compliance approval",
    "external security certification",
]


def add_check(checks, name, passed, details=None):
    checks.append({
        "name": name,
        "passed": bool(passed),
        "details": details or {},
    })


def sample_events(entity_id):
    return [
        {
            "event_id": f"evt_{entity_id}_001",
            "entity_id": entity_id,
            "entity_type": "account",
            "timestamp": "2026-06-20T13:00:00Z",
            "timestamp_index": 1,
            "event_type": "origin",
            "state_before": "no active review",
            "state_after": "ordinary account activity",
            "signal_type": "origin",
            "status": "historical",
            "trust_level": "trusted",
            "evidence": [
                {
                    "evidence_id": f"ev_{entity_id}_001",
                    "summary": "Synthetic baseline account activity.",
                    "supports": ["ordinary_activity"],
                }
            ],
            "tags": ["synthetic", "controlled_alpha"],
        },
        {
            "event_id": f"evt_{entity_id}_002",
            "entity_id": entity_id,
            "entity_type": "account",
            "timestamp": "2026-06-20T13:05:00Z",
            "timestamp_index": 2,
            "event_type": "current_state",
            "state_before": "ordinary account activity",
            "state_after": "unusual recipient introduced",
            "signal_type": "unusual_recipient",
            "status": "active",
            "trust_level": "trusted",
            "evidence": [
                {
                    "evidence_id": f"ev_{entity_id}_002",
                    "summary": "Synthetic recipient change requires review.",
                    "supports": ["unusual_recipient"],
                }
            ],
            "tags": ["synthetic", "controlled_alpha"],
        },
        {
            "event_id": f"evt_{entity_id}_003",
            "entity_id": entity_id,
            "entity_type": "account",
            "timestamp": "2026-06-20T13:10:00Z",
            "timestamp_index": 3,
            "event_type": "stale_signal",
            "state_before": "old device note active",
            "state_after": "old device note superseded",
            "signal_type": "old_device_note",
            "status": "stale",
            "trust_level": "trusted",
            "evidence": [],
            "counter_evidence": [
                {
                    "evidence_id": f"ev_{entity_id}_003",
                    "summary": "Synthetic device note is stale.",
                }
            ],
            "tags": ["synthetic", "controlled_alpha"],
        },
    ]


def base_request(client_id, key, vault_id):
    return {
        "client_id": client_id,
        "api_key": key,
        "vault_id": vault_id,
        "namespace": "default",
        "metadata": {"dataset_type": "synthetic"},
    }


def independent_recompute(events):
    rows = sorted(events, key=lambda item: int(item.get("timestamp_index", 0)))
    active_rows = [row for row in rows if row.get("status") == "active"]
    stale_rows = [row for row in rows if row.get("status") == "stale"]
    current_rows = [
        row
        for row in active_rows
        if row.get("event_type") in {"current_state", "state_change"}
    ]
    current_state = (
        current_rows[-1]["state_after"]
        if current_rows
        else (active_rows[-1]["state_after"] if active_rows else None)
    )
    previous_state = (
        current_rows[-1]["state_before"]
        if current_rows
        else (rows[0]["state_before"] if rows else None)
    )

    return {
        "current_state": current_state,
        "previous_state": previous_state,
        "active_signals": sorted({
            row.get("signal_type")
            for row in active_rows
            if row.get("signal_type")
        }),
        "stale_signals": sorted({
            row.get("signal_type")
            for row in stale_rows
            if row.get("signal_type")
        }),
    }


def public_checks(checks):
    return [
        {
            "name": check["name"],
            "passed": check["passed"],
        }
        for check in checks
    ]


def usage_subset(usage):
    return {
        key: usage.get(key, 0)
        for key in [
            "events_ingested",
            "packets_generated",
            "reconstructions",
            "explanations",
            "least_harm_actions",
            "reports_created",
            "reports_read",
            "key_rotations",
            "key_revocations",
        ]
    }


def successful_usage_total(usage):
    return sum(usage_subset(usage).values())


def state_counts(api):
    return {
        "event_count": sum(len(rows) for rows in api.events.values()),
        "packet_count": len(api.packets),
        "public_report_count": len(api.public_reports),
        "restricted_report_count": len(api.restricted_debug_reports),
        "usage_scope_count": len(api.usage),
        "successful_usage_total": sum(
            successful_usage_total(usage)
            for usage in api.usage.values()
        ),
    }


def text_contains_claim_without_negation(text, claim):
    lower = text.lower()
    index = lower.find(claim)
    if index == -1:
        return False

    window = lower[max(0, index - 16):index]
    return not any(marker in window for marker in ["not ", "no ", "does not ", "is not "])


def run_v0521_runner():
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return subprocess.run(
        [sys.executable, "benchmarks/runners/run_alpha_api_sandbox_v0521.py"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def build_public_report(checks, usage_policy, v0521_status):
    passed_count = sum(1 for check in checks if check["passed"])
    total_checks = len(checks)
    result = "PASS" if passed_count == total_checks else "NEEDS_WORK"

    return {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": "0.52.2",
        "report_type": "alpha_api_sandbox_integrity",
        "public_safe": True,
        "timestamp": datetime.now().isoformat(),
        "result": result,
        "passed_checks": passed_count,
        "total_checks": total_checks,
        "all_checks_passed": passed_count == total_checks,
        "checks": public_checks(checks),
        "usage_policy": usage_policy,
        "v0521_runner_status": v0521_status,
        "honest_boundary": (
            "V0.52.2 is local controlled-alpha sandbox integrity evidence only. "
            "It is not a hosted API. It provides no production, banking, compliance, "
            "or external security approval or certification."
        ),
        "data_boundary": "Synthetic or approved data only; no real sensitive data unless approved.",
        "decision_boundary": "Review support only; no final punitive decisions.",
        "remaining_v053_live_demo_gaps": [
            "Add a small local demo harness that exercises the sandbox without hosted infrastructure claims.",
            "Add fixture-based replay tests for more event shapes and namespaces.",
            "Add explicit lifecycle traces for report creation, packet creation, and access denial paths.",
            "Document the exact local demo setup and synthetic data constraints.",
        ],
    }


def build_scorecard(public_report):
    lines = [
        "# PRMR V0.52.2 Alpha API Sandbox Integrity Audit",
        "",
        "Company: Afternum Industries  ",
        "Product: PRMR Memory Core  ",
        "Version: V0.52.2  ",
        "",
        "## Result",
        "",
        f"**{public_report['result']}**",
        "",
        f"Passed checks: **{public_report['passed_checks']}/{public_report['total_checks']}**",
        "",
        "## Checks",
        "",
    ]

    for check in public_report["checks"]:
        status = "PASS" if check["passed"] else "FAIL"
        lines.append(f"- {check['name']}: {status}")

    lines.extend([
        "",
        "## Usage Policy",
        "",
        public_report["usage_policy"],
        "",
        "## Boundary",
        "",
        public_report["honest_boundary"],
        "",
        public_report["data_boundary"],
        "",
        public_report["decision_boundary"],
        "",
        "## V0.53 Live Demo Gaps",
        "",
    ])

    for gap in public_report["remaining_v053_live_demo_gaps"]:
        lines.append(f"- {gap}")

    return "\n".join(lines)


def main():
    print("PRMR V0.52.2 ALPHA API SANDBOX INTEGRITY AUDIT")
    print("------------------------------------------------")

    checks = []
    traces = {}
    api = PRMRAlphaAPISandbox()

    alpha_key = ALPHA_SANDBOX_KEYS["client_alpha"]
    beta_key = ALPHA_SANDBOX_KEYS["client_beta"]
    alpha_base = base_request("client_alpha", alpha_key, "alpha_vault")
    beta_base = base_request("client_beta", beta_key, "beta_vault")
    alpha_entity = "acct_integrity_alpha_001"
    beta_entity = "acct_integrity_beta_001"
    alpha_events = sample_events(alpha_entity)
    beta_events = sample_events(beta_entity)

    ingest = api.events_ingest({**alpha_base, "events": alpha_events})
    packet_result = api.continuity_packet({**alpha_base, "entity_id": alpha_entity})
    packet = packet_result.get("data", {}).get("packet", {}) if packet_result.get("ok") else {}
    expected = independent_recompute(alpha_events)
    observed = {
        "current_state": packet.get("current_state"),
        "previous_state": packet.get("previous_state"),
        "active_signals": packet.get("active_signals"),
        "stale_signals": packet.get("stale_signals"),
    }
    add_check(
        checks,
        "independent_reconstruction_recomputes_from_raw_events",
        ingest.get("ok") is True
        and packet_result.get("ok") is True
        and observed == expected,
        {"expected": expected, "observed": observed},
    )

    beta_ingest = api.events_ingest({**beta_base, "events": beta_events})
    beta_packet_result = api.continuity_packet({**beta_base, "entity_id": beta_entity})
    beta_packet = beta_packet_result.get("data", {}).get("packet", {}) if beta_packet_result.get("ok") else {}
    beta_report_id = beta_packet_result.get("data", {}).get("public_report_id")

    report_tamper = api.get_report({**alpha_base, "report_id": beta_report_id})
    add_check(
        checks,
        "report_owner_tamper_is_rejected",
        report_tamper.get("ok") is False
        and report_tamper.get("error", {}).get("code") == "vault_denied",
        {"error": report_tamper.get("error")},
    )

    packet_tamper = api.memory_reconstruct({**alpha_base, "packet_id": beta_packet.get("packet_id")})
    cross_vault_packet = api.memory_reconstruct({
        **alpha_base,
        "vault_id": "beta_vault",
        "packet_id": beta_packet.get("packet_id"),
    })
    add_check(
        checks,
        "packet_owner_tamper_is_rejected",
        packet_tamper.get("ok") is False
        and packet_tamper.get("error", {}).get("code") == "vault_denied"
        and cross_vault_packet.get("ok") is False
        and cross_vault_packet.get("error", {}).get("code") == "vault_denied",
        {
            "known_packet_error": packet_tamper.get("error"),
            "cross_vault_error": cross_vault_packet.get("error"),
        },
    )

    alpha_report_id = packet_result.get("data", {}).get("public_report_id")
    public_report_fetch = api.get_report({**alpha_base, "report_id": alpha_report_id})
    reconstruct = api.memory_reconstruct({**alpha_base, "packet_id": packet.get("packet_id")})
    explanation = api.explain({
        **alpha_base,
        "packet_id": packet.get("packet_id"),
        "audience": "customer_safe",
    })
    action = api.least_harm_action({**alpha_base, "packet_id": packet.get("packet_id")})
    usage_before_rotation = api.get_usage(alpha_base)
    usage_before_failed = deepcopy(usage_before_rotation.get("data", {}).get("usage", {}))

    rotation = api.rotate_key(alpha_base)
    new_key = rotation.get("data", {}).get("new_api_key")
    rotated_base = {**alpha_base, "api_key": new_key}
    usage_after_rotation = api.get_usage(rotated_base)

    public_surfaces = {
        "sandbox_public_report": public_report_fetch.get("data", {}).get("report", {}),
        "customer_safe_explanation": explanation.get("data", {}).get("explanation", {}),
        "least_harm_action": action.get("data", {}),
    }
    public_surface_text = json.dumps(public_surfaces, sort_keys=True)
    leaked_raw_keys = contains_raw_sandbox_key(public_surfaces) or (new_key and new_key in public_surface_text)
    leaked_rotation_terms = [
        term
        for term in ROTATED_KEY_PUBLIC_TERMS
        if term.lower() in public_surface_text.lower()
    ]
    add_check(
        checks,
        "rotated_key_details_absent_from_public_outputs",
        not leaked_raw_keys and not leaked_rotation_terms,
        {"leaked_rotation_terms": leaked_rotation_terms},
    )

    failed_invalid = api.events_ingest({
        **rotated_base,
        "api_key": "wrong_key",
        "events": sample_events("acct_integrity_failed_001"),
    })
    failed_missing = api.events_ingest({
        **rotated_base,
        "api_key": None,
        "events": sample_events("acct_integrity_failed_002"),
    })
    failed_revoked_old_key = api.events_ingest({
        **alpha_base,
        "events": sample_events("acct_integrity_failed_003"),
    })
    usage_after_failed = api.get_usage(rotated_base)
    usage_policy = (
        "Failed authorization calls are not counted as successful work usage in this local "
        "controlled-alpha sandbox; only authorized successful operations increment usage counters."
    )
    usage_after_rotation_data = usage_after_rotation.get("data", {}).get("usage", {})
    usage_after_failed_data = usage_after_failed.get("data", {}).get("usage", {})
    failed_errors_ok = {
        failed_invalid.get("error", {}).get("code"),
        failed_missing.get("error", {}).get("code"),
        failed_revoked_old_key.get("error", {}).get("code"),
    } == {"invalid_key", "missing_auth", "revoked_key"}
    add_check(
        checks,
        "usage_counter_policy_is_consistent",
        failed_errors_ok
        and usage_subset(usage_after_failed_data) == usage_subset(usage_after_rotation_data)
        and usage_after_rotation_data.get("events_ingested") == len(alpha_events),
        {
            "policy": usage_policy,
            "before_failed": usage_subset(usage_after_rotation_data),
            "after_failed": usage_subset(usage_after_failed_data),
        },
    )

    mutation_api = PRMRAlphaAPISandbox()
    mutation_base = base_request("client_alpha", ALPHA_SANDBOX_KEYS["client_alpha"], "alpha_vault")
    revoke_for_mutation = mutation_api.revoke_key(mutation_base)
    before_failed_auth_state = state_counts(mutation_api)
    missing_mutation = mutation_api.events_ingest({
        **mutation_base,
        "api_key": None,
        "events": sample_events("acct_missing_mutation_001"),
    })
    invalid_mutation = mutation_api.continuity_packet({
        **mutation_base,
        "api_key": "wrong_key",
        "entity_id": "acct_invalid_mutation_001",
    })
    revoked_mutation = mutation_api.events_ingest({
        **mutation_base,
        "events": sample_events("acct_revoked_mutation_001"),
    })
    after_failed_auth_state = state_counts(mutation_api)
    add_check(
        checks,
        "failed_auth_does_not_mutate_success_state",
        before_failed_auth_state == after_failed_auth_state
        and missing_mutation.get("ok") is False
        and invalid_mutation.get("ok") is False
        and revoked_mutation.get("ok") is False,
        {
            "before_failed_auth_state": before_failed_auth_state,
            "after_failed_auth_state": after_failed_auth_state,
            "errors": [
                missing_mutation.get("error"),
                invalid_mutation.get("error"),
                revoked_mutation.get("error"),
            ],
            "setup_revocation": revoke_for_mutation,
        },
    )

    v0521_run = run_v0521_runner()
    v0521_stdout = v0521_run.stdout
    v0521_stderr = v0521_run.stderr
    v0521_still_passes = (
        v0521_run.returncode == 0
        and "Passed checks: 18/18" in v0521_stdout
        and "Result: PASS" in v0521_stdout
    )
    add_check(
        checks,
        "v0521_sandbox_runner_still_passes",
        v0521_still_passes,
        {
            "returncode": v0521_run.returncode,
            "stdout_tail": v0521_stdout.splitlines()[-8:],
            "stderr_tail": v0521_stderr.splitlines()[-8:],
        },
    )

    add_check(
        checks,
        "alpha_boundary_preserved",
        all([
            packet.get("human_review_required") is True,
            action.get("data", {}).get("not_final_decision") is True,
            action.get("data", {}).get("human_review_required") is True,
            ingest.get("data", {}).get("alpha_boundary", {}).get("controlled_alpha_only") is True,
            ingest.get("data", {}).get("alpha_boundary", {}).get("hosted_production_api") is False,
            ingest.get("data", {}).get("alpha_boundary", {}).get("no_bank_certification") is True,
            ingest.get("data", {}).get("alpha_boundary", {}).get("no_compliance_approval") is True,
            ingest.get("data", {}).get("alpha_boundary", {}).get("no_external_security_certification") is True,
        ]),
        {
            "ingest_alpha_boundary": ingest.get("data", {}).get("alpha_boundary"),
            "action_boundary": action.get("data", {}),
        },
    )

    public_report = build_public_report(checks, usage_policy, "PASS" if v0521_still_passes else "NEEDS_WORK")
    scorecard_text = build_scorecard(public_report)
    public_scan_target = {
        "public_report": public_report,
        "scorecard": scorecard_text,
        "sandbox_public_surfaces": public_surfaces,
    }

    forbidden_terms = scan_public_forbidden_terms(public_scan_target)
    leaked_public_keys = contains_raw_sandbox_key(public_scan_target) or (
        new_key and new_key in json.dumps(public_scan_target, sort_keys=True)
    )
    add_check(
        checks,
        "public_restricted_report_boundary_holds",
        not forbidden_terms and not leaked_public_keys,
        {"forbidden_terms": forbidden_terms, "leaked_public_keys": bool(leaked_public_keys)},
    )

    unsafe_terms = scan_unsafe_public_language(public_scan_target)
    add_check(
        checks,
        "public_wording_hygiene_holds",
        not unsafe_terms,
        {"unsafe_terms": unsafe_terms},
    )

    public_report = build_public_report(checks, usage_policy, "PASS" if v0521_still_passes else "NEEDS_WORK")
    scorecard_text = build_scorecard(public_report)

    final_public_scan = {
        "public_report": public_report,
        "scorecard": scorecard_text,
        "sandbox_public_surfaces": public_surfaces,
    }
    final_forbidden = scan_public_forbidden_terms(final_public_scan)
    final_unsafe = scan_unsafe_public_language(final_public_scan)
    final_text = json.dumps(final_public_scan, sort_keys=True)
    final_claims = [
        claim
        for claim in CERTIFICATION_CLAIMS
        if text_contains_claim_without_negation(final_text, claim)
    ]

    if final_forbidden or final_unsafe or final_claims:
        add_check(
            checks,
            "final_public_artifact_guardrail_holds",
            False,
            {
                "forbidden_terms": final_forbidden,
                "unsafe_terms": final_unsafe,
                "claims_without_negation": final_claims,
            },
        )
        public_report = build_public_report(checks, usage_policy, "PASS" if v0521_still_passes else "NEEDS_WORK")
        scorecard_text = build_scorecard(public_report)

    passed_count = sum(1 for check in checks if check["passed"])
    total_checks = len(checks)
    result = "PASS" if passed_count == total_checks else "NEEDS_WORK"
    public_report["result"] = result
    public_report["passed_checks"] = passed_count
    public_report["total_checks"] = total_checks
    public_report["all_checks_passed"] = passed_count == total_checks

    traces.update({
        "ingest": ingest,
        "packet_result": packet_result,
        "expected_recompute": expected,
        "observed_packet_subset": observed,
        "beta_ingest": beta_ingest,
        "beta_packet_result": beta_packet_result,
        "report_tamper": report_tamper,
        "packet_tamper": packet_tamper,
        "cross_vault_packet": cross_vault_packet,
        "public_report_fetch": public_report_fetch,
        "reconstruct": reconstruct,
        "explanation": explanation,
        "least_harm_action": action,
        "usage_before_rotation": usage_before_rotation,
        "usage_before_failed": usage_before_failed,
        "rotation": rotation,
        "usage_after_rotation": usage_after_rotation,
        "failed_invalid": failed_invalid,
        "failed_missing": failed_missing,
        "failed_revoked_old_key": failed_revoked_old_key,
        "usage_after_failed": usage_after_failed,
        "mutation_auth_failures": {
            "revoke_for_mutation": revoke_for_mutation,
            "before_failed_auth_state": before_failed_auth_state,
            "missing_mutation": missing_mutation,
            "invalid_mutation": invalid_mutation,
            "revoked_mutation": revoked_mutation,
            "after_failed_auth_state": after_failed_auth_state,
        },
        "v0521_runner": {
            "returncode": v0521_run.returncode,
            "stdout": v0521_stdout,
            "stderr": v0521_stderr,
        },
    })

    private_report = {
        **public_report,
        "public_safe": False,
        "checks": checks,
        "restricted_integrity_traces": traces,
        "restricted_note": "Restricted report includes full sandbox integrity traces for internal validation.",
    }

    PUBLIC_PATH.write_text(json.dumps(public_report, indent=4), encoding="utf-8")
    PRIVATE_PATH.write_text(json.dumps(private_report, indent=4), encoding="utf-8")
    SCORECARD_PATH.write_text(scorecard_text, encoding="utf-8")

    print("Passed checks:", f"{passed_count}/{total_checks}")
    print("Result:", result)
    print("V0.52.1 runner:", "PASS" if v0521_still_passes else "NEEDS_WORK")
    print()
    print("Check list:")
    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        print("-", check["name"] + ":", status)
    print()
    print("Created:")
    print(PUBLIC_PATH)
    print(PRIVATE_PATH)
    print(SCORECARD_PATH)

    if result != "PASS":
        sys.exit(1)


if __name__ == "__main__":
    main()
