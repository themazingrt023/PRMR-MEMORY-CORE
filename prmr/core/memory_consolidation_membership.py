"""Deterministic manifests and complete event membership for consolidation."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any

from .memory_consolidation_models import (
    MEMORY_CONSOLIDATION_MANIFEST_REVISION,
    MEMORY_CONSOLIDATION_MEMBERSHIP_REVISION,
    ConsolidatedMemoryMember,
)
from .memory_query_results import (
    epistemic_status_for_event,
    event_time,
    signal_key_for_event,
)
from .memory_query_store import backend_name, placeholder, table
from .source_integrity import canonical_json, sha256_text
from .source_models import AuthenticatedScope


AUTHORITATIVE_MANIFEST_TABLES = (
    "prmr_memory_evolution_records",
    "prmr_memory_conflicts",
    "prmr_memory_importance_annotations",
    "prmr_entities",
    "prmr_entity_identifiers",
    "prmr_entity_alias_assertions",
    "prmr_entity_merges",
    "prmr_event_entity_links",
    "prmr_relationships",
    "prmr_relationship_evolution_records",
    "prmr_relationship_conflicts",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _payload(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _table_exists(connection: Any, repository: Any, table_name: str) -> bool:
    if backend_name(repository) == "postgres":
        row = connection.execute(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema=%s AND table_name=%s",
            ("prmr_self_serve", table_name),
        ).fetchone()
    else:
        row = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        ).fetchone()
    return bool(row)


def fast_authoritative_manifest(
    repository: Any, scope: AuthenticatedScope
) -> dict[str, Any]:
    """Hash authoritative rows only; query/consolidation artifacts are excluded."""

    p = placeholder(repository)
    scope_key = "::".join(scope.memory_boundary())
    material: dict[str, Any] = {
        "scope": list(scope.memory_boundary()),
        "revision": MEMORY_CONSOLIDATION_MANIFEST_REVISION,
        "tables": {},
    }
    with repository.connect() as connection:
        events_name = table(repository, "events")
        event_rows = connection.execute(
            f"SELECT payload_json FROM {events_name} WHERE scope_key={p}",
            (scope_key,),
        ).fetchall()
        material["tables"]["events"] = sorted(
            [_payload(row["payload_json"]) for row in event_rows],
            key=canonical_json,
        )
        for name in AUTHORITATIVE_MANIFEST_TABLES:
            if not _table_exists(connection, repository, name):
                material["tables"][name] = []
                continue
            qualified = table(repository, name)
            rows = connection.execute(
                f"SELECT * FROM {qualified} WHERE client_id={p} "
                f"AND vault_id={p} AND namespace={p}",
                scope.memory_boundary(),
            ).fetchall()
            material["tables"][name] = sorted(
                [
                    {
                        str(key): _payload(value)
                        for key, value in dict(row).items()
                    }
                    for row in rows
                ],
                key=canonical_json,
            )
    category_hashes = {
        name: sha256_text(canonical_json(values))
        for name, values in material["tables"].items()
    }
    return {
        "authoritative_manifest_hash": sha256_text(canonical_json(material)),
        "category_hashes": category_hashes,
        "event_count": sum(
            len(row) if isinstance(row, list) else 1
            for row in material["tables"].get("events", [])
        ),
        "material": material,
    }


def event_manifest(events: list[dict[str, Any]]) -> str:
    return sha256_text(
        canonical_json(
            [
                {
                    "event_id": str(item.get("event_id", "")),
                    "event_hash": sha256_text(canonical_json(item)),
                    "signal_key": signal_key_for_event(item),
                    "event_time": event_time(item),
                }
                for item in events
            ]
        )
    )


def deterministic_windows(
    events: list[dict[str, Any]], size: int, *, policy_revision: str
) -> list[dict[str, Any]]:
    windows: list[dict[str, Any]] = []
    for index in range(0, len(events), size):
        members = events[index : index + size]
        if not members:
            continue
        manifest = event_manifest(members)
        identity = sha256_text(
            canonical_json(
                {
                    "first": [
                        int(members[0].get("timestamp_index", 0)),
                        event_time(members[0]),
                        str(members[0].get("event_id", "")),
                    ],
                    "last": [
                        int(members[-1].get("timestamp_index", 0)),
                        event_time(members[-1]),
                        str(members[-1].get("event_id", "")),
                    ],
                    "manifest": manifest,
                    "policy_revision": policy_revision,
                }
            )
        )
        windows.append(
            {
                "window_id": f"mcwin_{identity[:24]}",
                "sequence_index": len(windows),
                "first_event_id": str(members[0].get("event_id", "")),
                "last_event_id": str(members[-1].get("event_id", "")),
                "event_ids": [str(item.get("event_id", "")) for item in members],
                "event_count": len(members),
                "window_start": event_time(members[0]),
                "window_end": event_time(members[-1]),
                "event_manifest_hash": manifest,
                "window_revision": "event_count_window_v1",
            }
        )
    return windows


def group_exact_signals(
    events: list[dict[str, Any]],
    windows: list[dict[str, Any]],
    minimum_group_size: int,
) -> list[dict[str, Any]]:
    by_id = {str(item.get("event_id")): item for item in events}
    groups: list[dict[str, Any]] = []
    for window in windows:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for event_id in window["event_ids"]:
            event = by_id[event_id]
            grouped.setdefault(signal_key_for_event(event), []).append(event)
        for signal_key, members in sorted(grouped.items()):
            if len(members) < minimum_group_size:
                continue
            manifest = event_manifest(members)
            groups.append(
                {
                    "group_key": f"{window['window_id']}:{signal_key}",
                    "window_id": window["window_id"],
                    "signal_key": signal_key,
                    "event_ids": [str(item["event_id"]) for item in members],
                    "event_count": len(members),
                    "first_occurrence_at": event_time(members[0]),
                    "latest_occurrence_at": event_time(members[-1]),
                    "event_manifest_hash": manifest,
                }
            )
    return groups


def build_event_members(
    consolidated_memory_id: str,
    events: list[dict[str, Any]],
    projection_by_id: dict[str, Any],
    *,
    created_at: str | None = None,
) -> list[ConsolidatedMemoryMember]:
    created = created_at or _utc_now()
    members: list[ConsolidatedMemoryMember] = []
    for index, event in enumerate(events):
        event_id = str(event.get("event_id"))
        projection = projection_by_id.get(event_id)
        role = (
            "first"
            if index == 0
            else "latest"
            if index == len(events) - 1
            else "contributing"
        )
        material = {
            "consolidated_memory_id": consolidated_memory_id,
            "event_id": event_id,
            "sequence_index": index,
            "event_hash": sha256_text(canonical_json(event)),
            "role": role,
            "membership_revision": MEMORY_CONSOLIDATION_MEMBERSHIP_REVISION,
        }
        digest = sha256_text(canonical_json(material))
        status = (
            str(projection.epistemic_status)
            if projection
            else epistemic_status_for_event(event)
        )
        members.append(
            ConsolidatedMemoryMember(
                consolidated_memory_member_id=f"cmemmem_{digest[:24]}",
                consolidated_memory_id=consolidated_memory_id,
                member_type="event",
                event_id=event_id,
                source_id=projection.source_id if projection else None,
                candidate_id=None,
                admission_id=projection.admission_id if projection else None,
                evolution_id=None,
                conflict_id=(
                    projection.open_conflict_ids[0]
                    if projection and projection.open_conflict_ids
                    else None
                ),
                entity_id=None,
                relationship_id=None,
                sequence_index=index,
                member_role=role,
                member_hash_sha256=digest,
                effective_state=(
                    str(projection.effective_state) if projection else "active"
                ),
                epistemic_status=status,
                valid_from=(
                    str(projection.valid_from)
                    if projection
                    else event_time(event)
                ),
                valid_until=projection.valid_until if projection else None,
                system_known_from=(
                    str(projection.system_known_from)
                    if projection
                    else event_time(event)
                ),
                system_known_until=(
                    projection.system_known_until if projection else None
                ),
                membership_revision=MEMORY_CONSOLIDATION_MEMBERSHIP_REVISION,
                created_at=created,
            )
        )
    return members


__all__ = [
    "AUTHORITATIVE_MANIFEST_TABLES",
    "build_event_members",
    "deterministic_windows",
    "event_manifest",
    "fast_authoritative_manifest",
    "group_exact_signals",
]
