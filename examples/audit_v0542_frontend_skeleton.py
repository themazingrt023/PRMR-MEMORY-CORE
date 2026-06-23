import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from prmr.product.alpha_api_sandbox_v0521 import scan_unsafe_public_language


VERSION = "0.54.2"
FRONTEND_DIR = Path("frontend")
REPORT_DIR = Path("reports/v0542")
REPORT_DIR.mkdir(parents=True, exist_ok=True)

PUBLIC_PATH = REPORT_DIR / "public_frontend_skeleton_v0542.json"
PRIVATE_PATH = REPORT_DIR / "private_internal_frontend_skeleton_v0542.json"
SCORECARD_PATH = REPORT_DIR / "scorecard_v0542.md"


ROUTES = {
    "/": FRONTEND_DIR / "app/page.tsx",
    "/demo": FRONTEND_DIR / "app/demo/page.tsx",
    "/alpha": FRONTEND_DIR / "app/alpha/page.tsx",
    "/docs": FRONTEND_DIR / "app/docs/page.tsx",
    "/contact": FRONTEND_DIR / "app/contact/page.tsx",
}

COMPONENTS = {
    "HeroSection": FRONTEND_DIR / "components/landing/HeroSection.tsx",
    "ProblemSection": FRONTEND_DIR / "components/landing/ProblemSection.tsx",
    "SolutionSection": FRONTEND_DIR / "components/landing/SolutionSection.tsx",
    "ApiFlowSection": FRONTEND_DIR / "components/landing/ApiFlowSection.tsx",
    "EvidenceSection": FRONTEND_DIR / "components/landing/EvidenceSection.tsx",
    "UseCasesSection": FRONTEND_DIR / "components/landing/UseCasesSection.tsx",
    "AlphaAccessSection": FRONTEND_DIR / "components/landing/AlphaAccessSection.tsx",
    "Footer": FRONTEND_DIR / "components/landing/Footer.tsx",
    "ScenarioSelector": FRONTEND_DIR / "components/demo/ScenarioSelector.tsx",
    "ContinuityPacketCard": FRONTEND_DIR / "components/demo/ContinuityPacketCard.tsx",
    "ExplanationCard": FRONTEND_DIR / "components/demo/ExplanationCard.tsx",
    "LeastHarmActionCard": FRONTEND_DIR / "components/demo/LeastHarmActionCard.tsx",
    "ReportPreviewCard": FRONTEND_DIR / "components/demo/ReportPreviewCard.tsx",
    "ApiOverview": FRONTEND_DIR / "components/docs/ApiOverview.tsx",
    "EndpointList": FRONTEND_DIR / "components/docs/EndpointList.tsx",
    "VersionTimeline": FRONTEND_DIR / "components/docs/VersionTimeline.tsx",
    "EvidenceBoundaryNotice": FRONTEND_DIR / "components/docs/EvidenceBoundaryNotice.tsx",
    "RequestAccessForm": FRONTEND_DIR / "components/alpha/RequestAccessForm.tsx",
    "ControlledAlphaNotice": FRONTEND_DIR / "components/alpha/ControlledAlphaNotice.tsx",
}

ROUTE_COMPONENTS = {
    "/": [
        "HeroSection",
        "ProblemSection",
        "SolutionSection",
        "ApiFlowSection",
        "EvidenceSection",
        "UseCasesSection",
        "AlphaAccessSection",
        "Footer",
    ],
    "/demo": [
        "ScenarioSelector",
        "ContinuityPacketCard",
        "ExplanationCard",
        "LeastHarmActionCard",
        "ReportPreviewCard",
        "Footer",
    ],
    "/alpha": ["ControlledAlphaNotice", "RequestAccessForm", "Footer"],
    "/docs": ["ApiOverview", "EndpointList", "VersionTimeline", "EvidenceBoundaryNotice", "Footer"],
    "/contact": ["Footer"],
}

REQUIRED_DATA_FILES = [
    FRONTEND_DIR / "data/demoData.ts",
    FRONTEND_DIR / "data/evidence.ts",
    FRONTEND_DIR / "data/apiDocs.ts",
]

REQUIRED_CONFIG_FILES = [
    FRONTEND_DIR / "package.json",
    FRONTEND_DIR / "next.config.mjs",
    FRONTEND_DIR / "tsconfig.json",
    FRONTEND_DIR / "tailwind.config.ts",
    FRONTEND_DIR / "postcss.config.mjs",
    FRONTEND_DIR / "app/globals.css",
    FRONTEND_DIR / "app/layout.tsx",
]

REQUIRED_STACK = ["next", "react", "react-dom", "typescript", "tailwindcss"]

FORBIDDEN_SERVICE_DEPS = [
    "stripe",
    "@stripe/stripe-js",
    "next-auth",
    "@auth/core",
    "@supabase/supabase-js",
    "firebase",
    "auth0",
    "@auth0/nextjs-auth0",
]

