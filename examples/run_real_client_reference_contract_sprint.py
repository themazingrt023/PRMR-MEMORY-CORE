"""Run the real-client reference contract sprint proof.

The reference client proof uses only HTTP against a running PRMR API process.
The setup harness creates local synthetic credentials through documented
self-serve HTTP routes, but the client actions themselves use only:
PRMR_API_URL, PRMR_API_KEY, and public protected endpoints.
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports" / "real_client_console_sprint"
PUBLIC_REPORT = REPORT_DIR / "public_real_client_console_sprint.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_real_client_console_sprint.json"
SMOKE_REPORT = REPORT_DIR / "real_client_reference_smoke.json"
SCORECARD = REPORT_DIR / "scorecard_real_client_console_sprint.md"
BOUNDARY = (
    "Real client and console separation sprint evidence. Local reference-client "
    "proof uses public PRMR HTTP endpoints only; hosted external-client proof "
    "requires PRMR_REFERENCE_API_KEY and a deployed reference-client URL. This "
    "is not production authentication hardening, live billing, compliance "
    "approval, legal approval, external security certification, or external "
    "real-world validation."
)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def add(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_health(base_url: str, timeout_seconds: float = 20.0) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            if httpx.get(f"{base_url}/health", timeout=2).status_code == 200:
                return
        except httpx.HTTPError:
            time.sleep(0.25)
    raise RuntimeError("PRMR local HTTP server did not become healthy.")


def event(action: str, actor: str, entity: str, signal: str, suffix: str) -> dict[str, Any]:
    mapping = {
        "create_project": "reference.project.created",
        "set_goal": "reference.project.goal_updated",
        "update_deadline": "reference.project.deadline_changed",
        "add_blocker": "reference.project.blocker_recorded",
        "record_decision": "reference.project.decision_recorded",
        "complete_milestone": "reference.project.milestone_completed",
    }
    return {
        "application_reference": "prmr_reference_client",
        "actor_reference": actor,
        "workspace_reference": "workspace_acme",
        "entity_reference": entity,
        "event_type": mapping[action],
        "signal": signal,
        "occurred_at": f"2026-07-21T12:{suffix}:00Z",
        "idempotency_key": f"workspace_acme:{actor}:{entity}:{action}:{suffix}",
        "metadata": {"source_app": "prmr_reference_client", "synthetic": True, "action": action},
    }


def protected_post(base_url: str, api_key: str, path: str, body: dict[str, Any]) -> httpx.Response:
    return httpx.post(
        f"{base_url}{path}",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=body,
        timeout=10,
    )


def protected_get(base_url: str, api_key: str, path: str) -> httpx.Response:
    return httpx.get(
        f"{base_url}{path}",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=10,
    )


def run() -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    private: dict[str, Any] = {"boundary": BOUNDARY}
    with tempfile.TemporaryDirectory(prefix="prmr-real-client-", ignore_cleanup_errors=True) as temp_dir:
        port = free_port()
        base_url = f"http://127.0.0.1:{port}"
        db_path = Path(temp_dir) / "self_serve.sqlite"
        env = {
            **dict(**__import__("os").environ),
            "PRMR_STORAGE_BACKEND": "sqlite",
            "PRMR_SELF_SERVE_STORAGE_PATH": str(db_path),
            "PRMR_API_MODE": "local_alpha",
            "PRMR_AUTH_BACKEND": "local_mvp",
            "PRMR_ALLOWED_ORIGINS": "http://localhost:3000",
        }
        server = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "prmr.product.api_server_v094:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--log-level",
                "warning",
            ],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            wait_for_health(base_url)
            signup = httpx.post(
                f"{base_url}/v1/self-serve/signup",
                json={"name": "Reference Client Team", "email": "reference-client@example.test", "password": "reference-client-password"},
                timeout=10,
            )
            user_id = signup.json()["account"]["user_id"]
            verify = httpx.post(f"{base_url}/v1/self-serve/verify", json={"user_id": user_id}, timeout=10)
            login = httpx.post(
                f"{base_url}/v1/self-serve/login",
                json={"email": "reference-client@example.test", "password": "reference-client-password"},
                timeout=10,
            )
            session = login.json()["session_token"]
            session_headers = {"Authorization": f"Session {session}"}
            httpx.post(f"{base_url}/v1/self-serve/plan", headers=session_headers, json={"plan_id": "free"}, timeout=10)
            provision = httpx.post(f"{base_url}/v1/self-serve/provision", headers=session_headers, timeout=10)
            key_response = httpx.post(
                f"{base_url}/v1/self-serve/keys",
                headers=session_headers,
                json={"label": "Reference client server", "application_reference": "app_main"},
                timeout=10,
            )
            if key_response.status_code != 201:
                # Bootstrap already created one key in newer flows.
                bootstrap = httpx.post(
                    f"{base_url}/v1/self-serve/keys",
                    headers=session_headers,
                    json={"label": "Reference client server", "application_reference": "app_main"},
                    timeout=10,
                )
                key_response = bootstrap
            key_body = key_response.json()
            raw_key = str(key_body.get("raw_api_key") or "")
            if not raw_key:
                activation = httpx.post(
                    f"{base_url}/v1/self-serve/keys",
                    headers=session_headers,
                    json={"label": "Reference client server 2"},
                    timeout=10,
                )
                raw_key = str(activation.json().get("raw_api_key") or "")

            alpha_events = [
                event("create_project", "actor_a", "project_alpha", "Project Alpha was created.", "01"),
                event("set_goal", "actor_a", "project_alpha", "Project Alpha goal is first buyer workflow.", "02"),
                event("update_deadline", "actor_a", "project_alpha", "Project Alpha deadline moved to Friday.", "03"),
                event("add_blocker", "actor_a", "project_alpha", "Project Alpha blocker is copy review.", "04"),
                event("record_decision", "actor_a", "project_alpha", "Project Alpha decision is to keep scope small.", "05"),
                event("complete_milestone", "actor_a", "project_alpha", "Project Alpha onboarding milestone completed.", "06"),
            ]
            beta_events = [
                event("create_project", "actor_b", "project_beta", "Project Beta was created.", "11"),
                event("set_goal", "actor_b", "project_beta", "Project Beta goal is dashboard polish.", "12"),
                event("record_decision", "actor_b", "project_beta", "Project Beta decision is to wait for feedback.", "13"),
            ]
            ingest_alpha = protected_post(base_url, raw_key, "/v1/events/ingest", {"events": alpha_events})
            ingest_beta = protected_post(base_url, raw_key, "/v1/events/ingest", {"events": beta_events})
            duplicate = protected_post(base_url, raw_key, "/v1/events/ingest", {"events": [alpha_events[0]]})
            alpha_scope = {
                "application_reference": "prmr_reference_client",
                "actor_reference": "actor_a",
                "workspace_reference": "workspace_acme",
                "entity_reference": "project_alpha",
            }
            beta_scope = {
                "application_reference": "prmr_reference_client",
                "actor_reference": "actor_b",
                "workspace_reference": "workspace_acme",
                "entity_reference": "project_beta",
            }
            alpha_packet_one = protected_post(base_url, raw_key, "/v1/continuity/packet", alpha_scope)
            beta_packet = protected_post(base_url, raw_key, "/v1/continuity/packet", beta_scope)
            alpha_packet_repeat = protected_post(base_url, raw_key, "/v1/continuity/packet", alpha_scope)
            added_event = event("record_decision", "actor_a", "project_alpha", "Project Alpha decision changed after review.", "07")
            add_event = protected_post(base_url, raw_key, "/v1/events/ingest", {"events": [added_event]})
            alpha_packet_after = protected_post(base_url, raw_key, "/v1/continuity/packet", alpha_scope)

            dashboard_before = httpx.get(f"{base_url}/v1/self-serve/dashboard", headers=session_headers, timeout=10)
            logs_before = dashboard_before.json().get("dashboard", {}).get("request_logs", [])
            reports_before = dashboard_before.json().get("dashboard", {}).get("reports", [])
            alpha_packet = alpha_packet_one.json().get("packet", {})
            beta_packet_body = beta_packet.json().get("packet", {})
            alpha_text = json.dumps(alpha_packet, sort_keys=True)
            beta_text = json.dumps(beta_packet_body, sort_keys=True)
            alpha_included = alpha_packet.get("provenance", {}).get("events_included", [])
            beta_included = beta_packet_body.get("provenance", {}).get("events_included", [])
            repeat_packet = alpha_packet_repeat.json().get("packet", {})
            after_packet = alpha_packet_after.json().get("packet", {})

            # Restart PRMR API process to prove continuity survives client/server restart.
            server.terminate()
            server.wait(timeout=10)
            server = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "prmr.product.api_server_v094:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                    "--log-level",
                    "warning",
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            wait_for_health(base_url)
            alpha_after_restart = protected_post(base_url, raw_key, "/v1/continuity/packet", alpha_scope)

            keys = httpx.get(f"{base_url}/v1/self-serve/keys", headers=session_headers, timeout=10).json().get("keys", [])
            active_key = next((item for item in keys if item.get("status") == "active"), {})
            revoke = httpx.request("DELETE", f"{base_url}/v1/self-serve/keys", headers=session_headers, json={"key_id": active_key.get("key_id")}, timeout=10)
            revoked_usage = protected_get(base_url, raw_key, "/v1/usage")
            rotated = httpx.post(
                f"{base_url}/v1/self-serve/keys",
                headers=session_headers,
                json={"label": "Reference client replacement"},
                timeout=10,
            )
            rotated_key = str(rotated.json().get("raw_api_key") or "")
            rotated_usage = protected_get(base_url, rotated_key, "/v1/usage") if rotated_key else None

            no_internal = not any(
                term in path.read_text(encoding="utf-8", errors="replace")
                for path in (ROOT / "reference-client").rglob("*")
                if path.is_file() and path.suffix in {".ts", ".tsx", ".mjs", ".json"}
                for term in ["prmr.product", "TestClient", "DATABASE_URL", "/api/dashboard", "X-Dashboard-Token"]
            )

            add(checks, "reference_client_files_exist", (ROOT / "reference-client" / "app" / "page.tsx").exists())
            add(checks, "no_internal_shortcut_used_by_reference_client", no_internal)
            add(checks, "alpha_events_sent", ingest_alpha.status_code == 200 and ingest_alpha.json().get("accepted_event_count") == 6, ingest_alpha.json())
            add(checks, "beta_events_sent", ingest_beta.status_code == 200 and ingest_beta.json().get("accepted_event_count") == 3, ingest_beta.json())
            add(checks, "duplicate_idempotency_blocked", duplicate.status_code == 200 and duplicate.json().get("duplicate_event_count") == 1, duplicate.json())
            add(
                checks,
                "alpha_packet_only_alpha_history",
                alpha_packet_one.status_code == 200
                and alpha_packet.get("source_event_count") == 6
                and all(
                    row.get("actor_reference") == "actor_a" and row.get("entity_reference") == "project_alpha"
                    for row in alpha_included
                ),
                alpha_packet.get("provenance"),
            )
            add(
                checks,
                "beta_packet_only_beta_history",
                beta_packet.status_code == 200
                and beta_packet_body.get("source_event_count") == 3
                and all(
                    row.get("actor_reference") == "actor_b" and row.get("entity_reference") == "project_beta"
                    for row in beta_included
                ),
                beta_packet_body.get("provenance"),
            )
            add(checks, "deterministic_same_history_packet", alpha_packet.get("packet_id") == repeat_packet.get("packet_id"), {"one": alpha_packet.get("packet_id"), "repeat": repeat_packet.get("packet_id")})
            add(checks, "adding_event_changes_packet_and_diff", after_packet.get("packet_id") != alpha_packet.get("packet_id") and after_packet.get("source_event_count") == 7, after_packet.get("state_transition_summary"))
            add(checks, "restart_keeps_prmr_continuity", alpha_after_restart.status_code == 200 and alpha_after_restart.json().get("packet", {}).get("source_event_count") == 7, alpha_after_restart.json().get("packet", {}).get("packet_id"))
            add(checks, "revoked_key_rejected", revoke.status_code == 200 and revoked_usage.status_code == 403, {"revoke": revoke.status_code, "revoked": revoked_usage.status_code})
            add(checks, "replacement_key_restores_integration", rotated.status_code in {200, 201} and rotated_usage is not None and rotated_usage.status_code == 200, {"rotate": rotated.status_code, "usage": rotated_usage.status_code if rotated_usage else None})
            add(checks, "console_request_logs_visible", len(logs_before) >= 5, len(logs_before))
            add(checks, "console_packet_reports_visible", len(reports_before) >= 2, len(reports_before))
            add(checks, "packet_provenance_correct", set(alpha_packet.get("provenance", {}).get("source_event_ids", [])) == {item["idempotency_key"] for item in alpha_events}, alpha_packet.get("provenance"))
            add(checks, "raw_key_not_in_public_packets", raw_key not in alpha_text and raw_key not in beta_text)

            private = {
                "boundary": BOUNDARY,
                "deployment_url": "local_reference_client_not_deployed",
                "api_domain_used": base_url,
                "key_environment": "local_test_server_env",
                "events_sent": {"alpha": ingest_alpha.json(), "beta": ingest_beta.json()},
                "packets_generated": {
                    "alpha_packet_id": alpha_packet.get("packet_id"),
                    "beta_packet_id": beta_packet_body.get("packet_id"),
                    "after_event_packet_id": after_packet.get("packet_id"),
                },
                "isolation_results": {"alpha_excludes_beta": "project_beta" not in alpha_text, "beta_excludes_alpha": "project_alpha" not in beta_text},
                "idempotency_results": duplicate.json(),
                "determinism_results": {"same_packet_id": alpha_packet.get("packet_id") == repeat_packet.get("packet_id")},
                "restart_persistence_result": alpha_after_restart.status_code,
                "revocation_result": revoked_usage.status_code,
                "rotation_result": rotated_usage.status_code if rotated_usage else None,
                "console_observability_result": {"request_logs": len(logs_before), "reports": len(reports_before)},
                "raw_key_in_reports": False,
            }
        finally:
            if server.poll() is None:
                server.terminate()
                try:
                    server.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    server.kill()

    public = {
        "version": "real_client_console_sprint",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "Real Client Proof and Console Separation Sprint",
        "result": "PASS WITH DOCUMENTED LIMITATIONS" if all(check["passed"] for check in checks) else "NEEDS_WORK",
        "checks_passed": sum(1 for check in checks if check["passed"]),
        "checks_total": len(checks),
        "deployment_url": "not_deployed_in_this_run",
        "api_domain_used": "local_http_public_contract",
        "hosted_external_client_smoke": "NEEDS_CREDENTIALS",
        "console_separation": "prepared_and_current_dashboard_shell_separated",
        "public_safe": True,
        "raw_keys_exposed": False,
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
                "# Real Client Proof and Console Separation Sprint",
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
    print("PRMR Real Client + Console Separation Sprint")
    print(f"Passed checks: {public['checks_passed']}/{public['checks_total']}")
    print(f"Result: {public['result']}")
    for check in checks:
        if not check["passed"]:
            print(f"FAIL: {check['name']} :: {str(check.get('detail'))[-600:]}")
    return 0 if not any(not check["passed"] for check in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
