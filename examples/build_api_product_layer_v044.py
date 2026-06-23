import json
from pathlib import Path

API_DIR = Path("prmr/product")
RUNNER_DIR = Path("benchmarks/runners")
REPORT_DIR = Path("reports/v044")

API_DIR.mkdir(parents=True, exist_ok=True)
RUNNER_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

api_code = r'''import json
import hashlib
from datetime import datetime

from prmr.core.engine import PRMRMemoryCore


class PRMRProductAPI:
    """
    V0.44 local product-layer API simulation.

    This is not a hosted web server yet.
    It is an API-shaped local layer with route-like methods:
    - client_status
    - ingest
    - reconstruct
    - public_report
    - rotate_key
    - revoke_key
    """

    def __init__(self):
        self.engine = PRMRMemoryCore()
        self.max_rows_per_ingest = 500

        self.clients = {
            "client_alpha": {
                "active_key_hashes": set(),
                "revoked_key_hashes": set(),
                "vaults": {"alpha_vault"},
                "namespaces": {"default", "research"},
                "plan": "local_alpha",
                "status": "active",
            },
            "client_beta": {
                "active_key_hashes": set(),
                "revoked_key_hashes": set(),
                "vaults": {"beta_vault"},
                "namespaces": {"default"},
                "plan": "local_alpha",
                "status": "active",
            },
        }

        self.local_test_keys = {
            "client_alpha": "prmr_v044_alpha_key_LOCAL_TEST_DO_NOT_SHARE",
            "client_beta": "prmr_v044_beta_key_LOCAL_TEST_DO_NOT_SHARE",
        }

        for client_id, raw_key in self.local_test_keys.items():
            self.clients[client_id]["active_key_hashes"].add(self.hash_key(raw_key))

        self.memory_store = {}
        self.last_public_reports = {}

    def hash_key(self, raw_key):
        return hashlib.sha256(str(raw_key).encode("utf-8")).hexdigest()

    def key_fingerprint(self, raw_key):
        return self.hash_key(raw_key)[:12]

    def _scope_key(self, client_id, vault_id, namespace):
        return f"{client_id}::{vault_id}::{namespace}"

    def _safe_error(self, code, message):
        return {
            "ok": False,
            "error": {"code": code, "message": message},
            "data": None,
        }

    def _ok(self, data):
        return {"ok": True, "error": None, "data": data}

    def authorize(self, client_id, api_key, vault_id, namespace):
        if client_id not in self.clients:
            return False, "unknown_client"

        client = self.clients[client_id]

        if client.get("status") != "active":
            return False, "client_inactive"

        key_hash = self.hash_key(api_key)

        if key_hash in client["revoked_key_hashes"]:
            return False, "revoked_key"

        if key_hash not in client["active_key_hashes"]:
            return False, "invalid_key"

        if vault_id not in client["vaults"]:
            return False, "vault_denied"

        if namespace not in client["namespaces"]:
            return False, "namespace_denied"

        return True, "authorized"

    def client_status(self, request):
        client_id = request.get("client_id")
        api_key = request.get("api_key")
        vault_id = request.get("vault_id")
        namespace = request.get("namespace")

        authorized, reason = self.authorize(client_id, api_key, vault_id, namespace)

        if not authorized:
            return self._safe_error(reason, "Request is not authorized.")

        client = self.clients[client_id]

        return self._ok({
            "client_id": client_id,
            "vault_id": vault_id,
            "namespace": namespace,
            "plan": client["plan"],
            "status": client["status"],
            "active_key_count": len(client["active_key_hashes"]),
            "revoked_key_count": len(client["revoked_key_hashes"]),
        })

    def _validate_rows(self, rows):
        if not isinstance(rows, list):
            return False, "rows_must_be_list", []

        if len(rows) > self.max_rows_per_ingest:
            return False, "payload_too_large", []

        safe_rows = []

        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                return False, "row_must_be_object", []

            safe_row = dict(row)
            safe_row["text"] = str(safe_row.get("text", ""))[:1000]
            safe_row["memory_value"] = str(safe_row.get("memory_value", ""))[:1000]
            safe_row["timestamp_index"] = int(safe_row.get("timestamp_index", index + 1))
            safe_row["topic"] = str(safe_row.get("topic", "unknown"))[:120]
            safe_row["signal_type"] = str(safe_row.get("signal_type", "note"))[:80]
            safe_row["status"] = str(safe_row.get("status", "active"))[:80]
            safe_row["trust_level"] = str(safe_row.get("trust_level", "trusted"))[:80]

            safe_rows.append(safe_row)

        return True, "rows_valid", safe_rows

    def ingest(self, request):
        client_id = request.get("client_id")
        api_key = request.get("api_key")
        vault_id = request.get("vault_id")
        namespace = request.get("namespace")
        rows = request.get("rows")

        authorized, reason = self.authorize(client_id, api_key, vault_id, namespace)

        if not authorized:
            return self._safe_error(reason, "Request is not authorized.")

        valid, validation_reason, safe_rows = self._validate_rows(rows)

        if not valid:
            return self._safe_error(validation_reason, "Payload failed validation.")

        scoped_rows = []

        for row in safe_rows:
            scoped_row = dict(row)
            scoped_row["client_id"] = client_id
            scoped_row["vault_id"] = vault_id
            scoped_row["namespace"] = namespace
            scoped_rows.append(scoped_row)

        key = self._scope_key(client_id, vault_id, namespace)
        self.memory_store.setdefault(key, [])
        self.memory_store[key].extend(scoped_rows)

        return self._ok({
            "client_id": client_id,
            "vault_id": vault_id,
            "namespace": namespace,
            "ingested_rows": len(scoped_rows),
            "total_rows": len(self.memory_store[key]),
        })

    def _build_continuity_packet(self, rows, client_id):
        topics = {}

        trusted_rows = [
            row for row in rows
            if row.get("trust_level") == "trusted"
            and row.get("status") in ("active", "historical")
        ]

        grouped = {}

        for row in trusted_rows:
            grouped.setdefault(row.get("topic", "unknown"), []).append(row)

        for topic, topic_rows in grouped.items():
            ordered = sorted(topic_rows, key=lambda row: row.get("timestamp_index", 0))

            current_rows = [row for row in ordered if row.get("signal_type") in ("current_state", "current_commitment")]
            reason_rows = [row for row in ordered if row.get("signal_type") in ("decision_reason", "lineage")]
            risk_rows = [row for row in ordered if row.get("signal_type") in ("latent_risk", "risk")]
            next_rows = [row for row in ordered if row.get("signal_type") in ("next_action", "next")]
            origin_rows = [row for row in ordered if row.get("signal_type") in ("origin", "old_state")]

            topics[topic] = {
                "client_id": client_id,
                "current_state": current_rows[-1]["memory_value"] if current_rows else None,
                "decision_reason": reason_rows[-1]["memory_value"] if reason_rows else None,
                "latent_risk": risk_rows[-1]["memory_value"] if risk_rows else None,
                "next_action": next_rows[-1]["memory_value"] if next_rows else None,
                "old_state": origin_rows[-1]["memory_value"] if origin_rows else None,
            }

        return topics

    def reconstruct(self, request):
        client_id = request.get("client_id")
        api_key = request.get("api_key")
        vault_id = request.get("vault_id")
        namespace = request.get("namespace")

        authorized, reason = self.authorize(client_id, api_key, vault_id, namespace)

        if not authorized:
            return self._safe_error(reason, "Request is not authorized.")

        key = self._scope_key(client_id, vault_id, namespace)
        rows = self.memory_store.get(key, [])

        engine_input = [{
            "name": "api_product_layer_v044",
            "description": "V0.44 API product-layer reconstruction",
            "rows": rows,
        }]

        engine_result = self.engine.run(engine_input)
        decision = engine_result["results"][0]["decision"]
        reconstructed_rows = decision["reconstructed_rows"]

        reconstruction_match = reconstructed_rows == rows
        continuity_packet = self._build_continuity_packet(reconstructed_rows, client_id)

        public_report = {
            "company": "Afternum Industries",
            "product": "PRMR Memory Core",
            "version": "0.44",
            "report_type": "api_product_layer_public_report",
            "public_safe": True,
            "timestamp": datetime.now().isoformat(),
            "client_id": client_id,
            "vault_id": vault_id,
            "namespace": namespace,
            "row_count": len(reconstructed_rows),
            "topic_count": len(continuity_packet),
            "reconstruction_match": reconstruction_match,
            "engine_public": {
                "policy_mode": decision.get("policy_mode"),
                "raw_size": decision.get("raw_size"),
                "policy_size": decision.get("policy_size"),
                "policy_compression_ratio": decision.get("policy_compression_ratio"),
                "policy_saved_percentage": decision.get("policy_saved_percentage"),
            },
            "claim": "Public report exposes product-level reconstruction status only. Protected engine internals are not included."
        }

        self.last_public_reports[key] = public_report

        return self._ok({
            "client_id": client_id,
            "vault_id": vault_id,
            "namespace": namespace,
            "continuity_packet": continuity_packet,
            "public_report": public_report,
        })

    def public_report(self, request):
        client_id = request.get("client_id")
        api_key = request.get("api_key")
        vault_id = request.get("vault_id")
        namespace = request.get("namespace")

        authorized, reason = self.authorize(client_id, api_key, vault_id, namespace)

        if not authorized:
            return self._safe_error(reason, "Request is not authorized.")

        key = self._scope_key(client_id, vault_id, namespace)
        report = self.last_public_reports.get(key)

        if not report:
            return self._safe_error("report_not_found", "No public report exists yet. Run reconstruct first.")

        return self._ok(report)

    def rotate_key(self, request):
        client_id = request.get("client_id")
        api_key = request.get("api_key")
        vault_id = request.get("vault_id")
        namespace = request.get("namespace")
        new_api_key = request.get("new_api_key")

        authorized, reason = self.authorize(client_id, api_key, vault_id, namespace)

        if not authorized:
            return self._safe_error(reason, "Request is not authorized.")

        if not new_api_key:
            return self._safe_error("missing_new_key", "New access key is required.")

        client = self.clients[client_id]
        old_hash = self.hash_key(api_key)
        new_hash = self.hash_key(new_api_key)

        client["active_key_hashes"].discard(old_hash)
        client["revoked_key_hashes"].add(old_hash)
        client["active_key_hashes"].add(new_hash)

        return self._ok({
            "client_id": client_id,
            "rotated": True,
            "old_key_fingerprint": self.key_fingerprint(api_key),
            "new_key_fingerprint": self.key_fingerprint(new_api_key),
        })

    def revoke_key(self, request):
        client_id = request.get("client_id")
        api_key = request.get("api_key")
        vault_id = request.get("vault_id")
        namespace = request.get("namespace")
        key_to_revoke = request.get("key_to_revoke")

        authorized, reason = self.authorize(client_id, api_key, vault_id, namespace)

        if not authorized:
            return self._safe_error(reason, "Request is not authorized.")

        if not key_to_revoke:
            return self._safe_error("missing_key_to_revoke", "Key to revoke is required.")

        client = self.clients[client_id]
        revoke_hash = self.hash_key(key_to_revoke)

        client["active_key_hashes"].discard(revoke_hash)
        client["revoked_key_hashes"].add(revoke_hash)

        return self._ok({
            "client_id": client_id,
            "revoked": True,
            "revoked_key_fingerprint": self.key_fingerprint(key_to_revoke),
        })


def contains_raw_local_test_key(obj):
    text = json.dumps(obj, sort_keys=True)
    markers = [
        "prmr_v044_alpha_key_LOCAL_TEST_DO_NOT_SHARE",
        "prmr_v044_beta_key_LOCAL_TEST_DO_NOT_SHARE",
    ]
    return any(marker in text for marker in markers)


def contains_private_engine_terms(obj):
    text = json.dumps(obj, sort_keys=True).lower()
    forbidden = [
        "compressed_package",
        "reconstructed_rows",
        "engine_result_snapshot",
        "internal_rule_data",
        "private_answer_details",
        "protected_note",
    ]
    return [term for term in forbidden if term in text]
'''

api_path = API_DIR / "api_product_layer_v044.py"
api_path.write_text(api_code, encoding="utf-8")

runner_code = r'''import json
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
        "api_outputs_do_not_expose_raw_local_test_keys",
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
'''

runner_path = RUNNER_DIR / "run_api_product_layer_v044.py"
runner_path.write_text(runner_code, encoding="utf-8")

print("PRMR V0.44 API Product Layer created.")
print("API module:", api_path)
print("Runner:", runner_path)