import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from prmr.product.alpha_api_sandbox_v0521 import scan_unsafe_public_language


VERSION = "0.54.8"
FRONTEND_DIR = Path("frontend")
REPORT_DIR = Path("reports/v0548")
REPORT_DIR.mkdir(parents=True, exist_ok=True)

PUBLIC_PATH = REPORT_DIR / "public_kimi_section_fidelity_v0548.json"
PRIVATE_PATH = REPORT_DIR / "private_internal_kimi_section_fidelity_v0548.json"
SCORECARD_PATH = REPORT_DIR / "scorecard_v0548.md"

BOUNDARY_WORDING = "Internal/local controlled-alpha evidence only. External validation and production hardening are separate future milestones."

REQUIRED_ROUTES = {
    "/": FRONTEND_DIR / "app/page.tsx",
    "/demo": FRONTEND_DIR / "app/demo/page.tsx",
    "/alpha": FRONTEND_DIR / "app/alpha/page.tsx",
    "/docs": FRONTEND_DIR / "app/docs/page.tsx",
    "/contact": FRONTEND_DIR / "app/contact/page.tsx",
}

SOURCE_DIRS = [
    FRONTEND_DIR / "app",
    FRONTEND_DIR / "components",
    FRONTEND_DIR / "data",
]

WARM_TERMS = [
    "gold",
    "bronze",
    "amber",
    "rgba(215",
    "rgba(200, 170",
    "b78645",
    "d7b46a",
    "GoldDivider",
    "AmberCascades",
]

UNSAFE_CLAIM_TERMS = [
    "hosted api",
    "hosted production",
    "production-ready",
    "production ready",
    "bank approved",
    "bank approval",
    "compliance approved",
    "compliance approval",
    "legal approved",
    "legal approval",
    "external security certified",
    "external security certification",
    "security-certified",
    "certified",
    "real-world validation",
    "real world validation",
    "externally validated",
    "bank grade",
    "guaranteed fraud detection",
    "agi memory",
]

RESTRICTED_PUBLIC_TERMS = [
    "raw_api_key",
    "new_api_key",
    "private_internal",
    "private_checks",
    "private_packets",
    "private_explanations",
    "private_harm_packets",
    "internal_rule_data",
    "do_not_share",
    "do_not_leak",
    "local_test",
]


def read_text(path):
    return path.read_text(encoding="utf-8")


def add_check(checks, name, passed, details=None):
    checks.append({"name": name, "passed": bool(passed), "details": details or {}})


def public_checks(checks):
    return [{"name": check["name"], "passed": check["passed"]} for check in checks]


def source_files():
    files = []
    for directory in SOURCE_DIRS:
        files.extend(path for path in directory.rglob("*") if path.is_file() and path.suffix in {".ts", ".tsx", ".css"})
    files.extend([FRONTEND_DIR / "README.md", FRONTEND_DIR / "tailwind.config.ts", FRONTEND_DIR / "package.json"])
    return [path for path in files if path.exists()]


def combined_source_text():
    return "\n".join(read_text(path) for path in source_files())


def lines_with_terms(text, terms):
    hits = []
    for line in text.splitlines():
        lower = line.lower()
        if any(term.lower() in lower for term in terms):
            hits.append(line.strip())
    return sorted(set(hits))


def all_terms_present(text, terms):
    lower = text.lower()
    return [term for term in terms if term.lower() not in lower]


def unsafe_claim_lines(text):
    unsafe = []
    for line in text.splitlines():
        lower = line.lower()
        for term in UNSAFE_CLAIM_TERMS:
            if term not in lower:
                continue
            negated = any(marker in lower for marker in [
                "not ",
                "no ",
                "never ",
                "without ",
                "does not ",
                "do not ",
                "not a ",
                "no hosted",
                "not hosted",
                "not claimed",
                "not externally",
            ])
            if not negated:
                unsafe.append(line.strip())
    return sorted(set(unsafe))


def restricted_hits(text):
    lower = text.lower()
    return [term for term in RESTRICTED_PUBLIC_TERMS if term in lower]


def frontend_exposes_credentials(text):
    unsafe = []
    for line in text.splitlines():
        lower = line.lower()
        if "api key" not in lower and "api_key" not in lower:
            continue
        if any(marker in lower for marker in ["never expose", "must not", "do not", "does not", "no "]):
            continue
        unsafe.append(line.strip())
    return unsafe


def run_frontend_command(command):
    env = os.environ.copy()
    env["NEXT_TELEMETRY_DISABLED"] = "1"
    return subprocess.run(command, cwd=FRONTEND_DIR, capture_output=True, text=True, shell=True, env=env, check=False)


