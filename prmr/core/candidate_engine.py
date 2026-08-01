"""Durable deterministic Candidate Memory Engine for PRMR Memory Core."""

from __future__ import annotations

from collections import Counter
import json
import logging
import sqlite3
import time
from typing import Any

from .candidate_evidence import (
    evidence_manifest_hash,
    evidence_text_from_source,
    materialize_evidence,
    verify_evidence_record,
)
from .candidate_integrity import candidate_fingerprint, candidate_manifest_hash
from .candidate_models import (
    CANDIDATE_CLAIM_SPLITTER_REVISION,
    CANDIDATE_EXTRACTOR_REVISION,
    CANDIDATE_RULE_REVISION,
    CANDIDATE_SCHEMA_REVISION,
    EPISTEMIC_POLICY_REVISION,
    CandidateEngineError,
    CandidateEvidence,
    CandidateExtractionPolicy,
    CandidateExtractionResult,
    CandidateIntegrityResult,
    CandidateMemory,
    CandidatePage,
    CandidateStatus,
    EpistemicStatus,
    ExtractionRun,
    ExtractionRunPage,
    ExtractionRunStatus,
)
from .candidate_rules import EvidenceSpec, RuleMatch, extract_rule_matches
from .source_integrity import canonical_json, sha256_text
from .source_ledger import POSTGRES_SCHEMA, SourceLedger, utc_now
from .source_models import AuthenticatedScope, MaintenanceContext, SourceLedgerError, SourceRecord, SourceSegment


LOGGER = logging.getLogger("prmr.core.candidate_engine")
RUN_TABLE = "prmr_candidate_extraction_runs"
CANDIDATE_TABLE = "prmr_candidate_memories"
EVIDENCE_TABLE = "prmr_candidate_evidence"


