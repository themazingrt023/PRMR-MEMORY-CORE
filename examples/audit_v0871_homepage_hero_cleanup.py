"""Audit V0.87.1 homepage hero cleanup."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REPORT_DIR = ROOT / "reports" / "v0871"
PUBLIC_REPORT = REPORT_DIR / "public_homepage_hero_cleanup_v0871.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_homepage_hero_cleanup_v0871.json"
SMOKE_REPORT = REPORT_DIR / "homepage_hero_cleanup_smoke_v0871.json"
SCORECARD = REPORT_DIR / "scorecard_v0871.md"

V087_PUBLIC = ROOT / "reports" / "v087" / "public_commercial_alpha_site_v087.json"
RUNNER_PATH = ROOT / "examples" / "run_homepage_hero_cleanup_v0871.py"

COPY_FILE = FRONTEND / "data" / "commercialAlphaCopy.ts"
NAV_FILE = FRONTEND / "components" / "landing" / "Navigation.tsx"
HERO_FILE = FRONTEND / "components" / "landing" / "HeroSection.tsx"
LEVERAGE_FILE = FRONTEND / "components" / "landing" / "InfrastructureLeverageSection.tsx"
HOME_PAGE = FRONTEND / "app" / "page.tsx"
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


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


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


def frontend_text() -> str:
    files = [COPY_FILE, NAV_FILE, HERO_FILE, LEVERAGE_FILE, HOME_PAGE, MARKET_PAGE, PILOT_PAGE]
    files.extend((FRONTEND / "components" / "landing").glob("*.tsx"))
    return "\n".join(read_text(path) for path in files)


def run_frontend_command(command: str) -> dict[str, Any]:
    npm = "npm.cmd" if os.name == "nt" else "npm"
    completed = subprocess.run(
        [npm, "run", command],
        cwd=FRONTEND,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=300,
        check=False,
    )
    output = (completed.stdout or "").strip()
    return {
        "command": f"npm run {command}",
        "returncode": completed.returncode,
        "passed": completed.returncode == 0,
        "output_tail": output[-4000:],
    }


def load_runner_module():
    spec = importlib.util.spec_from_file_location("run_homepage_hero_cleanup_v0871", RUNNER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load V0.87.1 homepage cleanup runner.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def build_public_report(
    checks: list[dict[str, Any]],
    runner_public: dict[str, Any],
    typecheck_result: dict[str, Any],
    build_result: dict[str, Any],
) -> dict[str, Any]:
    failures = [check for check in checks if not check["passed"]]
    return {
        "version": "0.87.1",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "Homepage Hero Cleanup Audit",
        "result": "PASS" if not failures else "NEEDS_WORK",
        "runner_result": runner_public.get("result"),
        "checks_passed": sum(1 for check in checks if check["passed"]),
        "checks_total": len(checks),
        "public_safe": True,
        "boundary": BOUNDARY_V0871,
        "hero_before": OLD_HERO,
        "hero_after": runner_public.get("hero_after"),
        "nav_after": runner_public.get("nav_after"),
        "infrastructure_leverage_section": runner_public.get("infrastructure_leverage_section"),
        "proof_handling": runner_public.get("proof_handling"),
        "frontend_commands": {
            "typecheck": {"command": typecheck_result["command"], "passed": typecheck_result["passed"]},
            "build": {"command": build_result["command"], "passed": build_result["passed"]},
        },
    }


def build_private_report(
    public_report: dict[str, Any],
    checks: list[dict[str, Any]],
    runner_public: dict[str, Any],
    typecheck_result: dict[str, Any],
    build_result: dict[str, Any],
) -> dict[str, Any]:
    return {
        **public_report,
        "public_safe": False,
        "checks": checks,
        "runner_public_summary": runner_public,
        "typecheck_output_tail": typecheck_result["output_tail"],
        "build_output_tail": build_result["output_tail"],
        "restricted_note": "No raw keys, private reports, or protected core internals are included.",
    }


def build_scorecard(public_report: dict[str, Any], checks: list[dict[str, Any]]) -> str:
    lines = [
        "# V0.87.1 Homepage Hero Cleanup Audit",
        "",
        f"Result: {public_report['result']}",
        f"Runner result: {public_report['runner_result']}",
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


def run_audit() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    v087 = read_json(V087_PUBLIC)
    text = frontend_text()
    copy = read_text(COPY_FILE)
    nav = read_text(NAV_FILE)
    hero = read_text(HERO_FILE)
    home = read_text(HOME_PAGE)

    add_check(checks, "v087_evidence_exists", V087_PUBLIC.exists(), V087_PUBLIC.as_posix())
    add_check(checks, "v087_commercial_alpha_site_passed", v087.get("result") == "PASS", v087.get("result"))
    add_check(checks, "homepage_hero_updated", "Infrastructure for evolving memory." in copy and "viewPilot" in hero, None)
    add_check(checks, "old_long_hero_headline_removed_or_demoted", OLD_HERO not in hero and OLD_HERO not in copy, None)
    add_check(checks, "infrastructure_prints_leverage_section_exists", LEVERAGE_FILE.exists() and "Infrastructure prints leverage." in copy and "InfrastructureLeverageSection" in home, None)
    add_check(checks, "public_proof_removed_from_top_nav", "Public Proof" not in nav, None)
    add_check(checks, "market_pilot_routes_preserved", MARKET_PAGE.exists() and PILOT_PAGE.exists(), None)
    add_check(checks, "request_alpha_and_book_demo_ctas_preserved", "requestAlpha" in hero and "bookDemo" in hero, None)
    add_check(checks, "no_secret_exposure", not secret_hits(text), secret_hits(text))
    add_check(checks, "no_unsafe_claims", not unsafe_claim_hits(text), unsafe_claim_hits(text))

    runner = load_runner_module()
    runner_public, runner_private, smoke_report, runner_checks = runner.run_smoke()
    runner.write_json(runner.PUBLIC_REPORT, runner_public)
    runner.write_json(runner.PRIVATE_REPORT, runner_private)
    runner.write_json(runner.SMOKE_REPORT, smoke_report)
    runner.SCORECARD.write_text(runner.build_scorecard(runner_public, runner_checks), encoding="utf-8")
    add_check(checks, "runner_result_passed", runner_public.get("result") == "PASS", runner_public.get("result"))

    print("Running frontend typecheck...")
    typecheck_result = run_frontend_command("typecheck")
    add_check(checks, "frontend_typecheck_passes", typecheck_result["passed"], typecheck_result["output_tail"][-800:] or "ok")

    print("Running frontend build...")
    build_result = run_frontend_command("build")
    add_check(checks, "frontend_build_passes", build_result["passed"], build_result["output_tail"][-800:] or "ok")

    public_report = build_public_report(checks, runner_public, typecheck_result, build_result)
    add_check(checks, "public_report_contains_no_secrets", not secret_hits(json.dumps(public_report, sort_keys=True)), None)
    add_check(checks, "public_report_has_no_unsafe_claims", not unsafe_claim_hits(json.dumps(public_report, sort_keys=True)), unsafe_claim_hits(json.dumps(public_report, sort_keys=True)))

    public_report = build_public_report(checks, runner_public, typecheck_result, build_result)
    private_report = build_private_report(public_report, checks, runner_public, typecheck_result, build_result)
    return public_report, private_report, smoke_report, checks


def main() -> int:
    public_report, private_report, smoke_report, checks = run_audit()
    write_json(PUBLIC_REPORT, public_report)
    write_json(PRIVATE_REPORT, private_report)
    write_json(SMOKE_REPORT, smoke_report)
    SCORECARD.write_text(build_scorecard(public_report, checks), encoding="utf-8")

    print("PRMR Memory Core V0.87.1 Homepage Hero Cleanup Audit")
    print(f"Runner result: {public_report.get('runner_result')}")
    print(f"Hero headline: {public_report.get('hero_after', {}).get('headline')}")
    print(f"Public report: {PUBLIC_REPORT.as_posix()}")
    print(f"Private report: {PRIVATE_REPORT.as_posix()}")
    print(f"Smoke report: {SMOKE_REPORT.as_posix()}")
    print(f"Scorecard: {SCORECARD.as_posix()}")
    print(f"Passed checks: {public_report.get('checks_passed')}/{public_report.get('checks_total')}")
    print(f"Result: {public_report.get('result')}")
    return 0 if public_report.get("result") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
