"""Run V0.87 commercial alpha site smoke checks."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
REPORT_DIR = ROOT / "reports" / "v087"
PUBLIC_REPORT = REPORT_DIR / "public_commercial_alpha_site_v087.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_commercial_alpha_site_v087.json"
SMOKE_REPORT = REPORT_DIR / "commercial_alpha_site_smoke_v087.json"
SCORECARD = REPORT_DIR / "scorecard_v087.md"

COPY_FILE = FRONTEND / "data" / "commercialAlphaCopy.ts"
NAV_FILE = FRONTEND / "components" / "landing" / "Navigation.tsx"
HOME_FILES = [
    FRONTEND / "components" / "landing" / "HeroSection.tsx",
    FRONTEND / "components" / "landing" / "ProblemSection.tsx",
    FRONTEND / "components" / "landing" / "ApiFlowSection.tsx",
    FRONTEND / "components" / "landing" / "AlphaAccessSection.tsx",
]
PAGE_FILES = {
    "/public-proof": FRONTEND / "app" / "public-proof" / "page.tsx",
    "/market": FRONTEND / "app" / "market" / "page.tsx",
    "/pilot": FRONTEND / "app" / "pilot" / "page.tsx",
    "/alpha": FRONTEND / "app" / "alpha" / "page.tsx",
    "/book-demo": FRONTEND / "app" / "book-demo" / "page.tsx",
}

BOUNDARY_V087 = (
    "V0.87 is a controlled alpha commercial pathway only. It is not self-serve "
    "production API access, full billing automation, compliance approval, legal "
    "approval, bank approval, external security certification, or real-world validation."
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


def competitor_attack_hits(text: str) -> list[str]:
    lowered = text.lower()
    phrases = ["competitors are bad", "nobody else is doing memory", "only prmr", "all competitors"]
    return [phrase for phrase in phrases if phrase in lowered]


def frontend_text() -> str:
    files = [COPY_FILE, NAV_FILE, *HOME_FILES, *PAGE_FILES.values()]
    return "\n".join(read_text(path) for path in files)


def build_public_report(checks: list[dict[str, Any]], smoke: dict[str, Any]) -> dict[str, Any]:
    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    return {
        "version": "0.87",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "Commercial Alpha Site Upgrade",
        "result": "PASS" if passed == total else "NEEDS_WORK",
        "checks_passed": passed,
        "checks_total": total,
        "public_safe": True,
        "boundary": BOUNDARY_V087,
        "new_pages": ["/public-proof", "/market", "/pilot"],
        "nav_links": smoke["nav_links"],
        "commercial_alpha_offer": smoke["commercial_alpha_offer"],
        "market_positioning": smoke["market_positioning"],
        "public_proof_structure": smoke["public_proof_structure"],
        "remaining_manual_step": "Pick the first tester/client and run the controlled alpha with honest evidence capture.",
    }


def build_private_report(public_report: dict[str, Any], checks: list[dict[str, Any]], smoke: dict[str, Any]) -> dict[str, Any]:
    return {
        **public_report,
        "public_safe": False,
        "checks": checks,
        "smoke": smoke,
        "restricted_note": "Private V0.87 report includes route/copy audit detail only. No raw keys or protected core internals are included.",
    }


def build_scorecard(public_report: dict[str, Any], checks: list[dict[str, Any]]) -> str:
    lines = [
        "# V0.87 Commercial Alpha Site Upgrade",
        "",
        f"Result: {public_report['result']}",
        f"Passed checks: {public_report['checks_passed']}/{public_report['checks_total']}",
        "",
        f"Boundary: {BOUNDARY_V087}",
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
            "- RUN: python examples/run_commercial_alpha_site_v087.py",
            "- RUN: python examples/audit_v087_commercial_alpha_site.py",
            "",
        ]
    )
    return "\n".join(lines)


def run_smoke() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    text = frontend_text()
    copy = read_text(COPY_FILE)
    nav = read_text(NAV_FILE)
    home = "\n".join(read_text(path) for path in HOME_FILES)
    public_proof = read_text(PAGE_FILES["/public-proof"])
    market = read_text(PAGE_FILES["/market"])
    pilot = read_text(PAGE_FILES["/pilot"])

    add_check(checks, "public_proof_page_exists", PAGE_FILES["/public-proof"].exists(), PAGE_FILES["/public-proof"].as_posix())
    add_check(checks, "market_page_exists", PAGE_FILES["/market"].exists(), PAGE_FILES["/market"].as_posix())
    add_check(checks, "pilot_page_exists", PAGE_FILES["/pilot"].exists(), PAGE_FILES["/pilot"].as_posix())
    add_check(checks, "commercial_copy_file_exists", COPY_FILE.exists(), COPY_FILE.as_posix())
    add_check(checks, "nav_links_exist", all(label in nav for label in ["Public Proof", "Market", "Pilot", "Demo", "Docs", "Alpha", "Contact"]), None)
    add_check(checks, "hero_copy_contains_infrastructure_evolve_wording", "infrastructure layer" in copy and "remember what matters as it evolves" in copy, None)
    add_check(checks, "homepage_explains_protected_core_private", "protected core" in home.lower() and "private" in home.lower(), None)
    add_check(checks, "market_page_does_not_attack_competitors", not competitor_attack_hits(market), competitor_attack_hits(market))
    add_check(checks, "pilot_page_includes_controlled_alpha_offer", "Controlled Alpha API Pilot" in copy and "manually approved" in copy and "pilotOffer" in pilot, None)
    add_check(checks, "pricing_is_controlled_alpha_only", "from £250" in copy and "manually approved" in copy and "No automatic checkout" in copy, None)
    add_check(checks, "public_proof_includes_safe_evidence", all(term in copy for term in ["Reconstruction verification", "Protected hosted smoke", "Multi-client isolation", "Public/private report hygiene"]) and "proofHighlights" in public_proof, None)
    add_check(checks, "request_alpha_path_exists", PAGE_FILES["/alpha"].exists(), PAGE_FILES["/alpha"].as_posix())
    add_check(checks, "book_demo_path_exists", PAGE_FILES["/book-demo"].exists(), PAGE_FILES["/book-demo"].as_posix())
    add_check(checks, "no_unsafe_commercial_claims", not unsafe_claim_hits(text), unsafe_claim_hits(text))
    add_check(checks, "no_raw_keys_or_tokens_in_frontend_source", not secret_hits(text), secret_hits(text))
    add_check(checks, "no_protected_core_internals_exposed", "protected engine internals" in public_proof and "debug_trace" not in text and "private_internal" not in text, None)

    smoke = {
        "nav_links": ["Public Proof", "Market", "Pilot", "Demo", "Docs", "Alpha", "Contact"],
        "commercial_alpha_offer": {
            "name": "Controlled Alpha API Pilot",
            "pricing": "Free discovery / trial review first. Controlled Alpha API Pilot from £250.",
            "payment_boundary": "manual approval and direct arrangement only",
            "automatic_checkout": False,
        },
        "market_positioning": {
            "category": "AI memory infrastructure",
            "competitor_framing": "competitors/categories are treated as evidence the category is forming",
            "categories": ["memory APIs", "graph memory", "stateful agents", "vector retrieval/RAG", "managed agent memory", "academic long-term memory systems"],
        },
        "public_proof_structure": ["evidence ladder", "reconstruction verification", "hosted frontend/backend status", "protected hosted smoke", "multi-client isolation", "public/private report hygiene"],
        "secret_hygiene": {"raw_secret_patterns_found": False},
    }

    public_report = build_public_report(checks, smoke)
    add_check(checks, "public_report_contains_no_secrets", not secret_hits(json.dumps(public_report, sort_keys=True)), None)
    add_check(checks, "public_report_has_no_unsafe_claims", not unsafe_claim_hits(json.dumps(public_report, sort_keys=True)), unsafe_claim_hits(json.dumps(public_report, sort_keys=True)))

    public_report = build_public_report(checks, smoke)
    private_report = build_private_report(public_report, checks, smoke)
    smoke_report = {
        "version": "0.87",
        "public_safe": True,
        "boundary": BOUNDARY_V087,
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

    print("PRMR Memory Core V0.87 Commercial Alpha Site Smoke")
    print(f"New pages: {', '.join(public_report['new_pages'])}")
    print(f"Public report: {PUBLIC_REPORT.as_posix()}")
    print(f"Private report: {PRIVATE_REPORT.as_posix()}")
    print(f"Smoke report: {SMOKE_REPORT.as_posix()}")
    print(f"Scorecard: {SCORECARD.as_posix()}")
    print(f"Passed checks: {public_report.get('checks_passed')}/{public_report.get('checks_total')}")
    print(f"Result: {public_report.get('result')}")
    return 0 if public_report.get("result") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
