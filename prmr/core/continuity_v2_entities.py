"""Scope-bound entity context projection for V2 packets."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .continuity_v2_models import ContinuityEntityContextV2
from .entity_identity_service import EntityIdentityService
from .source_integrity import canonical_json, sha256_text
from .source_models import AuthenticatedScope


def build_entity_context(
    repository: Any,
    scope: AuthenticatedScope,
    event_ids: set[str],
    information_by_event: dict[str, dict[str, Any]],
    relationship_ids_by_entity: dict[str, list[str]],
    *,
    requested_entity_id: str | None,
    valid_at: str,
    known_at: str,
) -> list[ContinuityEntityContextV2]:
    identity = EntityIdentityService(repository, initialize=False)
    links = identity.list_event_links(
        scope, valid_at=valid_at, known_at=known_at, current_only=True
    )
    links = [item for item in links if item.event_id in event_ids]
    entity_ids = {item.entity_id for item in links}
    if requested_entity_id:
        canonical = identity.resolver.resolve_canonical_entity_id(
            scope, requested_entity_id, known_at=known_at
        )
        entity_ids = {canonical}
    contexts: list[ContinuityEntityContextV2] = []
    for raw_id in sorted(entity_ids):
        canonical = identity.resolver.resolve_canonical_entity_id(
            scope, raw_id, known_at=known_at
        )
        entity = identity.resolver.get_entity(scope, canonical)
        linked = sorted(
            {
                item.event_id
                for item in links
                if identity.resolver.resolve_canonical_entity_id(
                    scope, item.entity_id, known_at=known_at
                )
                == canonical
            }
        )
        aliases = identity.list_aliases(
            scope, canonical, valid_at=valid_at, known_at=known_at
        )
        counts: Counter[str] = Counter()
        conflict_ids: set[str] = set()
        for event_id in linked:
            item = information_by_event.get(event_id, {})
            counts[str(item.get("packet_epistemic_class", "unknown"))] += 1
            conflict_ids.update(item.get("conflict_ids", []))
        material = {
            "requested": requested_entity_id,
            "canonical": canonical,
            "type": entity.canonical_entity_type,
            "label": entity.canonical_label,
            "aliases": sorted(item.alias_value for item in aliases),
            "events": linked,
            "relationships": sorted(relationship_ids_by_entity.get(canonical, [])),
            "conflicts": sorted(conflict_ids),
            "revision": "continuity_entity_context_v1",
        }
        contexts.append(
            ContinuityEntityContextV2(
                requested_entity_id=requested_entity_id if requested_entity_id else raw_id,
                canonical_entity_id=canonical,
                entity_type=entity.canonical_entity_type,
                canonical_label=entity.canonical_label,
                active_aliases=sorted(item.alias_value for item in aliases),
                identity_status=entity.entity_status,
                linked_event_ids=linked,
                asserted_memory_count=counts["asserted"],
                derived_memory_count=counts["derived_assertion"],
                tentative_memory_count=counts["tentative"],
                unknown_memory_count=counts["unknown"],
                conflicted_memory_count=sum(
                    1 for event_id in linked if information_by_event.get(event_id, {}).get("conflict_ids")
                ),
                active_relationship_ids=sorted(relationship_ids_by_entity.get(canonical, [])),
                entity_conflict_ids=sorted(conflict_ids),
                entity_view_hash=sha256_text(canonical_json(material)),
            )
        )
    return contexts


__all__ = ["build_entity_context"]
