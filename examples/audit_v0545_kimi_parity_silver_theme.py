import json
import os
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from prmr.product.alpha_api_sandbox_v0521 import scan_unsafe_public_language


VERSION = "0.54.5"
FRONTEND_DIR = Path("frontend")
REPORT_DIR = Path("reports/v0545")
REPORT_DIR.mkdir(parents=True, exist_ok=True)

PUBLIC_PATH = REPORT_DIR / "public_kimi_parity_silver_theme_v0545.json"
PRIVATE_PATH = REPORT_DIR / "private_internal_kimi_parity_silver_theme_v0545.json"
SCORECARD_PATH = REPORT_DIR / "scorecard_v0545.md"

KIMI_ZIP = Path("C:/Users/theam/Downloads/Kimi_Agent_PRMR Memory Core Design.zip")
BOUNDARY_WORDING = "Internal/local controlled-alpha evidence only. External validation and production hardening are separate future milestones."

ROUTES = {
    "/": FRONTEND_DIR / "app/page.tsx",
    "/demo": FRONTEND_DIR / "app/demo/page.tsx",
    "/alpha": FRONTEND_DIR / "app/alpha/page.tsx",
    "/docs": FRONTEND_DIR / "app/docs/page.tsx",
    "/contact": FRONTEND_DIR / "app/contact/page.tsx",
}

LOGO_PLACEMENTS = {
    "navigation": FRONTEND_DIR / "components/landing/Navigation.tsx",
    "hero": FRONTEND_DIR / "components/landing/HeroSection.tsx",
    "footer": FRONTEND_DIR / "components/landing/Footer.tsx",
    "alpha_section": FRONTEND_DIR / "components/landing/AlphaAccessSection.tsx",
}

EXPECTED_KIMI_FILES = [
    "app/src/App.tsx",
    "app/src/config.ts",
    "app/src/sections/Hero.tsx",
    "app/src/sections/Navigation.tsx",
    "app/src/sections/Footer.tsx",
    "app/src/sections/AlphaAccessSection.tsx",
    "app/src/sections/ApiFlowSection.tsx",
    "app/src/sections/DemoPreview.tsx",
    "app/src/sections/EvidenceSection.tsx",
    "app/src/sections/ProblemSection.tsx",
    "app/src/sections/SolutionSection.tsx",
    "app/src/index.css",
    "app/tailwind.config.js",
]

SOURCE_DIRS = [
    FRONTEND_DIR / "app",
    FRONTEND_DIR / "components",
    FRONTEND_DIR / "data",
]

WARM_THEME_TERMS = [
    "gold",
    "bronze",
    "amber",
    "rgba(215",
    "rgba(200, 170",
    "b78645",
    "d7b46a",
    "GoldDivider",
]

