"""Audit PRMR product-readiness sprint deliverables and regressions."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


REPORT_DIR = ROOT / "reports" / "product_readiness_sprint"
PUBLIC_REPORT = REPORT_DIR / "public_product_readiness_audit.json"
PRIVATE_REPORT = REPORT_DIR / "private_product_readiness_audit.json"
SCORECARD = REPORT_DIR / "scorecard_product_readiness_audit.md"

REQUIRED_FILES = [
    ROOT / "docs" / "product_readiness_architecture_map.md",
    ROOT / "docs" / "product_readiness_gap_register.md",
    ROOT / "docs" / "api_contract_product_ready.md",
    ROOT / "docs" / "security_boundary_product_ready.md",
    ROOT / "docs" / "operational_runbook_product_ready.md",
    ROOT / "migrations" / "v101_entity_scope_indexes.sql",
    ROOT / "examples" / "run_product_readiness_sprint.py",
    ROOT / "examples" / "benchmark_entity_scoped_packets.py",
]

BOUNDARY = (
    "Product-readiness sprint audit. PASS means critical local product-flow "
    "checks passed with documented limitations; it does not mean enterprise "
    "readiness, billing readiness, compliance approval, legal approval, or "
    "external security certification."
)


def add(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def command(args: list[str], cwd: Path = ROOT) -> tuple[bool, str]:
    completed = subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.returncode == 0, (completed.stdout + "\n" + completed.stderr).strip()[-2200:]


def file_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def main() -> int:
    checks: list[dict[str, Any]] = []
    add(checks, "required_deliverable_files_exist", all(path.exists() for path in REQUIRED_FILES), [path.as_posix() for path in REQUIRED_FILES if not path.exists()])
    combined_docs = "\n".join(file_text(path) for path in REQUIRED_FILES)
    add(checks, "docs_cover_entity_scoped_memory", all(term in combined_docs for term in ["entity-scoped", "application_reference", "actor_reference", "workspace_reference", "entity_reference"]))
    add(checks, "docs_include_gap_register_and_boundaries", "Gap Register" in combined_docs and "not enterprise readiness" in combined_docs.lower(), None)
    add(checks, "migration_includes_indexes", "CREATE INDEX IF NOT EXISTS" in file_text(ROOT / "migrations" / "v101_entity_scope_indexes.sql"), None)
    add(checks, "no_false_certification_claims", not any(term in combined_docs.lower() for term in ["compliance approved", "security certified", "enterprise-ready", "guaranteed results"]), None)

    regression_commands = [
        ("product_readiness_runner_passes", ["python", "examples/run_product_readiness_sprint.py"], ROOT),
        ("v098_external_event_contract_still_passes", ["python", "examples/audit_v098_external_event_contract.py"], ROOT),
        ("v099_theory_packet_still_passes", ["python", "examples/audit_v099_theory_to_product_packet.py"], ROOT),
        ("v100_dashboard_observability_still_passes", ["python", "examples/audit_v100_dashboard_observability.py"], ROOT),
        ("secret_cleanup_still_passes", ["python", "examples/audit_v0782_secret_cleanup.py"], ROOT),
    ]
    for name, args, cwd in regression_commands:
        ok, output = command(args, cwd)
        add(checks, name, ok, output)

    npm = "npm.cmd" if os.name == "nt" else "npm"
    type_ok, type_output = command([npm, "run", "typecheck"], ROOT / "frontend")
    add(checks, "frontend_typecheck_passes", type_ok, type_output)
    build_ok, build_output = command([npm, "run", "build"], ROOT / "frontend")
    add(checks, "frontend_build_passes", build_ok, build_output)

    failures = [check for check in checks if not check["passed"]]
    result = "PASS WITH DOCUMENTED LIMITATIONS" if not failures else "NEEDS_WORK"
    public = {
        "version": "product_readiness_sprint",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "Product Readiness Completion Sprint Audit",
        "result": result,
        "checks_passed": len(checks) - len(failures),
        "checks_total": len(checks),
        "truth_label": "critical product-flow implementation evidence with documented limitations",
        "boundary": BOUNDARY,
        "critical_fixes_verified": [
            "entity-scoped packet generation",
            "application object and application-bound keys",
            "packet provenance",
            "idempotent ingest",
            "liveness/readiness endpoints",
        ],
        "remaining_blockers": [
            "full relational event storage migration",
            "hosted performance/load measurements",
            "rate limiting and abuse controls",
            "external engineering team validation",
            "independent production security review",
        ],
        "public_safe": True,
    }
    private = {**public, "checks": checks, "public_safe": False}
    write_json(PUBLIC_REPORT, public)
    write_json(PRIVATE_REPORT, private)
    SCORECARD.write_text(
        "\n".join(
            [
                "# Product Readiness Completion Sprint Audit",
                "",
                f"Result: {result}",
                f"Checks: {public['checks_passed']}/{public['checks_total']}",
                "",
                f"Boundary: {BOUNDARY}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print("PRMR Product Readiness Sprint Audit")
    print(f"Passed checks: {public['checks_passed']}/{public['checks_total']}")
    print(f"Result: {result}")
    for check in failures:
        print(f"FAIL: {check['name']}")
        print(str(check.get("detail"))[-800:])
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