FORBIDDEN_PUBLIC_TERMS = [
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

CLAIM_PATTERNS = [
    "production-ready",
    "production ready",
    "externally validated",
    "bank-approved",
    "bank approved",
    "compliance-certified",
    "compliance certified",
    "legal-approved",
    "legal approved",
    "security-certified",
    "security certified",
    "deployed service",
    "hosted api is live",
    "stripe integration",
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


def all_frontend_text():
    paths = [
        *ROUTES.values(),
        *COMPONENTS.values(),
        *REQUIRED_DATA_FILES,
        FRONTEND_DIR / "README.md",
    ]
    return "\n".join(read_text(path) for path in paths if path.exists())


def component_exports_ok():
    missing = []
    malformed = []
    for name, path in COMPONENTS.items():
        if not path.exists():
            missing.append(name)
            continue
        text = read_text(path)
        if f"export function {name}" not in text:
            malformed.append(name)
        if "return (" not in text:
            malformed.append(f"{name}: no JSX return")
    return missing, malformed


def route_wiring_ok():
    missing = []
    for route, path in ROUTES.items():
        if not path.exists():
            missing.append({"route": route, "reason": "missing file"})
            continue
        text = read_text(path)
        for component in ROUTE_COMPONENTS[route]:
            if f"<{component}" not in text and f"import {{ {component} }}" not in text:
                missing.append({"route": route, "component": component})
    return missing


def package_json():
    return json.loads(read_text(FRONTEND_DIR / "package.json"))


def claim_hits(text):
    lower = text.lower()
    return [term for term in CLAIM_PATTERNS if term in lower]


def restricted_hits(text):
    lower = text.lower()
    return [term for term in FORBIDDEN_PUBLIC_TERMS if term in lower]


def build_public_report(checks):
    passed_count = sum(1 for check in checks if check["passed"])
    total_checks = len(checks)
    result = "PASS" if passed_count == total_checks else "NEEDS_WORK"

    return {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": VERSION,
        "report_type": "frontend_skeleton",
        "public_safe": True,
        "timestamp": datetime.now().isoformat(),
        "result": result,
        "passed_checks": passed_count,
        "total_checks": total_checks,
        "all_checks_passed": passed_count == total_checks,
        "routes": list(ROUTES.keys()),
        "landing_components": [
            "HeroSection",
            "ProblemSection",
            "SolutionSection",
            "ApiFlowSection",
            "EvidenceSection",
            "UseCasesSection",
            "AlphaAccessSection",
            "Footer",
        ],
        "demo_components": [
            "ScenarioSelector",
            "ContinuityPacketCard",
            "ExplanationCard",
            "LeastHarmActionCard",
            "ReportPreviewCard",
        ],
        "docs_components": [
            "ApiOverview",
            "EndpointList",
            "VersionTimeline",
            "EvidenceBoundaryNotice",
        ],
        "alpha_components": ["RequestAccessForm", "ControlledAlphaNotice"],
        "stack": ["Next.js", "React", "TypeScript", "Tailwind CSS"],
        "data_policy": "Synthetic/demo data only.",
        "service_policy": "No external services, billing, payment provider wiring, or live authentication are wired in this skeleton.",
        "boundary": (
            "This is a local frontend product shell only. It asserts no deployment status, field validation, "
            "banking sign-off, regulatory sign-off, legal sign-off, third-party security sign-off, or launch readiness."
        ),
        "checks": public_checks(checks),
        "remaining_gaps": [
            "Review the remaining moderate npm audit advisories in the Next/PostCSS dependency path when an upstream-compatible fix is available.",
            "Add Kimi's visual design layer without changing evidence boundaries.",
            "Add backend proxy route stubs before connecting any sandbox calls.",
            "Keep public demo data synthetic until approved data handling is explicitly added.",
        ],
    }


def build_scorecard(public_report):
    lines = [
        "# PRMR V0.54.2 Frontend Skeleton",
        "",
        "Company: Afternum Industries  ",
        "Product: PRMR Memory Core  ",
        "Version: V0.54.2  ",
        "",
        "## Result",
        "",
        f"**{public_report['result']}**",
        "",
        f"Passed checks: **{public_report['passed_checks']}/{public_report['total_checks']}**",
        "",
        "## Routes",
        "",
    ]
    for route in public_report["routes"]:
        lines.append(f"- `{route}`")

    lines.extend(["", "## Components", ""])
    for group in ["landing_components", "demo_components", "docs_components", "alpha_components"]:
        lines.append(f"{group}: {', '.join(public_report[group])}")

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

    lines.extend(["", "## Remaining Gaps", ""])
    for gap in public_report["remaining_gaps"]:
        lines.append(f"- {gap}")
    return "\n".join(lines)


def scan_public_report(public_report, scorecard_text):
    text = json.dumps({"public_report": public_report, "scorecard": scorecard_text}, sort_keys=True)
    return {
        "restricted_terms": restricted_hits(text),
        "unsafe_terms": scan_unsafe_public_language({"text": text}),
        "claim_hits": claim_hits(text),
    }


def main():
    print("PRMR V0.54.2 FRONTEND SKELETON AUDIT")
    print("------------------------------------")

    checks = []

    missing_routes = [route for route, path in ROUTES.items() if not path.exists()]
    add_check(checks, "all_routes_exist", not missing_routes, {"missing_routes": missing_routes})

    missing_configs = [str(path) for path in REQUIRED_CONFIG_FILES if not path.exists()]
    add_check(checks, "next_typescript_tailwind_config_exists", not missing_configs, {"missing_configs": missing_configs})

    missing_components, malformed_components = component_exports_ok()
    add_check(
        checks,
        "all_components_renderable_as_tsx_functions",
        not missing_components and not malformed_components,
        {"missing_components": missing_components, "malformed_components": malformed_components},
    )

    route_wiring_missing = route_wiring_ok()
    add_check(
        checks,
        "routes_wire_required_components",
        not route_wiring_missing,
        {"missing_wiring": route_wiring_missing},
    )

    data_missing = [str(path) for path in REQUIRED_DATA_FILES if not path.exists()]
    demo_data_text = read_text(FRONTEND_DIR / "data/demoData.ts") if not data_missing else ""
    expected_scenarios = ["agent-memory", "support-history", "risk-continuity"]
    missing_scenarios = [item for item in expected_scenarios if item not in demo_data_text]
    demo_surface_terms = ["continuityPacket", "explanation", "leastHarmAction", "reportPreview"]
    missing_demo_terms = [item for item in demo_surface_terms if item not in demo_data_text]
    add_check(
        checks,
        "synthetic_demo_data_loads",
        not data_missing and not missing_scenarios and not missing_demo_terms,
        {
            "missing_data_files": data_missing,
            "missing_scenarios": missing_scenarios,
            "missing_demo_terms": missing_demo_terms,
        },
    )

    pkg = package_json()
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    missing_stack = [name for name in REQUIRED_STACK if name not in deps]
    forbidden_deps = [name for name in FORBIDDEN_SERVICE_DEPS if name in deps]
    add_check(
        checks,
        "required_stack_present_without_external_service_deps",
        not missing_stack and not forbidden_deps,
        {"missing_stack": missing_stack, "forbidden_deps": forbidden_deps},
    )

    frontend_text = all_frontend_text()
    add_check(
        checks,
        "no_production_or_certification_claims",
        not claim_hits(frontend_text),
        {"claim_hits": claim_hits(frontend_text)},
    )

    add_check(
        checks,
        "no_punitive_or_certain_guilt_wording",
        not scan_unsafe_public_language({"frontend": frontend_text}),
        {"unsafe_terms": scan_unsafe_public_language({"frontend": frontend_text})},
    )

    add_check(
        checks,
        "no_restricted_public_terms",
        not restricted_hits(frontend_text),
        {"restricted_terms": restricted_hits(frontend_text)},
    )

    readme_path = FRONTEND_DIR / "README.md"
    readme_text = read_text(readme_path) if readme_path.exists() else ""
    required_readme_terms = [
        "Run Locally",
        "Routes",
        "Component Architecture",
        "Current Limitations",
        "Integration Boundary",
    ]
    missing_readme_terms = [term for term in required_readme_terms if term not in readme_text]
    add_check(
        checks,
        "readme_exists_with_required_sections",
        readme_path.exists() and not missing_readme_terms,
        {"missing_readme_terms": missing_readme_terms},
    )

    demo_page = read_text(ROUTES["/demo"])
    add_check(
        checks,
        "demo_page_displays_required_outputs",
        all(term in demo_page for term in [
            "ContinuityPacketCard",
            "ExplanationCard",
            "LeastHarmActionCard",
            "ReportPreviewCard",
            "demoScenarios",
        ]),
        {"demo_page": str(ROUTES["/demo"])},
    )

    public_report = build_public_report(checks)
    scorecard_text = build_scorecard(public_report)
    public_scan = scan_public_report(public_report, scorecard_text)
    add_check(
        checks,
        "public_report_hygiene_holds",
        not public_scan["restricted_terms"] and not public_scan["unsafe_terms"] and not public_scan["claim_hits"],
        public_scan,
    )

    public_report = build_public_report(checks)
    scorecard_text = build_scorecard(public_report)
    final_public_scan = scan_public_report(public_report, scorecard_text)
    if final_public_scan["restricted_terms"] or final_public_scan["unsafe_terms"] or final_public_scan["claim_hits"]:
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
        "audited_files": [
            *(str(path) for path in ROUTES.values()),
            *(str(path) for path in COMPONENTS.values()),
            *(str(path) for path in REQUIRED_DATA_FILES),
            str(FRONTEND_DIR / "README.md"),
            str(FRONTEND_DIR / "package.json"),
        ],
        "restricted_note": "Restricted report includes detailed static audit results for internal validation.",
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
