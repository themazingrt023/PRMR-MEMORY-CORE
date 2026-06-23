import json
import re
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from datetime import datetime
from fastapi import HTTPException

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from prmr_api import run_prmr
from prmr.security.access_layer import (
    create_client,
    revoke_api_key,
    rotate_api_key_for_client
)


API_URL = "http://127.0.0.1:8000/run"
INPUT_FILE = Path("inputs/demo_input_v029.json")
REPORT_DIR = Path("reports/v0363")
REPORT_PATH = REPORT_DIR / "security_isolation_deep_test_v0363.json"


def call_prmr(api_key=None, vault_id=None, namespace="default"):
    if not INPUT_FILE.exists():
        return {
            "ok": False,
            "status_code": None,
            "data": {"detail": f"Missing input file: {INPUT_FILE}"}
        }

    try:
        payload = json.loads(INPUT_FILE.read_text(encoding="utf-8"))
        response_data = run_prmr(
            payload=payload,
            x_prmr_api_key=api_key,
            x_prmr_vault_id=vault_id or "default_vault",
            x_prmr_namespace=namespace or "default"
        )
        return {
            "ok": True,
            "status_code": 200,
            "data": response_data
        }

    except HTTPException as error:
        return {
            "ok": False,
            "status_code": error.status_code,
            "data": {"detail": error.detail}
        }

    except Exception as error:
        return {
            "ok": False,
            "status_code": None,
            "data": {"detail": str(error)}
        }


def public_report_is_safe(public_report_path):
    if not public_report_path:
        return {
            "passed": False,
            "reason": "No public report path returned."
        }

    path = Path(public_report_path)

    if not path.exists():
        return {
            "passed": False,
            "reason": f"Public report file does not exist: {public_report_path}"
        }

    text = path.read_text(encoding="utf-8", errors="ignore")
    lowered = text.lower()

    # These are genuinely private/internal concepts that should not appear in public reports.
    forbidden_terms = [
        "compressed_package",
        "internal_rule_data",
        "private_internal",
        "x-prmr-api-key",
        "api_key",
        "secret"
    ]

    forbidden_terms_found = [
        term for term in forbidden_terms
        if term.lower() in lowered
    ]

    # Smart key detection:
    # Do NOT fail on safe fields like "prmr_size_estimate".
    # Only fail on actual-looking API keys such as prmr_ + long random token.
    api_key_pattern = re.compile(r"prmr_[A-Za-z0-9]{20,}")
    api_key_matches = api_key_pattern.findall(text)

    return {
        "passed": len(forbidden_terms_found) == 0 and len(api_key_matches) == 0,
        "public_report_path": public_report_path,
        "forbidden_terms_found": forbidden_terms_found,
        "api_key_like_matches_found": len(api_key_matches),
        "note": "Safe PRMR metric names such as prmr_size_estimate are allowed. Actual API-key-like values are blocked."
    }


def logs_do_not_store_raw_keys(keys):
    log_root = Path("logs")

    if not log_root.exists():
        return {
            "passed": True,
            "reason": "No logs folder found."
        }

    exposed = []

    for file_path in log_root.rglob("*"):
        if not file_path.is_file():
            continue

        try:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        for key_name, key_value in keys.items():
            if key_value and key_value in text:
                exposed.append({
                    "key_name": key_name,
                    "file": str(file_path)
                })

    return {
        "passed": len(exposed) == 0,
        "raw_key_exposures": exposed
    }


