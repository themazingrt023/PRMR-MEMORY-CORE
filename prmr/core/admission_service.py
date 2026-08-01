"""Durable controlled admission of candidate memories into the existing event ledger."""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from typing import Any

from .admission_bridge import CandidateToEventBridge
from .admission_models import (
    ADMISSION_BRIDGE_REVISION,
    ADMISSION_INTEGRITY_REVISION,
    ADMISSION_POLICY_REVISION,
    ADMISSION_SCHEMA_REVISION,
    ADMITTED_EVENT_METADATA_REVISION,
    CANDIDATE_CORRECTION_REVISION,
    AdmissionDecisionActor,
    AdmissionDecisionStatus,
    AdmissionDecisionType,
    AdmissionIntegrityResult,
    AdmissionPage,
    AdmissionResult,
    AdmittedMemoryLink,
    MemoryAdmissionDecision,
    MemoryAdmissionError,
    PolicyAdmissionResult,
)
from .admission_policy import (
    MANUAL_STRICT_V1,
    SAFE_EXPLICIT_AUTO_V1,
    admission_policy,
)
from .candidate_engine import CandidateMemoryEngine
from .candidate_evidence import evidence_manifest_hash, evidence_text_from_source, materialize_evidence
from .candidate_integrity import candidate_fingerprint
from .candidate_models import (
    CANDIDATE_SCHEMA_REVISION,
    CandidateEngineError,
    CandidateMemory,
    CandidateStatus,
    EVENT_TYPE_PATTERN,
    ExtractionRunStatus,
)
from .candidate_rules import EvidenceSpec, RuleMatch
from .source_integrity import canonical_json, sha256_text
from .source_ledger import POSTGRES_SCHEMA, SourceLedger, utc_now
from .source_models import AuthenticatedScope, SourceLedgerError, SourceRecord, SourceSegment


LOGGER = logging.getLogger("prmr.core.admission")
ADMISSION_TABLE = "prmr_memory_admission_decisions"
LINK_TABLE = "prmr_admitted_memory_links"


SQLITE_ADMISSION_SCHEMA = """
CREATE TABLE IF NOT EXISTS prmr_admission_schema_migrations (
    revision TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS prmr_memory_admission_decisions (
    admission_id TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL,
    extraction_run_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    application_reference TEXT,
    actor_reference TEXT,
    workspace_reference TEXT,
    entity_references_json TEXT NOT NULL,
    session_reference TEXT,
    decision_type TEXT NOT NULL,
    decision_status TEXT NOT NULL,
    decision_actor_type TEXT NOT NULL,
    decision_actor_reference TEXT NOT NULL,
    decision_reason TEXT NOT NULL,
    decision_metadata_json TEXT NOT NULL,
    admission_policy_id TEXT NOT NULL,
    admission_policy_revision TEXT NOT NULL,
    admission_schema_revision TEXT NOT NULL,
    admission_bridge_revision TEXT NOT NULL,
    candidate_fingerprint_sha256 TEXT NOT NULL,
    candidate_evidence_manifest_hash_sha256 TEXT NOT NULL,
    source_content_hash_sha256 TEXT NOT NULL,
    source_segment_manifest_hash_sha256 TEXT NOT NULL,
    admitted_event_id TEXT,
    replacement_candidate_id TEXT,
    decision_idempotency_digest TEXT NOT NULL,
    decided_at TEXT NOT NULL,
    completed_at TEXT,
    duration_ms REAL NOT NULL,
    error_code TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(client_id, vault_id, namespace, decision_idempotency_digest),
    FOREIGN KEY(candidate_id) REFERENCES prmr_candidate_memories(candidate_id) ON DELETE CASCADE,
    FOREIGN KEY(extraction_run_id) REFERENCES prmr_candidate_extraction_runs(extraction_run_id) ON DELETE CASCADE,
    FOREIGN KEY(source_id) REFERENCES prmr_sources(source_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS prmr_admitted_memory_links (
    admitted_memory_link_id TEXT PRIMARY KEY,
    admission_id TEXT NOT NULL UNIQUE,
    candidate_id TEXT NOT NULL UNIQUE,
    extraction_run_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    admitted_event_id TEXT NOT NULL UNIQUE,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    application_reference TEXT,
    actor_reference TEXT,
    workspace_reference TEXT,
    entity_references_json TEXT NOT NULL,
    session_reference TEXT,
    epistemic_status TEXT NOT NULL,
    proposed_event_type TEXT NOT NULL,
    candidate_fingerprint_sha256 TEXT NOT NULL,
    source_content_hash_sha256 TEXT NOT NULL,
    evidence_manifest_hash_sha256 TEXT NOT NULL,
    admission_policy_revision TEXT NOT NULL,
    admission_bridge_revision TEXT NOT NULL,
    admitted_event_metadata_revision TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(admission_id) REFERENCES prmr_memory_admission_decisions(admission_id),
    FOREIGN KEY(candidate_id) REFERENCES prmr_candidate_memories(candidate_id),
    FOREIGN KEY(extraction_run_id) REFERENCES prmr_candidate_extraction_runs(extraction_run_id),
    FOREIGN KEY(source_id) REFERENCES prmr_sources(source_id)
);
CREATE INDEX IF NOT EXISTS prmr_admissions_candidate_idx ON prmr_memory_admission_decisions(candidate_id);
CREATE INDEX IF NOT EXISTS prmr_admissions_source_idx ON prmr_memory_admission_decisions(source_id);
CREATE INDEX IF NOT EXISTS prmr_admissions_run_idx ON prmr_memory_admission_decisions(extraction_run_id);
CREATE INDEX IF NOT EXISTS prmr_admissions_type_idx ON prmr_memory_admission_decisions(decision_type);
CREATE INDEX IF NOT EXISTS prmr_admissions_status_idx ON prmr_memory_admission_decisions(decision_status);
CREATE INDEX IF NOT EXISTS prmr_admissions_scope_idx ON prmr_memory_admission_decisions(client_id, vault_id, namespace);
CREATE INDEX IF NOT EXISTS prmr_admissions_decided_idx ON prmr_memory_admission_decisions(decided_at);
CREATE INDEX IF NOT EXISTS prmr_links_source_idx ON prmr_admitted_memory_links(source_id);
CREATE INDEX IF NOT EXISTS prmr_links_scope_idx ON prmr_admitted_memory_links(client_id, vault_id, namespace);
"""


def _safe_log(event: str, **fields: Any) -> None:
    allowed = {
        "admission_id", "candidate_id", "source_id", "extraction_run_id",
        "admitted_event_id", "decision_type", "decision_actor_type",
        "epistemic_status", "policy_id", "duration_ms", "error_code",
        "admission_schema_revision", "admission_policy_revision",
        "admission_bridge_revision", "client_id", "vault_id", "namespace",
        "accepted_count", "skipped_count", "failed_count",
    }
    LOGGER.info(
        "%s",
        json.dumps(
            {"event": event, **{key: value for key, value in fields.items() if key in allowed}},
            sort_keys=True,
            separators=(",", ":"),
        ),
    )


def initialize_sqlite_admission_schema(connection: sqlite3.Connection) -> None:
    columns = {str(row["name"]) for row in connection.execute("PRAGMA table_info(prmr_candidate_memories)")}
    additions = {
        "corrected_from_candidate_id": "TEXT",
        "replacement_candidate_id": "TEXT",
        "current_admission_state": "TEXT NOT NULL DEFAULT 'pending_review'",
        "accepted_admission_id": "TEXT",
        "accepted_event_id": "TEXT",
        "candidate_correction_revision": "TEXT",
    }
    for name, declaration in additions.items():
        if name not in columns:
            connection.execute(f"ALTER TABLE prmr_candidate_memories ADD COLUMN {name} {declaration}")
    connection.executescript(SQLITE_ADMISSION_SCHEMA)
    connection.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS prmr_candidates_replacement_unique_idx "
        "ON prmr_candidate_memories(replacement_candidate_id) WHERE replacement_candidate_id IS NOT NULL"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS prmr_candidates_corrected_from_idx "
        "ON prmr_candidate_memories(corrected_from_candidate_id)"
    )
    connection.execute(
        "INSERT OR IGNORE INTO prmr_admission_schema_migrations(revision, applied_at) VALUES (?, ?)",
        (ADMISSION_SCHEMA_REVISION, utc_now()),
    )


