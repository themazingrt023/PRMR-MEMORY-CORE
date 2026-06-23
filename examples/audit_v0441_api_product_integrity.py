import json
import importlib.util
import os
import sys
from pathlib import Path
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

PUBLIC_REPORT = Path("reports/v044/public_api_product_layer_v044.json")
PRIVATE_REPORT = Path("reports/v044/private_internal_api_product_layer_v044.json")
API_PATH = Path("prmr/product/api_product_layer_v044.py")
RUNNER_PATH = Path("benchmarks/runners/run_api_product_layer_v044.py")

OUT_DIR = Path("reports/v0441")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_JSON = OUT_DIR / "api_product_integrity_audit_v0441.json"
OUT_MD = OUT_DIR / "api_product_integrity_audit_v0441.md"


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def add_check(checks, name, passed, details=None):
    checks.append({
        "name": name,
        "passed": bool(passed),
        "details": details or {}
    })


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def public_safety_scan(text):
    forbidden_terms = [
        "compressed_package",
        "reconstructed_rows",
        "engine_result_snapshot",
        "internal_rule_data",
        "private_answer_details",
        "protected_note",
        "prmr_v044_alpha_key_LOCAL_TEST_DO_NOT_SHARE",
        "prmr_v044_beta_key_LOCAL_TEST_DO_NOT_SHARE",
        "prmr_v044_alpha_rotated_key_LOCAL_TEST_DO_NOT_SHARE",
    ]

    return [term for term in forbidden_terms if term.lower() in text.lower()]


def hardcode_scan(text):
    suspicious = []

    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        lowered = stripped.lower()

        if not stripped or stripped.startswith("#"):
            continue

        if (
            "result" in lowered
            and "pass" in lowered
            and " if " not in lowered
            and "else" not in lowered
            and ("report" in lowered or "public_report_out" in lowered)
        ):
            suspicious.append({
                "line": line_number,
                "reason": "possible_direct_result_pass_assignment",
                "text": stripped
            })

        if (
            ("passed_tests" in lowered or "passed_count" in lowered)
            and ("= 15" in lowered or ": 15" in lowered)
            and "sum(" not in lowered
        ):
            suspicious.append({
                "line": line_number,
                "reason": "possible_fixed_pass_count",
                "text": stripped
            })

    return suspicious


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


def recompute_api_behaviors(api_module):
    api = api_module.PRMRProductAPI()

    alpha_key = api.local_test_keys["client_alpha"]
    beta_key = api.local_test_keys["client_beta"]

    base_request = {
        "client_id": "client_alpha",
        "api_key": alpha_key,
        "vault_id": "alpha_vault",
        "namespace": "default",
    }

    results = {}

    status = api.client_status(base_request)
    results["client_status_authorized"] = status["ok"] is True

    ingest = api.ingest({**base_request, "rows": sample_rows()})
    results["ingest_accepts_valid_rows"] = (
        ingest["ok"] is True
        and ingest["data"]["ingested_rows"] == len(sample_rows())
    )

    reconstruct = api.reconstruct(base_request)
    continuity = reconstruct["data"]["continuity_packet"].get("product_direction", {}) if reconstruct["ok"] else {}

    results["reconstruct_returns_expected_continuity_packet"] = (
        reconstruct["ok"] is True
        and continuity.get("current_state") == "API product layer"
        and continuity.get("decision_reason") == "clients need usable endpoints, not engine internals"
        and continuity.get("latent_risk") == "leaking protected internals through API reports"
        and continuity.get("next_action") == "test API product layer then audit it"
        and continuity.get("current_state") != "skip API and launch public beta immediately"
    )

    public_report = api.public_report(base_request)

    results["public_report_available_after_reconstruct"] = (
        public_report["ok"] is True
        and public_report["data"]["public_safe"] is True
        and public_report["data"]["reconstruction_match"] is True
    )

    wrong_key = api.client_status({**base_request, "api_key": "wrong_key"})
    results["wrong_key_rejected"] = wrong_key["ok"] is False and wrong_key["error"]["code"] == "invalid_key"

    cross_vault = api.client_status({**base_request, "vault_id": "beta_vault"})
    results["cross_vault_rejected"] = cross_vault["ok"] is False and cross_vault["error"]["code"] == "vault_denied"

    cross_namespace = api.client_status({
        "client_id": "client_beta",
        "api_key": beta_key,
        "vault_id": "beta_vault",
        "namespace": "research",
    })
    results["cross_namespace_rejected"] = (
        cross_namespace["ok"] is False
        and cross_namespace["error"]["code"] == "namespace_denied"
    )

    huge_ingest = api.ingest({**base_request, "rows": sample_rows() * 200})
    results["huge_ingest_rejected"] = (
        huge_ingest["ok"] is False
        and huge_ingest["error"]["code"] == "payload_too_large"
    )

    new_key = "prmr_v044_alpha_rotated_key_LOCAL_TEST_DO_NOT_SHARE"

    rotation = api.rotate_key({**base_request, "new_api_key": new_key})
    results["key_rotation_succeeds"] = rotation["ok"] is True and rotation["data"]["rotated"] is True

    old_key_status = api.client_status(base_request)
    results["old_key_rejected_after_rotation"] = (
        old_key_status["ok"] is False
        and old_key_status["error"]["code"] == "revoked_key"
    )

    new_key_request = {
        "client_id": "client_alpha",
        "api_key": new_key,
        "vault_id": "alpha_vault",
        "namespace": "default",
    }

    new_key_status = api.client_status(new_key_request)
    results["new_key_authorized_after_rotation"] = new_key_status["ok"] is True

    revoke = api.revoke_key({**new_key_request, "key_to_revoke": new_key})
    results["key_revoke_succeeds"] = revoke["ok"] is True and revoke["data"]["revoked"] is True

    revoked_status = api.client_status(new_key_request)
    results["revoked_key_rejected"] = (
        revoked_status["ok"] is False
        and revoked_status["error"]["code"] == "revoked_key"
    )

    public_safe_objects = {
        "status": status,
        "ingest": ingest,
        "reconstruct_public_report": reconstruct["data"]["public_report"] if reconstruct["ok"] else {},
        "public_report": public_report,
        "rotation": rotation,
        "revoke": revoke,
    }

    results["api_outputs_do_not_expose_raw_local_test_keys"] = (
        api_module.contains_raw_local_test_key(public_safe_objects) is False
    )

    results["public_report_exposes_no_private_engine_terms"] = (
        len(api_module.contains_private_engine_terms(public_report)) == 0
    )

    return results


