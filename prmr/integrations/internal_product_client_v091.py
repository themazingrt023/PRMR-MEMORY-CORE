"""V0.91 server-side PRMR API client for the first internal integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

import httpx


BOUNDARY_V091 = (
    "V0.91 is the first internal server-side product integration using a "
    "controlled synthetic PRMR scope. Local HTTP evidence does not prove a live "
    "hosted internal integration, external client validation, production "
    "readiness, or billing."
)


class HTTPClient(Protocol):
    def get(self, url: str, **kwargs: Any): ...

    def post(self, url: str, **kwargs: Any): ...


@dataclass(frozen=True)
class PRMRClientConfig:
    api_base_url: str
    api_key: str
    client_id: str
    vault_id: str
    namespace: str

    @classmethod
    def from_environment(cls, environment: Mapping[str, str]) -> "PRMRClientConfig":
        required = {
            "PRMR_API_BASE_URL": "api_base_url",
            "PRMR_API_KEY": "api_key",
            "PRMR_CLIENT_ID": "client_id",
            "PRMR_VAULT_ID": "vault_id",
            "PRMR_NAMESPACE": "namespace",
        }
        values: dict[str, str] = {}
        missing: list[str] = []
        for variable, field_name in required.items():
            value = str(environment.get(variable) or "").strip()
            if not value:
                missing.append(variable)
            values[field_name] = value
        if missing:
            raise ValueError(f"Missing PRMR environment variables: {', '.join(sorted(missing))}")
        return cls(**values)

    def public_scope(self) -> dict[str, Any]:
        return {
            "api_base_url": self.api_base_url,
            "client_id": self.client_id,
            "vault_id": self.vault_id,
            "namespace": self.namespace,
            "credential_configured": bool(self.api_key),
            "credential_value_exposed": False,
        }


class InternalPRMRClientV091:
    """Small server-side client that exercises the contracted PRMR workflow."""

    def __init__(self, config: PRMRClientConfig, http_client: HTTPClient | None = None) -> None:
        self.config = config
        self._owned_client = http_client is None
        self.http = http_client or httpx.Client(
            base_url=config.api_base_url.rstrip("/"),
            timeout=20.0,
        )

    @property
    def scoped_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config.api_key}",
            "X-Client-ID": self.config.client_id,
            "X-Vault-ID": self.config.vault_id,
            "X-Namespace": self.config.namespace,
            "Content-Type": "application/json",
        }

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        kwargs: dict[str, Any] = {"headers": self.scoped_headers}
        if payload is not None:
            kwargs["json"] = payload
        response = self.http.post(path, **kwargs) if method == "POST" else self.http.get(path, **kwargs)
        body = response.json()
        return {
            "status_code": response.status_code,
            "body": body if isinstance(body, dict) else {"status": "error"},
        }

    def health(self) -> dict[str, Any]:
        response = self.http.get("/health", headers={"Accept": "application/json"})
        body = response.json()
        return {"status_code": response.status_code, "body": body}

    def run_continuity_workflow(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        ingest = self.request("POST", "/v1/events/ingest", {"events": events})
        packet = self.request("POST", "/v1/continuity/packet", {})
        packet_body = packet["body"]
        packet_id = packet_body.get("packet_id")
        report_id = packet_body.get("report_id")
        reconstruct = self.request("POST", "/v1/memory/reconstruct", {"packet_id": packet_id})
        explain = self.request("POST", "/v1/explain", {"packet_id": packet_id})
        least_harm = self.request("POST", "/v1/actions/least-harm", {"packet_id": packet_id})
        report = self.request("GET", f"/v1/reports/{report_id}")
        usage = self.request("GET", "/v1/usage")
        return {
            "health": self.health(),
            "ingest": ingest,
            "packet": packet,
            "reconstruct": reconstruct,
            "explain": explain,
            "least_harm": least_harm,
            "report": report,
            "usage": usage,
            "packet_id": packet_id,
            "report_id": report_id,
            "scope": self.config.public_scope(),
            "boundary": BOUNDARY_V091,
        }

    def close(self) -> None:
        if self._owned_client and hasattr(self.http, "close"):
            self.http.close()

