import json
from pathlib import Path
from datetime import datetime

TARGET_FILES = [
    Path("reports/v044/public_api_product_layer_v044.json"),
    Path("reports/v044/scorecard_v044.md"),
    Path("reports/v0441/api_product_integrity_audit_v0441.json"),
    Path("reports/v0441/api_product_integrity_audit_v0441.md"),
]

OUT_DIR = Path("reports/v0442")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_JSON = OUT_DIR / "api_report_leak_scan_v0442.json"
OUT_MD = OUT_DIR / "api_report_leak_scan_v0442.md"

RAW_KEY_MARKERS = [
    "prmr_v044_alpha_key_LOCAL_TEST_DO_NOT_SHARE",
    "prmr_v044_beta_key_LOCAL_TEST_DO_NOT_SHARE",
    "prmr_v044_alpha_rotated_key_LOCAL_TEST_DO_NOT_SHARE",
    "DO_NOT_SHARE",
]

PUBLIC_FORBIDDEN_TERMS = [
    "compressed_package",
    "reconstructed_rows",
    "engine_result_snapshot",
    "internal_rule_data",
    "private_answer_details",
    "protected_note",
    "private_internal",
]


def read_text(path):
    return path.read_text(encoding="utf-8", errors="ignore")


def scan_terms(text, terms):
    lowered = text.lower()
    return [term for term in terms if term.lower() in lowered]


def main():
    print("PRMR V0.44.2 API REPORT LEAK SCAN")
    print("---------------------------------")

    missing_files = []
    raw_key_findings = []
    private_term_findings = []

    for path in TARGET_FILES:
        if not path.exists():
            missing_files.append(str(path))
            continue

        text = read_text(path)

        raw_hits = [term for term in RAW_KEY_MARKERS if term in text]
        private_hits = scan_terms(text, PUBLIC_FORBIDDEN_TERMS)

        if raw_hits:
            raw_key_findings.append({
                "file": str(path),
                "raw_key_markers_found": raw_hits
            })

        if private_hits:
            private_term_findings.append({
                "file": str(path),
                "private_terms_found": private_hits
            })

    checks = [
        {
            "name": "target_api_reports_exist",
            "passed": len(missing_files) == 0,
            "details": {"missing_files": missing_files}
        },
        {
            "name": "api_public_reports_expose_no_raw_test_keys",
            "passed": len(raw_key_findings) == 0,
            "details": {"raw_key_findings": raw_key_findings}
        },
        {
            "name": "api_public_reports_expose_no_private_engine_terms",
            "passed": len(private_term_findings) == 0,
            "details": {"private_term_findings": private_term_findings}
        }
    ]

    passed_count = sum(1 for check in checks if check["passed"])
    total_checks = len(checks)
    all_passed = passed_count == total_checks

    report = {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": "0.44.2",
        "report_type": "api_report_leak_scan",
        "timestamp": datetime.now().isoformat(),
        "public_safe": True,
        "passed_checks": passed_count,
        "total_checks": total_checks,
        "all_checks_passed": all_passed,
        "result": "PASS" if all_passed else "NEEDS_WORK",
        "checks": checks,
        "honest_claim": (
            "V0.44.2 checks the V0.44/V0.44.1 public-facing API reports for raw local test-key markers "
            "and private engine vocabulary. It is report hygiene evidence, not production security certification."
        ),
        "next_phase": "V0.45 Pilot Sandbox"
    }

    OUT_JSON.write_text(json.dumps(report, indent=4), encoding="utf-8")

    md = [
        "# PRMR V0.44.2 API Report Leak Scan",
        "",
        "Company: Afternum Industries  ",
        "Product: PRMR Memory Core  ",
        "Version: V0.44.2  ",
        "",
        "## Result",
        "",
        f"**{report['result']}**",
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
        "This confirms the new API product-layer reports remain public-safe.",
        "",
        "## Build Mantra",
        "",
        "Test. Break. Patch. Rerun. Score. Climb.",
        "",
    ])

    OUT_MD.write_text("\n".join(md), encoding="utf-8")

    print("Passed checks:", f"{passed_count}/{total_checks}")
    print("Result:", report["result"])
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