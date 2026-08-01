"""Conservative deterministic relationship extraction rules."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable

from .relationship_models import validate_relationship_type
from .entity_store import safe_display


@dataclass(frozen=True)
class ExtractedRelationship:
    subject_reference: str
    object_reference: str
    relationship_type: str
    epistemic_status: str
    extraction_confidence: float
    extraction_method: str
    primary_rule_id: str
    matched_rule_ids: list[str]
    json_pointer: str | None = None
    proposed_valid_from: str | None = None
    proposed_valid_until: str | None = None
    source_text: str = ""
    quoted_claim: bool = False
    future_or_planned: bool = False


STRUCTURED_KEYS = ("relationship", "relationship_type", "predicate")
TEXT_PATTERNS = (
    ("owns", re.compile(r"(?i)^(.+?)\s+owns\s+(.+?)\.?$")),
    ("belongs_to", re.compile(r"(?i)^(.+?)\s+belongs to\s+(.+?)\.?$")),
    ("depends_on", re.compile(r"(?i)^(.+?)\s+depends on\s+(.+?)\.?$")),
    ("supports", re.compile(r"(?i)^(.+?)\s+supports\s+(.+?)\.?$")),
    ("opposes", re.compile(r"(?i)^(.+?)\s+opposes\s+(.+?)\.?$")),
    ("member_of", re.compile(r"(?i)^(.+?)\s+is a member of\s+(.+?)\.?$")),
    ("authored", re.compile(r"(?i)^(.+?)\s+authored\s+(.+?)\.?$")),
    ("located_in", re.compile(r"(?i)^(.+?)\s+is located in\s+(.+?)\.?$")),
    ("participates_in", re.compile(r"(?i)^(.+?)\s+participated in\s+(.+?)\.?$")),
    ("interacts_with", re.compile(r"(?i)^(.+?)\s+interacted with\s+(.+?)\.?$")),
)
LABEL_BLOCK_RE = re.compile(
    r"(?ims)Subject\s*:\s*(?P<subject>[^\r\n]+)\s*\r?\n"
    r"Relationship\s*:\s*(?P<relationship>[a-zA-Z0-9_.]+)\s*\r?\n"
    r"Object\s*:\s*(?P<object>[^\r\n]+)"
)
NEGATION_RE = re.compile(
    r"(?i)\b(?:not|does not|did not|is not|never|no longer)\b"
)
INFERRED_MODAL_RE = re.compile(r"(?i)\b(?:may|might|could|possibly|perhaps)\b")
FUTURE_MODAL_RE = re.compile(r"(?i)\b(?:will|plans? to|intends? to)\b")
QUOTED_CLAIM_RE = re.compile(r"(?i)\b(?:said|stated|claimed|reported)\b")
MODAL_DEPENDS_RE = re.compile(
    r"(?i)^(.+?)\s+(may|might|could|possibly|will)\s+depend on\s+(.+?)\.?$"
)


def _pointer(parent: str, key: str | int) -> str:
    token = str(key).replace("~", "~0").replace("/", "~1")
    return f"{parent}/{token}" if parent else f"/{token}"


def _objects(value: Any, pointer: str = "") -> Iterable[tuple[dict[str, Any], str]]:
    if isinstance(value, dict):
        yield value, pointer
        for key, child in value.items():
            yield from _objects(child, _pointer(pointer, key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _objects(child, _pointer(pointer, index))


def extract_structured_relationships(payload: Any) -> list[ExtractedRelationship]:
    output: list[ExtractedRelationship] = []
    for item, pointer in _objects(payload):
        relation_key = next((key for key in STRUCTURED_KEYS if item.get(key)), None)
        if relation_key and item.get("subject") and item.get("object"):
            relation = validate_relationship_type(str(item[relation_key]))
            output.append(
                ExtractedRelationship(
                    subject_reference=safe_display(item["subject"], 512),
                    object_reference=safe_display(item["object"], 512),
                    relationship_type=relation,
                    epistemic_status=str(item.get("epistemic_status") or "explicit"),
                    extraction_confidence=1.0,
                    extraction_method="structured_field",
                    primary_rule_id="relationship.structured.triple_v1",
                    matched_rule_ids=["relationship.structured.explicit_v1"],
                    json_pointer=pointer or "/",
                    proposed_valid_from=(
                        str(item.get("valid_from")) if item.get("valid_from") else None
                    ),
                    proposed_valid_until=(
                        str(item.get("valid_until")) if item.get("valid_until") else None
                    ),
                    source_text=f"{item['subject']} {relation} {item['object']}",
                )
            )
        if item.get("owner_id") and item.get("project_id"):
            output.append(
                ExtractedRelationship(
                    subject_reference=safe_display(item["owner_id"], 512),
                    object_reference=safe_display(item["project_id"], 512),
                    relationship_type="owns",
                    epistemic_status="explicit",
                    extraction_confidence=1.0,
                    extraction_method="structured_field",
                    primary_rule_id="relationship.structured.owner_project_v1",
                    matched_rule_ids=["relationship.structured.explicit_v1"],
                    json_pointer=pointer or "/",
                    source_text="explicit owner/project relationship",
                )
            )
    return output


def extract_text_relationships(text: str) -> list[ExtractedRelationship]:
    output: list[ExtractedRelationship] = []
    for match in LABEL_BLOCK_RE.finditer(text):
        relation = validate_relationship_type(match.group("relationship"))
        output.append(
            ExtractedRelationship(
                subject_reference=safe_display(match.group("subject"), 512),
                object_reference=safe_display(match.group("object"), 512),
                relationship_type=relation,
                epistemic_status="explicit",
                extraction_confidence=0.98,
                extraction_method="explicit_label",
                primary_rule_id="relationship.text.label_block_v1",
                matched_rule_ids=["relationship.text.explicit_v1"],
                source_text=match.group(0),
            )
        )
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or NEGATION_RE.search(line):
            continue
        modal = MODAL_DEPENDS_RE.fullmatch(line)
        if modal:
            future = modal.group(2).lower() == "will"
            output.append(
                ExtractedRelationship(
                    subject_reference=safe_display(modal.group(1), 512),
                    object_reference=safe_display(modal.group(3), 512),
                    relationship_type="depends_on",
                    epistemic_status="inferred",
                    extraction_confidence=0.75,
                    extraction_method="deterministic_pattern",
                    primary_rule_id="relationship.text.modal_depends_on_v1",
                    matched_rule_ids=["relationship.text.modality_v1"],
                    source_text=line,
                    future_or_planned=future,
                )
            )
            continue
        for relationship_type, pattern in TEXT_PATTERNS:
            match = pattern.fullmatch(line)
            if not match:
                continue
            inferred = bool(INFERRED_MODAL_RE.search(line))
            future = bool(FUTURE_MODAL_RE.search(line))
            quoted = bool(QUOTED_CLAIM_RE.search(line))
            output.append(
                ExtractedRelationship(
                    subject_reference=safe_display(match.group(1), 512),
                    object_reference=safe_display(match.group(2), 512),
                    relationship_type=relationship_type,
                    epistemic_status=(
                        "inferred" if inferred or future or quoted else "explicit"
                    ),
                    extraction_confidence=(
                        0.8 if inferred or future or quoted else 0.95
                    ),
                    extraction_method="deterministic_pattern",
                    primary_rule_id=f"relationship.text.{relationship_type}_v1",
                    matched_rule_ids=["relationship.text.conservative_v1"],
                    source_text=line,
                    quoted_claim=quoted,
                    future_or_planned=future,
                )
            )
            break
    return output


def extract_relationships(payload: Any, source_type: str) -> list[ExtractedRelationship]:
    found: list[ExtractedRelationship] = []
    if source_type in {"json", "conversation", "timeline", "log"}:
        found.extend(extract_structured_relationships(payload))
    if source_type in {"plain_text", "markdown"} and isinstance(payload, str):
        found.extend(extract_text_relationships(payload))
    unique: dict[tuple[Any, ...], ExtractedRelationship] = {}
    for item in found:
        key = (
            item.subject_reference,
            item.relationship_type,
            item.object_reference,
            item.json_pointer,
            item.epistemic_status,
        )
        unique.setdefault(key, item)
    return list(unique.values())


__all__ = ["ExtractedRelationship", "extract_relationships"]