SILVER_THEME_TERMS = [
    "silver",
    "steel",
    "frost",
    "bluewhite",
    "rgba(232,238,245",
    "rgba(185,215,255",
    "SilverDivider",
    "silver-button",
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
    checks.append({
        "name": name,
        "passed": bool(passed),
        "details": details or {},
    })


def public_checks(checks):
    return [{"name": check["name"], "passed": check["passed"]} for check in checks]


def source_files():
    files = []
    for directory in SOURCE_DIRS:
        files.extend(path for path in directory.rglob("*") if path.is_file() and path.suffix in {".ts", ".tsx", ".css"})
    files.append(FRONTEND_DIR / "README.md")
    files.append(FRONTEND_DIR / "tailwind.config.ts")
    files.append(FRONTEND_DIR / "package.json")
    return [path for path in files if path.exists()]


def combined_source_text():
    return "\n".join(read_text(path) for path in source_files())


def inspect_kimi_zip():
    if not KIMI_ZIP.exists():
        return {"exists": False, "missing_expected_files": EXPECTED_KIMI_FILES, "asset_count": 0}
    with zipfile.ZipFile(KIMI_ZIP, "r") as archive:
        names = set(archive.namelist())
    return {
        "exists": True,
        "missing_expected_files": [name for name in EXPECTED_KIMI_FILES if name not in names],
        "asset_count": sum(1 for name in names if name.startswith("app/public/") and not name.endswith(".gitkeep")),
    }


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


def build_public_report(checks, kimi_inspection):
    passed_count = sum(1 for check in checks if check["passed"])
    total_checks = len(checks)
    result = "PASS" if passed_count == total_checks else "NEEDS_WORK"

    return {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": VERSION,
        "report_type": "kimi_parity_silver_theme_frontend_correction",
        "public_safe": True,
        "timestamp": datetime.now().isoformat(),
        "result": result,
        "passed_checks": passed_count,
        "total_checks": total_checks,
        "all_checks_passed": passed_count == total_checks,
        "kimi_design_source_inspected": kimi_inspection["exists"] and not kimi_inspection["missing_expected_files"],
        "canonical_frontend": "frontend/",
        "routes": list(ROUTES.keys()),
        "visual_correction_summary": [
            "Moved the frontend from warm metallic styling to Afternum silver, white, black, cool grey, and faint blue-white glow.",
            "Reworked the hero toward a Kimi-style full-screen central identity composition.",
            "Replaced warm dividers and accents with silver lab-frame, sparse navigation, cold data-rain, and larger cinematic section rhythm.",
            "Preserved PRMR product clarity, mock data, routes, and evidence boundaries.",
        ],
        "boundary": (
            "V0.54.5 is local frontend visual/design correction evidence only. It is not hosted, "
            "not production-ready, not bank approved, not compliance approved, not legal approval, "
            "not external security certification, and not real-world validation."
        ),
        "checks": public_checks(checks),
        "remaining_gaps": [
            "Founder visual approval still requires human review in browser.",
            "Backend/demo connection remains future work.",
            "Accessibility and responsive visual polish should get a dedicated follow-up pass.",
            "Dependency audit still reports moderate advisories that need an upstream-compatible fix.",
        ],
    }


def build_scorecard(public_report):
    lines = [
        "# PRMR V0.54.5 Kimi Design Parity Correction + Silver Afternum Theme",
        "",
        "Company: Afternum Industries  ",
        "Product: PRMR Memory Core  ",
        "Version: V0.54.5  ",
        "",
        "## Result",
        "",
        f"**{public_report['result']}**",
        "",
        f"Passed checks: **{public_report['passed_checks']}/{public_report['total_checks']}**",
        "",
        "## Visual Correction",
        "",
    ]
    for item in public_report["visual_correction_summary"]:
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
    print("PRMR V0.54.5 KIMI PARITY SILVER THEME AUDIT")
    print("-------------------------------------------")

    checks = []
    source_text = combined_source_text()
    kimi_inspection = inspect_kimi_zip()

    add_check(
        checks,
        "kimi_source_was_inspected",
        kimi_inspection["exists"] and not kimi_inspection["missing_expected_files"],
        kimi_inspection,
    )

    add_check(
        checks,
        "canonical_frontend_preserved",
        FRONTEND_DIR.exists() and (FRONTEND_DIR / "app").exists() and (FRONTEND_DIR / "components").exists(),
        {"canonical_frontend": str(FRONTEND_DIR)},
    )

    for placement, path in LOGO_PLACEMENTS.items():
        text = read_text(path) if path.exists() else ""
        add_check(
            checks,
            f"afternum_logo_still_in_{placement}",
            path.exists() and "AfternumLogo" in text,
            {"path": str(path)},
        )

    warm_hits = lines_with_terms(source_text, WARM_THEME_TERMS)
    add_check(
        checks,
        "warm_theme_is_not_primary",
        not warm_hits,
        {"warm_theme_hit_count": len(warm_hits), "warm_theme_hits": warm_hits[:20]},
    )

    missing_silver_terms = [term for term in SILVER_THEME_TERMS if term not in source_text]
    add_check(
        checks,
        "silver_white_black_theme_tokens_present",
        not missing_silver_terms,
        {"missing_silver_terms": missing_silver_terms},
    )

    add_check(
        checks,
        "no_gold_divider_component_remains",
        not (FRONTEND_DIR / "components/visual/GoldDivider.tsx").exists()
        and (FRONTEND_DIR / "components/visual/SilverDivider.tsx").exists()
        and "GoldDivider" not in source_text,
        {},
    )

    background_text = read_text(FRONTEND_DIR / "components/visual/DataRainBackground.tsx")
    add_check(
        checks,
        "data_rain_uses_cool_silver_theme",
        "226, 235, 244" in background_text and "185, 215, 255" in background_text and "215, 180, 106" not in background_text,
        {},
    )

    missing_routes = [route for route, path in ROUTES.items() if not path.exists()]
    add_check(checks, "all_routes_still_exist", not missing_routes, {"missing_routes": missing_routes})

    add_check(
        checks,
        "homepage_includes_afternum_company_identity",
        "Afternum Industries" in source_text,
        {},
    )

    add_check(
        checks,
        "homepage_includes_prmr_first_product",
        "PRMR Memory Core" in source_text,
        {},
    )

    add_check(
        checks,
        "boundary_wording_is_present",
        BOUNDARY_WORDING in source_text,
        {"boundary": BOUNDARY_WORDING},
    )

    add_check(
        checks,
        "no_hosted_or_production_claims",
        not unsafe_claim_lines(source_text),
        {"unsafe_claim_lines": unsafe_claim_lines(source_text)},
    )

    approval_terms = [
        "bank approved",
        "bank approval",
        "compliance approved",
        "compliance approval",
        "legal approval",
        "legal approved",
        "external security certification",
        "external security certified",
    ]
    approval_claim_lines = unsafe_claim_lines("\n".join(lines_with_terms(source_text, approval_terms)))
    add_check(
        checks,
        "no_bank_compliance_legal_security_approval_claims",
        not approval_claim_lines,
        {"unsafe_approval_claim_lines": approval_claim_lines},
    )

    unsafe_terms = scan_unsafe_public_language({"frontend": source_text})
    add_check(
        checks,
        "no_punitive_or_certain_guilt_wording",
        not unsafe_terms,
        {"unsafe_terms": unsafe_terms},
    )

    restricted_terms = restricted_hits(source_text)
    add_check(
        checks,
        "no_restricted_public_terms",
        not restricted_terms,
        {"restricted_terms": restricted_terms},
    )

    add_check(
        checks,
        "frontend_does_not_expose_credentials",
        not frontend_exposes_credentials(source_text),
        {"unsafe_lines": frontend_exposes_credentials(source_text)},
    )

    add_check(
        checks,
        "frontend_still_uses_synthetic_demo_data_only",
        "Synthetic/demo data only" in source_text and "demoScenarios" in source_text and "fetch(" not in source_text,
        {},
    )

    typecheck = run_frontend_command("npm run typecheck")
    add_check(
        checks,
        "npm_typecheck_passes",
        typecheck.returncode == 0,
        {"returncode": typecheck.returncode, "stdout_tail": typecheck.stdout.splitlines()[-12:], "stderr_tail": typecheck.stderr.splitlines()[-12:]},
    )

    build = run_frontend_command("npm run build")
    add_check(
        checks,
        "npm_build_passes",
        build.returncode == 0,
        {"returncode": build.returncode, "stdout_tail": build.stdout.splitlines()[-16:], "stderr_tail": build.stderr.splitlines()[-16:]},
    )

    public_report = build_public_report(checks, kimi_inspection)
    scorecard_text = build_scorecard(public_report)
    public_scan = public_artifacts_are_clean(public_report, scorecard_text)
    add_check(
        checks,
        "public_report_and_scorecard_are_claim_safe",
        not public_scan["restricted_terms"] and not public_scan["unsafe_terms"] and not public_scan["unsafe_claim_lines"],
        public_scan,
    )

    public_report = build_public_report(checks, kimi_inspection)
    scorecard_text = build_scorecard(public_report)
    final_public_scan = public_artifacts_are_clean(public_report, scorecard_text)
    if final_public_scan["restricted_terms"] or final_public_scan["unsafe_terms"] or final_public_scan["unsafe_claim_lines"]:
        add_check(checks, "final_public_artifact_hygiene_holds", False, final_public_scan)
        public_report = build_public_report(checks, kimi_inspection)
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
        "kimi_inspection": kimi_inspection,
        "command_outputs": {
            "typecheck": {
                "returncode": typecheck.returncode,
                "stdout": typecheck.stdout,
                "stderr": typecheck.stderr,
            },
            "build": {
                "returncode": build.returncode,
                "stdout": build.stdout,
                "stderr": build.stderr,
            },
        },
        "visual_source_files_checked": [str(path) for path in source_files()],
        "restricted_note": "Detailed report includes command output and source inspection traces for internal validation.",
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
