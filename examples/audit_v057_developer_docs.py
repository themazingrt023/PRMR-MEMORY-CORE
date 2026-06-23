import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from prmr.product.alpha_api_sandbox_v0521 import scan_unsafe_public_language


VERSION = "0.57"
ROOT = Path(".")
FRONTEND_DIR = ROOT / "frontend"
REPORT_DIR = ROOT / "reports/v057"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

DEVELOPER_DOCS = ROOT / "docs/developer_docs_v057.md"
API_EXAMPLES = ROOT / "docs/api_examples_v057.md"
INTEGRATION_GUIDE = ROOT / "docs/integration_guide_v057.md"
DOCS_PAGE = FRONTEND_DIR / "app/docs/page.tsx"
API_DATA = FRONTEND_DIR / "data/apiDocs.ts"

PUBLIC_PATH = REPORT_DIR / "public_developer_docs_v057.json"
PRIVATE_PATH = REPORT_DIR / "private_internal_developer_docs_v057.json"
SCORECARD_PATH = REPORT_DIR / "scorecard_v057.md"

REQUIRED_ENDPOINTS = [
    "POST /v1/events/ingest",
    "POST /v1/continuity/packet",
    "POST /v1/memory/reconstruct",
    "POST /v1/explain",
    "POST /v1/actions/least-harm",
    "GET /v1/reports/{report_id}",
    "GET /v1/usage",
    "POST /v1/keys/rotate",
    "POST /v1/keys/revoke",
]

CORE_ENDPOINTS = [
    "/v1/events/ingest",
    "/v1/continuity/packet",
    "/v1/memory/reconstruct",
    "/v1/explain",
    "/v1/actions/least-harm",
    "/v1/reports/{report_id}",
]

FORBIDDEN_CLAIM_TERMS = [
    "hosted api",
    "hosted production",
    "production-ready",
    "production ready",
    "bank approved",
    "bank approval",
    "compliance approved",
    "compliance approval",
    "legal approval",
    "external security certification",
    "external certification",
    "real-world validation",
    "real world validation",
    "real-world validated",
    "externally validated",
]

RESTRICTED_PUBLIC_TERMS = [
    "raw_api_key",
    "new_api_key",
    "private_internal",
    "private_packets",
    "private packet",
    "private packets",
    "internal packet",
    "internal packets",
    "private_harm_packets",
    "internal_rule_data",
    "do_not_share",
    "do_not_leak",
]

BOUNDARY = (
    "V0.57 is developer documentation and docs-page upgrade only. It is not hosted, not production-ready, "
    "not bank approved, not compliance approved, not legal approval, not external security certification, "
    "and not real-world validation."
)


def read_text(path):
    return path.read_text(encoding="utf-8")


def add_check(checks, name, passed, details=None):
    checks.append({"name": name, "passed": bool(passed), "details": details or {}})


def run_command(command, cwd):
    env = os.environ.copy()
    env["NEXT_TELEMETRY_DISABLED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        shell=True,
        env=env,
        check=False,
        encoding="utf-8",
        errors="replace",
    )


def public_checks(checks):
    return [{"name": check["name"], "passed": check["passed"]} for check in checks]


def missing_terms(text, terms):
    lower = text.lower()
    return [term for term in terms if term.lower() not in lower]


def unqualified_claim_lines(text):
    hits = []
    for line in text.splitlines():
        lower = line.lower()
        for term in FORBIDDEN_CLAIM_TERMS:
            if term not in lower:
                continue
            negated = any(marker in lower for marker in [
                "not ",
                "no ",
                "never ",
                "do not ",
                "does not ",
                "future",
                "not current",
                "not a hosted",
                "not external",
            ])
            if not negated:
                hits.append(line.strip())
    return sorted(set(hits))


def restricted_hits(text):
    lower = text.lower()
    return [term for term in RESTRICTED_PUBLIC_TERMS if term in lower]


def frontend_source_text():
    paths = [
        FRONTEND_DIR / "app/docs/page.tsx",
        FRONTEND_DIR / "components/docs",
        FRONTEND_DIR / "data/apiDocs.ts",
    ]
    files = []
    for path in paths:
        if path.is_file():
            files.append(path)
        elif path.exists():
            files.extend(item for item in path.rglob("*") if item.suffix in {".ts", ".tsx"})
    return "\n".join(read_text(path) for path in files)


