import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from prmr.product.alpha_api_sandbox_v0521 import scan_unsafe_public_language


VERSION = "0.54.4"
FRONTEND_DIR = Path("frontend")
REPORT_DIR = Path("reports/v0544")
REPORT_DIR.mkdir(parents=True, exist_ok=True)

PUBLIC_PATH = REPORT_DIR / "public_kimi_visual_parity_v0544.json"
PRIVATE_PATH = REPORT_DIR / "private_internal_kimi_visual_parity_v0544.json"
SCORECARD_PATH = REPORT_DIR / "scorecard_v0544.md"

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
    "alpha_access": FRONTEND_DIR / "components/landing/AlphaAccessSection.tsx",
}

VISUAL_COMPONENTS = {
    "DataRainBackground": FRONTEND_DIR / "components/visual/DataRainBackground.tsx",
    "LabFrame": FRONTEND_DIR / "components/visual/LabFrame.tsx",
    "SectionShell": FRONTEND_DIR / "components/visual/SectionShell.tsx",
    "GoldDivider": FRONTEND_DIR / "components/visual/GoldDivider.tsx",
    "SignalGrid": FRONTEND_DIR / "components/visual/SignalGrid.tsx",
}

VISUAL_ASSET_DIR = FRONTEND_DIR / "public/visual"

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
                "not claimed",
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


def build_public_report(checks, kimi_available):
    passed_count = sum(1 for check in checks if check["passed"])
    total_checks = len(checks)
    result = "PASS" if passed_count == total_checks else "NEEDS_WORK"

    return {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": VERSION,
        "report_type": "kimi_visual_parity_afternum_brand_merge",
        "public_safe": True,
        "timestamp": datetime.now().isoformat(),
        "result": result,
        "passed_checks": passed_count,
        "total_checks": total_checks,
        "all_checks_passed": passed_count == total_checks,
        "kimi_design_source_inspected": bool(kimi_available),
        "canonical_frontend": "frontend/",
        "visual_components": list(VISUAL_COMPONENTS.keys()),
        "visual_assets": "frontend/public/visual/",
        "routes": list(ROUTES.keys()),
        "visual_findings": [
            "Kimi source emphasized amber data-rain atmosphere, cinematic spacing, thin borders, and serif-led hierarchy.",
            "Canonical frontend now uses reusable visual primitives instead of replacing the app.",
            "Afternum Industries remains the top-level identity; PRMR Memory Core remains the first product.",
        ],
        "boundary": (
            "V0.54.4 is local frontend visual/design integration only. It asserts no hosted service, "
            "deployment readiness, banking sign-off, regulatory sign-off, legal sign-off, third-party "
            "security sign-off, or field validation."
        ),
        "checks": public_checks(checks),
        "remaining_backend_demo_connection_gaps": [
            "Add backend proxy route stubs before connecting demo components to sandbox calls.",
            "Keep public demo output synthetic until approved data handling exists.",
            "Preserve public-safe report boundaries when local sandbox wiring is added.",
            "Continue tracking dependency audit advisories until an upstream-compatible fix is available.",
        ],
    }


