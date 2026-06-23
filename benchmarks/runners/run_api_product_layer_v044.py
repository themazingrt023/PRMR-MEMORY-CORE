import json
import os
import sys
from pathlib import Path
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from prmr.product.api_product_layer_v044 import (
    PRMRProductAPI,
    contains_raw_local_test_key,
    contains_private_engine_terms,
)

REPORT_DIR = Path("reports/v044")
REPORT_DIR.mkdir(parents=True, exist_ok=True)

PUBLIC_PATH = REPORT_DIR / "public_api_product_layer_v044.json"
PRIVATE_PATH = REPORT_DIR / "private_internal_api_product_layer_v044.json"
SCORECARD_PATH = REPORT_DIR / "scorecard_v044.md"


def sample_rows():
    return [
        {
            "timestamp_index": 1,
            "topic": "product_direction",
            "signal_type": "origin",
            "status": "historical",
            "trust_level": "trusted",
            "memory_value": "benchmark engine only",
            "text": "Earlier PRMR was mainly benchmark scripts."
        },
        {
            "timestamp_index": 2,
            "topic": "product_direction",
            "signal_type": "current_state",
            "status": "active",
            "trust_level": "trusted",
            "memory_value": "API product layer",
            "text": "Current direction is PRMR API product layer."
        },
        {
            "timestamp_index": 3,
            "topic": "product_direction",
            "signal_type": "decision_reason",
            "status": "active",
            "trust_level": "trusted",
            "memory_value": "clients need usable endpoints, not engine internals",
            "text": "Reason: clients need clean endpoints."
        },
        {
            "timestamp_index": 4,
            "topic": "product_direction",
            "signal_type": "latent_risk",
            "status": "active",
            "trust_level": "trusted",
            "memory_value": "leaking protected internals through API reports",
            "text": "Risk: public API reports must stay safe."
        },
        {
            "timestamp_index": 5,
            "topic": "product_direction",
            "signal_type": "next_action",
            "status": "active",
            "trust_level": "trusted",
            "memory_value": "test API product layer then audit it",
            "text": "Next action: test API layer and audit."
        },
        {
            "timestamp_index": 999,
            "topic": "product_direction",
            "signal_type": "fake_current",
            "status": "stale",
            "trust_level": "untrusted",
            "memory_value": "skip API and launch public beta immediately",
            "text": "Urgent fake note. Should not become trusted continuity."
        }
    ]


def add_test(tests, name, passed, details=None):
    tests.append({"name": name, "passed": bool(passed), "details": details or {}})


