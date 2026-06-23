import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from prmr.product.alpha_api_sandbox_v0521 import scan_unsafe_public_language


VERSION = "0.56"
DOCS_DIR = Path("docs")
REPORT_DIR = Path("reports/v056")
REPORT_DIR.mkdir(parents=True, exist_ok=True)

SCRIPT_PATH = DOCS_DIR / "demo_recording_script_v056.md"
CHECKLIST_PATH = DOCS_DIR / "demo_recording_checklist_v056.md"
BOUNDARIES_PATH = DOCS_DIR / "demo_claim_boundaries_v056.md"
V055_PUBLIC_PATH = Path("reports/v055/public_frontend_backend_connection_v055.json")

PUBLIC_PATH = REPORT_DIR / "public_demo_recording_pack_v056.json"
PRIVATE_PATH = REPORT_DIR / "private_internal_demo_recording_pack_v056.json"
SCORECARD_PATH = REPORT_DIR / "scorecard_v056.md"

BOUNDARY = (
    "V0.56 is a local demo recording pack only. It is not hosted, not production-ready, "
    "not bank approved, not compliance approved, not legal approval, not external security certification, "
    "and not real-world validation."
)

FORBIDDEN_CLAIMS = [
    "production-ready",
    "hosted API live",
    "bank approved",
    "compliance approved",
    "legal approval",
    "external security certification",
    "real-world validated",
    "guaranteed fraud detection",
    "final automated decisions",
]

UNSAFE_CLAIM_TERMS = [
    "hosted api live",
    "production-ready",
    "production ready",
    "bank approved",
    "compliance approved",
    "legal approval",
    "external security certification",
    "real-world validated",
    "real-world validation",
    "real world validation",
    "guaranteed fraud detection",
    "final automated decisions",
]

REQUIRED_FLOW_TERMS = [
    "localhost:3000/demo",
    "scenario selector",
    "Run Local Demo",
    "synthetic events",
    "continuity packet",
    "reconstructed state",
    "public-safe explanation",
    "least-harm action",
    "report preview",
    "denial path",
]