def initialize_postgres_admission_schema(connection: Any) -> None:
    cursor = connection.cursor()
    cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {POSTGRES_SCHEMA}")
    for name, declaration in {
        "corrected_from_candidate_id": "TEXT",
        "replacement_candidate_id": "TEXT",
        "current_admission_state": "TEXT NOT NULL DEFAULT 'pending_review'",
        "accepted_admission_id": "TEXT",
        "accepted_event_id": "TEXT",
        "candidate_correction_revision": "TEXT",
    }.items():
        cursor.execute(
            f"ALTER TABLE {POSTGRES_SCHEMA}.prmr_candidate_memories "
            f"ADD COLUMN IF NOT EXISTS {name} {declaration}"
        )
    cursor.execute(
        f"CREATE TABLE IF NOT EXISTS {POSTGRES_SCHEMA}.prmr_admission_schema_migrations "
        "(revision TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {POSTGRES_SCHEMA}.{ADMISSION_TABLE} (
            admission_id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL REFERENCES {POSTGRES_SCHEMA}.prmr_candidate_memories(candidate_id) ON DELETE CASCADE,
            extraction_run_id TEXT NOT NULL REFERENCES {POSTGRES_SCHEMA}.prmr_candidate_extraction_runs(extraction_run_id) ON DELETE CASCADE,
            source_id TEXT NOT NULL REFERENCES {POSTGRES_SCHEMA}.prmr_sources(source_id) ON DELETE CASCADE,
            client_id TEXT NOT NULL, vault_id TEXT NOT NULL, namespace TEXT NOT NULL,
            application_reference TEXT, actor_reference TEXT, workspace_reference TEXT,
            entity_references_json JSONB NOT NULL, session_reference TEXT,
            decision_type TEXT NOT NULL, decision_status TEXT NOT NULL,
            decision_actor_type TEXT NOT NULL, decision_actor_reference TEXT NOT NULL,
            decision_reason TEXT NOT NULL, decision_metadata_json JSONB NOT NULL,
            admission_policy_id TEXT NOT NULL, admission_policy_revision TEXT NOT NULL,
            admission_schema_revision TEXT NOT NULL, admission_bridge_revision TEXT NOT NULL,
            candidate_fingerprint_sha256 TEXT NOT NULL,
            candidate_evidence_manifest_hash_sha256 TEXT NOT NULL,
            source_content_hash_sha256 TEXT NOT NULL,
            source_segment_manifest_hash_sha256 TEXT NOT NULL,
            admitted_event_id TEXT, replacement_candidate_id TEXT,
            decision_idempotency_digest TEXT NOT NULL,
            decided_at TEXT NOT NULL, completed_at TEXT, duration_ms DOUBLE PRECISION NOT NULL,
            error_code TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            UNIQUE(client_id, vault_id, namespace, decision_idempotency_digest)
        )
        """
    )
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {POSTGRES_SCHEMA}.{LINK_TABLE} (
            admitted_memory_link_id TEXT PRIMARY KEY,
            admission_id TEXT NOT NULL UNIQUE REFERENCES {POSTGRES_SCHEMA}.{ADMISSION_TABLE}(admission_id),
            candidate_id TEXT NOT NULL UNIQUE REFERENCES {POSTGRES_SCHEMA}.prmr_candidate_memories(candidate_id),
            extraction_run_id TEXT NOT NULL REFERENCES {POSTGRES_SCHEMA}.prmr_candidate_extraction_runs(extraction_run_id),
            source_id TEXT NOT NULL REFERENCES {POSTGRES_SCHEMA}.prmr_sources(source_id),
            admitted_event_id TEXT NOT NULL UNIQUE,
            client_id TEXT NOT NULL, vault_id TEXT NOT NULL, namespace TEXT NOT NULL,
            application_reference TEXT, actor_reference TEXT, workspace_reference TEXT,
            entity_references_json JSONB NOT NULL, session_reference TEXT,
            epistemic_status TEXT NOT NULL, proposed_event_type TEXT NOT NULL,
            candidate_fingerprint_sha256 TEXT NOT NULL,
            source_content_hash_sha256 TEXT NOT NULL,
            evidence_manifest_hash_sha256 TEXT NOT NULL,
            admission_policy_revision TEXT NOT NULL,
            admission_bridge_revision TEXT NOT NULL,
            admitted_event_metadata_revision TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    indexes = (
        ("prmr_admissions_candidate_idx", f"{POSTGRES_SCHEMA}.{ADMISSION_TABLE}(candidate_id)"),
        ("prmr_admissions_source_idx", f"{POSTGRES_SCHEMA}.{ADMISSION_TABLE}(source_id)"),
        ("prmr_admissions_run_idx", f"{POSTGRES_SCHEMA}.{ADMISSION_TABLE}(extraction_run_id)"),
        ("prmr_admissions_type_idx", f"{POSTGRES_SCHEMA}.{ADMISSION_TABLE}(decision_type)"),
        ("prmr_admissions_status_idx", f"{POSTGRES_SCHEMA}.{ADMISSION_TABLE}(decision_status)"),
        ("prmr_admissions_scope_idx", f"{POSTGRES_SCHEMA}.{ADMISSION_TABLE}(client_id, vault_id, namespace)"),
        ("prmr_admissions_decided_idx", f"{POSTGRES_SCHEMA}.{ADMISSION_TABLE}(decided_at)"),
        ("prmr_links_source_idx", f"{POSTGRES_SCHEMA}.{LINK_TABLE}(source_id)"),
        ("prmr_links_scope_idx", f"{POSTGRES_SCHEMA}.{LINK_TABLE}(client_id, vault_id, namespace)"),
        ("prmr_candidates_corrected_from_idx", f"{POSTGRES_SCHEMA}.prmr_candidate_memories(corrected_from_candidate_id)"),
    )
    for name, expression in indexes:
        cursor.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {expression}")
    cursor.execute(
        f"CREATE UNIQUE INDEX IF NOT EXISTS prmr_candidates_replacement_unique_idx "
        f"ON {POSTGRES_SCHEMA}.prmr_candidate_memories(replacement_candidate_id) "
        "WHERE replacement_candidate_id IS NOT NULL"
    )
    cursor.execute(
        f"INSERT INTO {POSTGRES_SCHEMA}.prmr_admission_schema_migrations(revision, applied_at) "
        "VALUES (%s, %s) ON CONFLICT(revision) DO NOTHING",
        (ADMISSION_SCHEMA_REVISION, utc_now()),
    )


class MemoryAdmissionService:
    """Append-oriented admission decisions and atomic candidate-to-event bridge."""

    def __init__(self, repository: Any, *, initialize: bool = True) -> None:
        self.repository = repository
        self.backend = str(getattr(repository, "backend_name", "sqlite"))
        self.candidates = CandidateMemoryEngine(repository, initialize=initialize)
        self.sources = SourceLedger(repository, initialize=initialize)
        self.bridge = CandidateToEventBridge()
        prefix = f"{POSTGRES_SCHEMA}." if self.backend == "postgres" else ""
        self.admission_table = prefix + ADMISSION_TABLE
        self.link_table = prefix + LINK_TABLE
        self.candidate_table = prefix + "prmr_candidate_memories"
        self.events_table = prefix + "events"
        self.packets_table = prefix + "packets"
        if initialize:
            with repository.connect() as connection:
                if self.backend == "postgres":
                    initialize_postgres_admission_schema(connection)
                else:
                    initialize_sqlite_admission_schema(connection)

    def accept_candidate(
        self,
        authenticated_scope: AuthenticatedScope,
        candidate_id: str,
        decision_actor: AdmissionDecisionActor,
        reason: str,
        idempotency_key: str,
        admission_policy_id: str = MANUAL_STRICT_V1,
        *,
        frozen_decision_time: str | None = None,
    ) -> AdmissionResult:
        started = time.perf_counter()
        decision_actor.validate()
        policy = admission_policy(admission_policy_id)
        _safe_log(
            "memory_admission_started",
            candidate_id=candidate_id,
            decision_type="accept",
            decision_actor_type=decision_actor.actor_type,
            policy_id=policy.policy_id,
            client_id=authenticated_scope.client_id,
            vault_id=authenticated_scope.vault_id,
            namespace=authenticated_scope.namespace,
        )
        existing_link = self._link_for_candidate(authenticated_scope, candidate_id)
        if existing_link:
            return self._accepted_replay(authenticated_scope, existing_link)
        candidate, source, run, evidence, segments, candidate_order = self._validate_for_admission(
            authenticated_scope, candidate_id
        )
        if candidate.candidate_status == CandidateStatus.ACCEPTED.value:
            existing_link = self._link_for_candidate(
                authenticated_scope, candidate_id
            )
            if existing_link:
                return self._accepted_replay(
                    authenticated_scope, existing_link
                )
        if candidate.candidate_status == CandidateStatus.REJECTED.value:
            raise MemoryAdmissionError("ADMISSION_ALREADY_REJECTED", "Rejected candidate cannot be accepted in V1.")
        if candidate.candidate_status not in {
            CandidateStatus.PENDING_REVIEW.value,
            CandidateStatus.DEFERRED.value,
        }:
            raise MemoryAdmissionError("ADMISSION_CANDIDATE_STATE_INVALID", "Candidate state is not admissible.")
        safe_reason = self._safe_reason(reason)
        digest = self._idempotency_digest(idempotency_key, AdmissionDecisionType.ACCEPT.value)
        replay = self._decision_by_digest(authenticated_scope, digest)
        if replay:
            if replay.candidate_id != candidate_id or replay.decision_type != AdmissionDecisionType.ACCEPT.value:
                raise MemoryAdmissionError("ADMISSION_IDEMPOTENCY_CONFLICT", "Admission idempotency key conflicts.")
            link = self._link_for_admission(authenticated_scope, replay.admission_id)
            return AdmissionResult(replay, link, self.get_admitted_event(authenticated_scope, replay.admitted_event_id or ""), True)
        admission_id = self._admission_id(candidate_id, AdmissionDecisionType.ACCEPT.value, digest)
        event_id = self.bridge.deterministic_event_id(authenticated_scope, candidate)
        link_id = self.bridge.deterministic_link_id(candidate_id, event_id)
        event = self.bridge.build_event(
            scope=authenticated_scope,
            candidate=candidate,
            source=source,
            evidence=evidence,
            segments=segments,
            admission_id=admission_id,
            admitted_memory_link_id=link_id,
            candidate_order=candidate_order,
        )
        if frozen_decision_time is not None:
            from .entity_store import utc as normalise_utc

            now = normalise_utc(frozen_decision_time)
        else:
            now = utc_now()
        decision = self._decision(
            admission_id=admission_id,
            candidate=candidate,
            source=source,
            decision_type=AdmissionDecisionType.ACCEPT.value,
            actor=decision_actor,
            reason=safe_reason,
            metadata={"automatic": policy.automatic, "truth_status_promoted": False},
            policy_id=policy.policy_id,
            digest=digest,
            admitted_event_id=event_id,
            replacement_candidate_id=None,
            status=AdmissionDecisionStatus.COMPLETED.value,
            started_at=now,
            completed_at=now if frozen_decision_time is not None else None,
            duration_ms=round((time.perf_counter() - started) * 1000, 3),
        )
        link = self._link(link_id, decision, candidate, source, event_id)
        try:
            with self.repository.connect() as connection:
                self._begin(connection)
                locked = self._candidate_row(connection, candidate_id, authenticated_scope, lock=True)
                if str(locked["candidate_status"]) == CandidateStatus.ACCEPTED.value:
                    raise sqlite3.IntegrityError("candidate already accepted")
                self._insert_decision(connection, decision)
                self._insert_event(connection, authenticated_scope, event)
                self._insert_link(connection, link)
                connection.execute(
                    f"UPDATE {self.candidate_table} SET candidate_status={self._placeholder}, "
                    f"current_admission_state={self._placeholder}, accepted_admission_id={self._placeholder}, "
                    f"accepted_event_id={self._placeholder}, updated_at={self._placeholder} "
                    f"WHERE candidate_id={self._placeholder}",
                    (
                        CandidateStatus.ACCEPTED.value,
                        CandidateStatus.ACCEPTED.value,
                        admission_id,
                        event_id,
                        now,
                        candidate_id,
                    ),
                )
        except Exception as exc:
            existing = self._link_for_candidate(authenticated_scope, candidate_id)
            if existing:
                return self._accepted_replay(authenticated_scope, existing)
            _safe_log(
                "memory_admission_failed",
                candidate_id=candidate_id,
                error_code="ADMISSION_TRANSACTION_FAILED",
            )
            raise MemoryAdmissionError(
                "ADMISSION_TRANSACTION_FAILED",
                "Admission transaction failed without persisting partial memory.",
                retryable=True,
            ) from exc
        _safe_log(
            "memory_admission_completed",
            admission_id=admission_id,
            candidate_id=candidate_id,
            source_id=source.source_id,
            extraction_run_id=run.extraction_run_id,
            admitted_event_id=event_id,
            decision_type="accept",
            epistemic_status=candidate.epistemic_status,
            duration_ms=decision.duration_ms,
            admission_schema_revision=ADMISSION_SCHEMA_REVISION,
            admission_policy_revision=ADMISSION_POLICY_REVISION,
            admission_bridge_revision=ADMISSION_BRIDGE_REVISION,
        )
        _safe_log("memory_event_created", admission_id=admission_id, candidate_id=candidate_id, admitted_event_id=event_id)
        return AdmissionResult(decision, link, event, False)

    def reject_candidate(
        self,
        authenticated_scope: AuthenticatedScope,
        candidate_id: str,
        decision_actor: AdmissionDecisionActor,
        reason: str,
        idempotency_key: str,
    ) -> AdmissionResult:
        candidate = self._get_candidate(authenticated_scope, candidate_id)
        if candidate.candidate_status == CandidateStatus.ACCEPTED.value:
            raise MemoryAdmissionError("ADMISSION_ALREADY_ACCEPTED", "Accepted candidate cannot be rejected.")
        if candidate.candidate_status == CandidateStatus.REJECTED.value:
            prior = self._latest_decision(authenticated_scope, candidate_id, AdmissionDecisionType.REJECT.value)
            if prior:
                return AdmissionResult(prior, None, None, True)
        if candidate.candidate_status not in {CandidateStatus.PENDING_REVIEW.value, CandidateStatus.DEFERRED.value}:
            raise MemoryAdmissionError("ADMISSION_CANDIDATE_STATE_INVALID", "Candidate cannot be rejected from this state.")
        return self._non_event_decision(
            authenticated_scope, candidate, decision_actor, reason, idempotency_key,
            decision_type=AdmissionDecisionType.REJECT.value,
            target_status=CandidateStatus.REJECTED.value,
            metadata={},
        )

    def defer_candidate(
        self,
        authenticated_scope: AuthenticatedScope,
        candidate_id: str,
        decision_actor: AdmissionDecisionActor,
        reason: str,
        idempotency_key: str,
        review_after: str | None = None,
    ) -> AdmissionResult:
        candidate = self._get_candidate(authenticated_scope, candidate_id)
        if candidate.candidate_status == CandidateStatus.ACCEPTED.value:
            raise MemoryAdmissionError("ADMISSION_ALREADY_ACCEPTED", "Accepted candidate cannot be deferred.")
        if candidate.candidate_status == CandidateStatus.DEFERRED.value:
            prior = self._latest_decision(authenticated_scope, candidate_id, AdmissionDecisionType.DEFER.value)
            if prior:
                return AdmissionResult(prior, None, None, True)
        if candidate.candidate_status != CandidateStatus.PENDING_REVIEW.value:
            raise MemoryAdmissionError("ADMISSION_CANDIDATE_STATE_INVALID", "Candidate cannot be deferred from this state.")
        return self._non_event_decision(
            authenticated_scope, candidate, decision_actor, reason, idempotency_key,
            decision_type=AdmissionDecisionType.DEFER.value,
            target_status=CandidateStatus.DEFERRED.value,
            metadata={"review_after": review_after, "scheduler_claimed": False},
        )

    def correct_candidate(
        self,
        authenticated_scope: AuthenticatedScope,
        candidate_id: str,
        *,
        correction_reason: str,
        decision_actor: AdmissionDecisionActor,
        idempotency_key: str,
        corrected_event_type: str | None = None,
        corrected_signal: str | None = None,
        corrected_occurred_at: str | None = None,
        corrected_epistemic_status: str | None = None,
    ) -> AdmissionResult:
        started = time.perf_counter()
        decision_actor.validate()
        original = self._get_candidate(authenticated_scope, candidate_id)
        if original.candidate_status == CandidateStatus.ACCEPTED.value:
            raise MemoryAdmissionError(
                "ADMISSION_ACCEPTED_CANDIDATE_REQUIRES_SUPERSESSION",
                "Accepted memory correction requires a later supersession mechanism.",
            )
        if original.candidate_status == CandidateStatus.CORRECTED.value:
            prior = self._latest_decision(authenticated_scope, candidate_id, AdmissionDecisionType.CORRECT.value)
            if prior and prior.replacement_candidate_id:
                replacement = self.candidates.get_candidate(authenticated_scope, prior.replacement_candidate_id)
                return AdmissionResult(prior, None, {"replacement_candidate": replacement.to_dict()}, True)
            raise MemoryAdmissionError("ADMISSION_CORRECTION_INVALID", "Corrected candidate cannot be corrected again.")
        if original.candidate_status not in {
            CandidateStatus.PENDING_REVIEW.value,
            CandidateStatus.DEFERRED.value,
            CandidateStatus.REJECTED.value,
        }:
            raise MemoryAdmissionError("ADMISSION_CORRECTION_INVALID", "Candidate state cannot be corrected.")
        source = self.sources.get_source(authenticated_scope, original.source_id)
        integrity = self.candidates.verify_extraction_integrity(
            authenticated_scope, original.extraction_run_id
        )
        if not integrity.verified:
            raise MemoryAdmissionError(
                "ADMISSION_EXTRACTION_INTEGRITY_FAILED",
                "Candidate extraction integrity failed before correction.",
            )
        evidence = self.candidates.get_candidate_evidence(authenticated_scope, candidate_id)
        segments = {
            item.segment_id: item
            for item in self._all_segments(authenticated_scope, source.source_id)
        }
        specs = self._evidence_specs(source, evidence, segments)
        event_type = corrected_event_type or original.proposed_event_type
        signal = corrected_signal if corrected_signal is not None else original.proposed_signal
        occurred_at = (
            corrected_occurred_at
            if corrected_occurred_at is not None
            else original.proposed_occurred_at
        )
        epistemic = corrected_epistemic_status or original.epistemic_status
        if not event_type or not EVENT_TYPE_PATTERN.fullmatch(event_type):
            raise MemoryAdmissionError("ADMISSION_EVENT_TYPE_INVALID", "Corrected event type is invalid.")
        if not signal.strip() or len(signal) > 1_200:
            raise MemoryAdmissionError("ADMISSION_SIGNAL_INVALID", "Corrected signal is invalid.")
        allowed_downgrades = {
            ("explicit", "inferred"),
            ("explicit", "unknown"),
            ("derived", "inferred"),
            ("inferred", "unknown"),
        }
        if epistemic != original.epistemic_status and (
            original.epistemic_status,
            epistemic,
        ) not in allowed_downgrades:
            raise MemoryAdmissionError(
                "ADMISSION_EPISTEMIC_UPGRADE_REQUIRES_NEW_EVIDENCE",
                "The requested epistemic change requires stronger evidence.",
            )
        supported_texts = [spec.text for spec in specs]
        label_stripped = [
            rema
            for text in supported_texts
            for rema in [text.split(":", 1)[1].strip() if ":" in text else text]
        ]
        if signal not in supported_texts and signal not in label_stripped and signal != original.proposed_signal:
            raise MemoryAdmissionError(
                "ADMISSION_CORRECTION_INVALID",
                "Corrected signal is not supported by the existing evidence.",
            )
        digest = self._idempotency_digest(idempotency_key, AdmissionDecisionType.CORRECT.value)
        replay = self._decision_by_digest(authenticated_scope, digest)
        if replay:
            if replay.candidate_id != candidate_id or replay.decision_type != "correct":
                raise MemoryAdmissionError("ADMISSION_IDEMPOTENCY_CONFLICT", "Correction idempotency key conflicts.")
            replacement = self.candidates.get_candidate(
                authenticated_scope, replay.replacement_candidate_id or ""
            )
            return AdmissionResult(replay, None, {"replacement_candidate": replacement.to_dict()}, True)
        match = RuleMatch(
            proposed_event_type=event_type,
            proposed_signal=signal,
            proposed_occurred_at=occurred_at,
            epistemic_status=epistemic,
            extraction_confidence=original.extraction_confidence,
            confidence_basis=original.confidence_basis,
            extraction_method=original.extraction_method,
            rule_id="rule.correction.v1",
            priority=0,
            evidence=specs,
            normalisation_details=original.normalisation_details,
        )
        fingerprint = candidate_fingerprint(
            source_id=source.source_id,
            match=match,
            evidence=specs,
            candidate_rule_revision=original.candidate_rule_revision,
            candidate_extractor_revision=original.candidate_extractor_revision,
        )
        if fingerprint == original.candidate_fingerprint_sha256:
            raise MemoryAdmissionError(
                "ADMISSION_CORRECTION_INVALID",
                "Correction must change at least one candidate memory field.",
            )
        replacement_id = f"cand_{sha256_text(canonical_json({'corrected_from': candidate_id, 'fingerprint': fingerprint}))[:24]}"
        now = utc_now()
        replacement = CandidateMemory(
            **{
                **original.to_dict(),
                "candidate_id": replacement_id,
                "proposed_event_type": event_type,
                "proposed_signal": signal,
                "proposed_occurred_at": occurred_at,
                "epistemic_status": epistemic,
                "primary_rule_id": "rule.correction.v1",
                "matched_rule_ids": sorted(set(original.matched_rule_ids + ["rule.correction.v1"])),
                "duplicate_match_count": 0,
                "candidate_status": CandidateStatus.PENDING_REVIEW.value,
                "candidate_fingerprint_sha256": fingerprint,
                "evidence_manifest_hash_sha256": evidence_manifest_hash(specs),
                "normalisation_details": {
                    **original.normalisation_details,
                    "corrected_from_candidate_id": original.candidate_id,
                    "candidate_correction_revision": CANDIDATE_CORRECTION_REVISION,
                    "correction_changes": {
                        "event_type": event_type != original.proposed_event_type,
                        "signal": signal != original.proposed_signal,
                        "occurred_at": occurred_at != original.proposed_occurred_at,
                        "epistemic_status": epistemic != original.epistemic_status,
                    },
                },
                "created_at": now,
                "updated_at": now,
                "corrected_from_candidate_id": original.candidate_id,
                "replacement_candidate_id": None,
                "current_admission_state": CandidateStatus.PENDING_REVIEW.value,
                "accepted_admission_id": None,
                "accepted_event_id": None,
                "candidate_correction_revision": CANDIDATE_CORRECTION_REVISION,
            }
        )
        replacement_evidence = materialize_evidence(
            candidate_id=replacement_id,
            source=source,
            segment_by_id=segments,
            specs=specs,
            extraction_rule_id="rule.correction.v1",
            created_at=now,
        )
        admission_id = self._admission_id(candidate_id, "correct", digest)
        decision = self._decision(
            admission_id=admission_id,
            candidate=original,
            source=source,
            decision_type="correct",
            actor=decision_actor,
            reason=self._safe_reason(correction_reason),
            metadata={
                "candidate_correction_revision": CANDIDATE_CORRECTION_REVISION,
                "event_created": False,
            },
            policy_id=MANUAL_STRICT_V1,
            digest=digest,
            admitted_event_id=None,
            replacement_candidate_id=replacement_id,
            status=AdmissionDecisionStatus.COMPLETED.value,
            started_at=now,
            duration_ms=round((time.perf_counter() - started) * 1000, 3),
        )
        try:
            with self.repository.connect() as connection:
                self._begin(connection)
                self._candidate_row(connection, candidate_id, authenticated_scope, lock=True)
                self._insert_decision(connection, decision)
                self._insert_replacement_candidate(connection, replacement)
                self.candidates._insert_evidence(connection, replacement_evidence)
                connection.execute(
                    f"UPDATE {self.candidate_table} SET candidate_status={self._placeholder}, "
                    f"current_admission_state={self._placeholder}, replacement_candidate_id={self._placeholder}, "
                    f"candidate_correction_revision={self._placeholder}, updated_at={self._placeholder} "
                    f"WHERE candidate_id={self._placeholder}",
                    (
                        CandidateStatus.CORRECTED.value,
                        CandidateStatus.CORRECTED.value,
                        replacement_id,
                        CANDIDATE_CORRECTION_REVISION,
                        now,
                        candidate_id,
                    ),
                )
        except Exception as exc:
            replay = self._latest_decision(authenticated_scope, candidate_id, "correct")
            if replay and replay.replacement_candidate_id:
                replacement = self.candidates.get_candidate(
                    authenticated_scope, replay.replacement_candidate_id
                )
                return AdmissionResult(replay, None, {"replacement_candidate": replacement.to_dict()}, True)
            raise MemoryAdmissionError(
                "ADMISSION_TRANSACTION_FAILED",
                "Correction transaction failed without partial persistence.",
                retryable=True,
            ) from exc
        _safe_log(
            "memory_candidate_corrected",
            admission_id=admission_id,
            candidate_id=candidate_id,
            source_id=source.source_id,
            decision_type="correct",
            duration_ms=decision.duration_ms,
        )
        return AdmissionResult(
            decision, None, {"replacement_candidate": replacement.to_dict()}, False
        )

    def run_admission_policy(
        self,
        authenticated_scope: AuthenticatedScope,
        *,
        source_id: str | None = None,
        extraction_run_id: str | None = None,
        policy_id: str = SAFE_EXPLICIT_AUTO_V1,
    ) -> PolicyAdmissionResult:
        policy = admission_policy(policy_id)
        if not policy.automatic:
            raise MemoryAdmissionError(
                "ADMISSION_POLICY_INVALID",
                "Manual policy cannot be run as automatic admission.",
            )
        _safe_log("memory_policy_started", policy_id=policy_id)
        candidates = self.candidates.list_candidates(
            authenticated_scope,
            source_id=source_id,
            extraction_run_id=extraction_run_id,
            candidate_status=CandidateStatus.PENDING_REVIEW.value,
            limit=5_000,
        ).items
        candidates = sorted(
            candidates,
            key=lambda item: (
                item.source_id,
                item.extraction_run_id,
                item.candidate_id,
            ),
        )
        accepted: list[str] = []
        skipped: list[str] = []
        failures: list[dict[str, str]] = []
        for candidate in candidates:
            try:
                source = self.sources.get_source(authenticated_scope, candidate.source_id)
                eligible, _ = policy.auto_eligible(
                    candidate, source_retention=source.retention_policy
                )
                if not eligible:
                    skipped.append(candidate.candidate_id)
                    continue
                result = self.accept_candidate(
                    authenticated_scope,
                    candidate.candidate_id,
                    AdmissionDecisionActor("engine_policy", "safe_explicit_auto_v1"),
                    "Accepted by conservative allowlisted automatic admission policy.",
                    f"policy:{policy.admission_policy_revision}:{candidate.candidate_id}",
                    admission_policy_id=policy_id,
                )
                if result.admitted_event:
                    accepted.append(str(result.admitted_event["event_id"]))
            except MemoryAdmissionError as exc:
                failures.append({"candidate_id": candidate.candidate_id, "error_code": exc.code})
        result = PolicyAdmissionResult(
            policy_id=policy_id,
            inspected_count=len(candidates),
            accepted_count=len(accepted),
            skipped_count=len(skipped),
            failed_count=len(failures),
            admitted_event_ids=accepted,
            skipped_candidate_ids=skipped,
            failures=failures,
        )
        _safe_log(
            "memory_policy_completed",
            policy_id=policy_id,
            accepted_count=result.accepted_count,
            skipped_count=result.skipped_count,
            failed_count=result.failed_count,
        )
        return result

    def get_admission(
        self,
        authenticated_scope: AuthenticatedScope,
        admission_id: str,
    ) -> MemoryAdmissionDecision:
        with self.repository.connect() as connection:
            row = connection.execute(
                f"SELECT * FROM {self.admission_table} "
                f"WHERE admission_id={self._placeholder} "
                f"AND client_id={self._placeholder} AND vault_id={self._placeholder} "
                f"AND namespace={self._placeholder}",
                (admission_id, *authenticated_scope.memory_boundary()),
            ).fetchone()
        if not row:
            raise MemoryAdmissionError(
                "ADMISSION_NOT_FOUND",
                "Admission was not found in the authenticated scope.",
            )
        decision = self._decision_from_row(row)
        self._require_subject_access(authenticated_scope, decision)
        return decision

    def list_admissions(
        self,
        authenticated_scope: AuthenticatedScope,
        *,
        candidate_id: str | None = None,
        source_id: str | None = None,
        decision_type: str | None = None,
        cursor: str | None = None,
        limit: int = 100,
    ) -> AdmissionPage:
        try:
            offset = int(cursor or 0)
            safe_limit = int(limit)
        except (TypeError, ValueError) as exc:
            raise MemoryAdmissionError("ADMISSION_POLICY_INVALID", "Admission pagination is invalid.") from exc
        if offset < 0 or not 1 <= safe_limit <= 500:
            raise MemoryAdmissionError("ADMISSION_POLICY_INVALID", "Admission pagination is outside limits.")
        where = (
            f"client_id={self._placeholder} AND vault_id={self._placeholder} "
            f"AND namespace={self._placeholder}"
        )
        params: list[Any] = [*authenticated_scope.memory_boundary()]
        for field, value in (
            ("candidate_id", candidate_id),
            ("source_id", source_id),
            ("decision_type", decision_type),
        ):
            if value is not None:
                where += f" AND {field}={self._placeholder}"
                params.append(value)
        params.extend([safe_limit + 1, offset])
        with self.repository.connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM {self.admission_table} WHERE {where} "
                f"ORDER BY decided_at, admission_id LIMIT {self._placeholder} OFFSET {self._placeholder}",
                tuple(params),
            ).fetchall()
        decisions = [self._decision_from_row(row) for row in rows]
        decisions = [
            item for item in decisions if self._subject_access_allowed(authenticated_scope, item)
        ]
        return AdmissionPage(
            decisions[:safe_limit],
            str(offset + safe_limit) if len(decisions) > safe_limit else None,
        )

    def get_admitted_memory_link(
        self,
        authenticated_scope: AuthenticatedScope,
        admitted_event_id: str,
    ) -> AdmittedMemoryLink:
        with self.repository.connect() as connection:
            row = connection.execute(
                f"SELECT * FROM {self.link_table} "
                f"WHERE admitted_event_id={self._placeholder} "
                f"AND client_id={self._placeholder} AND vault_id={self._placeholder} "
                f"AND namespace={self._placeholder}",
                (admitted_event_id, *authenticated_scope.memory_boundary()),
            ).fetchone()
        if not row:
            raise MemoryAdmissionError(
                "ADMISSION_NOT_FOUND",
                "Admitted memory was not found in the authenticated scope.",
            )
        link = self._link_from_row(row)
        self._require_subject_access(authenticated_scope, link)
        return link

    def get_admitted_event(
        self,
        authenticated_scope: AuthenticatedScope,
        admitted_event_id: str,
    ) -> dict[str, Any]:
        events = self._events_for_scope(authenticated_scope)
        event = next(
            (item for item in events if str(item.get("event_id")) == admitted_event_id),
            None,
        )
        if event is None:
            raise MemoryAdmissionError(
                "ADMISSION_EVENT_NOT_FOUND",
                "Admitted event was not found in the authenticated scope.",
            )
        return event

    def build_continuity_packet(
        self,
        authenticated_scope: AuthenticatedScope,
        *,
        previous_packet: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.bridge.build_packet(
            authenticated_scope,
            self._events_for_scope(authenticated_scope),
            previous_packet=previous_packet,
        )

    def verify_admission_integrity(
        self,
        authenticated_scope: AuthenticatedScope,
        admission_id: str,
    ) -> AdmissionIntegrityResult:
        failures: list[str] = []
        checks: dict[str, bool] = {}
        try:
            decision = self.get_admission(authenticated_scope, admission_id)
            candidate = self.candidates.get_candidate(
                authenticated_scope, decision.candidate_id
            )
            source = self.sources.get_source(authenticated_scope, decision.source_id)
            run = self.candidates.get_extraction_run(
                authenticated_scope, decision.extraction_run_id
            )
            source_integrity = self.sources.verify_source_integrity(
                authenticated_scope, source.source_id
            )
            extraction_integrity = self.candidates.verify_extraction_integrity(
                authenticated_scope, run.extraction_run_id
            )
            checks.update(
                {
                    "decision_scope": decision.client_id == authenticated_scope.client_id
                    and decision.vault_id == authenticated_scope.vault_id
                    and decision.namespace == authenticated_scope.namespace,
                    "candidate_anchor": (
                        decision.candidate_fingerprint_sha256
                        == candidate.candidate_fingerprint_sha256
                    ),
                    "candidate_evidence_anchor": (
                        decision.candidate_evidence_manifest_hash_sha256
                        == candidate.evidence_manifest_hash_sha256
                    ),
                    "source_content_anchor": (
                        decision.source_content_hash_sha256 == source.content_hash_sha256
                    ),
                    "source_segment_anchor": (
                        decision.source_segment_manifest_hash_sha256
                        == source.segment_manifest_hash_sha256
                    ),
                    "source_integrity": source_integrity.verified,
                    "extraction_integrity": extraction_integrity.verified,
                    "revision_anchors": (
                        decision.admission_schema_revision == ADMISSION_SCHEMA_REVISION
                        and decision.admission_policy_revision == ADMISSION_POLICY_REVISION
                        and decision.admission_bridge_revision == ADMISSION_BRIDGE_REVISION
                    ),
                }
            )
            if decision.decision_type == AdmissionDecisionType.ACCEPT.value:
                link = self._link_for_admission(authenticated_scope, admission_id)
                event = (
                    self.get_admitted_event(
                        authenticated_scope, decision.admitted_event_id or ""
                    )
                    if decision.admitted_event_id
                    else None
                )
                metadata = (
                    dict((event or {}).get("external_metadata", {}).get("metadata", {}))
                    if event
                    else {}
                )
                expected_event_id = self.bridge.deterministic_event_id(
                    authenticated_scope, candidate
                )
                checks.update(
                    {
                        "accepted_link_exists": link is not None,
                        "accepted_event_exists": event is not None,
                        "accepted_event_identity": bool(
                            event
                            and link
                            and event.get("event_id") == expected_event_id
                            and link.admitted_event_id == expected_event_id
                            and decision.admitted_event_id == expected_event_id
                        ),
                        "accepted_event_content": bool(
                            event
                            and event.get("type") == candidate.proposed_event_type
                            and event.get("content") == candidate.proposed_signal
                        ),
                        "accepted_event_provenance": bool(
                            link
                            and metadata.get("candidate_id") == candidate.candidate_id
                            and metadata.get("source_id") == source.source_id
                            and metadata.get("admission_id") == decision.admission_id
                            and metadata.get("candidate_fingerprint_sha256")
                            == candidate.candidate_fingerprint_sha256
                            and metadata.get("epistemic_status")
                            == candidate.epistemic_status
                        ),
                        "candidate_acceptance_state": (
                            candidate.candidate_status == CandidateStatus.ACCEPTED.value
                            and candidate.accepted_admission_id == admission_id
                            and candidate.accepted_event_id == expected_event_id
                        ),
                    }
                )
            else:
                link = self._link_for_admission(authenticated_scope, admission_id)
                checks.update(
                    {
                        "non_accept_has_no_link": link is None,
                        "non_accept_has_no_event": decision.admitted_event_id is None,
                    }
                )
        except (MemoryAdmissionError, CandidateEngineError, SourceLedgerError):
            checks["records_resolve"] = False
        failures = [name for name, passed in checks.items() if not passed]
        result = AdmissionIntegrityResult(
            admission_id=admission_id,
            verified=not failures,
            checks=checks,
            failures=failures,
        )
        _safe_log(
            "memory_admission_integrity_verified"
            if result.verified
            else "memory_admission_integrity_failed",
            admission_id=admission_id,
            error_code=None if result.verified else "ADMISSION_INTEGRITY_FAILED",
        )
        return result

    def trace_admitted_memory_origin(
        self,
        authenticated_scope: AuthenticatedScope,
        admitted_event_id: str,
        *,
        include_evidence_preview: bool = False,
    ) -> dict[str, Any]:
        event = self.get_admitted_event(authenticated_scope, admitted_event_id)
        link = self.get_admitted_memory_link(authenticated_scope, admitted_event_id)
        decision = self.get_admission(authenticated_scope, link.admission_id)
        candidate = self.candidates.get_candidate(
            authenticated_scope, link.candidate_id
        )
        run = self.candidates.get_extraction_run(
            authenticated_scope, link.extraction_run_id
        )
        source = self.sources.get_source(authenticated_scope, link.source_id)
        evidence = self.candidates.get_candidate_evidence(
            authenticated_scope, candidate.candidate_id
        )
        segments = {
            item.segment_id: item
            for item in self._all_segments(authenticated_scope, source.source_id)
        }
        evidence_trace: list[dict[str, Any]] = []
        for item in evidence:
            segment = segments[item.segment_id]
            trace_item: dict[str, Any] = {
                "evidence_id": item.evidence_id,
                "segment_id": item.segment_id,
                "evidence_role": item.evidence_role,
                "sequence_index": item.sequence_index,
                "evidence_text_hash_sha256": item.evidence_text_hash_sha256,
                "segment_content_hash_sha256": item.segment_content_hash_sha256,
                "source_content_hash_sha256": item.source_content_hash_sha256,
                "source_start_offset": item.source_start_offset,
                "source_end_offset": item.source_end_offset,
                "segment_start_offset": item.segment_start_offset,
                "segment_end_offset": item.segment_end_offset,
                "json_pointer": item.json_pointer,
            }
            if include_evidence_preview:
                trace_item["evidence_preview"] = evidence_text_from_source(
                    source,
                    segment,
                    source_start_offset=item.source_start_offset,
                    source_end_offset=item.source_end_offset,
                    segment_start_offset=item.segment_start_offset,
                    segment_end_offset=item.segment_end_offset,
                    json_pointer=item.json_pointer,
                )[:240]
            evidence_trace.append(trace_item)
        return {
            "admitted_event_id": event["event_id"],
            "admitted_memory_link_id": link.admitted_memory_link_id,
            "admission_id": decision.admission_id,
            "candidate_id": candidate.candidate_id,
            "extraction_run_id": run.extraction_run_id,
            "source_id": source.source_id,
            "event_type": event["type"],
            "epistemic_status": link.epistemic_status,
            "source_hashes": {
                "content_hash_sha256": source.content_hash_sha256,
                "segment_manifest_hash_sha256": source.segment_manifest_hash_sha256,
            },
            "revisions": {
                "admission_schema_revision": decision.admission_schema_revision,
                "admission_policy_revision": decision.admission_policy_revision,
                "admission_bridge_revision": decision.admission_bridge_revision,
                "admission_integrity_revision": ADMISSION_INTEGRITY_REVISION,
                "candidate_schema_revision": candidate.candidate_schema_revision,
                "source_schema_revision": source.source_schema_revision,
            },
            "evidence": evidence_trace,
            "source_content_included": False,
            "evidence_preview_included": include_evidence_preview,
        }

    def recover_incomplete_admissions(self) -> dict[str, Any]:
        return {
            "recovery_mode": "single_transaction_atomic",
            "recovered_count": 0,
            "incomplete_state_possible": False,
        }

    def _validate_for_admission(
        self,
        scope: AuthenticatedScope,
        candidate_id: str,
    ) -> tuple[
        CandidateMemory,
        SourceRecord,
        Any,
        list[Any],
        dict[str, SourceSegment],
        int,
    ]:
        try:
            candidate = self.candidates.get_candidate(scope, candidate_id)
            run = self.candidates.get_extraction_run(scope, candidate.extraction_run_id)
            source = self.sources.get_source(scope, candidate.source_id)
        except (CandidateEngineError, SourceLedgerError) as exc:
            raise MemoryAdmissionError(
                "ADMISSION_NOT_FOUND",
                "Candidate admission material was not found in the authenticated scope.",
            ) from exc
        if run.status != ExtractionRunStatus.COMPLETED.value:
            raise MemoryAdmissionError(
                "ADMISSION_EXTRACTION_INTEGRITY_FAILED",
                "Candidate extraction run is not completed.",
            )
        if source.retention_policy != "standard":
            raise MemoryAdmissionError(
                "ADMISSION_SOURCE_RETENTION_INCOMPATIBLE",
                "Only standard-retention sources can create admitted memory.",
            )
        source_integrity = self.sources.verify_source_integrity(scope, source.source_id)
        if not source_integrity.verified:
            raise MemoryAdmissionError(
                "ADMISSION_SOURCE_INTEGRITY_FAILED",
                "Source integrity verification failed.",
            )
        extraction_integrity = self.candidates.verify_extraction_integrity(
            scope, run.extraction_run_id
        )
        if not extraction_integrity.verified:
            raise MemoryAdmissionError(
                "ADMISSION_EXTRACTION_INTEGRITY_FAILED",
                "Candidate extraction integrity verification failed.",
            )
        evidence = self.candidates.get_candidate_evidence(scope, candidate.candidate_id)
        segments = {
            item.segment_id: item for item in self._all_segments(scope, source.source_id)
        }
        specs = self._evidence_specs(source, evidence, segments)
        if (
            evidence_manifest_hash(specs)
            != candidate.evidence_manifest_hash_sha256
        ):
            raise MemoryAdmissionError(
                "ADMISSION_EVIDENCE_INVALID",
                "Candidate evidence manifest failed verification.",
            )
        match = RuleMatch(
            proposed_event_type=candidate.proposed_event_type,
            proposed_signal=candidate.proposed_signal,
            proposed_occurred_at=candidate.proposed_occurred_at,
            epistemic_status=candidate.epistemic_status,
            extraction_confidence=candidate.extraction_confidence,
            confidence_basis=candidate.confidence_basis,
            extraction_method=candidate.extraction_method,
            rule_id=candidate.primary_rule_id,
            priority=0,
            evidence=specs,
            normalisation_details=candidate.normalisation_details,
        )
        if (
            candidate_fingerprint(
                source_id=source.source_id,
                match=match,
                evidence=specs,
                candidate_rule_revision=candidate.candidate_rule_revision,
                candidate_extractor_revision=candidate.candidate_extractor_revision,
            )
            != candidate.candidate_fingerprint_sha256
        ):
            raise MemoryAdmissionError(
                "ADMISSION_CANDIDATE_INTEGRITY_FAILED",
                "Candidate fingerprint failed verification.",
            )
        with self.repository.connect() as connection:
            row = self._candidate_row(connection, candidate_id, scope)
            candidate_order = int(row["candidate_order"])
        return candidate, source, run, evidence, segments, candidate_order

    def _non_event_decision(
        self,
        scope: AuthenticatedScope,
        candidate: CandidateMemory,
        actor: AdmissionDecisionActor,
        reason: str,
        idempotency_key: str,
        *,
        decision_type: str,
        target_status: str,
        metadata: dict[str, Any],
    ) -> AdmissionResult:
        actor.validate()
        digest = self._idempotency_digest(idempotency_key, decision_type)
        replay = self._decision_by_digest(scope, digest)
        if replay:
            if replay.candidate_id != candidate.candidate_id or replay.decision_type != decision_type:
                raise MemoryAdmissionError(
                    "ADMISSION_IDEMPOTENCY_CONFLICT",
                    "Admission idempotency key conflicts.",
                )
            return AdmissionResult(replay, None, None, True)
        source = self.sources.get_source(scope, candidate.source_id)
        now = utc_now()
        decision = self._decision(
            admission_id=self._admission_id(candidate.candidate_id, decision_type, digest),
            candidate=candidate,
            source=source,
            decision_type=decision_type,
            actor=actor,
            reason=self._safe_reason(reason),
            metadata={**metadata, "event_created": False},
            policy_id=MANUAL_STRICT_V1,
            digest=digest,
            admitted_event_id=None,
            replacement_candidate_id=None,
            status=AdmissionDecisionStatus.COMPLETED.value,
            started_at=now,
            duration_ms=0.0,
        )
        try:
            with self.repository.connect() as connection:
                self._begin(connection)
                locked = self._candidate_row(
                    connection, candidate.candidate_id, scope, lock=True
                )
                current = str(locked["candidate_status"])
                allowed = (
                    {CandidateStatus.PENDING_REVIEW.value, CandidateStatus.DEFERRED.value}
                    if target_status == CandidateStatus.REJECTED.value
                    else {CandidateStatus.PENDING_REVIEW.value}
                )
                if current not in allowed:
                    raise sqlite3.IntegrityError("candidate state changed")
                self._insert_decision(connection, decision)
                connection.execute(
                    f"UPDATE {self.candidate_table} SET candidate_status={self._placeholder}, "
                    f"current_admission_state={self._placeholder}, updated_at={self._placeholder} "
                    f"WHERE candidate_id={self._placeholder}",
                    (target_status, target_status, now, candidate.candidate_id),
                )
        except Exception as exc:
            replay = self._latest_decision(scope, candidate.candidate_id, decision_type)
            if replay:
                return AdmissionResult(replay, None, None, True)
            raise MemoryAdmissionError(
                "ADMISSION_TRANSACTION_FAILED",
                "Admission decision failed without partial persistence.",
                retryable=True,
            ) from exc
        _safe_log(
            "memory_candidate_rejected"
            if decision_type == AdmissionDecisionType.REJECT.value
            else "memory_candidate_deferred",
            admission_id=decision.admission_id,
            candidate_id=candidate.candidate_id,
            source_id=candidate.source_id,
            decision_type=decision_type,
        )
        return AdmissionResult(decision, None, None, False)

    def _decision(
        self,
        *,
        admission_id: str,
        candidate: CandidateMemory,
        source: SourceRecord,
        decision_type: str,
        actor: AdmissionDecisionActor,
        reason: str,
        metadata: dict[str, Any],
        policy_id: str,
        digest: str,
        admitted_event_id: str | None,
        replacement_candidate_id: str | None,
        status: str,
        started_at: str,
        duration_ms: float,
        completed_at: str | None = None,
    ) -> MemoryAdmissionDecision:
        now = completed_at or utc_now()
        return MemoryAdmissionDecision(
            admission_id=admission_id,
            candidate_id=candidate.candidate_id,
            extraction_run_id=candidate.extraction_run_id,
            source_id=source.source_id,
            client_id=candidate.client_id,
            vault_id=candidate.vault_id,
            namespace=candidate.namespace,
            application_reference=candidate.application_reference,
            actor_reference=candidate.actor_reference,
            workspace_reference=candidate.workspace_reference,
            entity_references=list(candidate.entity_references),
            session_reference=candidate.session_reference,
            decision_type=decision_type,
            decision_status=status,
            decision_actor_type=actor.actor_type,
            decision_actor_reference=actor.actor_reference,
            decision_reason=reason,
            decision_metadata=metadata,
            admission_policy_id=policy_id,
            admission_policy_revision=ADMISSION_POLICY_REVISION,
            admission_schema_revision=ADMISSION_SCHEMA_REVISION,
            admission_bridge_revision=ADMISSION_BRIDGE_REVISION,
            candidate_fingerprint_sha256=candidate.candidate_fingerprint_sha256,
            candidate_evidence_manifest_hash_sha256=candidate.evidence_manifest_hash_sha256,
            source_content_hash_sha256=source.content_hash_sha256,
            source_segment_manifest_hash_sha256=source.segment_manifest_hash_sha256,
            admitted_event_id=admitted_event_id,
            replacement_candidate_id=replacement_candidate_id,
            decision_idempotency_digest=digest,
            decided_at=now,
            completed_at=now if status == AdmissionDecisionStatus.COMPLETED.value else None,
            duration_ms=duration_ms,
            error_code=None,
            created_at=started_at,
            updated_at=now,
        )

    @staticmethod
    def _link(
        link_id: str,
        decision: MemoryAdmissionDecision,
        candidate: CandidateMemory,
        source: SourceRecord,
        event_id: str,
    ) -> AdmittedMemoryLink:
        return AdmittedMemoryLink(
            admitted_memory_link_id=link_id,
            admission_id=decision.admission_id,
            candidate_id=candidate.candidate_id,
            extraction_run_id=candidate.extraction_run_id,
            source_id=source.source_id,
            admitted_event_id=event_id,
            client_id=candidate.client_id,
            vault_id=candidate.vault_id,
            namespace=candidate.namespace,
            application_reference=candidate.application_reference,
            actor_reference=candidate.actor_reference,
            workspace_reference=candidate.workspace_reference,
            entity_references=list(candidate.entity_references),
            session_reference=candidate.session_reference,
            epistemic_status=candidate.epistemic_status,
            proposed_event_type=candidate.proposed_event_type or "information.unknown",
            candidate_fingerprint_sha256=candidate.candidate_fingerprint_sha256,
            source_content_hash_sha256=source.content_hash_sha256,
            evidence_manifest_hash_sha256=candidate.evidence_manifest_hash_sha256,
            admission_policy_revision=ADMISSION_POLICY_REVISION,
            admission_bridge_revision=ADMISSION_BRIDGE_REVISION,
            admitted_event_metadata_revision=ADMITTED_EVENT_METADATA_REVISION,
            created_at=decision.completed_at or decision.decided_at,
        )

    def _insert_decision(
        self, connection: Any, decision: MemoryAdmissionDecision
    ) -> None:
        columns = tuple(decision.to_dict().keys())
        values = [
            canonical_json(value)
            if name in {"entity_references", "decision_metadata"}
            else value
            for name, value in zip(columns, decision.to_dict().values())
        ]
        storage_columns = tuple(
            "entity_references_json"
            if name == "entity_references"
            else "decision_metadata_json"
            if name == "decision_metadata"
            else name
            for name in columns
        )
        placeholders = ",".join([self._placeholder] * len(values))
        connection.execute(
            f"INSERT INTO {self.admission_table} ({','.join(storage_columns)}) "
            f"VALUES ({placeholders})",
            tuple(values),
        )

    def _insert_link(self, connection: Any, link: AdmittedMemoryLink) -> None:
        data = link.to_dict()
        columns = tuple(data.keys())
        values = [
            canonical_json(value) if name == "entity_references" else value
            for name, value in data.items()
        ]
        storage_columns = tuple(
            "entity_references_json" if name == "entity_references" else name
            for name in columns
        )
        connection.execute(
            f"INSERT INTO {self.link_table} ({','.join(storage_columns)}) "
            f"VALUES ({','.join([self._placeholder] * len(values))})",
            tuple(values),
        )

    def _insert_event(
        self,
        connection: Any,
        scope: AuthenticatedScope,
        event: dict[str, Any],
    ) -> None:
        scope_key = self.bridge.scope_key(scope)
        row = connection.execute(
            f"SELECT payload_json FROM {self.events_table} "
            f"WHERE scope_key={self._placeholder}",
            (scope_key,),
        ).fetchone()
        events = self.bridge.event_list_from_storage(row["payload_json"]) if row else []
        if any(item.get("event_id") == event.get("event_id") for item in events):
            return
        events.append(event)
        events.sort(
            key=lambda item: (
                int(item.get("timestamp_index", 0)),
                str(item.get("timestamp", "")),
                str(item.get("event_id", "")),
            )
        )
        payload = canonical_json(events)
        if row:
            connection.execute(
                f"UPDATE {self.events_table} SET payload_json={self._placeholder} "
                f"WHERE scope_key={self._placeholder}",
                (payload, scope_key),
            )
        else:
            connection.execute(
                f"INSERT INTO {self.events_table}(scope_key, payload_json) "
                f"VALUES ({self._placeholder}, {self._placeholder})",
                (scope_key, payload),
            )

    def _insert_replacement_candidate(
        self,
        connection: Any,
        replacement: CandidateMemory,
    ) -> None:
        row = connection.execute(
            f"SELECT COALESCE(MAX(candidate_order), -1) AS maximum "
            f"FROM {self.candidate_table} WHERE extraction_run_id={self._placeholder}",
            (replacement.extraction_run_id,),
        ).fetchone()
        next_order = int(row["maximum"]) + 1
        columns = (
            "candidate_id", "candidate_order", "extraction_run_id", "source_id",
            "client_id", "vault_id", "namespace", "application_reference",
            "actor_reference", "workspace_reference", "entity_references_json",
            "session_reference", "proposed_event_type", "proposed_signal",
            "proposed_occurred_at", "epistemic_status", "extraction_confidence",
            "confidence_basis", "extraction_method", "primary_rule_id",
            "matched_rule_ids_json", "duplicate_match_count", "candidate_status",
            "candidate_fingerprint_sha256", "evidence_manifest_hash_sha256",
            "normalisation_details_json", "candidate_schema_revision",
            "candidate_extractor_revision", "candidate_rule_revision",
            "epistemic_policy_revision", "corrected_from_candidate_id",
            "replacement_candidate_id", "current_admission_state",
            "accepted_admission_id", "accepted_event_id",
            "candidate_correction_revision", "created_at", "updated_at",
        )
        values = (
            replacement.candidate_id, next_order, replacement.extraction_run_id,
            replacement.source_id, replacement.client_id, replacement.vault_id,
            replacement.namespace, replacement.application_reference,
            replacement.actor_reference, replacement.workspace_reference,
            canonical_json(replacement.entity_references),
            replacement.session_reference, replacement.proposed_event_type,
            replacement.proposed_signal, replacement.proposed_occurred_at,
            replacement.epistemic_status, replacement.extraction_confidence,
            replacement.confidence_basis, replacement.extraction_method,
            replacement.primary_rule_id, canonical_json(replacement.matched_rule_ids),
            replacement.duplicate_match_count, replacement.candidate_status,
            replacement.candidate_fingerprint_sha256,
            replacement.evidence_manifest_hash_sha256,
            canonical_json(replacement.normalisation_details),
            replacement.candidate_schema_revision,
            replacement.candidate_extractor_revision,
            replacement.candidate_rule_revision,
            replacement.epistemic_policy_revision,
            replacement.corrected_from_candidate_id,
            replacement.replacement_candidate_id,
            replacement.current_admission_state,
            replacement.accepted_admission_id,
            replacement.accepted_event_id,
            replacement.candidate_correction_revision,
            replacement.created_at,
            replacement.updated_at,
        )
        connection.execute(
            f"INSERT INTO {self.candidate_table} ({','.join(columns)}) "
            f"VALUES ({','.join([self._placeholder] * len(values))})",
            values,
        )

    def _events_for_scope(
        self, scope: AuthenticatedScope, *, connection: Any | None = None
    ) -> list[dict[str, Any]]:
        def read(active: Any) -> list[dict[str, Any]]:
            row = active.execute(
                f"SELECT payload_json FROM {self.events_table} "
                f"WHERE scope_key={self._placeholder}",
                (self.bridge.scope_key(scope),),
            ).fetchone()
            return (
                self.bridge.event_list_from_storage(row["payload_json"]) if row else []
            )

        if connection is not None:
            return read(connection)
        with self.repository.connect() as active:
            return read(active)

    def _candidate_row(
        self,
        connection: Any,
        candidate_id: str,
        scope: AuthenticatedScope,
        *,
        lock: bool = False,
    ) -> Any:
        suffix = " FOR UPDATE" if lock and self.backend == "postgres" else ""
        row = connection.execute(
            f"SELECT * FROM {self.candidate_table} "
            f"WHERE candidate_id={self._placeholder} "
            f"AND client_id={self._placeholder} AND vault_id={self._placeholder} "
            f"AND namespace={self._placeholder}{suffix}",
            (candidate_id, *scope.memory_boundary()),
        ).fetchone()
        if not row:
            raise MemoryAdmissionError(
                "ADMISSION_NOT_FOUND",
                "Candidate was not found in the authenticated scope.",
            )
        return row

    def _get_candidate(
        self, scope: AuthenticatedScope, candidate_id: str
    ) -> CandidateMemory:
        try:
            return self.candidates.get_candidate(scope, candidate_id)
        except CandidateEngineError as exc:
            raise MemoryAdmissionError(
                "ADMISSION_NOT_FOUND",
                "Candidate was not found in the authenticated scope.",
            ) from exc

    def _decision_by_digest(
        self, scope: AuthenticatedScope, digest: str
    ) -> MemoryAdmissionDecision | None:
        with self.repository.connect() as connection:
            row = connection.execute(
                f"SELECT * FROM {self.admission_table} "
                f"WHERE client_id={self._placeholder} AND vault_id={self._placeholder} "
                f"AND namespace={self._placeholder} "
                f"AND decision_idempotency_digest={self._placeholder}",
                (*scope.memory_boundary(), digest),
            ).fetchone()
        return self._decision_from_row(row) if row else None

    def _latest_decision(
        self,
        scope: AuthenticatedScope,
        candidate_id: str,
        decision_type: str,
    ) -> MemoryAdmissionDecision | None:
        with self.repository.connect() as connection:
            row = connection.execute(
                f"SELECT * FROM {self.admission_table} "
                f"WHERE candidate_id={self._placeholder} "
                f"AND client_id={self._placeholder} AND vault_id={self._placeholder} "
                f"AND namespace={self._placeholder} AND decision_type={self._placeholder} "
                "ORDER BY decided_at DESC, admission_id DESC LIMIT 1",
                (candidate_id, *scope.memory_boundary(), decision_type),
            ).fetchone()
        return self._decision_from_row(row) if row else None

    def _link_for_candidate(
        self, scope: AuthenticatedScope, candidate_id: str
    ) -> AdmittedMemoryLink | None:
        with self.repository.connect() as connection:
            row = connection.execute(
                f"SELECT * FROM {self.link_table} WHERE candidate_id={self._placeholder} "
                f"AND client_id={self._placeholder} AND vault_id={self._placeholder} "
                f"AND namespace={self._placeholder}",
                (candidate_id, *scope.memory_boundary()),
            ).fetchone()
        return self._link_from_row(row) if row else None

    def _link_for_admission(
        self, scope: AuthenticatedScope, admission_id: str
    ) -> AdmittedMemoryLink | None:
        with self.repository.connect() as connection:
            row = connection.execute(
                f"SELECT * FROM {self.link_table} WHERE admission_id={self._placeholder} "
                f"AND client_id={self._placeholder} AND vault_id={self._placeholder} "
                f"AND namespace={self._placeholder}",
                (admission_id, *scope.memory_boundary()),
            ).fetchone()
        return self._link_from_row(row) if row else None

    def _accepted_replay(
        self, scope: AuthenticatedScope, link: AdmittedMemoryLink
    ) -> AdmissionResult:
        decision = self.get_admission(scope, link.admission_id)
        event = self.get_admitted_event(scope, link.admitted_event_id)
        return AdmissionResult(decision, link, event, True)

    def _all_segments(
        self, scope: AuthenticatedScope, source_id: str
    ) -> list[SourceSegment]:
        items: list[SourceSegment] = []
        cursor: str | None = None
        while True:
            page = self.sources.list_source_segments(
                scope, source_id, cursor=cursor, limit=1000
            )
            items.extend(page.items)
            if page.next_cursor is None:
                return items
            cursor = page.next_cursor

    @staticmethod
    def _evidence_specs(
        source: SourceRecord,
        evidence: list[Any],
        segments: dict[str, SourceSegment],
    ) -> list[EvidenceSpec]:
        specs: list[EvidenceSpec] = []
        for item in evidence:
            segment = segments.get(item.segment_id)
            if segment is None or segment.source_id != source.source_id:
                raise MemoryAdmissionError(
                    "ADMISSION_EVIDENCE_INVALID",
                    "Candidate evidence segment is unavailable.",
                )
            try:
                text = evidence_text_from_source(
                    source,
                    segment,
                    source_start_offset=item.source_start_offset,
                    source_end_offset=item.source_end_offset,
                    segment_start_offset=item.segment_start_offset,
                    segment_end_offset=item.segment_end_offset,
                    json_pointer=item.json_pointer,
                )
            except CandidateEngineError as exc:
                raise MemoryAdmissionError(
                    "ADMISSION_EVIDENCE_INVALID",
                    "Candidate evidence did not resolve to its source.",
                ) from exc
            specs.append(
                EvidenceSpec(
                    segment_id=item.segment_id,
                    evidence_role=item.evidence_role,
                    text=text,
                    source_start_offset=item.source_start_offset,
                    source_end_offset=item.source_end_offset,
                    segment_start_offset=item.segment_start_offset,
                    segment_end_offset=item.segment_end_offset,
                    start_line=item.start_line,
                    end_line=item.end_line,
                    json_pointer=item.json_pointer,
                )
            )
        return specs

    def _decision_from_row(self, row: Any) -> MemoryAdmissionDecision:
        return MemoryAdmissionDecision(
            admission_id=str(row["admission_id"]),
            candidate_id=str(row["candidate_id"]),
            extraction_run_id=str(row["extraction_run_id"]),
            source_id=str(row["source_id"]),
            client_id=str(row["client_id"]),
            vault_id=str(row["vault_id"]),
            namespace=str(row["namespace"]),
            application_reference=row["application_reference"],
            actor_reference=row["actor_reference"],
            workspace_reference=row["workspace_reference"],
            entity_references=list(self._json_value(row["entity_references_json"])),
            session_reference=row["session_reference"],
            decision_type=str(row["decision_type"]),
            decision_status=str(row["decision_status"]),
            decision_actor_type=str(row["decision_actor_type"]),
            decision_actor_reference=str(row["decision_actor_reference"]),
            decision_reason=str(row["decision_reason"]),
            decision_metadata=dict(self._json_value(row["decision_metadata_json"])),
            admission_policy_id=str(row["admission_policy_id"]),
            admission_policy_revision=str(row["admission_policy_revision"]),
            admission_schema_revision=str(row["admission_schema_revision"]),
            admission_bridge_revision=str(row["admission_bridge_revision"]),
            candidate_fingerprint_sha256=str(row["candidate_fingerprint_sha256"]),
            candidate_evidence_manifest_hash_sha256=str(
                row["candidate_evidence_manifest_hash_sha256"]
            ),
            source_content_hash_sha256=str(row["source_content_hash_sha256"]),
            source_segment_manifest_hash_sha256=str(
                row["source_segment_manifest_hash_sha256"]
            ),
            admitted_event_id=row["admitted_event_id"],
            replacement_candidate_id=row["replacement_candidate_id"],
            decision_idempotency_digest=str(row["decision_idempotency_digest"]),
            decided_at=str(row["decided_at"]),
            completed_at=row["completed_at"],
            duration_ms=float(row["duration_ms"]),
            error_code=row["error_code"],
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    def _link_from_row(self, row: Any) -> AdmittedMemoryLink:
        return AdmittedMemoryLink(
            admitted_memory_link_id=str(row["admitted_memory_link_id"]),
            admission_id=str(row["admission_id"]),
            candidate_id=str(row["candidate_id"]),
            extraction_run_id=str(row["extraction_run_id"]),
            source_id=str(row["source_id"]),
            admitted_event_id=str(row["admitted_event_id"]),
            client_id=str(row["client_id"]),
            vault_id=str(row["vault_id"]),
            namespace=str(row["namespace"]),
            application_reference=row["application_reference"],
            actor_reference=row["actor_reference"],
            workspace_reference=row["workspace_reference"],
            entity_references=list(self._json_value(row["entity_references_json"])),
            session_reference=row["session_reference"],
            epistemic_status=str(row["epistemic_status"]),
            proposed_event_type=str(row["proposed_event_type"]),
            candidate_fingerprint_sha256=str(row["candidate_fingerprint_sha256"]),
            source_content_hash_sha256=str(row["source_content_hash_sha256"]),
            evidence_manifest_hash_sha256=str(row["evidence_manifest_hash_sha256"]),
            admission_policy_revision=str(row["admission_policy_revision"]),
            admission_bridge_revision=str(row["admission_bridge_revision"]),
            admitted_event_metadata_revision=str(
                row["admitted_event_metadata_revision"]
            ),
            created_at=str(row["created_at"]),
        )

    @staticmethod
    def _safe_reason(reason: str) -> str:
        if not isinstance(reason, str) or not reason.strip():
            raise MemoryAdmissionError(
                "ADMISSION_POLICY_INVALID", "A non-empty decision reason is required."
            )
        cleaned = " ".join(reason.split())
        for marker in (
            "authorization:",
            "bearer ",
            "api_key",
            "database_url",
            "postgresql://",
            "prmr_live_",
            "prmr_alpha_",
        ):
            if marker in cleaned.lower():
                raise MemoryAdmissionError(
                    "ADMISSION_POLICY_INVALID",
                    "Decision reason contains restricted credential material.",
                )
        return cleaned[:500]

    @staticmethod
    def _idempotency_digest(key: str, decision_type: str) -> str:
        if not isinstance(key, str) or not key.strip() or len(key) > 500:
            raise MemoryAdmissionError(
                "ADMISSION_POLICY_INVALID",
                "A valid admission idempotency key is required.",
            )
        return sha256_text(f"{decision_type}:{key}")

    @staticmethod
    def _admission_id(candidate_id: str, decision_type: str, digest: str) -> str:
        return f"adm_{sha256_text(canonical_json({'candidate_id': candidate_id, 'decision_type': decision_type, 'digest': digest}))[:24]}"

    def _begin(self, connection: Any) -> None:
        if self.backend == "sqlite":
            connection.execute("BEGIN IMMEDIATE")

    @property
    def _placeholder(self) -> str:
        return "%s" if self.backend == "postgres" else "?"

    @staticmethod
    def _json_value(value: Any) -> Any:
        return json.loads(value) if isinstance(value, str) else value

    @staticmethod
    def _subject_access_allowed(scope: AuthenticatedScope, record: Any) -> bool:
        if (
            record.client_id,
            record.vault_id,
            record.namespace,
        ) != scope.memory_boundary():
            return False
        for field in (
            "application_reference",
            "actor_reference",
            "workspace_reference",
            "session_reference",
        ):
            asserted = getattr(scope, field)
            if asserted is not None and asserted != getattr(record, field):
                return False
        if (
            scope.entity_reference is not None
            and scope.entity_reference not in record.entity_references
        ):
            return False
        return True

    def _require_subject_access(
        self, scope: AuthenticatedScope, record: Any
    ) -> None:
        if not self._subject_access_allowed(scope, record):
            raise MemoryAdmissionError(
                "ADMISSION_NOT_FOUND",
                "Admission was not found in the authenticated scope.",
            )


__all__ = [
    "ADMISSION_TABLE",
    "LINK_TABLE",
    "MemoryAdmissionService",
    "SQLITE_ADMISSION_SCHEMA",
    "initialize_postgres_admission_schema",
    "initialize_sqlite_admission_schema",
]
