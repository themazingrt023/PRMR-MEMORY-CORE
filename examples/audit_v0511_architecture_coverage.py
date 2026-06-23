import json
from pathlib import Path
from datetime import datetime


VERSION = "0.51.1"

DOC_PATH = Path("docs/product_clarity_v051.md")

REPORT_DIR = Path("reports/v0511")
PUBLIC_PATH = REPORT_DIR / "public_architecture_coverage_v0511.json"
PRIVATE_PATH = REPORT_DIR / "private_internal_architecture_coverage_v0511.json"
SCORECARD_PATH = REPORT_DIR / "scorecard_v0511.md"

INSPECTED_PATHS = [
    DOC_PATH,
    Path("reports/v045/public_fraud_continuity_simulator_v045.json"),
    Path("reports/v045/private_internal_fraud_continuity_simulator_v045.json"),
    Path("reports/v046/public_fraud_baseline_war_v046.json"),
    Path("reports/v0461/public_pattern_preservation_compression_audit_v0461.json"),
    Path("reports/v047/public_fraud_explainability_report_v047.json"),
    Path("reports/v048/public_human_harm_reduction_test_v048.json"),
    Path("reports/v049/fraud_track_master_gauntlet_v049.json"),
    Path("reports/v050/whole_core_truth_gauntlet_v050.json"),
    Path("benchmarks/runners/run_fraud_continuity_simulator_v045.py"),
    Path("benchmarks/runners/run_fraud_baseline_war_v046.py"),
    Path("benchmarks/runners/run_fraud_explainability_report_v047.py"),
    Path("benchmarks/runners/run_human_harm_reduction_test_v048.py"),
    Path("benchmarks/runners/run_api_product_layer_v044.py"),
    Path("benchmarks/runners/run_security_isolation_deep_v0363.py"),
    Path("prmr/product/api_product_layer_v044.py"),
    Path("prmr/security/access_layer.py"),
]

ARCHITECTURE_PIECES = [
    "Event Intake Layer",
    "Entity Resolver",
    "Continuity Graph",
    "Role Classifier",
    "Evidence Provenance Engine",
    "Dormant Chain Memory",
    "Recurrence Detection",
    "Least-Harm Action Engine",
    "Bank-Safe Explanation Packets",
    "Federated PRMR Layer",
]

