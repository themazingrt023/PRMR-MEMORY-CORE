"""Deterministic time-based memory dynamics over Sprint 4 effective events."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
from datetime import datetime, timezone
import json
import logging
import time
from typing import Any, Callable

from prmr.product.controlled_alpha_api_v071 import ALGORITHM_REVISION

from .admission_models import AdmissionDecisionActor
from .memory_importance import MemoryImportanceService
from .memory_ledger_models import (
    BITEMPORAL_POLICY_REVISION,
    MEMORY_STATE_RESOLVER_REVISION,
    MemoryTemporalBoundary,
)
from .memory_reconstruction import MemoryReconstructionService
from .memory_recurrence import (
    event_metadata,
    group_occurrences,
    recurrence_summary,
    signal_identity,
)
from .memory_temporal_models import (
    CONTINUITY_TEMPORAL_ADAPTER_REVISION,
    MEMORY_DYNAMICS_COMPARISON_REVISION,
    MEMORY_DYNAMICS_SNAPSHOT_REVISION,
    MEMORY_HORIZON_REVISION,
    MEMORY_IMPORTANCE_REVISION,
    MEMORY_INFLUENCE_REVISION,
    MEMORY_RECURRENCE_REVISION,
    MEMORY_REEMERGENCE_REVISION,
    MEMORY_TEMPORAL_POLICY_REVISION,
    MEMORY_TEMPORAL_SCHEMA_REVISION,
    SIGNAL_IDENTITY_REVISION,
    MemoryDynamicsComparison,
    MemoryDynamicsError,
    MemoryDynamicsIntegrityResult,
    MemoryDynamicsMode,
    MemoryDynamicsResult,
    MemoryDynamicsSnapshot,
    MemoryImportanceAnnotation,
    MemorySignalDynamics,
    TemporalMemoryPolicy,
)
from .memory_temporal_policy import (
    base_time_influence,
    clamp01,
    classify_horizon,
    classify_phase,
    cross_horizon_boost,
    policy_from_configuration,
    quantize8,
    recurrence_boost,
    validate_policy,
)
from .source_integrity import canonical_json, sha256_text
from .source_models import AuthenticatedScope


LOGGER = logging.getLogger("prmr.core.memory_dynamics")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _time(value: str) -> tuple[str, float]:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise MemoryDynamicsError(
            "MEMORY_EVENT_TIME_INVALID", "Event time is invalid."
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    parsed = parsed.astimezone(timezone.utc)
    return parsed.isoformat().replace("+00:00", "Z"), parsed.timestamp()


class MemoryDynamicsEngine:
    def __init__(self, repository: Any, *, initialize: bool = True) -> None:
        self.repository = repository
        self.importance = MemoryImportanceService(
            repository, initialize=initialize
        )
        self.ledger = self.importance.ledger
        self.reconstruction = MemoryReconstructionService(
            repository, initialize=initialize
        )
        self.state_resolver = self.reconstruction.resolver
        self.backend = self.importance.backend
        self.snapshot_table = self.importance.snapshot_table
        self.signal_table = self.importance.signal_table
        self.placeholder = self.importance.placeholder

    def compute_memory_dynamics(
        self,
        authenticated_scope: AuthenticatedScope,
        subject_scope: dict[str, str | None] | AuthenticatedScope | None = None,
        temporal_boundary: MemoryTemporalBoundary | None = None,
        policy_id: str = MemoryDynamicsMode.TEMPORAL_MEMORY_V1.value,
        persist: bool = True,
        event_ids: set[str] | frozenset[str] | None = None,
        signal_identity_resolver: (
            Callable[[dict[str, Any]], tuple[str, str]] | None
        ) = None,
    ) -> MemoryDynamicsResult:
        if policy_id != MemoryDynamicsMode.TEMPORAL_MEMORY_V1.value:
            raise MemoryDynamicsError(
                "MEMORY_TEMPORAL_POLICY_INVALID",
                "Dynamics snapshots require temporal_memory_v1; legacy_recent5_v1 is a packet replay mode.",
            )
        policy = validate_policy(TemporalMemoryPolicy(policy_id=policy_id))
        scope_fingerprint = sha256_text(
            canonical_json(authenticated_scope.memory_boundary())
        )[:16]
        LOGGER.info(
            "%s",
            json.dumps(
                {
                    "event": "memory_dynamics_started",
                    "policy_id": policy.policy_id,
                    "scope_fingerprint": scope_fingerprint,
                },
                sort_keys=True,
            ),
        )
        try:
            result = self._compute(
                authenticated_scope,
                subject_scope,
                temporal_boundary,
                policy,
                event_ids=event_ids,
                signal_identity_resolver=signal_identity_resolver,
            )
        except Exception as exc:
            LOGGER.error(
                "%s",
                json.dumps(
                    {
                        "event": "memory_dynamics_failed",
                        "policy_id": policy.policy_id,
                        "safe_error_code": getattr(
                            exc, "code", "MEMORY_DYNAMICS_FAILED"
                        ),
                        "scope_fingerprint": scope_fingerprint,
                    },
                    sort_keys=True,
                ),
            )
            raise
        existing = self._snapshot_by_identity(
            authenticated_scope, result.snapshot.dynamics_snapshot_identity
        )
        if existing:
            signals = self._signals_for_snapshot(
                authenticated_scope, existing.dynamics_snapshot_id
            )
            LOGGER.info(
                "%s",
                json.dumps(
                    {
                        "event": "memory_dynamics_replayed",
                        "snapshot_id": existing.dynamics_snapshot_id,
                        "signal_count": len(signals),
                        "policy_id": policy.policy_id,
                    },
                    sort_keys=True,
                ),
            )
            return MemoryDynamicsResult(
                existing,
                signals,
                created=False,
                replayed=True,
                resolver_duration_ms=result.resolver_duration_ms,
                recurrence_duration_ms=result.recurrence_duration_ms,
                reemergence_duration_ms=result.reemergence_duration_ms,
                persistence_duration_ms=0.0,
            )
        if not persist:
            self._log_completed(result, scope_fingerprint)
            return result
        started = time.perf_counter()
        try:
            self._persist(result.snapshot, result.signals)
        except Exception as exc:
            existing = self._snapshot_by_identity(
                authenticated_scope, result.snapshot.dynamics_snapshot_identity
            )
            if existing:
                return MemoryDynamicsResult(
                    existing,
                    self._signals_for_snapshot(
                        authenticated_scope, existing.dynamics_snapshot_id
                    ),
                    created=False,
                    replayed=True,
                    resolver_duration_ms=result.resolver_duration_ms,
                    recurrence_duration_ms=result.recurrence_duration_ms,
                    reemergence_duration_ms=result.reemergence_duration_ms,
                    persistence_duration_ms=round(
                        (time.perf_counter() - started) * 1000, 3
                    ),
                )
            raise MemoryDynamicsError(
                "MEMORY_DYNAMICS_FAILED",
                "Temporal dynamics snapshot transaction failed.",
                retryable=True,
            ) from exc
        persisted = replace(
            result,
            persistence_duration_ms=round(
                (time.perf_counter() - started) * 1000, 3
            ),
        )
        self._log_completed(persisted, scope_fingerprint)
        return persisted

    def get_dynamics_snapshot(
        self, authenticated_scope: AuthenticatedScope, dynamics_snapshot_id: str
    ) -> MemoryDynamicsSnapshot:
        p = self.placeholder
        with self.repository.connect() as connection:
            row = connection.execute(
                f"SELECT payload_json FROM {self.snapshot_table} "
                f"WHERE dynamics_snapshot_id={p} AND client_id={p} "
                f"AND vault_id={p} AND namespace={p}",
                (dynamics_snapshot_id, *authenticated_scope.memory_boundary()),
            ).fetchone()
        if not row:
            raise MemoryDynamicsError(
                "MEMORY_DYNAMICS_SNAPSHOT_NOT_FOUND",
                "Dynamics snapshot was not found in the authenticated scope.",
            )
        return self._snapshot_from_payload(row["payload_json"])

    def list_signal_dynamics(
        self,
        authenticated_scope: AuthenticatedScope,
        dynamics_snapshot_id: str,
        memory_phase: str | None = None,
        reinforced: bool | None = None,
        re_emerging: bool | None = None,
        cursor: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        self.get_dynamics_snapshot(authenticated_scope, dynamics_snapshot_id)
        try:
            offset, safe_limit = int(cursor or 0), int(limit)
        except (TypeError, ValueError) as exc:
            raise MemoryDynamicsError(
                "MEMORY_DYNAMICS_FAILED", "Signal pagination is invalid."
            ) from exc
        if offset < 0 or not 1 <= safe_limit <= 1000:
            raise MemoryDynamicsError(
                "MEMORY_DYNAMICS_FAILED", "Signal pagination is outside limits."
            )
        where = f"dynamics_snapshot_id={self.placeholder}"
        params: list[Any] = [dynamics_snapshot_id]
        for field, value in (
            ("memory_phase", memory_phase),
            ("reinforced", reinforced),
            ("re_emerging", re_emerging),
        ):
            if value is not None:
                where += f" AND {field}={self.placeholder}"
                params.append(value)
        params.extend([safe_limit + 1, offset])
        with self.repository.connect() as connection:
            rows = connection.execute(
                f"SELECT payload_json FROM {self.signal_table} WHERE {where} "
                f"ORDER BY signal_key LIMIT {self.placeholder} OFFSET {self.placeholder}",
                tuple(params),
            ).fetchall()
        items = [self._signal_from_payload(row["payload_json"]) for row in rows]
        return {
            "items": items[:safe_limit],
            "next_cursor": str(offset + safe_limit) if len(items) > safe_limit else None,
        }

    def compare_dynamics_snapshots(
        self,
        authenticated_scope: AuthenticatedScope,
        first_snapshot_id: str,
        second_snapshot_id: str,
    ) -> MemoryDynamicsComparison:
        first = self.get_dynamics_snapshot(
            authenticated_scope, first_snapshot_id
        )
        second = self.get_dynamics_snapshot(
            authenticated_scope, second_snapshot_id
        )
        first_signals = {
            item.signal_key: item
            for item in self._signals_for_snapshot(
                authenticated_scope, first_snapshot_id
            )
        }
        second_signals = {
            item.signal_key: item
            for item in self._signals_for_snapshot(
                authenticated_scope, second_snapshot_id
            )
        }
        common = sorted(set(first_signals) & set(second_signals))
        phase_changes = [
            {
                "signal_key": key,
                "from": first_signals[key].memory_phase,
                "to": second_signals[key].memory_phase,
            }
            for key in common
            if first_signals[key].memory_phase != second_signals[key].memory_phase
        ]
        influence_changes = [
            {
                "signal_key": key,
                "from": first_signals[key].final_influence,
                "to": second_signals[key].final_influence,
            }
            for key in common
            if first_signals[key].final_influence
            != second_signals[key].final_influence
        ]
        conflict_changes = [
            {
                "signal_key": key,
                "from": first_signals[key].conflicted,
                "to": second_signals[key].conflicted,
            }
            for key in common
            if first_signals[key].conflicted != second_signals[key].conflicted
        ]
        data = {
            "first_snapshot_id": first_snapshot_id,
            "second_snapshot_id": second_snapshot_id,
            "first_boundary": {"valid_at": first.valid_at, "known_at": first.known_at},
            "second_boundary": {
                "valid_at": second.valid_at,
                "known_at": second.known_at,
            },
            "signals_added": sorted(set(second_signals) - set(first_signals)),
            "signals_removed": sorted(set(first_signals) - set(second_signals)),
            "phase_changes": phase_changes,
            "influence_changes": influence_changes,
            "newly_reinforced": [
                key for key in common if not first_signals[key].reinforced and second_signals[key].reinforced
            ],
            "no_longer_reinforced": [
                key for key in common if first_signals[key].reinforced and not second_signals[key].reinforced
            ],
            "newly_re_emerging": [
                key for key in common if not first_signals[key].re_emerging and second_signals[key].re_emerging
            ],
            "newly_dormant": [
                item["signal_key"] for item in phase_changes if item["to"] == "dormant"
            ],
            "newly_decayed": [
                item["signal_key"] for item in phase_changes if item["to"] == "decayed"
            ],
            "reactivated_signals": [
                item["signal_key"]
                for item in phase_changes
                if item["to"] == "active" and item["from"] != "active"
            ],
            "conflict_state_changes": conflict_changes,
        }
        digest = sha256_text(
            canonical_json(
                {
                    **data,
                    "comparison_revision": MEMORY_DYNAMICS_COMPARISON_REVISION,
                }
            )
        )
        comparison = MemoryDynamicsComparison(
            **data, comparison_hash=digest
        )
        LOGGER.info(
            "%s",
            json.dumps(
                {
                    "event": "memory_dynamics_snapshot_compared",
                    "first_snapshot_id": first_snapshot_id,
                    "second_snapshot_id": second_snapshot_id,
                },
                sort_keys=True,
            ),
        )
        return comparison

    def annotate_memory_importance(self, *args: Any, **kwargs: Any) -> MemoryImportanceAnnotation:
        return self.importance.annotate_memory_importance(*args, **kwargs)

    def list_importance_annotations(
        self, authenticated_scope: AuthenticatedScope, event_id: str
    ) -> list[MemoryImportanceAnnotation]:
        return self.importance.list_importance_annotations(
            authenticated_scope, event_id
        )

    def build_continuity_packet(
        self,
        authenticated_scope: AuthenticatedScope,
        subject_scope: dict[str, str | None] | AuthenticatedScope | None = None,
        temporal_boundary: MemoryTemporalBoundary | None = None,
        dynamics_mode: str = MemoryDynamicsMode.TEMPORAL_MEMORY_V1.value,
        previous_packet: dict[str, Any] | None = None,
        event_ids: set[str] | frozenset[str] | None = None,
        persist_dynamics: bool = True,
        signal_identity_resolver: (
            Callable[[dict[str, Any]], tuple[str, str]] | None
        ) = None,
    ) -> dict[str, Any]:
        if dynamics_mode == MemoryDynamicsMode.LEGACY_RECENT5_V1.value:
            packet = self.reconstruction.build_continuity_packet(
                authenticated_scope,
                temporal_boundary=temporal_boundary,
                subject_scope=subject_scope,
                previous_packet=previous_packet,
                event_ids=event_ids,
            )
            packet["memory_dynamics_mode"] = dynamics_mode
            return packet
        if dynamics_mode != MemoryDynamicsMode.TEMPORAL_MEMORY_V1.value:
            raise MemoryDynamicsError(
                "MEMORY_TEMPORAL_POLICY_INVALID", "Dynamics mode is invalid."
            )
        result = self.compute_memory_dynamics(
            authenticated_scope,
            subject_scope,
            temporal_boundary,
            persist=persist_dynamics,
            event_ids=event_ids,
            signal_identity_resolver=signal_identity_resolver,
        )
        boundary = MemoryTemporalBoundary(
            valid_at=result.snapshot.valid_at, known_at=result.snapshot.known_at
        )
        packet = self.reconstruction.build_continuity_packet(
            authenticated_scope,
            temporal_boundary=boundary,
            subject_scope=subject_scope,
            previous_packet=previous_packet,
            event_ids=event_ids,
        )
        by_phase = {
            phase: [
                self._safe_signal(item)
                for item in result.signals
                if item.memory_phase == phase
            ]
            for phase in ("active", "latent", "dormant", "decayed")
        }
        packet["active_information"] = by_phase["active"]
        packet["latent_information"] = by_phase["latent"]
        packet["dormant_information"] = by_phase["dormant"]
        packet["decayed_signals"] = by_phase["decayed"]
        packet["reinforced_signals"] = [
            self._safe_signal(item) for item in result.signals if item.reinforced
        ]
        packet["re_emergence_signals"] = [
            {
                **self._safe_signal(item),
                "prior_occurrence_event_id": item.prior_occurrence_event_id,
                "latest_occurrence_event_id": item.latest_occurrence_event_id,
                "gap_seconds": item.reemergence_gap_seconds,
                "gap_event_count": item.reemergence_gap_event_count,
                "prior_memory_phase": item.prior_memory_phase,
            }
            for item in result.signals
            if item.re_emerging
        ]
        horizon_counts: Counter[str] = Counter()
        for item in result.signals:
            horizon_counts.update(item.occurrences_by_horizon)
        packet["temporal_horizon_summary"] = dict(sorted(horizon_counts.items()))
        latest_event = self._latest_effective_event(
            authenticated_scope, boundary, subject_scope, event_ids=event_ids
        )
        latest_signal = None
        if latest_event:
            key, _ = signal_identity(latest_event)
            latest_signal = next(
                (item for item in result.signals if item.signal_key == key), None
            )
        packet["current_state_event_id"] = (
            str(latest_event.get("event_id")) if latest_event else None
        )
        packet["current_state_signal"] = (
            latest_signal.signal_key if latest_signal else None
        )
        packet["current_state_age_seconds"] = (
            latest_signal.age_seconds if latest_signal else None
        )
        packet["current_state_horizon"] = (
            latest_signal.latest_horizon if latest_signal else None
        )
        packet["current_state_memory_phase"] = (
            latest_signal.memory_phase if latest_signal else None
        )
        packet["current_state_influence"] = (
            latest_signal.final_influence if latest_signal else None
        )
        packet["current_state_time_basis"] = (
            latest_signal.event_time_basis if latest_signal else None
        )
        influences = [item.final_influence for item in result.signals]
        strongest = max(
            result.signals,
            key=lambda item: (item.final_influence, item.signal_key),
            default=None,
        )
        active = [item for item in result.signals if item.memory_phase == "active"]
        packet["temporal_quality"] = {
            "active_signal_count": result.snapshot.active_signal_count,
            "dormant_signal_count": result.snapshot.dormant_signal_count,
            "decayed_signal_count": result.snapshot.decayed_signal_count,
            "reinforced_signal_count": result.snapshot.reinforced_signal_count,
            "re_emerging_signal_count": result.snapshot.re_emerging_signal_count,
            "average_influence": quantize8(
                sum(influences) / len(influences) if influences else 0.0
            ),
            "strongest_signal": strongest.signal_key if strongest else None,
            "oldest_active_signal": min(
                active, key=lambda item: (-item.age_seconds, item.signal_key)
            ).signal_key
            if active
            else None,
            "temporal_coverage_span_seconds": max(
                (item.recurrence_span_seconds for item in result.signals),
                default=0.0,
            ),
        }
        context = {
            "dynamics_snapshot_id": result.snapshot.dynamics_snapshot_id,
            "dynamics_snapshot_hash": result.snapshot.dynamics_snapshot_identity,
            "dynamics_mode": dynamics_mode,
            "temporal_policy_id": result.snapshot.temporal_policy_id,
            "temporal_boundary": {
                "valid_at": result.snapshot.valid_at,
                "known_at": result.snapshot.known_at,
            },
            "resolved_event_manifest_hash": result.snapshot.resolved_event_manifest_hash,
            "importance_annotation_manifest_hash": result.snapshot.importance_annotation_manifest_hash,
            "signal_dynamics_manifest_hash": result.snapshot.signal_dynamics_manifest_hash,
            "memory_temporal_policy_revision": MEMORY_TEMPORAL_POLICY_REVISION,
            "memory_influence_revision": MEMORY_INFLUENCE_REVISION,
            "memory_recurrence_revision": MEMORY_RECURRENCE_REVISION,
            "memory_reemergence_revision": MEMORY_REEMERGENCE_REVISION,
            "continuity_temporal_adapter_revision": CONTINUITY_TEMPORAL_ADAPTER_REVISION,
        }
        packet["memory_dynamics_context"] = context
        packet["memory_dynamics_mode"] = dynamics_mode
        identity_material = {
            "base_packet_id": packet["packet_id"],
            "snapshot_id": result.snapshot.dynamics_snapshot_id,
            "snapshot_hash": result.snapshot.dynamics_snapshot_identity,
            "boundary": context["temporal_boundary"],
            "policy_revision": MEMORY_TEMPORAL_POLICY_REVISION,
            "continuity_revision": ALGORITHM_REVISION,
            "subject_scope": self.reconstruction._subject_kwargs(subject_scope),
            "adapter_revision": CONTINUITY_TEMPORAL_ADAPTER_REVISION,
        }
        digest = sha256_text(canonical_json(identity_material))
        packet["base_continuity_packet_id"] = packet["packet_id"]
        packet["packet_id"] = f"packet_temporal_{digest[:24]}"
        packet["report_id"] = f"report_temporal_{digest[:24]}"
        packet["provenance"]["deterministic_packet_hash"] = digest
        packet["provenance"]["temporal_memory_adapter"] = True
        packet["provenance"]["source_text_exposed"] = False
        packet["temporal_packet_change_reason"] = self._change_reason(
            previous_packet, context
        )
        if persist_dynamics:
            self._link_packet(
                authenticated_scope,
                result.snapshot.dynamics_snapshot_id,
                packet["packet_id"],
                digest,
            )
        return packet

    def verify_memory_dynamics_integrity(
        self,
        authenticated_scope: AuthenticatedScope,
        dynamics_snapshot_id: str,
    ) -> MemoryDynamicsIntegrityResult:
        checks: dict[str, bool] = {}
        details: dict[str, Any] = {}
        snapshot = self.get_dynamics_snapshot(
            authenticated_scope, dynamics_snapshot_id
        )
        stored_signals = self._signals_for_snapshot(
            authenticated_scope, dynamics_snapshot_id
        )
        policy = policy_from_configuration(snapshot.temporal_policy_configuration)
        subject = {
            "application_reference": snapshot.application_reference,
            "actor_reference": snapshot.actor_reference,
            "workspace_reference": snapshot.workspace_reference,
            "entity_reference": snapshot.entity_reference,
            "session_reference": snapshot.session_reference,
        }
        recomputed = self._compute(
            authenticated_scope,
            subject,
            MemoryTemporalBoundary(
                valid_at=snapshot.valid_at, known_at=snapshot.known_at
            ),
            policy,
        )
        checks["snapshot_identity_reproduces"] = (
            recomputed.snapshot.dynamics_snapshot_identity
            == snapshot.dynamics_snapshot_identity
            and recomputed.snapshot.dynamics_snapshot_id
            == snapshot.dynamics_snapshot_id
        )
        checks["resolved_event_manifest_reproduces"] = (
            recomputed.snapshot.resolved_event_manifest_hash
            == snapshot.resolved_event_manifest_hash
        )
        checks["importance_manifest_reproduces"] = (
            recomputed.snapshot.importance_annotation_manifest_hash
            == snapshot.importance_annotation_manifest_hash
        )
        checks["signal_manifest_reproduces"] = (
            recomputed.snapshot.signal_dynamics_manifest_hash
            == snapshot.signal_dynamics_manifest_hash
        )
        stored_by_key = {item.signal_key: item for item in stored_signals}
        recomputed_by_key = {item.signal_key: item for item in recomputed.signals}
        checks["signal_identity_reproduces"] = set(stored_by_key) == set(recomputed_by_key)
        checks["signal_dynamics_reproduce"] = all(
            self._signal_manifest_item(stored_by_key[key])
            == self._signal_manifest_item(recomputed_by_key[key])
            for key in stored_by_key
            if key in recomputed_by_key
        )
        checks["snapshot_counts_match"] = (
            snapshot.signal_count == len(stored_signals)
            and snapshot.active_signal_count
            == sum(item.memory_phase == "active" for item in stored_signals)
            and snapshot.latent_signal_count
            == sum(item.memory_phase == "latent" for item in stored_signals)
            and snapshot.dormant_signal_count
            == sum(item.memory_phase == "dormant" for item in stored_signals)
            and snapshot.decayed_signal_count
            == sum(item.memory_phase == "decayed" for item in stored_signals)
            and snapshot.reinforced_signal_count
            == sum(item.reinforced for item in stored_signals)
            and snapshot.re_emerging_signal_count
            == sum(item.re_emerging for item in stored_signals)
            and snapshot.conflicted_signal_count
            == sum(item.conflicted for item in stored_signals)
        )
        subject_kwargs = self.reconstruction._subject_kwargs(subject)
        resolved_view = self.state_resolver.resolve_effective_events(
            authenticated_scope,
            MemoryTemporalBoundary(
                valid_at=snapshot.valid_at, known_at=snapshot.known_at
            ),
            **subject_kwargs,
            include_conflicted=True,
        )
        effective_event_ids = {
            str(item.get("event_id")) for item in resolved_view.effective_events
        }
        checks["occurrence_events_exist_and_scoped"] = all(
            event_id in effective_event_ids
            for item in stored_signals
            for event_id in item.occurrence_event_ids
        )
        checks["no_future_leakage"] = all(
            item.latest_occurrence_at <= snapshot.valid_at for item in stored_signals
        )
        if snapshot.temporal_packet_id and snapshot.temporal_packet_hash:
            packet = self.build_continuity_packet(
                authenticated_scope,
                subject,
                MemoryTemporalBoundary(
                    valid_at=snapshot.valid_at, known_at=snapshot.known_at
                ),
            )
            checks["temporal_packet_hash_reproduces"] = (
                packet["packet_id"] == snapshot.temporal_packet_id
                and packet["provenance"]["deterministic_packet_hash"]
                == snapshot.temporal_packet_hash
            )
        else:
            checks["temporal_packet_hash_reproduces"] = True
        failures = [name for name, passed in checks.items() if not passed]
        details.update(
            {
                "signal_count": len(stored_signals),
                "resolved_event_count": snapshot.resolved_event_count,
                "temporal_packet_linked": bool(snapshot.temporal_packet_id),
            }
        )
        result = MemoryDynamicsIntegrityResult(
            dynamics_snapshot_id=dynamics_snapshot_id,
            verified=not failures,
            checks=checks,
            failures=failures,
            details=details,
        )
        LOGGER.info(
            "%s",
            json.dumps(
                {
                    "event": (
                        "memory_dynamics_integrity_verified"
                        if result.verified
                        else "memory_dynamics_integrity_failed"
                    ),
                    "snapshot_id": dynamics_snapshot_id,
                    "signal_count": len(stored_signals),
                    "error_code": None
                    if result.verified
                    else "MEMORY_DYNAMICS_INTEGRITY_FAILED",
                },
                sort_keys=True,
            ),
        )
        return result

    def _compute(
        self,
        scope: AuthenticatedScope,
        subject_scope: dict[str, str | None] | AuthenticatedScope | None,
        temporal_boundary: MemoryTemporalBoundary | None,
        policy: TemporalMemoryPolicy,
        *,
        event_ids: set[str] | frozenset[str] | None = None,
        signal_identity_resolver: (
            Callable[[dict[str, Any]], tuple[str, str]] | None
        ) = None,
    ) -> MemoryDynamicsResult:
        started = time.perf_counter()
        captured = _now()
        boundary = temporal_boundary or MemoryTemporalBoundary(
            valid_at=captured, known_at=captured
        )
        boundary = MemoryTemporalBoundary(
            valid_at=boundary.valid_at or captured,
            known_at=boundary.known_at or captured,
        )
        valid_at, valid_epoch = _time(boundary.valid_at)
        known_at, _ = _time(boundary.known_at)
        subject = self.reconstruction._subject_kwargs(subject_scope)
        resolver_started = time.perf_counter()
        view = self.state_resolver.resolve_effective_events(
            scope,
            MemoryTemporalBoundary(valid_at=valid_at, known_at=known_at),
            **subject,
            include_conflicted=True,
            event_ids=event_ids,
        )
        resolver_ms = round((time.perf_counter() - resolver_started) * 1000, 3)
        projection_map = {item.event_id: item for item in view.projections}
        effective_annotations = self.importance.effective_annotations(scope, known_at)
        occurrences: list[dict[str, Any]] = []
        for index, event in enumerate(view.effective_events):
            event_id = str(event.get("event_id"))
            occurred_at, event_epoch, basis = self._event_time(scope, event)
            age_seconds = valid_epoch - event_epoch
            if age_seconds < 0:
                raise MemoryDynamicsError(
                    "MEMORY_EVENT_TIME_INVALID",
                    "A future event unexpectedly reached temporal dynamics.",
                )
            signal_key, identity_source = (
                signal_identity_resolver(event)
                if signal_identity_resolver is not None
                else signal_identity(event)
            )
            projection = projection_map[event_id]
            weight, annotation_id = self._event_importance(
                event, effective_annotations.get(event_id), policy
            )
            occurrences.append(
                {
                    "event_id": event_id,
                    "event": event,
                    "global_index": index,
                    "occurred_at": occurred_at,
                    "occurred_epoch": event_epoch,
                    "age_seconds": age_seconds,
                    "horizon": classify_horizon(
                        age_seconds, policy.horizon_policy
                    ),
                    "event_time_basis": basis,
                    "signal_key": signal_key,
                    "signal_identity_source": identity_source,
                    "importance_weight": weight,
                    "importance_annotation_id": annotation_id,
                    "epistemic_status": projection.epistemic_status,
                    "source_id": projection.source_id,
                    "open_conflict_ids": list(projection.open_conflict_ids),
                }
            )
        recurrence_started = time.perf_counter()
        grouped = group_occurrences(occurrences)
        recurrence_ms = round((time.perf_counter() - recurrence_started) * 1000, 3)
        occurrence_event_ids = {entry["event_id"] for entry in occurrences}
        event_manifest = [
            {
                "event_id": item.event_id,
                "event_hash": item.event_hash,
            }
            for item in view.projections
            if item.event_id in occurrence_event_ids
        ]
        event_manifest_hash = sha256_text(canonical_json(event_manifest))
        annotation_manifest = [
            {
                "annotation_id": annotation.importance_annotation_id,
                "event_id": event_id,
                "weight": annotation.importance_weight,
                "system_effective_at": annotation.system_effective_at,
            }
            for event_id, annotation in sorted(effective_annotations.items())
            if event_id in occurrence_event_ids
        ]
        annotation_manifest_hash = sha256_text(canonical_json(annotation_manifest))
        identity_material = {
            "scope": scope.memory_boundary(),
            "subject_scope": subject,
            "valid_at": valid_at,
            "known_at": known_at,
            "resolved_event_manifest_hash": event_manifest_hash,
            "importance_annotation_manifest_hash": annotation_manifest_hash,
            "signal_identity_mode": (
                "custom_revisioned_projection"
                if signal_identity_resolver is not None
                else "exact_signal_v1"
            ),
            "policy": policy.configuration(),
            "revisions": {
                "schema": MEMORY_TEMPORAL_SCHEMA_REVISION,
                "policy": MEMORY_TEMPORAL_POLICY_REVISION,
                "horizon": MEMORY_HORIZON_REVISION,
                "influence": MEMORY_INFLUENCE_REVISION,
                "recurrence": MEMORY_RECURRENCE_REVISION,
                "reemergence": MEMORY_REEMERGENCE_REVISION,
                "importance": MEMORY_IMPORTANCE_REVISION,
                "resolver": MEMORY_STATE_RESOLVER_REVISION,
                "bitemporal": BITEMPORAL_POLICY_REVISION,
            },
        }
        identity = sha256_text(canonical_json(identity_material))
        snapshot_id = f"mdyn_{identity[:24]}"
        computed_at = _now()
        reemergence_started = time.perf_counter()
        signals = [
            self._build_signal(
                scope,
                snapshot_id,
                signal_key,
                items,
                occurrences,
                policy,
                computed_at,
            )
            for signal_key, items in grouped.items()
        ]
        for item in signals:
            if item.reinforced:
                self._log_signal_state("memory_signal_reinforced", item, snapshot_id)
            if item.re_emerging:
                self._log_signal_state("memory_signal_reemerged", item, snapshot_id)
            if item.memory_phase == "dormant":
                self._log_signal_state(
                    "memory_signal_became_dormant", item, snapshot_id
                )
            if item.memory_phase == "decayed":
                self._log_signal_state("memory_signal_decayed", item, snapshot_id)
        reemergence_ms = round(
            (time.perf_counter() - reemergence_started) * 1000, 3
        )
        signal_manifest = [
            self._signal_manifest_item(item) for item in signals
        ]
        signal_manifest_hash = sha256_text(canonical_json(signal_manifest))
        counts = Counter(item.memory_phase for item in signals)
        snapshot = MemoryDynamicsSnapshot(
            dynamics_snapshot_id=snapshot_id,
            dynamics_snapshot_identity=identity,
            client_id=scope.client_id,
            vault_id=scope.vault_id,
            namespace=scope.namespace,
            application_reference=subject["application_reference"],
            actor_reference=subject["actor_reference"],
            workspace_reference=subject["workspace_reference"],
            entity_reference=subject["entity_reference"],
            session_reference=subject["session_reference"],
            valid_at=valid_at,
            known_at=known_at,
            computed_at=computed_at,
            dynamics_mode=MemoryDynamicsMode.TEMPORAL_MEMORY_V1.value,
            temporal_policy_id=policy.policy_id,
            temporal_policy_configuration=policy.configuration(),
            resolved_event_count=len(occurrences),
            resolved_event_manifest_hash=event_manifest_hash,
            importance_annotation_manifest_hash=annotation_manifest_hash,
            signal_count=len(signals),
            active_signal_count=counts["active"],
            latent_signal_count=counts["latent"],
            dormant_signal_count=counts["dormant"],
            decayed_signal_count=counts["decayed"],
            reinforced_signal_count=sum(item.reinforced for item in signals),
            re_emerging_signal_count=sum(item.re_emerging for item in signals),
            conflicted_signal_count=sum(item.conflicted for item in signals),
            signal_dynamics_manifest_hash=signal_manifest_hash,
            temporal_packet_id=None,
            temporal_packet_hash=None,
            memory_temporal_schema_revision=MEMORY_TEMPORAL_SCHEMA_REVISION,
            memory_temporal_policy_revision=MEMORY_TEMPORAL_POLICY_REVISION,
            memory_horizon_revision=MEMORY_HORIZON_REVISION,
            memory_influence_revision=MEMORY_INFLUENCE_REVISION,
            memory_recurrence_revision=MEMORY_RECURRENCE_REVISION,
            memory_reemergence_revision=MEMORY_REEMERGENCE_REVISION,
            memory_importance_revision=MEMORY_IMPORTANCE_REVISION,
            memory_state_resolver_revision=MEMORY_STATE_RESOLVER_REVISION,
            bitemporal_policy_revision=BITEMPORAL_POLICY_REVISION,
            duration_ms=round((time.perf_counter() - started) * 1000, 3),
            created_at=computed_at,
        )
        return MemoryDynamicsResult(
            snapshot=snapshot,
            signals=signals,
            created=True,
            replayed=False,
            resolver_duration_ms=resolver_ms,
            recurrence_duration_ms=recurrence_ms,
            reemergence_duration_ms=reemergence_ms,
            persistence_duration_ms=0.0,
        )

    def _build_signal(
        self,
        scope: AuthenticatedScope,
        snapshot_id: str,
        signal_key: str,
        items: list[dict[str, Any]],
        all_occurrences: list[dict[str, Any]],
        policy: TemporalMemoryPolicy,
        created_at: str,
    ) -> MemorySignalDynamics:
        summary = recurrence_summary(items)
        latest = items[-1]
        base = base_time_influence(latest["age_seconds"], policy.half_life_seconds)
        selected = max(
            items,
            key=lambda item: (
                item["importance_weight"],
                item["event_id"],
            ),
        )
        importance_weight = selected["importance_weight"]
        weighted = quantize8(base * importance_weight)
        recurrence = recurrence_boost(len(items), policy)
        cross = cross_horizon_boost(summary["distinct_horizon_count"], policy)
        total_boost = quantize8(recurrence + cross)
        raw = quantize8(weighted + recurrence + cross)
        final = clamp01(raw)
        phase = classify_phase(final, policy)
        reemergence = self._reemergence(
            items, all_occurrences, policy
        )
        identity = sha256_text(
            canonical_json(
                {
                    "snapshot_id": snapshot_id,
                    "signal_key": signal_key,
                    "occurrences": summary["occurrence_event_ids"],
                    "revision": MEMORY_DYNAMICS_SNAPSHOT_REVISION,
                }
            )
        )
        epistemic = Counter(item["epistemic_status"] for item in items)
        sources = sorted(
            {str(item["source_id"]) for item in items if item["source_id"]}
        )
        open_conflicts = sorted(
            {
                conflict_id
                for item in items
                for conflict_id in item["open_conflict_ids"]
            }
        )
        return MemorySignalDynamics(
            signal_dynamics_id=f"msig_{identity[:24]}",
            dynamics_snapshot_id=snapshot_id,
            signal_key=signal_key,
            signal_identity_source=latest["signal_identity_source"],
            client_id=scope.client_id,
            vault_id=scope.vault_id,
            namespace=scope.namespace,
            application_reference=latest["event"].get("application_reference") or None,
            actor_reference=latest["event"].get("actor_reference") or None,
            workspace_reference=latest["event"].get("workspace_reference") or None,
            entity_reference=latest["event"].get("entity_reference") or None,
            session_reference=latest["event"].get("session_reference") or None,
            first_occurrence_at=summary["first_occurrence_at"],
            latest_occurrence_at=summary["latest_occurrence_at"],
            occurrence_count=summary["occurrence_count"],
            occurrence_event_ids=summary["occurrence_event_ids"],
            occurrences_by_horizon=summary["occurrences_by_horizon"],
            distinct_horizon_count=summary["distinct_horizon_count"],
            latest_horizon=latest["horizon"],
            age_seconds=quantize8(latest["age_seconds"]),
            age_days=round(latest["age_seconds"] / 86_400.0, 4),
            event_time_basis=latest["event_time_basis"],
            base_time_influence=base,
            importance_weight=importance_weight,
            importance_selected_event_id=selected["event_id"],
            importance_annotation_id=selected["importance_annotation_id"],
            importance_aggregation_method="max_effective_event_importance_v1",
            weighted_time_influence=weighted,
            recurrence_boost=recurrence,
            cross_horizon_boost=cross,
            total_reinforcement_boost=total_boost,
            reinforcement_reason=(
                "Repeated structural signal occurrences increase continuity influence; repetition does not prove truth."
                if len(items) >= 2 and total_boost > 0
                else None
            ),
            unclamped_influence=raw,
            final_influence=final,
            memory_phase=phase,
            reinforced=len(items) >= 2 and total_boost > 0,
            re_emerging=reemergence["re_emerging"],
            re_emergence_count=reemergence["re_emergence_count"],
            prior_occurrence_event_id=reemergence["prior_occurrence_event_id"],
            latest_occurrence_event_id=latest["event_id"],
            reemergence_gap_seconds=reemergence["gap_seconds"],
            reemergence_gap_event_count=reemergence["gap_event_count"],
            prior_memory_phase=reemergence["prior_memory_phase"],
            reemergence_detection_revision=MEMORY_REEMERGENCE_REVISION,
            conflicted=bool(open_conflicts),
            # Terminal states are excluded by MemoryStateResolver before this model.
            superseded=False,
            retracted=False,
            invalidated=False,
            open_conflict_ids=open_conflicts,
            epistemic_status_counts=dict(sorted(epistemic.items())),
            source_count=len(sources),
            source_ids=sources,
            maximum_gap_seconds=quantize8(summary["maximum_gap_seconds"]),
            maximum_gap_event_count=summary["maximum_gap_event_count"],
            recurrence_span_seconds=quantize8(summary["recurrence_span_seconds"]),
            signal_identity_revision=SIGNAL_IDENTITY_REVISION,
            memory_temporal_policy_revision=MEMORY_TEMPORAL_POLICY_REVISION,
            memory_influence_revision=MEMORY_INFLUENCE_REVISION,
            memory_recurrence_revision=MEMORY_RECURRENCE_REVISION,
            memory_reemergence_revision=MEMORY_REEMERGENCE_REVISION,
            created_at=created_at,
        )

    def _reemergence(
        self,
        items: list[dict[str, Any]],
        all_occurrences: list[dict[str, Any]],
        policy: TemporalMemoryPolicy,
    ) -> dict[str, Any]:
        result = {
            "re_emerging": False,
            "re_emergence_count": 0,
            "prior_occurrence_event_id": None,
            "gap_seconds": None,
            "gap_event_count": None,
            "prior_memory_phase": None,
        }
        if len(items) < 2:
            return result
        qualifying: list[dict[str, Any]] = []
        for prior_index, (prior, current) in enumerate(zip(items, items[1:])):
            gap_seconds = current["occurred_epoch"] - prior["occurred_epoch"]
            gap_events = current["global_index"] - prior["global_index"] - 1
            prior_items = items[: prior_index + 1]
            prior_phase = self._phase_at(
                prior_items, current["occurred_epoch"], policy
            )
            qualifies = (
                gap_seconds >= policy.minimum_reemergence_gap_seconds
                or gap_events >= policy.minimum_reemergence_gap_events
            ) and prior_phase in {"latent", "dormant", "decayed"}
            if qualifies:
                qualifying.append(
                    {
                        "prior_occurrence_event_id": prior["event_id"],
                        "latest_occurrence_event_id": current["event_id"],
                        "gap_seconds": quantize8(gap_seconds),
                        "gap_event_count": max(0, gap_events),
                        "prior_memory_phase": prior_phase,
                    }
                )
        result["re_emergence_count"] = len(qualifying)
        if not qualifying:
            return result
        latest_pair = qualifying[-1]
        if (
            latest_pair["latest_occurrence_event_id"] == items[-1]["event_id"]
            and items[-1]["horizon"] in {"immediate", "short"}
        ):
            result.update(latest_pair)
            result["re_emerging"] = True
        return result

    def _phase_at(
        self,
        items: list[dict[str, Any]],
        as_of_epoch: float,
        policy: TemporalMemoryPolicy,
    ) -> str:
        latest = items[-1]
        age = max(0.0, as_of_epoch - latest["occurred_epoch"])
        base = base_time_influence(age, policy.half_life_seconds)
        importance = max(item["importance_weight"] for item in items)
        horizons = {
            classify_horizon(
                max(0.0, as_of_epoch - item["occurred_epoch"]),
                policy.horizon_policy,
            )
            for item in items
        }
        final = clamp01(
            base * importance
            + recurrence_boost(len(items), policy)
            + cross_horizon_boost(len(horizons), policy)
        )
        return classify_phase(final, policy)

    def _event_time(
        self, scope: AuthenticatedScope, event: dict[str, Any]
    ) -> tuple[str, float, str]:
        external = event.get("external_metadata")
        metadata = event_metadata(event)
        for value in (
            event.get("occurred_at"),
            external.get("occurred_at") if isinstance(external, dict) else None,
        ):
            if value:
                normalized, epoch = _time(str(value))
                return normalized, epoch, "event_occurred_at"
        candidate_id = metadata.get("candidate_id")
        if candidate_id:
            try:
                candidate = self.ledger.admission.candidates.get_candidate(
                    scope, str(candidate_id)
                )
                if candidate.proposed_occurred_at:
                    normalized, epoch = _time(candidate.proposed_occurred_at)
                    return normalized, epoch, "candidate_occurred_at"
                evidence = self.ledger.admission.candidates.get_candidate_evidence(
                    scope, candidate.candidate_id
                )
                primary = next(
                    (item for item in evidence if item.evidence_role == "primary"),
                    None,
                )
                if primary:
                    source_id = metadata.get("source_id") or candidate.source_id
                    page = self.ledger.admission.sources.list_source_segments(
                        scope, str(source_id), limit=1000
                    )
                    segment = next(
                        (
                            item
                            for item in page.items
                            if item.segment_id == primary.segment_id
                        ),
                        None,
                    )
                    if segment and segment.occurred_at:
                        normalized, epoch = _time(segment.occurred_at)
                        return normalized, epoch, "segment_occurred_at"
            except Exception:
                pass
        source_id = metadata.get("source_id")
        if source_id:
            try:
                source = self.ledger.admission.sources.get_source(
                    scope, str(source_id)
                )
                if source.occurred_at:
                    normalized, epoch = _time(source.occurred_at)
                    return normalized, epoch, "source_occurred_at"
                normalized, epoch = _time(source.ingested_at)
                return normalized, epoch, "source_ingested_at"
            except Exception:
                pass
        if event.get("timestamp"):
            normalized, epoch = _time(str(event["timestamp"]))
            return normalized, epoch, "event_stored_at"
        raise MemoryDynamicsError(
            "MEMORY_EVENT_TIME_INVALID", "Event has no supported temporal anchor."
        )

    def _event_importance(
        self,
        event: dict[str, Any],
        annotation: MemoryImportanceAnnotation | None,
        policy: TemporalMemoryPolicy,
    ) -> tuple[float, str | None]:
        if annotation:
            return annotation.importance_weight, annotation.importance_annotation_id
        metadata = event_metadata(event)
        weights = policy.configuration()["importance_weights"]
        level = metadata.get("importance_level")
        if isinstance(level, str) and level in weights:
            return quantize8(weights[level]), None
        numeric = metadata.get("importance_weight")
        if isinstance(numeric, (int, float)) and not isinstance(numeric, bool):
            value = float(numeric)
            if policy.numeric_importance_min <= value <= policy.numeric_importance_max:
                return quantize8(value), None
        return 1.0, None

    def _persist(
        self,
        snapshot: MemoryDynamicsSnapshot,
        signals: list[MemorySignalDynamics],
    ) -> None:
        snapshot_payload: Any = canonical_json(snapshot.to_dict())
        with self.repository.connect() as connection:
            if self.backend == "sqlite":
                connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                f"INSERT INTO {self.snapshot_table}("
                "dynamics_snapshot_id,dynamics_snapshot_identity,client_id,vault_id,namespace,"
                "application_reference,actor_reference,workspace_reference,entity_reference,"
                "session_reference,valid_at,known_at,dynamics_mode,temporal_policy_id,"
                "resolved_event_manifest_hash,importance_annotation_manifest_hash,"
                "signal_dynamics_manifest_hash,payload_json,created_at"
                f") VALUES({','.join([self.placeholder] * 19)})",
                (
                    snapshot.dynamics_snapshot_id,
                    snapshot.dynamics_snapshot_identity,
                    snapshot.client_id,
                    snapshot.vault_id,
                    snapshot.namespace,
                    snapshot.application_reference,
                    snapshot.actor_reference,
                    snapshot.workspace_reference,
                    snapshot.entity_reference,
                    snapshot.session_reference,
                    snapshot.valid_at,
                    snapshot.known_at,
                    snapshot.dynamics_mode,
                    snapshot.temporal_policy_id,
                    snapshot.resolved_event_manifest_hash,
                    snapshot.importance_annotation_manifest_hash,
                    snapshot.signal_dynamics_manifest_hash,
                    snapshot_payload,
                    snapshot.created_at,
                ),
            )
            for signal in signals:
                payload: Any = canonical_json(signal.to_dict())
                connection.execute(
                    f"INSERT INTO {self.signal_table}("
                    "signal_dynamics_id,dynamics_snapshot_id,signal_key,memory_phase,"
                    "reinforced,re_emerging,final_influence,payload_json,created_at"
                    f") VALUES({','.join([self.placeholder] * 9)})",
                    (
                        signal.signal_dynamics_id,
                        signal.dynamics_snapshot_id,
                        signal.signal_key,
                        signal.memory_phase,
                        signal.reinforced,
                        signal.re_emerging,
                        signal.final_influence,
                        payload,
                        signal.created_at,
                    ),
                )

    def _snapshot_by_identity(
        self, scope: AuthenticatedScope, identity: str
    ) -> MemoryDynamicsSnapshot | None:
        p = self.placeholder
        with self.repository.connect() as connection:
            row = connection.execute(
                f"SELECT payload_json FROM {self.snapshot_table} "
                f"WHERE dynamics_snapshot_identity={p} AND client_id={p} "
                f"AND vault_id={p} AND namespace={p}",
                (identity, *scope.memory_boundary()),
            ).fetchone()
        return self._snapshot_from_payload(row["payload_json"]) if row else None

    def _signals_for_snapshot(
        self, scope: AuthenticatedScope, snapshot_id: str
    ) -> list[MemorySignalDynamics]:
        self.get_dynamics_snapshot(scope, snapshot_id)
        with self.repository.connect() as connection:
            rows = connection.execute(
                f"SELECT payload_json FROM {self.signal_table} "
                f"WHERE dynamics_snapshot_id={self.placeholder} ORDER BY signal_key",
                (snapshot_id,),
            ).fetchall()
        return [self._signal_from_payload(row["payload_json"]) for row in rows]

    @staticmethod
    def _snapshot_from_payload(value: Any) -> MemoryDynamicsSnapshot:
        payload = json.loads(value) if isinstance(value, str) else value
        return MemoryDynamicsSnapshot(**payload)

    @staticmethod
    def _signal_from_payload(value: Any) -> MemorySignalDynamics:
        payload = json.loads(value) if isinstance(value, str) else value
        return MemorySignalDynamics(**payload)

    @staticmethod
    def _signal_manifest_item(item: MemorySignalDynamics) -> dict[str, Any]:
        payload = item.to_dict()
        payload.pop("created_at", None)
        return payload

    @staticmethod
    def _safe_signal(item: MemorySignalDynamics) -> dict[str, Any]:
        return {
            "signal": item.signal_key,
            "phase": item.memory_phase,
            "influence": item.final_influence,
            "latest_horizon": item.latest_horizon,
            "occurrence_count": item.occurrence_count,
            "reinforced": item.reinforced,
            "re_emerging": item.re_emerging,
            "conflicted": item.conflicted,
            "last_seen": item.latest_occurrence_at,
        }

    def _latest_effective_event(
        self,
        scope: AuthenticatedScope,
        boundary: MemoryTemporalBoundary,
        subject_scope: dict[str, str | None] | AuthenticatedScope | None,
        *,
        event_ids: set[str] | frozenset[str] | None = None,
    ) -> dict[str, Any] | None:
        subject = self.reconstruction._subject_kwargs(subject_scope)
        view = self.state_resolver.resolve_effective_events(
            scope,
            boundary,
            **subject,
            include_conflicted=True,
            event_ids=event_ids,
        )
        return view.effective_events[-1] if view.effective_events else None

    def _link_packet(
        self,
        scope: AuthenticatedScope,
        snapshot_id: str,
        packet_id: str,
        packet_hash: str,
    ) -> None:
        snapshot = self.get_dynamics_snapshot(scope, snapshot_id)
        if (
            snapshot.temporal_packet_id == packet_id
            and snapshot.temporal_packet_hash == packet_hash
        ):
            return
        updated = replace(
            snapshot,
            temporal_packet_id=packet_id,
            temporal_packet_hash=packet_hash,
        )
        payload: Any = canonical_json(updated.to_dict())
        p = self.placeholder
        with self.repository.connect() as connection:
            if self.backend == "sqlite":
                connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                f"UPDATE {self.snapshot_table} SET payload_json={p} "
                f"WHERE dynamics_snapshot_id={p} AND client_id={p} "
                f"AND vault_id={p} AND namespace={p}",
                (
                    payload,
                    snapshot_id,
                    *scope.memory_boundary(),
                ),
            )

    @staticmethod
    def _change_reason(
        previous_packet: dict[str, Any] | None, context: dict[str, Any]
    ) -> str:
        if not previous_packet:
            return "new_event"
        previous = previous_packet.get("memory_dynamics_context") or {}
        if previous.get("memory_temporal_policy_revision") != context.get(
            "memory_temporal_policy_revision"
        ):
            return "policy_revision"
        if previous.get("importance_annotation_manifest_hash") != context.get(
            "importance_annotation_manifest_hash"
        ):
            return "importance_annotation"
        if previous.get("resolved_event_manifest_hash") != context.get(
            "resolved_event_manifest_hash"
        ):
            return "memory_evolution"
        if previous.get("temporal_boundary") != context.get("temporal_boundary"):
            return "time_progression"
        return "new_event"

    @staticmethod
    def _log_signal_state(
        event_name: str, signal: MemorySignalDynamics, snapshot_id: str
    ) -> None:
        LOGGER.info(
            "%s",
            json.dumps(
                {
                    "event": event_name,
                    "snapshot_id": snapshot_id,
                    "policy_id": MemoryDynamicsMode.TEMPORAL_MEMORY_V1.value,
                    "phase": signal.memory_phase,
                    "occurrence_count": signal.occurrence_count,
                },
                sort_keys=True,
            ),
        )

    @staticmethod
    def _log_completed(
        result: MemoryDynamicsResult, scope_fingerprint: str
    ) -> None:
        LOGGER.info(
            "%s",
            json.dumps(
                {
                    "event": "memory_dynamics_completed",
                    "snapshot_id": result.snapshot.dynamics_snapshot_id,
                    "event_count": result.snapshot.resolved_event_count,
                    "signal_count": result.snapshot.signal_count,
                    "phase_counts": {
                        "active": result.snapshot.active_signal_count,
                        "latent": result.snapshot.latent_signal_count,
                        "dormant": result.snapshot.dormant_signal_count,
                        "decayed": result.snapshot.decayed_signal_count,
                    },
                    "reinforced_count": result.snapshot.reinforced_signal_count,
                    "re_emergence_count": result.snapshot.re_emerging_signal_count,
                    "policy_id": result.snapshot.temporal_policy_id,
                    "duration_ms": result.snapshot.duration_ms,
                    "scope_fingerprint": scope_fingerprint,
                },
                sort_keys=True,
            ),
        )


__all__ = ["MemoryDynamicsEngine"]