def build_public_report(checks):
    passed_count = sum(1 for check in checks if check["passed"])
    total_checks = len(checks)
    result = "PASS" if passed_count == total_checks else "NEEDS_WORK"
    return {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": VERSION,
        "report_type": "kimi_section_fidelity_product_story_correction",
        "public_safe": True,
        "timestamp": datetime.now().isoformat(),
        "result": result,
        "passed_checks": passed_count,
        "total_checks": total_checks,
        "all_checks_passed": passed_count == total_checks,
        "routes": list(REQUIRED_ROUTES.keys()),
        "purpose": "Correct lower-section visual fidelity and product story while preserving the approved hero.",
        "changes": [
            "Global tiled background removed from lower-page body styling.",
            "Problem section rewritten around real storage pain, continuity losses, and consequences.",
            "Solution and API sections rewritten as continuity infrastructure and developer flow.",
            "Evidence section rebuilt as a version proof ladder with benchmark categories.",
            "Capabilities restored with Kimi-like large serif rows and hover imagery.",
            "Use cases, demo, alpha, and footer moved toward premium black section rhythm.",
        ],
        "boundary": (
            "V0.54.8 is local frontend content/design/story correction only. It is not hosted, "
            "not production-ready, not bank approved, not compliance approved, not legal approval, "
            "not external security certification, and not real-world validation."
        ),
        "checks": public_checks(checks),
        "remaining_gaps": [
            "Founder visual approval still requires human browser review.",
            "Interactive hover fidelity should be reviewed on desktop and mobile.",
            "Backend/demo connection remains future work.",
            "Accessibility and responsive polish need a dedicated pass.",
            "Dependency audit still reports moderate advisories that need an upstream-compatible fix.",
        ],
    }


