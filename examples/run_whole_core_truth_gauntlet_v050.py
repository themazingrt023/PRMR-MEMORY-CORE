import json
import os
import re
import subprocess
from pathlib import Path
from datetime import datetime

OUT_DIR = Path("reports/v050")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_JSON = OUT_DIR / "whole_core_truth_gauntlet_v050.json"
OUT_MD = OUT_DIR / "whole_core_truth_gauntlet_v050.md"

SCRIPT_ROOTS = [
    Path("benchmarks/runners"),
    Path("examples"),
]

REPORT_ROOT = Path("reports")

EXCLUDE_SCRIPT_PARTS = [
    "build_",
    "patch_",
    "inspect_",
    "debug_",
    "fix_",
    "sanitize_",
    "show_",
    "open_",
    "run_whole_core_truth_gauntlet_v050.py",
    "run_baseline_war_v038.py",  # superseded by V0.38.1 anti-leak + V0.38.2 integrity audit
]

REQUIRED_VERSION_MARKERS = [
    "v036",
    "v037",
    "v038",
    "v039",
    "v040",
    "v041",
    "v042",
    "v043",
    "v044",
    "v045",
    "v046",
    "v047",
    "v048",
    "v049",
]

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
    "do_not_share",
    "do_not_leak",
    "local_test",
]

UNSAFE_PUBLIC_LANGUAGE = [
    "criminal",
    "fraudster",
    "guilty",
    "blacklist",
    "ban user",
    "definitely fraud",
    "close account immediately",
]


def should_run_script(path: Path) -> bool:
    name = path.name.lower()

    if not name.endswith(".py"):
        return False

    if not (name.startswith("run_") or name.startswith("audit_")):
        return False

    if "_v" not in name and "gauntlet" not in name:
        return False

    for excluded in EXCLUDE_SCRIPT_PARTS:
        if excluded in name:
            return False

    return True


def discover_scripts():
    scripts = []

    for root in SCRIPT_ROOTS:
        if not root.exists():
            continue

        for path in root.rglob("*.py"):
            if should_run_script(path):
                scripts.append(path)

    def sort_key(path):
        text = str(path).lower()
        version_match = re.search(r"v(\d{3,4})", text)
        version = int(version_match.group(1)) if version_match else 9999
        return (version, str(path))

    return sorted(set(scripts), key=sort_key)


