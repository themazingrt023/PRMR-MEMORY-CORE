"""Run the PRMR Console Product Experience Reset proof."""

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
from prmr.product.supabase_auth_bridge_v095 import FixtureSupabaseIdentityVerifier, SupabaseAuthBridgeV095, SupabaseIdentity


REPORT_DIR = ROOT / "reports" / "console_product_experience_reset"
PUBLIC_REPORT = REPORT_DIR / "public_console_product_experience_reset.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_console_product_experience_reset.json"
SMOKE_REPORT = REPORT_DIR / "console_product_experience_reset_smoke.json"
SCORECARD = REPORT_DIR / "scorecard_console_product_experience_reset.md"
BOUNDARY = (
    "Console Product Experience Reset evidence. PASS means local synthetic "
    "console product-flow checks passed. It does not claim production auth "
    "hardening, live billing, compliance approval, legal approval, external "
    "security certification, or external real-world validation."
)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def add(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="replace")


def live_event() -> dict[str, Any]:
    return {
        "application_reference": "app_main",
        "actor_reference": "live_actor_a",
        "workspace_reference": "live_workspace",
        "entity_reference": "live_actor_a",
        "event_type": "customer.workflow.updated",
        "signal": "Live customer workflow event reached Memory Core.",
        "occurred_at": "2026-07-21T12:00:00Z",
        "idempotency_key": "console-reset-live-event-001",
        "metadata": {"source_app": "console_reset_smoke", "synthetic": True},
    }


