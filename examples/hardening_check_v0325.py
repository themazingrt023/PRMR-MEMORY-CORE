import json
import os
import urllib.error
import urllib.request


BASE_URL = "http://127.0.0.1:8000"
INPUT_FILE = "inputs/demo_input_v029.json"
REPORT_FOLDER = "reports/v0325"


def request_json(method, path, body=None, headers=None):
    url = BASE_URL + path

    data = None

    if body is not None:
        data = json.dumps(body).encode("utf-8")

    request = urllib.request.Request(
        url=url,
        data=data,
        method=method,
        headers=headers or {}
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
            error_data = json.loads(error.read().decode("utf-8"))
        except Exception:
            error_data = {"detail": "Could not parse error body."}

        return {
            "ok": False,
            "status_code": error.code,
            "data": error_data
        }

    except Exception as error:
        return {
            "ok": False,
            "status_code": None,
            "data": {"detail": str(error)}
        }


def load_input_payload():
    with open(INPUT_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def run_hardening_check():
    os.makedirs(REPORT_FOLDER, exist_ok=True)

    payload = load_input_payload()

    results = []

    # 1. Health check
    health = request_json("GET", "/health")
    results.append({
        "test": "health_check",
        "passed": health["ok"] and health["data"].get("status") == "ok",
        "status_code": health["status_code"],
        "details": health["data"]
    })

    # 2. Access status
    access = request_json("GET", "/access/status")
    results.append({
        "test": "access_status",
        "passed": access["ok"] and access["data"].get("default_local_key") == "prmr_local_dev_key_v031",
        "status_code": access["status_code"],
        "details": access["data"]
    })

    # 3. Valid API run
    valid_headers = {
        "Content-Type": "application/json",
        "X-PRMR-API-Key": "prmr_local_dev_key_v031",
        "X-PRMR-Vault-ID": "default_vault",
        "X-PRMR-Namespace": "default"
    }

    valid_run = request_json(
        "POST",
        "/run",
        body=payload,
        headers=valid_headers
    )

    run_id = None

    if valid_run["ok"]:
        run_id = valid_run["data"].get("run_id")

    results.append({
        "test": "valid_api_run",
        "passed": (
            valid_run["ok"]
            and valid_run["data"].get("public_safe") is True
            and valid_run["data"].get("all_reconstructions_verified") is True
            and valid_run["data"].get("company") == "Afternum Industries"
            and run_id is not None
        ),
        "status_code": valid_run["status_code"],
        "details": {
            "run_id": run_id,
            "all_reconstructions_verified": valid_run["data"].get("all_reconstructions_verified") if valid_run["ok"] else None,
            "public_report_path": valid_run["data"].get("public_report_path") if valid_run["ok"] else None
        }
    })

    # 4. Missing API key should fail
    missing_key_headers = {
        "Content-Type": "application/json"
    }

    missing_key = request_json(
        "POST",
        "/run",
        body=payload,
        headers=missing_key_headers
    )

    results.append({
        "test": "missing_api_key_blocked",
        "passed": missing_key["status_code"] == 401,
        "status_code": missing_key["status_code"],
        "details": missing_key["data"]
    })

    # 5. Wrong API key should fail
    wrong_key_headers = {
        "Content-Type": "application/json",
        "X-PRMR-API-Key": "wrong_key",
        "X-PRMR-Vault-ID": "default_vault",
        "X-PRMR-Namespace": "default"
    }

    wrong_key = request_json(
        "POST",
        "/run",
        body=payload,
        headers=wrong_key_headers
    )

    results.append({
        "test": "wrong_api_key_blocked",
        "passed": wrong_key["status_code"] == 403,
        "status_code": wrong_key["status_code"],
        "details": wrong_key["data"]
    })

    # 6. Wrong vault should fail
    wrong_vault_headers = {
        "Content-Type": "application/json",
        "X-PRMR-API-Key": "prmr_local_dev_key_v031",
        "X-PRMR-Vault-ID": "forbidden_vault",
        "X-PRMR-Namespace": "default"
    }

    wrong_vault = request_json(
        "POST",
        "/run",
        body=payload,
        headers=wrong_vault_headers
    )

    results.append({
        "test": "wrong_vault_blocked",
        "passed": wrong_vault["status_code"] == 403,
        "status_code": wrong_vault["status_code"],
        "details": wrong_vault["data"]
    })

    # 7. Dashboard runs endpoint should work and not expose private report paths
    dashboard_runs = request_json("GET", "/dashboard/api/runs")

    dashboard_exposes_private_path = False

    if dashboard_runs["ok"]:
        for run in dashboard_runs["data"].get("runs", []):
            if "private_report_path" in run:
                dashboard_exposes_private_path = True

    results.append({
        "test": "dashboard_runs_public_safe",
        "passed": dashboard_runs["ok"] and not dashboard_exposes_private_path,
        "status_code": dashboard_runs["status_code"],
        "details": {
            "run_count": len(dashboard_runs["data"].get("runs", [])) if dashboard_runs["ok"] else None,
            "exposes_private_report_path": dashboard_exposes_private_path
        }
    })

    # 8. Public report preview should load for the valid run
    public_report_result = None

    if run_id is not None:
        public_report_result = request_json(
            "GET",
            f"/dashboard/api/public-report/{run_id}"
        )

        public_report_passed = (
            public_report_result["ok"]
            and public_report_result["data"].get("company") == "Afternum Industries"
            and public_report_result["data"].get("all_reconstructions_verified") is True
            and "protection_warning" not in public_report_result["data"]
        )

    else:
        public_report_result = {
            "ok": False,
            "status_code": None,
            "data": {"detail": "No run_id available."}
        }

        public_report_passed = False

    results.append({
        "test": "public_report_preview_safe",
        "passed": public_report_passed,
        "status_code": public_report_result["status_code"],
        "details": {
            "has_private_warning": "protection_warning" in public_report_result["data"],
            "all_reconstructions_verified": public_report_result["data"].get("all_reconstructions_verified")
        }
    })

    all_passed = all(result["passed"] for result in results)

    report = {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": "0.32.5",
        "report_type": "private_hardening_check",
        "public_safe_summary": {
            "all_hardening_checks_passed": all_passed,
            "tests_run": len(results),
            "server": BASE_URL
        },
        "results": results,
        "protected_note": "Internal hardening check. Do not publish raw test details if they expose local paths or access structure."
    }

    with open(os.path.join(REPORT_FOLDER, "hardening_check_v0325.json"), "w", encoding="utf-8") as file:
        json.dump(report, file, indent=4)

    return report


report = run_hardening_check()

print("PRMR MEMORY CORE HARDENING CHECK V0.32.5")
print("----------------------------------------")

print("\nAll hardening checks passed:", report["public_safe_summary"]["all_hardening_checks_passed"])
print("Tests run:", report["public_safe_summary"]["tests_run"])

print("\nRESULTS:")

for result in report["results"]:
    status = "PASS" if result["passed"] else "FAIL"
    print(f"- {result['test']}: {status} ({result['status_code']})")

print("\nREPORT CREATED:")
print("reports/v0325/hardening_check_v0325.json")

print("\nIMPORTANT:")
print("This is an internal hardening report. Do not publish raw details.")