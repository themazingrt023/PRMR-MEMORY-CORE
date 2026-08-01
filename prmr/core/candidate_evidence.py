"""Evidence construction and exact provenance resolution for candidates."""

from __future__ import annotations

from typing import Any

from .candidate_models import CandidateEngineError, CandidateEvidence, EvidenceRole
from .candidate_rules import EvidenceSpec
from .source_integrity import canonical_json, sha256_text
from .source_models import SourceRecord, SourceSegment


def resolve_json_pointer(document: Any, pointer: str) -> Any:
    if pointer == "":
        return document
    if not pointer.startswith("/"):
        raise CandidateEngineError("CANDIDATE_EVIDENCE_INVALID", "Evidence JSON pointer is invalid.")
    current = document
    for token in pointer[1:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        try:
            current = current[int(token)] if isinstance(current, list) else current[token]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise CandidateEngineError(
                "CANDIDATE_EVIDENCE_INVALID",
                "Evidence JSON pointer does not resolve inside the source.",
            ) from exc
    return current


def evidence_text_from_source(
    source: SourceRecord,
    segment: SourceSegment,
    *,
    source_start_offset: int | None,
    source_end_offset: int | None,
    segment_start_offset: int | None,
    segment_end_offset: int | None,
    json_pointer: str | None,
) -> str:
    if json_pointer is not None:
        value = resolve_json_pointer(source.sanitised_payload, json_pointer)
        text = value if isinstance(value, str) else canonical_json(value)
        if segment_start_offset is None and segment_end_offset is None:
            return text
        if (
            segment_start_offset is None
            or segment_end_offset is None
            or not 0 <= segment_start_offset < segment_end_offset <= len(text)
        ):
            raise CandidateEngineError(
                "CANDIDATE_EVIDENCE_INVALID",
                "Structured evidence offsets are outside the referenced value.",
            )
        resolved = text[segment_start_offset:segment_end_offset]
        if segment.content[segment_start_offset:segment_end_offset] != resolved:
            raise CandidateEngineError(
                "CANDIDATE_EVIDENCE_INVALID",
                "Structured evidence does not match its source segment.",
            )
        return resolved
    if not isinstance(source.sanitised_payload, str):
        raise CandidateEngineError(
            "CANDIDATE_EVIDENCE_INVALID",
            "Text offsets require a text-backed source.",
        )
    if None in (source_start_offset, source_end_offset, segment_start_offset, segment_end_offset):
        raise CandidateEngineError("CANDIDATE_EVIDENCE_INVALID", "Text evidence offsets are incomplete.")
    assert source_start_offset is not None
    assert source_end_offset is not None
    assert segment_start_offset is not None
    assert segment_end_offset is not None
    if not (
        0 <= source_start_offset < source_end_offset <= len(source.sanitised_payload)
        and 0 <= segment_start_offset < segment_end_offset <= len(segment.content)
    ):
        raise CandidateEngineError("CANDIDATE_EVIDENCE_INVALID", "Evidence offsets are outside source bounds.")
    source_text = source.sanitised_payload[source_start_offset:source_end_offset]
    segment_text = segment.content[segment_start_offset:segment_end_offset]
    if source_text != segment_text:
        raise CandidateEngineError(
            "CANDIDATE_EVIDENCE_INVALID",
            "Source and segment evidence spans do not match.",
        )
    return source_text


def evidence_identity(spec: EvidenceSpec) -> dict[str, Any]:
    return {
        "segment_id": spec.segment_id,
        "evidence_role": spec.evidence_role,
        "source_start_offset": spec.source_start_offset,
        "source_end_offset": spec.source_end_offset,
        "segment_start_offset": spec.segment_start_offset,
        "segment_end_offset": spec.segment_end_offset,
        "json_pointer": spec.json_pointer,
        "evidence_text_hash_sha256": sha256_text(spec.text),
    }


def evidence_manifest_hash(specs: list[EvidenceSpec]) -> str:
    ordered = [evidence_identity(spec) for spec in specs]
    return sha256_text(canonical_json(ordered))


def materialize_evidence(
    *,
    candidate_id: str,
    source: SourceRecord,
    segment_by_id: dict[str, SourceSegment],
    specs: list[EvidenceSpec],
    extraction_rule_id: str,
    created_at: str,
) -> list[CandidateEvidence]:
    if not specs or not any(spec.evidence_role == EvidenceRole.PRIMARY.value for spec in specs):
        raise CandidateEngineError(
            "CANDIDATE_EVIDENCE_INVALID",
            "Every candidate requires at least one primary evidence record.",
        )
    evidence: list[CandidateEvidence] = []
    for sequence_index, spec in enumerate(specs):
        segment = segment_by_id.get(spec.segment_id)
        if not segment or segment.source_id != source.source_id:
            raise CandidateEngineError(
                "CANDIDATE_EVIDENCE_SCOPE_MISMATCH",
                "Candidate evidence does not belong to its source.",
            )
        resolved = evidence_text_from_source(
            source,
            segment,
            source_start_offset=spec.source_start_offset,
            source_end_offset=spec.source_end_offset,
            segment_start_offset=spec.segment_start_offset,
            segment_end_offset=spec.segment_end_offset,
            json_pointer=spec.json_pointer,
        )
        if resolved != spec.text:
            raise CandidateEngineError(
                "CANDIDATE_EVIDENCE_INVALID",
                "Candidate evidence text does not match the stored source provenance.",
            )
        identity = canonical_json(
            {
                "candidate_id": candidate_id,
                "sequence_index": sequence_index,
                **evidence_identity(spec),
            }
        )
        evidence.append(
            CandidateEvidence(
                evidence_id=f"evid_{sha256_text(identity)[:24]}",
                candidate_id=candidate_id,
                source_id=source.source_id,
                segment_id=segment.segment_id,
                evidence_role=spec.evidence_role,
                sequence_index=sequence_index,
                source_start_offset=spec.source_start_offset,
                source_end_offset=spec.source_end_offset,
                segment_start_offset=spec.segment_start_offset,
                segment_end_offset=spec.segment_end_offset,
                start_line=spec.start_line,
                end_line=spec.end_line,
                json_pointer=spec.json_pointer,
                evidence_text_hash_sha256=sha256_text(resolved),
                segment_content_hash_sha256=segment.content_hash_sha256,
                source_content_hash_sha256=source.content_hash_sha256,
                extraction_rule_id=extraction_rule_id,
                created_at=created_at,
            )
        )
    return evidence


def verify_evidence_record(
    source: SourceRecord,
    segment: SourceSegment,
    evidence: CandidateEvidence,
) -> dict[str, bool]:
    ownership = evidence.source_id == source.source_id == segment.source_id
    try:
        text = evidence_text_from_source(
            source,
            segment,
            source_start_offset=evidence.source_start_offset,
            source_end_offset=evidence.source_end_offset,
            segment_start_offset=evidence.segment_start_offset,
            segment_end_offset=evidence.segment_end_offset,
            json_pointer=evidence.json_pointer,
        )
        resolves = True
    except CandidateEngineError:
        text = ""
        resolves = False
    return {
        "ownership": ownership,
        "source_hash_anchor": evidence.source_content_hash_sha256 == source.content_hash_sha256,
        "segment_hash_anchor": evidence.segment_content_hash_sha256 == segment.content_hash_sha256,
        "evidence_resolves": resolves,
        "evidence_text_hash": resolves and sha256_text(text) == evidence.evidence_text_hash_sha256,
    }


__all__ = [
    "evidence_identity",
    "evidence_manifest_hash",
    "evidence_text_from_source",
    "materialize_evidence",
    "resolve_json_pointer",
    "verify_evidence_record",
]
