import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from prmr.product.alpha_api_sandbox_v0521 import (
    scan_public_forbidden_terms,
    scan_unsafe_public_language,
)


VERSION = "0.54"
BOUNDARY_WORDING = (
    "Current evidence is internal/local controlled-alpha evidence. "
    "External validation and production hardening are separate future milestones."
)

LANDING_PATH = Path("docs/landing_page_v054.md")
STRUCTURE_PATH = Path("docs/site_structure_v054.md")
INTEGRATION_PATH = Path("docs/frontend_backend_integration_notes_v054.md")

REPORT_DIR = Path("reports/v054")
REPORT_DIR.mkdir(parents=True, exist_ok=True)

PUBLIC_PATH = REPORT_DIR / "public_landing_page_pack_v054.json"
PRIVATE_PATH = REPORT_DIR / "private_internal_landing_page_pack_v054.json"
SCORECARD_PATH = REPORT_DIR / "scorecard_v054.md"


REQUIRED_SECTIONS = [
    "Hero",
    "Problem",
    "Solution",
    "API Flow",
    "Local Demo Preview",
    "Evidence, Clearly Labelled",
    "Use Cases",
    "Why Continuity Matters",
    "Controlled Alpha Access",
    "Footer",
]

REQUIRED_ROUTES = [
    "/",
    "/demo",
    "/alpha",
    "/docs",
    "/contact",
]

REQUIRED_COMPONENTS = [
    "HeroSection",
    "ProblemSection",
    "SolutionSection",
    "ApiFlowSection",
    "DemoPreview",
    "EvidenceCards",
    "UseCaseCards",
    "AlphaAccessForm",
    "BoundaryNotice",
    "Footer",
]

REQUIRED_EVIDENCE_LABELS = [
    "Whole-core truth gauntlet: PASS",
    "Alpha API contract: PASS",
    "Alpha sandbox: PASS",
    "Sandbox integrity audit: PASS",
    "Local live demo harness: PASS",
    "Demo replay pack: PASS",
    "Public/private report hygiene: PASS",
    "Key rotation/revocation checks: PASS",
    "Cross-client denial checks: PASS",
]

REQUIRED_INTEGRATION_NOTES = [
    "Next.js",
    "React",
    "TypeScript",
    "Tailwind CSS",
    "Never expose API keys in frontend",
    "Frontend should call backend proxy routes, not PRMR core directly",
    "Public demo should use synthetic/demo data only",
    "Public demo should fetch public-safe reports only",
    "Private/internal reports must never be exposed in public frontend",
    "API key validation",
    "vaults",
    "namespaces",
    "report access",
    "usage logs",
    "key rotation",
    "key revocation",
]

REQUIRED_PROXY_ROUTES = [
    "/api/demo/run",
    "/api/demo/report",
    "/api/alpha/request",
    "/api/usage",
    "/api/keys/rotate",
    "/api/keys/revoke",
]

CLAIM_PATTERNS = [
    "production ready",
    "production readiness achieved",
    "bank approved",
    "bank approval achieved",
    "compliance approved",
    "compliance approval achieved",
    "legal approved",
    "legal approval achieved",
    "external security certified",
    "external security certification achieved",
    "real-world validated",
    "hosted api is live",
    "hosted production api",
]

RESTRICTED_DOC_TERMS = [
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
    "do_not_share",
    "do_not_leak",
    "local_test",
]


def read_text(path):
    return path.read_text(encoding="utf-8")


def add_check(checks, name, passed, details=None):
    checks.append({
        "name": name,
        "passed": bool(passed),
        "details": details or {},
    })


def public_checks(checks):
    return [
        {
            "name": check["name"],
            "passed": check["passed"],
        }
        for check in checks
    ]


def missing_items(text, items):
    return [item for item in items if item not in text]


def missing_headings(text, headings):
    missing = []
    for heading in headings:
        if f"## {heading}" not in text and f"### {heading}" not in text:
            missing.append(heading)
    return missing


def exposes_frontend_keys_unsafely(text):
    unsafe_lines = []
    for line in text.splitlines():
        lower = line.lower()
        if "expose api keys" in lower and "never expose api keys" not in lower:
            unsafe_lines.append(line)
        if "frontend should expose" in lower and "api key" in lower:
            unsafe_lines.append(line)
        if "browser" in lower and "api key" in lower and "never" not in lower and "do not" not in lower:
            unsafe_lines.append(line)
    return unsafe_lines


def public_frontend_exposes_restricted_reports(text):
    unsafe_lines = []
    for line in text.splitlines():
        lower = line.lower()
        if "public frontend" in lower and "private/internal reports" in lower and "must never" not in lower:
            unsafe_lines.append(line)
        if "public frontend" in lower and "restricted report" in lower and "not" not in lower and "never" not in lower:
            unsafe_lines.append(line)
    return unsafe_lines


