"""Versioned deterministic claim splitting and candidate extraction rules."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

from .candidate_models import (
    CANDIDATE_CLAIM_SPLITTER_REVISION,
    CandidateExtractionPolicy,
    ClaimSpan,
    EpistemicStatus,
    EvidenceRole,
    ExtractionMethod,
    EVENT_TYPE_PATTERN,
)
from .source_integrity import canonical_json, sha256_text
from .source_models import SourceRecord, SourceSegment


APPROVED_V1_EVENT_TYPES = {
    "goal.created",
    "goal.updated",
    "decision.recorded",
    "blocker.detected",
    "blocker.resolved",
    "state.changed",
    "status.updated",
    "action.started",
    "action.completed",
    "milestone.completed",
    "observation.recorded",
    "statement.recorded",
    "information.unknown",
}

LABEL_EVENT_TYPES = {
    "goal": "goal.created",
    "objective": "goal.created",
    "decision": "decision.recorded",
    "blocker": "blocker.detected",
    "issue": "blocker.detected",
    "problem": "blocker.detected",
    "resolution": "blocker.resolved",
    "resolved": "blocker.resolved",
    "change": "state.changed",
    "changed": "state.changed",
    "status": "status.updated",
    "action": "observation.recorded",
    "started": "action.started",
    "completed": "action.completed",
    "milestone": "milestone.completed",
    "observation": "observation.recorded",
    "unknown": "information.unknown",
    "unclear": "information.unknown",
}

TIMELINE_EVENT_TYPES = {
    "goal": "goal.created",
    "decision": "decision.recorded",
    "blocker": "blocker.detected",
    "resolved": "blocker.resolved",
    "change": "state.changed",
    "status": "status.updated",
    "action started": "action.started",
    "action completed": "action.completed",
    "milestone": "milestone.completed",
    "observation": "observation.recorded",
    "unknown": "information.unknown",
}

NEGATION_PATTERNS = (
    r"\bnot\b",
    r"\bnever\b",
    r"\bdidn't\b",
    r"\bwasn't\b",
    r"\bhasn't\b",
    r"\bcouldn't\b",
    r"\bdid\s+not\b",
    r"\bwas\s+not\b",
    r"\bhas\s+not\b",
    r"\bcould\s+not\b",
    r"\bfailed\s+to\b",
    r"\bwithout\s+completing\b",
)
FUTURE_PATTERNS = (
    r"\bwill\b",
    r"\bplans?\s+to\b",
    r"\bintends?\s+to\b",
    r"\bexpects?\s+to\b",
    r"\bscheduled\s+to\b",
    r"\bgoing\s+to\b",
)
HYPOTHETICAL_PATTERNS = (
    r"^\s*if\b",
    r"\bwould\b",
    r"\bcould\s+(?!not\b|no\s+longer\b)",
    r"\bmight\b",
    r"\bmay\b",
    r"\bpossibly\b",
    r"\bperhaps\b",
)
INFERENCE_PATTERNS = (
    r"\bseems?\b",
    r"\bappears?\b",
    r"\blikely\b",
    r"\bprobably\b",
    r"\bmay\s+have\b",
    r"\bmight\s+have\b",
    r"\bpossibly\b",
    r"\bsuggests?\b",
    r"\bcould\s+indicate\b",
)
UNKNOWN_PATTERNS = (
    r"\bunknown\b",
    r"\bunclear\b",
    r"\bnot\s+known\b",
    r"\binsufficient\s+information\b",
    r"\bcould\s+not\s+determine\b",
    r"\bundetermined\b",
    r"\bnot\s+established\b",
    r"\bno\s+evidence\s+available\b",
)
PROMPT_INSTRUCTION_PATTERNS = (
    r"\bignore\s+(?:all\s+)?(?:previous|prior|system)\s+instructions\b",
    r"\bdisregard\s+(?:the\s+)?(?:rules|instructions)\b",
    r"\byou\s+are\s+(?:chatgpt|an?\s+assistant)\b",
)
QUOTED_OR_REPORTED_PATTERN = re.compile(
    r"\b(?:said|stated|reported|claimed|wrote|told\s+\w+)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class EvidenceSpec:
    segment_id: str
    evidence_role: str
    text: str
    source_start_offset: int | None
    source_end_offset: int | None
    segment_start_offset: int | None
    segment_end_offset: int | None
    start_line: int | None
    end_line: int | None
    json_pointer: str | None


@dataclass(frozen=True)
class RuleMatch:
    proposed_event_type: str | None
    proposed_signal: str
    proposed_occurred_at: str | None
    epistemic_status: str
    extraction_confidence: float
    confidence_basis: str
    extraction_method: str
    rule_id: str
    priority: int
    evidence: list[EvidenceSpec]
    normalisation_details: dict[str, Any] = field(default_factory=dict)


def _contains(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def _line_for_relative(segment: SourceSegment, relative_offset: int) -> int | None:
    if segment.start_line is None:
        return None
    return segment.start_line + segment.content.count("\n", 0, relative_offset)


def split_claim_spans(segment: SourceSegment) -> list[ClaimSpan]:
    """Split a segment using stable punctuation and line boundaries only."""

    spans: list[ClaimSpan] = []
    start = 0
    claim_index = 0
    text = segment.content

    structured_pointer = None
    if segment.json_pointer is not None:
        suffix = {
            "conversation_turn": "/content",
            "timeline_entry": "/content",
            "log_record": "/message",
        }.get(segment.segment_type)
        if suffix:
            structured_pointer = segment.json_pointer.rstrip("/") + suffix

    def append(end: int) -> None:
        nonlocal start, claim_index
        raw = text[start:end]
        left = len(raw) - len(raw.lstrip())
        right = len(raw.rstrip())
        claim_start = start + left
        claim_end = start + right
        if claim_end > claim_start:
            source_start = (
                segment.start_offset + claim_start if segment.start_offset is not None else None
            )
            source_end = segment.start_offset + claim_end if segment.start_offset is not None else None
            spans.append(
                ClaimSpan(
                    segment_id=segment.segment_id,
                    segment_sequence_index=segment.sequence_index,
                    claim_sequence_index=claim_index,
                    text=text[claim_start:claim_end],
                    segment_start_offset=claim_start,
                    segment_end_offset=claim_end,
                    source_start_offset=source_start,
                    source_end_offset=source_end,
                    start_line=_line_for_relative(segment, claim_start),
                    end_line=_line_for_relative(segment, max(claim_start, claim_end - 1)),
                    json_pointer=structured_pointer,
                )
            )
            claim_index += 1
        start = end

    for index, character in enumerate(text):
        if character in ".?!;\n":
            end = index + 1
            while end < len(text) and text[end] in "\"'":
                end += 1
            append(end)
    if start < len(text):
        append(len(text))
    return spans


def claim_evidence(span: ClaimSpan) -> EvidenceSpec:
    source_start = None if span.json_pointer is not None else span.source_start_offset
    source_end = None if span.json_pointer is not None else span.source_end_offset
    return EvidenceSpec(
        segment_id=span.segment_id,
        evidence_role=EvidenceRole.PRIMARY.value,
        text=span.text,
        source_start_offset=source_start,
        source_end_offset=source_end,
        segment_start_offset=span.segment_start_offset,
        segment_end_offset=span.segment_end_offset,
        start_line=span.start_line,
        end_line=span.end_line,
        json_pointer=span.json_pointer,
    )


def text_rule_matches(span: ClaimSpan, policy: CandidateExtractionPolicy) -> list[RuleMatch]:
    claim = span.text
    lowered = claim.lower()
    if len(claim) < policy.minimum_signal_length or len(claim) > policy.maximum_signal_length:
        return []
    if "[redacted:" in lowered or _contains(claim, PROMPT_INSTRUCTION_PATTERNS):
        return []

    evidence = [claim_evidence(span)]
    matches: list[RuleMatch] = []
    label = re.match(
        r"^\s*(Goal|Objective|Decision|Blocker|Issue|Problem|Resolution|Resolved|Change|Changed|Status|Action|Started|Completed|Milestone|Observation|Unknown|Unclear)\s*:\s*(.+?)\s*$",
        claim,
        re.IGNORECASE | re.DOTALL,
    )
    if label and policy.labelled_rules_enabled:
        label_name = label.group(1).lower()
        signal = label.group(2).strip()
        event_type = LABEL_EVENT_TYPES[label_name]
        unknown = event_type == "information.unknown"
        if (not unknown and policy.allow_explicit) or (unknown and policy.record_unknown_markers):
            matches.append(
                RuleMatch(
                    proposed_event_type=event_type,
                    proposed_signal=signal,
                    proposed_occurred_at=None,
                    epistemic_status=(EpistemicStatus.UNKNOWN.value if unknown else EpistemicStatus.EXPLICIT.value),
                    extraction_confidence=0.99,
                    confidence_basis="Exact leading label matched a versioned deterministic rule.",
                    extraction_method=(ExtractionMethod.UNKNOWN_MARKER.value if unknown else ExtractionMethod.EXPLICIT_LABEL.value),
                    rule_id=f"rule.label.{label_name}.v1",
                    priority=2,
                    evidence=evidence,
                    normalisation_details={"label_removed": f"{label.group(1)}:", "source_wording_preserved": True},
                )
            )

    # When a labelled claim also matches a lexical rule for the same event type,
    # use the same lossless label-stripped signal. This lets fingerprint-based
    # deduplication retain one candidate while recording every matched rule.
    labelled_signal = label.group(2).strip() if label else None
    labelled_event_type = LABEL_EVENT_TYPES[label.group(1).lower()] if label else None

    # Hearsay is explicit only about the act of making the statement.
    if QUOTED_OR_REPORTED_PATTERN.search(claim):
        if policy.allow_explicit:
            quote_match = re.search(r"[\"“](.+?)[\"”]", claim)
            details: dict[str, Any] = {"reported_statement": True, "truth_of_quoted_content_confirmed": False}
            if quote_match:
                details.update(
                    {
                        "quoted_content_hash_sha256": sha256_text(quote_match.group(1)),
                        "quotation_start_offset": quote_match.start(1),
                        "quotation_end_offset": quote_match.end(1),
                    }
                )
            matches.append(
                RuleMatch(
                    proposed_event_type="statement.recorded",
                    proposed_signal=claim,
                    proposed_occurred_at=None,
                    epistemic_status=EpistemicStatus.EXPLICIT.value,
                    extraction_confidence=0.94,
                    confidence_basis="A deterministic reporting-speech pattern identified the act of stating, not the truth of the claim.",
                    extraction_method=ExtractionMethod.DETERMINISTIC_PATTERN.value,
                    rule_id="rule.pattern.reported_statement.v1",
                    priority=3,
                    evidence=evidence,
                    normalisation_details=details,
                )
            )
        return matches

    if _contains(claim, UNKNOWN_PATTERNS):
        if policy.record_unknown_markers:
            matches.append(
                RuleMatch(
                    proposed_event_type="information.unknown",
                    proposed_signal=claim,
                    proposed_occurred_at=None,
                    epistemic_status=EpistemicStatus.UNKNOWN.value,
                    extraction_confidence=0.98,
                    confidence_basis="The source explicitly contains a versioned unknown-information marker.",
                    extraction_method=ExtractionMethod.UNKNOWN_MARKER.value,
                    rule_id="rule.unknown.marker.v1",
                    priority=5,
                    evidence=evidence,
                    normalisation_details={"underlying_information_known": False},
                )
            )
        return matches

    negated = _contains(claim, NEGATION_PATTERNS)
    future = _contains(claim, FUTURE_PATTERNS)
    hypothetical = _contains(claim, HYPOTHETICAL_PATTERNS)
    inferred = _contains(claim, INFERENCE_PATTERNS)

    if inferred and policy.allow_inferred and policy.uncertainty_rules_enabled:
        matches.append(
            RuleMatch(
                proposed_event_type="observation.recorded",
                proposed_signal=claim,
                proposed_occurred_at=None,
                epistemic_status=EpistemicStatus.INFERRED.value,
                extraction_confidence=0.70,
                confidence_basis="The source itself uses an uncertainty marker; confidence concerns extraction only, not truth.",
                extraction_method=ExtractionMethod.UNCERTAINTY_PATTERN.value,
                rule_id="rule.inference.uncertainty_marker.v1",
                priority=4,
                evidence=evidence,
                normalisation_details={"confirmed_fact": False, "uncertainty_preserved": True},
            )
        )
        return matches

    if negated:
        if policy.allow_explicit and re.search(r"\b(?:complete|completed|finish|finished|launch|launched|resolve|resolved|deploy|deployed)\b", lowered):
            matches.append(
                RuleMatch(
                    proposed_event_type="status.updated",
                    proposed_signal=claim,
                    proposed_occurred_at=None,
                    epistemic_status=EpistemicStatus.EXPLICIT.value,
                    extraction_confidence=0.93,
                    confidence_basis="A negated status was directly stated; no completion or resolution is emitted.",
                    extraction_method=ExtractionMethod.DETERMINISTIC_PATTERN.value,
                    rule_id="rule.modality.negated_status.v1",
                    priority=3,
                    evidence=evidence,
                    normalisation_details={"negation_detected": True, "completion_confirmed": False},
                )
            )
        return matches

    if future or hypothetical:
        if policy.allow_explicit and re.search(r"\bplans?\s+to\b|\bintends?\s+to\b", lowered):
            matches.append(
                RuleMatch(
                    proposed_event_type="goal.created",
                    proposed_signal=claim,
                    proposed_occurred_at=None,
                    epistemic_status=EpistemicStatus.EXPLICIT.value,
                    extraction_confidence=0.90,
                    confidence_basis="A future plan was explicitly stated; it is represented as a goal, never a completion.",
                    extraction_method=ExtractionMethod.DETERMINISTIC_PATTERN.value,
                    rule_id="rule.modality.plan_goal.v1",
                    priority=3,
                    evidence=evidence,
                    normalisation_details={"future_or_plan_detected": True, "completion_confirmed": False},
                )
            )
        return matches

    if not policy.lexical_rules_enabled or not policy.allow_explicit:
        return matches

    patterns: tuple[tuple[str, str, tuple[str, ...], dict[str, Any]], ...] = (
        (
            "goal.created",
            "rule.pattern.goal.v1",
            (r"\bthe\s+goal\s+is\s+to\b", r"\bset\s+a\s+goal\s+to\b", r"\bteam\s+aimed\s+to\b", r"\bteam\s+planned\s+to\b", r"\bobjective\s+was\s+to\b", r"\bwe\s+intend\s+to\b"),
            {},
        ),
        (
            "decision.recorded",
            "rule.pattern.decision.v1",
            (r"\bdecided\s+to\b", r"\bchose\s+to\b", r"\bselected\b", r"\bagreed\s+to\b", r"\bthe\s+decision\s+was\b"),
            {},
        ),
        (
            "blocker.detected",
            "rule.pattern.blocker.v1",
            (r"\bwas\s+blocked\s+(?:by|because)\b", r"\bis\s+blocked\s+(?:by|because)\b", r"\bcould\s+not\s+continue\s+because\b", r"\bthe\s+blocker\s+was\b", r"\bthe\s+issue\s+prevented\b"),
            {},
        ),
        (
            "blocker.resolved",
            "rule.pattern.resolution.v1",
            (r"\bresolved\s+the\s+blocker\b", r"\bfixed\s+the\s+issue\b", r"\bthe\s+problem\s+was\s+resolved\b", r"\bthe\s+failure\s+was\s+corrected\b"),
            {},
        ),
        (
            "state.changed",
            "rule.pattern.state_change.v1",
            (r"\bchanged\s+.+?\s+from\s+.+?\s+to\s+.+", r"\bmoved\s+from\s+.+?\s+to\s+.+", r"\bstatus\s+changed\s+to\b", r"\bbecame\b", r"\bwas\s+replaced\s+by\b"),
            {},
        ),
        (
            "action.started",
            "rule.pattern.action_started.v1",
            (r"\bstarted\b", r"\bbegan\b", r"\binitiated\b"),
            {},
        ),
        (
            "milestone.completed",
            "rule.pattern.milestone.v1",
            (r"\bmilestone\s+completed\b", r"\breached\s+the\s+milestone\b", r"\breleased\s+the\s+first\s+version\b", r"\blaunched\s+the\s+controlled\s+alpha\b"),
            {},
        ),
        (
            "action.completed",
            "rule.pattern.action_completed.v1",
            (r"\bcompleted\b", r"\bfinished\b", r"\bsuccessfully\s+implemented\b", r"\bsuccessfully\s+deployed\b"),
            {},
        ),
    )
    for event_type, rule_id, rule_patterns, details in patterns:
        if _contains(claim, rule_patterns):
            normalisation = dict(details)
            proposed_signal = claim
            if labelled_signal is not None and labelled_event_type == event_type:
                proposed_signal = labelled_signal
                normalisation.update(
                    {
                        "label_removed": f"{label.group(1)}:",
                        "source_wording_preserved": True,
                    }
                )
            if event_type == "state.changed":
                transition = re.search(r"\bfrom\s+(.+?)\s+to\s+(.+?)(?:[.!?;]|$)", claim, re.IGNORECASE)
                if transition:
                    normalisation.update(
                        {"previous_state": transition.group(1), "current_state": transition.group(2)}
                    )
            matches.append(
                RuleMatch(
                    proposed_event_type=event_type,
                    proposed_signal=proposed_signal,
                    proposed_occurred_at=None,
                    epistemic_status=EpistemicStatus.EXPLICIT.value,
                    extraction_confidence=0.91,
                    confidence_basis="A conservative versioned lexical pattern matched an unnegated, non-hypothetical claim.",
                    extraction_method=ExtractionMethod.DETERMINISTIC_PATTERN.value,
                    rule_id=rule_id,
                    priority=3,
                    evidence=evidence,
                    normalisation_details=normalisation,
                )
            )
    return matches


def _escape_pointer(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _segment_for_pointer(segments: list[SourceSegment], pointer: str) -> SourceSegment | None:
    exact = next((item for item in segments if item.json_pointer == pointer), None)
    if exact:
        return exact
    candidates = [
        item
        for item in segments
        if item.json_pointer is not None
        and (pointer == item.json_pointer or pointer.startswith(item.json_pointer.rstrip("/") + "/"))
    ]
    return max(candidates, key=lambda item: len(item.json_pointer or ""), default=None)


def structured_evidence(
    segments: list[SourceSegment],
    pointer: str,
    value: Any,
    role: str = EvidenceRole.PRIMARY.value,
) -> EvidenceSpec | None:
    segment = _segment_for_pointer(segments, pointer)
    if not segment:
        return None
    text = value if isinstance(value, str) else canonical_json(value)
    segment_start = 0 if segment.content == text else None
    segment_end = len(text) if segment.content == text else None
    return EvidenceSpec(
        segment_id=segment.segment_id,
        evidence_role=role,
        text=text,
        source_start_offset=None,
        source_end_offset=None,
        segment_start_offset=segment_start,
        segment_end_offset=segment_end,
        start_line=segment.start_line,
        end_line=segment.end_line,
        json_pointer=pointer,
    )


def json_rule_matches(
    source: SourceRecord,
    segments: list[SourceSegment],
    policy: CandidateExtractionPolicy,
) -> list[RuleMatch]:
    if not policy.structured_rules_enabled:
        return []
    records: list[tuple[str, dict[str, Any]]] = []
    if isinstance(source.sanitised_payload, dict):
        records = [("", source.sanitised_payload)]
    elif isinstance(source.sanitised_payload, list):
        records = [
            (f"/{index}", value)
            for index, value in enumerate(source.sanitised_payload)
            if isinstance(value, dict)
        ]
    matches: list[RuleMatch] = []
    field_mappings = {
        "goal": "goal.created",
        "decision": "decision.recorded",
        "blocker": "blocker.detected",
        "milestone": "milestone.completed",
        "status": "status.updated",
        "action": "observation.recorded",
    }
    for base, record in records:
        def pointer(field: str) -> str:
            return f"{base}/{_escape_pointer(field)}" if base else f"/{_escape_pointer(field)}"

        explicit_type = record.get("event_type") or record.get("type")
        signal_key = next((key for key in ("signal", "content", "summary") if isinstance(record.get(key), str)), None)
        if (
            policy.allow_explicit
            and isinstance(explicit_type, str)
            and EVENT_TYPE_PATTERN.fullmatch(explicit_type)
            and explicit_type in APPROVED_V1_EVENT_TYPES
            and signal_key
        ):
            primary = structured_evidence(segments, pointer(signal_key), record[signal_key])
            supporting = structured_evidence(segments, pointer("event_type" if "event_type" in record else "type"), explicit_type, EvidenceRole.SUPPORTING.value)
            if primary:
                matches.append(
                    RuleMatch(
                        proposed_event_type=explicit_type,
                        proposed_signal=record[signal_key],
                        proposed_occurred_at=record.get("occurred_at") or record.get("timestamp"),
                        epistemic_status=EpistemicStatus.EXPLICIT.value,
                        extraction_confidence=0.99,
                        confidence_basis="Valid event type and exact signal fields were explicitly present in structured source data.",
                        extraction_method=ExtractionMethod.STRUCTURED_FIELD.value,
                        rule_id="rule.structured.explicit_event.v1",
                        priority=1,
                        evidence=[primary] + ([supporting] if supporting else []),
                        normalisation_details={"signal_field": signal_key, "scope_fields_authoritative": False},
                    )
                )
        for field_name, event_type in field_mappings.items():
            value = record.get(field_name)
            if policy.allow_explicit and isinstance(value, str) and len(value.strip()) >= policy.minimum_signal_length:
                evidence = structured_evidence(segments, pointer(field_name), value)
                if evidence:
                    matches.append(
                        RuleMatch(
                            proposed_event_type=event_type,
                            proposed_signal=value,
                            proposed_occurred_at=record.get("occurred_at") or record.get("timestamp"),
                            epistemic_status=EpistemicStatus.EXPLICIT.value,
                            extraction_confidence=0.98,
                            confidence_basis=f"Structured field {field_name} is explicitly present.",
                            extraction_method=ExtractionMethod.STRUCTURED_FIELD.value,
                            rule_id=f"rule.structured.{field_name}.v1",
                            priority=1,
                            evidence=[evidence],
                            normalisation_details={"structured_field": field_name},
                        )
                    )
        previous = record.get("previous_state")
        current = record.get("current_state")
        if policy.allow_derived and previous is not None and current is not None:
            previous_text = previous if isinstance(previous, str) else canonical_json(previous)
            current_text = current if isinstance(current, str) else canonical_json(current)
            first = structured_evidence(segments, pointer("previous_state"), previous, EvidenceRole.PRIMARY.value)
            second = structured_evidence(segments, pointer("current_state"), current, EvidenceRole.DERIVATION_INPUT.value)
            if first and second:
                matches.append(
                    RuleMatch(
                        proposed_event_type="state.changed",
                        proposed_signal=f"State changed from {previous_text} to {current_text}.",
                        proposed_occurred_at=record.get("occurred_at") or record.get("timestamp"),
                        epistemic_status=EpistemicStatus.DERIVED.value,
                        extraction_confidence=0.99,
                        confidence_basis="Both derivation inputs were explicit structured fields and the operator is deterministic.",
                        extraction_method=ExtractionMethod.DETERMINISTIC_DERIVATION.value,
                        rule_id="rule.derivation.state_transition_v1",
                        priority=1,
                        evidence=[first, second],
                        normalisation_details={
                            "derivation_operator": "state_transition_v1",
                            "derivation_inputs": [previous, current],
                            "source_wording_preserved": False,
                            "deterministic_derivation": True,
                        },
                    )
                )
    return matches


def timeline_rule_matches(
    source: SourceRecord,
    segments: list[SourceSegment],
    policy: CandidateExtractionPolicy,
) -> list[RuleMatch]:
    if not policy.structured_rules_enabled or not isinstance(source.sanitised_payload, list):
        return []
    matches: list[RuleMatch] = []
    for index, entry in enumerate(source.sanitised_payload):
        if not isinstance(entry, dict):
            continue
        label = str(entry.get("label") or entry.get("type") or "").strip().lower()
        content = entry.get("content")
        event_type = TIMELINE_EVENT_TYPES.get(label)
        if not event_type or not isinstance(content, str):
            continue
        unknown = event_type == "information.unknown"
        if (unknown and not policy.record_unknown_markers) or (not unknown and not policy.allow_explicit):
            continue
        pointer = f"/{index}/content"
        evidence = structured_evidence(segments, pointer, content)
        if evidence:
            matches.append(
                RuleMatch(
                    proposed_event_type=event_type,
                    proposed_signal=content,
                    proposed_occurred_at=entry.get("timestamp") or entry.get("occurred_at"),
                    epistemic_status=EpistemicStatus.UNKNOWN.value if unknown else EpistemicStatus.EXPLICIT.value,
                    extraction_confidence=0.99,
                    confidence_basis="A documented timeline label mapped deterministically to an approved event type.",
                    extraction_method=ExtractionMethod.STRUCTURED_FIELD.value,
                    rule_id=f"rule.timeline.{label.replace(' ', '_')}.v1",
                    priority=1,
                    evidence=[evidence],
                    normalisation_details={"timeline_label": entry.get("label") or entry.get("type")},
                )
            )
    return matches


def extract_rule_matches(
    source: SourceRecord,
    segments: list[SourceSegment],
    policy: CandidateExtractionPolicy,
) -> tuple[list[RuleMatch], int]:
    matches: list[RuleMatch] = []
    claim_span_count = 0
    if source.source_type == "json":
        matches.extend(json_rule_matches(source, segments, policy))
        return matches, claim_span_count
    if source.source_type == "timeline":
        matches.extend(timeline_rule_matches(source, segments, policy))

    for segment in sorted(segments, key=lambda item: item.sequence_index):
        if segment.segment_type in {"heading", "fenced_code_block", "json_field", "json_record", "json_root"}:
            continue
        spans = split_claim_spans(segment)
        claim_span_count += len(spans)
        for span in spans:
            span_matches = text_rule_matches(span, policy)
            occurred_at = segment.occurred_at
            if occurred_at:
                span_matches = [
                    RuleMatch(
                        proposed_event_type=item.proposed_event_type,
                        proposed_signal=item.proposed_signal,
                        proposed_occurred_at=occurred_at,
                        epistemic_status=item.epistemic_status,
                        extraction_confidence=item.extraction_confidence,
                        confidence_basis=item.confidence_basis,
                        extraction_method=item.extraction_method,
                        rule_id=item.rule_id,
                        priority=item.priority,
                        evidence=item.evidence,
                        normalisation_details={**item.normalisation_details, "speaker": segment.speaker} if segment.speaker else item.normalisation_details,
                    )
                    for item in span_matches
                ]
            matches.extend(span_matches)
    return matches, claim_span_count


__all__ = [
    "APPROVED_V1_EVENT_TYPES",
    "EvidenceSpec",
    "LABEL_EVENT_TYPES",
    "RuleMatch",
    "extract_rule_matches",
    "split_claim_spans",
]