def build_public_report(checks, command_results):
    passed_count = sum(1 for check in checks if check["passed"])
    total_checks = len(checks)
    result = "PASS" if passed_count == total_checks else "NEEDS_WORK"
    return {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": VERSION,
        "report_type": "developer_docs",
        "timestamp": datetime.now().isoformat(),
        "result": result,
        "passed_checks": passed_count,
        "total_checks": total_checks,
        "all_checks_passed": passed_count == total_checks,
        "purpose": "Developer-facing documentation and frontend docs-page upgrade for early builders.",
        "created_or_updated": [
            str(DEVELOPER_DOCS),
            str(API_EXAMPLES),
            str(INTEGRATION_GUIDE),
            str(DOCS_PAGE),
            str(API_DATA),
        ],
        "endpoint_summary": REQUIRED_ENDPOINTS,
        "sample_json_summary": [
            "event ingest",
            "continuity packet",
            "reconstructed state",
            "public-safe explanation",
            "least-harm action",
            "public report preview",
        ],
        "command_summary": {
            name: "PASS" if data["returncode"] == 0 else "NEEDS_WORK"
            for name, data in command_results.items()
        },
        "checks": public_checks(checks),
        "boundary": BOUNDARY,
        "remaining_gaps": [
            "V0.58 Alpha Access Pipeline should define controlled intake and follow-up without production claims.",
            "Hosted API, credential issuing, billing, rate limits, dashboard, and external review remain future work.",
            "Developer SDKs and generated OpenAPI artifacts are not built yet.",
        ],
    }


def build_scorecard(public_report):
    lines = [
        "# PRMR V0.57 Developer Docs / API Docs Upgrade",
        "",
        "Company: Afternum Industries  ",
        "Product: PRMR Memory Core  ",
        "Version: V0.57  ",
        "",
        "## Result",
        "",
        f"**{public_report['result']}**",
        "",
        f"Passed checks: **{public_report['passed_checks']}/{public_report['total_checks']}**",
        "",
        "## Endpoint Summary",
        "",
    ]
    for endpoint in public_report["endpoint_summary"]:
        lines.append(f"- {endpoint}")
    lines.extend(["", "## Checks", ""])
    for check in public_report["checks"]:
        lines.append(f"- {check['name']}: {'PASS' if check['passed'] else 'FAIL'}")
    lines.extend(["", "## Boundary", "", public_report["boundary"], "", "## Remaining Gaps", ""])
    for gap in public_report["remaining_gaps"]:
        lines.append(f"- {gap}")
    return "\n".join(lines)


def public_artifacts_are_clean(public_report, scorecard_text):
    public_text = json.dumps({"public_report": public_report, "scorecard": scorecard_text}, sort_keys=True)
    return {
        "unsafe_language": scan_unsafe_public_language({"text": public_text}),
        "restricted_terms": restricted_hits(public_text),
        "unqualified_claim_lines": unqualified_claim_lines(public_text),
    }


