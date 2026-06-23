import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from prmr.product.alpha_api_sandbox_v0521 import scan_unsafe_public_language


VERSION = "0.54.3"
FRONTEND_DIR = Path("frontend")
REPORT_DIR = Path("reports/v0543")
REPORT_DIR.mkdir(parents=True, exist_ok=True)

PUBLIC_PATH = REPORT_DIR / "public_afternum_identity_integration_v0543.json"
PRIVATE_PATH = REPORT_DIR / "private_internal_afternum_identity_integration_v0543.json"
SCORECARD_PATH = REPORT_DIR / "scorecard_v0543.md"

LOGO_ASSET = FRONTEND_DIR / "public/brand/afternum-logo.png"
LOGO_COMPONENT = FRONTEND_DIR / "components/brand/AfternumLogo.tsx"
KIMI_ZIP = Path("C:/Users/theam/Downloads/Kimi_Agent_PRMR Memory Core Design.zip")

ROUTES = {
    "/": FRONTEND_DIR / "app/page.tsx",
    "/demo": FRONTEND_DIR / "app/demo/page.tsx",
    "/alpha": FRONTEND_DIR / "app/alpha/page.tsx",
    "/docs": FRONTEND_DIR / "app/docs/page.tsx",
    "/contact": FRONTEND_DIR / "app/contact/page.tsx",
}

PLACEMENT_FILES = {
    "navigation": FRONTEND_DIR / "components/landing/Navigation.tsx",
    "hero": FRONTEND_DIR / "components/landing/HeroSection.tsx",
    "footer": FRONTEND_DIR / "components/landing/Footer.tsx",
    "alpha_access": FRONTEND_DIR / "components/landing/AlphaAccessSection.tsx",
    "alpha_notice": FRONTEND_DIR / "components/alpha/ControlledAlphaNotice.tsx",
}

SOURCE_DIRS = [
    FRONTEND_DIR / "app",
    FRONTEND_DIR / "components",
    FRONTEND_DIR / "data",
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
    files.append(FRONTEND_DIR / "package.json")
    return files


def combined_public_source_text():
    return "\n".join(read_text(path) for path in source_files() if path.exists())


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
                "no deployment",
                "not hosted",
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
        "report_type": "afternum_identity_integration",
        "public_safe": True,
        "timestamp": datetime.now().isoformat(),
        "result": result,
        "passed_checks": passed_count,
        "total_checks": total_checks,
        "all_checks_passed": passed_count == total_checks,
        "logo_asset": "frontend/public/brand/afternum-logo.png",
        "logo_component": "frontend/components/brand/AfternumLogo.tsx",
        "logo_placements": ["navigation", "hero", "footer", "alpha_access"],
        "routes": list(ROUTES.keys()),
        "kimi_design_source_inspected": KIMI_ZIP.exists(),
        "identity_summary": [
            "Afternum Industries is now the top-level hero and navigation identity.",
            "PRMR Memory Core is presented as the first product under Afternum.",
            "Logo usage is reusable across nav, hero, footer, alpha access, and mark contexts.",
            "The frontend remains local, synthetic/demo-only, and disconnected from backend services.",
        ],
        "boundary": (
            "V0.54.3 is local frontend identity/design integration only. It asserts no hosted service, "
            "deployment readiness, banking sign-off, regulatory sign-off, legal sign-off, third-party "
            "security sign-off, or field validation."
        ),
        "checks": public_checks(checks),
        "remaining_v0544_gaps": [
            "Add backend proxy route stubs before connecting the demo to sandbox calls.",
            "Keep public demo data synthetic until approved data handling is explicitly added.",
            "Preserve logo identity while adding live local demo wiring.",
            "Revisit dependency audit advisories when an upstream-compatible Next/PostCSS fix is available.",
        ],
    }