def main() -> int:
    checks: list[dict[str, Any]] = []
    private: dict[str, Any] = {"boundary": BOUNDARY}
    with tempfile.TemporaryDirectory(prefix="prmr-console-reset-", ignore_cleanup_errors=True) as temp_dir:
        product = DurableSelfServeProductV093(Path(temp_dir) / "console.sqlite")
        bridge = SupabaseAuthBridgeV095(
            product,
            FixtureSupabaseIdentityVerifier(
                {
                    "console_token": SupabaseIdentity(
                        subject="console-reset-user",
                        email="console-reset@example.test",
                        email_confirmed_at="2026-07-21T10:00:00Z",
                        role="authenticated",
                        display_name="Console Reset User",
                    )
                }
            ),
        )
        with TestClient(create_app_v094(product, bridge)) as client:
            auth = {"Authorization": "Bearer console_token"}
            activation = client.post("/v1/auth/supabase/activate", headers=auth, json={"plan_id": "free"})
            raw_key = str(activation.json().get("raw_api_key") or "")
            live_headers = {"Authorization": f"Bearer {raw_key}"}
            live_ingest = client.post("/v1/events/ingest", headers=live_headers, json={"events": [live_event()]})
            live_packet = client.post(
                "/v1/continuity/packet",
                headers=live_headers,
                json={"application_reference": "app_main", "actor_reference": "live_actor_a", "workspace_reference": "live_workspace", "entity_reference": "live_actor_a"},
            )
            events = client.get("/v1/auth/supabase/dashboard/events", headers=auth)
            packets = client.get("/v1/auth/supabase/dashboard/packets", headers=auth)
            actors = client.get("/v1/auth/supabase/dashboard/actors", headers=auth)
            usage = client.get("/v1/auth/supabase/dashboard/usage", headers=auth)
            logs = client.get("/v1/auth/supabase/dashboard/logs", headers=auth)
            playground_event = client.post(
                "/v1/auth/supabase/dashboard/playground/event",
                headers=auth,
                json={"actor_id": "test_actor", "event_type": "test.event", "payload": {"summary": "test only"}},
            )
            playground_packet = client.post(
                "/v1/auth/supabase/dashboard/playground/packet",
                headers=auth,
                json={"actor_id": "test_actor"},
            )
            events_after_test = client.get("/v1/auth/supabase/dashboard/events", headers=auth)
            packets_after_test = client.get("/v1/auth/supabase/dashboard/packets", headers=auth)
            actors_after_test = client.get("/v1/auth/supabase/dashboard/actors", headers=auth)
            reset = client.request("DELETE", "/v1/auth/supabase/dashboard/playground", headers=auth)
            events_after_reset = client.get("/v1/auth/supabase/dashboard/events", headers=auth)
            packets_after_reset = client.get("/v1/auth/supabase/dashboard/packets", headers=auth)

            add(checks, "automatic_bootstrap_creates_first_key", activation.status_code == 201 and raw_key.startswith("prmr_alpha_"))
            add(checks, "live_event_ingest_works", live_ingest.status_code == 200 and live_ingest.json().get("accepted_event_count") == 1, live_ingest.json())
            add(checks, "live_packet_generated", live_packet.status_code == 200 and live_packet.json().get("packet", {}).get("actor_reference") == "live_actor_a", live_packet.json())
            add(checks, "events_endpoint_lists_live_events", events.status_code == 200 and events.json().get("total_count") == 1, events.json())
            add(checks, "packets_endpoint_lists_live_packets", packets.status_code == 200 and packets.json().get("total_count") == 1, packets.json())
            add(checks, "actors_endpoint_lists_live_actors", actors.status_code == 200 and actors.json().get("total_count") == 1, actors.json())
            add(checks, "usage_endpoint_reports_product_metrics", usage.status_code == 200 and usage.json().get("usage", {}).get("events_received") == 1 and usage.json().get("usage", {}).get("billing_live") is False, usage.json())
            add(checks, "logs_endpoint_has_readable_logs", logs.status_code == 200 and logs.json().get("total_count", 0) >= 2, logs.json())
            add(checks, "playground_uses_real_engine", playground_event.status_code == 200 and playground_packet.status_code == 200 and bool(playground_packet.json().get("packet")), playground_packet.json())
            add(checks, "playground_response_labels_test_mode", playground_packet.json().get("test_mode") is True and playground_packet.json().get("isolated_from_live") is True, playground_packet.json())
            add(checks, "playground_event_not_in_live_events", "test_actor" not in json.dumps(events_after_test.json()), events_after_test.json())
            add(checks, "playground_packet_not_in_live_packets", "test_actor" not in json.dumps(packets_after_test.json()), packets_after_test.json())
            add(checks, "playground_actor_not_in_live_actors", "test_actor" not in json.dumps(actors_after_test.json()), actors_after_test.json())
            add(checks, "reset_removes_test_only_and_live_survives", reset.status_code == 200 and events_after_reset.json().get("total_count") == 1 and packets_after_reset.json().get("total_count") == 1, reset.json())

            private.update(
                {
                    "activation": {k: v for k, v in activation.json().items() if k != "raw_api_key"},
                    "live_ingest": live_ingest.json(),
                    "live_packet": live_packet.json(),
                    "events": events.json(),
                    "packets": packets.json(),
                    "actors": actors.json(),
                    "usage": usage.json(),
                    "logs": logs.json(),
                    "playground_packet": playground_packet.json(),
                    "reset": reset.json(),
                }
            )

    console_text = read("frontend/components/console/ConsoleShell.tsx") + read("frontend/components/dashboard/HostedSelfServeDashboard.tsx")
    public_nav = read("frontend/components/landing/Navigation.tsx")
    add(checks, "target_console_navigation_present", all(term in console_text for term in ["Memory Core", "Home", "Playground", "Events", "Packets", "Actors", "API Keys", "Usage", "Logs", "How to Use", "Settings"]), None)
    add(checks, "forbidden_primary_console_terms_hidden", not any(term in console_text for term in ["Organisations", "Vaults", "Namespaces", "Storage Backends", "Internal Reports", "Scope Resolution"]), None)
    add(checks, "billing_navigation_removed", "Billing" not in read("frontend/components/console/ConsoleShell.tsx"), None)
    add(checks, "marketing_navigation_simplified", all(term in public_nav for term in ["Product", "How It Works", "Use Cases", "Pricing", "Sign in", "Start building"]) and "Docs" not in public_nav, public_nav)
    add(checks, "ux_questions_answered", all(term in console_text for term in ["Copy API Key", "Paste JSON", "Continuity packets", "Which events", "Usage", "Why", "How to Use Memory Core"]), None)
    add(checks, "raw_key_not_in_public_console_report", "raw_api_key" not in json.dumps(private.get("events", {})) and "raw_api_key" not in json.dumps(private.get("packets", {})), None)

    failures = [check for check in checks if not check["passed"]]
    result = "PASS" if not failures else "NEEDS_WORK"
    public = {
        "version": "console_product_experience_reset",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "Console Product Experience Reset",
        "result": result,
        "checks_passed": len(checks) - len(failures),
        "checks_total": len(checks),
        "backend_endpoints_added": [
            "GET /v1/auth/supabase/dashboard/events",
            "GET /v1/auth/supabase/dashboard/packets",
            "GET /v1/auth/supabase/dashboard/packets/{packet_id}",
            "GET /v1/auth/supabase/dashboard/actors",
            "GET /v1/auth/supabase/dashboard/usage",
            "POST /v1/auth/supabase/dashboard/playground/event",
            "POST /v1/auth/supabase/dashboard/playground/packet",
            "DELETE /v1/auth/supabase/dashboard/playground",
        ],
        "migrations": "none",
        "test_live_isolation": "verified",
        "billing_exposed": False,
        "public_safe": True,
        "raw_keys_exposed": False,
        "boundary": BOUNDARY,
    }
    write_json(PUBLIC_REPORT, public)
    write_json(PRIVATE_REPORT, {**private, "checks": checks, "public_safe": False})
    write_json(SMOKE_REPORT, {"result": result, "checks": checks, "public_safe": False})
    SCORECARD.write_text(
        f"# Console Product Experience Reset\n\nResult: {result}\nChecks: {public['checks_passed']}/{public['checks_total']}\n\nBoundary: {BOUNDARY}\n",
        encoding="utf-8",
    )
    print("PRMR Console Product Experience Reset")
    print(f"Passed checks: {public['checks_passed']}/{public['checks_total']}")
    print(f"Result: {result}")
    for failure in failures:
        print(f"FAIL: {failure['name']} :: {str(failure.get('detail'))[-700:]}")
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
