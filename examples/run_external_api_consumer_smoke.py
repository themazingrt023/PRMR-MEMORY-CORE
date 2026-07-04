"""Call the hosted PRMR API exactly like an external server-side consumer."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


BASE_URL = os.getenv(
    "PRMR_API_BASE_URL",
    "https://prmr-memory-core-api.onrender.com",
).rstrip("/")
API_KEY = os.getenv("PRMR_API_KEY", "").strip()


def request(method: str, path: str, payload: dict | None = None) -> tuple[int, dict]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Accept": "application/json",
    }
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(f"{BASE_URL}{path}", data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        payload = json.loads(exc.read().decode("utf-8"))
        return exc.code, payload


def main() -> int:
    if not API_KEY:
        print("NEEDS_PRMR_API_KEY")
        print('$env:PRMR_API_KEY="<COPY_ONCE_KEY>"')
        print("python examples/run_external_api_consumer_smoke.py")
        return 0

    usage_status, _ = request("GET", "/v1/usage")
    ingest_status, _ = request(
        "POST",
        "/v1/events/ingest",
        {
            "events": [
                {
                    "type": "external_consumer_smoke",
                    "content": "Synthetic hosted smoke event.",
                    "timestamp_index": 1,
                }
            ]
        },
    )
    packet_status, _ = request("POST", "/v1/continuity/packet", {})
    print("PRMR External Consumer Hosted Smoke")
    print(f"Base URL: {BASE_URL}")
    print(f"GET /v1/usage: {usage_status}")
    print(f"POST /v1/events/ingest: {ingest_status}")
    print(f"POST /v1/continuity/packet: {packet_status}")
    result = "PASS" if all(status == 200 for status in [usage_status, ingest_status, packet_status]) else "NEEDS_WORK"
    print(f"Result: {result}")
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
