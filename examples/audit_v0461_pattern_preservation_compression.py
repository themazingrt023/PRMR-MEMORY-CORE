import json
import os
import sys
import importlib.util
from pathlib import Path
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from prmr.core.engine import PRMRMemoryCore

DATASET_PATH = Path("benchmarks/datasets_v045/fraud_continuity_simulator_v045.json")
V046_RUNNER = Path("benchmarks/runners/run_fraud_baseline_war_v046.py")

OUT_DIR = Path("reports/v0461")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_JSON = OUT_DIR / "pattern_preservation_compression_audit_v0461.json"
OUT_MD = OUT_DIR / "pattern_preservation_compression_audit_v0461.md"


EXPECTED_PATTERN_FACTS = {
    "acct_normal_001": [
        "ordinary spending continues",
        "no fraud escalation needed",
    ],
    "acct_scam_victim_001": [
        "sudden repeated transfers",
        "unfamiliar recipient",
        "coached by caller",
        "scam victim support review",
    ],
    "acct_pressured_mule_001": [
        "unusual inbound funds",
        "fast outbound movement",
        "mule risk",
        "pressure",
        "safeguarding assessment",
    ],
    "acct_ato_001": [
        "sudden device change",
        "password reset",
        "device continuity broke",
        "did not authorize",
        "account takeover",
    ],
    "acct_malicious_001": [
        "suspicious deposits",
        "rapid dispersal",
        "coordinated pattern",
        "no clear victim",
        "fraud investigation",
    ],
    "acct_false_positive_001": [
        "large unusual incoming payment",
        "documented student finance",
        "move-in costs",
        "likely false positive",
    ],
}

EXPECTED_LABELS = {
    "acct_normal_001": "normal_user",
    "acct_scam_victim_001": "possible_scam_victim",
    "acct_pressured_mule_001": "possible_coercion_or_pressured_mule",
    "acct_ato_001": "possible_account_takeover_victim",
    "acct_malicious_001": "fraud_investigation_needed",
    "acct_false_positive_001": "likely_false_positive",
}


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def add_check(checks, name, passed, details=None):
    checks.append({
        "name": name,
        "passed": bool(passed),
        "details": details or {}
    })


