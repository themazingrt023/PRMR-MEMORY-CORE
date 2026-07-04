"""Prove that a dashboard-created key authenticates protected PRMR routes."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from prmr.product.api_server_v094 import create_app_v094
from prmr.product.durable_self_serve_storage_v093 import DurableSelfServeProductV093


REPORT_DIR = ROOT / "reports" / "api_key_validation"
PUBLIC_REPORT = REPORT_DIR / "public_external_api_key_usability.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_external_api_key_usability.json"


def add(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def provision_dashboard_key(client: TestClient) -> tuple[str, str, dict[str, str]]:
    signup = client.post(
        "/v1/self-serve/signup",
        json={
            "name": "External Consumer Fixture",
            "email": "external-consumer@example.test",
            "password": "synthetic-external-consumer-password",
        },
    )
    user_id = signup.json()["account"]["user_id"]
    client.post("/v1/self-serve/verify", json={"user_id": user_id})
    login = client.post(
        "/v1/self-serve/login",
        json={
            "email": "external-consumer@example.test",
            "password": "synthetic-external-consumer-password",
        },
    )
    session_token = login.json()["session_token"]
    session_headers = {"Authorization": f"Session {session_token}"}
    client.post("/v1/self-serve/plan", headers=session_headers, json={"plan_id": "free"})
    scope = client.post("/v1/self-serve/provision", headers=session_headers).json()["scope"]
    key_response = client.post(
        "/v1/self-serve/keys",
        headers=session_headers,
        json={"label": "External server"},
    )
    return session_token, key_response.json()["raw_api_key"], scope


def run_probe() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    details: dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="prmr-key-usability-", ignore_cleanup_errors=True) as temp_dir:
        storage_path = Path(temp_dir) / "self_serve.sqlite"
        product = DurableSelfServeProductV093(storage_path)
        with TestClient(create_app_v094(product)) as client:
            health = client.get("/health")
            session_token, raw_key, scope = provision_dashboard_key(client)
            bearer = {"Authorization": f"Bearer {raw_key}"}

            usage = client.get("/v1/usage", headers=bearer)
            whitespace = client.get(
                "/v1/usage",
                headers={"Authorization": f"Bearer   {raw_key}  "},
            )
            ingest = client.post(
                "/v1/events/ingest",
                headers=bearer,
                json={
                    "events": [
                        {
                            "type": "project_updated",
                            "content": "Synthetic external-consumer integration event.",
                            "timestamp_index": 1,
                        }
                    ]
                },
            )
            packet = client.post("/v1/continuity/packet", headers=bearer, json={})
            reloaded_active = DurableSelfServeProductV093(storage_path)
            with TestClient(create_app_v094(reloaded_active)) as reloaded_client:
                persisted_active = reloaded_client.get(
                    "/v1/usage",
                    headers={"Authorization": f"Bearer {raw_key}"},
                )
            list_keys = client.get(
                "/v1/self-serve/keys",
                headers={"Authorization": f"Session {session_token}"},
            )
            missing = client.get("/v1/usage")
            raw_header = client.get("/v1/usage", headers={"Authorization": raw_key})
            x_api_key = client.get("/v1/usage", headers={"x-api-key": raw_key})
            wrong = client.get(
                "/v1/usage",
                headers={"Authorization": "Bearer prmr_alpha_not_a_real_external_key"},
            )
            wrong_scope = client.get(
                "/v1/usage",
                headers={
                    **bearer,
                    "X-Client-ID": "client_wrong_scope",
                    "X-Vault-ID": scope["vault_id"],
                    "X-Namespace": scope["namespace"],
                },
            )
            key_id = list_keys.json()["keys"][0]["key_id"]
            lifecycle = product.product.api.lifecycle
            lifecycle.lifecycle_keys[key_id].status = "suspended"
            lifecycle.foundation.api_keys[key_id].status = "suspended"
            inactive = client.get("/v1/usage", headers=bearer)
            lifecycle.lifecycle_keys[key_id].status = "active"
            lifecycle.foundation.api_keys[key_id].status = "active"
            revoke = client.request(
                "DELETE",
                "/v1/self-serve/keys",
                headers={"Authorization": f"Session {session_token}"},
                json={"key_id": key_id},
            )
            revoked = client.get("/v1/usage", headers=bearer)

            add(checks, "dashboard_created_key_uses_prmr_prefix", raw_key.startswith("prmr_alpha_"))
            add(
                checks,
                "health_declares_scope_inference_revision",
                health.status_code == 200
                and health.json().get("api_key_auth", {}).get("validation_revision")
                == "external_consumer_scope_v1",
            )
            add(checks, "bearer_only_usage_succeeds", usage.status_code == 200, usage.status_code)
            add(checks, "surrounding_whitespace_is_trimmed", whitespace.status_code == 200, whitespace.status_code)
            add(checks, "bearer_only_ingest_succeeds", ingest.status_code == 200, ingest.status_code)
            add(checks, "bearer_only_packet_succeeds", packet.status_code == 200, packet.status_code)
            add(
                checks,
                "copy_once_list_is_secret_safe",
                raw_key not in json.dumps(list_keys.json())
                and list_keys.json().get("credential_values_returned") is False,
            )
            add(checks, "missing_authorization_rejected", missing.status_code == 401, missing.status_code)
            add(checks, "raw_authorization_rejected", raw_header.status_code == 401, raw_header.status_code)
            add(checks, "x_api_key_rejected", x_api_key.status_code == 401, x_api_key.status_code)
            add(checks, "wrong_key_rejected", wrong.status_code == 401, wrong.status_code)
            add(checks, "wrong_explicit_scope_rejected", wrong_scope.status_code == 403, wrong_scope.status_code)
            add(checks, "inactive_key_rejected", inactive.status_code == 403, inactive.status_code)
            add(checks, "revoke_operation_succeeds", revoke.status_code == 200, revoke.status_code)
            add(checks, "revoked_key_rejected", revoked.status_code == 403, revoked.status_code)
            add(checks, "raw_key_not_stored", not product.repository.raw_value_present(raw_key))
            add(
                checks,
                "safe_diagnostics_contain_no_key_material",
                raw_key not in json.dumps(product.product.api_key_diagnostics)
                and all("key_hash" not in row for row in product.product.api_key_diagnostics),
            )
            add(
                checks,
                "active_key_validates_after_storage_reload",
                persisted_active.status_code == 200,
                persisted_active.status_code,
            )
            details = {
                "scope_inferred_from_key": usage.json().get("client_id") == scope["client_id"],
                "usage_status": usage.status_code,
                "ingest_status": ingest.status_code,
                "packet_status": packet.status_code,
                "missing_status": missing.status_code,
                "wrong_scope_status": wrong_scope.status_code,
                "inactive_status": inactive.status_code,
                "revoked_status": revoked.status_code,
                "raw_key_reported": False,
                "session_token_reported": False,
            }

        reloaded = DurableSelfServeProductV093(storage_path)
        with TestClient(create_app_v094(reloaded)) as client:
            persisted_revoked = client.get("/v1/usage", headers={"Authorization": f"Bearer {raw_key}"})
            add(
                checks,
                "revoked_status_persists_after_reload",
                persisted_revoked.status_code == 403,
                persisted_revoked.status_code,
            )
    return checks, details


def main() -> int:
    checks, details = run_probe()
    passed = sum(1 for check in checks if check["passed"])
    result = "PASS" if passed == len(checks) else "NEEDS_WORK"
    public = {
        "product": "PRMR Memory Core",
        "title": "External API Key Usability Audit",
        "result": result,
        "checks_passed": passed,
        "checks_total": len(checks),
        "contract": "Authorization: Bearer <PRMR_API_KEY>",
        "scope_behavior": "Key scope is inferred when scope headers are absent; supplied mismatched scope is denied.",
        "raw_key_exposed": False,
        "hash_exposed": False,
        "details": details,
        "boundary": "Internal synthetic integration evidence. This is not external security certification.",
    }
    private = {**public, "public_safe": False, "checks": checks}
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    PUBLIC_REPORT.write_text(json.dumps(public, indent=2) + "\n", encoding="utf-8")
    PRIVATE_REPORT.write_text(json.dumps(private, indent=2) + "\n", encoding="utf-8")
    print("PRMR External API Key Usability Audit")
    print(f"Passed checks: {passed}/{len(checks)}")
    print(f"Result: {result}")
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
