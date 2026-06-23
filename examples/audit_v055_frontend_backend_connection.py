import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from prmr.product.alpha_api_sandbox_v0521 import (
    contains_raw_sandbox_key,
    scan_public_forbidden_terms,
    scan_unsafe_public_language,
)
from prmr.product.frontend_demo_bridge_v055 import available_scenarios, run_frontend_demo


VERSION = "0.55"
ROOT = Path(".")
FRONTEND_DIR = ROOT / "frontend"
REPORT_DIR = ROOT / "reports/v055"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

PUBLIC_PATH = REPORT_DIR / "public_frontend_backend_connection_v055.json"
PRIVATE_PATH = REPORT_DIR / "private_internal_frontend_backend_connection_v055.json"
SCORECARD_PATH = REPORT_DIR / "scorecard_v055.md"

BOUNDARY = (
    "V0.55 is local frontend-to-demo-backend connection only. It is not hosted, not production-ready, "
    "not bank approved, not compliance approved, not legal approval, not external security certification, "
    "and not real-world validation."
)

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
    "external security certification",
    "security-certified",
    "real-world validation",
    "real world validation",
    "externally validated",
]

SECRET_SOURCE_TERMS = [
    "ALPHA_SANDBOX_KEYS",
    "prmr_v0521_alpha_seed_key",
    "prmr_v0521_beta_seed_key",
    "new_api_key",
    "raw_api_key",
]


def read_text(path):
    return path.read_text(encoding="utf-8")


def add_check(checks, name, public_name, passed, details=None):
    checks.append({
        "name": name,
        "public_name": public_name,
        "passed": bool(passed),
        "details": details or {},
    })


def run_command(command, cwd=ROOT):
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["NEXT_TELEMETRY_DISABLED"] = "1"
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        shell=True,
        env=env,
        check=False,
        encoding="utf-8",
        errors="replace",
    )


def source_files(paths):
    files = []
    for path in paths:
        if path.is_file():
            files.append(path)
        elif path.exists():
            files.extend(item for item in path.rglob("*") if item.is_file() and item.suffix in {".ts", ".tsx", ".md", ".py"})
    return files


def frontend_client_text():
    client_paths = [
        FRONTEND_DIR / "app/demo",
        FRONTEND_DIR / "components/demo",
        FRONTEND_DIR / "data",
    ]
    return "\n".join(read_text(path) for path in source_files(client_paths))


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
                "not hosted",
                "not claimed",
                "future",
            ])
            if not negated:
                unsafe.append(line.strip())
    return sorted(set(unsafe))


def public_checks(checks):
    return [{"name": check["public_name"], "passed": check["passed"]} for check in checks]


def response_shape_ok(response):
    required_top = [
        "status",
        "scenario_id",
        "scenario_name",
        "synthetic_only",
        "boundary",
        "events_summary",
        "continuity_packet",
        "reconstruction",
        "explanation",
        "least_harm_action",
        "report_preview",
        "denial_path",
    ]
    packet_required = ["current_state", "active_signals", "stale_signals", "evidence", "summary"]
    return (
        all(key in response for key in required_top)
        and all(key in response["continuity_packet"] for key in packet_required)
        and bool(response["reconstruction"].get("state"))
        and bool(response["explanation"].get("public_safe_summary"))
        and bool(response["least_harm_action"].get("label"))
        and response["report_preview"].get("owner_access") == "allowed"
        and response["denial_path"].get("wrong_key_denied") is True
        and response["denial_path"].get("cross_client_denied") is True
    )


def public_artifacts_are_clean(public_report, scorecard_text):
    payload = {"public_report": public_report, "scorecard": scorecard_text}
    return {
        "restricted_terms": scan_public_forbidden_terms(payload),
        "unsafe_terms": scan_unsafe_public_language(payload),
        "contains_seed_secret": contains_raw_sandbox_key(payload),
        "unsafe_claim_lines": unsafe_claim_lines(json.dumps(payload, sort_keys=True)),
    }


def build_public_report(checks, command_results, bridge_results):
    passed_count = sum(1 for check in checks if check["passed"])
    total_checks = len(checks)
    result = "PASS" if passed_count == total_checks else "NEEDS_WORK"
    return {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": VERSION,
        "report_type": "frontend_backend_connection",
        "timestamp": datetime.now().isoformat(),
        "result": result,
        "passed_checks": passed_count,
        "total_checks": total_checks,
        "all_checks_passed": passed_count == total_checks,
        "purpose": "Connect the local frontend demo page to a local server-side PRMR demo bridge using synthetic data only.",
        "architecture": [
            "Browser demo page calls Next.js local proxy route.",
            "Proxy route runs a local deterministic PRMR demo bridge.",
            "Bridge returns public-safe synthetic demo output only.",
            "Browser receives continuity packet, reconstruction, explanation, least-harm action, report preview, and denial outcome.",
            "Secret material and diagnostic traces stay server-side.",
        ],
        "scenarios": [item["scenario_name"] for item in bridge_results],
        "command_summary": {
            name: "PASS" if result_data["returncode"] == 0 else "NEEDS_WORK"
            for name, result_data in command_results.items()
        },
        "checks": public_checks(checks),
        "boundary": BOUNDARY,
        "remaining_gaps": [
            "Hosted backend service is future work.",
            "Production authentication and credential custody are future work.",
            "Rate limits, observability, deployment hardening, and external validation are future work.",
            "The current bridge is local child-process demo wiring only.",
        ],
    }