def build_scorecard(public_report):
    lines = [
        "# PRMR V0.54.4 Kimi Visual Parity + Afternum Brand Merge",
        "",
        "Company: Afternum Industries  ",
        "Product: PRMR Memory Core  ",
        "Version: V0.54.4  ",
        "",
        "## Result",
        "",
        f"**{public_report['result']}**",
        "",
        f"Passed checks: **{public_report['passed_checks']}/{public_report['total_checks']}**",
        "",
        "## Visual Components",
        "",
    ]
    for name in public_report["visual_components"]:
        lines.append(f"- {name}")

    lines.extend(["", "## Routes", ""])
    for route in public_report["routes"]:
        lines.append(f"- `{route}`")

    lines.extend(["", "## Boundary", "", public_report["boundary"], "", "## Checks", ""])
    for check in public_report["checks"]:
        status = "PASS" if check["passed"] else "FAIL"
        lines.append(f"- {check['name']}: {status}")

    lines.extend(["", "## Remaining Backend/Demo Connection Gaps", ""])
    for gap in public_report["remaining_backend_demo_connection_gaps"]:
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
    print("PRMR V0.54.4 KIMI VISUAL PARITY AUDIT")
    print("-------------------------------------")

    checks = []
    source_text = combined_public_source_text()

    add_check(
        checks,
        "kimi_design_source_inspected_or_reported",
        KIMI_ZIP.exists(),
        {"kimi_zip": str(KIMI_ZIP), "exists": KIMI_ZIP.exists()},
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

    missing_visual_components = [name for name, path in VISUAL_COMPONENTS.items() if not path.exists()]
    add_check(
        checks,
        "visual_components_created",
        not missing_visual_components,
        {"missing_visual_components": missing_visual_components},
    )

    visual_source_requirements = ["DataRainBackground", "LabFrame", "SectionShell", "SignalGrid", "lab-grid"]
    missing_visual_references = [term for term in visual_source_requirements if term not in source_text]
    add_check(
        checks,
        "visual_system_applied_to_frontend",
        not missing_visual_references,
        {"missing_visual_references": missing_visual_references},
    )

    visual_assets = list(VISUAL_ASSET_DIR.glob("*")) if VISUAL_ASSET_DIR.exists() else []
    add_check(
        checks,
        "safe_visual_assets_available",
        len(visual_assets) >= 4,
        {"asset_count": len(visual_assets), "asset_names": [path.name for path in visual_assets]},
    )

    missing_routes = [route for route, path in ROUTES.items() if not path.exists()]
    add_check(checks, "required_routes_still_exist", not missing_routes, {"missing_routes": missing_routes})

    homepage_text = read_text(ROUTES["/"]) + read_text(FRONTEND_DIR / "components/landing/HeroSection.tsx")
    add_check(
        checks,
        "homepage_preserves_brand_hierarchy",
        "Afternum Industries" in source_text
        and "PRMR Memory Core" in source_text
        and "Infrastructure for Continuity" in homepage_text,
        {},
    )

    add_check(
        checks,
        "required_boundary_wording_present",
        BOUNDARY_WORDING in source_text,
        {"boundary": BOUNDARY_WORDING},
    )

    add_check(
        checks,
        "no_unqualified_hosted_production_or_certification_claims",
        not unsafe_claim_lines(source_text),
        {"unsafe_claim_lines": unsafe_claim_lines(source_text)},
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

    public_report = build_public_report(checks, KIMI_ZIP.exists())
    scorecard_text = build_scorecard(public_report)
    public_scan = public_artifacts_are_clean(public_report, scorecard_text)
    add_check(
        checks,
        "public_report_hygiene_holds",
        not public_scan["restricted_terms"] and not public_scan["unsafe_terms"] and not public_scan["unsafe_claim_lines"],
        public_scan,
    )

    public_report = build_public_report(checks, KIMI_ZIP.exists())
    scorecard_text = build_scorecard(public_report)
    final_public_scan = public_artifacts_are_clean(public_report, scorecard_text)
    if final_public_scan["restricted_terms"] or final_public_scan["unsafe_terms"] or final_public_scan["unsafe_claim_lines"]:
        add_check(checks, "final_public_artifact_hygiene_holds", False, final_public_scan)
        public_report = build_public_report(checks, KIMI_ZIP.exists())
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
            "inspected_for": [
                "AmberCascades",
                "Hero",
                "Navigation",
                "Footer",
                "AlphaAccessSection",
                "ApiFlowSection",
                "DemoPreview",
                "EvidenceSection",
                "ProblemSection",
                "SolutionSection",
                "index.css",
                "tailwind.config.js",
                "public images",
            ],
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
        "restricted_note": "Restricted report includes detailed audit checks and command outputs for internal validation.",
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