REQUIRED_EVIDENCE_TERMS = [
    "V0.50 whole-core truth gauntlet: PASS",
    "V0.52 local alpha API sandbox: PASS",
    "V0.52.2 sandbox integrity audit: PASS",
    "V0.53.1 replay pack: PASS",
    "V0.55 frontend-to-demo-backend connection: PASS",
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
    return [{"name": check["name"], "passed": check["passed"]} for check in checks]


def missing_terms(text, terms):
    lower = text.lower()
    return [term for term in terms if term.lower() not in lower]


def forbidden_section_text(boundary_text):
    marker = "## Forbidden Claims"
    next_marker = "\n## Safe Boundary Statement"
    if marker not in boundary_text:
        return ""
    after = boundary_text.split(marker, 1)[1]
    return after.split(next_marker, 1)[0] if next_marker in after else after


def text_without_allowed_forbidden_section(script_text, checklist_text, boundary_text):
    forbidden_section = forbidden_section_text(boundary_text)
    return "\n".join([
        script_text,
        checklist_text,
        boundary_text.replace(forbidden_section, ""),
    ])


def unqualified_forbidden_claim_lines(text):
    hits = []
    for line in text.splitlines():
        lower = line.lower()
        for term in UNSAFE_CLAIM_TERMS:
            if term not in lower:
                continue
            negated = any(marker in lower for marker in [
                "not ",
                "no ",
                "never ",
                "do not ",
                "does not ",
                "must not ",
                "avoid ",
                "forbidden",
                "future",
            ])
            if not negated:
                hits.append(line.strip())
    return sorted(set(hits))


def load_v055_status():
    if not V055_PUBLIC_PATH.exists():
        return {"exists": False, "result": "missing"}
    report = json.loads(read_text(V055_PUBLIC_PATH))
    return {
        "exists": True,
        "result": report.get("result"),
        "passed_checks": report.get("passed_checks"),
        "total_checks": report.get("total_checks"),
    }


def build_public_report(checks, v055_status):
    passed_count = sum(1 for check in checks if check["passed"])
    total_checks = len(checks)
    result = "PASS" if passed_count == total_checks else "NEEDS_WORK"
    return {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": VERSION,
        "report_type": "demo_recording_pack",
        "timestamp": datetime.now().isoformat(),
        "result": result,
        "passed_checks": passed_count,
        "total_checks": total_checks,
        "all_checks_passed": passed_count == total_checks,
        "purpose": "Create a founder-ready local demo recording pack for a professional 2-5 minute walkthrough.",
        "artifacts": [
            str(SCRIPT_PATH),
            str(CHECKLIST_PATH),
            str(BOUNDARIES_PATH),
        ],
        "safe_recording_summary": {
            "opening": "PRMR Memory Core is continuity infrastructure for AI systems and organisations.",
            "flow": "Open the local demo, select a synthetic scenario, run the local demo, then explain the public-safe output cards.",
            "evidence": "Internal/local milestone evidence is referenced as passed without external certification claims.",
            "cta": "Controlled alpha conversations with AI builders, SaaS teams, and organisations with continuity problems.",
        },
        "v055_prerequisite": v055_status,
        "npm_typecheck": "not run by design because V0.56 changes documentation and audit artifacts only",
        "npm_build": "not run by design because V0.56 changes documentation and audit artifacts only",
        "checks": public_checks(checks),
        "boundary": BOUNDARY,
        "remaining_gaps": [
            "V0.57 developer docs can turn the local API/demo architecture into clearer implementation notes.",
            "V0.58 alpha access pipeline can define intake, approval, and follow-up workflow without adding production claims.",
            "Future video production could add captions, voiceover timing, and edited cuts after founder approval.",
        ],
    }


def build_scorecard(public_report):
    lines = [
        "# PRMR V0.56 Founder Demo Recording Pack",
        "",
        "Company: Afternum Industries  ",
        "Product: PRMR Memory Core  ",
        "Version: V0.56  ",
        "",
        "## Result",
        "",
        f"**{public_report['result']}**",
        "",
        f"Passed checks: **{public_report['passed_checks']}/{public_report['total_checks']}**",
        "",
        "## Artifacts",
        "",
    ]
    for artifact in public_report["artifacts"]:
        lines.append(f"- {artifact}")
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
        "unsafe_terms": scan_unsafe_public_language({"text": public_text}),
        "unqualified_claim_lines": unqualified_forbidden_claim_lines(public_text),
    }


