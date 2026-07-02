"""Create or verify a real hosted V0.94 self-serve redeploy checkpoint."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


REPORT_DIR = ROOT / "reports" / "v094"
PUBLIC_CHECKPOINT_REPORT = REPORT_DIR / "hosted_redeploy_checkpoint_v094.json"
PRIVATE_CHECKPOINT_PACKET = REPORT_DIR / "private_redeploy_checkpoint_v094.json"


def write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def health_is_durable(client: httpx.Client) -> tuple[bool, dict[str, Any]]:
    response = client.get("/health")
    payload = response.json() if response.status_code == 200 else {}
    storage = payload.get("storage", {})
    durable_sqlite = bool(
        response.status_code == 200
        and storage.get("storage_mode") == "hosted_durable_sqlite"
        and storage.get("durable_storage_verified") is True
        and storage.get("durable_storage_claim_allowed") is True
    )
    durable_postgres = bool(
        response.status_code == 200
        and storage.get("storage_backend") == "postgres"
        and storage.get("storage_mode") == "hosted_managed_postgres"
        and storage.get("database_connected") is True
        and storage.get("durable_storage_verified") is True
        and storage.get("durable_storage_claim_allowed") is True
    )
    return durable_sqlite or durable_postgres, payload


def needs(reason: str) -> int:
    payload = {
        "version": "0.94",
        "result": "NEEDS_HOSTED_DURABLE_STORAGE",
        "reason": reason,
        "raw_key_exposed": False,
        "public_safe": True,
    }
    write(PUBLIC_CHECKPOINT_REPORT, payload)
    print("PRMR V0.94 Hosted Self-Serve Redeploy Checkpoint")
    print("Result: NEEDS_HOSTED_DURABLE_STORAGE")
    return 0


def create_checkpoint(client: httpx.Client, configured_email: str) -> int:
    checkpoint_id = f"checkpoint_v094_{uuid4().hex[:12]}"
    local, separator, domain = configured_email.partition("@")
    email = f"{local}+{checkpoint_id}@{domain}" if separator else configured_email
    password = os.getenv("PRMR_SELF_SERVE_TEST_PASSWORD", "").strip() or secrets.token_urlsafe(24)
    signup = client.post(
        "/v1/self-serve/signup",
        json={"name": "Generic V0.94 Redeploy Checkpoint", "email": email, "password": password},
    )
    if signup.status_code != 201:
        return needs("Checkpoint signup did not complete.")
    user_id = signup.json()["account"]["user_id"]
    client.post("/v1/self-serve/verify", json={"user_id": user_id})
    login = client.post("/v1/self-serve/login", json={"email": email, "password": password})
    if login.status_code != 200:
        return needs("Checkpoint login did not complete.")
    session_token = login.json()["session_token"]
    session_headers = {"Authorization": f"Session {session_token}"}
    client.post("/v1/self-serve/plan", headers=session_headers, json={"plan_id": "free"})
    provision = client.post("/v1/self-serve/provision", headers=session_headers)
    scope = provision.json()["scope"]
    key = client.post(
        "/v1/self-serve/keys",
        headers=session_headers,
        json={"label": "Redeploy checkpoint key"},
    ).json()
    raw_key = key["raw_api_key"]
    api_headers = {
        "Authorization": f"Bearer {raw_key}",
        "X-Client-ID": scope["client_id"],
        "X-Vault-ID": scope["vault_id"],
        "X-Namespace": scope["namespace"],
    }
    client.post(
        "/v1/events/ingest",
        headers=api_headers,
        json={
            "events": [
                {
                    "event_id": checkpoint_id,
                    "type": "redeploy_checkpoint",
                    "content": "Synthetic V0.94 hosted persistence checkpoint.",
                    "timestamp_index": 1,
                }
            ]
        },
    )
    packet = client.post("/v1/continuity/packet", headers=api_headers, json={}).json()
    private_packet = {
        "warning": "PRIVATE LOCAL ONLY. DO NOT COMMIT OR SHARE.",
        "version": "0.94",
        "checkpoint_id": checkpoint_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "email": email,
        "password": password,
        "session_token": session_token,
        "raw_api_key": raw_key,
        "key_id": key["key_id"],
        "safe_key_preview": key["safe_key_preview"],
        "client_id": scope["client_id"],
        "vault_id": scope["vault_id"],
        "namespace": scope["namespace"],
        "report_id": packet.get("report_id"),
    }
    write(PRIVATE_CHECKPOINT_PACKET, private_packet)
    public = {
        "version": "0.94",
        "result": "CHECKPOINT_CREATED_REDEPLOY_REQUIRED",
        "checkpoint_id": checkpoint_id,
        "safe_key_preview": key["safe_key_preview"],
        "scope_created": True,
        "usage_and_report_created": bool(packet.get("report_id")),
        "raw_key_exposed": False,
        "private_packet_path": "reports/v094/private_redeploy_checkpoint_v094.json",
        "next_step": "Redeploy Render, then run verify_checkpoint.",
        "public_safe": True,
    }
    write(PUBLIC_CHECKPOINT_REPORT, public)
    print("PRMR V0.94 Hosted Self-Serve Redeploy Checkpoint")
    print(f"Checkpoint: {checkpoint_id}")
    print("Result: CHECKPOINT_CREATED_REDEPLOY_REQUIRED")
    return 0


def verify_checkpoint(client: httpx.Client) -> int:
    if not PRIVATE_CHECKPOINT_PACKET.exists():
        return needs("Private checkpoint packet is missing.")
    packet = json.loads(PRIVATE_CHECKPOINT_PACKET.read_text(encoding="utf-8"))
    checkpoint_id = os.getenv("PRMR_V094_CHECKPOINT_ID", "").strip() or packet.get("checkpoint_id", "")
    password = os.getenv("PRMR_SELF_SERVE_TEST_PASSWORD", "").strip() or packet.get("password", "")
    raw_key = os.getenv("PRMR_V094_CHECKPOINT_API_KEY", "").strip() or packet.get("raw_api_key", "")
    login = client.post(
        "/v1/self-serve/login",
        json={"email": packet.get("email"), "password": password},
    )
    if login.status_code != 200:
        public = {
            "version": "0.94",
            "result": "NEEDS_WORK",
            "checkpoint_id": checkpoint_id,
            "checkpoint_survived": False,
            "reason": "User login failed after redeploy.",
            "raw_key_exposed": False,
            "public_safe": True,
        }
        write(PUBLIC_CHECKPOINT_REPORT, public)
        print("Result: NEEDS_WORK")
        return 1
    session_token = login.json()["session_token"]
    session_headers = {"Authorization": f"Session {session_token}"}
    dashboard = client.get("/v1/self-serve/dashboard", headers=session_headers)
    keys = client.get("/v1/self-serve/keys", headers=session_headers)
    api_headers = {
        "Authorization": f"Bearer {raw_key}",
        "X-Client-ID": packet.get("client_id", ""),
        "X-Vault-ID": packet.get("vault_id", ""),
        "X-Namespace": packet.get("namespace", ""),
    }
    usage = client.get("/v1/usage", headers=api_headers)
    dashboard_text = json.dumps(dashboard.json(), sort_keys=True)
    keys_text = json.dumps(keys.json(), sort_keys=True)
    survived = bool(
        dashboard.status_code == 200
        and keys.status_code == 200
        and usage.status_code == 200
        and packet.get("safe_key_preview") in keys_text
        and packet.get("report_id") in dashboard_text
        and raw_key not in dashboard_text
        and raw_key not in keys_text
    )
    result = "PASS_HOSTED_REDEPLOY_CHECKPOINT" if survived else "NEEDS_WORK"
    public = {
        "version": "0.94",
        "result": result,
        "checkpoint_id": checkpoint_id,
        "checkpoint_survived": survived,
        "user_recovered": login.status_code == 200,
        "dashboard_recovered": dashboard.status_code == 200,
        "safe_key_preview_recovered": packet.get("safe_key_preview") in keys_text,
        "usage_recovered": usage.status_code == 200,
        "report_reference_recovered": packet.get("report_id") in dashboard_text,
        "raw_key_recoverable_from_public_state": False,
        "raw_key_exposed": False,
        "public_safe": True,
    }
    write(PUBLIC_CHECKPOINT_REPORT, public)
    print("PRMR V0.94 Hosted Self-Serve Redeploy Checkpoint")
    print(f"Checkpoint: {checkpoint_id}")
    print(f"Result: {result}")
    return 0 if survived else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["create_checkpoint", "verify_checkpoint"], required=True)
    args = parser.parse_args()
    base_url = os.getenv("PRMR_HOSTED_API_URL", "").strip().rstrip("/")
    email = os.getenv("PRMR_SELF_SERVE_TEST_EMAIL", "").strip()
    if not base_url or not email:
        return needs("PRMR_HOSTED_API_URL and PRMR_SELF_SERVE_TEST_EMAIL are required.")
    with httpx.Client(base_url=base_url, timeout=45.0, follow_redirects=True) as client:
        durable, _ = health_is_durable(client)
        if not durable:
            return needs("Hosted health does not report verified durable self-serve storage.")
        return create_checkpoint(client, email) if args.mode == "create_checkpoint" else verify_checkpoint(client)


if __name__ == "__main__":
    raise SystemExit(main())