def build_scorecard(public_report):
    lines = [
        "# PRMR V0.55 Frontend Backend Connection",
        "",
        "Company: Afternum Industries  ",
        "Product: PRMR Memory Core  ",
        "Version: V0.55  ",
        "",
        "## Result",
        "",
        f"**{public_report['result']}**",
        "",
        f"Passed checks: **{public_report['passed_checks']}/{public_report['total_checks']}**",
        "",
        "## Architecture",
        "",
    ]
    for item in public_report["architecture"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Checks", ""])
    for check in public_report["checks"]:
        lines.append(f"- {check['name']}: {'PASS' if check['passed'] else 'FAIL'}")
    lines.extend(["", "## Boundary", "", public_report["boundary"], "", "## Remaining Gaps", ""])
    for gap in public_report["remaining_gaps"]:
        lines.append(f"- {gap}")
    return "\n".join(lines)


def main():
    checks = []

    route_scenarios = FRONTEND_DIR / "app/api/demo/scenarios/route.ts"
    route_run = FRONTEND_DIR / "app/api/demo/run/route.ts"
    route_report = FRONTEND_DIR / "app/api/demo/report/route.ts"
    route_health = FRONTEND_DIR / "app/api/demo/health/route.ts"
    local_bridge_route = FRONTEND_DIR / "app/api/demo/localBridge.ts"
    demo_runner = FRONTEND_DIR / "components/demo/LocalDemoRunner.tsx"
    demo_page = FRONTEND_DIR / "app/demo/page.tsx"
    docs_path = ROOT / "docs/frontend_backend_connection_v055.md"
    bridge_path = ROOT / "prmr/product/frontend_demo_bridge_v055.py"

    add_check(checks, "api_demo_scenarios_route_exists", "scenario proxy route exists", route_scenarios.exists())
    add_check(checks, "api_demo_run_route_exists", "run proxy route exists", route_run.exists())
    add_check(checks, "api_demo_report_route_exists", "report proxy route exists", route_report.exists())
    add_check(checks, "api_demo_health_route_exists", "health proxy route exists", route_health.exists())

    routes_text = "\n".join(read_text(path) for path in [route_scenarios, route_run, route_report, route_health, local_bridge_route] if path.exists())
    add_check(
        checks,
        "routes_are_server_side_node_proxy_routes",
        "server-side proxy routes use local bridge",
        'runtime = "nodejs"' in routes_text and "callLocalDemoBridge" in routes_text and "spawn(" in routes_text,
    )

    client_text = frontend_client_text()
    add_check(
        checks,
        "demo_page_calls_proxy_route_not_prmr_core_directly",
        "demo page calls proxy route only",
        '"/api/demo/run"' in read_text(demo_runner)
        and "prmr/product" not in client_text.lower()
        and "alpha_api_sandbox" not in client_text.lower(),
    )
    secret_hits = [term for term in SECRET_SOURCE_TERMS if term in client_text]
    add_check(
        checks,
        "browser_client_code_does_not_expose_api_keys",
        "browser code has no secret material",
        not secret_hits,
        {"secret_hits": secret_hits},
    )

    bridge_results = [run_frontend_demo(item["scenario_id"]) for item in available_scenarios()]
    add_check(
        checks,
        "all_bridge_responses_have_required_public_shape",
        "bridge responses have required public shape",
        all(response_shape_ok(response) for response in bridge_results),
    )
    bridge_hygiene = {
        "restricted_terms": sorted(set(term for response in bridge_results for term in scan_public_forbidden_terms(response))),
        "unsafe_terms": sorted(set(term for response in bridge_results for term in scan_unsafe_public_language(response))),
        "contains_seed_secret": any(contains_raw_sandbox_key(response) for response in bridge_results),
    }
    add_check(
        checks,
        "demo_response_is_public_safe",
        "demo response is public-safe",
        not bridge_hygiene["restricted_terms"] and not bridge_hygiene["unsafe_terms"] and not bridge_hygiene["contains_seed_secret"],
        bridge_hygiene,
    )
    add_check(
        checks,
        "synthetic_only_boundary_present",
        "synthetic boundary present",
        all(response.get("synthetic_only") is True and "Synthetic data only" in response.get("boundary", "") for response in bridge_results),
    )

    page_text = read_text(demo_page) + read_text(demo_runner)
    required_ui_terms = [
        "Run Local Demo",
        "isLoading",
        "error",
        "ContinuityPacketCard",
        "ReconstructionCard",
        "ExplanationCard",
        "LeastHarmActionCard",
        "ReportPreviewCard",
        "DenialPathCard",
    ]
    missing_ui = [term for term in required_ui_terms if term not in page_text]
    add_check(checks, "demo_page_has_required_interactive_states_and_cards", "demo page has required states and cards", not missing_ui, {"missing_ui": missing_ui})

    doc_text = read_text(docs_path) if docs_path.exists() else ""
    readme_text = read_text(FRONTEND_DIR / "README.md") if (FRONTEND_DIR / "README.md").exists() else ""
    add_check(
        checks,
        "v055_docs_exist_and_state_local_boundary",
        "V0.55 docs state local boundary",
        docs_path.exists()
        and "local-only demo connection" in (doc_text + readme_text).lower()
        and "browser code never receives raw keys" in doc_text.lower()
        and "not a production backend pattern" in readme_text.lower(),
    )

    all_frontend_text = "\n".join(read_text(path) for path in source_files([FRONTEND_DIR / "app", FRONTEND_DIR / "components", FRONTEND_DIR / "data", FRONTEND_DIR / "README.md"]))
    claim_hits = unsafe_claim_lines(all_frontend_text + "\n" + doc_text)
    add_check(checks, "no_unqualified_hosted_production_or_certification_claims", "no unqualified production or approval claims", not claim_hits, {"claim_hits": claim_hits[:20]})

    command_results = {}
    commands = {
        "v0522_integrity_audit": ("python examples/audit_v0522_alpha_api_sandbox_integrity.py", ROOT),
        "v0531_replay_pack": ("python examples/demo_v0531_replay_pack.py", ROOT),
        "frontend_typecheck": ("npm run typecheck", FRONTEND_DIR),
        "frontend_build": ("npm run build", FRONTEND_DIR),
    }
    for name, (command, cwd) in commands.items():
        completed = run_command(command, cwd)
        command_results[name] = {
            "command": command,
            "returncode": completed.returncode,
            "stdout_tail": completed.stdout.splitlines()[-30:],
            "stderr_tail": completed.stderr.splitlines()[-30:],
        }
        public_name = {
            "v0522_integrity_audit": "V0.52.2 integrity audit still passes",
            "v0531_replay_pack": "V0.53.1 replay pack still passes",
            "frontend_typecheck": "frontend typecheck passes",
            "frontend_build": "frontend build passes",
        }[name]
        add_check(checks, name, public_name, completed.returncode == 0, command_results[name])

    add_check(
        checks,
        "bridge_file_exists_and_uses_v0521_v0531_sources",
        "bridge uses prior local evidence sources",
        bridge_path.exists()
        and "PRMRAlphaAPISandbox" in read_text(bridge_path)
        and "fixture_scenarios" in read_text(bridge_path),
    )

    public_report = build_public_report(checks, command_results, bridge_results)
    scorecard_text = build_scorecard(public_report)
    clean = public_artifacts_are_clean(public_report, scorecard_text)
    add_check(
        checks,
        "public_report_and_scorecard_are_claim_safe",
        "public artifacts are claim-safe",
        not clean["restricted_terms"] and not clean["unsafe_terms"] and not clean["contains_seed_secret"] and not clean["unsafe_claim_lines"],
        clean,
    )

    public_report = build_public_report(checks, command_results, bridge_results)
    scorecard_text = build_scorecard(public_report)
    final_clean = public_artifacts_are_clean(public_report, scorecard_text)
    if final_clean["restricted_terms"] or final_clean["unsafe_terms"] or final_clean["contains_seed_secret"] or final_clean["unsafe_claim_lines"]:
        add_check(checks, "final_public_artifact_hygiene_holds", "final public artifact hygiene holds", False, final_clean)
        public_report = build_public_report(checks, command_results, bridge_results)
        scorecard_text = build_scorecard(public_report)

    private_report = {
        **public_report,
        "public_safe": False,
        "checks": checks,
        "bridge_results": bridge_results,
        "command_results": command_results,
        "implementation_files": [
            str(route_scenarios),
            str(route_run),
            str(route_report),
            str(route_health),
            str(local_bridge_route),
            str(demo_runner),
            str(bridge_path),
            str(docs_path),
        ],
    }

    PUBLIC_PATH.write_text(json.dumps(public_report, indent=4), encoding="utf-8")
    PRIVATE_PATH.write_text(json.dumps(private_report, indent=4), encoding="utf-8")
    SCORECARD_PATH.write_text(scorecard_text, encoding="utf-8")

    print("PRMR V0.55 FRONTEND BACKEND CONNECTION AUDIT")
    print("--------------------------------------------")
    print(f"Passed checks: {public_report['passed_checks']}/{public_report['total_checks']}")
    print("Result:", public_report["result"])
    print()
    print("Command summary:")
    for name, result in command_results.items():
        print(f"- {name}: {'PASS' if result['returncode'] == 0 else 'NEEDS_WORK'}")
    print()
    print("Created:")
    print(PUBLIC_PATH)
    print(PRIVATE_PATH)
    print(SCORECARD_PATH)

    if public_report["result"] != "PASS":
        sys.exit(1)


if __name__ == "__main__":
    main()
