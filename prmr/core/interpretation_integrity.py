"""Integrity verification for stored bounded interpretation artifacts."""

from __future__ import annotations

from typing import Any

from .interpretation_chunking import build_chunk_plan
from .interpretation_engine import InterpretationEngine
from .interpretation_models import (
    INTERPRETATION_INTEGRITY_REVISION,
    InterpretationIntegrityResult,
)
from .interpretation_policy import InterpretationPolicy, contains_secret
from .source_integrity import canonical_json, sha256_text
from .source_models import AuthenticatedScope


class InterpretationIntegrityVerifier:
    def __init__(self, repository: Any, *, initialize: bool = True) -> None:
        self.engine = InterpretationEngine(repository, initialize=initialize)

    def verify_interpretation_integrity(
        self, scope: AuthenticatedScope, request_id: str
    ) -> InterpretationIntegrityResult:
        request = self.engine.get_interpretation_request(scope, request_id)
        source = self.engine.sources.get_source(scope, request.source_id)
        source_integrity = self.engine.sources.verify_source_integrity(
            scope, request.source_id
        )
        segments = self.engine._segments(scope, request.source_id)
        plan = build_chunk_plan(
            source.source_id,
            segments,
            InterpretationPolicy(policy_id=request.interpretation_policy_id),
        )
        proposals = self.engine.list_interpretation_proposals(scope, request_id)
        response = None
        try:
            result = self.engine._stored_result(scope, request)
            response = result.response if result else None
        except Exception:
            response = None
        checks = {
            "source_integrity": source_integrity.verified,
            "source_content_hash": (
                source.content_hash_sha256 == request.source_content_hash_sha256
            ),
            "source_segment_manifest": (
                source.segment_manifest_hash_sha256
                == request.source_segment_manifest_hash_sha256
            ),
            "chunk_plan_identity": plan.chunk_plan_id == request.chunk_plan_id,
            "selected_segments": (
                tuple(plan.selected_segment_ids) == request.selected_segment_ids
            ),
            "response_hash": bool(
                response
                and response.validated_output_hash_sha256
                == sha256_text(
                    canonical_json(
                        [
                            item.to_dict()
                            for item in response.validated_structured_output
                        ]
                    )
                )
            ),
            "proposal_links_unique": len(
                {
                    (
                        item["interpretation_response_record_id"],
                        item["proposal_fingerprint_sha256"],
                    )
                    for item in proposals
                }
            )
            == len(proposals),
            "all_proposals_pending": all(
                item.get("candidate_status") == "pending_review"
                and item.get("authoritative_memory_created") is False
                for item in proposals
            ),
            "no_secret_exposure": not contains_secret(
                {
                    "request": request.to_dict(),
                    "response": response.to_dict() if response else None,
                    "proposals": proposals,
                }
            ),
        }
        failures = tuple(name for name, passed in checks.items() if not passed)
        return InterpretationIntegrityResult(
            interpretation_request_id=request_id,
            verified=not failures,
            checks=checks,
            failures=failures,
            details={
                "proposal_count": len(proposals),
                "integrity_revision": INTERPRETATION_INTEGRITY_REVISION,
            },
        )


def verify_interpretation_integrity(
    repository: Any, scope: AuthenticatedScope, request_id: str
) -> InterpretationIntegrityResult:
    return InterpretationIntegrityVerifier(
        repository
    ).verify_interpretation_integrity(scope, request_id)


__all__ = [
    "InterpretationIntegrityVerifier",
    "verify_interpretation_integrity",
]