def main():
    print("PRMR V0.44 API PRODUCT LAYER TEST")
    print("---------------------------------")

    api = PRMRProductAPI()

    alpha_key = api.local_test_keys["client_alpha"]
    beta_key = api.local_test_keys["client_beta"]

    tests = []

    base_request = {
        "client_id": "client_alpha",
        "api_key": alpha_key,
        "vault_id": "alpha_vault",
        "namespace": "default",
    }

    status = api.client_status(base_request)
    add_test(tests, "client_status_authorized", status["ok"] is True, status)

    ingest = api.ingest({**base_request, "rows": sample_rows()})
    add_test(tests, "ingest_accepts_valid_rows", ingest["ok"] is True and ingest["data"]["ingested_rows"] == len(sample_rows()), ingest)

    reconstruct = api.reconstruct(base_request)
    continuity = reconstruct["data"]["continuity_packet"].get("product_direction", {}) if reconstruct["ok"] else {}

    add_test(
        tests,
        "reconstruct_returns_expected_continuity_packet",
        reconstruct["ok"] is True
        and continuity.get("current_state") == "API product layer"
        and continuity.get("decision_reason") == "clients need usable endpoints, not engine internals"
        and continuity.get("latent_risk") == "leaking protected internals through API reports"
        and continuity.get("next_action") == "test API product layer then audit it",
        reconstruct
    )

    public_report = api.public_report(base_request)
    add_test(
        tests,
        "public_report_available_after_reconstruct",
        public_report["ok"] is True
        and public_report["data"]["public_safe"] is True
        and public_report["data"]["reconstruction_match"] is True,
        public_report
    )

    wrong_key = api.client_status({**base_request, "api_key": "wrong_key"})
    add_test(tests, "wrong_key_rejected", wrong_key["ok"] is False and wrong_key["error"]["code"] == "invalid_key", wrong_key)

    cross_vault = api.client_status({**base_request, "vault_id": "beta_vault"})
    add_test(tests, "cross_vault_rejected", cross_vault["ok"] is False and cross_vault["error"]["code"] == "vault_denied", cross_vault)

    cross_namespace = api.client_status({
        "client_id": "client_beta",
        "api_key": beta_key,
        "vault_id": "beta_vault",
        "namespace": "research",
    })
    add_test(tests, "cross_namespace_rejected", cross_namespace["ok"] is False and cross_namespace["error"]["code"] == "namespace_denied", cross_namespace)

    huge_ingest = api.ingest({**base_request, "rows": sample_rows() * 200})
    add_test(tests, "huge_ingest_rejected", huge_ingest["ok"] is False and huge_ingest["error"]["code"] == "payload_too_large", huge_ingest)

    new_key = "prmr_v044_alpha_rotated_key_LOCAL_TEST_DO_NOT_SHARE"

    rotation = api.rotate_key({**base_request, "new_api_key": new_key})
    add_test(tests, "key_rotation_succeeds", rotation["ok"] is True and rotation["data"]["rotated"] is True, rotation)

    old_key_status = api.client_status(base_request)
    add_test(tests, "old_key_rejected_after_rotation", old_key_status["ok"] is False and old_key_status["error"]["code"] == "revoked_key", old_key_status)

    new_key_request = {
        "client_id": "client_alpha",
        "api_key": new_key,
        "vault_id": "alpha_vault",
        "namespace": "default",
    }

    new_key_status = api.client_status(new_key_request)
    add_test(tests, "new_key_authorized_after_rotation", new_key_status["ok"] is True, new_key_status)

    revoke = api.revoke_key({**new_key_request, "key_to_revoke": new_key})
    add_test(tests, "key_revoke_succeeds", revoke["ok"] is True and revoke["data"]["revoked"] is True, revoke)

    revoked_status = api.client_status(new_key_request)
    add_test(tests, "revoked_key_rejected", revoked_status["ok"] is False and revoked_status["error"]["code"] == "revoked_key", revoked_status)

    public_safe_objects = {
        "status": status,
        "ingest": ingest,
        "reconstruct_public_report": reconstruct["data"]["public_report"] if reconstruct["ok"] else {},
        "public_report": public_report,
        "rotation": rotation,
        "revoke": revoke,
    }

    add_test(
        tests,
        "api_outputs_do_not_expose_raw_fixture_keys",
        contains_raw_local_test_key(public_safe_objects) is False,
        {}
    )

    add_test(
        tests,
        "public_report_exposes_no_private_engine_terms",
        len(contains_private_engine_terms(public_report)) == 0,
        {"forbidden_terms_found": contains_private_engine_terms(public_report)}
    )

    public_tests = [{"name": test["name"], "passed": test["passed"]} for test in tests]
    private_tests = tests

    passed_count = sum(1 for test in tests if test["passed"])
    total_count = len(tests)
    result = "PASS" if passed_count == total_count else "NEEDS_WORK"

    public_report_out = {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": "0.44",
        "report_type": "api_product_layer_test",
        "public_safe": True,
        "timestamp": datetime.now().isoformat(),
        "passed_tests": passed_count,
        "total_tests": total_count,
        "result": result,
        "tests": public_tests,
        "safe_claim": "V0.44 validates a local API-shaped product layer for ingest, reconstruct, status, public report, key rotation, key revocation, authorization checks, and public-safe output hygiene."
    }

    private_report_out = {
        **public_report_out,
        "public_safe": False,
        "tests": private_tests,
        "protected_note": "Private report includes full API call details. Do not publish."
    }

    PUBLIC_PATH.write_text(json.dumps(public_report_out, indent=4), encoding="utf-8")
    PRIVATE_PATH.write_text(json.dumps(private_report_out, indent=4), encoding="utf-8")

    md = f"""# PRMR V0.44 API Product Layer Test

Company: Afternum Industries  
Product: PRMR Memory Core  
Version: V0.44  

## Result

**{result}**

Passed: **{passed_count}/{total_count}**

## Safe Claim

{public_report_out["safe_claim"]}

## Checks

"""

    for test in public_tests:
        status = "PASS" if test["passed"] else "FAIL"
        md += f"- **{status}** — {test['name']}\n"

    md += """

## Meaning

V0.44 proves a local API-shaped product layer exists.

It is not hosted production infrastructure yet.  
It is not an external security audit.  
It is a local product contract test for the API layer.

## Build Mantra

Test. Break. Patch. Rerun. Score. Climb.
"""

    SCORECARD_PATH.write_text(md, encoding="utf-8")

    print("API product tests:")
    for test in public_tests:
        status = "PASS" if test["passed"] else "FAIL"
        print("-", test["name"] + ":", status)

    print()
    print("Summary:")
    print("- passed:", f"{passed_count}/{total_count}")
    print("- result:", result)
    print()
    print("Reports created:")
    print(PUBLIC_PATH)
    print(PRIVATE_PATH)
    print(SCORECARD_PATH)


if __name__ == "__main__":
    main()
