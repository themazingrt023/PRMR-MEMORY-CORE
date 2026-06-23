import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from prmr.product.alpha_api_sandbox_v0521 import scan_unsafe_public_language


VERSION = "0.54.9"
FRONTEND_DIR = Path("frontend")
REPORT_DIR = Path("reports/v0549")
REPORT_DIR.mkdir(parents=True, exist_ok=True)

PUBLIC_PATH = REPORT_DIR / "public_final_visual_interaction_polish_v0549.json"
PRIVATE_PATH = REPORT_DIR / "private_internal_final_visual_interaction_polish_v0549.json"
SCORECARD_PATH = REPORT_DIR / "scorecard_v0549.md"

BOUNDARY_WORDING = "Internal/local controlled-alpha evidence only. External validation and production hardening are separate future milestones."

REQUIRED_ROUTES = {
    "/": FRONTEND_DIR / "app/page.tsx",
    "/demo": FRONTEND_DIR / "app/demo/page.tsx",
    "/alpha": FRONTEND_DIR / "app/alpha/page.tsx",
    "/docs": FRONTEND_DIR / "app/docs/page.tsx",
    "/contact": FRONTEND_DIR / "app/contact/page.tsx",
    "/capabilities/[slug]": FRONTEND_DIR / "app/capabilities/[slug]/page.tsx",
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
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return subprocess.run(
        command,
        cwd=FRONTEND_DIR,
        capture_output=True,
        text=True,
        shell=True,
        env=env,
        check=False,
        encoding="utf-8",
        errors="replace",
    )


def build_public_report(checks):
    passed_count = sum(1 for check in checks if check["passed"])
    total_checks = len(checks)
    result = "PASS" if passed_count == total_checks else "NEEDS_WORK"
    return {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": VERSION,
        "report_type": "final_visual_interaction_polish",
        "public_safe": True,
        "timestamp": datetime.now().isoformat(),
        "result": result,
        "passed_checks": passed_count,
        "total_checks": total_checks,
        "all_checks_passed": passed_count == total_checks,
        "routes": list(REQUIRED_ROUTES.keys()),
        "purpose": "Final local frontend polish for navigation, interaction, capabilities, evidence reveal, and claim-safe story.",
        "changes": [
            "Header navigation now uses Kimi-style homepage section anchors and removes Docs from the main nav.",
            "Capability rows now link to dedicated capability detail pages.",
            "Evidence section uses expandable benchmark rows instead of a default full version ladder.",
            "Interactive surfaces use restrained silver/white hover response.",
            "API/product copy now starts from PRMR not replacing database, vector store, or AI model.",
        ],
        "boundary": (
            "V0.54.9 is local frontend visual/content/interaction polish only. It is not hosted, "
            "not production-ready, not bank approved, not compliance approved, not legal approval, "
            "not external security certification, and not real-world validation."
        ),
        "checks": public_checks(checks),
        "remaining_gaps": [
            "Founder visual approval still requires human browser review.",
            "Capability pages are static local explanation pages, not live product docs.",
            "Benchmark reveals use public-safe summaries and do not expose private traces.",
            "Backend/demo connection remains future work.",
            "Dependency audit still reports moderate advisories that need an upstream-compatible fix.",
        ],
    }


def build_scorecard(public_report):
    lines = [
        "# PRMR V0.54.9 Final Visual Interaction Polish",
        "",
        "Company: Afternum Industries  ",
        "Product: PRMR Memory Core  ",
        "Version: V0.54.9  ",
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
    print("PRMR V0.54.9 FINAL VISUAL INTERACTION POLISH AUDIT")
    print("--------------------------------------------------")
    checks = []
    source_text = combined_source_text()

    globals_text = read_text(FRONTEND_DIR / "app/globals.css")
    nav_text = read_text(FRONTEND_DIR / "components/landing/Navigation.tsx")
    hero_text = read_text(FRONTEND_DIR / "components/landing/HeroSection.tsx")
    logo_text = read_text(FRONTEND_DIR / "components/brand/AfternumLogo.tsx")
    api_text = read_text(FRONTEND_DIR / "components/landing/ApiFlowSection.tsx")
    problem_text = read_text(FRONTEND_DIR / "components/landing/ProblemSection.tsx")
    solution_text = read_text(FRONTEND_DIR / "components/landing/SolutionSection.tsx")
    capabilities_text = read_text(FRONTEND_DIR / "components/landing/CapabilitiesSection.tsx")
    capability_detail_text = read_text(FRONTEND_DIR / "app/capabilities/[slug]/page.tsx")
    evidence_text = read_text(FRONTEND_DIR / "components/landing/EvidenceSection.tsx")
    benchmark_text = read_text(FRONTEND_DIR / "data/benchmarkEvidence.ts")
    use_cases_text = read_text(FRONTEND_DIR / "components/landing/UseCasesSection.tsx")
    alpha_text = read_text(FRONTEND_DIR / "components/landing/AlphaAccessSection.tsx")
    footer_text = read_text(FRONTEND_DIR / "components/landing/Footer.tsx")
    demo_text = read_text(FRONTEND_DIR / "components/landing/DemoPreviewSection.tsx")

    missing_routes = [route for route, path in REQUIRED_ROUTES.items() if not path.exists()]
    add_check(checks, "all_required_routes_still_exist", not missing_routes, {"missing_routes": missing_routes})
    add_check(checks, "docs_route_still_exists", (FRONTEND_DIR / "app/docs/page.tsx").exists(), {})

    required_nav = ["Problem", "Solution", "API", "Demo", "Evidence", "Access", "Contact"]
    missing_nav = [label for label in required_nav if f'label: "{label}"' not in nav_text]
    add_check(checks, "main_header_nav_contains_required_kimi_labels", not missing_nav, {"missing_nav": missing_nav})
    add_check(checks, "main_header_nav_does_not_contain_docs", 'label: "Docs"' not in nav_text and 'href: "/docs"' not in nav_text, {})

    anchor_map = {
        "/#problem": 'id="problem"',
        "/#solution": 'id="solution"',
        "/#api": 'id="api"',
        "/#demo": 'id="demo"',
        "/#evidence": 'id="evidence"',
        "/#access": 'id="access"',
    }
    all_component_text = "\n".join(read_text(path) for path in (FRONTEND_DIR / "components/landing").glob("*.tsx"))
    missing_anchors = [href for href, section_id in anchor_map.items() if f'href: "{href}"' not in nav_text or section_id not in all_component_text]
    add_check(checks, "nav_anchors_point_to_valid_homepage_section_ids", not missing_anchors and 'href: "/contact"' in nav_text, {"missing_or_invalid": missing_anchors})

    add_check(
        checks,
        "hero_remains_present_and_uses_full_afternum_logo",
        "Infrastructure for Continuity" in hero_text and "AfternumLogo" in hero_text and 'size="heroFull"' in hero_text and 'src="/brand/afternum-logo.png"' in logo_text,
        {},
    )

    grid_markers = [
        "linear-gradient(rgba(242, 245, 247, 0.035) 1px",
        "linear-gradient(90deg, rgba(242, 245, 247, 0.035) 1px",
        "linear-gradient(rgba(242, 245, 247, 0.04) 1px",
        "linear-gradient(90deg, rgba(242, 245, 247, 0.04) 1px",
        "background-size: 64px 64px",
        "background-size: 48px 48px",
        "radial-gradient(circle at 50% -12%",
        "radial-gradient(circle at 12% 28%",
        "radial-gradient(circle at 88% 64%",
    ]
    add_check(
        checks,
        "lower_sections_no_heavy_repeated_square_tile_checker_background_globally",
        not any(marker in globals_text for marker in grid_markers) and "background-image" not in globals_text,
        {"matched_grid_markers": [marker for marker in grid_markers if marker in globals_text]},
    )
    lower_background_sources = "\n".join([
        globals_text,
        read_text(FRONTEND_DIR / "components/visual/KimiSectionShell.tsx"),
        problem_text,
        solution_text,
        api_text,
        demo_text,
        evidence_text,
        use_cases_text,
        alpha_text,
        footer_text,
    ])
    pure_black_background_hits = [
        line.strip()
        for line in lower_background_sources.splitlines()
        if any(marker in line for marker in ["bg-black", "background: #000", "background-color: #000", "background-color: black", "background: black"])
    ]
    add_check(
        checks,
        "body_main_and_lower_sections_share_afternum_charcoal_background_tokens",
        "--afternum-bg: #090909" in globals_text
        and "--afternum-bg-deep: #090909" in globals_text
        and "--afternum-bg-section: #090909" in globals_text
        and "--afternum-bg-panel: #0b0b0b" in globals_text
        and "background: var(--afternum-bg)" in globals_text
        and "main {" in globals_text
        and "bg-[var(--afternum-bg-section)]" in read_text(FRONTEND_DIR / "components/visual/KimiSectionShell.tsx")
        and all('className="bg-[var(--afternum-bg-section)]"' in text for text in [problem_text, solution_text, api_text, demo_text])
        and "bg-[var(--afternum-bg-section)]" in footer_text
        and not pure_black_background_hits,
        {"pure_black_background_hits": pure_black_background_hits[:20]},
    )
    add_check(
        checks,
        "hero_can_keep_own_atmospheric_background",
        "DataRainBackground" in hero_text and "overflow-hidden" in hero_text and "hero-shell" in hero_text and "var(--afternum-bg-section)" in globals_text,
        {},
    )
    greenish_terms = ["green", "#111111", "#1b1b1b", "rgb(17", "rgb(27"]
    greenish_background_hits = [
        line for line in lines_with_terms(source_text, greenish_terms)
        if "background" in line.lower() or "bg-" in line.lower()
    ]
    add_check(checks, "no_warm_or_greenish_background_token_used_for_lower_sections", not greenish_background_hits, {"hits": greenish_background_hits[:20]})

    add_check(
        checks,
        "interactive_elements_include_silver_hover_glow_styling",
        "silver-hover" in globals_text and "rgba(232, 238, 245" in globals_text and "text-shadow" in globals_text and all(term in source_text for term in ["silver-hover", "group-hover"]),
        {},
    )
    add_check(
        checks,
        "nav_hover_styling_remains_silver_white_not_gold",
        ".nav-link:hover" in globals_text and "rgba(232, 238, 245" in globals_text and not lines_with_terms(nav_text + globals_text, WARM_TERMS),
        {"warm_hits": lines_with_terms(nav_text + globals_text, WARM_TERMS)},
    )

    add_check(
        checks,
        "footer_uses_logo_as_primary_identity_not_giant_typed_afternum",
        "AfternumMark" in footer_text
        and "PRMR Memory Core" in footer_text
        and "Afternum Industries" not in footer_text
        and "clamp(48px,7vw,96px)" not in footer_text
        and ">AFTERNUM<" not in footer_text,
        {},
    )

    api_start = "PRMR Memory Core does not replace your database, vector store, or AI model"
    api_follow = "Applications send events into PRMR"
    add_check(checks, "api_product_explanation_uses_required_stronger_wording", api_start in api_text and api_follow in api_text, {})
    add_check(checks, "prmr_is_described_as_not_an_ai_model", "PRMR Memory Core is not an AI model" in source_text, {})

    capability_titles = ["Event Ingestion", "Continuity Packets", "State Reconstruction", "Stale Signal Handling", "Evidence Awareness", "Public-Safe Explanations", "Least-Harm Actions", "Public / Private Reports"]
    missing_capabilities = all_terms_present(read_text(FRONTEND_DIR / "data/capabilities.ts"), capability_titles)
    add_check(checks, "capabilities_section_exists_with_at_least_8_capability_items", not missing_capabilities, {"missing_terms": missing_capabilities})
    add_check(checks, "capabilities_have_hover_and_interactive_styling", "Link" in capabilities_text and "group-hover" in capabilities_text and "silver-hover" in capabilities_text, {})
    add_check(checks, "capability_detail_pages_or_detail_views_exist", "generateStaticParams" in capability_detail_text and "Back to capabilities" in capability_detail_text and "/capabilities/" in capabilities_text, {})

    add_check(
        checks,
        "evidence_section_does_not_show_full_version_ladder_as_default_primary_visible_design",
        "proofLadder" not in evidence_text and "<details" in evidence_text and "Version proof ladder" not in evidence_text,
        {},
    )
    add_check(
        checks,
        "benchmark_categories_are_expandable_or_reveal_rows",
        "<details" in evidence_text and "<summary" in evidence_text and "benchmark-row" in evidence_text and "Reveal" in evidence_text,
        {},
    )
    benchmark_terms = [
        "Reconstruction tests",
        "Compression / token-cost tests",
        "Baseline comparisons",
        "Messy memory trials",
        "Security / client isolation checks",
        "API sandbox checks",
        "Explainability checks",
        "Human-harm reduction checks",
        "Public/private report hygiene",
    ]
    missing_benchmarks = all_terms_present(benchmark_text, benchmark_terms)
    add_check(checks, "benchmark_categories_include_required_real_evidence_groups", not missing_benchmarks, {"missing_terms": missing_benchmarks})

    add_check(checks, "use_cases_retain_kimi_style_image_card_design", "Image" in use_cases_text and "group-hover:scale" in use_cases_text and "silver-hover" in use_cases_text, {})
    add_check(checks, "alpha_access_uses_form_style_section", "<form" in alpha_text and all(term in alpha_text for term in ["Name", "Email", "Organisation", "Use case", "Apply for Alpha Access"]), {})
    add_check(checks, "local_demo_section_has_silver_interactive_rows", "silver-hover" in demo_text and "wrong-key/cross-client denial" in demo_text, {})

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
        "internal_visual_note": "Audit checks structure, copy, and claim boundaries. Founder visual approval remains a human browser review decision.",
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
