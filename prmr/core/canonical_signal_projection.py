"""Deterministic, bitemporal event-to-canonical-signal projection."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any

from .canonical_signal_models import (
    CANONICAL_SIGNAL_PROJECTION_REVISION,
    EventSignalProjection,
)
from .canonical_signal_registry import (
    CanonicalSignalRegistry,
    initialize_canonical_signal_schema,
)
from .entity_store import json_value, placeholder, scope_params, table
from .memory_query_results import signal_key_for_event
from .source_integrity import canonical_json, sha256_text
from .source_models import AuthenticatedScope


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def event_metadata_canonical_signal(event: dict[str, Any]) -> str | None:
    metadata = event.get("external_metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    nested = metadata.get("metadata", {})
    if not isinstance(nested, dict):
        nested = {}
    direct = event.get("metadata", {})
    if not isinstance(direct, dict):
        direct = {}
    value = (
        nested.get("canonical_signal")
        or metadata.get("canonical_signal")
        or direct.get("canonical_signal")
    )
    return str(value) if isinstance(value, str) and value else None


def initialize_signal_projection_schema(repository: Any) -> None:
    initialize_canonical_signal_schema(repository)
    prefix = "prmr_self_serve." if str(getattr(repository, "backend_name", "sqlite")) == "postgres" else ""
    json_type = "JSONB" if prefix else "TEXT"
    with repository.connect() as connection:
        connection.execute(
            f"""CREATE TABLE IF NOT EXISTS {prefix}prmr_event_signal_projections (
                event_signal_projection_id TEXT PRIMARY KEY, event_id TEXT NOT NULL,
                client_id TEXT NOT NULL, vault_id TEXT NOT NULL, namespace TEXT NOT NULL,
                original_signal_key TEXT NOT NULL, canonical_signal_key TEXT NOT NULL,
                mapping_applied INTEGER NOT NULL, valid_at TEXT NOT NULL, known_at TEXT NOT NULL,
                projection_hash_sha256 TEXT NOT NULL, created_at TEXT NOT NULL,
                payload_json {json_type} NOT NULL,
                UNIQUE(event_id,client_id,vault_id,namespace,valid_at,known_at,
                       projection_hash_sha256)
            )"""
        )
        connection.execute(
            f"CREATE INDEX IF NOT EXISTS prmr_esig_scope_idx ON "
            f"{prefix}prmr_event_signal_projections(client_id,vault_id,namespace,event_id)"
        )


class CanonicalSignalProjector:
    def __init__(self, repository: Any, *, initialize: bool = True) -> None:
        self.repository = repository
        if initialize:
            initialize_signal_projection_schema(repository)
        self.registry = CanonicalSignalRegistry(repository, initialize=False)
        self.table = table(repository, "prmr_event_signal_projections")
        self.p = placeholder(repository)

    def project_event(
        self,
        scope: AuthenticatedScope,
        event: dict[str, Any],
        *,
        valid_at: str,
        known_at: str,
        persist: bool = True,
    ) -> EventSignalProjection:
        event_id = str(event.get("event_id", ""))
        original = signal_key_for_event(event)
        resolution = self.registry.resolve_canonical_signal(
            scope, original, valid_at=valid_at, known_at=known_at
        )
        declared_canonical = event_metadata_canonical_signal(event)
        metadata_mapping_approved = (
            resolution.mapping_applied
            and declared_canonical is not None
            and declared_canonical in resolution.mapping_chain[1:]
        )
        mapping_source = (
            "approved_event_metadata"
            if metadata_mapping_approved
            else (
                "approved_alias_assertion"
                if resolution.mapping_applied
                else "original_event_signal"
            )
        )
        material = {
            "event_id": event_id,
            "scope": scope.memory_boundary(),
            "original_signal_key": original,
            "canonical_signal_key": resolution.canonical_signal_key,
            "mapping_source": mapping_source,
            "mapping_manifest": resolution.manifest_hash_sha256,
            "valid_at": valid_at,
            "known_at": known_at,
            "revision": CANONICAL_SIGNAL_PROJECTION_REVISION,
        }
        digest = sha256_text(canonical_json(material))
        projection = EventSignalProjection(
            event_signal_projection_id=f"esig_{digest[:24]}",
            event_id=event_id,
            client_id=scope.client_id,
            vault_id=scope.vault_id,
            namespace=scope.namespace,
            original_signal_key=original,
            canonical_signal_key=resolution.canonical_signal_key,
            mapping_applied=resolution.mapping_applied,
            mapping_source=mapping_source,
            alias_assertion_id=(
                resolution.alias_assertion_ids[-1]
                if resolution.alias_assertion_ids
                else None
            ),
            mapping_decision_id=(
                resolution.mapping_decision_ids[-1]
                if resolution.mapping_decision_ids
                else None
            ),
            valid_at=valid_at,
            known_at=known_at,
            projection_revision=CANONICAL_SIGNAL_PROJECTION_REVISION,
            projection_hash_sha256=digest,
            created_at=known_at,
        )
        if persist:
            with self.repository.connect() as connection:
                values = (
                    projection.event_signal_projection_id,
                    event_id,
                    scope.client_id,
                    scope.vault_id,
                    scope.namespace,
                    original,
                    projection.canonical_signal_key,
                    projection.mapping_applied,
                    valid_at,
                    known_at,
                    digest,
                    known_at,
                    json_value(self.repository, projection.to_dict()),
                )
                if str(getattr(self.repository, "backend_name", "sqlite")) == "postgres":
                    connection.execute(
                        f"INSERT INTO {self.table}(event_signal_projection_id,event_id,"
                        f"client_id,vault_id,namespace,original_signal_key,"
                        f"canonical_signal_key,mapping_applied,valid_at,known_at,"
                        f"projection_hash_sha256,created_at,payload_json) "
                        f"VALUES({','.join([self.p]*13)}) ON CONFLICT "
                        "(event_signal_projection_id) DO NOTHING",
                        values,
                    )
                else:
                    connection.execute(
                        f"INSERT OR IGNORE INTO {self.table}(event_signal_projection_id,"
                        f"event_id,client_id,vault_id,namespace,original_signal_key,"
                        f"canonical_signal_key,mapping_applied,valid_at,known_at,"
                        f"projection_hash_sha256,created_at,payload_json) "
                        f"VALUES({','.join([self.p]*13)})",
                        values,
                    )
        return projection

    def project_events(
        self,
        scope: AuthenticatedScope,
        events: list[dict[str, Any]],
        *,
        valid_at: str,
        known_at: str,
        persist: bool = True,
    ) -> list[EventSignalProjection]:
        return [
            self.project_event(
                scope,
                event,
                valid_at=valid_at,
                known_at=known_at,
                persist=persist,
            )
            for event in events
        ]

    def verify_signal_projection_integrity(
        self, scope: AuthenticatedScope, projection_id: str
    ) -> dict[str, Any]:
        with self.repository.connect() as connection:
            row = connection.execute(
                f"SELECT payload_json FROM {self.table} WHERE "
                f"event_signal_projection_id={self.p} AND client_id={self.p} "
                f"AND vault_id={self.p} AND namespace={self.p}",
                (projection_id, *scope_params(scope)),
            ).fetchone()
        if not row:
            return {"verified": False, "failures": ["projection_not_found"]}
        payload = row["payload_json"]
        payload = payload if isinstance(payload, dict) else json.loads(payload)
        material = {
            "event_id": payload["event_id"],
            "scope": scope.memory_boundary(),
            "original_signal_key": payload["original_signal_key"],
            "canonical_signal_key": payload["canonical_signal_key"],
            "mapping_source": payload["mapping_source"],
            "mapping_manifest": self.registry.resolve_canonical_signal(
                scope,
                payload["original_signal_key"],
                valid_at=payload["valid_at"],
                known_at=payload["known_at"],
            ).manifest_hash_sha256,
            "valid_at": payload["valid_at"],
            "known_at": payload["known_at"],
            "revision": CANONICAL_SIGNAL_PROJECTION_REVISION,
        }
        valid = sha256_text(canonical_json(material)) == payload["projection_hash_sha256"]
        return {
            "verified": valid,
            "checks": {"projection_hash": valid, "scope": True},
            "failures": [] if valid else ["projection_hash"],
        }


__all__ = [
    "CanonicalSignalProjector",
    "event_metadata_canonical_signal",
    "initialize_signal_projection_schema",
]