def estimate_tokens(obj):
    return max(1, len(json.dumps(obj, sort_keys=True)) // 4)


def packet_text(packet):
    return json.dumps(packet, sort_keys=True).lower()


def public_safety_scan(obj):
    text = json.dumps(obj, sort_keys=True).lower()

    forbidden = [
        "truth_private",
        "private_truth",
        "private_packets",
        "private_classifications",
        "private_checks",
        "compressed_package",
        "reconstructed_rows",
        "engine_result_snapshot",
        "protected_note",
        "raw_api_key",
        "api_key",
    ]

    return [term for term in forbidden if term in text]


def main():
    print("PRMR V0.46.1 PATTERN PRESERVATION + COMPRESSION AUDIT")
    print("------------------------------------------------------")

    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    runner = load_module(V046_RUNNER, "run_fraud_baseline_war_v046")
    engine = PRMRMemoryCore()

    accounts = dataset["accounts"]

    checks = []

    engine_input = [
        {
            "name": account["account_id"],
            "description": "Synthetic fraud pattern preservation audit timeline",
            "rows": [
                {
                    **row,
                    "account_id": account["account_id"],
                    "case_family": account["case_family"],
                }
                for row in account["rows"]
            ],
        }
        for account in accounts
    ]

    engine_result = engine.run(engine_input)

    reconstruction_results = {}
    packets = {}
    predictions = {}
    missing_facts = {}
    stale_trap_leaks = {}
    engine_storage_metrics = {}

    raw_payload = {}
    packet_payload = {}

    for account, result in zip(accounts, engine_result["results"]):
        account_id = account["account_id"]

        original_rows = [
            {
                **row,
                "account_id": account["account_id"],
                "case_family": account["case_family"],
            }
            for row in account["rows"]
        ]

        decision = result["decision"]
        reconstructed = decision["reconstructed_rows"]

        reconstruction_results[account_id] = reconstructed == original_rows

        packet = runner.build_prmr_packet(reconstructed)
        packets[account_id] = packet
        predictions[account_id] = runner.classify_prmr(packet)

        raw_payload[account_id] = estimate_tokens(original_rows)
        packet_payload[account_id] = estimate_tokens(packet)

        ptext = packet_text(packet)

        expected_facts = EXPECTED_PATTERN_FACTS[account_id]
        missing_facts[account_id] = [
            fact for fact in expected_facts
            if fact.lower() not in ptext
        ]

        stale_trap_leaks[account_id] = [
            phrase for phrase in [
                "fake_current",
                "stale duplicate",
                "close account immediately without review",
                "customer is malicious fraud actor",
                "money mule pattern confirmed",
                "skip api and launch public beta immediately",
                "normal ordinary household spending only",
            ]
            if phrase in ptext
        ]

        engine_storage_metrics[account_id] = {
            "policy_mode": decision.get("policy_mode"),
            "raw_size": decision.get("raw_size"),
            "policy_size": decision.get("policy_size"),
            "policy_compression_ratio": decision.get("policy_compression_ratio"),
            "policy_saved_percentage": decision.get("policy_saved_percentage"),
        }

    total_raw_tokens = sum(raw_payload.values())
    total_packet_tokens = sum(packet_payload.values())
    token_reduction = round((1 - total_packet_tokens / total_raw_tokens) * 100, 2)

    prediction_matches = {
        account_id: predictions[account_id] == EXPECTED_LABELS[account_id]
        for account_id in EXPECTED_LABELS
    }

    fact_preservation_matches = {
        account_id: len(missing) == 0
        for account_id, missing in missing_facts.items()
    }

    stale_trap_clean = {
        account_id: len(leaks) == 0
        for account_id, leaks in stale_trap_leaks.items()
    }

    add_check(
        checks,
        "all_timelines_reconstruct_exactly_before_packet_building",
        all(reconstruction_results.values()),
        reconstruction_results
    )

    add_check(
        checks,
        "prmr_continuity_packet_is_smaller_than_raw_timelines",
        total_packet_tokens < total_raw_tokens,
        {
            "total_raw_tokens": total_raw_tokens,
            "total_packet_tokens": total_packet_tokens,
            "token_reduction_percentage": token_reduction,
            "raw_payload_by_account": raw_payload,
            "packet_payload_by_account": packet_payload,
        }
    )

    add_check(
        checks,
        "prmr_packet_preserves_required_pattern_facts",
        all(fact_preservation_matches.values()),
        {
            "fact_preservation_matches": fact_preservation_matches,
            "missing_facts": missing_facts,
        }
    )

    add_check(
        checks,
        "prmr_packet_excludes_stale_fake_current_traps",
        all(stale_trap_clean.values()),
        {
            "stale_trap_clean": stale_trap_clean,
            "stale_trap_leaks": stale_trap_leaks,
        }
    )

    add_check(
        checks,
        "classification_recomputes_from_prmr_packets",
        all(prediction_matches.values()),
        {
            "predictions": predictions,
            "expected_labels": EXPECTED_LABELS,
            "prediction_matches": prediction_matches,
        }
    )

    account_packet_field_coverage = {
        account_id: {
            "has_current_state": bool(packet.get("current_state")),
            "has_review_action": bool(packet.get("review_action")),
            "has_risk_or_counter_or_human_context": bool(
                packet.get("risk_signals")
                or packet.get("counter_evidence")
                or packet.get("human_context")
            )
        }
        for account_id, packet in packets.items()
    }

    add_check(
        checks,
        "prmr_packets_have_required_signal_field_coverage",
        all(
            coverage["has_current_state"]
            and coverage["has_review_action"]
            and coverage["has_risk_or_counter_or_human_context"]
            for coverage in account_packet_field_coverage.values()
        ),
        account_packet_field_coverage
    )

    public_preview = {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": "0.46.1",
        "report_type": "pattern_preservation_compression_audit",
        "public_safe": True,
        "synthetic_only": True,
        "account_count": len(accounts),
        "total_raw_tokens": total_raw_tokens,
        "total_packet_tokens": total_packet_tokens,
        "token_reduction_percentage": token_reduction,
        "prediction_accuracy": round(
            sum(1 for ok in prediction_matches.values() if ok) / len(prediction_matches) * 100,
            2
        ),
        "pattern_fact_preservation_rate": round(
            sum(1 for ok in fact_preservation_matches.values() if ok) / len(fact_preservation_matches) * 100,
            2
        ),
        "stale_trap_exclusion_rate": round(
            sum(1 for ok in stale_trap_clean.values() if ok) / len(stale_trap_clean) * 100,
            2
        ),
    }

    public_forbidden = public_safety_scan(public_preview)

    add_check(
        checks,
        "public_report_preview_exposes_no_private_labels_or_engine_internals",
        len(public_forbidden) == 0,
        {"forbidden_terms_found": public_forbidden}
    )

    passed_count = sum(1 for check in checks if check["passed"])
    total_checks = len(checks)
    result = "PASS" if passed_count == total_checks else "NEEDS_WORK"

    public_report = {
        **public_preview,
        "timestamp": datetime.now().isoformat(),
        "passed_checks": passed_count,
        "total_checks": total_checks,
        "result": result,
        "checks": [
            {"name": check["name"], "passed": check["passed"]}
            for check in checks
        ],
        "safe_claim": (
            "V0.46.1 tests whether PRMR's smaller continuity packets preserve the pattern information needed for fraud-continuity classification. "
            "In this synthetic audit, PRMR packets stayed smaller than raw timelines while preserving required pattern facts, excluding stale traps, and allowing classification to recompute from the packets."
        ),
        "honest_boundary": (
            "Synthetic internal audit only. This proves pattern preservation inside the simulator, not real-world banking performance or compliance approval."
        ),
        "next_phase": "V0.46.2 Fraud Baseline War Integrity Audit or V0.47 Explainability Report",
    }

    private_report = {
        **public_report,
        "public_safe": False,
        "private_packets": packets,
        "private_predictions": predictions,
        "private_missing_facts": missing_facts,
        "private_stale_trap_leaks": stale_trap_leaks,
        "private_engine_storage_metrics": engine_storage_metrics,
        "private_checks": checks,
        "protected_note": "Private report includes packets, predictions, and pattern preservation diagnostics. Do not publish."
    }

    public_path = OUT_DIR / "public_pattern_preservation_compression_audit_v0461.json"
    private_path = OUT_DIR / "private_internal_pattern_preservation_compression_audit_v0461.json"
    scorecard_path = OUT_DIR / "scorecard_v0461.md"

    public_path.write_text(json.dumps(public_report, indent=4), encoding="utf-8")
    private_path.write_text(json.dumps(private_report, indent=4), encoding="utf-8")

    md = [
        "# PRMR V0.46.1 Pattern Preservation + Compression Audit",
        "",
        "Company: Afternum Industries  ",
        "Product: PRMR Memory Core  ",
        "Version: V0.46.1  ",
        "",
        "## Result",
        "",
        f"**{result}**",
        "",
        f"Passed: **{passed_count}/{total_checks}**",
        "",
        "## Compression",
        "",
        f"- Raw timeline tokens: **{total_raw_tokens}**",
        f"- PRMR packet tokens: **{total_packet_tokens}**",
        f"- Reduction: **{token_reduction}%**",
        "",
        "## Preservation",
        "",
        f"- Prediction accuracy from packets: **{public_preview['prediction_accuracy']}%**",
        f"- Pattern fact preservation rate: **{public_preview['pattern_fact_preservation_rate']}%**",
        f"- Stale trap exclusion rate: **{public_preview['stale_trap_exclusion_rate']}%**",
        "",
        "## Safe Claim",
        "",
        public_report["safe_claim"],
        "",
        "## Honest Boundary",
        "",
        public_report["honest_boundary"],
        "",
        "## Checks",
        "",
    ]

    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        md.append(f"- **{status}** — {check['name']}")

    md.extend([
        "",
        "## Meaning",
        "",
        "This audit checks that PRMR is not merely producing a smaller output.",
        "",
        "It checks whether the smaller continuity packet still preserves useful pattern information and excludes stale/fake traps.",
        "",
        "## Build Mantra",
        "",
        "Test. Break. Patch. Rerun. Score. Climb.",
        "",
    ])

    scorecard_path.write_text("\n".join(md), encoding="utf-8")

    print("Passed checks:", f"{passed_count}/{total_checks}")
    print("Result:", result)
    print()
    print("Compression:")
    print("- raw_timeline_tokens:", total_raw_tokens)
    print("- prmr_packet_tokens:", total_packet_tokens)
    print("- reduction:", str(token_reduction) + "%")
    print()
    print("Preservation:")
    print("- prediction_accuracy_from_packets:", str(public_preview["prediction_accuracy"]) + "%")
    print("- pattern_fact_preservation_rate:", str(public_preview["pattern_fact_preservation_rate"]) + "%")
    print("- stale_trap_exclusion_rate:", str(public_preview["stale_trap_exclusion_rate"]) + "%")
    print()
    print("Check list:")
    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        print("-", check["name"] + ":", status)
    print()
    print("Created:")
    print(public_path)
    print(private_path)
    print(scorecard_path)


if __name__ == "__main__":
    main()