ALLOWED_STATUSES = {
    "implemented",
    "simulated",
    "partial",
    "missing",
    "future_enterprise_layer",
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


def read_text(path):
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def load_json_safe(path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return None


def scan_terms(text, terms):
    lowered = text.lower()
    return [term for term in terms if term.lower() in lowered]


def inspect_repo():
    file_records = []
    corpus_parts = []

    for path in INSPECTED_PATHS:
        text = read_text(path)
        exists = path.exists()

        file_records.append({
            "path": str(path),
            "exists": exists,
            "byte_count": len(text.encode("utf-8")),
        })

        if exists:
            corpus_parts.append(text)

    corpus = "\n".join(corpus_parts).lower()
    v050 = load_json_safe(Path("reports/v050/whole_core_truth_gauntlet_v050.json")) or {}

    flags = {
        "clarity_doc_exists": DOC_PATH.exists(),
        "v050_pass": v050.get("result") == "PASS" and v050.get("passed_checks") == v050.get("total_checks"),
        "event_intake_terms": all(term in corpus for term in ["event intake", "ingest"]),
        "state_transform_terms": "what changed" in corpus or "current_state" in corpus,
        "api_ingest_exists": "def ingest" in corpus and "rows" in corpus,
        "entity_node_terms": any(term in corpus for term in ["account_id", "client_id", "vault_id", "namespace"]),
        "broad_entity_terms": any(term in corpus for term in ["device", "recipient", "payee", "merchant", "invoice", "wallet"]),
        "continuity_packet_terms": "continuity_packet" in corpus or "continuity packet" in corpus,
        "money_flow_terms": any(term in corpus for term in ["money", "cash-out", "off-ramp", "recipient", "funds"]),
        "role_terms": all(term in corpus for term in ["possible_scam_victim", "possible_coercion_or_pressured_mule", "likely_false_positive"]),
        "evidence_terms": all(term in corpus for term in ["supporting", "counter_evidence"]),
        "dormant_terms": any(term in corpus for term in ["dormant", "unresolved", "last known", "recurrence triggers"]),
        "recurrence_terms": any(term in corpus for term in ["recurrence", "repeated structure", "timing rhythm", "pattern preservation"]),
        "least_harm_terms": any(term in corpus for term in ["least-harm", "harm_safe", "protect_and_support", "release cleared funds"]),
        "explanation_packet_terms": any(term in corpus for term in ["explanation", "customer-safe", "safe labels", "bank-safe"]),
        "federated_terms": any(term in corpus for term in ["federated", "institutions", "pattern signatures", "raw data"]),
    }

    return {
        "files": file_records,
        "flags": flags,
    }


def build_coverage(flags):
    return [
        {
            "piece": "Event Intake Layer",
            "status": "partial",
            "rationale": (
                "The repo has event-intake intent in V0.51 and API-shaped ingest plus synthetic timelines, "
                "but it does not yet contain a production raw-activity transformer."
            ),
            "evidence": [
                "V0.51 clarity pack names event intake",
                "V0.44 API product layer exposes ingest",
                "V0.45-V0.48 synthetic timelines feed continuity tests",
            ],
        },
        {
            "piece": "Entity Resolver",
            "status": "partial" if flags["entity_node_terms"] else "missing",
            "rationale": (
                "The repo tracks account/client/vault scoped nodes and some device or recipient context, "
                "but there is no general resolver for people, companies, devices, emails, phones, wallets, payees, invoices, sessions, merchants, and platforms."
            ),
            "evidence": [
                "Account and client scoped fields appear in fraud and API tests",
                "No dedicated resolver module or broad entity-linking contract was found",
            ],
        },
        {
            "piece": "Continuity Graph",
            "status": "simulated",
            "rationale": (
                "Synthetic fraud-continuity tests preserve origin, current state, risk signals, counter-evidence, review action, and pattern facts. "
                "This is graph-shaped continuity evidence, but not yet a persistent money-flow graph engine."
            ),
            "evidence": [
                "V0.45 continuity packets",
                "V0.46 and V0.46.1 pattern preservation reports",
                "V0.49 fraud-track gauntlet",
            ],
        },
        {
            "piece": "Role Classifier",
            "status": "simulated",
            "rationale": (
                "The fraud track classifies synthetic roles such as scam victim, pressured mule risk, account takeover victim, false positive, normal user, and investigation-worthy pattern. "
                "The wording keeps a human-review boundary and avoids certain-guilt labels."
            ),
            "evidence": [
                "V0.45 role classification",
                "V0.47 safe labels",
                "V0.48 harm-safe actions",
            ],
        },
        {
            "piece": "Evidence Provenance Engine",
            "status": "partial",
            "rationale": (
                "Explainability and integrity audits check supporting evidence, counter-evidence, reconstruction, and explanation consistency. "
                "There is not yet a standalone provenance engine tied to full money-flow lineage."
            ),
            "evidence": [
                "V0.47 explanation checks",
                "V0.47.1 explainability integrity audit",
                "V0.48.1 harm integrity audit",
            ],
        },
        {
            "piece": "Dormant Chain Memory",
            "status": "missing",
            "rationale": (
                "The clarity pack describes stale and unresolved context goals, but current fraud reports do not prove a durable dormant-chain store for unresolved endpoints, missing evidence, causal scars, or recurrence triggers."
            ),
            "evidence": [
                "V0.51 describes stale and review-oriented continuity",
                "No durable dormant-chain store was found",
            ],
        },
        {
            "piece": "Recurrence Detection",
            "status": "simulated",
            "rationale": (
                "V0.46.1 tests pattern preservation and stale-trap exclusion across synthetic cases. "
                "This shows repeated-structure handling in simulation, but not full recurrence detection across changing real-world surfaces."
            ),
            "evidence": [
                "V0.46.1 pattern preservation and compression audit",
                "V0.46.2 pattern integrity audit",
            ],
        },
        {
            "piece": "Least-Harm Action Engine",
            "status": "simulated",
            "rationale": (
                "V0.48 assigns proportionate synthetic actions such as protect and support, safeguarding review, account access protection, investigation review, no escalation, and false-positive avoidance. "
                "This is not a deployed action engine."
            ),
            "evidence": [
                "V0.48 human harm reduction test",
                "V0.48.1 harm integrity audit",
                "V0.48.2 harm report leak scan",
            ],
        },
        {
            "piece": "Bank-Safe Explanation Packets",
            "status": "simulated",
            "rationale": (
                "V0.47 generates safe synthetic explanation packets with supporting and review evidence, context or counter-evidence, and human-review boundary language. "
                "They are not bank-approved production explanation packets."
            ),
            "evidence": [
                "V0.47 fraud explainability report",
                "V0.47.1 explainability integrity audit",
                "V0.47.2 report leak scan",
            ],
        },
        {
            "piece": "Federated PRMR Layer",
            "status": "future_enterprise_layer",
            "rationale": (
                "No implemented or simulated federated layer was found. "
                "This remains a future enterprise architecture layer where institutions would keep data separate and share only legally allowed safe pattern signatures."
            ),
            "evidence": [
                "No federated implementation evidence found in current repo inspection",
            ],
        },
    ]


def public_projection(coverage):
    return [
        {
            "piece": item["piece"],
            "status": item["status"],
            "rationale": item["rationale"],
            "evidence": item["evidence"],
        }
        for item in coverage
    ]


def validate_coverage(public_report, private_report):
    checks = []
    coverage = public_report["coverage"]
    piece_names = [item["piece"] for item in coverage]

    checks.append({
        "name": "all_10_architecture_pieces_covered",
        "passed": sorted(piece_names) == sorted(ARCHITECTURE_PIECES) and len(coverage) == 10,
        "details": {
            "covered_count": len(coverage),
            "missing_pieces": sorted(set(ARCHITECTURE_PIECES) - set(piece_names)),
            "extra_pieces": sorted(set(piece_names) - set(ARCHITECTURE_PIECES)),
        },
    })

    invalid_statuses = [
        {"piece": item["piece"], "status": item["status"]}
        for item in coverage
        if item["status"] not in ALLOWED_STATUSES
    ]

    checks.append({
        "name": "all_statuses_are_allowed",
        "passed": len(invalid_statuses) == 0,
        "details": {"invalid_statuses": invalid_statuses},
    })

    public_text = json.dumps(public_report, sort_keys=True)
    forbidden_hits = scan_terms(public_text, PUBLIC_FORBIDDEN_TERMS)
    unsafe_hits = scan_terms(public_text, UNSAFE_PUBLIC_LANGUAGE)

    checks.append({
        "name": "public_report_exposes_no_restricted_packet_terms",
        "passed": len(forbidden_hits) == 0,
        "details": {"forbidden_terms_found": forbidden_hits},
    })

    checks.append({
        "name": "public_report_avoids_punitive_or_certain_guilt_language",
        "passed": len(unsafe_hits) == 0,
        "details": {"unsafe_language_found": unsafe_hits},
    })

    implemented_count = sum(1 for item in coverage if item["status"] == "implemented")

    checks.append({
        "name": "not_every_piece_is_marked_implemented",
        "passed": implemented_count < len(coverage),
        "details": {"implemented_count": implemented_count, "total_pieces": len(coverage)},
    })

    federated = next((item for item in coverage if item["piece"] == "Federated PRMR Layer"), None)

    checks.append({
        "name": "federated_layer_not_falsely_marked_implemented",
        "passed": federated is not None and federated["status"] == "future_enterprise_layer",
        "details": {"federated_status": federated.get("status") if federated else None},
    })

    evidence_gaps = [
        item["piece"]
        for item in coverage
        if not item.get("rationale") or not item.get("evidence")
    ]

    checks.append({
        "name": "each_piece_has_rationale_and_evidence_note",
        "passed": len(evidence_gaps) == 0,
        "details": {"evidence_gaps": evidence_gaps},
    })

    inspected_files = private_report["repo_inspection"]["files"]
    missing_inspection_files = [
        item["path"]
        for item in inspected_files
        if not item["exists"]
    ]

    checks.append({
        "name": "required_evidence_files_were_inspected",
        "passed": DOC_PATH.exists() and Path("reports/v050/whole_core_truth_gauntlet_v050.json").exists(),
        "details": {
            "missing_inspection_files": missing_inspection_files,
            "required_minimum_files_present": DOC_PATH.exists() and Path("reports/v050/whole_core_truth_gauntlet_v050.json").exists(),
        },
    })

    return checks


def build_scorecard(public_report):
    lines = [
        "# PRMR V0.51.1 Ten-Piece Architecture Coverage Test",
        "",
        "Company: Afternum Industries  ",
        "Product: PRMR Memory Core  ",
        "Version: V0.51.1  ",
        "",
        "## Result",
        "",
        f"**{public_report['result']}**",
        "",
        f"Passed checks: **{public_report['passed_checks']}/{public_report['total_checks']}**",
        "",
        "## Coverage",
        "",
        "| Piece | Status |",
        "|---|---|",
    ]

    for item in public_report["coverage"]:
        lines.append(f"| {item['piece']} | {item['status']} |")

    lines.extend([
        "",
        "## Meaning",
        "",
        "This audit checks whether the future banking and fraud-continuity architecture is mapped honestly against current repo evidence.",
        "",
        "Passing means the coverage map is complete, public-safe, and does not claim all pieces are implemented.",
        "",
        "It does not claim production readiness, bank approval, compliance approval, external security review, or real-client validation.",
        "",
    ])

    return "\n".join(lines)


def main():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    inspection = inspect_repo()
    coverage = build_coverage(inspection["flags"])

    public_report = {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": VERSION,
        "report_type": "ten_piece_architecture_coverage",
        "timestamp": datetime.now().isoformat(),
        "public_safe": True,
        "result": "NEEDS_WORK",
        "passed_checks": 0,
        "total_checks": 0,
        "all_checks_passed": False,
        "architecture_domain": "future banking and fraud-continuity architecture",
        "coverage": public_projection(coverage),
        "status_counts": {},
        "honest_boundary": (
            "This is a controlled repo coverage audit. It maps implemented, simulated, partial, missing, and future enterprise layers. "
            "It does not claim production readiness, bank approval, compliance approval, external security review, or real-client validation."
        ),
        "next_phase_gaps": [
            "Build a real event transformation contract for raw activity intake.",
            "Design a general entity resolver across people, accounts, devices, contact channels, wallets, payees, invoices, sessions, merchants, and platforms.",
            "Create a persistent continuity graph for money-flow and unresolved endpoints.",
            "Add a durable dormant-chain memory store.",
            "Promote recurrence detection from synthetic pattern preservation to explicit cross-case detection.",
            "Keep federated PRMR as a future enterprise layer until legal, security, and data-sharing constraints are specified.",
        ],
    }

    private_report = {
        **public_report,
        "public_safe": False,
        "coverage": coverage,
        "repo_inspection": inspection,
        "restricted_note": "Restricted report includes inspected file paths and evidence flags for audit debugging.",
    }

    checks = validate_coverage(public_report, private_report)
    passed_count = sum(1 for check in checks if check["passed"])
    total_checks = len(checks)
    all_passed = passed_count == total_checks
    status_counts = {
        status: sum(1 for item in coverage if item["status"] == status)
        for status in sorted(ALLOWED_STATUSES)
    }

    public_report["checks"] = [
        {
            "name": check["name"],
            "passed": check["passed"],
        }
        for check in checks
    ]
    public_report["passed_checks"] = passed_count
    public_report["total_checks"] = total_checks
    public_report["all_checks_passed"] = all_passed
    public_report["result"] = "PASS" if all_passed else "NEEDS_WORK"
    public_report["status_counts"] = status_counts

    private_report["checks"] = checks
    private_report["passed_checks"] = passed_count
    private_report["total_checks"] = total_checks
    private_report["all_checks_passed"] = all_passed
    private_report["result"] = public_report["result"]
    private_report["status_counts"] = status_counts

    PUBLIC_PATH.write_text(json.dumps(public_report, indent=4), encoding="utf-8")
    PRIVATE_PATH.write_text(json.dumps(private_report, indent=4), encoding="utf-8")
    SCORECARD_PATH.write_text(build_scorecard(public_report), encoding="utf-8")

    print("PRMR V0.51.1 TEN-PIECE ARCHITECTURE COVERAGE TEST")
    print("--------------------------------------------------")
    print("Result:", public_report["result"])
    print("Passed checks:", f"{passed_count}/{total_checks}")
    print()
    print("Coverage statuses:")
    for item in coverage:
        print("-", item["piece"] + ":", item["status"])
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


if __name__ == "__main__":
    main()
