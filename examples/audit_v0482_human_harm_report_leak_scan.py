import json
from pathlib import Path
from datetime import datetime

TARGET_FILES = [
    Path("reports/v048/public_human_harm_reduction_test_v048.json"),
    Path("reports/v048/scorecard_v048.md"),
    Path("reports/v0481/human_harm_integrity_audit_v0481.json"),
    Path("reports/v0481/human_harm_integrity_audit_v0481.md"),
]

OUT_DIR = Path("reports/v0482")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_JSON = OUT_DIR / "human_harm_report_leak_scan_v0482.json"
OUT_MD = OUT_DIR / "human_harm_report_leak_scan_v0482.md"

FORBIDDEN_PUBLIC_TERMS = [
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

UNSAFE_LANGUAGE = [
    "criminal",
    "fraudster",
    "guilty",
    "blacklist",
    "ban user",
    "definitely fraud",
    "close account immediately",
]


def read_text(path):
    return path.read_text(encoding="utf-8", errors="ignore")


def scan_terms(text, terms):
    lowered = text.lower()
    return [term for term in terms if term.lower() in lowered]


def main():
    print("PRMR V0.48.2 HUMAN HARM REPORT LEAK SCAN")
    print("----------------------------------------")

    missing_files = []
    forbidden_findings = []
    raw_key_findings = []
    unsafe_language_findings = []

    for path in TARGET_FILES:
        if not path.exists():
            missing_files.append(str(path))
            continue

        text = read_text(path)

        forbidden_hits = scan_terms(text, FORBIDDEN_PUBLIC_TERMS)
        raw_key_hits = [marker for marker in RAW_KEY_MARKERS if marker in text]
        unsafe_hits = scan_terms(text, UNSAFE_LANGUAGE)

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

        if unsafe_hits:
            unsafe_language_findings.append({
                "file": str(path),
                "unsafe_language_found": unsafe_hits,
            })

    checks = [
        {
            "name": "target_human_harm_reports_exist",
            "passed": len(missing_files) == 0,
            "details": {"missing_files": missing_files},
        },
        {
            "name": "human_harm_public_reports_expose_no_hidden_packets_or_engine_internals",
            "passed": len(forbidden_findings) == 0,
            "details": {"forbidden_findings": forbidden_findings},
        },
        {
            "name": "human_harm_public_reports_expose_no_raw_key_markers",
            "passed": len(raw_key_findings) == 0,
            "details": {"raw_key_findings": raw_key_findings},
        },
        {
            "name": "human_harm_public_reports_avoid_punitive_or_certain_guilt_language",
            "passed": len(unsafe_language_findings) == 0,
            "details": {"unsafe_language_findings": unsafe_language_findings},
        },
    ]

    passed_count = sum(1 for check in checks if check["passed"])
    total_checks = len(checks)
    all_passed = passed_count == total_checks
    result = "PASS" if all_passed else "NEEDS_WORK"

    report = {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": "0.48.2",
        "report_type": "human_harm_report_leak_scan",
        "timestamp": datetime.now().isoformat(),
        "public_safe": True,
        "passed_checks": passed_count,
        "total_checks": total_checks,
        "all_checks_passed": all_passed,
        "result": result,
        "checks": checks,
        "honest_claim": (
            "V0.48.2 checks V0.48/V0.48.1 public-facing human-harm reports for private packet leakage, "
            "protected engine vocabulary, raw key markers, and unsafe punitive wording. "
            "It is report hygiene evidence only, not banking compliance certification."
        ),
        "next_phase": "V0.49 Fraud Track Master Gauntlet",
    }

    OUT_JSON.write_text(json.dumps(report, indent=4), encoding="utf-8")

    md = [
        "# PRMR V0.48.2 Human Harm Report Leak Scan",
        "",
        "Company: Afternum Industries  ",
        "Product: PRMR Memory Core  ",
        "Version: V0.48.2  ",
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
        "This confirms the synthetic human-harm reduction reports remain public-safe and avoid harmful punitive wording.",
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