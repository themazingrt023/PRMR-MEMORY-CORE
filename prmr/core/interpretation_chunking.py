"""Deterministic source-segment chunk planning."""

from __future__ import annotations

from typing import Iterable

from .interpretation_models import (
    INTERPRETATION_CHUNKING_REVISION,
    InterpretationChunk,
    InterpretationChunkPlan,
)
from .interpretation_policy import InterpretationPolicy
from .source_integrity import canonical_json, sha256_text
from .source_models import SourceSegment


def build_chunk_plan(
    source_id: str,
    segments: Iterable[SourceSegment],
    policy: InterpretationPolicy,
) -> InterpretationChunkPlan:
    policy.validate()
    ordered = sorted(segments, key=lambda item: (item.sequence_index, item.segment_id))
    chunks: list[InterpretationChunk] = []
    start = 0
    previous_ids: set[str] = set()
    while start < len(ordered):
        selected: list[SourceSegment] = []
        chars = 0
        index = start
        while index < len(ordered) and len(selected) < policy.maximum_segments_per_chunk:
            segment = ordered[index]
            addition = len(segment.content)
            if selected and chars + addition > policy.maximum_characters_per_chunk:
                break
            selected.append(segment)
            chars += addition
            index += 1
        if not selected:
            selected = [ordered[start]]
            index = start + 1
            chars = len(ordered[start].content)
        material = {
            "source_id": source_id,
            "segment_ids": [item.segment_id for item in selected],
            "segment_hashes": [item.content_hash_sha256 for item in selected],
            "first_index": selected[0].sequence_index,
            "last_index": selected[-1].sequence_index,
            "revision": INTERPRETATION_CHUNKING_REVISION,
        }
        digest = sha256_text(canonical_json(material))
        chunks.append(
            InterpretationChunk(
                chunk_id=f"ichunk_{digest[:24]}",
                ordered_segment_ids=tuple(item.segment_id for item in selected),
                overlap_segment_ids=tuple(
                    item.segment_id
                    for item in selected
                    if item.segment_id in previous_ids
                ),
                first_segment_index=selected[0].sequence_index,
                last_segment_index=selected[-1].sequence_index,
                character_count=chars,
                source_start_offset=selected[0].start_offset,
                source_end_offset=selected[-1].end_offset,
                chunk_hash_sha256=digest,
            )
        )
        if index >= len(ordered):
            break
        previous_ids = {item.segment_id for item in selected}
        start = max(start + 1, index - policy.overlap_segments)
    manifest = sha256_text(
        canonical_json(
            [
                {
                    "segment_id": item.segment_id,
                    "sequence_index": item.sequence_index,
                    "content_hash": item.content_hash_sha256,
                }
                for item in ordered
            ]
        )
    )
    plan_hash = sha256_text(
        canonical_json(
            {
                "source_id": source_id,
                "chunks": [item.to_dict() for item in chunks],
                "manifest": manifest,
                "revision": INTERPRETATION_CHUNKING_REVISION,
            }
        )
    )
    return InterpretationChunkPlan(
        chunk_plan_id=f"ichunkplan_{plan_hash[:24]}",
        source_id=source_id,
        chunks=tuple(chunks),
        selected_segment_ids=tuple(item.segment_id for item in ordered),
        segment_manifest_hash_sha256=manifest,
        chunk_plan_hash_sha256=plan_hash,
    )


__all__ = ["build_chunk_plan"]
