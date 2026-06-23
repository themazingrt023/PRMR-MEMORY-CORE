import json
from pathlib import Path
from datetime import datetime

REPORTS_ROOT = Path("reports")
OUT_DIR = Path("reports/v0432")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_JSON = OUT_DIR / "report_leak_scan_v0432.json"
OUT_MD = OUT_DIR / "report_leak_scan_v0432.md"

RAW_KEY_MARKERS = [
    "prmr_live_alpha_current_043_DO_NOT_LEAK",
    "prmr_live_alpha_old_revoked_043_DO_NOT_LEAK",
    "prmr_live_alpha_rotated_new_043_DO_NOT_LEAK",
    "prmr_live_beta_current_043_DO_NOT_LEAK",
    "prmr_wrong_key_043_DO_NOT_LEAK",
    "DO_NOT_LEAK",
]

PUBLIC_FORBIDDEN_TERMS = [
    "private_answer_details",
    "protected_note",
    "engine_result_snapshot",
    "reconstructed_rows",
    "compressed_package",
    "internal_rule_data",
    "private_internal",
    "x-prmr-api-key",
    "api_key",
    "secret",
]

PUBLIC_REPORT_PATTERNS = [
    "public_",
    "scorecard",
    "claim_hardening",
]


def read_text(path):
    return path.read_text(encoding="utf-8", errors="ignore")


def is_report_file(path):
    return path.suffix.lower() in {".json", ".md", ".txt"}


def is_public_facing(path):
    name = path.name.lower()
    return any(pattern in name for pattern in PUBLIC_REPORT_PATTERNS)


def scan_for_terms(text, terms, case_sensitive=False):
    if case_sensitive:
        return [term for term in terms if term in text]

    lowered = text.lower()
    return [term for term in terms if term.lower() in lowered]


def main():
    print("PRMR V0.43.2 REPORT + LOG LEAK SCAN")
    print("-----------------------------------")

    files_scanned = []
    raw_key_leaks = []
    public_internal_leaks = []

    for path in REPORTS_ROOT.rglob("*"):
        if not path.is_file():
            continue

        if not is_report_file(path):
            continue

        # Avoid scanning this audit output while it is being created.
        if "v0432" in str(path).replace("\\", "/"):
            continue

        text = read_text(path)
        files_scanned.append(str(path))

        raw_hits = scan_for_terms(text, RAW_KEY_MARKERS, case_sensitive=True)

        if raw_hits:
            raw_key_leaks.append({
                "file": str(path),
                "raw_key_markers_found": raw_hits
            })

        if is_public_facing(path):
            forbidden_hits = scan_for_terms(text, PUBLIC_FORBIDDEN_TERMS)

            if forbidden_hits:
                public_internal_leaks.append({
                    "file": str(path),
                    "forbidden_terms_found": forbidden_hits
                })

    checks = [
        {
            "name": "no_raw_key_markers_found_in_reports_or_scorecards",
            "passed": len(raw_key_leaks) == 0,
            "details": {
                "raw_key_leaks": raw_key_leaks
            }
        },
        {
            "name": "public_facing_reports_contain_no_private_internal_terms",
            "passed": len(public_internal_leaks) == 0,
            "details": {
                "public_internal_leaks": public_internal_leaks
            }
        },
        {
            "name": "reports_folder_was_scanned",
            "passed": len(files_scanned) > 0,
            "details": {
                "files_scanned_count": len(files_scanned)
            }
        }
    ]

    passed_count = sum(1 for check in checks if check["passed"])
    total_checks = len(checks)
    all_passed = passed_count == total_checks

    report = {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": "0.43.2",
        "report_type": "report_and_log_leak_scan",
        "timestamp": datetime.now().isoformat(),
        "public_safe": True,
        "passed_checks": passed_count,
        "total_checks": total_checks,
        "all_checks_passed": all_passed,
        "result": "PASS" if all_passed else "NEEDS_WORK",
        "files_scanned_count": len(files_scanned),
        "checks": checks,
        "honest_claim": (
            "V0.43.2 scans generated reports and scorecards for raw test-key markers and public/private report leakage. "
            "It does not scan the entire source tree, because the V0.43 runner intentionally contains fake local test keys as fixtures."
        ),
        "next_phase": "V0.44 API Product Layer"
    }

    OUT_JSON.write_text(json.dumps(report, indent=4), encoding="utf-8")

    md = f"""# PRMR V0.43.2 Report + Log Leak Scan

Company: Afternum Industries  
Product: PRMR Memory Core  
Version: V0.43.2  

## Result

**{report["result"]}**

Passed: **{passed_count}/{total_checks}**

Files scanned: **{len(files_scanned)}**

## Honest Claim

{report["honest_claim"]}

## Checks

"""

    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        md += f"- **{status}** — {check['name']}\n"

    if raw_key_leaks:
        md += "\n## Raw Key Marker Findings\n\n"
        for leak in raw_key_leaks:
            md += f"- {leak['file']}: {leak['raw_key_markers_found']}\n"

    if public_internal_leaks:
        md += "\n## Public Internal Leak Findings\n\n"
        for leak in public_internal_leaks:
            md += f"- {leak['file']}: {leak['forbidden_terms_found']}\n"

    md += """

## Meaning

This scan checks generated reports and scorecards for obvious raw key leakage and public/private boundary mistakes.

It is internal leak-scan evidence, not a formal security audit.

## Build Mantra

Test. Break. Patch. Rerun. Score. Climb.
"""

    OUT_MD.write_text(md, encoding="utf-8")

    print("Files scanned:", len(files_scanned))
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