def main():
    checks = []

    public = load_json(PUBLIC_REPORT)
    private = load_json(PRIVATE_REPORT)
    api_module = load_module(API_PATH, "api_product_layer_v044")

    # 1. Public report pass count recomputes.
    public_passed = sum(1 for test in public["tests"] if test["passed"])
    public_total = len(public["tests"])

    add_check(
        checks,
        "public_report_pass_count_recomputes",
        public_passed == public["passed_tests"] and public_total == public["total_tests"],
        {
            "reported_passed": public["passed_tests"],
            "recomputed_passed": public_passed,
            "reported_total": public["total_tests"],
            "recomputed_total": public_total
        }
    )

    # 2. Private report pass count recomputes.
    private_passed = sum(1 for test in private["tests"] if test["passed"])
    private_total = len(private["tests"])

    add_check(
        checks,
        "private_report_pass_count_recomputes",
        private_passed == private["passed_tests"] and private_total == private["total_tests"],
        {
            "reported_passed": private["passed_tests"],
            "recomputed_passed": private_passed,
            "reported_total": private["total_tests"],
            "recomputed_total": private_total
        }
    )

    # 3. Public/private test statuses agree.
    public_status = {test["name"]: test["passed"] for test in public["tests"]}
    private_status = {test["name"]: test["passed"] for test in private["tests"]}

    add_check(
        checks,
        "public_and_private_reports_agree_on_test_statuses",
        public_status == private_status,
        {
            "public_only": sorted(set(public_status) - set(private_status)),
            "private_only": sorted(set(private_status) - set(public_status))
        }
    )

    # 4. Endpoint behavior recomputes from API module.
    recomputed = recompute_api_behaviors(api_module)

    add_check(
        checks,
        "api_endpoint_behaviors_recompute_from_product_layer",
        all(recomputed.values()),
        recomputed
    )

    # 5. API module exposes the required product methods.
    required_methods = [
        "client_status",
        "ingest",
        "reconstruct",
        "public_report",
        "rotate_key",
        "revoke_key",
    ]

    missing_methods = [
        method for method in required_methods
        if not hasattr(api_module.PRMRProductAPI, method)
    ]

    add_check(
        checks,
        "api_product_layer_exposes_required_methods",
        len(missing_methods) == 0,
        {
            "required_methods": required_methods,
            "missing_methods": missing_methods
        }
    )

    # 6. Public report contains no raw local test keys or private terms.
    public_text = PUBLIC_REPORT.read_text(encoding="utf-8", errors="ignore")
    public_forbidden = public_safety_scan(public_text)

    add_check(
        checks,
        "public_report_exposes_no_raw_keys_or_private_terms",
        len(public_forbidden) == 0,
        {
            "forbidden_terms_found": public_forbidden
        }
    )

    # 7. Public report has no detailed private test internals.
    public_has_details = any("details" in test for test in public["tests"])

    add_check(
        checks,
        "public_report_has_no_detailed_private_test_internals",
        public_has_details is False,
        {
            "public_has_details": public_has_details
        }
    )

    # 8. Private report contains details for debugging.
    private_has_details = all("details" in test for test in private["tests"])

    add_check(
        checks,
        "private_report_contains_detailed_test_internals",
        private_has_details is True,
        {
            "private_has_details": private_has_details
        }
    )

    # 9. API output sanitizer helper works.
    raw_key_probe = {
        "api_key": "prmr_v044_alpha_key_LOCAL_TEST_DO_NOT_SHARE"
    }

    add_check(
        checks,
        "raw_key_detection_helper_flags_test_key_probe",
        api_module.contains_raw_local_test_key(raw_key_probe) is True,
        {}
    )

    safe_probe = {
        "client_id": "client_alpha",
        "message": "no raw key here"
    }

    add_check(
        checks,
        "raw_key_detection_helper_allows_safe_probe",
        api_module.contains_raw_local_test_key(safe_probe) is False,
        {}
    )

    # 10. Public report helper detects forbidden engine terms.
    private_term_probe = {"engine_result_snapshot": {"x": 1}}

    add_check(
        checks,
        "private_engine_term_helper_flags_probe",
        "engine_result_snapshot" in api_module.contains_private_engine_terms(private_term_probe),
        {}
    )

    # 11. Hardcode scan.
    runner_text = RUNNER_PATH.read_text(encoding="utf-8", errors="ignore")
    api_text = API_PATH.read_text(encoding="utf-8", errors="ignore")
    suspicious = hardcode_scan(runner_text + "\n" + api_text)

    add_check(
        checks,
        "api_runner_does_not_directly_hardcode_final_pass",
        len(suspicious) == 0,
        {
            "suspicious_patterns_found": suspicious
        }
    )

    passed_count = sum(1 for check in checks if check["passed"])
    total_checks = len(checks)
    all_passed = passed_count == total_checks

    report = {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": "0.44.1",
        "report_type": "api_product_layer_integrity_audit",
        "timestamp": datetime.now().isoformat(),
        "public_safe": True,
        "passed_checks": passed_count,
        "total_checks": total_checks,
        "all_integrity_checks_passed": all_passed,
        "checks": checks,
        "verdict": (
            "V0.44 API product layer result is internally consistent. Endpoint behavior recomputes, required product methods exist, key lifecycle behavior holds, scoped reconstruction works, and public output remains safe."
            if all_passed
            else "V0.44 API product layer result needs review. One or more integrity checks failed."
        ),
        "honest_claim": (
            "V0.44 is a local API-shaped product layer proof. It is not yet hosted production infrastructure."
        ),
        "next_phase": "V0.45 Pilot Sandbox or V0.44.2 API Report Leak Scan"
    }

    OUT_JSON.write_text(json.dumps(report, indent=4), encoding="utf-8")

    md = f"""# PRMR V0.44.1 API Product Layer Integrity Audit

Company: Afternum Industries  
Product: PRMR Memory Core  
Version: V0.44.1  

## Result

**{passed_count}/{total_checks} checks passed**

All integrity checks passed: **{all_passed}**

## Verdict

{report["verdict"]}

## Honest Claim

{report["honest_claim"]}

## Checks

"""

    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        md += f"- **{status}** — {check['name']}\n"

    md += """

## Meaning

This verifies the V0.44 local API-shaped product layer.

It checks endpoint behavior, report consistency, method availability, key lifecycle behavior, output hygiene, and hardcode risk.

This remains internal product-layer evidence, not production certification.

## Build Mantra

Test. Break. Patch. Rerun. Score. Climb.
"""

    OUT_MD.write_text(md, encoding="utf-8")

    print("PRMR V0.44.1 API PRODUCT LAYER INTEGRITY AUDIT")
    print("----------------------------------------------")
    print("Passed checks:", f"{passed_count}/{total_checks}")
    print("All integrity checks passed:", all_passed)
    print("Verdict:", report["verdict"])
    print()
    print("Honest claim:")
    print(report["honest_claim"])
    print()
    print("Check list:")
    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        print("-", check["name"] + ":", status)
    print()
    print("Created:")
    print(OUT_JSON)
    print(OUT_MD)


if __name__ == "__main__":
    main()