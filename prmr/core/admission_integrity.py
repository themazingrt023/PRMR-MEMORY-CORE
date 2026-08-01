"""Integrity facade for admitted-memory verification and origin tracing."""

from __future__ import annotations

from typing import Any

from .admission_models import AdmissionIntegrityResult
from .admission_service import MemoryAdmissionService
from .source_models import AuthenticatedScope


class MemoryAdmissionIntegrityVerifier:
    """Read-only verifier over durable admission, event, and source records."""

    def __init__(self, service: MemoryAdmissionService) -> None:
        self.service = service

    def verify(
        self,
        authenticated_scope: AuthenticatedScope,
        admission_id: str,
    ) -> AdmissionIntegrityResult:
        return self.service.verify_admission_integrity(
            authenticated_scope, admission_id
        )

    def trace_origin(
        self,
        authenticated_scope: AuthenticatedScope,
        admitted_event_id: str,
        *,
        include_evidence_preview: bool = False,
    ) -> dict[str, Any]:
        return self.service.trace_admitted_memory_origin(
            authenticated_scope,
            admitted_event_id,
            include_evidence_preview=include_evidence_preview,
        )


__all__ = ["MemoryAdmissionIntegrityVerifier"]
