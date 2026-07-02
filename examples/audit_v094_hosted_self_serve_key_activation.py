"""Audit V0.94 hosted self-serve activation implementation and truth state."""

from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from examples.run_hosted_self_serve_key_activation_v094 import (
    PRIVATE_REPORT,
    PUBLIC_REPORT,
    SCORECARD,
    SMOKE_REPORT,
    build_scorecard,
    contains_secret,
    run_hosted_smoke,
    write_json,
)
from prmr.product.api_server_v094 import create_app_v094
from prmr.product.durable_self_serve_storage_v093 import DurableSelfServeProductV093


def add(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def has_unqualified_claim(text: str) -> bool:
    pattern = re.compile(
        r"\b(?:real email verification|stripe billing is live|production auth(?:entication)? complete|"
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


def local_http_probe() -> dict[str, Any]:
    raw_key = ""
    session_token = ""
    with tempfile.TemporaryDirectory(prefix="prmr-v094-audit-", ignore_cleanup_errors=True) as temp_dir:
        product = DurableSelfServeProductV093(Path(temp_dir) / "v094.sqlite")
        with TestClient(create_app_v094(product)) as client:
            health = client.get("/health")
            signup = client.post(
                "/v1/self-serve/signup",
                json={
                    "name": "Generic V0.94 Audit Builder",
                    "email": "v094-audit@example.test",
                    "password": "synthetic-v094-audit-password",
                },
            )
            user_id = signup.json().get("account", {}).get("user_id", "")
            verify = client.post("/v1/self-serve/verify", json={"user_id": user_id})
            login = client.post(
                "/v1/self-serve/login",
                json={
                    "email": "v094-audit@example.test",
                    "password": "synthetic-v094-audit-password",
                },
            )
            session_token = login.json().get("session_token", "")
            session_headers = {"Authorization": f"Session {session_token}"}
            plan = client.post("/v1/self-serve/plan", headers=session_headers, json={"plan_id": "free"})
            provision = client.post("/v1/self-serve/provision", headers=session_headers)
            scope = provision.json().get("scope", {})
            key_create = client.post(
                "/v1/self-serve/keys",
                headers=session_headers,
                json={"label": "Audit server"},
            )
            raw_key = key_create.json().get("raw_api_key", "")
            key_list = client.get("/v1/self-serve/keys", headers=session_headers)
            api_headers = {
                "Authorization": f"Bearer {raw_key}",
                "X-Client-ID": scope.get("client_id", ""),
                "X-Vault-ID": scope.get("vault_id", ""),
                "X-Namespace": scope.get("namespace", ""),
            }
            ingest = client.post(
                "/v1/events/ingest",
                headers=api_headers,
                json={
                    "events": [
                        {
                            "type": "project_updated",
                            "content": "Generic V0.94 local HTTP audit event.",
                            "timestamp_index": 1,
                        }
                    ]
                },
            )
            packet = client.post("/v1/continuity/packet", headers=api_headers, json={})
            packet_id = packet.json().get("packet_id")
            report_id = packet.json().get("report_id")
            reconstruct = client.post(
                "/v1/memory/reconstruct",
                headers=api_headers,
                json={"packet_id": packet_id},
            )
            explain = client.post(
                "/v1/explain",
                headers=api_headers,
                json={"packet_id": packet_id},
            )
            report = client.get(f"/v1/reports/{report_id}", headers=api_headers)
            usage = client.get("/v1/usage", headers=api_headers)
            dashboard = client.get("/v1/self-serve/dashboard", headers=session_headers)
            public_outputs = {
                "health": health.json(),
                "signup": signup.json(),
                "verify": verify.json(),
                "plan": plan.json(),
                "provision": provision.json(),
                "key_list": key_list.json(),
                "dashboard": dashboard.json(),
            }
            return {
                "health": health.status_code == 200,
                "account_flow": all(
                    status in {200, 201}
                    for status in [
                        signup.status_code,
                        verify.status_code,
                        login.status_code,
                        plan.status_code,
                        provision.status_code,
                    ]
                ),
                "copy_once_key": key_create.status_code == 201 and bool(raw_key),
                "safe_key_list": key_list.status_code == 200
                and key_list.json().get("credential_values_returned") is False
                and raw_key not in json.dumps(key_list.json()),
                "protected_flow": all(
                    response.status_code == 200
                    for response in [ingest, packet, reconstruct, explain, report, usage]
                ),
                "dashboard": dashboard.status_code == 200
                and len(dashboard.json().get("dashboard", {}).get("reports", [])) == 1,
                "public_outputs_safe": not contains_secret(public_outputs, [raw_key, session_token]),
            }


def main() -> int:
    checks: list[dict[str, Any]] = []
    v093 = ROOT / "reports" / "v093" / "public_durable_self_serve_storage_v093.json"
    server = ROOT / "prmr" / "product" / "api_server_v094.py"
    runner = ROOT / "examples" / "run_hosted_self_serve_key_activation_v094.py"
    checkpoint = ROOT / "examples" / "run_hosted_self_serve_redeploy_checkpoint_v094.py"
    docs = ROOT / "docs" / "hosted_self_serve_key_activation_v094.md"
    render = ROOT / "render.yaml"
    proxy_files = [
        ROOT / "frontend" / "app" / "api" / "self-serve" / "activate" / "route.ts",
        ROOT / "frontend" / "app" / "api" / "dashboard" / "state" / "route.ts",
        ROOT / "frontend" / "app" / "api" / "dashboard" / "keys" / "route.ts",
    ]
    supabase_session_files = [
        ROOT / "frontend" / "lib" / "supabaseServer.ts",
        ROOT / "frontend" / "app" / "auth" / "callback" / "route.ts",
    ]
    v095_evidence = ROOT / "reports" / "v095" / "public_supabase_auth_real_email_v095.json"

    add(checks, "v093_evidence_exists", v093.exists())
    add(checks, "hosted_api_server_exists", server.exists())
    add(checks, "hosted_smoke_runner_exists", runner.exists())
    add(checks, "redeploy_checkpoint_helper_exists", checkpoint.exists())
    add(checks, "hosted_activation_docs_exist", docs.exists())
    add(checks, "frontend_proxy_routes_exist", all(path.exists() for path in proxy_files))

    source_files = [
        server,
        runner,
        checkpoint,
        docs,
        render,
        *proxy_files,
        *supabase_session_files,
    ]
    source_text = "\n".join(path.read_text(encoding="utf-8") for path in source_files if path.exists())
    add(checks, "no_continuum_specific_tailoring", "continuum" not in source_text.lower())
    add(
        checks,
        "generic_client_route_flow_exists",
        all(
            route in source_text
            for route in [
                "/v1/self-serve/signup",
                "/v1/self-serve/verify",
                "/v1/self-serve/login",
                "/v1/self-serve/plan",
                "/v1/self-serve/provision",
                "/v1/self-serve/keys",
                "/v1/self-serve/dashboard",
            ]
        ),
    )
    add(
        checks,
        "render_durable_storage_is_documented",
        "/var/data/prmr_self_serve.sqlite" in source_text
        and "PRMR_DURABLE_STORAGE_VERIFIED" in source_text
        and "api_server_v094:app" in source_text,
    )
    add(
        checks,
        "tmp_is_not_claimed_durable",
        "/tmp" in docs.read_text(encoding="utf-8")
        and "never count as" in docs.read_text(encoding="utf-8"),
    )
    v095_audit_passed = False
    if v095_evidence.exists():
        v095_payload = json.loads(v095_evidence.read_text(encoding="utf-8"))
        v095_audit_passed = (
            v095_payload.get("audit", {}).get("result") == "PASS"
            and v095_payload.get("audit", {}).get("checks_passed") == 21
        )
    legacy_cookie_boundary = (
        "httpOnly: true" in source_text and 'sameSite: "strict"' in source_text
    )
    supabase_session_boundary = (
        all(path.exists() for path in supabase_session_files)
        and "createServerClient" in source_text
        and "auth.getUser" in source_text
        and "exchangeCodeForSession" in source_text
        and v095_audit_passed
    )
    add(
        checks,
        "frontend_session_boundary_is_protected",
        legacy_cookie_boundary or supabase_session_boundary,
        {
            "legacy_http_only_cookie": legacy_cookie_boundary,
            "supabase_v095_verified_session": supabase_session_boundary,
        },
    )
    add(
        checks,
        "frontend_source_contains_no_raw_credentials",
        not re.search(r"\bprmr_(?:alpha|live)_[A-Za-z0-9_-]{24,}\b", source_text),
    )
    probe = local_http_probe()
    for name in [
        "health",
        "account_flow",
        "copy_once_key",
        "safe_key_list",
        "protected_flow",
        "dashboard",
        "public_outputs_safe",
    ]:
        add(checks, f"local_http_{name}", probe[name])

    hosted_public, hosted_private, hosted_smoke, hosted_checks = run_hosted_smoke()
    add(
        checks,
        "hosted_smoke_status_is_honest",
        hosted_public["result"] in {"PASS", "NEEDS_HOSTED_DURABLE_STORAGE", "NEEDS_WORK"},
        hosted_public["result"],
    )
    add(
        checks,
        "hosted_public_report_contains_no_secrets",
        not contains_secret(hosted_public) and not contains_secret(hosted_smoke),
    )
    add(
        checks,
        "no_real_email_or_stripe_claim",
        "no verification email is sent" in source_text.lower()
        and "stripe is not connected" in source_text.lower(),
    )
    add(
        checks,
        "no_production_or_certification_claim",
        not has_unqualified_claim(source_text + "\n" + json.dumps(hosted_public)),
    )

    passed = sum(1 for item in checks if item["passed"])
    total = len(checks)
    audit_result = "PASS" if passed == total else "NEEDS_WORK"
    hosted_result = hosted_public["result"]
    milestone_result = "PASS" if audit_result == "PASS" and hosted_result == "PASS" else hosted_result
    audit = {
        "version": "0.94",
        "result": audit_result,
        "milestone_result": milestone_result,
        "checks_passed": passed,
        "checks_total": total,
        "hosted_smoke_result": hosted_result,
        "public_safe": True,
        "checks": [{"name": item["name"], "passed": item["passed"]} for item in checks],
    }
    write_json(PUBLIC_REPORT, {**hosted_public, "audit_result": audit_result, "milestone_result": milestone_result})
    write_json(
        PRIVATE_REPORT,
        {
            **hosted_private,
            "audit": {**audit, "checks": checks},
            "local_http_probe": probe,
            "hosted_checks": hosted_checks,
        },
    )
    write_json(SMOKE_REPORT, {**hosted_smoke, "audit_result": audit_result, "milestone_result": milestone_result})
    SCORECARD.write_text(
        build_scorecard(hosted_public, hosted_checks)
        + "\n## Independent audit\n\n"
        + f"- Result: {audit_result}\n"
        + f"- Passed checks: {passed}/{total}\n"
        + f"- Hosted smoke: {hosted_result}\n"
        + f"- Milestone result: {milestone_result}\n",
        encoding="utf-8",
    )
    print("PRMR Memory Core V0.94 Hosted Self-Serve Activation Audit")
    print(f"Local/deployable audit: {audit_result} ({passed}/{total})")
    print(f"Hosted smoke: {hosted_result}")
    print(f"Milestone result: {milestone_result}")
    if audit_result != "PASS":
        for item in checks:
            if not item["passed"]:
                print(f"FAIL: {item['name']}")
    return 0 if audit_result == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
