import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from prmr.product.alpha_api_sandbox_v0521 import scan_unsafe_public_language


VERSION = "0.54.6"
FRONTEND_DIR = Path("frontend")
KIMI_DIR = Path("design_sources/kimi_prmr_site/app")
REPORT_DIR = Path("reports/v0546")
REPORT_DIR.mkdir(parents=True, exist_ok=True)

PUBLIC_PATH = REPORT_DIR / "public_kimi_base_transplant_v0546.json"
PRIVATE_PATH = REPORT_DIR / "private_internal_kimi_base_transplant_v0546.json"
SCORECARD_PATH = REPORT_DIR / "scorecard_v0546.md"

BOUNDARY_WORDING = "Internal/local controlled-alpha evidence only. External validation and production hardening are separate future milestones."
CORE_LINE = "Continuity infrastructure for AI systems and organisations."
SUPPORT_LINE = "PRMR Memory Core turns messy event histories into smaller, safer continuity packets that preserve what changed, what matters, what became stale, and what needs review."
CORE_CONCEPT = "Storage remembers data. PRMR remembers change."

REQUIRED_ROUTES = {
    "/": FRONTEND_DIR / "app/page.tsx",
    "/demo": FRONTEND_DIR / "app/demo/page.tsx",
    "/alpha": FRONTEND_DIR / "app/alpha/page.tsx",
    "/docs": FRONTEND_DIR / "app/docs/page.tsx",
    "/contact": FRONTEND_DIR / "app/contact/page.tsx",
}

KIMI_FILES = [
    KIMI_DIR / "src/App.tsx",
    KIMI_DIR / "src/config.ts",
    KIMI_DIR / "src/index.css",
    KIMI_DIR / "src/main.tsx",
    KIMI_DIR / "src/sections/Hero.tsx",
    KIMI_DIR / "src/sections/Navigation.tsx",
    KIMI_DIR / "src/sections/Footer.tsx",
    KIMI_DIR / "src/sections/AlphaAccessSection.tsx",
    KIMI_DIR / "src/sections/ApiFlowSection.tsx",
    KIMI_DIR / "src/sections/DemoPreview.tsx",
    KIMI_DIR / "src/sections/EvidenceSection.tsx",
    KIMI_DIR / "src/sections/ProblemSection.tsx",
    KIMI_DIR / "src/sections/SolutionSection.tsx",
    KIMI_DIR / "src/sections/AmberCascades.tsx",
    KIMI_DIR / "src/components/LiquidGlassButton.tsx",
    KIMI_DIR / "tailwind.config.js",
]

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
    files.extend([
        FRONTEND_DIR / "README.md",
        FRONTEND_DIR / "tailwind.config.ts",
        FRONTEND_DIR / "package.json",
    ])
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
    return subprocess.run(
        command,
        cwd=FRONTEND_DIR,
        capture_output=True,
        text=True,
        shell=True,
        env=env,
        check=False,
    )


def build_public_report(checks):
    passed_count = sum(1 for check in checks if check["passed"])
    total_checks = len(checks)
    result = "PASS" if passed_count == total_checks else "NEEDS_WORK"
    return {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": VERSION,
        "report_type": "kimi_design_base_transplant_prmr_function_merge",
        "public_safe": True,
        "timestamp": datetime.now().isoformat(),
        "result": result,
        "passed_checks": passed_count,
        "total_checks": total_checks,
        "all_checks_passed": passed_count == total_checks,
        "kimi_source": "design_sources/kimi_prmr_site/app/",
        "canonical_frontend": "frontend/",
        "mark_only_logo_created": (FRONTEND_DIR / "public/brand/afternum-mark.png").exists(),
        "routes": list(REQUIRED_ROUTES.keys()),
        "visual_transplant_summary": [
            "Kimi full-screen hero structure was ported into the Next.js shell.",
            "The hero now uses a large Afternum mark-only asset instead of a wordmark-heavy logo composition.",
            "Kimi sparse navigation, section label/divider rhythm, local demo preview panel, cinematic architecture band, image grid, and large footer rhythm were merged with PRMR copy and mock data.",
            "The theme remains silver, white, black, cool grey, and faint blue-white glow.",
        ],
        "boundary": (
            "V0.54.6 is local frontend visual transplant/design correction evidence only. It is not hosted, "
            "not production-ready, not bank approved, not compliance approved, not legal approval, "
            "not external security certification, and not real-world validation."
        ),
        "checks": public_checks(checks),
        "remaining_gaps": [
            "Founder visual approval still requires human review in browser.",
            "Backend/demo connection remains future work.",
            "Accessibility and responsive polish need a dedicated pass.",
            "Dependency audit still reports moderate advisories that need an upstream-compatible fix.",
        ],
    }