def main():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    print("PRMR V0.36.3 SECURITY + CLIENT ISOLATION DEEP TEST")
    print("---------------------------------------------------")

    timestamp = int(time.time())

    client_a = create_client(
        client_name=f"V0363 Client A {timestamp}",
        plan="developer",
        vault_id=f"vault_v0363_client_a_{timestamp}"
    )

    client_b = create_client(
        client_name=f"V0363 Client B {timestamp}",
        plan="developer",
        vault_id=f"vault_v0363_client_b_{timestamp}"
    )

    client_a_key = client_a["api_key"]
    client_b_key = client_b["api_key"]
    client_a_vault = client_a["vault_id"]
    client_b_vault = client_b["vault_id"]
    namespace = "default"

    print("Created Client A:", client_a["client_id"], client_a_vault)
    print("Created Client B:", client_b["client_id"], client_b_vault)
    print()

    checks = []

    def add_check(name, passed, details):
        checks.append({
            "name": name,
            "passed": bool(passed),
            "details": details
        })

        status = "PASS" if passed else "FAIL"
        print(name + ":", status)

    # 1. Valid Client A request.
    client_a_valid = call_prmr(
        api_key=client_a_key,
        vault_id=client_a_vault,
        namespace=namespace
    )

    add_check(
        "client_a_valid_key_own_vault_returns_200",
        client_a_valid["ok"] and client_a_valid["status_code"] == 200,
        {
            "status_code": client_a_valid["status_code"],
            "client_id": client_a_valid["data"].get("client_id"),
            "vault_id": client_a_valid["data"].get("vault_id"),
            "all_reconstructions_verified": client_a_valid["data"].get("all_reconstructions_verified")
        }
    )

    # 2. Valid Client B request.
    client_b_valid = call_prmr(
        api_key=client_b_key,
        vault_id=client_b_vault,
        namespace=namespace
    )

    add_check(
        "client_b_valid_key_own_vault_returns_200",
        client_b_valid["ok"] and client_b_valid["status_code"] == 200,
        {
            "status_code": client_b_valid["status_code"],
            "client_id": client_b_valid["data"].get("client_id"),
            "vault_id": client_b_valid["data"].get("vault_id"),
            "all_reconstructions_verified": client_b_valid["data"].get("all_reconstructions_verified")
        }
    )

    # 3. Client A cannot access Client B vault.
    client_a_to_b = call_prmr(
        api_key=client_a_key,
        vault_id=client_b_vault,
        namespace=namespace
    )

    add_check(
        "client_a_cannot_access_client_b_vault",
        client_a_to_b["status_code"] == 403,
        {
            "status_code": client_a_to_b["status_code"],
            "response": client_a_to_b["data"]
        }
    )

    # 4. Client B cannot access Client A vault.
    client_b_to_a = call_prmr(
        api_key=client_b_key,
        vault_id=client_a_vault,
        namespace=namespace
    )

    add_check(
        "client_b_cannot_access_client_a_vault",
        client_b_to_a["status_code"] == 403,
        {
            "status_code": client_b_to_a["status_code"],
            "response": client_b_to_a["data"]
        }
    )

    # 5. Missing API key blocked.
    missing_key = call_prmr(
        api_key=None,
        vault_id=client_a_vault,
        namespace=namespace
    )

    add_check(
        "missing_api_key_blocked",
        missing_key["status_code"] in (401, 403),
        {
            "status_code": missing_key["status_code"],
            "response": missing_key["data"]
        }
    )

    # 6. Invalid API key blocked.
    invalid_key = call_prmr(
        api_key="prmr_invalid_key_v0363",
        vault_id=client_a_vault,
        namespace=namespace
    )

    add_check(
        "invalid_api_key_blocked",
        invalid_key["status_code"] in (401, 403),
        {
            "status_code": invalid_key["status_code"],
            "response": invalid_key["data"]
        }
    )

    # 7. Revoke Client A key.
    revoke_result = revoke_api_key(
        client_a_key,
        reason="V0.36.3 deep security isolation test"
    )

    revoked_call = call_prmr(
        api_key=client_a_key,
        vault_id=client_a_vault,
        namespace=namespace
    )

    add_check(
        "revoked_client_a_key_blocked",
        revoke_result.get("revoked") is True and revoked_call["status_code"] == 403,
        {
            "revoke_result": {
                "revoked": revoke_result.get("revoked"),
                "client_id": revoke_result.get("client_id"),
                "audit_path": revoke_result.get("audit_path")
            },
            "status_code_after_revoke": revoked_call["status_code"],
            "response_after_revoke": revoked_call["data"]
        }
    )

    # 8. Rotate Client A key.
    rotate_result = rotate_api_key_for_client(client_a["client_id"])
    rotated_key = rotate_result.get("api_key")

    rotated_call = call_prmr(
        api_key=rotated_key,
        vault_id=client_a_vault,
        namespace=namespace
    )

    add_check(
        "rotated_client_a_new_key_works",
        rotate_result.get("rotated") is True
        and rotated_call["ok"]
        and rotated_call["status_code"] == 200
        and rotated_call["data"].get("all_reconstructions_verified") is True,
        {
            "rotate_result": {
                "rotated": rotate_result.get("rotated"),
                "client_id": rotate_result.get("client_id"),
                "client_name": rotate_result.get("client_name"),
                "allowed_vaults": rotate_result.get("allowed_vaults"),
                "plan": rotate_result.get("plan"),
                "audit_path": rotate_result.get("audit_path")
            },
            "status_code": rotated_call["status_code"],
            "all_reconstructions_verified": rotated_call["data"].get("all_reconstructions_verified")
        }
    )

    # 9. Old key remains blocked after rotation.
    old_after_rotation = call_prmr(
        api_key=client_a_key,
        vault_id=client_a_vault,
        namespace=namespace
    )

    add_check(
        "old_client_a_key_still_blocked_after_rotation",
        old_after_rotation["status_code"] == 403,
        {
            "status_code": old_after_rotation["status_code"],
            "response": old_after_rotation["data"]
        }
    )

    # 10. Public report safety.
    public_report_path = rotated_call["data"].get("public_report_path") if rotated_call["ok"] else None
    public_safety = public_report_is_safe(public_report_path)

    add_check(
        "public_report_exposes_no_private_internals_or_keys",
        public_safety["passed"],
        public_safety
    )

    # 11. Logs do not store raw generated keys.
    log_safety = logs_do_not_store_raw_keys({
        "client_a_original_key": client_a_key,
        "client_a_rotated_key": rotated_key,
        "client_b_key": client_b_key
    })

    add_check(
        "logs_do_not_store_raw_full_api_keys",
        log_safety["passed"],
        log_safety
    )

    passed_count = sum(1 for check in checks if check["passed"])
    total_count = len(checks)
    all_passed = passed_count == total_count

    report = {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": "0.36.3",
        "report_type": "security_client_isolation_deep_test",
        "public_safe": False,
        "timestamp": datetime.now().isoformat(),
        "all_security_checks_passed": all_passed,
        "passed_checks": passed_count,
        "total_checks": total_count,
        "checks": checks,
        "client_test_summary": {
            "client_a_id": client_a["client_id"],
            "client_b_id": client_b["client_id"],
            "client_a_vault": client_a_vault,
            "client_b_vault": client_b_vault,
            "namespace": namespace
        },
        "protected_note": "This report does not store raw API keys. It records only pass/fail status and non-secret IDs."
    }

    REPORT_PATH.write_text(json.dumps(report, indent=4), encoding="utf-8")

    print()
    print("RESULT:")
    print("Passed checks:", f"{passed_count}/{total_count}")
    print("All security checks passed:", all_passed)
    print("Report:", REPORT_PATH)

    if all_passed:
        print()
        print("V0.36.3 SECURITY + CLIENT ISOLATION DEEP TEST: PASS")
    else:
        print()
        print("V0.36.3 SECURITY + CLIENT ISOLATION DEEP TEST: NEEDS WORK")


if __name__ == "__main__":
    main()
