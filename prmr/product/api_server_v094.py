"""Hosted/deployable self-serve API activation surface for PRMR V0.94."""

from __future__ import annotations

import os
from pathlib import Path
from threading import RLock
from typing import Any, Callable

from fastapi import FastAPI, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from prmr.product.durable_self_serve_storage_v093 import (
    BOUNDARY_V093,
    DurableSelfServeProductV093,
    env_flag,
)
from prmr.product.postgres_self_serve_storage_v0941 import PostgresSelfServeProductV0941


ROOT = Path(__file__).resolve().parents[2]
BOUNDARY_V094 = (
    "V0.94 is a hosted/deployable self-serve activation MVP using a local/test "
    "verification state and hash-backed session tokens. It is not real email "
    "verification, Stripe billing, production auth hardening, compliance "
    "approval, legal approval, or external security certification."
)
DEFAULT_BACKEND_URL = "https://prmr-memory-core-api.onrender.com"


def configured_storage_path() -> Path:
    configured = os.getenv("PRMR_SELF_SERVE_STORAGE_PATH", "").strip()
    if configured:
        return Path(configured)
    return ROOT / "reports" / "v094" / "prmr_self_serve_local.sqlite"


def configured_storage_backend() -> str:
    backend = os.getenv("PRMR_STORAGE_BACKEND", "sqlite").strip().lower() or "sqlite"
    if backend not in {"sqlite", "postgres"}:
        raise ValueError("PRMR_STORAGE_BACKEND must be sqlite or postgres.")
    return backend


def configured_product() -> DurableSelfServeProductV093 | PostgresSelfServeProductV0941:
    if configured_storage_backend() == "postgres":
        return PostgresSelfServeProductV0941.from_environment()
    return DurableSelfServeProductV093(
        configured_storage_path(),
        api_mode=os.getenv("PRMR_API_MODE", "local_alpha"),
        durable_storage_verified=env_flag("PRMR_DURABLE_STORAGE_VERIFIED", False),
    )


def allowed_origins() -> list[str]:
    configured = os.getenv(
        "PRMR_ALLOWED_ORIGINS",
        "https://prmr-memory-core.vercel.app,http://localhost:3000",
    )
    return [item.strip() for item in configured.split(",") if item.strip() and item.strip() != "*"]


def session_token(authorization: str | None) -> tuple[str | None, dict[str, str] | None]:
    if not authorization:
        return None, {"code": "missing_session", "message": "A self-serve session is required."}
    if not authorization.startswith("Session "):
        return None, {
            "code": "malformed_session",
            "message": "Authorization must use the Session scheme for self-serve routes.",
        }
    token = authorization.removeprefix("Session ").strip()
    if not token:
        return None, {"code": "missing_session", "message": "A self-serve session is required."}
    return token, None


def bearer_key(authorization: str | None) -> tuple[str | None, dict[str, str] | None]:
    if not authorization:
        return None, {"code": "missing_key", "message": "A valid API key is required."}
    if not authorization.startswith("Bearer "):
        return None, {
            "code": "malformed_authorization",
            "message": "Authorization must use the Bearer scheme.",
        }
    key = authorization.removeprefix("Bearer ").strip()
    if not key:
        return None, {"code": "missing_key", "message": "A valid API key is required."}
    return key, None


async def json_body(request: Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "error",
            "error": {"code": code, "message": message},
            "public_safe": True,
            "boundary": BOUNDARY_V094,
        },
    )


def result_response(result: dict[str, Any], *, strip_session: bool = False) -> JSONResponse:
    status_code = int(result.get("status_code", 200 if result.get("ok") else 400))
    payload = dict(result)
    payload.setdefault("status", "ok" if status_code < 400 else "error")
    payload.setdefault("public_safe", True)
    payload.setdefault("boundary", BOUNDARY_V094)
    if strip_session:
        payload.pop("session_token", None)
    return JSONResponse(status_code=status_code, content=payload)


def protected_response(result: dict[str, Any]) -> JSONResponse:
    return JSONResponse(
        status_code=int(result.get("status_code", 500)),
        content=dict(result.get("body") or {}),
    )