def build_scorecard(public_report):
    lines = [
        "# PRMR V0.54.3 Afternum Identity Integration",
        "",
        "Company: Afternum Industries  ",
        "Product: PRMR Memory Core  ",
        "Version: V0.54.3  ",
        "",
        "## Result",
        "",
        f"**{public_report['result']}**",
        "",
        f"Passed checks: **{public_report['passed_checks']}/{public_report['total_checks']}**",
        "",
        "## Logo",
        "",
        f"- Asset: `{public_report['logo_asset']}`",
        f"- Component: `{public_report['logo_component']}`",
        f"- Placements: {', '.join(public_report['logo_placements'])}",
        "",
        "## Routes",
        "",
    ]

    for route in public_report["routes"]:
        lines.append(f"- `{route}`")

    lines.extend([
        "",
        "## Boundary",
        "",
        public_report["boundary"],
        "",
        "## Checks",
        "",
    ])

    for check in public_report["checks"]:
        status = "PASS" if check["passed"] else "FAIL"
        lines.append(f"- {check['name']}: {status}")

    lines.extend(["", "## V0.54.4 Gaps", ""])
    for gap in public_report["remaining_v0544_gaps"]:
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
    print("PRMR V0.54.3 AFTERNUM IDENTITY INTEGRATION AUDIT")
    print("------------------------------------------------")

    checks = []
    source_text = combined_public_source_text()

    add_check(
        checks,
        "logo_asset_exists_at_required_path",
        LOGO_ASSET.exists() and LOGO_ASSET.stat().st_size > 0,
        {"path": str(LOGO_ASSET), "exists": LOGO_ASSET.exists()},
    )

    logo_text = read_text(LOGO_COMPONENT) if LOGO_COMPONENT.exists() else ""
    add_check(
        checks,
        "afternum_logo_component_exists",
        LOGO_COMPONENT.exists()
        and "/brand/afternum-logo.png" in logo_text
        and "Afternum Industries logo" in logo_text
        and "next/image" in logo_text
        and all(size in logo_text for size in ['"nav"', '"hero"', '"footer"', '"mark"']),
        {"path": str(LOGO_COMPONENT)},
    )

    for placement, path in PLACEMENT_FILES.items():
        text = read_text(path) if path.exists() else ""
        add_check(
            checks,
            f"logo_appears_in_{placement}",
            path.exists() and "AfternumLogo" in text,
            {"path": str(path)},
        )

    missing_routes = [route for route, path in ROUTES.items() if not path.exists()]
    add_check(checks, "required_routes_still_exist", not missing_routes, {"missing_routes": missing_routes})

    add_check(
        checks,
        "frontend_does_not_expose_credentials",
        not frontend_exposes_credentials(source_text),
        {"unsafe_lines": frontend_exposes_credentials(source_text)},
    )

    synthetic_terms_present = all(term in source_text for term in ["Synthetic/demo data only", "demoScenarios"])
    add_check(
        checks,
        "frontend_still_uses_synthetic_demo_data_only",
        synthetic_terms_present and "fetch(" not in source_text and "axios" not in source_text,
        {"synthetic_terms_present": synthetic_terms_present},
    )

    add_check(
        checks,
        "public_copy_has_no_unqualified_hosted_or_production_claims",
        not unsafe_claim_lines(source_text),
        {"unsafe_claim_lines": unsafe_claim_lines(source_text)},
    )

    unsafe_terms = scan_unsafe_public_language({"frontend": source_text})
    add_check(
        checks,
        "public_copy_avoids_punitive_or_certain_guilt_wording",
        not unsafe_terms,
        {"unsafe_terms": unsafe_terms},
    )

    restricted_terms = restricted_hits(source_text)
    add_check(
        checks,
        "public_copy_avoids_restricted_terms",
        not restricted_terms,
        {"restricted_terms": restricted_terms},
    )

    readme_text = read_text(FRONTEND_DIR / "README.md") if (FRONTEND_DIR / "README.md").exists() else ""
    readme_terms = [
        "Logo Usage",
        "frontend/public/brand/afternum-logo.png",
        "frontend/components/brand/AfternumLogo.tsx",
        "Afternum Industries logo",
        "Current Limitations",
    ]
    missing_readme_terms = [term for term in readme_terms if term not in readme_text]
    add_check(
        checks,
        "readme_documents_logo_usage_and_limitations",
        not missing_readme_terms,
        {"missing_readme_terms": missing_readme_terms},
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

    public_report = build_public_report(checks)
    scorecard_text = build_scorecard(public_report)
    public_scan = public_artifacts_are_clean(public_report, scorecard_text)
    add_check(
        checks,
        "public_report_hygiene_holds",
        not public_scan["restricted_terms"] and not public_scan["unsafe_terms"] and not public_scan["unsafe_claim_lines"],
        public_scan,
    )

    public_report = build_public_report(checks)
    scorecard_text = build_scorecard(public_report)
    final_public_scan = public_artifacts_are_clean(public_report, scorecard_text)
    if final_public_scan["restricted_terms"] or final_public_scan["unsafe_terms"] or final_public_scan["unsafe_claim_lines"]:
        add_check(checks, "final_public_artifact_hygiene_holds", False, final_public_scan)
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
        "kimi_design_zip": {
            "path": str(KIMI_ZIP),
            "exists": KIMI_ZIP.exists(),
            "inspected_for": ["Hero", "Navigation", "Footer", "AlphaAccessSection", "config", "index.css"],
        },
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
        "restricted_note": "Restricted report includes full command tails and design-source inspection metadata.",
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
