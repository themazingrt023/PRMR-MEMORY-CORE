import json
import os
from datetime import datetime

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware

from prmr import PRMRMemoryCore
from prmr.reports import build_public_report, build_private_report

from prmr.security.access_layer import (
    ensure_access_config,
    build_access_context,
    save_run_log
)


APP_VERSION = "0.31"

app = FastAPI(
    title="PRMR Memory Core API",
    description="Local API server for PRMR Memory Core.",
    version=APP_VERSION
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def ensure_output_folder():
    os.makedirs("reports", exist_ok=True)
    os.makedirs("reports/v031", exist_ok=True)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)


def validate_payload(payload):
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=400,
            detail="Payload must be a JSON object."
        )

    if "datasets" not in payload:
        raise HTTPException(
            status_code=400,
            detail="Payload must contain a 'datasets' field."
        )

    if not isinstance(payload["datasets"], list):
        raise HTTPException(
            status_code=400,
            detail="'datasets' must be a list."
        )

    for index, dataset in enumerate(payload["datasets"]):
        if not isinstance(dataset, dict):
            raise HTTPException(
                status_code=400,
                detail=f"Dataset at index {index} must be an object."
            )

        if "name" not in dataset:
            raise HTTPException(
                status_code=400,
                detail=f"Dataset at index {index} is missing 'name'."
            )

        if "description" not in dataset:
            raise HTTPException(
                status_code=400,
                detail=f"Dataset at index {index} is missing 'description'."
            )

        if "rows" not in dataset:
            raise HTTPException(
                status_code=400,
                detail=f"Dataset at index {index} is missing 'rows'."
            )

        if not isinstance(dataset["rows"], list):
            raise HTTPException(
                status_code=400,
                detail=f"Dataset '{dataset['name']}' rows must be a list."
            )


def stamp_report_version(report, report_type, access_context):
    report["version"] = APP_VERSION
    report["report_type"] = report_type
    report["api_timestamp"] = datetime.now().isoformat()

    report["client_id"] = access_context["client_id"]
    report["vault_id"] = access_context["vault_id"]
    report["namespace"] = access_context["namespace"]
    report["run_id"] = access_context["run_id"]

    if "results" in report:
        for result in report["results"]:
            result["version"] = APP_VERSION

    return report


@app.on_event("startup")
def startup_event():
    ensure_access_config()
    ensure_output_folder()


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "product": "PRMR Memory Core",
        "company": "Afternum Industries",
        "version": APP_VERSION,
        "mode": "local_api_server_with_access_layer"
    }


@app.get("/access/status")
def access_status():
    return {
        "status": "ok",
        "message": "Local access layer active.",
        "required_header": "X-PRMR-API-Key",
        "default_local_key": "prmr_local_dev_key_v031",
        "default_vault": "default_vault",
        "default_namespace": "default"
    }


@app.post("/run")
def run_prmr(
    payload: dict,
    x_prmr_api_key: str = Header(default=None),
    x_prmr_vault_id: str = Header(default="default_vault"),
    x_prmr_namespace: str = Header(default="default")
):
    if not x_prmr_api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing X-PRMR-API-Key header."
        )

    access_context = build_access_context(
        api_key=x_prmr_api_key,
        vault_id=x_prmr_vault_id,
        namespace=x_prmr_namespace
    )

    if not access_context["allowed"]:
        raise HTTPException(
            status_code=403,
            detail=access_context["reason"]
        )

    validate_payload(payload)
    ensure_output_folder()

    engine = PRMRMemoryCore()
    engine_run = engine.run(payload["datasets"])

    public_report = build_public_report(engine_run)
    private_report = build_private_report(engine_run)

    public_report = stamp_report_version(
        public_report,
        "public_safe_api_run",
        access_context
    )

    private_report = stamp_report_version(
        private_report,
        "private_internal_api_run",
        access_context
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    client_folder = os.path.join(
        "reports",
        "v031",
        access_context["client_id"],
        access_context["vault_id"],
        access_context["namespace"]
    )

    os.makedirs(client_folder, exist_ok=True)

    public_path = os.path.join(
        client_folder,
        f"{access_context['run_id']}_public.json"
    )

    private_path = os.path.join(
        client_folder,
        f"{access_context['run_id']}_private_internal.json"
    )

    save_json(public_path, public_report)
    save_json(private_path, private_report)

    log_path = save_run_log(
        access_context=access_context,
        public_report_path=public_path,
        private_report_path=private_path,
        summary={
            "all_reconstructions_verified": public_report["all_reconstructions_verified"],
            "dataset_count": len(public_report["results"])
        }
    )

    response = {
        "api_version": APP_VERSION,
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "public_safe": True,
        "client_id": access_context["client_id"],
        "vault_id": access_context["vault_id"],
        "namespace": access_context["namespace"],
        "run_id": access_context["run_id"],
        "all_reconstructions_verified": public_report["all_reconstructions_verified"],
        "public_report_path": public_path,
        "private_report_saved": True,
        "private_report_warning": "Private internal report is NOT safe to publish.",
        "log_path": log_path,
        "public_report": public_report
    }

    if not public_report["all_reconstructions_verified"]:
        response["warning"] = "One or more reconstructions failed."

    return response


@app.post("/run-public")
def run_prmr_public_only(
    payload: dict,
    x_prmr_api_key: str = Header(default=None),
    x_prmr_vault_id: str = Header(default="default_vault"),
    x_prmr_namespace: str = Header(default="default")
):
    return run_prmr(
        payload=payload,
        x_prmr_api_key=x_prmr_api_key,
        x_prmr_vault_id=x_prmr_vault_id,
        x_prmr_namespace=x_prmr_namespace
    )