def build_scorecard(public_report):
    lines = [
        "# PRMR V0.54.6 Kimi Design Base Transplant + PRMR Function Merge",
        "",
        "Company: Afternum Industries  ",
        "Product: PRMR Memory Core  ",
        "Version: V0.54.6  ",
        "",
        "## Result",
        "",
        f"**{public_report['result']}**",
        "",
        f"Passed checks: **{public_report['passed_checks']}/{public_report['total_checks']}**",
        "",
        "## Visual Transplant",
        "",
    ]
    for item in public_report["visual_transplant_summary"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Routes", ""])
    for route in public_report["routes"]:
        lines.append(f"- `{route}`")
    lines.extend(["", "## Boundary", "", public_report["boundary"], "", "## Checks", ""])
    for check in public_report["checks"]:
        status = "PASS" if check["passed"] else "FAIL"
        lines.append(f"- {check['name']}: {status}")
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
    print("PRMR V0.54.6 KIMI BASE TRANSPLANT AUDIT")
    print("---------------------------------------")
    checks = []
    source_text = combined_source_text()

    add_check(checks, "kimi_source_folder_exists", KIMI_DIR.exists(), {"path": str(KIMI_DIR)})
    missing_kimi_files = [str(path) for path in KIMI_FILES if not path.exists()]
    add_check(checks, "kimi_source_files_were_inspected", not missing_kimi_files, {"missing_kimi_files": missing_kimi_files})
    add_check(checks, "canonical_frontend_still_exists", FRONTEND_DIR.exists() and (FRONTEND_DIR / "app").exists(), {})

    missing_routes = [route for route, path in REQUIRED_ROUTES.items() if not path.exists()]
    add_check(checks, "all_required_routes_still_exist", not missing_routes, {"missing_routes": missing_routes})

    navigation_text = read_text(FRONTEND_DIR / "components/landing/Navigation.tsx")
    hero_text = read_text(FRONTEND_DIR / "components/landing/HeroSection.tsx")
    footer_text = read_text(FRONTEND_DIR / "components/landing/Footer.tsx")
    alpha_text = read_text(FRONTEND_DIR / "components/landing/AlphaAccessSection.tsx")

    add_check(checks, "afternum_logo_or_mark_appears_in_nav", "AfternumMark" in navigation_text and "AFTERNUM" in navigation_text, {})
    add_check(
        checks,
        "large_mark_only_logo_appears_in_hero",
        "AfternumMark" in hero_text and 'size="hero"' in hero_text and (FRONTEND_DIR / "public/brand/afternum-mark.png").exists(),
        {"mark_path": str(FRONTEND_DIR / "public/brand/afternum-mark.png")},
    )
    add_check(
        checks,
        "hero_avoids_cluttered_wordmark_under_logo",
        "AfternumLogo" not in hero_text and "Afternum Industries" not in hero_text and "AFTERNUM" not in hero_text,
        {},
    )
    add_check(checks, "footer_includes_afternum_identity", "AFTERNUM" in footer_text and "AfternumLogo" in footer_text, {})
    add_check(checks, "alpha_section_includes_afternum_identity", "AfternumLogo" in alpha_text or "Afternum" in alpha_text, {})

    add_check(checks, "required_core_line_present", CORE_LINE in source_text, {})
    add_check(checks, "required_support_line_present", SUPPORT_LINE in source_text, {})
    add_check(checks, "required_core_concept_present", CORE_CONCEPT in source_text, {})
    add_check(checks, "boundary_wording_present", BOUNDARY_WORDING in source_text, {})

    required_visual_structures = [
        "DataRainBackground",
        "LiquidGlassButton",
        "KimiSectionShell",
        "DemoPreviewSection",
        "CinematicVisionSection",
        "cinematic-vision.mp4",
        "usecase-agent.jpg",
    ]
    missing_visual_structures = [term for term in required_visual_structures if term not in source_text]
    if not (FRONTEND_DIR / "public/videos/cinematic-vision.mp4").exists():
        missing_visual_structures.append("frontend/public/videos/cinematic-vision.mp4")
    add_check(checks, "kimi_visual_structures_were_ported", not missing_visual_structures, {"missing": missing_visual_structures})

    warm_hits = lines_with_terms(source_text, WARM_TERMS)
    add_check(checks, "visual_theme_is_silver_white_black_not_warm", not warm_hits, {"warm_hits": warm_hits[:20]})

    add_check(checks, "no_hosted_or_production_claims", not unsafe_claim_lines(source_text), {"unsafe_claim_lines": unsafe_claim_lines(source_text)})

    approval_terms = [
        "bank approved",
        "bank approval",
        "compliance approved",
        "compliance approval",
        "legal approval",
        "legal approved",
        "external security certification",
        "external security certified",
        "certified",
    ]
    approval_claim_lines = unsafe_claim_lines("\n".join(lines_with_terms(source_text, approval_terms)))
    add_check(checks, "no_bank_compliance_legal_security_approval_claims", not approval_claim_lines, {"approval_claim_lines": approval_claim_lines})

    unsafe_terms = scan_unsafe_public_language({"frontend": source_text})
    add_check(checks, "no_punitive_or_certain_guilt_wording", not unsafe_terms, {"unsafe_terms": unsafe_terms})

    restricted_terms = restricted_hits(source_text)
    add_check(checks, "no_restricted_public_terms", not restricted_terms, {"restricted_terms": restricted_terms})
    add_check(checks, "frontend_does_not_expose_api_keys", not frontend_exposes_credentials(source_text), {"unsafe_lines": frontend_exposes_credentials(source_text)})
    add_check(checks, "frontend_still_uses_synthetic_demo_data_only", "Synthetic/demo data only" in source_text and "demoScenarios" in source_text and "fetch(" not in source_text, {})

    typecheck = run_frontend_command("npm run typecheck")
    add_check(checks, "npm_typecheck_passes", typecheck.returncode == 0, {"returncode": typecheck.returncode, "stdout_tail": typecheck.stdout.splitlines()[-12:], "stderr_tail": typecheck.stderr.splitlines()[-12:]})

    build = run_frontend_command("npm run build")
    add_check(checks, "npm_build_passes", build.returncode == 0, {"returncode": build.returncode, "stdout_tail": build.stdout.splitlines()[-16:], "stderr_tail": build.stderr.splitlines()[-16:]})

    public_report = build_public_report(checks)
    scorecard_text = build_scorecard(public_report)
    public_scan = public_artifacts_are_clean(public_report, scorecard_text)
    add_check(
        checks,
        "public_report_and_scorecard_are_claim_safe",
        not public_scan["restricted_terms"] and not public_scan["unsafe_terms"] and not public_scan["unsafe_claim_lines"],
        public_scan,
    )

    public_report = build_public_report(checks)
    scorecard_text = build_scorecard(public_report)
    final_scan = public_artifacts_are_clean(public_report, scorecard_text)
    if final_scan["restricted_terms"] or final_scan["unsafe_terms"] or final_scan["unsafe_claim_lines"]:
        add_check(checks, "final_public_artifact_hygiene_holds", False, final_scan)
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
        "kimi_files_checked": [str(path) for path in KIMI_FILES],
        "source_files_checked": [str(path) for path in source_files()],
        "command_outputs": {
            "typecheck": {"returncode": typecheck.returncode, "stdout": typecheck.stdout, "stderr": typecheck.stderr},
            "build": {"returncode": build.returncode, "stdout": build.stdout, "stderr": build.stderr},
        },
        "restricted_note": "Detailed report includes source inspection paths and command outputs for internal validation.",
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
