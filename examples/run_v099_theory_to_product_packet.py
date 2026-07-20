"""Run V0.99 deterministic theory-to-product packet smoke."""

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


REPORT_DIR = ROOT / "reports" / "v099"
SMOKE_REPORT = REPORT_DIR / "theory_to_product_packet_smoke_v099.json"
BOUNDARY_V099 = (
    "V0.99 is deterministic PRMR theory-to-product packet evidence. It "
    "operationalizes active, latent, lineage, causal signature, horizon, "
    "coherence, recoverability, decay, and re-emergence for scoped software "
    "event streams. It is not full scientific validation, production security "
    "certification, compliance approval, legal approval, or long-term external proof."
)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def add(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def provision(client: TestClient, email: str) -> tuple[str, str, dict[str, Any]]:
    signup = client.post(
        "/v1/self-serve/signup",
        json={"name": "V099 Packet Fixture", "email": email, "password": "synthetic-v099-password"},
    )
    user_id = signup.json()["account"]["user_id"]
    client.post("/v1/self-serve/verify", json={"user_id": user_id})
    login = client.post("/v1/self-serve/login", json={"email": email, "password": "synthetic-v099-password"})
    session_token = login.json()["session_token"]
    session_headers = {"Authorization": f"Session {session_token}"}
    client.post("/v1/self-serve/plan", headers=session_headers, json={"plan_id": "free"})
    scope = client.post("/v1/self-serve/provision", headers=session_headers).json()["scope"]
    key = client.post("/v1/self-serve/keys", headers=session_headers, json={"label": "V0.99 packet smoke"}).json()["raw_api_key"]
    return session_token, key, scope


def packet(client: TestClient, key: str, scope: dict[str, Any] | None = None) -> dict[str, Any]:
    response = client.post("/v1/continuity/packet", headers={"Authorization": f"Bearer {key}"}, json=scope or {})
    body = response.json()
    return {"status_code": response.status_code, "body": body, "packet": body.get("packet", {})}


def run_flow() -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    details: dict[str, Any] = {}
    private: dict[str, Any] = {"boundary": BOUNDARY_V099}
    with tempfile.TemporaryDirectory(prefix="prmr-v099-", ignore_cleanup_errors=True) as temp_dir:
        product = DurableSelfServeProductV093(Path(temp_dir) / "self_serve.sqlite")
        with TestClient(create_app_v094(product)) as client:
            session, raw_key, scope = provision(client, "v099@example.test")
            headers = {"Authorization": f"Bearer {raw_key}"}
            empty_packet = packet(client, raw_key)
            add(checks, "empty_scope_returns_safe_empty_packet", empty_packet["status_code"] == 200 and empty_packet["packet"].get("event_count") == 0, empty_packet["packet"])

            events = [
                {
                    "event_id": "evt_001",
                    "type": "project_created",
                    "content": "Project opened.",
                    "timestamp": "2026-07-05T00:00:00Z",
                    "timestamp_index": 1,
                    "application_reference": "app_v099",
                    "actor_reference": "hashed_actor",
                    "workspace_reference": "hashed_workspace",
                    "entity_reference": "project_v099",
                },
                {
                    "event_type": "habit.completed",
                    "signal": "A recurring habit was completed.",
                    "metadata": {"source_app": "external_product", "Authorization": "Bearer prmr_alpha_should_redact"},
                    "occurred_at": "2026-07-05T00:01:00Z",
                    "actor_reference": "hashed_actor",
                    "workspace_reference": "hashed_workspace",
                    "application_reference": "app_v099",
                    "entity_reference": "project_v099",
                    "idempotency_key": "evt_002",
                    "timestamp_index": 2,
                },
                {
                    "event_type": "project_updated",
                    "signal": "Project was updated.",
                    "metadata": {"source_app": "external_product"},
                    "occurred_at": "2026-07-05T00:02:00Z",
                    "actor_reference": "hashed_actor",
                    "workspace_reference": "hashed_workspace",
                    "application_reference": "app_v099",
                    "entity_reference": "project_v099",
                    "idempotency_key": "evt_003",
                    "timestamp_index": 3,
                },
                {
                    "event_type": "habit.completed",
                    "signal": "A recurring habit was completed again.",
                    "metadata": {"source_app": "external_product"},
                    "occurred_at": "2026-07-05T00:03:00Z",
                    "actor_reference": "hashed_actor",
                    "workspace_reference": "hashed_workspace",
                    "application_reference": "app_v099",
                    "entity_reference": "project_v099",
                    "idempotency_key": "evt_004",
                    "timestamp_index": 4,
                },
                {
                    "event_type": "decision.logged",
                    "signal": "A decision was logged.",
                    "metadata": {"source_app": "external_product"},
                    "occurred_at": "2026-07-05T00:04:00Z",
                    "actor_reference": "hashed_actor",
                    "workspace_reference": "hashed_workspace",
                    "application_reference": "app_v099",
                    "entity_reference": "project_v099",
                    "idempotency_key": "evt_005",
                    "timestamp_index": 5,
                },
                {
                    "event_type": "project_updated",
                    "signal": "Project was updated after a gap.",
                    "metadata": {"source_app": "external_product"},
                    "occurred_at": "2026-07-05T00:05:00Z",
                    "actor_reference": "hashed_actor",
                    "workspace_reference": "hashed_workspace",
                    "application_reference": "app_v099",
                    "entity_reference": "project_v099",
                    "idempotency_key": "evt_006",
                    "timestamp_index": 6,
                },
                {
                    "type": "status_reviewed",
                    "content": "Status was reviewed.",
                    "timestamp": "2026-07-05T00:06:00Z",
                    "timestamp_index": 7,
                    "application_reference": "app_v099",
                    "actor_reference": "hashed_actor",
                    "workspace_reference": "hashed_workspace",
                    "entity_reference": "project_v099",
                },
                {
                    "event_type": "project_updated",
                    "signal": "Project was updated as current state.",
                    "metadata": {"source_app": "external_product", "file_path": "C:/Users/example/secret.txt"},
                    "occurred_at": "2026-07-05T00:07:00Z",
                    "actor_reference": "hashed_actor",
                    "workspace_reference": "hashed_workspace",
                    "application_reference": "app_v099",
                    "entity_reference": "project_v099",
                    "idempotency_key": "evt_008",
                    "timestamp_index": 8,
                },
            ]
            ingest = client.post("/v1/events/ingest", headers=headers, json={"events": events})
            rich = packet(
                client,
                raw_key,
                {
                    "application_reference": "app_v099",
                    "actor_reference": "hashed_actor",
                    "workspace_reference": "hashed_workspace",
                    "entity_reference": "project_v099",
                },
            )
            rich_packet = rich["packet"]
            active_signals = {item["signal"] for item in rich_packet.get("active_information", [])}
            latent_signals = {item["signal"] for item in rich_packet.get("latent_information", [])}
            reemerged = {item["signal"] for item in rich_packet.get("re_emergence_signals", [])}
            repeated = {item["pattern"] for item in rich_packet.get("repeated_patterns", [])}
            causal = rich_packet.get("causal_signature", {})
            horizon = rich_packet.get("recursive_horizon", {})
            packet_text = json.dumps(rich_packet, sort_keys=True)
            stored_text = json.dumps(product.product.api.events, sort_keys=True)

            add(checks, "single_event_creates_current_state_and_active_information", ingest.status_code == 200 and rich_packet.get("current_state") == "Project was updated as current state." and "project_updated" in active_signals, rich_packet)
            add(checks, "repeated_events_create_lineage_information", any(row.get("signal") == "project_updated" and row.get("count", 0) >= 3 for row in rich_packet.get("lineage_information", [])), rich_packet.get("lineage_information"))
            add(checks, "dormant_old_signals_become_latent_information", "project_created" in latent_signals, rich_packet.get("latent_information"))
            add(checks, "returning_dormant_signal_becomes_re_emergence", "project_updated" in reemerged, rich_packet.get("re_emergence_signals"))
            add(checks, "missing_old_signal_becomes_decayed", "project_created" in set(rich_packet.get("decayed_signals", [])), rich_packet.get("decayed_signals"))
            add(checks, "causal_signature_includes_stable_patterns", "project_updated" in causal.get("recurring_signal_names", []) and "project_updated" in repeated, causal)
            add(checks, "recursive_horizon_separates_recent_and_historical", "project_created" in horizon.get("historical_signal_set", []) and "project_created" not in horizon.get("recent_signal_set", []), horizon)
            add(checks, "generic_v098_events_contribute_correctly", "habit.completed" in causal.get("signal_frequency_distribution", {}) and "A recurring habit was completed" in packet_text, causal)
            add(checks, "legacy_type_content_events_contribute_correctly", "status_reviewed" in causal.get("signal_frequency_distribution", {}) and "Status was reviewed." in packet_text, causal)
            add(checks, "metadata_is_sanitized", "metadata_source_app_distribution" in causal and causal["metadata_source_app_distribution"].get("external_product", 0) >= 1, causal)
            add(
                checks,
                "unsafe_metadata_is_redacted",
                "prmr_alpha_should_redact" not in packet_text
                and "secret.txt" not in packet_text
                and "prmr_alpha_should_redact" not in stored_text
                and "secret.txt" not in stored_text
                and "[redacted]" in stored_text,
                {"packet_safe": True, "stored_metadata_redacted": "[redacted]" in stored_text},
            )
            add(checks, "bearer_auth_still_required", client.post("/v1/continuity/packet", json={}).status_code == 401)
            add(checks, "wrong_and_malformed_keys_fail", client.post("/v1/continuity/packet", headers={"Authorization": raw_key}, json={}).status_code == 401 and client.post("/v1/continuity/packet", headers={"Authorization": "Bearer prmr_alpha_wrong_v099_key"}, json={}).status_code == 401)
            keys = client.get("/v1/self-serve/keys", headers={"Authorization": f"Session {session}"}).json()["keys"]
            client.request("DELETE", "/v1/self-serve/keys", headers={"Authorization": f"Session {session}"}, json={"key_id": keys[0]["key_id"]})
            add(checks, "revoked_key_fails", client.post("/v1/continuity/packet", headers=headers, json={}).status_code == 403)

            stable_product = DurableSelfServeProductV093(Path(temp_dir) / "stable.sqlite")
            with TestClient(create_app_v094(stable_product)) as stable_client:
                _, stable_key, _ = provision(stable_client, "v099-stable@example.test")
                stable_headers = {"Authorization": f"Bearer {stable_key}"}
                sparse_events = {"events": [{"type": "a", "content": "one", "timestamp_index": 1}]}
                stable_client.post("/v1/events/ingest", headers=stable_headers, json=sparse_events)
                sparse_packet = packet(stable_client, stable_key)["packet"]
                stable_client.post(
                    "/v1/events/ingest",
                    headers=stable_headers,
                    json={
                        "events": [
                            {"type": "a", "content": "two", "timestamp_index": 2},
                            {"type": "a", "content": "three", "timestamp_index": 3},
                            {"type": "a", "content": "four", "timestamp_index": 4},
                            {"type": "a", "content": "five", "timestamp_index": 5},
                        ]
                    },
                )
                stable_packet = packet(stable_client, stable_key)["packet"]
                add(checks, "stable_repeated_patterns_improve_coherence_score", stable_packet.get("coherence_score", 0) > sparse_packet.get("coherence_score", 0), {"sparse": sparse_packet.get("coherence_score"), "stable": stable_packet.get("coherence_score")})
                add(checks, "ordered_complete_events_improve_recoverability_score", stable_packet.get("recoverability_score", 0) > sparse_packet.get("recoverability_score", 0), {"sparse": sparse_packet.get("recoverability_score"), "stable": stable_packet.get("recoverability_score")})

            details = {
                "ingest_status": ingest.status_code,
                "packet_status": rich["status_code"],
                "event_count": rich_packet.get("event_count"),
                "coherence_score": rich_packet.get("coherence_score"),
                "recoverability_score": rich_packet.get("recoverability_score"),
                "active_information_count": len(rich_packet.get("active_information", [])),
                "latent_information_count": len(rich_packet.get("latent_information", [])),
                "raw_key_reported": False,
            }
            private = {
                **private,
                "scope": scope,
                "packet": rich_packet,
                "stored_events": product.product.api.events,
            }
    return checks, details, private


def main() -> int:
    checks, details, private = run_flow()
    passed = sum(1 for check in checks if check["passed"])
    result = "PASS" if passed == len(checks) else "NEEDS_WORK"
    smoke = {
        "version": "0.99",
        "title": "Theory-to-Product Continuity Packet Smoke",
        "result": result,
        "checks_passed": passed,
        "checks_total": len(checks),
        "details": details,
        "public_safe": True,
        "boundary": BOUNDARY_V099,
    }
    write_json(SMOKE_REPORT, smoke)
    write_json(REPORT_DIR / "private_theory_to_product_packet_trace_v099.json", {**private, "checks": checks, "result": result, "public_safe": False})
    print("PRMR V0.99 Theory-to-Product Packet Smoke")
    print(f"Passed checks: {passed}/{len(checks)}")
    print(f"Result: {result}")
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
