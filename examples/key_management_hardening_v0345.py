import json
import os
import sys
import urllib.error
import urllib.request

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from prmr.security.access_layer import (
    find_client_by_api_key,
    revoke_api_key,
    rotate_api_key_for_client
)

API_URL = "http://127.0.0.1:8000/run"
INPUT_FILE = "inputs/demo_input_v029.json"
REPORT_FOLDER = "reports/v0345"


def call_prmr(api_key, vault_id, namespace):
    with open(INPUT_FILE, "rb") as file:
        body = file.read()

    request = urllib.request.Request(
        API_URL,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-PRMR-API-Key": api_key,
            "X-PRMR-Vault-ID": vault_id,
            "X-PRMR-Namespace": namespace
        }
    )

    try:
        with urllib.request.urlopen(request) as response:
            return {
                "ok": True,
                "status_code": response.status,
                "data": json.loads(response.read().decode("utf-8"))
            }

    except urllib.error.HTTPError as error:
        try:
            error_body = json.loads(error.read().decode("utf-8"))
        except Exception:
            error_body = {"detail": "Could not parse error response."}

        return {
            "ok": False,
            "status_code": error.code,
            "data": error_body
        }

    except Exception as error:
        return {
            "ok": False,
            "status_code": None,
            "data": {"detail": str(error)}
        }


def main():
    os.makedirs(REPORT_FOLDER, exist_ok=True)

    print("PRMR KEY MANAGEMENT HARDENING V0.34.5")
    print("-------------------------------------")

    old_key = input("Paste existing generated API key to test/revoke/rotate: ").strip()
    vault_id = input("Vault ID [test_client_vault]: ").strip() or "test_client_vault"
    namespace = input("Namespace [default]: ").strip() or "default"

    client_record = find_client_by_api_key(old_key)

    if client_record is None:
        print("\nFAILED ❌")
        print("Could not find that API key in local config.")
        return

    client_id = client_record["client_id"]

    print("\nClient found:")
    print("Client ID:", client_id)
    print("Client Name:", client_record.get("client_name"))
    print("Plan:", client_record.get("plan"))
    print("Status:", client_record.get("status"))

    print("\n1. Testing old key before revoke...")
    old_key_before = call_prmr(old_key, vault_id, namespace)

    print("Status:", old_key_before["status_code"])
    print("Works before revoke:", old_key_before["ok"])

    print("\n2. Revoking old key...")
    revoke_result = revoke_api_key(
        old_key,
        reason="V0.34.5 hardening test"
    )

    print("Revoked:", revoke_result.get("revoked"))

    print("\n3. Testing old key after revoke...")
    old_key_after = call_prmr(old_key, vault_id, namespace)

    print("Status:", old_key_after["status_code"])
    print("Blocked after revoke:", old_key_after["status_code"] == 403)

    print("\n4. Rotating key for same client...")
    rotate_result = rotate_api_key_for_client(client_id)

    print("Rotated:", rotate_result.get("rotated"))

    new_key = rotate_result.get("api_key")

    print("\n5. Testing new rotated key...")
    new_key_test = call_prmr(new_key, vault_id, namespace)

    print("Status:", new_key_test["status_code"])
    print("New key works:", new_key_test["ok"])
    print("All reconstructions verified:", new_key_test["data"].get("all_reconstructions_verified") if new_key_test["ok"] else None)

    all_passed = (
        old_key_before["ok"] is True
        and revoke_result.get("revoked") is True
        and old_key_after["status_code"] == 403
        and rotate_result.get("rotated") is True
        and new_key_test["ok"] is True
        and new_key_test["data"].get("all_reconstructions_verified") is True
    )

    report = {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": "0.34.5",
        "report_type": "private_key_management_hardening",
        "client_id": client_id,
        "vault_id": vault_id,
        "namespace": namespace,
        "all_key_management_checks_passed": all_passed,
        "checks": {
            "old_key_worked_before_revoke": old_key_before["ok"],
            "old_key_revoked": revoke_result.get("revoked"),
            "old_key_blocked_after_revoke": old_key_after["status_code"] == 403,
            "new_key_rotated": rotate_result.get("rotated"),
            "new_key_works": new_key_test["ok"],
            "new_key_reconstruction_verified": new_key_test["data"].get("all_reconstructions_verified") if new_key_test["ok"] else False
        },
        "audit_paths": {
            "revoke_audit_path": revoke_result.get("audit_path"),
            "rotate_audit_path": rotate_result.get("audit_path")
        },
        "protected_note": "Internal key hardening report. Do not publish raw key details."
    }

    report_path = os.path.join(REPORT_FOLDER, "key_management_hardening_v0345.json")

    with open(report_path, "w", encoding="utf-8") as file:
        json.dump(report, file, indent=4)

    print("\nRESULT:")
    print("All key management checks passed:", all_passed)

    print("\nREPORT CREATED:")
    print(report_path)

    if all_passed:
        print("\nV0.34.5 key management hardening passed ✅")
        print("IMPORTANT: The old key is revoked. Use the new rotated key from local config/output if needed.")
    else:
        print("\nV0.34.5 did not fully pass ❌")


if __name__ == "__main__":
    main()