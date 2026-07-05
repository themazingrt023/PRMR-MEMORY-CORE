"""Smoke V0.98 generic external event contract behavior."""

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


REPORT_DIR = ROOT / "reports" / "v098"
SMOKE_REPORT = REPORT_DIR / "external_event_contract_smoke_v098.json"
BOUNDARY_V098 = (
    "V0.98 is generic external event contract evidence for controlled hosted "
    "API ingestion. It does not claim long-term memory quality, production "
    "security certification, compliance approval, legal approval, or external "
    "validation."
)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def add(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def provision_dashboard_key(client: TestClient) -> tuple[str, str, dict[str, Any]]:
    signup = client.post(
        "/v1/self-serve/signup",
        json={
            "name": "Generic Event Contract Fixture",
            "email": "generic-event-contract@example.test",
            "password": "synthetic-generic-event-contract-password",
        },
    )
    user_id = signup.json()["account"]["user_id"]
    client.post("/v1/self-serve/verify", json={"user_id": user_id})
    login = client.post(
        "/v1/self-serve/login",
        json={
            "email": "generic-event-contract@example.test",
            "password": "synthetic-generic-event-contract-password",
        },
    )
    session_token = login.json()["session_token"]
    session_headers = {"Authorization": f"Session {session_token}"}
    client.post("/v1/self-serve/plan", headers=session_headers, json={"plan_id": "free"})
    scope = client.post("/v1/self-serve/provision", headers=session_headers).json()["scope"]
    key_response = client.post(
        "/v1/self-serve/keys",
        headers=session_headers,
        json={"label": "Generic event contract smoke"},
    )
    return session_token, key_response.json()["raw_api_key"], scope


def safe_details(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in payload.items()
        if key not in {"raw_key", "raw_api_key", "authorization", "session_token"}
    }


def run_smoke() -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    details: dict[str, Any] = {}
    private_trace: dict[str, Any] = {"boundary": BOUNDARY_V098}
    with tempfile.TemporaryDirectory(prefix="prmr-v098-", ignore_cleanup_errors=True) as temp_dir:
        product = DurableSelfServeProductV093(Path(temp_dir) / "self_serve.sqlite")
        with TestClient(create_app_v094(product)) as client:
            session_token, raw_key, scope = provision_dashboard_key(client)
            bearer = {"Authorization": f"Bearer {raw_key}"}
            scope_key = product.product.api.scope_key(
                scope["client_id"],
                scope["vault_id"],
                scope["namespace"],
            )

            legacy_payload = {
                "events": [
                    {
                        "event_id": "evt_legacy_001",
                        "user_id": "synthetic_user",
                        "type": "project_updated",
                        "content": "Synthetic legacy event still works.",
                        "timestamp": "2026-07-05T00:00:00Z",
                        "timestamp_index": 1,
                    }
                ]
            }
            batch_generic_payload = {
                "events": [
                    {
                        "event_type": "external.project.updated",
                        "signal": "User updated a project in an external product.",
                        "metadata": {
                            "source_app": "external_product",
                            "project_ref": "safe_project_ref",
                            "api_key": "prmr_alpha_should_not_survive",
                        },
                        "occurred_at": "2026-07-05T00:01:00.000Z",
                        "actor_reference": "hashed_actor",
                        "workspace_reference": "hashed_workspace",
                        "idempotency_key": "stable-event-id",
                        "unknown_safe_field": "safe_unknown_value",
                    }
                ]
            }
            single_generic_payload = {
                "event_type": "external.task.completed",
                "signal": "A task was completed in an external product.",
                "metadata": {"source_app": "external_product"},
                "occurred_at": "2026-07-05T00:02:00.000Z",
                "actor_reference": "hashed_actor_2",
                "workspace_reference": "hashed_workspace",
                "idempotency_key": "stable-event-id-2",
            }
            unsafe_metadata_payload = {
                "event_type": "external.secret.test",
                "signal": "Unsafe metadata should be redacted.",
                "metadata": {
                    "Authorization": "Bearer prmr_alpha_should_not_survive",
                    "nested": {"token": "sk-test-unsafe"},
                    "safe_note": "keep this",
                },
                "occurred_at": "2026-07-05T00:03:00.000Z",
                "idempotency_key": "stable-event-id-3",
            }

            legacy = client.post("/v1/events/ingest", headers=bearer, json=legacy_payload)
            batch_generic = client.post("/v1/events/ingest", headers=bearer, json=batch_generic_payload)
            single_generic = client.post("/v1/events/ingest", headers=bearer, json=single_generic_payload)
            unsafe_metadata = client.post("/v1/events/ingest", headers=bearer, json=unsafe_metadata_payload)
            events = product.product.api.events.get(scope_key, [])
            by_id = {event.get("event_id"): event for event in events}
            batch_event = by_id.get("stable-event-id", {})
            single_event = by_id.get("stable-event-id-2", {})
            unsafe_event = by_id.get("stable-event-id-3", {})

            packet = client.post("/v1/continuity/packet", headers=bearer, json={})
            packet_payload = packet.json()
            packet_id = packet_payload.get("packet_id")
            internal_packet = product.product.api.packets.get(str(packet_id), {})

            missing = client.post("/v1/events/ingest", json=legacy_payload)
            malformed = client.post(
                "/v1/events/ingest",
                headers={"Authorization": raw_key},
                json=legacy_payload,
            )
            wrong = client.post(
                "/v1/events/ingest",
                headers={"Authorization": "Bearer prmr_alpha_wrong_external_event_contract_key"},
                json=legacy_payload,
            )
            x_api_key = client.post(
                "/v1/events/ingest",
                headers={"x-api-key": raw_key},
                json=legacy_payload,
            )
            keys = client.get(
                "/v1/self-serve/keys",
                headers={"Authorization": f"Session {session_token}"},
            )
            key_id = keys.json()["keys"][0]["key_id"]
            revoke = client.request(
                "DELETE",
                "/v1/self-serve/keys",
                headers={"Authorization": f"Session {session_token}"},
                json={"key_id": key_id},
            )
            revoked = client.post("/v1/events/ingest", headers=bearer, json=legacy_payload)

            add(checks, "legacy_type_content_payload_works", legacy.status_code == 200, legacy.status_code)
            add(checks, "batch_generic_payload_works", batch_generic.status_code == 200, batch_generic.status_code)
            add(checks, "single_generic_payload_works", single_generic.status_code == 200, single_generic.status_code)
            add(checks, "event_type_normalizes_to_type", batch_event.get("type") == "external.project.updated", batch_event)
            add(checks, "signal_normalizes_to_content", batch_event.get("content") == "User updated a project in an external product.", batch_event)
            add(checks, "occurred_at_normalizes_to_timestamp", batch_event.get("timestamp") == "2026-07-05T00:01:00.000Z", batch_event)
            add(checks, "actor_reference_maps_to_user_id", batch_event.get("user_id") == "hashed_actor", batch_event)
            add(
                checks,
                "workspace_reference_preserved_safely",
                batch_event.get("external_metadata", {}).get("workspace_reference") == "hashed_workspace",
                batch_event,
            )
            add(checks, "idempotency_key_used_as_event_id", "stable-event-id" in by_id, list(by_id))
            add(
                checks,
                "unknown_fields_do_not_crash_and_are_sanitized",
                batch_generic.status_code == 200
                and batch_event.get("external_metadata", {}).get("unknown_fields", {}).get("unknown_safe_field") == "safe_unknown_value",
                batch_event,
            )
            unsafe_text = json.dumps(unsafe_event, sort_keys=True)
            add(
                checks,
                "unsafe_metadata_redacted",
                unsafe_metadata.status_code == 200
                and "prmr_alpha_should_not_survive" not in unsafe_text
                and "sk-test-unsafe" not in unsafe_text
                and "[redacted]" in unsafe_text,
                unsafe_event,
            )
            add(
                checks,
                "continuity_packet_reflects_normalized_generic_events",
                packet.status_code == 200
                and internal_packet.get("current_state") == "Unsafe metadata should be redacted."
                and "external.project.updated" in internal_packet.get("active_signals", [])
                and "external.task.completed" in internal_packet.get("active_signals", []),
                internal_packet,
            )
            add(checks, "bearer_auth_required", missing.status_code == 401, missing.status_code)
            add(checks, "malformed_authorization_blocked", malformed.status_code == 401, malformed.status_code)
            add(checks, "wrong_key_blocked", wrong.status_code == 401, wrong.status_code)
            add(checks, "x_api_key_unsupported", x_api_key.status_code == 401, x_api_key.status_code)
            add(checks, "revoked_key_blocked", revoked.status_code == 403, revoked.status_code)
            add(
                checks,
                "raw_key_not_stored",
                not product.repository.raw_value_present(raw_key),
            )

            details = {
                "legacy_status": legacy.status_code,
                "batch_generic_status": batch_generic.status_code,
                "single_generic_status": single_generic.status_code,
                "unsafe_metadata_status": unsafe_metadata.status_code,
                "packet_status": packet.status_code,
                "stored_event_count": len(events),
                "packet_active_signal_count": len(internal_packet.get("active_signals", [])),
                "raw_key_reported": False,
                "session_token_reported": False,
            }
            private_trace = {
                **private_trace,
                "scope": scope,
                "stored_events": events,
                "packet": internal_packet,
                "revoke_probe": {"status_code": revoke.status_code, "body": safe_details(revoke.json())},
            }
    return checks, details, private_trace


def main() -> int:
    checks, details, private_trace = run_smoke()
    passed = sum(1 for check in checks if check["passed"])
    result = "PASS" if passed == len(checks) else "NEEDS_WORK"
    smoke = {
        "version": "0.98",
        "title": "Generic External Event Contract Smoke",
        "result": result,
        "checks_passed": passed,
        "checks_total": len(checks),
        "details": details,
        "public_safe": True,
        "boundary": BOUNDARY_V098,
        "private_trace_available": True,
    }
    private_trace = {**private_trace, "result": result, "checks": checks, "public_safe": False}
    write_json(SMOKE_REPORT, smoke)
    write_json(REPORT_DIR / "private_external_event_contract_smoke_trace_v098.json", private_trace)
    print("PRMR V0.98 External Event Contract Smoke")
    print(f"Passed checks: {passed}/{len(checks)}")
    print(f"Result: {result}")
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
