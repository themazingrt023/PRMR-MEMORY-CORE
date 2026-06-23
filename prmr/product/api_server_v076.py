"""V0.76 real local HTTP API server for PRMR Memory Core.

This module exposes the V0.75 local API wrapper through FastAPI routes. It is a
real local HTTP server surface for smoke testing, not hosted live client access.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from prmr.product.api_config_v075 import PRMRAPIConfig, load_api_config
from prmr.product.hosted_api_wrapper_v075 import (
    OVERCLAIMS,
    PUNITIVE_TERMS,
    PUBLIC_FORBIDDEN_TERMS,
    PRMRHostedAPIWrapper,
    ROUTES,
    contains_full_dev_key,
    sample_event,
    scan_terms,
)
from prmr.product.hosted_backend_foundation_v069 import utc_now


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "reports" / "v076"

BOUNDARY_V076 = (
    "V0.76 is a real local HTTP API server plus local HTTP smoke tests. It proves "
    "that PRMR controlled-alpha requests can pass through a local FastAPI server "
    "with HTTP headers, scoped auth, SQLite persistence, and public-safe JSON. It "
    "is not hosted live client access, not production readiness, not billing, not "
    "external validation, not bank approval, not compliance approval, not legal "
    "approval, not external security certification, and not real-world validation."
)

SERVER_FRAMEWORK = "FastAPI"

REQUIRED_HEADERS = [
    "Authorization: Bearer <api_key>",
    "X-Client-ID: <client_id>",
    "X-Vault-ID: <vault_id>",
    "X-Namespace: <namespace>",
]

PUBLIC_FORBIDDEN_TERMS_V076 = PUBLIC_FORBIDDEN_TERMS + [
    "raw_api_key",
    "full_api_key",
    "api_secret",
    "private_key",
    "key_hash",
    "validation_outcomes",
    "private_trace",
]

OVERCLAIMS_V076 = OVERCLAIMS + [
    "hosted live client access",
    "live hosted api",
    "production-ready",
    "production ready",
]


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, details: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "details": details})


def safe_json_clone(payload: Any) -> Any:
    return json.loads(json.dumps(payload, sort_keys=True, default=str))


def header_context(
    *,
    authorization: str | None,
    client_id: str | None,
    vault_id: str | None,
    namespace: str | None,
) -> tuple[dict[str, Any], dict[str, str] | None]:
    context = {
        "client_id": str(client_id or ""),
        "vault_id": str(vault_id or ""),
        "namespace": str(namespace or ""),
        "api_key": None,
    }
    if authorization is None or not authorization.strip():
        return context, None
    if not authorization.startswith("Bearer "):
        return context, {
            "code": "malformed_authorization",
            "message": "Authorization must use the Bearer scheme.",
        }
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        return context, {
            "code": "malformed_authorization",
            "message": "Authorization must include a Bearer token.",
        }
    context["api_key"] = token
    return context, None


def operation_for_route(route: str) -> str:
    return ROUTES.get(route, route.lower().replace(" ", "_").replace("/", "_").strip("_"))


def log_direct_block(
    wrapper: PRMRHostedAPIWrapper,
    *,
    operation: str,
    context: dict[str, Any],
    code: str,
    message: str,
) -> str:
    log_id = f"http_request_v076_{uuid4().hex[:12]}"
    usage_log_id = f"http_usage_v076_{uuid4().hex[:12]}"
    wrapper.persist_identity_state()
    wrapper.storage.store_request_log(
        {
            "log_id": log_id,
            "client_id": context.get("client_id") or "missing_client",
            "vault_id": context.get("vault_id") or "missing_vault",
            "namespace": context.get("namespace") or "missing_namespace",
            "operation": operation,
            "status": "blocked",
            "reason": code,
            "public_safe_message": message,
            "timestamp": utc_now(),
        }
    )
    wrapper.storage.store_usage_log(
        {
            "log_id": usage_log_id,
            "client_id": context.get("client_id") or "missing_client",
            "vault_id": context.get("vault_id") or "missing_vault",
            "namespace": context.get("namespace") or "missing_namespace",
            "operation": operation,
            "status": "blocked",
            "reason": code,
            "count": 1,
            "timestamp": utc_now(),
        }
    )
    return log_id


def direct_error_response(
    wrapper: PRMRHostedAPIWrapper,
    *,
    status_code: int,
    operation: str,
    context: dict[str, Any],
    code: str,
    message: str,
) -> JSONResponse:
    log_id = log_direct_block(wrapper, operation=operation, context=context, code=code, message=message)
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "error",
            "operation": operation,
            "client_id": context.get("client_id") or "",
            "vault_id": context.get("vault_id") or "",
            "namespace": context.get("namespace") or "",
            "request_id": log_id,
            "log_id": log_id,
            "public_safe": True,
            "boundary": BOUNDARY_V076,
            "error": {"code": code, "message": message},
        },
    )


def normalize_response(operation: str, result: dict[str, Any], context: dict[str, Any]) -> JSONResponse:
    status_code = int(result.get("status_code", 500))
    body = dict(result.get("body") or {})
    request_id = f"http_request_v076_{uuid4().hex[:12]}"
    status = body.get("status", "error" if status_code >= 400 else "ok")
    base = {
        "status": status,
        "operation": operation,
        "client_id": body.get("client_id", context.get("client_id", "")),
        "vault_id": body.get("vault_id", context.get("vault_id", "")),
        "namespace": body.get("namespace", context.get("namespace", "")),
        "request_id": request_id,
        "public_safe": True,
        "boundary": BOUNDARY_V076,
    }
    if status == "error" or status_code >= 400:
        return JSONResponse(
            status_code=status_code,
            content={
                **base,
                "status": "error",
                "error": body.get("error", {"code": "request_failed", "message": "Request did not complete."}),
            },
        )

    payload = {
        key: value
        for key, value in body.items()
        if key not in {"status", "client_id", "vault_id", "namespace", "public_safe", "boundary"}
    }
    return JSONResponse(status_code=status_code, content={**base, **payload})


async def json_body(request: Request) -> dict[str, Any]:
    if request.method.upper() == "GET":
        return {}
    try:
        value = await request.json()
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def create_app(wrapper: PRMRHostedAPIWrapper | None = None, config: PRMRAPIConfig | None = None) -> FastAPI:
    """Create the local V0.76 FastAPI app.

    A runner can inject a pre-seeded wrapper so real HTTP requests exercise the
    same in-memory auth/runtime state while persistence lands in SQLite.
    """

    active_config = config or load_api_config()
    active_wrapper = wrapper or PRMRHostedAPIWrapper(config=active_config, reset_storage=False)
    app = FastAPI(
        title="PRMR Memory Core Local HTTP API V0.76",
        version="0.76",
        description=BOUNDARY_V076,
    )
    app.state.prmr_wrapper = active_wrapper
    app.state.prmr_config = active_config
    app.add_middleware(
        CORSMiddleware,
        allow_origins=active_config.allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "X-Client-ID", "X-Vault-ID", "X-Namespace", "Content-Type"],
    )

    async def protected_payload(
        request: Request,
        route: str,
        authorization: str | None,
        client_id: str | None,
        vault_id: str | None,
        namespace: str | None,
    ) -> tuple[dict[str, Any], JSONResponse | None]:
        operation = operation_for_route(route)
        context, header_error = header_context(
            authorization=authorization,
            client_id=client_id,
            vault_id=vault_id,
            namespace=namespace,
        )
        if header_error:
            return context, direct_error_response(
                active_wrapper,
                status_code=401,
                operation=operation,
                context=context,
                code=header_error["code"],
                message=header_error["message"],
            )
        body = await json_body(request)
        payload = {**body, **context}
        return payload, None

    @app.get("/health")
    def health() -> dict[str, Any]:
        wrapper_health = active_wrapper.health()["body"]
        return {
            "status": "ok",
            "operation": "health",
            "server_framework": SERVER_FRAMEWORK,
            "api_mode": active_config.api_mode,
            "synthetic_only": active_config.synthetic_only,
            "public_safe": True,
            "boundary": BOUNDARY_V076,
            "routes": sorted(ROUTES.keys()),
            "required_headers": REQUIRED_HEADERS,
            "cors": {
                "allowed_origins": active_config.allowed_origins,
                "wildcard_origin": "*" in active_config.allowed_origins,
                "hosted_cors_policy_pending": True,
            },
            "wrapper_status": wrapper_health.get("status"),
        }

    @app.post("/v1/events/ingest")
    async def events_ingest(
        request: Request,
        authorization: str | None = Header(default=None, alias="Authorization"),
        client_id: str | None = Header(default=None, alias="X-Client-ID"),
        vault_id: str | None = Header(default=None, alias="X-Vault-ID"),
        namespace: str | None = Header(default=None, alias="X-Namespace"),
    ) -> JSONResponse:
        payload, error = await protected_payload(request, "POST /v1/events/ingest", authorization, client_id, vault_id, namespace)
        if error:
            return error
        return normalize_response("events_ingest", active_wrapper.events_ingest(payload), payload)

    @app.post("/v1/continuity/packet")
    async def continuity_packet(
        request: Request,
        authorization: str | None = Header(default=None, alias="Authorization"),
        client_id: str | None = Header(default=None, alias="X-Client-ID"),
        vault_id: str | None = Header(default=None, alias="X-Vault-ID"),
        namespace: str | None = Header(default=None, alias="X-Namespace"),
    ) -> JSONResponse:
        payload, error = await protected_payload(request, "POST /v1/continuity/packet", authorization, client_id, vault_id, namespace)
        if error:
            return error
        return normalize_response("continuity_packet", active_wrapper.continuity_packet(payload), payload)

    @app.post("/v1/memory/reconstruct")
    async def memory_reconstruct(
        request: Request,
        authorization: str | None = Header(default=None, alias="Authorization"),
        client_id: str | None = Header(default=None, alias="X-Client-ID"),
        vault_id: str | None = Header(default=None, alias="X-Vault-ID"),
        namespace: str | None = Header(default=None, alias="X-Namespace"),
    ) -> JSONResponse:
        payload, error = await protected_payload(request, "POST /v1/memory/reconstruct", authorization, client_id, vault_id, namespace)
        if error:
            return error
        return normalize_response("memory_reconstruct", active_wrapper.memory_reconstruct(payload), payload)

    @app.post("/v1/explain")
    async def explain(
        request: Request,
        authorization: str | None = Header(default=None, alias="Authorization"),
        client_id: str | None = Header(default=None, alias="X-Client-ID"),
        vault_id: str | None = Header(default=None, alias="X-Vault-ID"),
        namespace: str | None = Header(default=None, alias="X-Namespace"),
    ) -> JSONResponse:
        payload, error = await protected_payload(request, "POST /v1/explain", authorization, client_id, vault_id, namespace)
        if error:
            return error
        return normalize_response("explain", active_wrapper.explain(payload), payload)

    @app.post("/v1/actions/least-harm")
    async def least_harm_action(
        request: Request,
        authorization: str | None = Header(default=None, alias="Authorization"),
        client_id: str | None = Header(default=None, alias="X-Client-ID"),
        vault_id: str | None = Header(default=None, alias="X-Vault-ID"),
        namespace: str | None = Header(default=None, alias="X-Namespace"),
    ) -> JSONResponse:
        payload, error = await protected_payload(request, "POST /v1/actions/least-harm", authorization, client_id, vault_id, namespace)
        if error:
            return error
        return normalize_response("least_harm_action", active_wrapper.least_harm_action(payload), payload)

    @app.get("/v1/reports/{report_id}")
    async def get_report(
        report_id: str,
        request: Request,
        authorization: str | None = Header(default=None, alias="Authorization"),
        client_id: str | None = Header(default=None, alias="X-Client-ID"),
        vault_id: str | None = Header(default=None, alias="X-Vault-ID"),
        namespace: str | None = Header(default=None, alias="X-Namespace"),
    ) -> JSONResponse:
        payload, error = await protected_payload(request, "GET /v1/reports/{report_id}", authorization, client_id, vault_id, namespace)
        if error:
            return error
        return normalize_response("get_report", active_wrapper.get_report(payload, report_id), payload)

    @app.get("/v1/usage")
    async def get_usage(
        request: Request,
        authorization: str | None = Header(default=None, alias="Authorization"),
        client_id: str | None = Header(default=None, alias="X-Client-ID"),
        vault_id: str | None = Header(default=None, alias="X-Vault-ID"),
        namespace: str | None = Header(default=None, alias="X-Namespace"),
    ) -> JSONResponse:
        payload, error = await protected_payload(request, "GET /v1/usage", authorization, client_id, vault_id, namespace)
        if error:
            return error
        return normalize_response("get_usage", active_wrapper.get_usage(payload), payload)

    @app.get("/v1/dashboard/state")
    async def get_dashboard_state(
        request: Request,
        authorization: str | None = Header(default=None, alias="Authorization"),
        client_id: str | None = Header(default=None, alias="X-Client-ID"),
        vault_id: str | None = Header(default=None, alias="X-Vault-ID"),
        namespace: str | None = Header(default=None, alias="X-Namespace"),
    ) -> JSONResponse:
        payload, error = await protected_payload(request, "GET /v1/dashboard/state", authorization, client_id, vault_id, namespace)
        if error:
            return error
        response = active_wrapper.get_dashboard_state(payload)
        dashboard = response["body"].get("dashboard", {})
        if dashboard:
            dashboard["version"] = "0.76"
            dashboard["boundary"] = BOUNDARY_V076
            dashboard.setdefault("memory_health_panel", {})["status"] = "http_api_server_connected"
        normalized = normalize_response("get_dashboard_state", response, payload)
        active_wrapper.storage.store_dashboard_refresh(
            {
                "refresh_id": "refresh_v076_latest",
                "client_id": payload["client_id"],
                "vault_id": payload["vault_id"],
                "namespace": payload["namespace"],
                "allowed_request_count": dashboard.get("usage_overview", {}).get("allowed_request_count", 0),
                "blocked_request_count": dashboard.get("usage_overview", {}).get("blocked_request_count", 0),
                "events_received": dashboard.get("memory_health_panel", {}).get("events_received", 0),
                "packets_generated": dashboard.get("memory_health_panel", {}).get("packets_generated", 0),
                "reports_visible": dashboard.get("memory_health_panel", {}).get("reports_visible", 0),
                "memory_health": "http_api_server_connected",
                "created_at": utc_now(),
            }
        )
        return normalized

    return app


app = create_app()


def build_public_report(checks: list[dict[str, Any]], smoke_summary: dict[str, Any], config: PRMRAPIConfig) -> dict[str, Any]:
    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    return {
        "version": "0.76",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "Real Local HTTP API Server",
        "result": "PASS" if passed == total else "NEEDS_WORK",
        "checks_passed": passed,
        "checks_total": total,
        "public_safe": True,
        "boundary": BOUNDARY_V076,
        "server_framework": SERVER_FRAMEWORK,
        "truth_label": "real local HTTP API server and local HTTP smoke tests",
        "hosted_live_client_access": False,
        "routes": sorted(ROUTES.keys()),
        "required_headers": REQUIRED_HEADERS,
        "cors": {
            "allowed_origins": config.allowed_origins,
            "wildcard_origin": "*" in config.allowed_origins,
            "hosted_cors_policy_pending": True,
        },
        "smoke_summary": smoke_summary,
    }


def build_private_report(
    public_report: dict[str, Any],
    checks: list[dict[str, Any]],
    wrapper: PRMRHostedAPIWrapper,
    http_results: dict[str, Any],
) -> dict[str, Any]:
    return {
        **public_report,
        "public_safe": False,
        "title": "Real Local HTTP API Server Restricted Synthetic Evidence",
        "checks": checks,
        "http_results": http_results,
        "storage_snapshot_restricted": wrapper.storage.export_storage_snapshot(public_safe=False),
        "restricted_note": "Restricted synthetic evidence may include key hashes. Raw API key values are not persisted or reported.",
    }


def build_scorecard(public_report: dict[str, Any], checks: list[dict[str, Any]]) -> str:
    lines = [
        "# V0.76 Real Local HTTP API Server",
        "",
        f"Result: {public_report['result']}",
        f"Passed checks: {public_report['checks_passed']}/{public_report['checks_total']}",
        "",
        f"Boundary: {BOUNDARY_V076}",
        "",
        "## Server",
        "",
        f"- Framework: {SERVER_FRAMEWORK}",
        "- Truth label: real local HTTP API server and local HTTP smoke tests",
        "- Hosted live client access: false",
        "",
        "## Routes",
        "",
        *[f"- {route}" for route in public_report["routes"]],
        "",
        "## Headers",
        "",
        *[f"- {header}" for header in REQUIRED_HEADERS],
        "",
        "## Checks",
        "",
    ]
    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        lines.append(f"- {status}: {check['name']}")
    lines.extend(
        [
            "",
            "## Command Results",
            "",
            "- RUN: python examples/run_api_server_v076.py",
            "- RUN: python examples/audit_v076_api_server.py",
            "",
            BOUNDARY_V076,
            "",
        ]
    )
    return "\n".join(lines)


def contains_forbidden_public_material(payload: Any) -> bool:
    return contains_full_dev_key(payload) or bool(scan_terms(payload, PUBLIC_FORBIDDEN_TERMS_V076))


def public_hygiene_failures(payload: Any) -> dict[str, Any]:
    return {
        "full_dev_key_present": contains_full_dev_key(payload),
        "restricted_terms": scan_terms(payload, PUBLIC_FORBIDDEN_TERMS_V076),
        "overclaims": scan_terms(payload, OVERCLAIMS_V076),
        "punitive_terms": scan_terms(payload, PUNITIVE_TERMS),
    }


def safe_route_results_for_public(results: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for name, result in results.items():
        body = result.get("body", {}) if isinstance(result, dict) else {}
        safe[name] = {
            "status_code": result.get("status_code") if isinstance(result, dict) else None,
            "status": body.get("status"),
            "operation": body.get("operation"),
            "error_code": body.get("error", {}).get("code") if isinstance(body.get("error"), dict) else None,
            "public_safe": body.get("public_safe"),
        }
    return safe