def main():
    checks = []

    add_check(checks, "developer_docs_file_exists", DEVELOPER_DOCS.exists())
    add_check(checks, "api_examples_file_exists", API_EXAMPLES.exists())
    add_check(checks, "integration_guide_exists", INTEGRATION_GUIDE.exists())
    add_check(checks, "frontend_docs_page_updated", DOCS_PAGE.exists() and "DeveloperDocsSections" in read_text(DOCS_PAGE))

    docs_text = "\n".join(read_text(path) for path in [DEVELOPER_DOCS, API_EXAMPLES, INTEGRATION_GUIDE] if path.exists())
    frontend_text = frontend_source_text()
    combined_text = docs_text + "\n" + frontend_text

    missing_endpoints = missing_terms(combined_text, REQUIRED_ENDPOINTS)
    add_check(checks, "all_required_endpoints_documented", not missing_endpoints, {"missing_endpoints": missing_endpoints})

    missing_core_samples = [
        endpoint for endpoint in CORE_ENDPOINTS
        if endpoint.lower() not in combined_text.lower()
        or "Request:" not in docs_text
        or "Response:" not in docs_text
    ]
    add_check(checks, "sample_request_and_response_exists_for_core_endpoints", not missing_core_samples, {"missing_core_samples": missing_core_samples})

    add_check(
        checks,
        "prmr_is_described_as_not_an_ai_model",
        "PRMR Memory Core is not an AI model" in combined_text,
    )
    add_check(
        checks,
        "local_demo_architecture_is_documented",
        all(term.lower() in combined_text.lower() for term in [
            "Browser /demo",
            "Next.js server-side proxy",
            "local Python PRMR bridge",
            "V0.52.1 sandbox / V0.53.1 synthetic fixtures",
            "public-safe JSON",
            "frontend cards",
        ]),
    )
    add_check(
        checks,
        "safety_boundaries_are_present",
        all(term.lower() in combined_text.lower() for term in [
            "Synthetic/demo data only",
            "No real sensitive data unless explicitly approved",
            "No final punitive decisions",
            "Browser never receives raw credentials",
            "External validation and production hardening are future milestones",
        ]),
    )
    add_check(
        checks,
        "future_hosted_api_features_are_marked_future_not_current",
        "Future hosted API work" in docs_text
        and "future milestones, not current" in docs_text.lower()
        and all(term in docs_text for term in ["hosted backend", "client accounts", "rate limits", "billing", "external security review"]),
    )

    claim_hits = unqualified_claim_lines(combined_text)
    add_check(checks, "no_hosted_or_production_claims", not claim_hits, {"claim_hits": claim_hits[:20]})

    unsafe_language = scan_unsafe_public_language({"text": combined_text})
    add_check(checks, "no_punitive_or_certain_guilt_wording", not unsafe_language, {"unsafe_language": unsafe_language})

    restricted = restricted_hits(combined_text)
    add_check(checks, "no_restricted_packet_terms_in_public_docs", not restricted, {"restricted_hits": restricted})

    secret_hits = [
        term for term in ["ALPHA_SANDBOX_KEYS", "prmr_v0521_alpha_seed_key", "prmr_v0521_beta_seed_key", "raw_api_key", "new_api_key"]
        if term in frontend_text
    ]
    add_check(checks, "frontend_does_not_expose_api_keys", not secret_hits, {"secret_hits": secret_hits})

    add_check(
        checks,
        "docs_page_has_developer_layout_sidebar_endpoint_cards_code_blocks_copy_buttons_and_links",
        all(term in frontend_text for term in ["sticky top-28", "EndpointList", "CopyableCode", "Open Local Demo", "Request Alpha Access", "Sample request", "Sample response"]),
    )

    command_results = {}
    for name, command in {
        "frontend_typecheck": "npm run typecheck",
        "frontend_build": "npm run build",
    }.items():
        completed = run_command(command, FRONTEND_DIR)
        command_results[name] = {
            "command": command,
            "returncode": completed.returncode,
            "stdout_tail": completed.stdout.splitlines()[-40:],
            "stderr_tail": completed.stderr.splitlines()[-40:],
        }
        add_check(checks, f"{name}_passes", completed.returncode == 0, command_results[name])

    public_report = build_public_report(checks, command_results)
    scorecard_text = build_scorecard(public_report)
    clean = public_artifacts_are_clean(public_report, scorecard_text)
    add_check(
        checks,
        "public_report_and_scorecard_are_claim_safe",
        not clean["unsafe_language"] and not clean["restricted_terms"] and not clean["unqualified_claim_lines"],
        clean,
    )

    public_report = build_public_report(checks, command_results)
    scorecard_text = build_scorecard(public_report)
    final_clean = public_artifacts_are_clean(public_report, scorecard_text)
    if final_clean["unsafe_language"] or final_clean["restricted_terms"] or final_clean["unqualified_claim_lines"]:
        add_check(checks, "final_public_artifact_hygiene_holds", False, final_clean)
        public_report = build_public_report(checks, command_results)
        scorecard_text = build_scorecard(public_report)

    private_report = {
        **public_report,
        "public_safe": False,
        "checks": checks,
        "command_results": command_results,
        "document_lengths": {
            "developer_docs_chars": len(read_text(DEVELOPER_DOCS)) if DEVELOPER_DOCS.exists() else 0,
            "api_examples_chars": len(read_text(API_EXAMPLES)) if API_EXAMPLES.exists() else 0,
            "integration_guide_chars": len(read_text(INTEGRATION_GUIDE)) if INTEGRATION_GUIDE.exists() else 0,
        },
    }

    PUBLIC_PATH.write_text(json.dumps(public_report, indent=4), encoding="utf-8")
    PRIVATE_PATH.write_text(json.dumps(private_report, indent=4), encoding="utf-8")
    SCORECARD_PATH.write_text(scorecard_text, encoding="utf-8")

    print("PRMR V0.57 DEVELOPER DOCS AUDIT")
    print("--------------------------------")
    print(f"Passed checks: {public_report['passed_checks']}/{public_report['total_checks']}")
    print("Result:", public_report["result"])
    print()
    print("Command summary:")
    for name, data in command_results.items():
        print(f"- {name}: {'PASS' if data['returncode'] == 0 else 'NEEDS_WORK'}")
    print()
    print("Created:")
    print(PUBLIC_PATH)
    print(PRIVATE_PATH)
    print(SCORECARD_PATH)

    if public_report["result"] != "PASS":
        sys.exit(1)


if __name__ == "__main__":
    main()
