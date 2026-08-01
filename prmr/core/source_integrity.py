"""Deterministic hashing helpers for source and segment integrity."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

from .source_models import SourceSegment


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="strict")).hexdigest()


def canonical_json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError, RecursionError) as exc:
        from .source_models import SourceLedgerError

        raise SourceLedgerError(
            "SOURCE_PAYLOAD_INVALID",
            "Structured source payload is not valid canonical JSON.",
        ) from exc


def segment_manifest_payload(segments: Iterable[SourceSegment]) -> list[dict[str, Any]]:
    return [
        {
            "segment_id": segment.segment_id,
            "sequence_index": segment.sequence_index,
            "segment_type": segment.segment_type,
            "content_hash_sha256": segment.content_hash_sha256,
            "start_offset": segment.start_offset,
            "end_offset": segment.end_offset,
            "start_line": segment.start_line,
            "end_line": segment.end_line,
            "json_pointer": segment.json_pointer,
            "speaker": segment.speaker,
            "occurred_at": segment.occurred_at,
            "label": segment.label,
            "segmenter_revision": segment.segmenter_revision,
        }
        for segment in sorted(segments, key=lambda item: item.sequence_index)
    ]


def segment_manifest_hash(segments: Iterable[SourceSegment]) -> str:
    return sha256_text(canonical_json(segment_manifest_payload(segments)))


__all__ = [
    "canonical_json",
    "segment_manifest_hash",
    "segment_manifest_payload",
    "sha256_text",
]