def build_scorecard(public_report):
    lines = [
        "# PRMR V0.54.8 Kimi Section Fidelity",
        "",
        "Company: Afternum Industries  ",
        "Product: PRMR Memory Core  ",
        "Version: V0.54.8  ",
        "",
        "## Result",
        "",
        f"**{public_report['result']}**",
        "",
        f"Passed checks: **{public_report['passed_checks']}/{public_report['total_checks']}**",
        "",
        "## Changes",
        "",
    ]
    for item in public_report["changes"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Boundary", "", public_report["boundary"], "", "## Checks", ""])
    for check in public_report["checks"]:
        lines.append(f"- {check['name']}: {'PASS' if check['passed'] else 'FAIL'}")
    lines.extend(["", "## Remaining Gaps", ""])
    for gap in public_report["remaining_gaps"]:
        lines.append(f"- {gap}")
    return "\n".join(lines)


def public_artifacts_are_clean(public_report, scorecard_text):
    text = json.dumps({"public_report": public_report, "scorecard": scorecard_text}, sort_keys=True)
    return {
        "restricted_terms": restricted_hits(text),
        "unsafe_terms": scan_unsafe_public_language({"text": text}),
        "unsafe_claim_lines": unsafe_claim_lines(text),
    }


def main():
    print("PRMR V0.54.8 KIMI SECTION FIDELITY AUDIT")
    print("----------------------------------------")
    checks = []
    source_text = combined_source_text()

    globals_text = read_text(FRONTEND_DIR / "app/globals.css")
    problem_text = read_text(FRONTEND_DIR / "components/landing/ProblemSection.tsx")
    solution_text = read_text(FRONTEND_DIR / "components/landing/SolutionSection.tsx")
    api_text = read_text(FRONTEND_DIR / "components/landing/ApiFlowSection.tsx")
    evidence_text = read_text(FRONTEND_DIR / "components/landing/EvidenceSection.tsx")
    capabilities_text = read_text(FRONTEND_DIR / "components/landing/CapabilitiesSection.tsx")
    use_cases_text = read_text(FRONTEND_DIR / "components/landing/UseCasesSection.tsx")
    demo_text = read_text(FRONTEND_DIR / "components/landing/DemoPreviewSection.tsx")
    alpha_text = read_text(FRONTEND_DIR / "components/landing/AlphaAccessSection.tsx")
    footer_text = read_text(FRONTEND_DIR / "components/landing/Footer.tsx")
    hero_text = read_text(FRONTEND_DIR / "components/landing/HeroSection.tsx")
    logo_text = read_text(FRONTEND_DIR / "components/brand/AfternumLogo.tsx")

    missing_routes = [route for route, path in REQUIRED_ROUTES.items() if not path.exists()]
    add_check(checks, "all_routes_still_exist", not missing_routes, {"missing_routes": missing_routes})

    add_check(
        checks,
        "hero_remains_present_and_uses_full_afternum_logo",
        "Infrastructure for Continuity" in hero_text and "AfternumLogo" in hero_text and 'size="heroFull"' in hero_text and 'src="/brand/afternum-logo.png"' in logo_text,
        {},
    )

    grid_markers = [
        "linear-gradient(rgba(242, 245, 247, 0.035) 1px",
        "linear-gradient(90deg, rgba(242, 245, 247, 0.035) 1px",
        "background-size: 64px 64px",
    ]
    add_check(
        checks,
        "heavy_square_tile_background_removed_from_most_lower_sections",
        not any(marker in globals_text for marker in grid_markers) and source_text.count("lab-grid") <= 1,
        {"lab_grid_count": source_text.count("lab-grid")},
    )

    storage_terms = ["logs", "tickets", "documents", "chat history", "vectors", "summaries", "case notes", "transactions", "user events"]
    loss_terms = ["what changed", "what stayed true", "what became stale", "what evidence matters", "what should happen next", "what should stay private", "what needs human review"]
    missing_problem_terms = all_terms_present(problem_text, storage_terms + loss_terms)
    add_check(checks, "problem_section_includes_storage_types_and_continuity_losses", not missing_problem_terms, {"missing_terms": missing_problem_terms})

    consequence_terms = ["memory bloat", "stale context", "wasted context windows/tokens", "weak reasoning", "poor handovers", "human harm"]
    missing_consequences = all_terms_present(problem_text, consequence_terms)
    add_check(checks, "problem_section_includes_required_consequences", not missing_consequences, {"missing_terms": missing_consequences})

    solution_terms = ["PRMR Memory Core is not an AI model", "continuity infrastructure layer", "Event Intake", "Continuity Packet", "State Reconstruction", "Explanation", "Least-Harm Action", "Public / Private Reports"]
    missing_solution = all_terms_present(solution_text, solution_terms)
    add_check(checks, "solution_section_explains_prmr_as_continuity_infrastructure_and_pipeline", not missing_solution, {"missing_terms": missing_solution})

    api_terms = ["Your app sends events to PRMR Memory Core", "does not replace your database", "vector store", "sits beside", "/v1/events/ingest", "/v1/continuity/packet", "/v1/reports/{report_id}"]
    missing_api_terms = all_terms_present(api_text, api_terms)
    add_check(checks, "api_flow_includes_plain_english_developer_explanation_not_only_endpoints", not missing_api_terms, {"missing_terms": missing_api_terms})

    proof_terms = ["V0.50", "Whole Core Truth Gauntlet", "V0.51", "Product Clarity Pack", "V0.52.0", "Alpha API Contract", "V0.53.1", "Demo Replay Pack", "V0.54.6", "Kimi Design Base Transplant", "V0.54.7"]
    benchmark_terms = ["reconstruction tests", "compression/token-cost tests", "baseline comparisons", "messy memory trials", "security/client isolation checks", "API sandbox checks", "fraud/risk continuity simulations", "explainability checks", "human-harm reduction checks", "public/private report hygiene"]
    missing_evidence = all_terms_present(evidence_text, proof_terms + benchmark_terms)
    add_check(checks, "evidence_section_includes_full_version_proof_ladder_and_benchmark_categories", not missing_evidence, {"missing_terms": missing_evidence})

    capability_titles = ["Event Ingestion", "Continuity Packets", "State Reconstruction", "Stale Signal Handling", "Evidence Awareness", "Public-Safe Explanations", "Least-Harm Actions", "Public / Private Reports"]
    missing_capabilities = all_terms_present(capabilities_text, capability_titles)
    add_check(checks, "capabilities_section_exists_with_at_least_8_capability_items", not missing_capabilities and capabilities_text.count("[") >= 8, {"missing_terms": missing_capabilities})

    add_check(
        checks,
        "capabilities_use_kimi_large_serif_hover_image_rhythm",
        "group-hover:opacity-100" in capabilities_text and "clamp(42px,5.5vw,86px)" in capabilities_text and "gap-24" in capabilities_text,
        {},
    )
    add_check(checks, "use_cases_section_uses_kimi_style_image_hover_cards_or_equivalent", "group-hover:scale" in use_cases_text and "grayscale" in use_cases_text and "border-l border-t" in use_cases_text, {})

    demo_terms = ["synthetic events", "continuity packet", "reconstructed state", "public-safe explanation", "least-harm action", "owner report", "wrong-key/cross-client denial"]
    missing_demo = all_terms_present(demo_text, demo_terms)
    add_check(checks, "local_demo_section_shows_required_replay_flow", not missing_demo, {"missing_terms": missing_demo})

    add_check(checks, "alpha_access_form_style_section_exists", "<form" in alpha_text and all(term in alpha_text for term in ["Name", "Email", "Organisation", "Use case", "Apply for Alpha Access"]), {})
    add_check(checks, "footer_does_not_use_giant_typed_afternum_as_main_identity", "clamp(48px,7vw,96px)" not in footer_text and ">AFTERNUM<" not in footer_text and "Afternum Industries" in footer_text, {})

    warm_hits = lines_with_terms(source_text, WARM_TERMS)
    add_check(checks, "visual_theme_remains_silver_white_black_not_gold_bronze_amber", not warm_hits, {"warm_hits": warm_hits[:20]})

    add_check(checks, "frontend_uses_synthetic_demo_data_only", "Synthetic/demo data only" in source_text and "demoScenarios" in source_text and "fetch(" not in source_text, {})
    add_check(checks, "frontend_does_not_expose_api_keys", not frontend_exposes_credentials(source_text), {"unsafe_lines": frontend_exposes_credentials(source_text)})
    add_check(checks, "boundary_wording_is_present", BOUNDARY_WORDING in source_text, {})
    add_check(checks, "no_hosted_or_production_claims", not unsafe_claim_lines(source_text), {"unsafe_claim_lines": unsafe_claim_lines(source_text)})

    approval_terms = ["bank approved", "bank approval", "compliance approved", "compliance approval", "legal approval", "legal approved", "external security certification", "external security certified", "certified"]
    approval_claim_lines = unsafe_claim_lines("\n".join(lines_with_terms(source_text, approval_terms)))
    add_check(checks, "no_bank_compliance_legal_security_or_external_certification_claims", not approval_claim_lines, {"approval_claim_lines": approval_claim_lines})
    add_check(checks, "no_punitive_or_certain_guilt_wording", not scan_unsafe_public_language({"frontend": source_text}), {"unsafe_terms": scan_unsafe_public_language({"frontend": source_text})})
    add_check(checks, "no_restricted_public_terms", not restricted_hits(source_text), {"restricted_terms": restricted_hits(source_text)})

    typecheck = run_frontend_command("npm run typecheck")
    add_check(checks, "npm_typecheck_passes", typecheck.returncode == 0, {"returncode": typecheck.returncode, "stdout_tail": typecheck.stdout.splitlines()[-12:], "stderr_tail": typecheck.stderr.splitlines()[-12:]})

    build = run_frontend_command("npm run build")
    add_check(checks, "npm_build_passes", build.returncode == 0, {"returncode": build.returncode, "stdout_tail": build.stdout.splitlines()[-16:], "stderr_tail": build.stderr.splitlines()[-16:]})

    public_report = build_public_report(checks)
    scorecard_text = build_scorecard(public_report)
    public_scan = public_artifacts_are_clean(public_report, scorecard_text)
    add_check(checks, "public_report_and_scorecard_are_claim_safe", not public_scan["restricted_terms"] and not public_scan["unsafe_terms"] and not public_scan["unsafe_claim_lines"], public_scan)

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
        "source_files_checked": [str(path) for path in source_files()],
        "command_outputs": {
            "typecheck": {"returncode": typecheck.returncode, "stdout": typecheck.stdout, "stderr": typecheck.stderr},
            "build": {"returncode": build.returncode, "stdout": build.stdout, "stderr": build.stderr},
        },
        "internal_visual_note": "Audit checks structure and copy. Founder visual approval remains a human review decision.",
    }

    PUBLIC_PATH.write_text(json.dumps(public_report, indent=4), encoding="utf-8")
    PRIVATE_PATH.write_text(json.dumps(private_report, indent=4), encoding="utf-8")
    SCORECARD_PATH.write_text(scorecard_text, encoding="utf-8")

    print("Passed checks:", f"{passed_count}/{total_checks}")
    print("Result:", result)
    print()
    print("Check list:")
    for check in checks:
        print("-", check["name"] + ":", "PASS" if check["passed"] else "FAIL")
    print()
    print("Created:")
    print(PUBLIC_PATH)
    print(PRIVATE_PATH)
    print(SCORECARD_PATH)

    if result != "PASS":
        sys.exit(1)


if __name__ == "__main__":
    main()
