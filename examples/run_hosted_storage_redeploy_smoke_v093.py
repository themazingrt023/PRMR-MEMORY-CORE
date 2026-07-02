"""Two-run hosted persistent-storage checkpoint helper for V0.93."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from prmr.product.durable_self_serve_storage_v093 import DurableSelfServeProductV093, env_flag


REPORT = ROOT / "reports" / "v093" / "hosted_storage_redeploy_smoke_v093.json"


def write(payload: dict[str, object]) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    storage_path = os.getenv("PRMR_SELF_SERVE_STORAGE_PATH", "").strip()
    hosted_url = os.getenv("PRMR_HOSTED_API_URL", "").strip()
    verified = env_flag("PRMR_DURABLE_STORAGE_VERIFIED", False)
    checkpoint_id = os.getenv("PRMR_V093_REDEPLOY_CHECKPOINT_ID", "").strip()
    if not storage_path or not hosted_url or not verified:
        payload = {
            "version": "0.93",
            "result": "NEEDS_HOSTED_DURABLE_STORAGE",
            "required_environment": [
                "PRMR_SELF_SERVE_STORAGE_PATH",
                "PRMR_DURABLE_STORAGE_VERIFIED=true",
                "PRMR_HOSTED_API_URL",
            ],
            "raw_key_exposed": False,
            "public_safe": True,
        }
        write(payload)
        print("PRMR V0.93 Hosted Storage Redeploy Smoke")
        print("Result: NEEDS_HOSTED_DURABLE_STORAGE")
        print("Set a verified durable storage path and hosted API URL, then run again.")
        return 0

    product = DurableSelfServeProductV093(
        storage_path,
        api_mode="hosted_alpha",
        durable_storage_verified=True,
    )
    if not product.storage_status["durable_storage_claim_allowed"]:
        payload = {
            "version": "0.93",
            "result": "NEEDS_HOSTED_DURABLE_STORAGE",
            "storage": product.storage_status,
            "reason": "Configured path is not classified as verified hosted durable storage.",
            "raw_key_exposed": False,
            "public_safe": True,
        }
        write(payload)
        print("Result: NEEDS_HOSTED_DURABLE_STORAGE")
        return 0

    if checkpoint_id:
        checkpoint = product.repository.get_audit_metadata(f"redeploy_checkpoint:{checkpoint_id}")
        survived = bool(
            checkpoint
            and checkpoint.get("user_id") in product.product.accounts.accounts
            and checkpoint.get("client_id") in product.product.keys.user_by_client
            and checkpoint.get("key_id") in product.product.api.lifecycle.lifecycle_keys
        )
        result = "PASS_HOSTED_REDEPLOY_CHECKPOINT" if survived else "NEEDS_WORK"
        payload = {
            "version": "0.93",
            "result": result,
            "checkpoint_id": checkpoint_id,
            "checkpoint_survived_redeploy": survived,
            "hosted_url_configured": True,
            "storage": product.storage_status,
            "raw_key_exposed": False,
            "public_safe": True,
        }
        write(payload)
        print("PRMR V0.93 Hosted Storage Redeploy Smoke")
        print(f"Checkpoint: {checkpoint_id}")
        print(f"Result: {result}")
        return 0 if survived else 1

    checkpoint_id = f"checkpoint_v093_{uuid4().hex[:12]}"
    email = f"{checkpoint_id}@example.test"
    password = f"synthetic-checkpoint-{uuid4().hex}"
    signup = product.signup(
        name="Synthetic Hosted Redeploy Checkpoint",
        email=email,
        password=password,
    )
    user_id = signup["account"]["user_id"]
    product.verify_email_local(user_id=user_id)
    login = product.login(email=email, password=password)
    session_token = login["session_token"]
    product.choose_plan(session_token=session_token, plan_id="free")
    scope = product.provision_default_scope(session_token=session_token)["scope"]
    created_key = product.create_key(session_token=session_token, label="Redeploy checkpoint key")
    product.repository.set_audit_metadata(
        f"redeploy_checkpoint:{checkpoint_id}",
        {
            "user_id": user_id,
            "client_id": scope["client_id"],
            "vault_id": scope["vault_id"],
            "namespace": scope["namespace"],
            "key_id": created_key["key_id"],
            "safe_key_preview": created_key["safe_key_preview"],
            "raw_key_persisted": False,
        },
    )
    payload = {
        "version": "0.93",
        "result": "CHECKPOINT_CREATED_REDEPLOY_REQUIRED",
        "checkpoint_id": checkpoint_id,
        "hosted_url_configured": True,
        "storage": product.storage_status,
        "raw_key_exposed": False,
        "next_step": (
            "Redeploy/restart the hosted service, set "
            f"PRMR_V093_REDEPLOY_CHECKPOINT_ID={checkpoint_id}, and rerun this helper."
        ),
        "public_safe": True,
    }
    write(payload)
    print("PRMR V0.93 Hosted Storage Redeploy Smoke")
    print(f"Checkpoint created: {checkpoint_id}")
    print("Result: CHECKPOINT_CREATED_REDEPLOY_REQUIRED")
    print("Redeploy the service and rerun with PRMR_V093_REDEPLOY_CHECKPOINT_ID set.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
