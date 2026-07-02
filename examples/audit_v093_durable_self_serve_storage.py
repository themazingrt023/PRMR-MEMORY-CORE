"""Audit V0.93 durable self-serve storage and restart evidence."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from examples.run_durable_self_serve_storage_v093 import (
    PRIVATE_REPORT,
    PUBLIC_REPORT,
    SCORECARD,
    SMOKE_REPORT,
    build_scorecard,
    contains_secret,
    run_smoke,
    write_json,
)
from prmr.product.durable_self_serve_storage_v093 import storage_status_v093
from prmr.product.self_serve_repository_v093 import TABLES


def add(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def has_unqualified_claim(text: str) -> bool:
    pattern = re.compile(
        r"\b(?:production[- ]ready|production auth(?:entication)? complete|"
        r"compliance approved|legal approved|security certified|externally validated)\b",
        re.IGNORECASE,
    )
    for paragraph in re.split(r"\n\s*\n", text):
        if pattern.search(paragraph) and not re.search(
            r"\b(?:not|no|does not|is not|without|unfinished|future)\b",
            paragraph,
            re.IGNORECASE,
        ):
            return True
    return False


def main() -> int:
    checks: list[dict[str, Any]] = []
    v092 = ROOT / "reports" / "v092" / "public_self_serve_api_product_v092.json"
    storage_module = ROOT / "prmr" / "product" / "durable_self_serve_storage_v093.py"
    repository_module = ROOT / "prmr" / "product" / "self_serve_repository_v093.py"
    runner = ROOT / "examples" / "run_durable_self_serve_storage_v093.py"
    hosted_helper = ROOT / "examples" / "run_hosted_storage_redeploy_smoke_v093.py"
    docs = ROOT / "docs" / "durable_self_serve_storage_v093.md"

    add(checks, "v092_self_serve_evidence_exists", v092.exists())
    add(checks, "durable_storage_module_exists", storage_module.exists())
    add(checks, "repository_module_exists", repository_module.exists())
    add(checks, "durable_storage_docs_exist", docs.exists())
    add(checks, "runner_and_hosted_helper_exist", runner.exists() and hosted_helper.exists())
    add(
        checks,
        "explicit_persistence_tables_exist",
        all(
            table in TABLES
            for table in [
                "users",
                "sessions",
                "plans",
                "clients",
                "vaults",
                "namespaces",
                "api_keys",
                "monthly_usage",
                "request_logs",
                "reports",
                "dashboard_snapshots",
            ]
        ),
    )

    public_report, private_report, smoke_report, runner_checks = run_smoke()
    by_name = {item["name"]: item["passed"] for item in runner_checks}
    for audit_name, runner_name in [
        ("users_persist_after_reload", "user_exists_after_reload"),
        ("verification_state_persists", "verification_state_exists_after_reload"),
        ("plan_persists", "plan_exists_after_reload"),
        ("client_vault_namespace_persist", "scope_exists_after_reload"),
        ("key_hash_persists_privately", "key_hash_persisted"),
        ("safe_preview_persists", "safe_preview_exists_after_reload"),
        ("raw_key_is_not_recoverable", "raw_key_not_recoverable_after_reload"),
        ("key_validation_works_after_reload", "persisted_key_validates"),
        ("protected_flow_works_after_reload", "protected_prmr_flow_works"),
        ("usage_persists", "usage_persists_after_reload"),
        ("request_logs_persist", "request_logs_persist_after_reload"),
        ("reports_persist", "report_references_persist_after_reload"),
        ("rotation_persists", "old_key_blocked_after_persisted_rotation"),
        ("replacement_key_validates", "new_key_validates_after_reload"),
        ("revocation_persists", "revoked_key_blocked_after_reload"),
        ("dashboard_state_reloads", "dashboard_reloads_from_persisted_records"),
        ("public_report_runner_check_passes", "public_report_has_no_secrets"),
    ]:
        add(checks, audit_name, by_name.get(runner_name) is True)

    local = storage_status_v093(
        storage_path="reports/v093/local.sqlite",
        api_mode="local_alpha",
        durable_storage_verified=False,
    )
    ephemeral = storage_status_v093(
        storage_path="/tmp/prmr_self_serve.sqlite",
        api_mode="hosted_alpha",
        durable_storage_verified=True,
    )
    durable = storage_status_v093(
        storage_path="/var/data/prmr_self_serve.sqlite",
        api_mode="hosted_alpha",
        durable_storage_verified=True,
    )
    add(
        checks,
        "storage_mode_classification_present",
        local["storage_mode"] == "local_sqlite"
        and ephemeral["storage_mode"] == "hosted_ephemeral_sqlite"
        and durable["storage_mode"] == "hosted_durable_sqlite",
    )
    add(
        checks,
        "tmp_is_never_claimed_durable",
        ephemeral["ephemeral_storage"] is True
        and ephemeral["durable_storage_claim_allowed"] is False
        and bool(ephemeral["tmp_warning"]),
    )
    add(
        checks,
        "hosted_durable_claim_requires_verification",
        storage_status_v093(
            storage_path="/var/data/prmr_self_serve.sqlite",
            api_mode="hosted_alpha",
            durable_storage_verified=False,
        )["durable_storage_claim_allowed"]
        is False
        and durable["durable_storage_claim_allowed"] is True,
    )

    docs_text = docs.read_text(encoding="utf-8")
    add(
        checks,
        "docs_cover_required_storage_boundaries",
        all(
            phrase in docs_text
            for phrase in [
                "/var/data/prmr_self_serve.sqlite",
                "`hosted_ephemeral_sqlite`",
                "Raw API keys and raw passwords are never persisted",
                "Future managed Postgres",
                "NEEDS_HOSTED_DURABLE_STORAGE",
            ]
        ),
    )
    add(
        checks,
        "hosted_redeploy_proof_not_faked",
        public_report["storage"]["hosted_redeploy_proof"] == "NOT_RUN"
        and smoke_report["hosted_redeploy_proof"] == "NOT_RUN",
    )
    add(
        checks,
        "public_reports_contain_no_secrets",
        not contains_secret(public_report) and not contains_secret(smoke_report),
    )
    combined_public = docs_text + "\n" + json.dumps(public_report, sort_keys=True)
    add(
        checks,
        "no_real_email_or_payment_claim",
        public_report["real_email_delivery"] == "NOT_CONNECTED"
        and public_report["payment_processing"] == "NOT_CONNECTED",
    )
    add(
        checks,
        "no_production_or_certification_claim",
        public_report["production_auth"] == "NOT_IMPLEMENTED"
        and not has_unqualified_claim(combined_public),
    )
    add(
        checks,
        "runner_has_exact_30_passing_checks",
        len(runner_checks) == 30 and all(item["passed"] for item in runner_checks),
        {"passed": sum(1 for item in runner_checks if item["passed"]), "total": len(runner_checks)},
    )

    passed = sum(1 for item in checks if item["passed"])
    total = len(checks)
    result = "PASS" if passed == total and public_report["result"] == "PASS" else "NEEDS_WORK"
    audit = {
        "version": "0.93",
        "result": result,
        "checks_passed": passed,
        "checks_total": total,
        "runner_result": public_report["result"],
        "public_safe": True,
        "checks": [{"name": item["name"], "passed": item["passed"]} for item in checks],
    }
    write_json(PUBLIC_REPORT, {**public_report, "audit_result": result})
    write_json(PRIVATE_REPORT, {**private_report, "audit": {**audit, "checks": checks}})
    write_json(SMOKE_REPORT, {**smoke_report, "audit_result": result})
    SCORECARD.write_text(
        build_scorecard(public_report, runner_checks)
        + "\n## Independent audit\n\n"
        + f"- Result: {result}\n"
        + f"- Passed checks: {passed}/{total}\n",
        encoding="utf-8",
    )
    print("PRMR Memory Core V0.93 Durable Self-Serve Storage Audit")
    print(f"Runner result: {public_report['result']} ({public_report['checks_passed']}/{public_report['checks_total']})")
    print(f"Hosted redeploy proof: {smoke_report['hosted_redeploy_proof']}")
    print(f"Passed checks: {passed}/{total}")
    print(f"Result: {result}")
    if result != "PASS":
        for item in checks:
            if not item["passed"]:
                print(f"FAIL: {item['name']}")
                if item.get("detail"):
                    print(str(item["detail"])[-600:])
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
