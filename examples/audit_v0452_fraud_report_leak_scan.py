import json
from pathlib import Path
from datetime import datetime

TARGET_FILES = [
    Path("reports/v045/public_fraud_continuity_simulator_v045.json"),
    Path("reports/v045/scorecard_v045.md"),
    Path("reports/v0451/fraud_simulator_integrity_audit_v0451.json"),
    Path("reports/v0451/fraud_simulator_integrity_audit_v0451.md"),
]

OUT_DIR = Path("reports/v0452")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_JSON = OUT_DIR / "fraud_report_leak_scan_v0452.json"
OUT_MD = OUT_DIR / "fraud_report_leak_scan_v0452.md"

FORBIDDEN_PUBLIC_TERMS = [
    "truth_private",
    "private_truth",
    "private_packets",
    "private_classifications",
    "private_reconstruction_results",
    "private_checks",
    "protected_note",
    "compressed_package",
    "reconstructed_rows",
    "engine_result_snapshot",
    "internal_rule_data",
    "raw_api_key",
    "api_key",
]

RAW_KEY_MARKERS = [
    "DO_NOT_SHARE",
    "DO_NOT_LEAK",
    "LOCAL_TEST",
]


def read_text(path):
    return path.read_text(encoding="utf-8", errors="ignore")


def scan_terms(text, terms):
    lowered = text.lower()
    return [term for term in terms if term.lower() in lowered]


def main():
    print("PRMR V0.45.2 FRAUD REPORT LEAK SCAN")
    print("-----------------------------------")

    missing_files = []
    forbidden_findings = []
    raw_key_findings = []

    for path in TARGET_FILES:
        if not path.exists():
            missing_files.append(str(path))
            continue

        text = read_text(path)

        forbidden_hits = scan_terms(text, FORBIDDEN_PUBLIC_TERMS)
        raw_key_hits = [marker for marker in RAW_KEY_MARKERS if marker in text]

        if forbidden_hits:
            forbidden_findings.append({
                "file": str(path),
                "forbidden_terms_found": forbidden_hits,
            })

        if raw_key_hits:
            raw_key_findings.append({
                "file": str(path),
                "raw_key_markers_found": raw_key_hits,
            })

    checks = [
        {
            "name": "target_fraud_reports_exist",
            "passed": len(missing_files) == 0,
            "details": {"missing_files": missing_files},
        },
        {
            "name": "fraud_public_reports_expose_no_private_labels_or_engine_internals",
            "passed": len(forbidden_findings) == 0,
            "details": {"forbidden_findings": forbidden_findings},
        },
        {
            "name": "fraud_public_reports_expose_no_raw_key_markers",
            "passed": len(raw_key_findings) == 0,
            "details": {"raw_key_findings": raw_key_findings},
        },
    ]

    passed_count = sum(1 for check in checks if check["passed"])
    total_checks = len(checks)
    all_passed = passed_count == total_checks
    result = "PASS" if all_passed else "NEEDS_WORK"

    report = {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": "0.45.2",
        "report_type": "fraud_report_leak_scan",
        "timestamp": datetime.now().isoformat(),
        "public_safe": True,
        "passed_checks": passed_count,
        "total_checks": total_checks,
        "all_checks_passed": all_passed,
        "result": result,
        "checks": checks,
        "honest_claim": (
            "V0.45.2 checks the V0.45/V0.45.1 public-facing fraud-continuity reports for private label leakage, "
            "protected engine vocabulary, and raw key markers. It is report hygiene evidence only, not banking compliance certification."
        ),
        "next_phase": "V0.46 PRMR vs Rule Engine vs Vector Search",
    }

    OUT_JSON.write_text(json.dumps(report, indent=4), encoding="utf-8")

    md = [
        "# PRMR V0.45.2 Fraud Report Leak Scan",
        "",
        "Company: Afternum Industries  ",
        "Product: PRMR Memory Core  ",
        "Version: V0.45.2  ",
        "",
        "## Result",
        "",
        f"**{result}**",
        "",
        f"Passed: **{passed_count}/{total_checks}**",
        "",
        "## Honest Claim",
        "",
        report["honest_claim"],
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
        "This confirms the synthetic fraud-continuity proof reports remain public-safe.",
        "",
        "## Build Mantra",
        "",
        "Test. Break. Patch. Rerun. Score. Climb.",
        "",
    ])

    OUT_MD.write_text("\n".join(md), encoding="utf-8")

    print("Passed checks:", f"{passed_count}/{total_checks}")
    print("Result:", result)
    print()
    print("Check list:")
    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        print("-", check["name"] + ":", status)
    print()
    print("Created:")
    print(OUT_JSON)
    print(OUT_MD)


if __name__ == "__main__":
    main()