"""Integrity verification for canonical signal definitions, aliases, and projections."""

from __future__ import annotations

import json
from typing import Any

from .canonical_signal_models import CanonicalSignalIntegrityResult
from .canonical_signal_projection import CanonicalSignalProjector
from .canonical_signal_registry import CanonicalSignalRegistry
from .entity_store import scope_params
from .source_models import AuthenticatedScope


class CanonicalSignalIntegrityVerifier:
    def __init__(self, repository: Any, *, initialize: bool = True) -> None:
        self.repository = repository
        self.registry = CanonicalSignalRegistry(
            repository, initialize=initialize
        )
        self.projector = CanonicalSignalProjector(
            repository, initialize=initialize
        )

    def verify_canonical_signal_integrity(
        self, scope: AuthenticatedScope
    ) -> CanonicalSignalIntegrityResult:
        proposals = self.registry.list_signal_mappings(scope)
        with self.repository.connect() as connection:
            decisions = connection.execute(
                f"SELECT payload_json FROM {self.registry.decisions} WHERE "
                f"client_id={self.registry.p} AND vault_id={self.registry.p} "
                f"AND namespace={self.registry.p}",
                scope_params(scope),
            ).fetchall()
            aliases = connection.execute(
                f"SELECT payload_json FROM {self.registry.aliases} WHERE "
                f"client_id={self.registry.p} AND vault_id={self.registry.p} "
                f"AND namespace={self.registry.p}",
                scope_params(scope),
            ).fetchall()
            projections = connection.execute(
                f"SELECT event_signal_projection_id FROM {self.projector.table} WHERE "
                f"client_id={self.projector.p} AND vault_id={self.projector.p} "
                f"AND namespace={self.projector.p}",
                scope_params(scope),
            ).fetchall()
        decoded_decisions = [self._decode(row["payload_json"]) for row in decisions]
        decoded_aliases = [self._decode(row["payload_json"]) for row in aliases]
        approved = {
            item["canonical_signal_proposal_id"]
            for item in decoded_decisions
            if item["decision_type"] == "approve"
        }
        active_aliases = [
            item for item in decoded_aliases if item["assertion_status"] == "active"
        ]
        no_cycles = True
        try:
            for item in active_aliases:
                self.registry.resolve_canonical_signal(
                    scope,
                    item["original_signal_key"],
                    valid_at="9999-12-31T23:59:59Z",
                    known_at="9999-12-31T23:59:59Z",
                )
        except Exception:
            no_cycles = False
        projection_checks = [
            self.projector.verify_signal_projection_integrity(
                scope, row["event_signal_projection_id"]
            )["verified"]
            for row in projections
        ]
        checks = {
            "approved_aliases_have_decisions": all(
                item["proposal_id"] in approved for item in active_aliases
            ),
            "pending_proposals_have_no_active_alias": all(
                proposal.proposal_status != "pending_review"
                or all(
                    alias["proposal_id"]
                    != proposal.canonical_signal_proposal_id
                    for alias in active_aliases
                )
                for proposal in proposals
            ),
            "no_mapping_cycles": no_cycles,
            "projection_hashes": all(projection_checks),
            "bitemporal_boundaries": all(
                item["valid_from"] and item["system_known_from"]
                for item in decoded_aliases
            ),
            "original_signals_preserved": all(
                item["original_signal_key"] for item in decoded_aliases
            ),
        }
        failures = tuple(name for name, passed in checks.items() if not passed)
        return CanonicalSignalIntegrityResult(
            verified=not failures,
            checks=checks,
            failures=failures,
            details={
                "proposal_count": len(proposals),
                "decision_count": len(decoded_decisions),
                "alias_count": len(decoded_aliases),
                "projection_count": len(projections),
            },
        )

    @staticmethod
    def _decode(value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else json.loads(value)


def verify_canonical_signal_integrity(
    repository: Any, scope: AuthenticatedScope
) -> CanonicalSignalIntegrityResult:
    return CanonicalSignalIntegrityVerifier(
        repository
    ).verify_canonical_signal_integrity(scope)


__all__ = [
    "CanonicalSignalIntegrityVerifier",
    "verify_canonical_signal_integrity",
]
