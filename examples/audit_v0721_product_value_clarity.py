"""Audit V0.72.1 product value clarity and site utility rewrite."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
REPORT_DIR = ROOT / "reports" / "v0721"
PUBLIC_REPORT = REPORT_DIR / "public_product_value_clarity_v0721.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_product_value_clarity_v0721.json"
SCORECARD = REPORT_DIR / "scorecard_v0721.md"

PUBLIC_SITE_FILES = [
    FRONTEND / "app" / "page.tsx",
    FRONTEND / "app" / "docs" / "page.tsx",
    FRONTEND / "app" / "demo" / "page.tsx",
    FRONTEND / "app" / "alpha" / "page.tsx",
    FRONTEND / "app" / "dashboard" / "page.tsx",
    FRONTEND / "data" / "productCopy.ts",
    FRONTEND / "data" / "apiDocs.ts",
    FRONTEND / "data" / "dashboardMockData.ts",
    FRONTEND / "components" / "landing" / "HeroSection.tsx",
    FRONTEND / "components" / "landing" / "ProblemSection.tsx",
    FRONTEND / "components" / "landing" / "SolutionSection.tsx",
    FRONTEND / "components" / "landing" / "ApiFlowSection.tsx",
    FRONTEND / "components" / "landing" / "DemoPreviewSection.tsx",
    FRONTEND / "components" / "landing" / "UseCasesSection.tsx",
    FRONTEND / "components" / "landing" / "EvidenceSection.tsx",
    FRONTEND / "components" / "docs" / "ApiOverview.tsx",
    FRONTEND / "components" / "docs" / "DeveloperDocsSections.tsx",
    FRONTEND / "components" / "demo" / "LocalDemoRunner.tsx",
    FRONTEND / "components" / "alpha" / "ControlledAlphaNotice.tsx",
    FRONTEND / "components" / "dashboard" / "ClientOverview.tsx",
]

BOUNDARY = (
    "V0.72.1 is a public site copy and structure clarity pass. It reflects working live frontend and "
    "local/deployable alpha evidence, while hosted client API access remains future work. It is not a "
    "production, bank, compliance, legal, external security, or real-world validation claim."
)

REQUIRED_FILES = PUBLIC_SITE_FILES

OVERCLAIMS = [
    "production-ready",
    "production ready",
    "hosted client api access is live",
    "live hosted api access",
    "live api access granted",
    "billing enabled",
    "self-serve access enabled",
    "bank-approved",
    "bank approved",
    "compliance-certified",
    "compliance certified",
    "legal-approved",
    "legal approved",
    "security-certified",
    "security certified",
    "external validation complete",
    "real-world validated",
    "real client data",
]

CERTIFICATION_PATTERNS = [
    r"(?<!no )bank approval",
    r"(?<!no )compliance approval",
    r"(?<!no )legal approval",
    r"(?<!no )external security certification",
]

VISUAL_REGRESSION_TERMS = ["gold", "bronze", "amber"]
PUNITIVE_TERMS = ["fraudster", "criminal", "guilty", "definitely fraud", "blacklist", "close account immediately"]


def run_command(command: list[str], cwd: Path, timeout: int = 240) -> dict[str, Any]:
    resolved = command[:]
    if resolved and resolved[0] == "npm":
        resolved[0] = shutil.which("npm") or shutil.which("npm.cmd") or "npm.cmd"
    completed = subprocess.run(
        resolved,
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )
    return {
        "command": " ".join(command),
        "returncode": completed.returncode,
        "passed": completed.returncode == 0,
        "output": completed.stdout,
    }


def read_source() -> tuple[str, dict[str, str]]:
    by_file: dict[str, str] = {}
    for path in PUBLIC_SITE_FILES:
        if path.exists():
            by_file[str(path.relative_to(ROOT))] = path.read_text(encoding="utf-8")
    return "\n".join(by_file.values()), by_file


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def contains_all(text: str, fragments: list[str]) -> bool:
    lower = text.lower()
    return all(fragment.lower() in lower for fragment in fragments)


def find_terms(text: str, terms: list[str]) -> list[str]:
    lower = text.lower()
    return [term for term in terms if term.lower() in lower]


def find_certification_claims(text: str) -> list[str]:
    lower = text.lower()
    found = []
    for pattern in CERTIFICATION_PATTERNS:
        if re.search(pattern, lower):
            found.append(pattern)
    return found


def contains_full_key(text: str) -> bool:
    return bool(re.search(r"prmr_alpha_dev_[a-f0-9]{16,}", text))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_scorecard(checks: list[dict[str, Any]], command_results: list[dict[str, Any]]) -> str:
    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"
    lines = [
        "# V0.72.1 Product Value Clarity + Site Utility Rewrite",
        "",
        f"Result: {result}",
        f"Passed checks: {passed}/{total}",
        "",
        f"Boundary: {BOUNDARY}",
        "",
        "## Checks",
        "",
    ]
    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        lines.append(f"- {status}: {check['name']} - {check['detail']}")
    lines.extend(["", "## Command Results", ""])
    for result_item in command_results:
        status = "PASS" if result_item["passed"] else "FAIL"
        lines.append(f"- {status}: {result_item['command']}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    checks: list[dict[str, Any]] = []
    command_results: list[dict[str, Any]] = []

    for path in REQUIRED_FILES:
        add_check(checks, f"{path.name}_exists", path.exists(), str(path.relative_to(ROOT)))

    source_text, by_file = read_source()
    lower = source_text.lower()

    add_check(checks, "homepage_states_continuity_infrastructure", "continuity infrastructure for ai systems and organisations" in lower, None)
    add_check(checks, "homepage_explains_api_key_client_vault_namespace", contains_all(source_text, ["API key", "client ID", "vault", "namespace"]), None)
    add_check(checks, "homepage_explains_messy_events_to_packets", contains_all(source_text, ["messy", "event", "continuity packets"]), None)
    add_check(
        checks,
        "context_efficiency_is_honest",
        "can make limited context feel wider" in lower and "does not literally increase" in lower and "official context window" in lower,
        None,
    )
    add_check(checks, "storage_remembers_line_present", "Storage remembers data. PRMR remembers change." in source_text, None)
    add_check(checks, "outside_model_line_present", "continuity layer outside the model" in lower, None)

    ai_use_case_terms = ["ai assistant", "agent memory", "chatbots", "cross-session", "cleaner continuity context"]
    add_check(checks, "ai_system_use_cases_explained", len([term for term in ai_use_case_terms if term in lower]) >= 3, ai_use_case_terms)

    org_use_case_terms = ["customer support", "legal", "research", "education", "game studio", "enterprise decision", "project management"]
    add_check(checks, "non_ai_organisation_use_cases_explained", len([term for term in org_use_case_terms if term in lower]) >= 6, org_use_case_terms)

    add_check(
        checks,
        "dashboard_client_value_explained",
        contains_all(source_text, ["dashboard lets clients see", "keys", "vaults", "namespaces", "usage", "blocked requests", "reports", "memory health"]),
        None,
    )
    add_check(
        checks,
        "raw_events_to_dashboard_flow_present",
        contains_all(source_text, ["Raw events", "PRMR continuity packet", "reconstructed state", "explanation/report", "dashboard visibility"]),
        None,
    )
    add_check(checks, "avoids_memory_magic_claims", "memory magic" not in lower and "magically" not in lower, None)

    overclaims = find_terms(source_text, OVERCLAIMS)
    add_check(checks, "avoids_false_production_or_hosted_claims", not overclaims, overclaims)
    add_check(checks, "no_raw_keys_or_secrets_exposed", not contains_full_key(source_text), None)
    cert_claims = find_certification_claims(source_text)
    add_check(checks, "no_bank_compliance_legal_security_certification_claims", not cert_claims, cert_claims)
    punitive = find_terms(source_text, PUNITIVE_TERMS)
    add_check(checks, "public_wording_non_punitive", not punitive, punitive)
    visual_terms = find_terms(source_text, VISUAL_REGRESSION_TERMS)
    add_check(checks, "no_gold_bronze_amber_visual_regression", not visual_terms, visual_terms)

    typecheck = run_command(["npm", "run", "typecheck"], FRONTEND, timeout=240)
    command_results.append(typecheck)
    add_check(checks, "npm_run_typecheck_passes", typecheck["passed"], typecheck["output"][-1000:])

    build = run_command(["npm", "run", "build"], FRONTEND, timeout=300)
    command_results.append(build)
    add_check(checks, "npm_run_build_passes", build["passed"], build["output"][-1200:])

    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"

    public_report = {
        "version": "0.72.1",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "Product Value Clarity + Site Utility Rewrite",
        "result": result,
        "checks_passed": passed,
        "checks_total": total,
        "public_safe": True,
        "boundary": BOUNDARY,
        "clarity_summary": {
            "product_explanation": "PRMR Memory Core is plug-in continuity infrastructure for AI systems and organisations.",
            "integration_model": "API key, client ID, vault, namespace, event ingest, continuity packet, reconstructed state, reports, and dashboard visibility.",
            "context_efficiency_boundary": "PRMR can make limited context feel wider with smaller continuity packets, but does not increase a model's official context window.",
            "key_line": "Storage remembers data. PRMR remembers change.",
        },
    }
    private_report = {
        **public_report,
        "public_safe": False,
        "checks": checks,
        "command_results": command_results,
        "files_scanned": sorted(by_file.keys()),
        "private_note": "Detailed audit evidence for V0.72.1 copy clarity. No hidden product/security certification claim is added by this report.",
    }

    write_json(PUBLIC_REPORT, public_report)
    write_json(PRIVATE_REPORT, private_report)
    SCORECARD.write_text(build_scorecard(checks, command_results), encoding="utf-8")

    print("PRMR Memory Core V0.72.1 Product Value Clarity Audit")
    for result_item in command_results:
        print(f"{'PASS' if result_item['passed'] else 'FAIL'}: {result_item['command']}")
    print(f"Passed checks: {passed}/{total}")
    print(f"Result: {result}")
    if result != "PASS":
        failing = [check for check in checks if not check["passed"]]
        print(json.dumps(failing, indent=2, sort_keys=True))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
