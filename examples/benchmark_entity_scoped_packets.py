"""Small local measurement helper for entity-scoped PRMR packets."""

from __future__ import annotations

import statistics
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from prmr.product.api_server_v094 import create_app_v094
from prmr.product.durable_self_serve_storage_v093 import DurableSelfServeProductV093


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="prmr-bench-", ignore_cleanup_errors=True) as temp_dir:
        product = DurableSelfServeProductV093(Path(temp_dir) / "bench.sqlite")
        with TestClient(create_app_v094(product)) as client:
            signup = client.post("/v1/self-serve/signup", json={"name": "Bench", "email": "bench@example.test", "password": "bench-password"})
            user_id = signup.json()["account"]["user_id"]
            client.post("/v1/self-serve/verify", json={"user_id": user_id})
            session = client.post("/v1/self-serve/login", json={"email": "bench@example.test", "password": "bench-password"}).json()["session_token"]
            session_headers = {"Authorization": f"Session {session}"}
            client.post("/v1/self-serve/plan", headers=session_headers, json={"plan_id": "free"})
            client.post("/v1/self-serve/provision", headers=session_headers)
            key = client.post("/v1/self-serve/keys", headers=session_headers, json={"label": "Benchmark"}).json()["raw_api_key"]
            bearer = {"Authorization": f"Bearer {key}"}
            event_total = 90
            events = [
                {
                    "event_type": "bench.event",
                    "signal": f"Benchmark event {index}",
                    "occurred_at": f"2026-07-20T10:{index % 60:02d}:00Z",
                    "application_reference": "app_bench",
                    "actor_reference": f"actor_{index % 10}",
                    "workspace_reference": f"workspace_{index % 3}",
                    "entity_reference": f"entity_{index % 25}",
                    "idempotency_key": f"bench-{index}",
                    "timestamp_index": index + 1,
                }
                for index in range(event_total)
            ]
            ingest_start = time.perf_counter()
            ingest = client.post("/v1/events/ingest", headers=bearer, json={"events": events})
            ingest_ms = (time.perf_counter() - ingest_start) * 1000
            packet_times = []
            for _ in range(20):
                start = time.perf_counter()
                packet = client.post(
                    "/v1/continuity/packet",
                    headers=bearer,
                    json={
                        "application_reference": "app_bench",
                        "actor_reference": "actor_1",
                        "entity_reference": "entity_1",
                        "allow_broad_scope": True,
                    },
                )
                packet.raise_for_status()
                packet_times.append((time.perf_counter() - start) * 1000)
            print("PRMR Entity-Scoped Packet Benchmark")
            print(f"Dataset: local synthetic, events={len(events)}, ingest_status={ingest.status_code}")
            print(f"ingest_ms={ingest_ms:.2f}")
            print(f"packet_p50_ms={statistics.median(packet_times):.2f}")
            print(f"packet_p95_ms={statistics.quantiles(packet_times, n=20)[18]:.2f}")
            print("Truth label: local synthetic measurement only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