def find_claims(text):
    lower = text.lower()
    return [pattern for pattern in CLAIM_PATTERNS if pattern in lower]


def find_restricted_terms(text):
    lower = text.lower()
    return [term for term in RESTRICTED_DOC_TERMS if term.lower() in lower]


def build_public_report(checks):
    passed_count = sum(1 for check in checks if check["passed"])
    total_checks = len(checks)
    result = "PASS" if passed_count == total_checks else "NEEDS_WORK"

    return {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": VERSION,
        "report_type": "landing_page_pack",
        "public_safe": True,
        "timestamp": datetime.now().isoformat(),
        "result": result,
        "passed_checks": passed_count,
        "total_checks": total_checks,
        "all_checks_passed": passed_count == total_checks,
        "landing_page_sections": REQUIRED_SECTIONS,
        "routes": REQUIRED_ROUTES,
        "components": REQUIRED_COMPONENTS,
        "evidence_labels": REQUIRED_EVIDENCE_LABELS,
        "recommended_stack": ["Next.js", "React", "TypeScript", "Tailwind CSS"],
        "backend_proxy_routes": REQUIRED_PROXY_ROUTES,
        "integration_summary": [
            "Browser code calls backend proxy routes, not PRMR core directly.",
            "Credentials stay server-side.",
            "Public demo uses synthetic/demo data only.",
            "Public demo fetches public-safe reports only.",
            "Restricted reports stay out of the public frontend.",
            "Backend handles validation, vaults, namespaces, report access, usage logs, key rotation, and key revocation.",
        ],
        "boundary_wording": BOUNDARY_WORDING,
        "checks": public_checks(checks),
        "remaining_v0541_visual_design_gaps": [
            "Turn copy into wireframes with the dark research-lab infrastructure aesthetic.",
            "Define typography tokens for elegant serif headings and technical sans-serif body text.",
            "Design gold/bronze data stream accents without generic AI robot imagery.",
            "Create responsive section layouts for desktop and mobile.",
        ],
        "remaining_v0542_frontend_build_gaps": [
            "Build the Next.js route skeleton.",
            "Implement the required React components.",
            "Add backend proxy route stubs with no frontend credential exposure.",
            "Connect the public demo to synthetic fixture output only.",
        ],
    }


def build_scorecard(public_report):
    lines = [
        "# PRMR V0.54 Landing Page Pack",
        "",
        "Company: Afternum Industries  ",
        "Product: PRMR Memory Core  ",
        "Version: V0.54  ",
        "",
        "## Result",
        "",
        f"**{public_report['result']}**",
        "",
        f"Passed checks: **{public_report['passed_checks']}/{public_report['total_checks']}**",
        "",
        "## Sections",
        "",
    ]

    for section in public_report["landing_page_sections"]:
        lines.append(f"- {section}")

    lines.extend([
        "",
        "## Routes",
        "",
    ])

    for route in public_report["routes"]:
        lines.append(f"- `{route}`")

    lines.extend([
        "",
        "## Integration Summary",
        "",
    ])

    for item in public_report["integration_summary"]:
        lines.append(f"- {item}")

    lines.extend([
        "",
        "## Boundary",
        "",
        public_report["boundary_wording"],
        "",
        "## Checks",
        "",
    ])

    for check in public_report["checks"]:
        status = "PASS" if check["passed"] else "FAIL"
        lines.append(f"- {check['name']}: {status}")

    lines.extend([
        "",
        "## V0.54.1 Visual Design Gaps",
        "",
    ])

    for gap in public_report["remaining_v0541_visual_design_gaps"]:
        lines.append(f"- {gap}")

    lines.extend([
        "",
        "## V0.54.2 Frontend Build Gaps",
        "",
    ])

    for gap in public_report["remaining_v0542_frontend_build_gaps"]:
        lines.append(f"- {gap}")

    return "\n".join(lines)


def scan_public_artifacts(public_report, scorecard_text):
    target = {
        "public_report": public_report,
        "scorecard": scorecard_text,
    }
    return {
        "restricted_terms": scan_public_forbidden_terms(target),
        "unsafe_terms": scan_unsafe_public_language(target),
    }


