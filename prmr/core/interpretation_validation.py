"""Schema, scope, evidence, and epistemic validation for provider output."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from .candidate_models import EVENT_TYPE_PATTERN
from .entity_models import ENTITY_TYPE_PATTERN
from .interpretation_models import (
    EvidenceReference,
    InterpretationOutputItem,
    InterpretationValidationFailure,
    ProposalType,
)
from .interpretation_policy import InterpretationPolicy, contains_secret
from .relationship_models import RELATIONSHIP_TYPE_PATTERN
from .source_integrity import canonical_json, sha256_text
from .source_models import SourceRecord, SourceSegment


EPISTEMIC = {"explicit", "derived", "inferred", "unknown"}
UNKNOWN_TYPES = {
    "insufficient_evidence",
    "ambiguous_entity",
    "ambiguous_relationship",
    "unclear_temporal_order",
    "unsupported_cause",
    "unsupported_signal_mapping",
    "conflicting_source_content",
    "unresolvable_reference",
    "provider_uncertain",
}
FORBIDDEN_KEYS = {
    "admit",
    "auto_admit",
    "approve",
    "merge",
    "execute",
    "tool",
    "tool_call",
    "url_to_fetch",
    "client_id",
    "vault_id",
    "namespace",
    "authorization",
    "api_key",
    "token",
    "chain_of_thought",
    "reasoning_trace",
}
NEGATION = re.compile(r"\b(?:not|never|didn't|did not|wasn't|was not|no longer)\b", re.I)
UNCERTAINTY = re.compile(r"\b(?:may|might|could|possibly|perhaps|unclear|unknown)\b", re.I)
FUTURE = re.compile(r"\b(?:will|plan(?:s|ned)? to|intend(?:s|ed)? to|would|hypothetical)\b", re.I)


@dataclass(frozen=True)
class ValidatedOutput:
    accepted: tuple[InterpretationOutputItem, ...]
    failures: tuple[InterpretationValidationFailure, ...]
    schema_error_count: int
    evidence_error_count: int
    scope_error_count: int
    secret_redaction_count: int


def _failure(
    attempt_id: str, index: int, code: str, detail: str
) -> InterpretationValidationFailure:
    digest = sha256_text(
        canonical_json(
            {"attempt": attempt_id, "index": index, "code": code, "detail": detail}
        )
    )
    return InterpretationValidationFailure(
        validation_failure_id=f"ivfail_{digest[:24]}",
        interpretation_attempt_id=attempt_id,
        proposal_index=index,
        failure_code=code,
        safe_detail=detail,
        created_at="",
    )


def _reference(raw: dict[str, Any]) -> EvidenceReference:
    return EvidenceReference(
        source_id=str(raw["source_id"]),
        segment_id=str(raw["segment_id"]),
        segment_start_offset=int(raw["segment_start_offset"]),
        segment_end_offset=int(raw["segment_end_offset"]),
        source_start_offset=(
            int(raw["source_start_offset"])
            if raw.get("source_start_offset") is not None
            else None
        ),
        source_end_offset=(
            int(raw["source_end_offset"])
            if raw.get("source_end_offset") is not None
            else None
        ),
        start_line=(
            int(raw["start_line"]) if raw.get("start_line") is not None else None
        ),
        end_line=int(raw["end_line"]) if raw.get("end_line") is not None else None,
        json_pointer=(
            str(raw["json_pointer"]) if raw.get("json_pointer") is not None else None
        ),
        exact_quote_hash=str(raw["exact_quote_hash"]),
        segment_content_hash=str(raw["segment_content_hash"]),
    )


def _validate_evidence(
    source: SourceRecord,
    segment_by_id: dict[str, SourceSegment],
    references: tuple[EvidenceReference, ...],
) -> tuple[bool, list[str], list[str]]:
    errors: list[str] = []
    evidence_texts: list[str] = []
    if not references:
        return False, ["missing_evidence"], []
    for reference in references:
        if reference.source_id != source.source_id:
            errors.append("wrong_source")
            continue
        segment = segment_by_id.get(reference.segment_id)
        if segment is None:
            errors.append("wrong_segment")
            continue
        if reference.segment_content_hash != segment.content_hash_sha256:
            errors.append("segment_hash_mismatch")
            continue
        start, end = reference.segment_start_offset, reference.segment_end_offset
        if start < 0 or end <= start or end > len(segment.content):
            errors.append("invalid_offset")
            continue
        text = segment.content[start:end]
        if sha256_text(text) != reference.exact_quote_hash:
            errors.append("quote_hash_mismatch")
            continue
        if (
            reference.source_start_offset is not None
            and segment.start_offset is not None
            and reference.source_start_offset != segment.start_offset + start
        ):
            errors.append("source_start_mismatch")
            continue
        if (
            reference.source_end_offset is not None
            and segment.start_offset is not None
            and reference.source_end_offset != segment.start_offset + end
        ):
            errors.append("source_end_mismatch")
            continue
        if reference.json_pointer != segment.json_pointer:
            errors.append("json_pointer_mismatch")
            continue
        evidence_texts.append(text)
    return not errors and len(evidence_texts) == len(references), errors, evidence_texts


def _schema_item(raw: dict[str, Any]) -> InterpretationOutputItem:
    if not isinstance(raw, dict):
        raise ValueError("item_not_object")
    if FORBIDDEN_KEYS.intersection(raw):
        raise ValueError("forbidden_control_field")
    proposal_type = str(raw["proposal_type"])
    if proposal_type not in {item.value for item in ProposalType}:
        raise ValueError("proposal_type_invalid")
    epistemic = str(raw["epistemic_status"])
    if epistemic not in EPISTEMIC:
        raise ValueError("epistemic_status_invalid")
    confidence = float(raw["extraction_confidence"])
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence_invalid")
    refs_raw = raw.get("evidence_references")
    if not isinstance(refs_raw, list):
        raise ValueError("evidence_references_invalid")
    refs = tuple(_reference(item) for item in refs_raw)
    kwargs: dict[str, Any] = {
        "proposal_type": proposal_type,
        "epistemic_status": epistemic,
        "extraction_confidence": confidence,
        "confidence_basis": str(raw.get("confidence_basis", "provider_proposal")),
        "evidence_references": refs,
        "uncertainty_flags": tuple(
            str(item) for item in raw.get("uncertainty_flags", [])
        ),
        "concise_justification": str(raw.get("concise_justification", ""))[:500],
    }
    for key in (
        "proposed_event_type",
        "proposed_signal",
        "proposed_entity_type",
        "proposed_entity_label",
        "proposed_subject_reference",
        "proposed_relationship_type",
        "proposed_object_reference",
        "proposed_canonical_signal",
        "original_signal",
        "unknown_reason",
        "derivation_operator",
        "attribution",
    ):
        kwargs[key] = str(raw[key]) if raw.get(key) is not None else None
    for key in ("quoted_claim", "negated", "future_or_hypothetical"):
        kwargs[key] = bool(raw.get(key, False))
    item = InterpretationOutputItem(**kwargs)
    if item.proposal_type == ProposalType.CANDIDATE_MEMORY.value:
        if not item.proposed_event_type or not EVENT_TYPE_PATTERN.fullmatch(
            item.proposed_event_type
        ):
            raise ValueError("event_type_invalid")
        if not item.proposed_signal:
            raise ValueError("signal_missing")
    elif item.proposal_type == ProposalType.ENTITY_CANDIDATE.value:
        if not item.proposed_entity_type or not ENTITY_TYPE_PATTERN.fullmatch(
            item.proposed_entity_type
        ):
            raise ValueError("entity_type_invalid")
    elif item.proposal_type == ProposalType.RELATIONSHIP_CANDIDATE.value:
        if (
            not item.proposed_relationship_type
            or not RELATIONSHIP_TYPE_PATTERN.fullmatch(
                item.proposed_relationship_type
            )
            or not item.proposed_subject_reference
            or not item.proposed_object_reference
        ):
            raise ValueError("relationship_fields_invalid")
    elif item.proposal_type == ProposalType.CANONICAL_SIGNAL_PROPOSAL.value:
        if not item.original_signal or not item.proposed_canonical_signal:
            raise ValueError("canonical_mapping_fields_invalid")
        if not EVENT_TYPE_PATTERN.fullmatch(
            item.original_signal
        ) or not EVENT_TYPE_PATTERN.fullmatch(item.proposed_canonical_signal):
            raise ValueError("canonical_signal_invalid")
    elif item.proposal_type == ProposalType.UNKNOWN_RESULT.value:
        if item.unknown_reason not in UNKNOWN_TYPES:
            raise ValueError("unknown_reason_invalid")
        if item.epistemic_status != "unknown":
            raise ValueError("unknown_epistemic_invalid")
    return item


def validate_provider_output(
    *,
    attempt_id: str,
    source: SourceRecord,
    segments: list[SourceSegment],
    raw_items: tuple[dict[str, Any], ...],
    policy: InterpretationPolicy,
    created_at: str,
) -> ValidatedOutput:
    accepted: list[InterpretationOutputItem] = []
    failures: list[InterpretationValidationFailure] = []
    schema_errors = evidence_errors = scope_errors = secret_errors = 0
    segment_by_id = {item.segment_id: item for item in segments}
    exact_seen: set[str] = set()
    for index, raw in enumerate(raw_items):
        try:
            if contains_secret(raw):
                secret_errors += 1
                raise ValueError("secret_looking_output")
            item = _schema_item(raw)
        except (KeyError, TypeError, ValueError) as exc:
            schema_errors += 1
            failure = _failure(
                attempt_id,
                index,
                "INTERPRETATION_OUTPUT_SCHEMA_INVALID",
                str(exc),
            )
            failures.append(
                InterpretationValidationFailure(
                    **{**failure.to_dict(), "created_at": created_at}
                )
            )
            continue
        valid, evidence_failures, evidence_texts = _validate_evidence(
            source, segment_by_id, item.evidence_references
        )
        if not valid:
            if any(code in {"wrong_source", "wrong_segment"} for code in evidence_failures):
                scope_errors += 1
                code = "INTERPRETATION_SCOPE_DENIED"
            else:
                evidence_errors += 1
                code = "INTERPRETATION_EVIDENCE_INVALID"
            failure = _failure(attempt_id, index, code, ",".join(evidence_failures))
            failures.append(
                InterpretationValidationFailure(
                    **{**failure.to_dict(), "created_at": created_at}
                )
            )
            continue
        joined = " ".join(evidence_texts)
        classification_error: str | None = None
        if item.epistemic_status == "explicit":
            signal = item.proposed_signal or item.proposed_entity_label or ""
            if UNCERTAINTY.search(joined):
                classification_error = "uncertain_source_cannot_be_explicit"
            elif FUTURE.search(joined) and not item.future_or_hypothetical:
                classification_error = "future_language_not_preserved"
            elif NEGATION.search(joined) and not item.negated:
                classification_error = "negation_not_preserved"
            elif item.quoted_claim and not item.attribution:
                classification_error = "quoted_claim_missing_attribution"
            elif signal and signal.lower() not in joined.lower():
                classification_error = "explicit_semantic_expansion"
        elif item.epistemic_status == "derived":
            if item.derivation_operator not in policy.allowed_derived_operators:
                classification_error = "derived_operator_not_allowlisted"
        if (
            re.search(r"\bcause is unknown\b", joined, re.I)
            and item.proposal_type == ProposalType.RELATIONSHIP_CANDIDATE.value
            and str(item.proposed_relationship_type).startswith("caus")
        ):
            classification_error = "unknown_cause_cannot_be_promoted"
        if classification_error:
            evidence_errors += 1
            failure = _failure(
                attempt_id,
                index,
                "INTERPRETATION_PROPOSAL_REJECTED",
                classification_error,
            )
            failures.append(
                InterpretationValidationFailure(
                    **{**failure.to_dict(), "created_at": created_at}
                )
            )
            continue
        fingerprint = sha256_text(canonical_json(item.to_dict()))
        if fingerprint in exact_seen:
            continue
        exact_seen.add(fingerprint)
        accepted.append(item)
    accepted.sort(key=lambda item: sha256_text(canonical_json(item.to_dict())))
    return ValidatedOutput(
        accepted=tuple(accepted),
        failures=tuple(failures),
        schema_error_count=schema_errors,
        evidence_error_count=evidence_errors,
        scope_error_count=scope_errors,
        secret_redaction_count=secret_errors,
    )


__all__ = ["ValidatedOutput", "validate_provider_output"]