SQLITE_CANDIDATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS prmr_candidate_schema_migrations (
    revision TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS prmr_candidate_extraction_runs (
    extraction_run_id TEXT PRIMARY KEY,
    extraction_identity_sha256 TEXT NOT NULL UNIQUE,
    source_id TEXT NOT NULL,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    application_reference TEXT,
    actor_reference TEXT,
    workspace_reference TEXT,
    entity_references_json TEXT NOT NULL,
    session_reference TEXT,
    source_content_hash_sha256 TEXT NOT NULL,
    source_canonical_hash_sha256 TEXT NOT NULL,
    source_segment_manifest_hash_sha256 TEXT NOT NULL,
    candidate_extractor_revision TEXT NOT NULL,
    candidate_rule_revision TEXT NOT NULL,
    candidate_claim_splitter_revision TEXT NOT NULL,
    epistemic_policy_revision TEXT NOT NULL,
    extraction_policy_json TEXT NOT NULL,
    status TEXT NOT NULL,
    candidate_count INTEGER NOT NULL,
    explicit_count INTEGER NOT NULL,
    derived_count INTEGER NOT NULL,
    inferred_count INTEGER NOT NULL,
    unknown_count INTEGER NOT NULL,
    duplicate_count INTEGER NOT NULL,
    candidate_manifest_hash_sha256 TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    duration_ms REAL NOT NULL,
    error_code TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(source_id) REFERENCES prmr_sources(source_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS prmr_candidate_memories (
    candidate_id TEXT PRIMARY KEY,
    candidate_order INTEGER NOT NULL,
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
    proposed_event_type TEXT,
    proposed_signal TEXT NOT NULL,
    proposed_occurred_at TEXT,
    epistemic_status TEXT NOT NULL,
    extraction_confidence REAL NOT NULL CHECK(extraction_confidence >= 0 AND extraction_confidence <= 1),
    confidence_basis TEXT NOT NULL,
    extraction_method TEXT NOT NULL,
    primary_rule_id TEXT NOT NULL,
    matched_rule_ids_json TEXT NOT NULL,
    duplicate_match_count INTEGER NOT NULL,
    candidate_status TEXT NOT NULL,
    candidate_fingerprint_sha256 TEXT NOT NULL,
    evidence_manifest_hash_sha256 TEXT NOT NULL,
    normalisation_details_json TEXT NOT NULL,
    candidate_schema_revision TEXT NOT NULL,
    candidate_extractor_revision TEXT NOT NULL,
    candidate_rule_revision TEXT NOT NULL,
    epistemic_policy_revision TEXT NOT NULL,
    corrected_from_candidate_id TEXT,
    replacement_candidate_id TEXT UNIQUE,
    current_admission_state TEXT NOT NULL DEFAULT 'pending_review',
    accepted_admission_id TEXT,
    accepted_event_id TEXT,
    candidate_correction_revision TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(extraction_run_id, candidate_fingerprint_sha256),
    UNIQUE(extraction_run_id, candidate_order),
    FOREIGN KEY(extraction_run_id) REFERENCES prmr_candidate_extraction_runs(extraction_run_id) ON DELETE CASCADE,
    FOREIGN KEY(source_id) REFERENCES prmr_sources(source_id) ON DELETE CASCADE,
    FOREIGN KEY(corrected_from_candidate_id) REFERENCES prmr_candidate_memories(candidate_id)
);
CREATE TABLE IF NOT EXISTS prmr_candidate_evidence (
    evidence_id TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    segment_id TEXT NOT NULL,
    evidence_role TEXT NOT NULL,
    sequence_index INTEGER NOT NULL,
    source_start_offset INTEGER,
    source_end_offset INTEGER,
    segment_start_offset INTEGER,
    segment_end_offset INTEGER,
    start_line INTEGER,
    end_line INTEGER,
    json_pointer TEXT,
    evidence_text_hash_sha256 TEXT NOT NULL,
    segment_content_hash_sha256 TEXT NOT NULL,
    source_content_hash_sha256 TEXT NOT NULL,
    extraction_rule_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(candidate_id, sequence_index),
    FOREIGN KEY(candidate_id) REFERENCES prmr_candidate_memories(candidate_id) ON DELETE CASCADE,
    FOREIGN KEY(source_id) REFERENCES prmr_sources(source_id) ON DELETE CASCADE,
    FOREIGN KEY(segment_id) REFERENCES prmr_source_segments(segment_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS prmr_candidate_runs_source_idx ON prmr_candidate_extraction_runs(source_id);
CREATE INDEX IF NOT EXISTS prmr_candidate_runs_scope_idx ON prmr_candidate_extraction_runs(client_id, vault_id, namespace, source_id);
CREATE INDEX IF NOT EXISTS prmr_candidate_runs_status_idx ON prmr_candidate_extraction_runs(status);
CREATE INDEX IF NOT EXISTS prmr_candidate_runs_created_idx ON prmr_candidate_extraction_runs(created_at);
CREATE INDEX IF NOT EXISTS prmr_candidates_scope_idx ON prmr_candidate_memories(client_id, vault_id, namespace, source_id);
CREATE INDEX IF NOT EXISTS prmr_candidates_fingerprint_idx ON prmr_candidate_memories(candidate_fingerprint_sha256);
CREATE INDEX IF NOT EXISTS prmr_candidates_event_type_idx ON prmr_candidate_memories(proposed_event_type);
CREATE INDEX IF NOT EXISTS prmr_candidates_epistemic_idx ON prmr_candidate_memories(epistemic_status);
CREATE INDEX IF NOT EXISTS prmr_candidates_status_idx ON prmr_candidate_memories(candidate_status);
CREATE INDEX IF NOT EXISTS prmr_candidates_created_idx ON prmr_candidate_memories(created_at);
CREATE INDEX IF NOT EXISTS prmr_candidates_corrected_from_idx ON prmr_candidate_memories(corrected_from_candidate_id);
CREATE INDEX IF NOT EXISTS prmr_evidence_candidate_idx ON prmr_candidate_evidence(candidate_id);
CREATE INDEX IF NOT EXISTS prmr_evidence_source_idx ON prmr_candidate_evidence(source_id);
CREATE INDEX IF NOT EXISTS prmr_evidence_segment_idx ON prmr_candidate_evidence(segment_id);
"""


def _safe_log(event: str, **fields: Any) -> None:
    allowed = {
        "extraction_run_id",
        "source_id",
        "source_type",
        "candidate_count",
        "explicit_count",
        "derived_count",
        "inferred_count",
        "unknown_count",
        "duplicate_count",
        "duration_ms",
        "candidate_extractor_revision",
        "candidate_rule_revision",
        "candidate_claim_splitter_revision",
        "epistemic_policy_revision",
        "error_code",
        "client_id",
        "vault_id",
        "namespace",
    }
    payload = {"event": event, **{key: value for key, value in fields.items() if key in allowed}}
    LOGGER.info("%s", json.dumps(payload, separators=(",", ":"), sort_keys=True))


def initialize_sqlite_candidate_schema(connection: sqlite3.Connection) -> None:
    existing = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (CANDIDATE_TABLE,),
    ).fetchone()
    if existing:
        columns = {
            str(row["name"])
            for row in connection.execute(
                f"PRAGMA table_info({CANDIDATE_TABLE})"
            ).fetchall()
        }
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
                connection.execute(
                    f"ALTER TABLE {CANDIDATE_TABLE} ADD COLUMN {name} {declaration}"
                )
    connection.executescript(SQLITE_CANDIDATE_SCHEMA)
    connection.execute(
        "INSERT OR IGNORE INTO prmr_candidate_schema_migrations(revision, applied_at) VALUES (?, ?)",
        (CANDIDATE_SCHEMA_REVISION, utc_now()),
    )


def initialize_postgres_candidate_schema(connection: Any) -> None:
    cursor = connection.cursor()
    cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {POSTGRES_SCHEMA}")
    cursor.execute(
        f"CREATE TABLE IF NOT EXISTS {POSTGRES_SCHEMA}.prmr_candidate_schema_migrations (revision TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {POSTGRES_SCHEMA}.{RUN_TABLE} (
            extraction_run_id TEXT PRIMARY KEY,
            extraction_identity_sha256 TEXT NOT NULL UNIQUE,
            source_id TEXT NOT NULL REFERENCES {POSTGRES_SCHEMA}.prmr_sources(source_id) ON DELETE CASCADE,
            client_id TEXT NOT NULL,
            vault_id TEXT NOT NULL,
            namespace TEXT NOT NULL,
            application_reference TEXT,
            actor_reference TEXT,
            workspace_reference TEXT,
            entity_references_json JSONB NOT NULL,
            session_reference TEXT,
            source_content_hash_sha256 TEXT NOT NULL,
            source_canonical_hash_sha256 TEXT NOT NULL,
            source_segment_manifest_hash_sha256 TEXT NOT NULL,
            candidate_extractor_revision TEXT NOT NULL,
            candidate_rule_revision TEXT NOT NULL,
            candidate_claim_splitter_revision TEXT NOT NULL,
            epistemic_policy_revision TEXT NOT NULL,
            extraction_policy_json JSONB NOT NULL,
            status TEXT NOT NULL,
            candidate_count INTEGER NOT NULL,
            explicit_count INTEGER NOT NULL,
            derived_count INTEGER NOT NULL,
            inferred_count INTEGER NOT NULL,
            unknown_count INTEGER NOT NULL,
            duplicate_count INTEGER NOT NULL,
            candidate_manifest_hash_sha256 TEXT NOT NULL,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            duration_ms DOUBLE PRECISION NOT NULL,
            error_code TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {POSTGRES_SCHEMA}.{CANDIDATE_TABLE} (
            candidate_id TEXT PRIMARY KEY,
            candidate_order INTEGER NOT NULL,
            extraction_run_id TEXT NOT NULL REFERENCES {POSTGRES_SCHEMA}.{RUN_TABLE}(extraction_run_id) ON DELETE CASCADE,
            source_id TEXT NOT NULL REFERENCES {POSTGRES_SCHEMA}.prmr_sources(source_id) ON DELETE CASCADE,
            client_id TEXT NOT NULL,
            vault_id TEXT NOT NULL,
            namespace TEXT NOT NULL,
            application_reference TEXT,
            actor_reference TEXT,
            workspace_reference TEXT,
            entity_references_json JSONB NOT NULL,
            session_reference TEXT,
            proposed_event_type TEXT,
            proposed_signal TEXT NOT NULL,
            proposed_occurred_at TEXT,
            epistemic_status TEXT NOT NULL,
            extraction_confidence DOUBLE PRECISION NOT NULL CHECK(extraction_confidence >= 0 AND extraction_confidence <= 1),
            confidence_basis TEXT NOT NULL,
            extraction_method TEXT NOT NULL,
            primary_rule_id TEXT NOT NULL,
            matched_rule_ids_json JSONB NOT NULL,
            duplicate_match_count INTEGER NOT NULL,
            candidate_status TEXT NOT NULL,
            candidate_fingerprint_sha256 TEXT NOT NULL,
            evidence_manifest_hash_sha256 TEXT NOT NULL,
            normalisation_details_json JSONB NOT NULL,
            candidate_schema_revision TEXT NOT NULL,
            candidate_extractor_revision TEXT NOT NULL,
            candidate_rule_revision TEXT NOT NULL,
            epistemic_policy_revision TEXT NOT NULL,
            corrected_from_candidate_id TEXT REFERENCES {POSTGRES_SCHEMA}.{CANDIDATE_TABLE}(candidate_id),
            replacement_candidate_id TEXT UNIQUE,
            current_admission_state TEXT NOT NULL DEFAULT 'pending_review',
            accepted_admission_id TEXT,
            accepted_event_id TEXT,
            candidate_correction_revision TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(extraction_run_id, candidate_fingerprint_sha256),
            UNIQUE(extraction_run_id, candidate_order)
        )
        """
    )
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {POSTGRES_SCHEMA}.{EVIDENCE_TABLE} (
            evidence_id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL REFERENCES {POSTGRES_SCHEMA}.{CANDIDATE_TABLE}(candidate_id) ON DELETE CASCADE,
            source_id TEXT NOT NULL REFERENCES {POSTGRES_SCHEMA}.prmr_sources(source_id) ON DELETE CASCADE,
            segment_id TEXT NOT NULL REFERENCES {POSTGRES_SCHEMA}.prmr_source_segments(segment_id) ON DELETE CASCADE,
            evidence_role TEXT NOT NULL,
            sequence_index INTEGER NOT NULL,
            source_start_offset INTEGER,
            source_end_offset INTEGER,
            segment_start_offset INTEGER,
            segment_end_offset INTEGER,
            start_line INTEGER,
            end_line INTEGER,
            json_pointer TEXT,
            evidence_text_hash_sha256 TEXT NOT NULL,
            segment_content_hash_sha256 TEXT NOT NULL,
            source_content_hash_sha256 TEXT NOT NULL,
            extraction_rule_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(candidate_id, sequence_index)
        )
        """
    )
    for name, declaration in {
        "corrected_from_candidate_id": "TEXT",
        "replacement_candidate_id": "TEXT",
        "current_admission_state": "TEXT NOT NULL DEFAULT 'pending_review'",
        "accepted_admission_id": "TEXT",
        "accepted_event_id": "TEXT",
        "candidate_correction_revision": "TEXT",
    }.items():
        cursor.execute(
            f"ALTER TABLE {POSTGRES_SCHEMA}.{CANDIDATE_TABLE} "
            f"ADD COLUMN IF NOT EXISTS {name} {declaration}"
        )
    indexes = (
        ("prmr_candidate_runs_source_idx", f"{POSTGRES_SCHEMA}.{RUN_TABLE}(source_id)"),
        ("prmr_candidate_runs_scope_idx", f"{POSTGRES_SCHEMA}.{RUN_TABLE}(client_id, vault_id, namespace, source_id)"),
        ("prmr_candidate_runs_status_idx", f"{POSTGRES_SCHEMA}.{RUN_TABLE}(status)"),
        ("prmr_candidate_runs_created_idx", f"{POSTGRES_SCHEMA}.{RUN_TABLE}(created_at)"),
        ("prmr_candidates_scope_idx", f"{POSTGRES_SCHEMA}.{CANDIDATE_TABLE}(client_id, vault_id, namespace, source_id)"),
        ("prmr_candidates_fingerprint_idx", f"{POSTGRES_SCHEMA}.{CANDIDATE_TABLE}(candidate_fingerprint_sha256)"),
        ("prmr_candidates_event_type_idx", f"{POSTGRES_SCHEMA}.{CANDIDATE_TABLE}(proposed_event_type)"),
        ("prmr_candidates_epistemic_idx", f"{POSTGRES_SCHEMA}.{CANDIDATE_TABLE}(epistemic_status)"),
        ("prmr_candidates_status_idx", f"{POSTGRES_SCHEMA}.{CANDIDATE_TABLE}(candidate_status)"),
        ("prmr_candidates_created_idx", f"{POSTGRES_SCHEMA}.{CANDIDATE_TABLE}(created_at)"),
        ("prmr_candidates_corrected_from_idx", f"{POSTGRES_SCHEMA}.{CANDIDATE_TABLE}(corrected_from_candidate_id)"),
        ("prmr_evidence_candidate_idx", f"{POSTGRES_SCHEMA}.{EVIDENCE_TABLE}(candidate_id)"),
        ("prmr_evidence_source_idx", f"{POSTGRES_SCHEMA}.{EVIDENCE_TABLE}(source_id)"),
        ("prmr_evidence_segment_idx", f"{POSTGRES_SCHEMA}.{EVIDENCE_TABLE}(segment_id)"),
    )
    for name, expression in indexes:
        cursor.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {expression}")
    cursor.execute(
        f"INSERT INTO {POSTGRES_SCHEMA}.prmr_candidate_schema_migrations(revision, applied_at) VALUES (%s, %s) ON CONFLICT(revision) DO NOTHING",
        (CANDIDATE_SCHEMA_REVISION, utc_now()),
    )


class CandidateMemoryEngine:
    """Extract pending candidate interpretations from verified source records."""

    def __init__(
        self,
        repository: Any,
        *,
        candidate_extractor_revision: str = CANDIDATE_EXTRACTOR_REVISION,
        candidate_rule_revision: str = CANDIDATE_RULE_REVISION,
        candidate_claim_splitter_revision: str = CANDIDATE_CLAIM_SPLITTER_REVISION,
        epistemic_policy_revision: str = EPISTEMIC_POLICY_REVISION,
        initialize: bool = True,
    ) -> None:
        self.repository = repository
        self.backend = str(getattr(repository, "backend_name", "sqlite"))
        self.source_ledger = SourceLedger(repository, initialize=initialize)
        self.candidate_extractor_revision = candidate_extractor_revision
        self.candidate_rule_revision = candidate_rule_revision
        self.candidate_claim_splitter_revision = candidate_claim_splitter_revision
        self.epistemic_policy_revision = epistemic_policy_revision
        prefix = f"{POSTGRES_SCHEMA}." if self.backend == "postgres" else ""
        self.run_table = prefix + RUN_TABLE
        self.candidate_table = prefix + CANDIDATE_TABLE
        self.evidence_table = prefix + EVIDENCE_TABLE
        if initialize:
            with repository.connect() as connection:
                if self.backend == "postgres":
                    initialize_postgres_candidate_schema(connection)
                else:
                    initialize_sqlite_candidate_schema(connection)

    def extract_candidates(
        self,
        authenticated_scope: AuthenticatedScope,
        source_id: str,
        extraction_policy: CandidateExtractionPolicy | str = "strict_v1",
    ) -> CandidateExtractionResult:
        started_clock = time.perf_counter()
        policy = self._policy(extraction_policy)
        _safe_log(
            "candidate_extraction_started",
            source_id=source_id,
            client_id=authenticated_scope.client_id,
            vault_id=authenticated_scope.vault_id,
            namespace=authenticated_scope.namespace,
            candidate_extractor_revision=self.candidate_extractor_revision,
            candidate_rule_revision=self.candidate_rule_revision,
            candidate_claim_splitter_revision=self.candidate_claim_splitter_revision,
            epistemic_policy_revision=self.epistemic_policy_revision,
        )
        try:
            source = self._source(authenticated_scope, source_id)
            integrity = self.source_ledger.verify_source_integrity(authenticated_scope, source_id)
            if (policy.require_source_integrity or policy.require_segment_integrity) and not integrity.verified:
                raise CandidateEngineError(
                    "CANDIDATE_SOURCE_INTEGRITY_FAILED",
                    "Source integrity verification failed; extraction did not begin.",
                )
            segments = self._all_segments(authenticated_scope, source_id)
            identity_hash = self._extraction_identity(source, policy)
            existing = self._find_run_by_identity(authenticated_scope, identity_hash)
            if existing:
                candidates = self.list_candidates(
                    authenticated_scope,
                    extraction_run_id=existing.extraction_run_id,
                    limit=max(1, existing.candidate_count + 1),
                ).items
                _safe_log(
                    "candidate_extraction_reused",
                    extraction_run_id=existing.extraction_run_id,
                    source_id=source_id,
                    candidate_count=existing.candidate_count,
                )
                return CandidateExtractionResult(existing, candidates, created=False, reused=True)

            matches, claim_span_count = extract_rule_matches(source, segments, policy)
            run_id = f"xrun_{identity_hash[:24]}"
            candidates, evidence_by_candidate, duplicate_count = self._materialize_candidates(
                run_id,
                source,
                segments,
                matches,
                policy,
            )
            if len(candidates) > policy.maximum_candidates_per_source:
                raise CandidateEngineError(
                    "CANDIDATE_LIMIT_EXCEEDED",
                    "Candidate extraction exceeded the configured source limit; nothing was persisted.",
                )
            counts = Counter(item.epistemic_status for item in candidates)
            now = utc_now()
            duration_ms = round((time.perf_counter() - started_clock) * 1000, 3)
            run = ExtractionRun(
                extraction_run_id=run_id,
                extraction_identity_sha256=identity_hash,
                source_id=source.source_id,
                client_id=source.client_id,
                vault_id=source.vault_id,
                namespace=source.namespace,
                application_reference=source.application_reference,
                actor_reference=source.actor_reference,
                workspace_reference=source.workspace_reference,
                entity_references=source.entity_references,
                session_reference=source.session_reference,
                source_content_hash_sha256=source.content_hash_sha256,
                source_canonical_hash_sha256=source.canonical_payload_hash_sha256,
                source_segment_manifest_hash_sha256=source.segment_manifest_hash_sha256,
                candidate_extractor_revision=self.candidate_extractor_revision,
                candidate_rule_revision=self.candidate_rule_revision,
                candidate_claim_splitter_revision=self.candidate_claim_splitter_revision,
                epistemic_policy_revision=self.epistemic_policy_revision,
                extraction_policy={**policy.to_dict(), "claim_span_count": claim_span_count},
                status=ExtractionRunStatus.COMPLETED.value,
                candidate_count=len(candidates),
                explicit_count=counts[EpistemicStatus.EXPLICIT.value],
                derived_count=counts[EpistemicStatus.DERIVED.value],
                inferred_count=counts[EpistemicStatus.INFERRED.value],
                unknown_count=counts[EpistemicStatus.UNKNOWN.value],
                duplicate_count=duplicate_count,
                candidate_manifest_hash_sha256=candidate_manifest_hash(candidates),
                started_at=now,
                completed_at=now,
                duration_ms=duration_ms,
                error_code=None,
                created_at=now,
                updated_at=now,
            )
            persisted = self._persist_run(run, candidates, evidence_by_candidate)
            if not persisted:
                reused = self._find_run_by_identity(authenticated_scope, identity_hash)
                if not reused:
                    raise CandidateEngineError("CANDIDATE_STORAGE_FAILED", "Candidate extraction run could not be stored.", retryable=True)
                reused_candidates = self.list_candidates(
                    authenticated_scope,
                    extraction_run_id=reused.extraction_run_id,
                    limit=max(1, reused.candidate_count + 1),
                ).items
                return CandidateExtractionResult(reused, reused_candidates, created=False, reused=True)
            _safe_log(
                "candidate_extraction_completed",
                extraction_run_id=run.extraction_run_id,
                source_id=source.source_id,
                source_type=source.source_type,
                candidate_count=run.candidate_count,
                explicit_count=run.explicit_count,
                derived_count=run.derived_count,
                inferred_count=run.inferred_count,
                unknown_count=run.unknown_count,
                duplicate_count=run.duplicate_count,
                duration_ms=duration_ms,
            )
            for _candidate in candidates:
                _safe_log("candidate_created", extraction_run_id=run.extraction_run_id, source_id=source.source_id)
            if duplicate_count:
                _safe_log("candidate_deduplicated", extraction_run_id=run.extraction_run_id, source_id=source.source_id, duplicate_count=duplicate_count)
            return CandidateExtractionResult(run, candidates, created=True, reused=False)
        except CandidateEngineError as exc:
            _safe_log(
                "candidate_extraction_failed",
                source_id=source_id,
                duration_ms=round((time.perf_counter() - started_clock) * 1000, 3),
                error_code=exc.code,
            )
            raise

    def get_extraction_run(self, scope: AuthenticatedScope, extraction_run_id: str) -> ExtractionRun:
        row = self._scoped_row(self.run_table, "extraction_run_id", extraction_run_id, scope, "CANDIDATE_RUN_NOT_FOUND")
        run = self._run_from_row(row)
        self._require_subject_access(scope, run)
        return run

    def list_extraction_runs(
        self,
        scope: AuthenticatedScope,
        source_id: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> ExtractionRunPage:
        offset, safe_limit = self._page(cursor, limit)
        placeholder = self._placeholder
        where = f"client_id={placeholder} AND vault_id={placeholder} AND namespace={placeholder}"
        params: list[Any] = [*scope.memory_boundary()]
        if source_id:
            where += f" AND source_id={placeholder}"
            params.append(source_id)
        params.extend([safe_limit + 1, offset])
        with self.repository.connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM {self.run_table} WHERE {where} ORDER BY created_at, extraction_run_id LIMIT {placeholder} OFFSET {placeholder}",
                tuple(params),
            ).fetchall()
        records = [self._run_from_row(row) for row in rows]
        records = [item for item in records if self._subject_access_allowed(scope, item)]
        return ExtractionRunPage(records[:safe_limit], str(offset + safe_limit) if len(records) > safe_limit else None)

    def get_candidate(self, scope: AuthenticatedScope, candidate_id: str) -> CandidateMemory:
        row = self._scoped_row(self.candidate_table, "candidate_id", candidate_id, scope, "CANDIDATE_NOT_FOUND")
        candidate = self._candidate_from_row(row)
        self._require_subject_access(scope, candidate)
        return candidate

    def list_candidates(
        self,
        scope: AuthenticatedScope,
        source_id: str | None = None,
        extraction_run_id: str | None = None,
        epistemic_status: str | None = None,
        candidate_status: str | None = None,
        cursor: str | None = None,
        limit: int = 200,
    ) -> CandidatePage:
        offset, safe_limit = self._page(cursor, limit, maximum=5_000)
        placeholder = self._placeholder
        where = f"client_id={placeholder} AND vault_id={placeholder} AND namespace={placeholder}"
        params: list[Any] = [*scope.memory_boundary()]
        for field, value in (
            ("source_id", source_id),
            ("extraction_run_id", extraction_run_id),
            ("epistemic_status", epistemic_status),
            ("candidate_status", candidate_status),
        ):
            if value is not None:
                where += f" AND {field}={placeholder}"
                params.append(value)
        params.extend([safe_limit + 1, offset])
        with self.repository.connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM {self.candidate_table} WHERE {where} ORDER BY extraction_run_id, candidate_order LIMIT {placeholder} OFFSET {placeholder}",
                tuple(params),
            ).fetchall()
        records = [self._candidate_from_row(row) for row in rows]
        records = [item for item in records if self._subject_access_allowed(scope, item)]
        return CandidatePage(records[:safe_limit], str(offset + safe_limit) if len(records) > safe_limit else None)

    def get_candidate_evidence(self, scope: AuthenticatedScope, candidate_id: str) -> list[CandidateEvidence]:
        candidate = self.get_candidate(scope, candidate_id)
        with self.repository.connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM {self.evidence_table} WHERE candidate_id={self._placeholder} ORDER BY sequence_index",
                (candidate.candidate_id,),
            ).fetchall()
        return [self._evidence_from_row(row) for row in rows]

    def verify_extraction_integrity(
        self,
        scope: AuthenticatedScope,
        extraction_run_id: str,
    ) -> CandidateIntegrityResult:
        run = self.get_extraction_run(scope, extraction_run_id)
        try:
            source = self._source(scope, run.source_id)
            source_integrity = self.source_ledger.verify_source_integrity(scope, source.source_id)
            segments = self._all_segments(scope, source.source_id)
        except (CandidateEngineError, SourceLedgerError):
            source = None
            source_integrity = None
            segments = []
        candidates = [
            item
            for item in self.list_candidates(
                scope,
                extraction_run_id=run.extraction_run_id,
                limit=max(1, run.candidate_count + 2_001),
            ).items
            if item.corrected_from_candidate_id is None
        ]
        segment_by_id = {item.segment_id: item for item in segments}
        evidence_valid = True
        fingerprint_valid = True
        evidence_manifest_valid = True
        primary_evidence_present = True
        candidate_scope_valid = True
        for candidate in candidates:
            evidence = self.get_candidate_evidence(scope, candidate.candidate_id)
            primary_evidence_present &= any(item.evidence_role == "primary" for item in evidence)
            candidate_scope_valid &= (
                candidate.source_id == run.source_id
                and candidate.client_id == run.client_id
                and candidate.vault_id == run.vault_id
                and candidate.namespace == run.namespace
            )
            specs: list[EvidenceSpec] = []
            for item in evidence:
                segment = segment_by_id.get(item.segment_id)
                if source is None or segment is None:
                    evidence_valid = False
                    continue
                checks = verify_evidence_record(source, segment, item)
                evidence_valid &= all(checks.values())
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
                except CandidateEngineError:
                    text = ""
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
            evidence_manifest_valid &= evidence_manifest_hash(specs) == candidate.evidence_manifest_hash_sha256
            synthetic_match = RuleMatch(
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
            fingerprint_valid &= candidate_fingerprint(
                source_id=candidate.source_id,
                match=synthetic_match,
                evidence=specs,
                candidate_rule_revision=candidate.candidate_rule_revision,
                candidate_extractor_revision=candidate.candidate_extractor_revision,
            ) == candidate.candidate_fingerprint_sha256
        checks = {
            "source_integrity": bool(source_integrity and source_integrity.verified),
            "run_source_hashes": bool(
                source
                and run.source_content_hash_sha256 == source.content_hash_sha256
                and run.source_canonical_hash_sha256 == source.canonical_payload_hash_sha256
                and run.source_segment_manifest_hash_sha256 == source.segment_manifest_hash_sha256
            ),
            "candidate_count": len(candidates) == run.candidate_count,
            "candidate_ordering": len({item.candidate_id for item in candidates}) == len(candidates),
            "candidate_fingerprints": fingerprint_valid,
            "primary_evidence": primary_evidence_present,
            "evidence_integrity": evidence_valid,
            "evidence_manifests": evidence_manifest_valid,
            "scope_ownership": candidate_scope_valid,
            "candidate_manifest": candidate_manifest_hash(candidates) == run.candidate_manifest_hash_sha256,
        }
        failures = [name for name, passed in checks.items() if not passed]
        result = CandidateIntegrityResult(run.extraction_run_id, not failures, checks, failures)
        _safe_log(
            "candidate_integrity_verified" if result.verified else "candidate_integrity_failed",
            extraction_run_id=run.extraction_run_id,
            source_id=run.source_id,
            candidate_count=run.candidate_count,
            error_code=None if result.verified else "CANDIDATE_MANIFEST_MISMATCH",
        )
        return result

    def invalidate_extraction_run(
        self,
        context: MaintenanceContext,
        extraction_run_id: str,
        reason: str,
    ) -> dict[str, Any]:
        if not isinstance(reason, str) or not reason.strip():
            raise CandidateEngineError("CANDIDATE_POLICY_INVALID", "Invalidation reason is required.")
        if not context.privileged and context.scope is None:
            raise CandidateEngineError("CANDIDATE_SCOPE_DENIED", "Explicit maintenance authority is required.")
        if context.scope:
            run = self.get_extraction_run(context.scope, extraction_run_id)
        else:
            with self.repository.connect() as connection:
                row = connection.execute(
                    f"SELECT * FROM {self.run_table} WHERE extraction_run_id={self._placeholder}",
                    (extraction_run_id,),
                ).fetchone()
            if not row:
                raise CandidateEngineError("CANDIDATE_RUN_NOT_FOUND", "Extraction run was not found.")
            run = self._run_from_row(row)
        now = utc_now()
        with self.repository.connect() as connection:
            if self.backend == "sqlite":
                connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                f"UPDATE {self.run_table} SET status={self._placeholder}, updated_at={self._placeholder}, error_code={self._placeholder} WHERE extraction_run_id={self._placeholder}",
                (ExtractionRunStatus.INVALIDATED.value, now, "explicit_invalidation", run.extraction_run_id),
            )
            connection.execute(
                f"UPDATE {self.candidate_table} SET candidate_status={self._placeholder}, updated_at={self._placeholder} WHERE extraction_run_id={self._placeholder}",
                (CandidateStatus.INVALIDATED.value, now, run.extraction_run_id),
            )
        _safe_log("candidate_run_invalidated", extraction_run_id=run.extraction_run_id, source_id=run.source_id)
        return {
            "extraction_run_id": run.extraction_run_id,
            "status": ExtractionRunStatus.INVALIDATED.value,
            "reason_recorded_in_log": True,
            "source_content_exposed": False,
        }

    def _materialize_candidates(
        self,
        run_id: str,
        source: SourceRecord,
        segments: list[SourceSegment],
        matches: list[RuleMatch],
        policy: CandidateExtractionPolicy,
    ) -> tuple[list[CandidateMemory], dict[str, list[CandidateEvidence]], int]:
        segment_by_id = {item.segment_id: item for item in segments}
        segment_order = {item.segment_id: item.sequence_index for item in segments}
        # One exact evidence span represents one claim. Multiple rules may
        # classify that claim, but rule priority selects a single candidate and
        # all matching rule IDs remain auditable on it.
        claim_groups: dict[str, list[RuleMatch]] = {}
        for match in matches:
            if not match.evidence:
                raise CandidateEngineError("CANDIDATE_EVIDENCE_INVALID", "Rule match has no evidence.")
            claim_groups.setdefault(evidence_manifest_hash(match.evidence), []).append(match)
        grouped: dict[str, list[RuleMatch]] = {}
        for group in claim_groups.values():
            primary = sorted(group, key=lambda item: (item.priority, item.rule_id))[0]
            fingerprint = candidate_fingerprint(
                source_id=source.source_id,
                match=primary,
                evidence=primary.evidence,
                candidate_rule_revision=self.candidate_rule_revision,
                candidate_extractor_revision=self.candidate_extractor_revision,
            )
            grouped.setdefault(fingerprint, []).extend(group)
        ordered_groups = sorted(
            grouped.items(),
            key=lambda item: (
                segment_order.get(item[1][0].evidence[0].segment_id, 10**9),
                item[1][0].evidence[0].segment_start_offset or 0,
                min(match.priority for match in item[1]),
                item[1][0].proposed_event_type or "",
                item[0],
            ),
        )
        now = utc_now()
        candidates: list[CandidateMemory] = []
        evidence_by_candidate: dict[str, list[CandidateEvidence]] = {}
        duplicate_count = 0
        for fingerprint, group in ordered_groups:
            primary = sorted(group, key=lambda item: (item.priority, item.rule_id))[0]
            matched_rule_ids = sorted({item.rule_id for item in group})
            duplicate_matches = max(0, len(group) - 1)
            duplicate_count += duplicate_matches
            candidate_id = f"cand_{sha256_text(canonical_json({'run': run_id, 'fingerprint': fingerprint}))[:24]}"
            evidence_hash = evidence_manifest_hash(primary.evidence)
            candidate = CandidateMemory(
                candidate_id=candidate_id,
                extraction_run_id=run_id,
                source_id=source.source_id,
                client_id=source.client_id,
                vault_id=source.vault_id,
                namespace=source.namespace,
                application_reference=source.application_reference,
                actor_reference=source.actor_reference,
                workspace_reference=source.workspace_reference,
                entity_references=source.entity_references,
                session_reference=source.session_reference,
                proposed_event_type=primary.proposed_event_type,
                proposed_signal=primary.proposed_signal,
                # Keep the stored value identical to the fingerprint input. A
                # source timestamp remains available through source provenance;
                # it is not silently injected into a claim after fingerprinting.
                proposed_occurred_at=primary.proposed_occurred_at,
                epistemic_status=primary.epistemic_status,
                extraction_confidence=primary.extraction_confidence,
                confidence_basis=primary.confidence_basis,
                extraction_method=primary.extraction_method,
                primary_rule_id=primary.rule_id,
                matched_rule_ids=matched_rule_ids,
                duplicate_match_count=duplicate_matches,
                candidate_status=CandidateStatus.PENDING_REVIEW.value,
                candidate_fingerprint_sha256=fingerprint,
                evidence_manifest_hash_sha256=evidence_hash,
                normalisation_details={
                    **primary.normalisation_details,
                    "extraction_confidence_definition": "confidence that the deterministic extraction rule was applied correctly; not real-world truth probability",
                    "admitted_memory": False,
                },
                candidate_schema_revision=CANDIDATE_SCHEMA_REVISION,
                candidate_extractor_revision=self.candidate_extractor_revision,
                candidate_rule_revision=self.candidate_rule_revision,
                epistemic_policy_revision=self.epistemic_policy_revision,
                created_at=now,
                updated_at=now,
            )
            evidence = materialize_evidence(
                candidate_id=candidate_id,
                source=source,
                segment_by_id=segment_by_id,
                specs=primary.evidence,
                extraction_rule_id=primary.rule_id,
                created_at=now,
            )
            candidates.append(candidate)
            evidence_by_candidate[candidate_id] = evidence
        return candidates, evidence_by_candidate, duplicate_count

    def _persist_run(
        self,
        run: ExtractionRun,
        candidates: list[CandidateMemory],
        evidence_by_candidate: dict[str, list[CandidateEvidence]],
    ) -> bool:
        with self.repository.connect() as connection:
            if self.backend == "sqlite":
                connection.execute("BEGIN IMMEDIATE")
                existing = connection.execute(
                    f"SELECT extraction_run_id FROM {self.run_table} WHERE extraction_identity_sha256=?",
                    (run.extraction_identity_sha256,),
                ).fetchone()
                if existing:
                    return False
            if not self._insert_run(connection, run):
                return False
            self._insert_candidates(connection, candidates)
            self._insert_evidence(connection, [item for candidate in candidates for item in evidence_by_candidate[candidate.candidate_id]])
        return True

    def _insert_run(self, connection: Any, run: ExtractionRun) -> bool:
        columns = (
            "extraction_run_id", "extraction_identity_sha256", "source_id", "client_id", "vault_id", "namespace",
            "application_reference", "actor_reference", "workspace_reference", "entity_references_json", "session_reference",
            "source_content_hash_sha256", "source_canonical_hash_sha256", "source_segment_manifest_hash_sha256",
            "candidate_extractor_revision", "candidate_rule_revision", "candidate_claim_splitter_revision", "epistemic_policy_revision",
            "extraction_policy_json", "status", "candidate_count", "explicit_count", "derived_count", "inferred_count",
            "unknown_count", "duplicate_count", "candidate_manifest_hash_sha256", "started_at", "completed_at", "duration_ms",
            "error_code", "created_at", "updated_at",
        )
        values = (
            run.extraction_run_id, run.extraction_identity_sha256, run.source_id, run.client_id, run.vault_id, run.namespace,
            run.application_reference, run.actor_reference, run.workspace_reference, self._json(run.entity_references), run.session_reference,
            run.source_content_hash_sha256, run.source_canonical_hash_sha256, run.source_segment_manifest_hash_sha256,
            run.candidate_extractor_revision, run.candidate_rule_revision, run.candidate_claim_splitter_revision, run.epistemic_policy_revision,
            self._json(run.extraction_policy), run.status, run.candidate_count, run.explicit_count, run.derived_count, run.inferred_count,
            run.unknown_count, run.duplicate_count, run.candidate_manifest_hash_sha256, run.started_at, run.completed_at, run.duration_ms,
            run.error_code, run.created_at, run.updated_at,
        )
        placeholders = ",".join([self._placeholder] * len(columns))
        sql = f"INSERT INTO {self.run_table} ({','.join(columns)}) VALUES ({placeholders})"
        if self.backend == "postgres":
            sql += " ON CONFLICT(extraction_identity_sha256) DO NOTHING RETURNING extraction_run_id"
            return connection.execute(sql, values).fetchone() is not None
        connection.execute(sql, values)
        return True

    def _insert_candidates(self, connection: Any, candidates: list[CandidateMemory]) -> None:
        columns = (
            "candidate_id", "candidate_order", "extraction_run_id", "source_id", "client_id", "vault_id", "namespace",
            "application_reference", "actor_reference", "workspace_reference", "entity_references_json", "session_reference",
            "proposed_event_type", "proposed_signal", "proposed_occurred_at", "epistemic_status", "extraction_confidence",
            "confidence_basis", "extraction_method", "primary_rule_id", "matched_rule_ids_json", "duplicate_match_count",
            "candidate_status", "candidate_fingerprint_sha256", "evidence_manifest_hash_sha256", "normalisation_details_json",
            "candidate_schema_revision", "candidate_extractor_revision", "candidate_rule_revision", "epistemic_policy_revision",
            "corrected_from_candidate_id", "replacement_candidate_id", "current_admission_state",
            "accepted_admission_id", "accepted_event_id", "candidate_correction_revision",
            "created_at", "updated_at",
        )
        rows = []
        for order, item in enumerate(candidates):
            rows.append((
                item.candidate_id, order, item.extraction_run_id, item.source_id, item.client_id, item.vault_id, item.namespace,
                item.application_reference, item.actor_reference, item.workspace_reference, self._json(item.entity_references), item.session_reference,
                item.proposed_event_type, item.proposed_signal, item.proposed_occurred_at, item.epistemic_status, item.extraction_confidence,
                item.confidence_basis, item.extraction_method, item.primary_rule_id, self._json(item.matched_rule_ids), item.duplicate_match_count,
                item.candidate_status, item.candidate_fingerprint_sha256, item.evidence_manifest_hash_sha256, self._json(item.normalisation_details),
                item.candidate_schema_revision, item.candidate_extractor_revision, item.candidate_rule_revision, item.epistemic_policy_revision,
                item.corrected_from_candidate_id, item.replacement_candidate_id, item.current_admission_state,
                item.accepted_admission_id, item.accepted_event_id, item.candidate_correction_revision,
                item.created_at, item.updated_at,
            ))
        if rows:
            placeholders = ",".join([self._placeholder] * len(columns))
            connection.cursor().executemany(
                f"INSERT INTO {self.candidate_table} ({','.join(columns)}) VALUES ({placeholders})",
                rows,
            )

    def _insert_evidence(self, connection: Any, evidence: list[CandidateEvidence]) -> None:
        columns = (
            "evidence_id", "candidate_id", "source_id", "segment_id", "evidence_role", "sequence_index",
            "source_start_offset", "source_end_offset", "segment_start_offset", "segment_end_offset", "start_line", "end_line",
            "json_pointer", "evidence_text_hash_sha256", "segment_content_hash_sha256", "source_content_hash_sha256",
            "extraction_rule_id", "created_at",
        )
        rows = [tuple(getattr(item, column) for column in columns) for item in evidence]
        if rows:
            placeholders = ",".join([self._placeholder] * len(columns))
            connection.cursor().executemany(
                f"INSERT INTO {self.evidence_table} ({','.join(columns)}) VALUES ({placeholders})",
                rows,
            )

    def _extraction_identity(self, source: SourceRecord, policy: CandidateExtractionPolicy) -> str:
        return sha256_text(
            canonical_json(
                {
                    "source_id": source.source_id,
                    "source_content_hash_sha256": source.content_hash_sha256,
                    "source_segment_manifest_hash_sha256": source.segment_manifest_hash_sha256,
                    "extraction_policy": policy.to_dict(),
                    "candidate_extractor_revision": self.candidate_extractor_revision,
                    "candidate_rule_revision": self.candidate_rule_revision,
                    "candidate_claim_splitter_revision": self.candidate_claim_splitter_revision,
                    "epistemic_policy_revision": self.epistemic_policy_revision,
                }
            )
        )

    def _find_run_by_identity(self, scope: AuthenticatedScope, identity: str) -> ExtractionRun | None:
        with self.repository.connect() as connection:
            row = connection.execute(
                f"SELECT * FROM {self.run_table} WHERE extraction_identity_sha256={self._placeholder} AND client_id={self._placeholder} AND vault_id={self._placeholder} AND namespace={self._placeholder}",
                (identity, *scope.memory_boundary()),
            ).fetchone()
        if not row:
            return None
        run = self._run_from_row(row)
        return run if self._subject_access_allowed(scope, run) else None

    def _source(self, scope: AuthenticatedScope, source_id: str) -> SourceRecord:
        try:
            return self.source_ledger.get_source(scope, source_id)
        except SourceLedgerError as exc:
            mapping = {
                "SOURCE_EXPIRED": "CANDIDATE_SOURCE_EXPIRED",
                "SOURCE_INTEGRITY_FAILED": "CANDIDATE_SOURCE_INTEGRITY_FAILED",
            }
            raise CandidateEngineError(
                mapping.get(exc.code, "CANDIDATE_SOURCE_NOT_FOUND"),
                "Source is unavailable in the authenticated candidate scope.",
            ) from exc

    def _all_segments(self, scope: AuthenticatedScope, source_id: str) -> list[SourceSegment]:
        items: list[SourceSegment] = []
        cursor: str | None = None
        while True:
            page = self.source_ledger.list_source_segments(scope, source_id, cursor=cursor, limit=1000)
            items.extend(page.items)
            if page.next_cursor is None:
                return items
            cursor = page.next_cursor

    def _policy(self, policy: CandidateExtractionPolicy | str) -> CandidateExtractionPolicy:
        if isinstance(policy, str):
            if policy != "strict_v1":
                raise CandidateEngineError("CANDIDATE_POLICY_INVALID", "Unknown candidate extraction policy.")
            policy = CandidateExtractionPolicy()
        if not isinstance(policy, CandidateExtractionPolicy):
            raise CandidateEngineError("CANDIDATE_POLICY_INVALID", "Candidate extraction policy is invalid.")
        policy.validate()
        return policy

    def _scoped_row(
        self,
        table: str,
        id_field: str,
        value: str,
        scope: AuthenticatedScope,
        error_code: str,
    ) -> Any:
        with self.repository.connect() as connection:
            row = connection.execute(
                f"SELECT * FROM {table} WHERE {id_field}={self._placeholder} AND client_id={self._placeholder} AND vault_id={self._placeholder} AND namespace={self._placeholder}",
                (value, *scope.memory_boundary()),
            ).fetchone()
        if not row:
            raise CandidateEngineError(error_code, "Candidate record was not found in the authenticated scope.")
        return row

    def _subject_access_allowed(self, scope: AuthenticatedScope, record: Any) -> bool:
        pairs = (
            (scope.application_reference, record.application_reference),
            (scope.actor_reference, record.actor_reference),
            (scope.workspace_reference, record.workspace_reference),
            (scope.session_reference, record.session_reference),
        )
        if any(asserted is not None and asserted != stored for asserted, stored in pairs):
            return False
        return scope.entity_reference is None or scope.entity_reference in record.entity_references

    def _require_subject_access(self, scope: AuthenticatedScope, record: Any) -> None:
        if not self._subject_access_allowed(scope, record):
            raise CandidateEngineError("CANDIDATE_NOT_FOUND", "Candidate record was not found in the authenticated scope.")

    def _run_from_row(self, row: Any) -> ExtractionRun:
        return ExtractionRun(
            extraction_run_id=str(row["extraction_run_id"]),
            extraction_identity_sha256=str(row["extraction_identity_sha256"]),
            source_id=str(row["source_id"]), client_id=str(row["client_id"]), vault_id=str(row["vault_id"]), namespace=str(row["namespace"]),
            application_reference=row["application_reference"], actor_reference=row["actor_reference"], workspace_reference=row["workspace_reference"],
            entity_references=list(self._json_value(row["entity_references_json"])), session_reference=row["session_reference"],
            source_content_hash_sha256=str(row["source_content_hash_sha256"]), source_canonical_hash_sha256=str(row["source_canonical_hash_sha256"]),
            source_segment_manifest_hash_sha256=str(row["source_segment_manifest_hash_sha256"]),
            candidate_extractor_revision=str(row["candidate_extractor_revision"]), candidate_rule_revision=str(row["candidate_rule_revision"]),
            candidate_claim_splitter_revision=str(row["candidate_claim_splitter_revision"]), epistemic_policy_revision=str(row["epistemic_policy_revision"]),
            extraction_policy=dict(self._json_value(row["extraction_policy_json"])), status=str(row["status"]), candidate_count=int(row["candidate_count"]),
            explicit_count=int(row["explicit_count"]), derived_count=int(row["derived_count"]), inferred_count=int(row["inferred_count"]),
            unknown_count=int(row["unknown_count"]), duplicate_count=int(row["duplicate_count"]),
            candidate_manifest_hash_sha256=str(row["candidate_manifest_hash_sha256"]), started_at=str(row["started_at"]), completed_at=row["completed_at"],
            duration_ms=float(row["duration_ms"]), error_code=row["error_code"], created_at=str(row["created_at"]), updated_at=str(row["updated_at"]),
        )

    def _candidate_from_row(self, row: Any) -> CandidateMemory:
        return CandidateMemory(
            candidate_id=str(row["candidate_id"]), extraction_run_id=str(row["extraction_run_id"]), source_id=str(row["source_id"]),
            client_id=str(row["client_id"]), vault_id=str(row["vault_id"]), namespace=str(row["namespace"]),
            application_reference=row["application_reference"], actor_reference=row["actor_reference"], workspace_reference=row["workspace_reference"],
            entity_references=list(self._json_value(row["entity_references_json"])), session_reference=row["session_reference"],
            proposed_event_type=row["proposed_event_type"], proposed_signal=str(row["proposed_signal"]), proposed_occurred_at=row["proposed_occurred_at"],
            epistemic_status=str(row["epistemic_status"]), extraction_confidence=float(row["extraction_confidence"]), confidence_basis=str(row["confidence_basis"]),
            extraction_method=str(row["extraction_method"]), primary_rule_id=str(row["primary_rule_id"]), matched_rule_ids=list(self._json_value(row["matched_rule_ids_json"])),
            duplicate_match_count=int(row["duplicate_match_count"]), candidate_status=str(row["candidate_status"]),
            candidate_fingerprint_sha256=str(row["candidate_fingerprint_sha256"]), evidence_manifest_hash_sha256=str(row["evidence_manifest_hash_sha256"]),
            normalisation_details=dict(self._json_value(row["normalisation_details_json"])), candidate_schema_revision=str(row["candidate_schema_revision"]),
            candidate_extractor_revision=str(row["candidate_extractor_revision"]), candidate_rule_revision=str(row["candidate_rule_revision"]),
            epistemic_policy_revision=str(row["epistemic_policy_revision"]), created_at=str(row["created_at"]), updated_at=str(row["updated_at"]),
            corrected_from_candidate_id=row["corrected_from_candidate_id"],
            replacement_candidate_id=row["replacement_candidate_id"],
            current_admission_state=str(row["current_admission_state"]),
            accepted_admission_id=row["accepted_admission_id"],
            accepted_event_id=row["accepted_event_id"],
            candidate_correction_revision=row["candidate_correction_revision"],
        )

    def _evidence_from_row(self, row: Any) -> CandidateEvidence:
        return CandidateEvidence(
            evidence_id=str(row["evidence_id"]), candidate_id=str(row["candidate_id"]), source_id=str(row["source_id"]), segment_id=str(row["segment_id"]),
            evidence_role=str(row["evidence_role"]), sequence_index=int(row["sequence_index"]), source_start_offset=row["source_start_offset"],
            source_end_offset=row["source_end_offset"], segment_start_offset=row["segment_start_offset"], segment_end_offset=row["segment_end_offset"],
            start_line=row["start_line"], end_line=row["end_line"], json_pointer=row["json_pointer"], evidence_text_hash_sha256=str(row["evidence_text_hash_sha256"]),
            segment_content_hash_sha256=str(row["segment_content_hash_sha256"]), source_content_hash_sha256=str(row["source_content_hash_sha256"]),
            extraction_rule_id=str(row["extraction_rule_id"]), created_at=str(row["created_at"]),
        )

    def _page(self, cursor: str | None, limit: int, *, maximum: int = 200) -> tuple[int, int]:
        try:
            offset = int(cursor or 0)
            safe_limit = int(limit)
        except (TypeError, ValueError) as exc:
            raise CandidateEngineError("CANDIDATE_POLICY_INVALID", "Candidate pagination values are invalid.") from exc
        if offset < 0 or not 1 <= safe_limit <= maximum:
            raise CandidateEngineError("CANDIDATE_POLICY_INVALID", "Candidate pagination values are outside allowed bounds.")
        return offset, safe_limit

    @property
    def _placeholder(self) -> str:
        return "%s" if self.backend == "postgres" else "?"

    def _json(self, value: Any) -> str:
        return canonical_json(value)

    def _json_value(self, value: Any) -> Any:
        return json.loads(value) if isinstance(value, str) else value


__all__ = [
    "CANDIDATE_TABLE",
    "EVIDENCE_TABLE",
    "RUN_TABLE",
    "CandidateMemoryEngine",
    "initialize_postgres_candidate_schema",
    "initialize_sqlite_candidate_schema",
]
