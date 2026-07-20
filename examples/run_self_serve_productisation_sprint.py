"""Run the PRMR self-serve productisation sprint smoke flow.

Truth label: local/deployable self-serve activation evidence only. This does
not claim production auth hardening, live billing, compliance approval, legal
approval, external security certification, or external real-world validation.
"""

from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from prmr.product.api_server_v094 import create_app_v094
from prmr.product.durable_self_serve_storage_v093 import DurableSelfServeProductV093
from prmr.product.supabase_auth_bridge_v095 import (
    FixtureSupabaseIdentityVerifier,
    SupabaseAuthBridgeV095,
    SupabaseIdentity,
)


REPORT_DIR = ROOT / "reports" / "self_serve_productisation_sprint"
PUBLIC_REPORT = REPORT_DIR / "public_self_serve_productisation_sprint.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_self_serve_productisation_sprint.json"
SMOKE_REPORT = REPORT_DIR / "self_serve_productisation_smoke.json"
SCORECARD = REPORT_DIR / "scorecard_self_serve_productisation_sprint.md"
BOUNDARY = (
    "Self-serve productisation sprint evidence for first-run activation, "
    "sandbox key issuing, event ingest, continuity packets, usage, logs, and "
    "dashboard state. This is not production authentication hardening, live "
    "billing, compliance approval, legal approval, external security "
    "certification, or external real-world validation."
)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def add(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def synthetic_event() -> dict[str, Any]:
    return {
        "event_type": "demo.task_completed",
        "signal": "A synthetic dashboard user completed the first PRMR sandbox task.",
        "application_reference": "app_main",
        "actor_reference": "user_123",
        "workspace_reference": "workspace_demo",
        "entity_reference": "task_demo",
        "occurred_at": "2026-07-20T12:00:00Z",
        "metadata": {"synthetic": True, "source": "self_serve_productisation_sprint"},
        "idempotency_key": "self-serve-first-event-001",
    }


def run() -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    timings: dict[str, float] = {}
    with tempfile.TemporaryDirectory(prefix="prmr-self-serve-sprint-", ignore_cleanup_errors=True) as temp_dir:
        product = DurableSelfServeProductV093(Path(temp_dir) / "self_serve.sqlite")
        verifier = FixtureSupabaseIdentityVerifier(
            {
                "token_stranger": SupabaseIdentity(
                    subject="supabase-user-stranger",
                    email="stranger@example.test",
                    email_confirmed_at="2026-07-20T11:00:00Z",
                    role="authenticated",
                    display_name="Stranger Developer",
                ),
                "token_other": SupabaseIdentity(
                    subject="supabase-user-other",
                    email="other@example.test",
                    email_confirmed_at="2026-07-20T11:05:00Z",
                    role="authenticated",
                    display_name="Other Developer",
                ),
            }
        )
        bridge = SupabaseAuthBridgeV095(product, verifier)
        with TestClient(create_app_v094(product, bridge)) as client:
            health_started = time.perf_counter()
            health = client.get("/health")
            timings["health_ms"] = round((time.perf_counter() - health_started) * 1000, 2)

            activation_started = time.perf_counter()
            activation = client.post(
                "/v1/auth/supabase/activate",
                headers={"Authorization": "Bearer token_stranger"},
                json={"plan_id": "free"},
            )
            timings["activation_ms"] = round((time.perf_counter() - activation_started) * 1000, 2)
            activation_body = activation.json()
            raw_key = str(activation_body.get("raw_api_key") or "")
            scope = activation_body.get("scope") or {}
            application = activation_body.get("application") or {}

            second_activation = client.post(
                "/v1/auth/supabase/activate",
                headers={"Authorization": "Bearer token_stranger"},
                json={"plan_id": "free"},
            )
            second_body = second_activation.json()
            bearer = {"Authorization": f"Bearer {raw_key}"}

            ingest_started = time.perf_counter()
            ingest = client.post("/v1/events/ingest", headers=bearer, json={"events": [synthetic_event()]})
            timings["ingest_ms"] = round((time.perf_counter() - ingest_started) * 1000, 2)

            packet_request = {
                "application_reference": "app_main",
                "actor_reference": "user_123",
                "workspace_reference": "workspace_demo",
                "entity_reference": "task_demo",
            }
            packet_started = time.perf_counter()
            packet = client.post("/v1/continuity/packet", headers=bearer, json=packet_request)
            timings["packet_ms"] = round((time.perf_counter() - packet_started) * 1000, 2)
            packet_body = packet.json()
            report_id = packet_body.get("report_id")

            usage = client.get("/v1/usage", headers=bearer)
            report = client.get(f"/v1/reports/{report_id}", headers=bearer)
            dashboard = client.get(
                "/v1/auth/supabase/dashboard",
                headers={"Authorization": "Bearer token_stranger"},
            )
            logs = client.get(
                "/v1/auth/supabase/dashboard/logs",
                headers={"Authorization": "Bearer token_stranger"},
            )
            reports = client.get(
                "/v1/auth/supabase/dashboard/reports",
                headers={"Authorization": "Bearer token_stranger"},
            )

            other_activation = client.post(
                "/v1/auth/supabase/activate",
                headers={"Authorization": "Bearer token_other"},
                json={"plan_id": "free"},
            )
            other_key = str(other_activation.json().get("raw_api_key") or "")
            cross_report = client.get(
                f"/v1/reports/{report_id}",
                headers={"Authorization": f"Bearer {other_key}"},
            )

            public_text = json.dumps(
                {
                    "activation": {k: v for k, v in activation_body.items() if k != "raw_api_key"},
                    "dashboard": dashboard.json(),
                    "reports": reports.json(),
                    "report": report.json(),
                },
                sort_keys=True,
            )
            add(checks, "health_reports_self_serve_activation", health.status_code == 200 and "POST /v1/auth/supabase/activate" in json.dumps(health.json()), health.json().get("supabase_auth_routes"))
            add(checks, "supabase_verified_user_activates", activation.status_code == 201 and activation_body.get("provisioned") is True, activation_body)
            add(checks, "default_scope_created", all(scope.get(field) for field in ["client_id", "vault_id", "namespace"]), scope)
            add(checks, "default_sandbox_application_created", application.get("application_reference") == "app_main" and application.get("environment") == "sandbox", application)
            add(checks, "copy_once_key_created", raw_key.startswith("prmr_alpha_") and activation_body.get("raw_api_key_returned_once") is True, activation_body.get("safe_key_preview"))
            add(checks, "second_activation_does_not_return_raw_key", second_activation.status_code == 200 and not second_body.get("raw_api_key") and second_body.get("api_key_created") is False, second_body.get("safe_key_preview"))
            add(checks, "event_ingest_accepts_inferred_scope", ingest.status_code == 200 and ingest.json().get("accepted_event_count") == 1, ingest.json())
            add(checks, "continuity_packet_generated", packet.status_code == 200 and packet_body.get("packet", {}).get("entity_reference") == "task_demo", packet_body.get("packet", {}))
            add(checks, "usage_visible_for_owner", usage.status_code == 200 and usage.json().get("usage", {}).get("by_client") is None, usage.json())
            add(checks, "report_fetch_works_for_owner", report.status_code == 200 and report.json().get("report", {}).get("public_safe") is True, report.json())
            add(checks, "dashboard_shows_usage_logs_reports", dashboard.status_code == 200 and logs.json().get("total_count", 0) >= 2 and reports.json().get("total_count", 0) >= 1, {"logs": logs.json().get("total_count"), "reports": reports.json().get("total_count")})
            add(checks, "activation_funnel_tracks_first_run", dashboard.json().get("dashboard", {}).get("activation", {}).get("completed_count", 0) >= 6, dashboard.json().get("dashboard", {}).get("activation"))
            add(checks, "cross_client_report_denied", cross_report.status_code == 404, cross_report.json())
            add(checks, "public_outputs_hide_raw_key", raw_key not in public_text and other_key not in public_text, None)
            add(checks, "no_live_billing_claim", dashboard.json().get("dashboard", {}).get("billing", {}).get("live") is False, dashboard.json().get("dashboard", {}).get("billing"))

            private = {
                "boundary": BOUNDARY,
                "timings_ms": timings,
                "activation": activation_body,
                "second_activation": second_body,
                "scope": scope,
                "application": application,
                "ingest": ingest.json(),
                "packet": packet_body,
                "usage": usage.json(),
                "dashboard": dashboard.json(),
                "logs": logs.json(),
                "reports": reports.json(),
                "cross_report": cross_report.json(),
                "raw_key_length": len(raw_key),
                "raw_key_written_to_public_report": False,
            }

    public = {
        "version": "self_serve_productisation_sprint",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "Self-Serve Productisation Sprint",
        "result": "PASS" if all(check["passed"] for check in checks) else "NEEDS_WORK",
        "checks_passed": sum(1 for check in checks if check["passed"]),
        "checks_total": len(checks),
        "truth_label": "first-run self-serve activation evidence using synthetic data",
        "flow_verified": [
            "verified identity activation",
            "automatic client/vault/namespace bootstrap",
            "default sandbox application",
            "copy-once sandbox key",
            "event ingest",
            "continuity packet generation",
            "usage/log/report dashboard visibility",
            "cross-client report denial",
        ],
        "timings_ms": timings,
        "public_safe": True,
        "raw_keys_exposed": False,
        "billing_live": False,
        "boundary": BOUNDARY,
    }
    return checks, public, private


def main() -> int:
    checks, public, private = run()
    write_json(PUBLIC_REPORT, public)
    write_json(PRIVATE_REPORT, private)
    write_json(SMOKE_REPORT, {"result": public["result"], "checks": checks, "public_safe": False})
    SCORECARD.write_text(
        "\n".join(
            [
                "# Self-Serve Productisation Sprint Scorecard",
                "",
                f"Result: {public['result']}",
                f"Checks: {public['checks_passed']}/{public['checks_total']}",
                "",
                f"Boundary: {BOUNDARY}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print("PRMR Self-Serve Productisation Sprint")
    print(f"Passed checks: {public['checks_passed']}/{public['checks_total']}")
    print(f"Result: {public['result']}")
    if public["result"] != "PASS":
        for check in checks:
            if not check["passed"]:
                print(f"FAIL: {check['name']} :: {str(check.get('detail'))[-500:]}")
    return 0 if public["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
