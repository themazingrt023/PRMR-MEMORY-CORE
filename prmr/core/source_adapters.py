"""Deterministic source validation, sanitisation, canonicalisation, and segmentation."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import re
from typing import Any

from .source_integrity import canonical_json, sha256_text
from .source_models import (
    SANITISATION_REVISION,
    SEGMENTER_REVISION,
    SanitisationReport,
    SourceLedgerError,
    SourceSegment,
    SourceType,
)


MAX_SOURCE_PAYLOAD_BYTES = 256 * 1024
MAX_SEGMENT_COUNT = 10_000
MAX_METADATA_DEPTH = 10
MAX_METADATA_KEYS = 500
MAX_STRUCTURED_DEPTH = 50

REDACTION_MARKER_PREFIX = "[REDACTED:"
SENSITIVE_FIELD_TERMS = {
    "authorization",
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "token",
    "secret",
    "password",
    "credential",
    "private_key",
    "database_url",
    "service_role",
}
AUTH_SCOPE_KEYS = {"client_id", "vault_id", "namespace"}

SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "private_key",
        re.compile(
            r"-----BEGIN(?: [A-Z0-9]+)? PRIVATE KEY-----.*?-----END(?: [A-Z0-9]+)? PRIVATE KEY-----",
            re.IGNORECASE | re.DOTALL,
        ),
        "[REDACTED:private_key]",
    ),
    (
        "authorization_bearer",
        re.compile(r"Authorization\s*:\s*Bearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
        "Authorization: Bearer [REDACTED:bearer_token]",
    ),
    (
        "bearer_token",
        re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{16,}\b", re.IGNORECASE),
        "Bearer [REDACTED:bearer_token]",
    ),
    (
        "prmr_api_key",
        re.compile(r"\bprmr_(?:alpha|live)_[A-Za-z0-9_-]{8,}\b", re.IGNORECASE),
        "[REDACTED:prmr_api_key]",
    ),
    (
        "github_token",
        re.compile(r"\b(?:ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
        "[REDACTED:github_token]",
    ),
    (
        "provider_api_key",
        re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
        "[REDACTED:provider_api_key]",
    ),
    (
        "database_url",
        re.compile(
            r"\b(?:postgres(?:ql)?|mysql|mariadb|mongodb(?:\+srv)?|redis)://[^\s\"'<>]+",
            re.IGNORECASE,
        ),
        "[REDACTED:database_url]",
    ),
    (
        "password_assignment",
        re.compile(r"\b(password|passwd|pwd)\s*[:=]\s*([^\s,;]+)", re.IGNORECASE),
        r"\1=[REDACTED:password]",
    ),
)


@dataclass
class RedactionTracker:
    categories: Counter[str] = field(default_factory=Counter)
    null_character_count: int = 0

    @property
    def redaction_count(self) -> int:
        return sum(self.categories.values())


@dataclass(frozen=True)
class SegmentDraft:
    segment_type: str
    content: str
    start_offset: int | None = None
    end_offset: int | None = None
    start_line: int | None = None
    end_line: int | None = None
    json_pointer: str | None = None
    speaker: str | None = None
    occurred_at: str | None = None
    label: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PreparedSource:
    source_type: str
    sanitised_payload: Any
    stored_representation: str
    canonical_representation: str
    sanitised_metadata: dict[str, Any]
    segment_drafts: list[SegmentDraft]
    sanitisation_report: SanitisationReport


def _key_is_sensitive(key: str) -> bool:
    lowered = key.lower().strip()
    return any(term in lowered for term in SENSITIVE_FIELD_TERMS)


def _sanitize_text(value: str, tracker: RedactionTracker) -> str:
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeEncodeError as exc:
        raise SourceLedgerError(
            "SOURCE_PAYLOAD_INVALID",
            "Source text must be valid UTF-8.",
        ) from exc
    if "\x00" in value:
        count = value.count("\x00")
        tracker.null_character_count += count
        tracker.categories["null_character"] += count
        value = value.replace("\x00", "")
    for category, pattern, replacement in SECRET_PATTERNS:
        value, count = pattern.subn(replacement, value)
        if count:
            tracker.categories[category] += count
    return value


def _validate_and_sanitize_structure(
    value: Any,
    tracker: RedactionTracker,
    *,
    depth: int = 0,
    seen: set[int] | None = None,
    metadata_mode: bool = False,
    key_counter: list[int] | None = None,
) -> Any:
    if depth > (MAX_METADATA_DEPTH if metadata_mode else MAX_STRUCTURED_DEPTH):
        raise SourceLedgerError(
            "SOURCE_METADATA_INVALID" if metadata_mode else "SOURCE_PAYLOAD_INVALID",
            "Structured value exceeds the configured nesting depth.",
        )
    if seen is None:
        seen = set()
    if key_counter is None:
        key_counter = [0]

    if isinstance(value, dict):
        identity = id(value)
        if identity in seen:
            raise SourceLedgerError("SOURCE_PAYLOAD_INVALID", "Recursive source structures are not supported.")
        seen.add(identity)
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise SourceLedgerError(
                    "SOURCE_METADATA_INVALID" if metadata_mode else "SOURCE_PAYLOAD_INVALID",
                    "Structured object keys must be strings.",
                )
            key_counter[0] += 1
            if metadata_mode and key_counter[0] > MAX_METADATA_KEYS:
                raise SourceLedgerError("SOURCE_METADATA_INVALID", "Metadata exceeds the configured key limit.")
            clean_key = _sanitize_text(key, tracker)
            if clean_key.lower().strip() in AUTH_SCOPE_KEYS:
                result[clean_key] = "[REDACTED:authenticated_scope_override]"
                tracker.categories["authenticated_scope_override"] += 1
            elif _key_is_sensitive(clean_key):
                result[clean_key] = "[REDACTED:sensitive_field]"
                tracker.categories["sensitive_field"] += 1
            else:
                result[clean_key] = _validate_and_sanitize_structure(
                    item,
                    tracker,
                    depth=depth + 1,
                    seen=seen,
                    metadata_mode=metadata_mode,
                    key_counter=key_counter,
                )
        seen.remove(identity)
        return result

    if isinstance(value, (list, tuple)):
        identity = id(value)
        if identity in seen:
            raise SourceLedgerError("SOURCE_PAYLOAD_INVALID", "Recursive source structures are not supported.")
        seen.add(identity)
        result = [
            _validate_and_sanitize_structure(
                item,
                tracker,
                depth=depth + 1,
                seen=seen,
                metadata_mode=metadata_mode,
                key_counter=key_counter,
            )
            for item in value
        ]
        seen.remove(identity)
        return result
    if isinstance(value, str):
        return _sanitize_text(value, tracker)
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise SourceLedgerError("SOURCE_PAYLOAD_INVALID", "Non-finite numbers are not supported.")
        return value
    raise SourceLedgerError("SOURCE_PAYLOAD_INVALID", "Unsupported value in structured source payload.")


def sanitize_metadata(metadata: Any, tracker: RedactionTracker) -> dict[str, Any]:
    if metadata is None:
        return {}
    if not isinstance(metadata, dict):
        raise SourceLedgerError("SOURCE_METADATA_INVALID", "metadata must be an object.")
    return _validate_and_sanitize_structure(metadata, tracker, metadata_mode=True)


def sanitize_reference(value: Any, *, field_name: str) -> tuple[str | None, dict[str, int]]:
    if value is None:
        return None, {}
    if not isinstance(value, str):
        raise SourceLedgerError("SOURCE_SCOPE_INVALID", f"{field_name} must be a string.")
    tracker = RedactionTracker()
    cleaned = " ".join(_sanitize_text(value, tracker).split()).strip()
    if tracker.redaction_count:
        return None, dict(tracker.categories)
    if not cleaned:
        return None, {}
    return cleaned[:160], {}


def _validate_size(stored_representation: str) -> None:
    try:
        size = len(stored_representation.encode("utf-8", errors="strict"))
    except UnicodeEncodeError as exc:
        raise SourceLedgerError("SOURCE_PAYLOAD_INVALID", "Source payload must be valid UTF-8.") from exc
    if size > MAX_SOURCE_PAYLOAD_BYTES:
        raise SourceLedgerError(
            "SOURCE_PAYLOAD_TOO_LARGE",
            f"Source payload exceeds the {MAX_SOURCE_PAYLOAD_BYTES}-byte limit.",
        )


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _block_spans(text: str) -> list[tuple[int, int, int, int]]:
    spans: list[tuple[int, int, int, int]] = []
    offset = 0
    block_start: int | None = None
    block_end = 0
    block_start_line = 0
    block_end_line = 0
    for line_number, line in enumerate(text.splitlines(keepends=True), start=1):
        body = line.rstrip("\r\n")
        if body.strip():
            if block_start is None:
                block_start = offset
                block_start_line = line_number
            block_end = offset + len(body)
            block_end_line = line_number
        elif block_start is not None:
            spans.append((block_start, block_end, block_start_line, block_end_line))
            block_start = None
        offset += len(line)
    if text and not text.splitlines(keepends=True):
        return []
    if block_start is not None:
        spans.append((block_start, block_end, block_start_line, block_end_line))
    return spans


def _plain_text_segments(text: str) -> list[SegmentDraft]:
    return [
        SegmentDraft(
            segment_type="paragraph",
            content=text[start:end],
            start_offset=start,
            end_offset=end,
            start_line=start_line,
            end_line=end_line,
        )
        for start, end, start_line, end_line in _block_spans(text)
    ]


def _markdown_segments(text: str) -> list[SegmentDraft]:
    lines = text.splitlines(keepends=True)
    segments: list[SegmentDraft] = []
    offsets: list[int] = []
    current = 0
    for line in lines:
        offsets.append(current)
        current += len(line)

    def append_segment(kind: str, start_index: int, end_index: int) -> None:
        start = offsets[start_index]
        final_body = lines[end_index].rstrip("\r\n")
        end = offsets[end_index] + len(final_body)
        if end > start:
            segments.append(
                SegmentDraft(
                    segment_type=kind,
                    content=text[start:end],
                    start_offset=start,
                    end_offset=end,
                    start_line=start_index + 1,
                    end_line=end_index + 1,
                    metadata={"markdown_block_type": kind},
                )
            )

    index = 0
    while index < len(lines):
        body = lines[index].rstrip("\r\n")
        if not body.strip():
            index += 1
            continue
        fence = re.match(r"^\s*(```|~~~)", body)
        if fence:
            marker = fence.group(1)
            end_index = index
            while end_index + 1 < len(lines):
                end_index += 1
                if re.match(rf"^\s*{re.escape(marker)}\s*$", lines[end_index].rstrip("\r\n")):
                    break
            append_segment("fenced_code_block", index, end_index)
            index = end_index + 1
            continue
        classifiers = (
            ("heading", r"^\s{0,3}#{1,6}\s+"),
            ("list_item", r"^\s*(?:[-*+] |\d+[.)]\s+)"),
            ("block_quote", r"^\s*>"),
        )
        matched = next((kind for kind, pattern in classifiers if re.match(pattern, body)), None)
        if matched:
            append_segment(matched, index, index)
            index += 1
            continue
        end_index = index
        while end_index + 1 < len(lines):
            candidate = lines[end_index + 1].rstrip("\r\n")
            if not candidate.strip():
                break
            if re.match(r"^\s*(```|~~~|#{1,6}\s+|>|[-*+] |\d+[.)]\s+)", candidate):
                break
            end_index += 1
        append_segment("paragraph", index, end_index)
        index = end_index + 1
    return segments


def _escape_json_pointer(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _structured_content(value: Any) -> str:
    return value if isinstance(value, str) else canonical_json(value)


def _conversation_segments(payload: list[Any]) -> list[SegmentDraft]:
    segments: list[SegmentDraft] = []
    for index, turn in enumerate(payload):
        if not isinstance(turn, dict) or "content" not in turn or not isinstance(turn["content"], str):
            raise SourceLedgerError(
                "SOURCE_PAYLOAD_INVALID",
                "Each conversation turn must be an object with string content.",
            )
        speaker = turn.get("speaker")
        timestamp = turn.get("timestamp") or turn.get("occurred_at")
        if speaker is not None and not isinstance(speaker, str):
            raise SourceLedgerError("SOURCE_PAYLOAD_INVALID", "Conversation speaker must be a string.")
        if timestamp is not None and not isinstance(timestamp, str):
            raise SourceLedgerError("SOURCE_PAYLOAD_INVALID", "Conversation timestamp must be a string.")
        segments.append(
            SegmentDraft(
                segment_type="conversation_turn",
                content=turn["content"],
                json_pointer=f"/{index}",
                speaker=speaker,
                occurred_at=timestamp,
                metadata={
                    key: value
                    for key, value in turn.items()
                    if key not in {"content", "speaker", "timestamp", "occurred_at"}
                },
            )
        )
    return segments


def _json_segments(payload: Any) -> list[SegmentDraft]:
    if isinstance(payload, list):
        if not payload:
            return [SegmentDraft(segment_type="json_root", content="[]", json_pointer="")]
        return [
            SegmentDraft(
                segment_type="json_record",
                content=_structured_content(item),
                json_pointer=f"/{index}",
            )
            for index, item in enumerate(payload)
        ]
    if isinstance(payload, dict):
        if not payload:
            return [SegmentDraft(segment_type="json_root", content="{}", json_pointer="")]
        return [
            SegmentDraft(
                segment_type="json_field",
                content=_structured_content(payload[key]),
                json_pointer=f"/{_escape_json_pointer(key)}",
                label=key,
            )
            for key in sorted(payload)
        ]
    raise SourceLedgerError("SOURCE_PAYLOAD_INVALID", "json source payload must be an object or array.")


def _timeline_segments(payload: list[Any]) -> list[SegmentDraft]:
    segments: list[SegmentDraft] = []
    for index, entry in enumerate(payload):
        if not isinstance(entry, dict) or "content" not in entry or not isinstance(entry["content"], str):
            raise SourceLedgerError(
                "SOURCE_PAYLOAD_INVALID",
                "Each timeline entry must be an object with string content.",
            )
        timestamp = entry.get("timestamp") or entry.get("occurred_at")
        label = entry.get("label")
        if timestamp is not None and not isinstance(timestamp, str):
            raise SourceLedgerError("SOURCE_PAYLOAD_INVALID", "Timeline timestamp must be a string.")
        if label is not None and not isinstance(label, str):
            raise SourceLedgerError("SOURCE_PAYLOAD_INVALID", "Timeline label must be a string.")
        segments.append(
            SegmentDraft(
                segment_type="timeline_entry",
                content=entry["content"],
                json_pointer=f"/{index}",
                occurred_at=timestamp,
                label=label,
                metadata={
                    key: value
                    for key, value in entry.items()
                    if key not in {"content", "timestamp", "occurred_at", "label"}
                },
            )
        )
    return segments


def _log_segments(payload: Any) -> list[SegmentDraft]:
    if isinstance(payload, str):
        segments: list[SegmentDraft] = []
        offset = 0
        for line_number, line in enumerate(payload.splitlines(keepends=True), start=1):
            body = line.rstrip("\r\n")
            if body.strip():
                segments.append(
                    SegmentDraft(
                        segment_type="log_line",
                        content=body,
                        start_offset=offset,
                        end_offset=offset + len(body),
                        start_line=line_number,
                        end_line=line_number,
                    )
                )
            offset += len(line)
        return segments
    if not isinstance(payload, list):
        raise SourceLedgerError("SOURCE_PAYLOAD_INVALID", "log payload must be text or a list of records.")
    segments = []
    for index, record in enumerate(payload):
        if not isinstance(record, dict):
            raise SourceLedgerError("SOURCE_PAYLOAD_INVALID", "Each structured log record must be an object.")
        message = record.get("message")
        if not isinstance(message, str):
            raise SourceLedgerError("SOURCE_PAYLOAD_INVALID", "Each structured log record requires string message.")
        timestamp = record.get("timestamp") or record.get("occurred_at")
        if timestamp is not None and not isinstance(timestamp, str):
            raise SourceLedgerError("SOURCE_PAYLOAD_INVALID", "Log timestamp must be a string.")
        metadata = {
            key: value
            for key, value in record.items()
            if key not in {"message", "timestamp", "occurred_at", "level", "component"}
        }
        if "level" in record:
            metadata["log_level"] = record["level"]
        if "component" in record:
            metadata["component"] = record["component"]
        segments.append(
            SegmentDraft(
                segment_type="log_record",
                content=message,
                json_pointer=f"/{index}",
                occurred_at=timestamp,
                label=str(record.get("level")) if record.get("level") is not None else None,
                metadata=metadata,
            )
        )
    return segments


def prepare_source(source_type: SourceType | str, payload: Any, metadata: Any) -> PreparedSource:
    try:
        normalized_type = SourceType(str(getattr(source_type, "value", source_type)))
    except ValueError as exc:
        raise SourceLedgerError("SOURCE_TYPE_UNSUPPORTED", "Unsupported source type.") from exc

    tracker = RedactionTracker()
    sanitised_metadata = sanitize_metadata(metadata, tracker)
    if normalized_type in {SourceType.PLAIN_TEXT, SourceType.MARKDOWN}:
        if not isinstance(payload, str):
            raise SourceLedgerError("SOURCE_PAYLOAD_INVALID", f"{normalized_type.value} payload must be text.")
        sanitised_payload = _sanitize_text(payload, tracker)
        if not sanitised_payload.strip():
            raise SourceLedgerError("SOURCE_PAYLOAD_INVALID", "Source text must not be empty.")
        stored = sanitised_payload
        canonical = sanitised_payload
        drafts = (
            _plain_text_segments(sanitised_payload)
            if normalized_type == SourceType.PLAIN_TEXT
            else _markdown_segments(sanitised_payload)
        )
    elif normalized_type == SourceType.LOG and isinstance(payload, str):
        sanitised_payload = _sanitize_text(payload, tracker)
        if not sanitised_payload.strip():
            raise SourceLedgerError("SOURCE_PAYLOAD_INVALID", "Log source must not be empty.")
        stored = sanitised_payload
        canonical = sanitised_payload
        drafts = _log_segments(sanitised_payload)
    else:
        if isinstance(payload, (bytes, bytearray, memoryview)):
            raise SourceLedgerError("SOURCE_PAYLOAD_INVALID", "Binary source payloads are not supported.")
        sanitised_payload = _validate_and_sanitize_structure(payload, tracker)
        if normalized_type in {SourceType.CONVERSATION, SourceType.TIMELINE} and not isinstance(
            sanitised_payload, list
        ):
            raise SourceLedgerError(
                "SOURCE_PAYLOAD_INVALID",
                f"{normalized_type.value} payload must be an ordered list.",
            )
        if normalized_type == SourceType.LOG and not isinstance(sanitised_payload, list):
            raise SourceLedgerError("SOURCE_PAYLOAD_INVALID", "Structured log payload must be a list.")
        stored = canonical_json(sanitised_payload)
        canonical = stored
        if normalized_type == SourceType.CONVERSATION:
            drafts = _conversation_segments(sanitised_payload)
        elif normalized_type == SourceType.JSON:
            drafts = _json_segments(sanitised_payload)
        elif normalized_type == SourceType.TIMELINE:
            drafts = _timeline_segments(sanitised_payload)
        elif normalized_type == SourceType.LOG:
            drafts = _log_segments(sanitised_payload)
        else:
            raise SourceLedgerError("SOURCE_TYPE_UNSUPPORTED", "Unsupported source type.")

    _validate_size(stored)
    if len(drafts) > MAX_SEGMENT_COUNT:
        raise SourceLedgerError(
            "SOURCE_SEGMENT_LIMIT_EXCEEDED",
            f"Source exceeds the {MAX_SEGMENT_COUNT}-segment limit.",
        )
    if not drafts:
        raise SourceLedgerError("SOURCE_PAYLOAD_INVALID", "Source did not contain any structural segments.")
    affected_segments = sum(
        REDACTION_MARKER_PREFIX in draft.content
        or REDACTION_MARKER_PREFIX in canonical_json(draft.metadata)
        for draft in drafts
    )
    report = SanitisationReport(
        redaction_count=tracker.redaction_count,
        redaction_categories=dict(sorted(tracker.categories.items())),
        affected_segment_count=affected_segments,
        null_character_count=tracker.null_character_count,
        sanitisation_revision=SANITISATION_REVISION,
    )
    return PreparedSource(
        source_type=normalized_type.value,
        sanitised_payload=sanitised_payload,
        stored_representation=stored,
        canonical_representation=canonical,
        sanitised_metadata=sanitised_metadata,
        segment_drafts=drafts,
        sanitisation_report=report,
    )


def materialize_segments(source_id: str, drafts: list[SegmentDraft], created_at: str) -> list[SourceSegment]:
    segments: list[SourceSegment] = []
    for sequence_index, draft in enumerate(drafts):
        content_hash = sha256_text(draft.content)
        identity = canonical_json(
            {
                "source_id": source_id,
                "segmenter_revision": SEGMENTER_REVISION,
                "sequence_index": sequence_index,
                "segment_type": draft.segment_type,
                "content_hash_sha256": content_hash,
                "start_offset": draft.start_offset,
                "end_offset": draft.end_offset,
                "start_line": draft.start_line,
                "end_line": draft.end_line,
                "json_pointer": draft.json_pointer,
                "speaker": draft.speaker,
                "occurred_at": draft.occurred_at,
                "label": draft.label,
            }
        )
        segment_id = f"seg_{sha256_text(identity)[:24]}"
        segments.append(
            SourceSegment(
                segment_id=segment_id,
                source_id=source_id,
                sequence_index=sequence_index,
                parent_segment_id=None,
                segment_type=draft.segment_type,
                content=draft.content,
                content_hash_sha256=content_hash,
                start_offset=draft.start_offset,
                end_offset=draft.end_offset,
                start_line=draft.start_line,
                end_line=draft.end_line,
                json_pointer=draft.json_pointer,
                speaker=draft.speaker,
                occurred_at=draft.occurred_at,
                label=draft.label,
                metadata=draft.metadata,
                segmenter_revision=SEGMENTER_REVISION,
                created_at=created_at,
            )
        )
    return segments


__all__ = [
    "MAX_METADATA_DEPTH",
    "MAX_METADATA_KEYS",
    "MAX_SEGMENT_COUNT",
    "MAX_SOURCE_PAYLOAD_BYTES",
    "PreparedSource",
    "SegmentDraft",
    "materialize_segments",
    "prepare_source",
    "sanitize_reference",
]