def main():
    print("PRMR V0.54 LANDING PAGE PACK AUDIT")
    print("----------------------------------")

    landing = read_text(LANDING_PATH)
    structure = read_text(STRUCTURE_PATH)
    integration = read_text(INTEGRATION_PATH)
    combined = "\n".join([landing, structure, integration])
    checks = []

    missing_sections = missing_headings(landing, REQUIRED_SECTIONS)
    add_check(
        checks,
        "required_sections_present",
        not missing_sections,
        {"missing_sections": missing_sections},
    )

    missing_routes = missing_items(structure, [f"`{route}`" for route in REQUIRED_ROUTES])
    add_check(
        checks,
        "required_routes_present",
        not missing_routes,
        {"missing_routes": missing_routes},
    )

    missing_components = missing_items(structure, REQUIRED_COMPONENTS)
    add_check(
        checks,
        "required_components_present",
        not missing_components,
        {"missing_components": missing_components},
    )

    missing_evidence = missing_items(landing, REQUIRED_EVIDENCE_LABELS)
    add_check(
        checks,
        "safe_evidence_labels_present",
        not missing_evidence,
        {"missing_evidence": missing_evidence},
    )

    missing_integration_notes = missing_items(integration, REQUIRED_INTEGRATION_NOTES)
    add_check(
        checks,
        "frontend_backend_integration_notes_present",
        not missing_integration_notes,
        {"missing_integration_notes": missing_integration_notes},
    )

    missing_proxy_routes = missing_items(integration, [f"`{route}`" for route in REQUIRED_PROXY_ROUTES])
    add_check(
        checks,
        "backend_proxy_routes_present",
        not missing_proxy_routes,
        {"missing_proxy_routes": missing_proxy_routes},
    )

    unsafe_key_lines = exposes_frontend_keys_unsafely(integration)
    add_check(
        checks,
        "frontend_does_not_suggest_exposing_keys",
        not unsafe_key_lines,
        {"unsafe_key_lines": unsafe_key_lines},
    )

    unsafe_report_lines = public_frontend_exposes_restricted_reports(integration)
    add_check(
        checks,
        "restricted_reports_not_suggested_for_public_frontend",
        not unsafe_report_lines,
        {"unsafe_report_lines": unsafe_report_lines},
    )

    claim_hits = find_claims(combined)
    add_check(
        checks,
        "no_unqualified_production_or_certification_claims",
        not claim_hits,
        {"claim_hits": claim_hits},
    )

    unsafe_terms = scan_unsafe_public_language({"docs": combined})
    add_check(
        checks,
        "punitive_or_certain_guilt_wording_absent",
        not unsafe_terms,
        {"unsafe_terms": unsafe_terms},
    )

    restricted_terms = find_restricted_terms(combined)
    add_check(
        checks,
        "restricted_internal_packet_terms_absent",
        not restricted_terms,
        {"restricted_terms": restricted_terms},
    )

    boundary_count = combined.count(BOUNDARY_WORDING)
    add_check(
        checks,
        "boundary_wording_present_in_docs",
        boundary_count >= 3,
        {"boundary_count": boundary_count},
    )

    public_report = build_public_report(checks)
    scorecard_text = build_scorecard(public_report)
    public_scan = scan_public_artifacts(public_report, scorecard_text)
    add_check(
        checks,
        "public_report_hygiene_holds",
        not public_scan["restricted_terms"] and not public_scan["unsafe_terms"],
        public_scan,
    )

    public_report = build_public_report(checks)
    scorecard_text = build_scorecard(public_report)
    final_public_scan = scan_public_artifacts(public_report, scorecard_text)
    if final_public_scan["restricted_terms"] or final_public_scan["unsafe_terms"]:
        add_check(
            checks,
            "final_public_artifact_hygiene_holds",
            False,
            final_public_scan,
        )
        public_report = build_public_report(checks)
        scorecard_text = build_scorecard(public_report)

    passed_count = sum(1 for check in checks if check["passed"])
    total_checks = len(checks)
    result = "PASS" if passed_count == total_checks else "NEEDS_WORK"
    public_report["result"] = result
    public_report["passed_checks"] = passed_count
    public_report["total_checks"] = total_checks
    public_report["all_checks_passed"] = passed_count == total_checks
    scorecard_text = build_scorecard(public_report)

    private_report = {
        **public_report,
        "public_safe": False,
        "checks": checks,
        "audited_files": [
            str(LANDING_PATH),
            str(STRUCTURE_PATH),
            str(INTEGRATION_PATH),
        ],
        "doc_lengths": {
            "landing_page_chars": len(landing),
            "site_structure_chars": len(structure),
            "integration_notes_chars": len(integration),
        },
        "restricted_note": "Restricted report includes detailed audit results for internal validation.",
    }

    PUBLIC_PATH.write_text(json.dumps(public_report, indent=4), encoding="utf-8")
    PRIVATE_PATH.write_text(json.dumps(private_report, indent=4), encoding="utf-8")
    SCORECARD_PATH.write_text(scorecard_text, encoding="utf-8")

    print("Passed checks:", f"{passed_count}/{total_checks}")
    print("Result:", result)
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