def create_app_v094(
    product: DurableSelfServeProductV093 | PostgresSelfServeProductV0941 | None = None,
) -> FastAPI:
    active_product = product or configured_product()
    lock = RLock()
    app = FastAPI(
        title="PRMR Memory Core Self-Serve API",
        version="0.94",
        description=BOUNDARY_V094,
    )
    app.state.self_serve_product_v094 = active_product
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins(),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Client-ID",
            "X-Vault-ID",
            "X-Namespace",
        ],
    )

    def locked_call(function: Callable[..., dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        with lock:
            return function(**kwargs)

    def hosted_storage_guard() -> JSONResponse | None:
        if (
            active_product.api_mode.startswith("hosted")
            and not active_product.storage_status["durable_storage_claim_allowed"]
        ):
            return error(
                503,
                "needs_hosted_durable_storage",
                "Hosted self-serve activation requires verified durable storage.",
            )
        return None

    @app.get("/health")
    def health() -> dict[str, Any]:
        state = active_product.health()
        return {
            **state,
            "version": "0.94",
            "operation": "health",
            "hosted_self_serve_activation": state["storage"]["durable_storage_claim_allowed"],
            "self_serve_routes": [
                "POST /v1/self-serve/signup",
                "POST /v1/self-serve/verify",
                "POST /v1/self-serve/login",
                "POST /v1/self-serve/plan",
                "POST /v1/self-serve/provision",
                "GET|POST|PATCH|DELETE /v1/self-serve/keys",
                "GET /v1/self-serve/dashboard",
            ],
            "boundary": BOUNDARY_V094,
        }

    @app.post("/v1/self-serve/signup")
    async def signup(request: Request) -> JSONResponse:
        if storage_error := hosted_storage_guard():
            return storage_error
        body = await json_body(request)
        result = locked_call(
            active_product.signup,
            name=str(body.get("name", "")),
            email=str(body.get("email", "")),
            password=str(body.get("password", "")),
        )
        return result_response(result)

    @app.post("/v1/self-serve/verify")
    async def verify(request: Request) -> JSONResponse:
        if storage_error := hosted_storage_guard():
            return storage_error
        body = await json_body(request)
        result = locked_call(
            active_product.verify_email_local,
            user_id=str(body.get("user_id", "")),
        )
        return result_response(result)

    @app.post("/v1/self-serve/login")
    async def login(request: Request) -> JSONResponse:
        if storage_error := hosted_storage_guard():
            return storage_error
        body = await json_body(request)
        result = locked_call(
            active_product.login,
            email=str(body.get("email", "")),
            password=str(body.get("password", "")),
        )
        return result_response(result)

    async def require_session(
        authorization: str | None,
    ) -> tuple[str | None, JSONResponse | None]:
        if storage_error := hosted_storage_guard():
            return None, storage_error
        token, auth_error = session_token(authorization)
        if auth_error:
            return None, error(401, auth_error["code"], auth_error["message"])
        if active_product.product.accounts.validate_session(token) is None:
            return None, error(401, "invalid_session", "The self-serve session is not valid.")
        return token, None

    @app.post("/v1/self-serve/plan")
    async def choose_plan(
        request: Request,
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> JSONResponse:
        token, auth_error = await require_session(authorization)
        if auth_error:
            return auth_error
        body = await json_body(request)
        return result_response(
            locked_call(
                active_product.choose_plan,
                session_token=str(token),
                plan_id=str(body.get("plan_id", "free")),
            )
        )

    @app.post("/v1/self-serve/provision")
    async def provision(
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> JSONResponse:
        token, auth_error = await require_session(authorization)
        if auth_error:
            return auth_error
        return result_response(
            locked_call(active_product.provision_default_scope, session_token=str(token))
        )

    @app.get("/v1/self-serve/keys")
    async def list_keys(
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> JSONResponse:
        token, auth_error = await require_session(authorization)
        if auth_error:
            return auth_error
        return result_response(active_product.list_keys(session_token=str(token)))

    @app.post("/v1/self-serve/keys")
    async def create_key(
        request: Request,
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> JSONResponse:
        token, auth_error = await require_session(authorization)
        if auth_error:
            return auth_error
        body = await json_body(request)
        return result_response(
            locked_call(
                active_product.create_key,
                session_token=str(token),
                label=str(body.get("label", "")),
            )
        )

    @app.patch("/v1/self-serve/keys")
    async def rotate_key(
        request: Request,
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> JSONResponse:
        token, auth_error = await require_session(authorization)
        if auth_error:
            return auth_error
        body = await json_body(request)
        return result_response(
            locked_call(
                active_product.rotate_key,
                session_token=str(token),
                key_id=str(body.get("key_id", "")),
            )
        )

    @app.delete("/v1/self-serve/keys")
    async def revoke_key(
        request: Request,
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> JSONResponse:
        token, auth_error = await require_session(authorization)
        if auth_error:
            return auth_error
        body = await json_body(request)
        return result_response(
            locked_call(
                active_product.revoke_key,
                session_token=str(token),
                key_id=str(body.get("key_id", "")),
            )
        )

    @app.get("/v1/self-serve/dashboard")
    async def dashboard(
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> JSONResponse:
        token, auth_error = await require_session(authorization)
        if auth_error:
            return auth_error
        return result_response(active_product.dashboard_state(session_token=str(token)))

    async def protected_context(
        request: Request,
        authorization: str | None,
        client_id: str | None,
        vault_id: str | None,
        namespace: str | None,
    ) -> tuple[dict[str, Any], JSONResponse | None]:
        key, key_error = bearer_key(authorization)
        if key_error:
            return {}, error(401, key_error["code"], key_error["message"])
        body = await json_body(request)
        return {
            **body,
            "api_key": key,
            "client_id": str(client_id or ""),
            "vault_id": str(vault_id or ""),
            "namespace": str(namespace or ""),
        }, None

    async def execute_protected(
        request: Request,
        operation: str,
        authorization: str | None,
        client_id: str | None,
        vault_id: str | None,
        namespace: str | None,
        **extra: Any,
    ) -> JSONResponse:
        context, access_error = await protected_context(
            request,
            authorization,
            client_id,
            vault_id,
            namespace,
        )
        if access_error:
            return access_error
        context.update(extra)
        with lock:
            result = active_product.execute(operation, **context)
        return protected_response(result)

    def protected_headers(
        authorization: str | None,
        client_id: str | None,
        vault_id: str | None,
        namespace: str | None,
    ) -> tuple[str | None, str | None, str | None, str | None]:
        return authorization, client_id, vault_id, namespace

    @app.post("/v1/events/ingest")
    async def events_ingest(
        request: Request,
        authorization: str | None = Header(default=None, alias="Authorization"),
        client_id: str | None = Header(default=None, alias="X-Client-ID"),
        vault_id: str | None = Header(default=None, alias="X-Vault-ID"),
        namespace: str | None = Header(default=None, alias="X-Namespace"),
    ) -> JSONResponse:
        return await execute_protected(
            request, "events_ingest", *protected_headers(authorization, client_id, vault_id, namespace)
        )

    @app.post("/v1/continuity/packet")
    async def continuity_packet(
        request: Request,
        authorization: str | None = Header(default=None, alias="Authorization"),
        client_id: str | None = Header(default=None, alias="X-Client-ID"),
        vault_id: str | None = Header(default=None, alias="X-Vault-ID"),
        namespace: str | None = Header(default=None, alias="X-Namespace"),
    ) -> JSONResponse:
        return await execute_protected(
            request, "continuity_packet", *protected_headers(authorization, client_id, vault_id, namespace)
        )

    @app.post("/v1/memory/reconstruct")
    async def memory_reconstruct(
        request: Request,
        authorization: str | None = Header(default=None, alias="Authorization"),
        client_id: str | None = Header(default=None, alias="X-Client-ID"),
        vault_id: str | None = Header(default=None, alias="X-Vault-ID"),
        namespace: str | None = Header(default=None, alias="X-Namespace"),
    ) -> JSONResponse:
        return await execute_protected(
            request, "memory_reconstruct", *protected_headers(authorization, client_id, vault_id, namespace)
        )

    @app.post("/v1/explain")
    async def explain(
        request: Request,
        authorization: str | None = Header(default=None, alias="Authorization"),
        client_id: str | None = Header(default=None, alias="X-Client-ID"),
        vault_id: str | None = Header(default=None, alias="X-Vault-ID"),
        namespace: str | None = Header(default=None, alias="X-Namespace"),
    ) -> JSONResponse:
        return await execute_protected(
            request, "explain", *protected_headers(authorization, client_id, vault_id, namespace)
        )

    @app.post("/v1/actions/least-harm")
    async def least_harm_action(
        request: Request,
        authorization: str | None = Header(default=None, alias="Authorization"),
        client_id: str | None = Header(default=None, alias="X-Client-ID"),
        vault_id: str | None = Header(default=None, alias="X-Vault-ID"),
        namespace: str | None = Header(default=None, alias="X-Namespace"),
    ) -> JSONResponse:
        return await execute_protected(
            request, "least_harm_action", *protected_headers(authorization, client_id, vault_id, namespace)
        )

    @app.get("/v1/reports/{report_id}")
    async def get_report(
        report_id: str,
        request: Request,
        authorization: str | None = Header(default=None, alias="Authorization"),
        client_id: str | None = Header(default=None, alias="X-Client-ID"),
        vault_id: str | None = Header(default=None, alias="X-Vault-ID"),
        namespace: str | None = Header(default=None, alias="X-Namespace"),
    ) -> JSONResponse:
        return await execute_protected(
            request,
            "get_report",
            *protected_headers(authorization, client_id, vault_id, namespace),
            report_id=report_id,
        )

    @app.get("/v1/usage")
    async def get_usage(
        request: Request,
        authorization: str | None = Header(default=None, alias="Authorization"),
        client_id: str | None = Header(default=None, alias="X-Client-ID"),
        vault_id: str | None = Header(default=None, alias="X-Vault-ID"),
        namespace: str | None = Header(default=None, alias="X-Namespace"),
    ) -> JSONResponse:
        return await execute_protected(
            request, "get_usage", *protected_headers(authorization, client_id, vault_id, namespace)
        )

    return app


app = create_app_v094()
