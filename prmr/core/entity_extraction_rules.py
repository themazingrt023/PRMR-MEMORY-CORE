"""Conservative deterministic entity extraction rules for Core Sprint 6."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Iterable

from .entity_models import validate_entity_type
from .entity_store import normalise_label, safe_display


SCOPE_FIELDS = {
    "client_id",
    "vault_id",
    "namespace",
    "api_key",
    "authorization",
    "authentication_token",
    "token",
}
IDENTIFIER_FIELDS = {
    "entity_id": "entity",
    "entity_reference": "entity",
    "external_id": "external",
    "actor_id": "actor",
    "actor_reference": "actor",
    "user_id": "user",
    "account_id": "account",
    "project_id": "project",
    "device_id": "device",
    "character_id": "character",
    "organisation_id": "organisation",
    "organization_id": "organisation",
    "document_id": "document",
    "system_id": "software_system",
}
TYPE_BY_FIELD = {
    "user_id": "person",
    "account_id": "account",
    "project_id": "project",
    "device_id": "device",
    "character_id": "character",
    "organisation_id": "organisation",
    "organization_id": "organisation",
    "document_id": "document",
    "system_id": "software_system",
}
LABEL_TYPE_MAP = {
    "person": "person",
    "organisation": "organisation",
    "organization": "organisation",
    "project": "project",
    "account": "account",
    "agent": "agent",
    "character": "character",
    "device": "device",
    "document": "document",
    "location": "location",
    "concept": "concept",
    "system": "software_system",
    "entity": "unknown",
}
EXPLICIT_LABEL_RE = re.compile(
    r"(?im)^(Person|Organisation|Organization|Project|Account|Agent|Character|"
    r"Device|Document|Location|Concept|System|Entity)\s*:\s*([^\r\n]+?)\s*$"
)
IDENTITY_STATEMENT_RE = re.compile(
    r"(?im)^\s*([^.\r\n:]{1,120}?)\s+is\s+(?:an?\s+)?"
    r"(person|organisation|organization|project|account|agent|character|device|"
    r"document|location|concept|system)\s*\.\s*$"
)
ALSO_KNOWN_RE = re.compile(
    r"(?im)^\s*([^.\r\n]{1,120}?),?\s+also known as\s+([^.\r\n]{1,120})\s*\.\s*$"
)
PREVIOUSLY_CALLED_RE = re.compile(
    r"(?im)^\s*([^.\r\n]{1,120}?)\s+was previously called\s+"
    r"([^.\r\n]{1,120})\s*\.\s*$"
)


@dataclass(frozen=True)
class ExtractedEntity:
    entity_type: str
    label: str | None
    identifiers: list[tuple[str, str, str]] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    epistemic_status: str = "explicit"
    extraction_confidence: float = 1.0
    confidence_basis: str = "explicit deterministic structure"
    extraction_method: str = "structured_field"
    primary_rule_id: str = "entity.structured.explicit_v1"
    matched_rule_ids: list[str] = field(default_factory=list)
    json_pointer: str | None = None
    mention_role: str = "referenced"
    speaker: str | None = None
    occurred_at: str | None = None
    source_text: str = ""


def _pointer(parent: str, key: str | int) -> str:
    token = str(key).replace("~", "~0").replace("/", "~1")
    return f"{parent}/{token}" if parent else f"/{token}"


def _safe_identifier(value: Any) -> str | None:
    if isinstance(value, (str, int)) and str(value).strip():
        clean = str(value).strip()
        return clean if len(clean) <= 512 else None
    return None


def _structured_objects(value: Any, pointer: str = "") -> Iterable[tuple[dict[str, Any], str]]:
    if isinstance(value, dict):
        yield value, pointer
        for key, child in value.items():
            yield from _structured_objects(child, _pointer(pointer, key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _structured_objects(child, _pointer(pointer, index))


def extract_structured_entities(payload: Any, source_type: str) -> list[ExtractedEntity]:
    extracted: list[ExtractedEntity] = []
    for item, pointer in _structured_objects(payload):
        entity_type = str(item.get("entity_type") or "").strip().lower()
        label = item.get("name") or item.get("label")
        identifiers: list[tuple[str, str, str]] = []
        for field_name, namespace in IDENTIFIER_FIELDS.items():
            if field_name in SCOPE_FIELDS or field_name not in item:
                continue
            identifier = _safe_identifier(item.get(field_name))
            if identifier is None:
                continue
            identifiers.append((namespace, identifier, field_name))
            entity_type = entity_type or TYPE_BY_FIELD.get(field_name, "unknown")
        aliases = [
            safe_display(alias)
            for alias in item.get("aliases", [])
            if isinstance(alias, str) and safe_display(alias)
        ] if isinstance(item.get("aliases"), list) else []
        role = "referenced"
        if any(key in item for key in ("actor_id", "actor_reference", "user_id")):
            role = "actor"
        if "owner_id" in item:
            role = "owner"
        if identifiers or label:
            if not entity_type:
                entity_type = "unknown"
            extracted.append(
                ExtractedEntity(
                    entity_type=validate_entity_type(entity_type),
                    label=safe_display(label) or None,
                    identifiers=identifiers,
                    aliases=aliases,
                    extraction_confidence=1.0 if identifiers else 0.95,
                    confidence_basis=(
                        "explicit stable identifier field"
                        if identifiers
                        else "explicit structured label without stable identity"
                    ),
                    primary_rule_id=(
                        "entity.structured.identifier_v1"
                        if identifiers
                        else "entity.structured.label_only_v1"
                    ),
                    matched_rule_ids=["entity.structured.explicit_v1"],
                    json_pointer=pointer or "/",
                    mention_role=role,
                    occurred_at=(
                        str(item.get("occurred_at"))
                        if item.get("occurred_at")
                        else None
                    ),
                    source_text=safe_display(
                        label if label else (identifiers[0][1] if identifiers else "")
                    ),
                )
            )

        # Timeline/conversation fields can carry explicit entities without a
        # general entity object.
        for field_name, role_name in (
            ("subject", "subject"),
            ("actor", "actor"),
            ("participant", "participant"),
            ("speaker", "speaker"),
            ("author", "author"),
            ("recipient", "recipient"),
        ):
            raw = item.get(field_name)
            if raw in (None, ""):
                continue
            if isinstance(raw, dict):
                continue
            label_value = safe_display(raw)
            if not label_value:
                continue
            id_field = f"{field_name}_id"
            stable_value = _safe_identifier(item.get(id_field))
            explicit_type = str(item.get(f"{field_name}_type") or "unknown")
            extracted.append(
                ExtractedEntity(
                    entity_type=validate_entity_type(explicit_type),
                    label=label_value,
                    identifiers=(
                        [(field_name, stable_value, id_field)] if stable_value else []
                    ),
                    extraction_confidence=1.0 if stable_value else 0.9,
                    confidence_basis=(
                        "structured participant identifier"
                        if stable_value
                        else "structured participant label without stable identity"
                    ),
                    primary_rule_id=f"entity.{source_type}.{field_name}_v1",
                    matched_rule_ids=["entity.structured.participant_v1"],
                    json_pointer=_pointer(pointer, field_name),
                    mention_role=role_name,
                    speaker=label_value if field_name == "speaker" else None,
                    occurred_at=(
                        str(item.get("occurred_at"))
                        if item.get("occurred_at")
                        else None
                    ),
                    source_text=label_value,
                )
            )
    return extracted


def extract_explicit_text_entities(text: str) -> list[ExtractedEntity]:
    found: list[ExtractedEntity] = []
    for match in EXPLICIT_LABEL_RE.finditer(text):
        entity_type = LABEL_TYPE_MAP[match.group(1).lower()]
        label = safe_display(match.group(2))
        if label:
            found.append(
                ExtractedEntity(
                    entity_type=entity_type,
                    label=label,
                    extraction_confidence=0.95,
                    confidence_basis="explicit labelled entity statement",
                    extraction_method="explicit_label",
                    primary_rule_id="entity.text.explicit_label_v1",
                    matched_rule_ids=["entity.text.conservative_v1"],
                    source_text=match.group(0),
                )
            )
    for match in IDENTITY_STATEMENT_RE.finditer(text):
        label = safe_display(match.group(1))
        entity_type = LABEL_TYPE_MAP[match.group(2).lower()]
        if label:
            found.append(
                ExtractedEntity(
                    entity_type=entity_type,
                    label=label,
                    extraction_confidence=0.95,
                    confidence_basis="explicit identity statement",
                    extraction_method="deterministic_pattern",
                    primary_rule_id="entity.text.identity_statement_v1",
                    matched_rule_ids=["entity.text.conservative_v1"],
                    source_text=match.group(0),
                )
            )
    for pattern, rule_id in (
        (ALSO_KNOWN_RE, "entity.text.also_known_as_v1"),
        (PREVIOUSLY_CALLED_RE, "entity.text.previously_called_v1"),
    ):
        for match in pattern.finditer(text):
            label, alias = safe_display(match.group(1)), safe_display(match.group(2))
            if label and alias and normalise_label(label) != normalise_label(alias):
                found.append(
                    ExtractedEntity(
                        entity_type="unknown",
                        label=label,
                        aliases=[alias],
                        extraction_confidence=0.95,
                        confidence_basis="explicit alias statement",
                        extraction_method="deterministic_pattern",
                        primary_rule_id=rule_id,
                        matched_rule_ids=["entity.text.explicit_alias_v1"],
                        source_text=match.group(0),
                    )
                )
    return found


def extract_entities(payload: Any, source_type: str) -> list[ExtractedEntity]:
    results: list[ExtractedEntity] = []
    if source_type in {"json", "conversation", "timeline", "log"}:
        results.extend(extract_structured_entities(payload, source_type))
    if source_type in {"plain_text", "markdown"} and isinstance(payload, str):
        results.extend(extract_explicit_text_entities(payload))
    unique: dict[tuple[Any, ...], ExtractedEntity] = {}
    for item in results:
        key = (
            item.entity_type,
            normalise_label(item.label),
            tuple(sorted(item.identifiers)),
            tuple(sorted(normalise_label(alias) for alias in item.aliases)),
            item.json_pointer,
            item.mention_role,
        )
        unique.setdefault(key, item)
    return list(unique.values())


__all__ = ["ExtractedEntity", "extract_entities"]