def main():
    checks = []

    add_check(checks, "demo_script_exists", SCRIPT_PATH.exists())
    add_check(checks, "recording_checklist_exists", CHECKLIST_PATH.exists())
    add_check(checks, "claim_boundary_doc_exists", BOUNDARIES_PATH.exists())

    script_text = read_text(SCRIPT_PATH) if SCRIPT_PATH.exists() else ""
    checklist_text = read_text(CHECKLIST_PATH) if CHECKLIST_PATH.exists() else ""
    boundary_text = read_text(BOUNDARIES_PATH) if BOUNDARIES_PATH.exists() else ""
    combined_text = "\n".join([script_text, checklist_text, boundary_text])

    add_check(
        checks,
        "script_includes_required_opening_line",
        "PRMR Memory Core is continuity infrastructure for AI systems and organisations" in script_text
        and "what changed, what matters, what became stale, and what needs review" in script_text,
    )
    add_check(
        checks,
        "script_mentions_prmr_is_not_an_ai_model",
        "PRMR Memory Core is not an AI model" in script_text,
    )
    add_check(
        checks,
        "script_mentions_synthetic_local_controlled_alpha_boundary",
        "local controlled-alpha" in script_text.lower()
        and "synthetic data" in script_text.lower()
        and "not hosted production" in script_text.lower(),
    )
    add_check(
        checks,
        "script_includes_v055_demo_flow",
        not missing_terms(script_text, REQUIRED_FLOW_TERMS),
        {"missing_terms": missing_terms(script_text, REQUIRED_FLOW_TERMS)},
    )
    add_check(
        checks,
        "script_includes_safe_evidence_summary",
        not missing_terms(script_text, REQUIRED_EVIDENCE_TERMS),
        {"missing_terms": missing_terms(script_text, REQUIRED_EVIDENCE_TERMS)},
    )
    add_check(
        checks,
        "script_includes_safe_closing_cta",
        "controlled alpha conversations with AI builders, SaaS teams, and organisations" in script_text,
    )

    checklist_required = [
        "Local frontend server is running",
        "Run Local Demo",
        "result cards",
        "No raw keys visible",
        "No private/internal report is shown",
        "recording resolution",
        "Frame rate",
    ]
    add_check(
        checks,
        "checklist_covers_recording_and_safety_requirements",
        not missing_terms(checklist_text, checklist_required),
        {"missing_terms": missing_terms(checklist_text, checklist_required)},
    )

    forbidden_section = forbidden_section_text(boundary_text)
    add_check(
        checks,
        "claim_boundary_doc_lists_allowed_and_forbidden_claims",
        "## Allowed Claims" in boundary_text
        and "## Forbidden Claims" in boundary_text
        and not missing_terms(forbidden_section, FORBIDDEN_CLAIMS),
        {"missing_forbidden_claims": missing_terms(forbidden_section, FORBIDDEN_CLAIMS)},
    )

    scanned_text = text_without_allowed_forbidden_section(script_text, checklist_text, boundary_text)
    forbidden_hits = unqualified_forbidden_claim_lines(scanned_text)
    add_check(
        checks,
        "forbidden_claims_are_absent_outside_boundary_context",
        not forbidden_hits,
        {"forbidden_hits": forbidden_hits},
    )
    unsafe_language = scan_unsafe_public_language({"text": combined_text})
    add_check(
        checks,
        "no_punitive_or_certain_guilt_wording",
        not unsafe_language,
        {"unsafe_language": unsafe_language},
    )

    v055_status = load_v055_status()
    add_check(
        checks,
        "v055_pass_is_referenced_as_prerequisite",
        v055_status["exists"] and v055_status["result"] == "PASS",
        v055_status,
    )
    add_check(
        checks,
        "frontend_build_checks_not_rerun_by_design_for_doc_only_pack",
        True,
        {
            "npm_typecheck": "not run by design because V0.56 changes documentation and audit artifacts only",
            "npm_build": "not run by design because V0.56 changes documentation and audit artifacts only",
        },
    )

    public_report = build_public_report(checks, v055_status)
    scorecard_text = build_scorecard(public_report)
    clean = public_artifacts_are_clean(public_report, scorecard_text)
    add_check(
        checks,
        "public_report_is_claim_safe",
        not clean["unsafe_terms"] and not clean["unqualified_claim_lines"],
        clean,
    )

    public_report = build_public_report(checks, v055_status)
    scorecard_text = build_scorecard(public_report)
    final_clean = public_artifacts_are_clean(public_report, scorecard_text)
    if final_clean["unsafe_terms"] or final_clean["unqualified_claim_lines"]:
        add_check(checks, "final_public_artifact_hygiene_holds", False, final_clean)
        public_report = build_public_report(checks, v055_status)
        scorecard_text = build_scorecard(public_report)

    private_report = {
        **public_report,
        "public_safe": False,
        "checks": checks,
        "document_lengths": {
            "script_chars": len(script_text),
            "checklist_chars": len(checklist_text),
            "boundary_chars": len(boundary_text),
        },
        "v055_prerequisite_report_path": str(V055_PUBLIC_PATH),
        "note": "V0.56 is a documentation and recording-prep pack. Frontend build commands were not rerun because frontend code was not changed.",
    }

    PUBLIC_PATH.write_text(json.dumps(public_report, indent=4), encoding="utf-8")
    PRIVATE_PATH.write_text(json.dumps(private_report, indent=4), encoding="utf-8")
    SCORECARD_PATH.write_text(scorecard_text, encoding="utf-8")

    print("PRMR V0.56 FOUNDER DEMO RECORDING PACK AUDIT")
    print("--------------------------------------------")
    print(f"Passed checks: {public_report['passed_checks']}/{public_report['total_checks']}")
    print("Result:", public_report["result"])
    print()
    print("V0.55 prerequisite:", v055_status.get("result"))
    print("npm run typecheck: not run by design")
    print("npm run build: not run by design")
    print()
    print("Created:")
    print(PUBLIC_PATH)
    print(PRIVATE_PATH)
    print(SCORECARD_PATH)

    if public_report["result"] != "PASS":
        sys.exit(1)


if __name__ == "__main__":
    main()
