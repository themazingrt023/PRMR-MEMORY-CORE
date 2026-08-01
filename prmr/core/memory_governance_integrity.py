"""Integrity checks for governance records and content-free tombstones."""

from __future__ import annotations

import json
import re
from typing import Any

from .memory_governance_store import MemoryGovernanceStore
from .source_integrity import canonical_json, sha256_text
from .source_models import AuthenticatedScope


SECRET_PATTERN = re.compile(
    r"(?:prmr_(?:live|alpha)_|authorization\s*:\s*bearer|github_pat_|ghp_|sk-)",
    re.I,
)
FORBIDDEN_TOMBSTONE_KEYS = {
    "opaque_target_reference",
    "source_text",
    "content",
    "signal",
    "evidence_quote",
    "entity_label",
    "raw_identifier",
}


class MemoryGovernanceIntegrityVerifier:
    def __init__(self, repository: Any, *, initialize: bool = True) -> None:
        self.store = MemoryGovernanceStore(repository, initialize=initialize)

    def verify(self, scope: AuthenticatedScope) -> dict[str, Any]:
        failures: list[str] = []
        tombstones = self.store.manifest_rows(
            "tombstone", scope.memory_boundary()
        )
        requests = self.store.manifest_rows("request", scope.memory_boundary())
        executions = self.store.manifest_rows(
            "execution", scope.memory_boundary()
        )
        verifications = self.store.manifest_rows(
            "verification", scope.memory_boundary()
        )
        verification_ids = {
            item["governance_verification_id"] for item in verifications
        }
        for tombstone in tombstones:
            keys = self._keys(tombstone)
            if keys.intersection(FORBIDDEN_TOMBSTONE_KEYS):
                failures.append("tombstone_contains_forbidden_content_field")
            if SECRET_PATTERN.search(canonical_json(tombstone)):
                failures.append("tombstone_contains_secret_pattern")
        for execution in executions:
            if execution["execution_status"] in {
                "completed",
                "completed_with_invalidations",
            } and execution.get("verification_id") not in verification_ids:
                failures.append("completed_execution_missing_verification")
        request_ids = {item["governance_request_id"] for item in requests}
        for execution in executions:
            if execution["governance_request_id"] not in request_ids:
                failures.append("execution_missing_request")
        manifest = sha256_text(
            canonical_json(
                {
                    "scope": scope.memory_boundary(),
                    "requests": sorted(request_ids),
                    "executions": sorted(
                        item["governance_execution_id"] for item in executions
                    ),
                    "verifications": sorted(verification_ids),
                    "tombstones": sorted(
                        item["erasure_tombstone_id"] for item in tombstones
                    ),
                    "failures": sorted(failures),
                }
            )
        )
        return {
            "verified": not failures,
            "failures": sorted(set(failures)),
            "counts": {
                "requests": len(requests),
                "executions": len(executions),
                "verifications": len(verifications),
                "tombstones": len(tombstones),
            },
            "integrity_manifest_hash": manifest,
        }

    @classmethod
    def _keys(cls, value: Any) -> set[str]:
        found: set[str] = set()
        if isinstance(value, dict):
            for key, item in value.items():
                found.add(str(key))
                found.update(cls._keys(item))
        elif isinstance(value, list):
            for item in value:
                found.update(cls._keys(item))
        return found


__all__ = ["MemoryGovernanceIntegrityVerifier"]
