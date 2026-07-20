"""Run product-readiness sprint checks for PRMR Memory Core.

This is implementation evidence for the external engineering handoff path. It
does not claim enterprise readiness, compliance approval, legal approval, or
external security certification.
"""

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


REPORT_DIR = ROOT / "reports" / "product_readiness_sprint"
SMOKE_REPORT = REPORT_DIR / "product_readiness_sprint_smoke.json"
PUBLIC_REPORT = REPORT_DIR / "public_product_readiness_sprint.json"
PRIVATE_REPORT = REPORT_DIR / "private_product_readiness_sprint.json"
SCORECARD = REPORT_DIR / "scorecard_product_readiness_sprint.md"
BOUNDARY = (
    "Product-readiness sprint evidence for entity-scoped PRMR Memory Core API "
    "behavior. This is not enterprise readiness, compliance approval, legal "
    "approval, external security certification, billing readiness, or external "
    "real-world validation."
)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def add(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def provision(client: TestClient, email: str) -> tuple[str, dict[str, Any]]:
    signup = client.post(
        "/v1/self-serve/signup",
        json={"name": "External Engineering Team", "email": email, "password": "product-readiness-password"},
    )
    user_id = signup.json()["account"]["user_id"]
    client.post("/v1/self-serve/verify", json={"user_id": user_id})
    login = client.post("/v1/self-serve/login", json={"email": email, "password": "product-readiness-password"})
    session = login.json()["session_token"]
    headers = {"Authorization": f"Session {session}"}
    client.post("/v1/self-serve/plan", headers=headers, json={"plan_id": "free"})
    scope = client.post("/v1/self-serve/provision", headers=headers).json()["scope"]
    return session, scope


def product_events() -> list[dict[str, Any]]:
    base = {
        "application_reference": "app_product",
        "workspace_reference": "workspace_a",
    }
    return [
        {
            **base,
            "event_type": "project.created",
            "signal": "Project 42 was created.",
            "occurred_at": "2026-07-20T10:00:00Z",
            "actor_reference": "actor_a",
            "entity_reference": "project_42",
            "idempotency_key": "project-42-created",
            "timestamp_index": 1,
        },
        {
            **base,
            "event_type": "project.updated",
            "signal": "Actor A changed the launch date for Project 42.",
            "occurred_at": "2026-07-20T10:01:00Z",
            "actor_reference": "actor_a",
            "entity_reference": "project_42",
            "idempotency_key": "project-42-update-1",
            "timestamp_index": 2,
        },
        {
            **base,
            "event_type": "project.updated",
            "signal": "Actor A changed the launch date again for Project 42.",
            "occurred_at": "2026-07-20T10:02:00Z",
            "actor_reference": "actor_a",
            "entity_reference": "project_42",
            "idempotency_key": "project-42-update-2",
            "timestamp_index": 3,
        },
        {
            **base,
            "event_type": "project.updated",
            "signal": "Actor B updated Project 42 separately.",
            "occurred_at": "2026-07-20T10:03:00Z",
            "actor_reference": "actor_b",
            "entity_reference": "project_42",
            "idempotency_key": "project-42-actor-b-update",
            "timestamp_index": 4,
        },
        {
            **base,
            "event_type": "ticket.updated",
            "signal": "Actor A updated Ticket 77.",
            "occurred_at": "2026-07-20T10:04:00Z",
            "actor_reference": "actor_a",
            "entity_reference": "ticket_77",
            "idempotency_key": "ticket-77-update",
            "timestamp_index": 5,
        },
        {
            "application_reference": "app_product",
            "workspace_reference": "workspace_b",
            "event_type": "project.updated",
            "signal": "Workspace B updated a separate project.",
            "occurred_at": "2026-07-20T10:05:00Z",
            "actor_reference": "actor_a",
            "entity_reference": "project_42",
            "idempotency_key": "workspace-b-project-update",
            "timestamp_index": 6,
        },
    ]


def run() -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    private: dict[str, Any] = {"boundary": BOUNDARY}
    with tempfile.TemporaryDirectory(prefix="prmr-product-ready-", ignore_cleanup_errors=True) as temp_dir:
        db_path = Path(temp_dir) / "self_serve.sqlite"
        product = DurableSelfServeProductV093(db_path)
        with TestClient(create_app_v094(product)) as client:
            live = client.get("/health/live")
            ready = client.get("/health/ready")
            session, scope = provision(client, "product-ready@example.test")
            session_headers = {"Authorization": f"Session {session}"}
            app_create = client.post(
                "/v1/self-serve/applications",
                headers=session_headers,
                json={
                    "name": "Production CRM",
                    "application_reference": "app_product",
                    "environment": "production",
                },
            )
            apps = client.get("/v1/self-serve/applications", headers=session_headers)
            key_response = client.post(
                "/v1/self-serve/keys",
                headers=session_headers,
                json={
                    "label": "Production server",
                    "application_reference": "app_product",
                    "environment": "production",
                },
            )
            raw_key = key_response.json()["raw_api_key"]
            bearer = {"Authorization": f"Bearer {raw_key}"}
            ingest = client.post("/v1/events/ingest", headers=bearer, json={"events": product_events()})
            duplicate = client.post("/v1/events/ingest", headers=bearer, json={"events": [product_events()[1]]})
            global_packet = client.post("/v1/continuity/packet", headers=bearer, json={})
            packet_request = {
                "application_reference": "app_product",
                "actor_reference": "actor_a",
                "workspace_reference": "workspace_a",
                "entity_reference": "project_42",
            }
            scoped_packet = client.post("/v1/continuity/packet", headers=bearer, json=packet_request)
            scoped_body = scoped_packet.json()
            packet = scoped_body.get("packet", {})
            broad_blocked = client.post(
                "/v1/continuity/packet",
                headers=bearer,
                json={"application_reference": "app_product", "workspace_reference": "workspace_a"},
            )
            broad_allowed = client.post(
                "/v1/continuity/packet",
                headers=bearer,
                json={
                    "application_reference": "app_product",
                    "workspace_reference": "workspace_a",
                    "allow_broad_scope": True,
                },
            )
            repeat_packet = client.post("/v1/continuity/packet", headers=bearer, json=packet_request)
            report = client.get(f"/v1/reports/{scoped_body.get('report_id')}", headers=bearer)
            reconstruct = client.post("/v1/memory/reconstruct", headers=bearer, json={"packet_id": packet.get("packet_id")})

            other_session, _ = provision(client, "product-ready-other@example.test")
            other_headers = {"Authorization": f"Session {other_session}"}
            other_key = client.post("/v1/self-serve/keys", headers=other_headers, json={"label": "Other server"}).json()["raw_api_key"]
            cross_report = client.get(f"/v1/reports/{scoped_body.get('report_id')}", headers={"Authorization": f"Bearer {other_key}"})

            reloaded = DurableSelfServeProductV093(db_path)
            reloaded_session_apps = reloaded.list_applications(session_token=session)

            packet_text = json.dumps(packet, sort_keys=True)
            report_text = json.dumps(report.json(), sort_keys=True)
            add(checks, "liveness_endpoint_works", live.status_code == 200 and live.json().get("operation") == "liveness", live.json())
            add(checks, "readiness_endpoint_works", ready.status_code == 200 and ready.json().get("operation") == "readiness", ready.json())
            add(checks, "application_created", app_create.status_code == 201 and app_create.json().get("application", {}).get("application_reference") == "app_product", app_create.json())
            add(checks, "applications_listed", apps.status_code == 200 and any(app.get("application_reference") == "app_product" for app in apps.json().get("applications", [])), apps.json())
            add(checks, "application_key_created_copy_once", key_response.status_code == 201 and key_response.json().get("application_reference") == "app_product" and raw_key.startswith("prmr_alpha_"), {"safe_key_preview": key_response.json().get("safe_key_preview")})
            add(checks, "entity_events_ingested", ingest.status_code == 200 and ingest.json().get("accepted_event_count") == 6, ingest.json())
            add(checks, "duplicate_event_ignored", duplicate.status_code == 200 and duplicate.json().get("duplicate_event_count") == 1 and duplicate.json().get("accepted_event_count") == 0, duplicate.json())
            add(checks, "global_packet_blocked_for_scoped_events", global_packet.status_code == 400 and global_packet.json().get("error", {}).get("code") == "entity_scope_required", global_packet.json())
            add(checks, "entity_scoped_packet_generated", scoped_packet.status_code == 200 and packet.get("source_event_count") == 3 and packet.get("entity_reference") == "project_42", packet)
            add(checks, "actor_b_excluded_from_actor_a_packet", "Actor B" not in packet_text and all("actor_b" not in json.dumps(row) for row in packet.get("provenance", {}).get("events_included", [])), packet.get("provenance"))
            add(checks, "workspace_b_excluded_from_workspace_a_packet", "workspace_b" not in packet_text, packet.get("provenance"))
            add(checks, "ticket_entity_excluded_from_project_packet", "ticket_77" not in packet_text, packet.get("provenance"))
            add(checks, "broad_workspace_requires_explicit_flag", broad_blocked.status_code == 400 and broad_allowed.status_code == 200, {"blocked": broad_blocked.json(), "allowed_count": broad_allowed.json().get("packet", {}).get("source_event_count")})
            add(checks, "packet_id_is_deterministic", repeat_packet.json().get("packet_id") == packet.get("packet_id"), {"first": packet.get("packet_id"), "repeat": repeat_packet.json().get("packet_id")})
            add(checks, "packet_has_required_contract_fields", all(field in packet for field in [
                "packet_id", "report_id", "application_reference", "actor_reference", "workspace_reference", "entity_reference",
                "current_state", "active_information", "latent_information", "lineage_information", "causal_signature",
                "recursive_horizon", "coherence_score", "recoverability_score", "re_emergence_signals", "decayed_signals",
                "repeated_patterns", "state_transition_summary", "event_count", "source_event_count", "first_event_at",
                "last_updated", "packet_version", "algorithm_revision", "public_safe"
            ]), list(packet.keys()))
            add(checks, "provenance_explains_packet", all(field in packet.get("provenance", {}) for field in [
                "source_event_ids", "normalized_event_types", "events_included", "events_excluded",
                "active_classification_basis", "latent_classification_basis", "coherence_factor_breakdown",
                "recoverability_factor_breakdown", "transition_sequence", "diff_from_previous_packet"
            ]), packet.get("provenance"))
            add(checks, "report_and_reconstruct_work", report.status_code == 200 and reconstruct.status_code == 200, {"report": report.status_code, "reconstruct": reconstruct.status_code})
            add(checks, "client_cross_report_denied", cross_report.status_code == 404, cross_report.json())
            add(checks, "applications_persist_after_reload", any(app.get("application_reference") == "app_product" for app in reloaded_session_apps.get("applications", [])), reloaded_session_apps)
            add(checks, "public_outputs_do_not_expose_raw_key", raw_key not in packet_text and raw_key not in report_text, None)

            private = {
                **private,
                "scope": scope,
                "application": app_create.json().get("application"),
                "ingest": ingest.json(),
                "packet": packet,
                "broad_packet": broad_allowed.json().get("packet"),
                "raw_key_in_public_outputs": False,
            }

    public = {
        "version": "product_readiness_sprint",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "Product Readiness Completion Sprint",
        "result": "PASS" if all(check["passed"] for check in checks) else "NEEDS_WORK",
        "checks_passed": sum(1 for check in checks if check["passed"]),
        "checks_total": len(checks),
        "truth_label": "implementation evidence for entity-scoped API readiness, not enterprise certification",
        "boundary": BOUNDARY,
        "implemented_critical_fixes": [
            "entity-scoped packet generation",
            "safe packet provenance",
            "deterministic packet IDs",
            "idempotent event ingest",
            "application object and application-bound key metadata",
            "liveness/readiness endpoints",
        ],
        "remaining_blockers": [
            "large-scale hosted performance measurements",
            "full relational event storage migration",
            "rate limiting and abuse controls beyond existing quota enforcement",
            "production auth/security review",
            "external engineering team validation",
        ],
        "public_safe": True,
    }
    write_json(SMOKE_REPORT, {"checks": checks, "public": public})
    write_json(PUBLIC_REPORT, public)
    write_json(PRIVATE_REPORT, {**private, "checks": checks, "public": public})
    SCORECARD.write_text(
        "\n".join(
            [
                "# Product Readiness Completion Sprint",
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
    return checks, public, private


def main() -> int:
    checks, public, _ = run()
    print("PRMR Product Readiness Sprint")
    print(f"Passed checks: {public['checks_passed']}/{public['checks_total']}")
    print(f"Result: {public['result']}")
    for check in checks:
        if not check["passed"]:
            print(f"FAIL: {check['name']}")
            print(str(check.get("detail"))[-800:])
    return 0 if public["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