def run_script(path: Path):
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    completed = subprocess.run(
        ["python", str(path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )

    output = (completed.stdout or "") + "\n" + (completed.stderr or "")

    bad_markers = [
        "Result: NEEDS_WORK",
        "NEEDS_WORK",
        "- FAIL",
        ": FAIL",
        "Traceback",
        "Error:",
        "ModuleNotFoundError",
        "AssertionError",
    ]

    bad_hits = [marker for marker in bad_markers if marker in output]

    positive_markers = [
        "Result: PASS",
        "All integrity checks passed: True",
        "All checks passed: True",
        "All tests passed: True",
        "Tests passed:",
        "Passed commands:",
        "PASS",
    ]

    positive_hits = [marker for marker in positive_markers if marker in output]

    passed = completed.returncode == 0 and len(bad_hits) == 0 and len(positive_hits) > 0

    return {
        "script": str(path),
        "returncode": completed.returncode,
        "passed": passed,
        "positive_markers_found": positive_hits,
        "bad_markers_found": bad_hits,
        "output_preview": output[-2500:],
    }


def load_json_safe(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception as exc:
        return {"__json_load_error__": str(exc)}


def is_public_report(path: Path, data) -> bool:
    lower = str(path).lower()
    name = path.name.lower()

    # V0.38 original is a superseded diagnostic that intentionally returned NEEDS_WORK.
    # Current proof is V0.38.1/V0.38.2.
    if ("reports\\v038\\" in lower or "reports/v038/" in lower) and "v0381" not in lower and "v0382" not in lower:
        return False

    if "private" in lower or "internal" in lower:
        return False

    if isinstance(data, dict) and data.get("public_safe") is False:
        return False

    # Only scan genuinely public-facing artifacts as public.
    # Older audit files may be internal evidence even if they are not under a private filename.
    if name.startswith("public_"):
        return True

    if name.startswith("scorecard_"):
        return True

    if "public" in name and name.endswith(".json"):
        return True

    return False


def scan_text_terms(text, terms):
    lowered = text.lower()
    return [term for term in terms if term.lower() in lowered]


def audit_reports():
    json_reports = sorted(REPORT_ROOT.rglob("*.json")) if REPORT_ROOT.exists() else []
    md_reports = sorted(REPORT_ROOT.rglob("*.md")) if REPORT_ROOT.exists() else []

    pass_count_failures = []
    json_load_failures = []
    public_leak_findings = []
    unsafe_language_findings = []
    public_safe_flag_findings = []

    for path in json_reports:
        data = load_json_safe(path)

        if isinstance(data, dict) and "__json_load_error__" in data:
            json_load_failures.append({
                "file": str(path),
                "error": data["__json_load_error__"],
            })
            continue

        if isinstance(data, dict) and "checks" in data and isinstance(data["checks"], list):
            recomputed_passed = sum(1 for check in data["checks"] if check.get("passed") is True)
            recomputed_total = len(data["checks"])

            if "passed_checks" in data and data["passed_checks"] != recomputed_passed:
                pass_count_failures.append({
                    "file": str(path),
                    "field": "passed_checks",
                    "reported": data.get("passed_checks"),
                    "recomputed": recomputed_passed,
                })

            if "total_checks" in data and data["total_checks"] != recomputed_total:
                pass_count_failures.append({
                    "file": str(path),
                    "field": "total_checks",
                    "reported": data.get("total_checks"),
                    "recomputed": recomputed_total,
                })

            if "all_integrity_checks_passed" in data:
                expected = recomputed_passed == recomputed_total
                if data["all_integrity_checks_passed"] != expected:
                    pass_count_failures.append({
                        "file": str(path),
                        "field": "all_integrity_checks_passed",
                        "reported": data.get("all_integrity_checks_passed"),
                        "recomputed": expected,
                    })

            if "all_checks_passed" in data:
                expected = recomputed_passed == recomputed_total
                if data["all_checks_passed"] != expected:
                    pass_count_failures.append({
                        "file": str(path),
                        "field": "all_checks_passed",
                        "reported": data.get("all_checks_passed"),
                        "recomputed": expected,
                    })

        if is_public_report(path, data):
            text = json.dumps(data, sort_keys=True).lower()

            forbidden_hits = scan_text_terms(text, FORBIDDEN_PUBLIC_TERMS)
            unsafe_hits = scan_text_terms(text, UNSAFE_PUBLIC_LANGUAGE)

            if forbidden_hits:
                public_leak_findings.append({
                    "file": str(path),
                    "forbidden_terms_found": forbidden_hits,
                })

            if unsafe_hits:
                unsafe_language_findings.append({
                    "file": str(path),
                    "unsafe_language_found": unsafe_hits,
                })

            if isinstance(data, dict) and data.get("public_safe") is False:
                public_safe_flag_findings.append({
                    "file": str(path),
                    "issue": "public-looking report has public_safe false",
                })

    for path in md_reports:
        lower = str(path).lower()

        # V0.38 original is a superseded diagnostic artifact, not current public proof.
        if ("reports\\v038\\" in lower or "reports/v038/" in lower) and "v0381" not in lower and "v0382" not in lower:
            continue

        if "private" in lower or "internal" in lower:
            continue

        text = path.read_text(encoding="utf-8", errors="ignore").lower()

        forbidden_hits = scan_text_terms(text, FORBIDDEN_PUBLIC_TERMS)
        unsafe_hits = scan_text_terms(text, UNSAFE_PUBLIC_LANGUAGE)

        if forbidden_hits:
            public_leak_findings.append({
                "file": str(path),
                "forbidden_terms_found": forbidden_hits,
            })

        if unsafe_hits:
            unsafe_language_findings.append({
                "file": str(path),
                "unsafe_language_found": unsafe_hits,
            })

    return {
        "json_report_count": len(json_reports),
        "markdown_report_count": len(md_reports),
        "json_load_failures": json_load_failures,
        "pass_count_failures": pass_count_failures,
        "public_leak_findings": public_leak_findings,
        "unsafe_language_findings": unsafe_language_findings,
        "public_safe_flag_findings": public_safe_flag_findings,
    }


def scan_source_integrity():
    source_files = []
    findings = []

    for root in SCRIPT_ROOTS:
        if not root.exists():
            continue

        for path in root.rglob("*.py"):
            source_files.append(path)
            text = path.read_text(encoding="utf-8", errors="ignore")

            for line_number, line in enumerate(text.splitlines(), start=1):
                stripped = line.strip()

                if not stripped or stripped.startswith("#"):
                    continue

                # Direct forced PASS lines are suspicious.
                if re.match(r'^(result|final_result)\s*=\s*["\']PASS["\']\s*$', stripped):
                    findings.append({
                        "file": str(path),
                        "line": line_number,
                        "reason": "direct_forced_pass_assignment",
                        "text": stripped,
                    })

                # Fixed pass counts are suspicious.
                if re.match(r"^passed_count\s*=\s*\d+\s*$", stripped):
                    findings.append({
                        "file": str(path),
                        "line": line_number,
                        "reason": "fixed_pass_count_assignment",
                        "text": stripped,
                    })

                if re.match(r"^all_passed\s*=\s*True\s*$", stripped):
                    findings.append({
                        "file": str(path),
                        "line": line_number,
                        "reason": "forced_all_passed_true",
                        "text": stripped,
                    })

    return {
        "source_file_count": len(source_files),
        "source_integrity_findings": findings,
    }


def check_version_coverage(scripts, reports):
    script_text = " ".join(str(path).lower() for path in scripts)
    report_text = json.dumps(reports).lower()

    missing_markers = []

    for marker in REQUIRED_VERSION_MARKERS:
        if marker not in script_text and marker not in report_text:
            missing_markers.append(marker)

    return missing_markers


def main():
    print("PRMR V0.50 WHOLE CORE TRUTH GAUNTLET")
    print("------------------------------------")

    scripts = discover_scripts()
    script_results = []

    print("Discovered scripts:", len(scripts))

    for script in scripts:
        print()
        print("Running:", script)
        result = run_script(script)
        script_results.append(result)

        status = "PASS" if result["passed"] else "FAIL"
        print("-", status)

        if not result["passed"]:
            print("Bad markers:", result["bad_markers_found"])
            print("Output preview:")
            print(result["output_preview"])
            break

    report_audit = audit_reports()
    source_audit = scan_source_integrity()
    missing_versions = check_version_coverage(scripts, report_audit)

    all_scripts_passed = len(script_results) == len(scripts) and all(r["passed"] for r in script_results)

    reports_clean = (
        len(report_audit["json_load_failures"]) == 0
        and len(report_audit["pass_count_failures"]) == 0
        and len(report_audit["public_leak_findings"]) == 0
        and len(report_audit["unsafe_language_findings"]) == 0
        and len(report_audit["public_safe_flag_findings"]) == 0
    )

    source_clean = len(source_audit["source_integrity_findings"]) == 0

    enough_scripts = len(scripts) >= 10
    version_coverage_ok = len(missing_versions) == 0

    checks = [
        {
            "name": "all_discovered_run_and_audit_scripts_pass",
            "passed": all_scripts_passed,
            "details": {
                "discovered_script_count": len(scripts),
                "completed_script_count": len(script_results),
                "failed_scripts": [r for r in script_results if not r["passed"]],
            },
        },
        {
            "name": "minimum_script_coverage_exists",
            "passed": enough_scripts,
            "details": {"discovered_script_count": len(scripts), "minimum_required": 10},
        },
        {
            "name": "required_version_markers_present",
            "passed": version_coverage_ok,
            "details": {"missing_version_markers": missing_versions},
        },
        {
            "name": "all_json_reports_load",
            "passed": len(report_audit["json_load_failures"]) == 0,
            "details": {"json_load_failures": report_audit["json_load_failures"]},
        },
        {
            "name": "report_pass_counts_recompute",
            "passed": len(report_audit["pass_count_failures"]) == 0,
            "details": {"pass_count_failures": report_audit["pass_count_failures"]},
        },
        {
            "name": "public_reports_expose_no_restricted_packets_keys_or_engine_internals",
            "passed": len(report_audit["public_leak_findings"]) == 0,
            "details": {"public_leak_findings": report_audit["public_leak_findings"]},
        },
        {
            "name": "public_reports_avoid_punitive_or_certain_guilt_language",
            "passed": len(report_audit["unsafe_language_findings"]) == 0,
            "details": {"unsafe_language_findings": report_audit["unsafe_language_findings"]},
        },
        {
            "name": "public_safe_flags_are_consistent",
            "passed": len(report_audit["public_safe_flag_findings"]) == 0,
            "details": {"public_safe_flag_findings": report_audit["public_safe_flag_findings"]},
        },
        {
            "name": "source_files_do_not_obviously_force_pass_or_fixed_counts",
            "passed": source_clean,
            "details": source_audit,
        },
    ]

    passed_count = sum(1 for check in checks if check["passed"])
    total_checks = len(checks)
    all_passed = passed_count == total_checks

    result = "PASS" if all_passed else "NEEDS_WORK"

    final_report = {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": "0.50",
        "report_type": "whole_core_truth_gauntlet",
        "timestamp": datetime.now().isoformat(),
        "public_safe": True,
        "result": result,
        "passed_checks": passed_count,
        "total_checks": total_checks,
        "all_checks_passed": all_passed,
        "summary": {
            "scripts_discovered": len(scripts),
            "scripts_completed": len(script_results),
            "scripts_passed": sum(1 for r in script_results if r["passed"]),
            "json_reports_scanned": report_audit["json_report_count"],
            "markdown_reports_scanned": report_audit["markdown_report_count"],
            "source_files_scanned": source_audit["source_file_count"],
            "missing_version_markers": missing_versions,
        },
        "checks": checks,
        "script_results": script_results,
        "report_audit_summary": report_audit,
        "source_audit_summary": source_audit,
        "honest_claim": (
            "V0.50 is a whole-core internal truth gauntlet. It reruns discovered PRMR run/audit scripts, "
            "checks report consistency, scans public reports for private leakage, and scans source files for obvious forced-pass patterns. "
            "Passing this gauntlet means the current internal repo evidence is coherent and regression-clean. "
            "It does not prove external production readiness, bank certification, compliance approval, or real-client performance."
        ),
        "next_phase": (
            "If PASS: create external-style pilot sandbox and real-world dataset protocol. "
            "If NEEDS_WORK: inspect failed check details and patch honestly."
        ),
    }

    OUT_JSON.write_text(json.dumps(final_report, indent=4), encoding="utf-8")

    md = [
        "# PRMR V0.50 Whole Core Truth Gauntlet",
        "",
        "Company: Afternum Industries  ",
        "Product: PRMR Memory Core  ",
        "Version: V0.50  ",
        "",
        "## Result",
        "",
        f"**{result}**",
        "",
        f"Passed checks: **{passed_count}/{total_checks}**",
        "",
        "## Summary",
        "",
        f"- Scripts discovered: **{final_report['summary']['scripts_discovered']}**",
        f"- Scripts completed: **{final_report['summary']['scripts_completed']}**",
        f"- Scripts passed: **{final_report['summary']['scripts_passed']}**",
        f"- JSON reports scanned: **{final_report['summary']['json_reports_scanned']}**",
        f"- Markdown reports scanned: **{final_report['summary']['markdown_reports_scanned']}**",
        f"- Source files scanned: **{final_report['summary']['source_files_scanned']}**",
        f"- Missing version markers: **{final_report['summary']['missing_version_markers']}**",
        "",
        "## Honest Claim",
        "",
        final_report["honest_claim"],
        "",
        "## Checks",
        "",
    ]

    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        md.append(f"- **{status}** — {check['name']}")

    md.extend([
        "",
        "## Script Results",
        "",
    ])

    for item in script_results:
        status = "PASS" if item["passed"] else "FAIL"
        md.append(f"- **{status}** — `{item['script']}`")

    md.extend([
        "",
        "## Meaning",
        "",
        "This is not a marketing test.",
        "",
        "It is a repo-level truth gauntlet designed to catch broken scripts, stale reports, fake pass counts, leaked private terms, and obvious forced-pass patterns.",
        "",
        "## Build Mantra",
        "",
        "Test. Break. Patch. Rerun. Score. Climb.",
        "",
    ])

    OUT_MD.write_text("\n".join(md), encoding="utf-8")

    print()
    print("Passed checks:", f"{passed_count}/{total_checks}")
    print("Result:", result)
    print()
    print("Summary:")
    for key, value in final_report["summary"].items():
        print("-", key + ":", value)
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
