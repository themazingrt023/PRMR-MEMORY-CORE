"""Run V0.87.1 homepage hero cleanup smoke checks."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
REPORT_DIR = ROOT / "reports" / "v0871"
PUBLIC_REPORT = REPORT_DIR / "public_homepage_hero_cleanup_v0871.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_homepage_hero_cleanup_v0871.json"
SMOKE_REPORT = REPORT_DIR / "homepage_hero_cleanup_smoke_v0871.json"
SCORECARD = REPORT_DIR / "scorecard_v0871.md"

COPY_FILE = FRONTEND / "data" / "commercialAlphaCopy.ts"
NAV_FILE = FRONTEND / "components" / "landing" / "Navigation.tsx"
HERO_FILE = FRONTEND / "components" / "landing" / "HeroSection.tsx"
LEVERAGE_FILE = FRONTEND / "components" / "landing" / "InfrastructureLeverageSection.tsx"
HOME_PAGE = FRONTEND / "app" / "page.tsx"
PUBLIC_PROOF_PAGE = FRONTEND / "app" / "public-proof" / "page.tsx"
MARKET_PAGE = FRONTEND / "app" / "market" / "page.tsx"
PILOT_PAGE = FRONTEND / "app" / "pilot" / "page.tsx"

OLD_HERO = "PRMR Memory Core is an infrastructure layer that plugs into your system and helps it remember what matters as it evolves."
BOUNDARY_V0871 = (
    "V0.87.1 is homepage hero compression and proof navigation cleanup only. "
    "It does not claim production readiness, billing automation, compliance "
    "approval, legal approval, bank approval, external security certification, "
    "or real-world validation."
)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def secret_hits(text: str) -> list[str]:
    patterns = [
        r"\bsk-[A-Za-z0-9_\-]{16,}\b",
        r"\bghp_[A-Za-z0-9]{20,}\b",
        r"\bgithub_pat_[A-Za-z0-9_]{20,}\b",
        r"Authorization:\s*Bearer\s+(?!<PRMR_API_KEY>)[A-Za-z0-9_\-.]{12,}",
        r"prmr_alpha_dev_[a-f0-9]{16,}",
        r"dash_v08[0-9]_[a-f0-9]{16,}",
    ]
    return [pattern for pattern in patterns if re.search(pattern, text, re.IGNORECASE)]


def unsafe_claim_hits(text: str) -> list[str]:
    lowered = text.lower()
    phrases = [
        "production-ready",
        "production ready",
        "compliance-ready",
        "compliance ready",
        "certified product",
        "bank-approved",
        "bank approved",
        "guaranteed",
        "billing enabled",
        "external validation complete",
        "real-world validated",
    ]
    return [phrase for phrase in phrases if phrase in lowered]


def source_text() -> str:
    files = [
        COPY_FILE,
        NAV_FILE,
        HERO_FILE,
        LEVERAGE_FILE,
        HOME_PAGE,
        PUBLIC_PROOF_PAGE,
        MARKET_PAGE,
        PILOT_PAGE,
    ]
    return "\n".join(read_text(path) for path in files)


def build_public_report(checks: list[dict[str, Any]], smoke: dict[str, Any]) -> dict[str, Any]:
    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    return {
        "version": "0.87.1",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "Homepage Hero Cleanup",
        "result": "PASS" if passed == total else "NEEDS_WORK",
        "checks_passed": passed,
        "checks_total": total,
        "public_safe": True,
        "boundary": BOUNDARY_V0871,
        "hero_before": OLD_HERO,
        "hero_after": smoke["hero_after"],
        "nav_after": smoke["nav_after"],
        "infrastructure_leverage_section": smoke["infrastructure_leverage_section"],
        "proof_handling": smoke["proof_handling"],
    }


def build_private_report(public_report: dict[str, Any], checks: list[dict[str, Any]], smoke: dict[str, Any]) -> dict[str, Any]:
    return {
        **public_report,
        "public_safe": False,
        "checks": checks,
        "smoke": smoke,
        "restricted_note": "Private report contains copy/navigation smoke details only. No secrets or protected core internals are included.",
    }


def build_scorecard(public_report: dict[str, Any], checks: list[dict[str, Any]]) -> str:
    lines = [
        "# V0.87.1 Homepage Hero Cleanup",
        "",
        f"Result: {public_report['result']}",
        f"Passed checks: {public_report['checks_passed']}/{public_report['checks_total']}",
        "",
        f"Boundary: {BOUNDARY_V0871}",
        "",
        "## Checks",
        "",
    ]
    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        lines.append(f"- {status}: {check['name']}")
    lines.extend(
        [
            "",
            "## Commands",
            "",
            "- RUN: npm run build",
            "- RUN: npm run typecheck",
            "- RUN: python examples/run_homepage_hero_cleanup_v0871.py",
            "- RUN: python examples/audit_v0871_homepage_hero_cleanup.py",
            "",
        ]
    )
    return "\n".join(lines)


def run_smoke() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    text = source_text()
    copy = read_text(COPY_FILE)
    nav = read_text(NAV_FILE)
    hero = read_text(HERO_FILE)
    leverage = read_text(LEVERAGE_FILE)
    home = read_text(HOME_PAGE)
    proof = read_text(PUBLIC_PROOF_PAGE)

    add_check(checks, "hero_contains_new_headline", "Infrastructure for evolving memory." in copy, None)
    add_check(checks, "hero_does_not_use_old_oversized_headline", OLD_HERO not in hero and OLD_HERO not in copy, None)
    add_check(checks, "hero_contains_core_gap_line", "Storage remembers data. Retrieval finds data. PRMR preserves continuity." in copy, None)
    add_check(checks, "hero_ctas_updated", all(term in hero for term in ["requestAlpha", "bookDemo", "viewPilot"]) and "viewProof" not in hero, None)
    add_check(checks, "homepage_contains_infrastructure_prints_leverage", "Infrastructure prints leverage." in copy and "InfrastructureLeverageSection" in home, None)
    add_check(checks, "nav_does_not_contain_public_proof", "Public Proof" not in nav, None)
    add_check(checks, "nav_still_contains_required_links", all(label in nav for label in ["Market", "Pilot", "Demo", "Docs", "Alpha", "Contact"]), None)
    add_check(checks, "market_and_pilot_routes_preserved", MARKET_PAGE.exists() and PILOT_PAGE.exists(), None)
    add_check(checks, "proof_route_still_exists", PUBLIC_PROOF_PAGE.exists(), PUBLIC_PROOF_PAGE.as_posix())
    add_check(checks, "proof_route_content_has_no_secrets", not secret_hits(proof), secret_hits(proof))
    add_check(checks, "no_secret_exposure", not secret_hits(text), secret_hits(text))
    add_check(checks, "no_unsafe_claims", not unsafe_claim_hits(text), unsafe_claim_hits(text))
    add_check(checks, "no_gold_bronze_amber_reintroduced", not any(term in text.lower() for term in ["gold", "bronze", "amber"]), None)

    smoke = {
        "hero_after": {
            "headline": "Infrastructure for evolving memory.",
            "subheadline": "PRMR Memory Core plugs into your system and helps it remember what matters as it grows, changes, and learns.",
            "support": "A controlled-alpha API layer for AI products, agents, tools, games, workflows, and platforms that need memory, context, and state to survive over time.",
            "gap": "Storage remembers data. Retrieval finds data. PRMR preserves continuity.",
            "ctas": ["Request Alpha Access", "Book a Demo", "View Pilot"],
        },
        "nav_after": ["Problem", "Solution", "API", "Market", "Pilot", "Demo", "Docs", "Alpha", "Contact"],
        "infrastructure_leverage_section": {
            "title": "Why Infrastructure Matters",
            "main_line": "Infrastructure prints leverage.",
            "closing_lines": ["They build the app.", "PRMR preserves the continuity underneath."],
        },
        "proof_handling": {
            "public_proof_route_preserved": PUBLIC_PROOF_PAGE.exists(),
            "public_proof_removed_from_top_nav": "Public Proof" not in nav,
            "supporting_evidence_links": ["/pilot", "/market"],
        },
    }

    public_report = build_public_report(checks, smoke)
    add_check(checks, "public_report_contains_no_secrets", not secret_hits(json.dumps(public_report, sort_keys=True)), None)
    add_check(checks, "public_report_has_no_unsafe_claims", not unsafe_claim_hits(json.dumps(public_report, sort_keys=True)), unsafe_claim_hits(json.dumps(public_report, sort_keys=True)))

    public_report = build_public_report(checks, smoke)
    private_report = build_private_report(public_report, checks, smoke)
    smoke_report = {
        "version": "0.87.1",
        "public_safe": True,
        "boundary": BOUNDARY_V0871,
        "result": public_report["result"],
        "smoke": smoke,
    }
    return public_report, private_report, smoke_report, checks


def main() -> int:
    public_report, private_report, smoke_report, checks = run_smoke()
    write_json(PUBLIC_REPORT, public_report)
    write_json(PRIVATE_REPORT, private_report)
    write_json(SMOKE_REPORT, smoke_report)
    SCORECARD.write_text(build_scorecard(public_report, checks), encoding="utf-8")

    print("PRMR Memory Core V0.87.1 Homepage Hero Cleanup Smoke")
    print(f"Hero headline: {public_report['hero_after']['headline']}")
    print(f"Public report: {PUBLIC_REPORT.as_posix()}")
    print(f"Private report: {PRIVATE_REPORT.as_posix()}")
    print(f"Smoke report: {SMOKE_REPORT.as_posix()}")
    print(f"Scorecard: {SCORECARD.as_posix()}")
    print(f"Passed checks: {public_report.get('checks_passed')}/{public_report.get('checks_total')}")
    print(f"Result: {public_report.get('result')}")
    return 0 if public_report.get("result") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
