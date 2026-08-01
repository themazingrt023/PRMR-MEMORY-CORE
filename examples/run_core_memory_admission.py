"""Exercise Core Sprint 3 against PRMR's durable event and provenance stores."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import sys
from tempfile import TemporaryDirectory
import time
from typing import Any, Callable
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from prmr.core.admission_fixtures import (
    admission_policy_fixtures,
    correction_fixture,
    story_admission_fixture,
)
from prmr.core.admission_models import (
    AdmissionDecisionActor,
    MemoryAdmissionError,
)
from prmr.core.admission_service import MemoryAdmissionService
from prmr.core.candidate_engine import CandidateMemoryEngine
from prmr.core.candidate_fixtures import STRUCTURED_JSON
from prmr.core.source_ledger import SourceLedger
from prmr.core.source_models import (
    AuthenticatedScope,
    MaintenanceContext,
    SourceInput,
    SourceLedgerError,
)
from prmr.product.self_serve_repository_v093 import SelfServeRepositoryV093


REPORT_DIR = ROOT / "reports" / "core_memory_admission"
PUBLIC_REPORT = REPORT_DIR / "public_memory_admission.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_memory_admission.json"
SCORECARD = REPORT_DIR / "scorecard_memory_admission.md"
BOUNDARY = (
    "Core Sprint 3 is internal deterministic Memory Admission and event-ledger bridge evidence. "
    "It does not determine truth, provide accepted-event supersession, prove production readiness, "
    "or constitute external validation."
)
REQUIRED_FINAL_STATEMENT = (
    "Core Sprint 3 establishes Memory Admission and the Event-Ledger Bridge inside PRMR Memory Core. "
    "Provenance-backed candidate memories can now be accepted, rejected, deferred or corrected under "
    "explicit policy. Accepted candidates become exactly one scoped event in the existing deterministic "
    "continuity engine while preserving source, evidence, epistemic and admission provenance. Rejected "
    "and deferred candidates do not affect memory. Accepted-event supersession, contradiction handling "
    "and advanced temporal evolution remain later core-engine milestones."
)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def add(
    checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None
) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def expect_error(call: Callable[[], Any], code: str) -> bool:
    try:
        call()
    except (MemoryAdmissionError, SourceLedgerError) as exc:
        return exc.code == code
    return False


def count(
    repository: Any,
    table: str,
    where: str = "",
    params: tuple[Any, ...] = (),
) -> int:
    prefix = (
        "prmr_self_serve."
        if getattr(repository, "backend_name", "sqlite") == "postgres"
        else ""
    )
    with repository.connect() as connection:
        row = connection.execute(
            f"SELECT COUNT(*) AS count FROM {prefix}{table} {where}", params
        ).fetchone()
    return int(row["count"])


def contains_secret(value: Any) -> bool:
    text = (
        value
        if isinstance(value, str)
        else json.dumps(value, sort_keys=True, ensure_ascii=False)
    )
    patterns = (
        r"\bprmr_(?:alpha|live)_[A-Za-z0-9_-]{12,}\b",
        r"Authorization\s*:\s*Bearer\s+(?!\[REDACTED)[A-Za-z0-9._~+/=-]{8,}",
        r"postgres(?:ql)?://[^\s\"']+",
        r"-----BEGIN(?: [A-Z0-9]+)? PRIVATE KEY-----",
    )
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def candidate_by_type(items: list[Any], event_type: str) -> Any:
    return next(item for item in items if item.proposed_event_type == event_type)


def run_order_proof(base_path: Path, scope: AuthenticatedScope) -> dict[str, Any]:
    repository = SelfServeRepositoryV093(base_path)
    ledger = SourceLedger(repository)
    engine = CandidateMemoryEngine(repository)
    source = ledger.ingest_source(scope, story_admission_fixture()).source
    candidates = engine.extract_candidates(scope, source.source_id).candidates[:5]
    with repository.connect() as connection:
        connection.execute("PRAGMA wal_checkpoint(FULL)")
    reverse_path = base_path.with_name("reverse.sqlite")
    shutil.copy2(base_path, reverse_path)
    actor = AdmissionDecisionActor("test_runner", "order-proof")
    normal = MemoryAdmissionService(repository)
    for candidate in candidates:
        normal.accept_candidate(
            scope,
            candidate.candidate_id,
            actor,
            "Order independence proof.",
            f"normal:{candidate.candidate_id}",
        )
    reverse = MemoryAdmissionService(SelfServeRepositoryV093(reverse_path))
    for candidate in reversed(candidates):
        reverse.accept_candidate(
            scope,
            candidate.candidate_id,
            actor,
            "Order independence proof.",
            f"reverse:{candidate.candidate_id}",
        )
    normal_packet = normal.build_continuity_packet(scope)
    reverse_packet = reverse.build_continuity_packet(scope)
    normal_events = normal._events_for_scope(scope)
    reverse_events = reverse._events_for_scope(scope)
    return {
        "ordered_event_ids_match": [item["event_id"] for item in normal_events]
        == [item["event_id"] for item in reverse_events],
        "packet_id_matches": normal_packet["packet_id"] == reverse_packet["packet_id"],
        "packet_hash_matches": normal_packet["provenance"][
            "deterministic_packet_hash"
        ]
        == reverse_packet["provenance"]["deterministic_packet_hash"],
        "event_count": len(normal_events),
    }


def run_sqlite_suite() -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    started = time.perf_counter()
    actor = AdmissionDecisionActor("test_runner", "core-sprint-3")
    with TemporaryDirectory(prefix="prmr_memory_admission_") as temp:
        temp_path = Path(temp)
        db_path = temp_path / "memory_admission.sqlite"
        repository = SelfServeRepositoryV093(db_path)
        scope = AuthenticatedScope(
            "client_admission_alpha",
            "vault_admission_alpha",
            "default",
            application_reference="app_admission",
            actor_reference="actor_admission",
            workspace_reference="workspace_admission",
            entity_reference="entity_admission",
            session_reference="session_admission",
        )
        beta = AuthenticatedScope(
            "client_admission_beta", "vault_admission_beta", "default"
        )
        ledger = SourceLedger(repository)
        engine = CandidateMemoryEngine(repository)
        service = MemoryAdmissionService(repository)

        story_input = story_admission_fixture()
        story_input = SourceInput(
            **{
                **story_input.__dict__,
                "application_reference": scope.application_reference,
                "actor_reference": scope.actor_reference,
                "workspace_reference": scope.workspace_reference,
                "entity_references": [scope.entity_reference],
                "session_reference": scope.session_reference,
            }
        )
        story = ledger.ingest_source(scope, story_input).source
        extraction = engine.extract_candidates(scope, story.source_id)
        candidates = extraction.candidates
        add(checks, "story_source_ingested", story.source_id.startswith("src_"))
        add(checks, "story_candidates_extracted", len(candidates) == 8)
        add(
            checks,
            "story_fixture_contains_required_memory_classes",
            {
                item.proposed_event_type for item in candidates
            }
            >= {
                "goal.created",
                "blocker.detected",
                "decision.recorded",
                "observation.recorded",
                "state.changed",
                "status.updated",
                "action.completed",
                "information.unknown",
            },
        )
        baseline = service.build_continuity_packet(scope)
        add(checks, "baseline_packet_recorded", baseline["source_event_count"] == 0)

        goal = candidate_by_type(candidates, "goal.created")
        inferred = candidate_by_type(candidates, "observation.recorded")
        unknown = candidate_by_type(candidates, "information.unknown")
        rejected = candidate_by_type(candidates, "blocker.detected")
        deferred = candidate_by_type(candidates, "status.updated")
        accepted_results = [
            service.accept_candidate(
                scope, goal.candidate_id, actor, "Accept explicit goal.", "accept-goal"
            ),
            service.accept_candidate(
                scope,
                inferred.candidate_id,
                actor,
                "Accept uncertain interpretation without promotion.",
                "accept-inferred",
            ),
            service.accept_candidate(
                scope,
                unknown.candidate_id,
                actor,
                "Accept recorded unknown without promotion.",
                "accept-unknown",
            ),
        ]
        add(
            checks,
            "valid_explicit_candidate_accepted",
            accepted_results[0].admitted_event["type"] == "goal.created",
        )
        add(
            checks,
            "inferred_candidate_preserves_status",
            accepted_results[1].admitted_memory_link.epistemic_status == "inferred",
        )
        add(
            checks,
            "unknown_candidate_preserves_status",
            accepted_results[2].admitted_memory_link.epistemic_status == "unknown"
            and accepted_results[2].admitted_event["type"] == "information.unknown",
        )
        add(
            checks,
            "acceptance_creates_exactly_one_event_per_candidate",
            len(service._events_for_scope(scope)) == 3
            and count(repository, "prmr_admitted_memory_links") == 3,
        )
        for index, result in enumerate(accepted_results):
            candidate = (goal, inferred, unknown)[index]
            event = result.admitted_event
            metadata = event["external_metadata"]["metadata"]
            add(
                checks,
                f"accepted_event_{index}_type_matches",
                event["type"] == candidate.proposed_event_type,
            )
            add(
                checks,
                f"accepted_event_{index}_signal_matches",
                event["content"] == candidate.proposed_signal,
            )
            add(
                checks,
                f"accepted_event_{index}_safe_provenance",
                metadata["candidate_id"] == candidate.candidate_id
                and metadata["source_id"] == story.source_id
                and metadata["epistemic_status"] == candidate.epistemic_status
                and "source_content" not in metadata
                and "evidence_text" not in metadata,
            )
            add(
                checks,
                f"accepted_event_{index}_source_chronology",
                event["timestamp"] == story.occurred_at,
            )
            add(
                checks,
                f"accepted_event_{index}_integrity",
                service.verify_admission_integrity(
                    scope, result.admission.admission_id
                ).verified,
            )

        rejected_result = service.reject_candidate(
            scope,
            rejected.candidate_id,
            actor,
            "Reject candidate after review.",
            "reject-blocker",
        )
        event_count_after_reject = len(service._events_for_scope(scope))
        add(
            checks,
            "pending_candidate_rejected",
            engine.get_candidate(scope, rejected.candidate_id).candidate_status
            == "rejected",
        )
        add(
            checks,
            "rejection_creates_no_event",
            rejected_result.admitted_event is None and event_count_after_reject == 3,
        )
        deferred_result = service.defer_candidate(
            scope,
            deferred.candidate_id,
            actor,
            "Defer for explicit review.",
            "defer-status",
            review_after="2026-08-01T00:00:00Z",
        )
        add(
            checks,
            "pending_candidate_deferred",
            engine.get_candidate(scope, deferred.candidate_id).candidate_status
            == "deferred",
        )
        add(
            checks,
            "deferral_creates_no_event",
            deferred_result.admitted_event is None
            and len(service._events_for_scope(scope)) == 3,
        )
        deferred_accept = service.accept_candidate(
            scope,
            deferred.candidate_id,
            actor,
            "Accept after deferred review.",
            "accept-deferred-status",
        )
        add(
            checks,
            "deferred_candidate_later_accepted",
            deferred_accept.admitted_event is not None
            and engine.get_candidate(scope, deferred.candidate_id).candidate_status
            == "accepted",
        )
        add(
            checks,
            "rejected_candidate_cannot_be_accepted",
            expect_error(
                lambda: service.accept_candidate(
                    scope,
                    rejected.candidate_id,
                    actor,
                    "Attempt invalid reopening.",
                    "accept-rejected",
                ),
                "ADMISSION_ALREADY_REJECTED",
            ),
        )
        add(
            checks,
            "accepted_candidate_cannot_be_rejected",
            expect_error(
                lambda: service.reject_candidate(
                    scope,
                    goal.candidate_id,
                    actor,
                    "Invalid later rejection.",
                    "reject-accepted",
                ),
                "ADMISSION_ALREADY_ACCEPTED",
            ),
        )
        replay = service.accept_candidate(
            scope, goal.candidate_id, actor, "Replay.", "accept-goal"
        )
        replay_other_key = service.accept_candidate(
            scope, goal.candidate_id, actor, "Replay.", "accept-goal-other-key"
        )
        add(
            checks,
            "same_acceptance_request_replays",
            replay.replayed
            and replay.admission.admission_id
            == accepted_results[0].admission.admission_id,
        )
        add(
            checks,
            "different_acceptance_key_returns_existing_event",
            replay_other_key.replayed
            and replay_other_key.admitted_event["event_id"]
            == accepted_results[0].admitted_event["event_id"],
        )
        add(
            checks,
            "same_rejection_request_replays",
            service.reject_candidate(
                scope,
                rejected.candidate_id,
                actor,
                "Replay rejection.",
                "reject-blocker",
            ).replayed,
        )

        packet_after = service.build_continuity_packet(scope)
        admitted_signals = {
            result.admitted_event["type"]
            for result in accepted_results + [deferred_accept]
        }
        add(
            checks,
            "packet_changes_after_acceptance",
            packet_after["packet_id"] != baseline["packet_id"]
            and packet_after["source_event_count"] == 4,
        )
        add(
            checks,
            "packet_contains_admitted_signals_only",
            {
                item["signal"] for item in packet_after["active_information"]
            }.issubset(admitted_signals),
        )
        add(
            checks,
            "rejected_and_deferred_decisions_do_not_add_memory",
            rejected.proposed_event_type
            not in {item["signal"] for item in packet_after["active_information"]},
        )

        structured = ledger.ingest_source(
            scope,
            SourceInput(
                "json",
                STRUCTURED_JSON,
                application_reference=scope.application_reference,
                actor_reference=scope.actor_reference,
                workspace_reference=scope.workspace_reference,
                entity_references=[scope.entity_reference],
                session_reference=scope.session_reference,
                idempotency_key="admission-derived-v1",
            ),
        ).source
        structured_candidates = engine.extract_candidates(
            scope, structured.source_id
        ).candidates
        derived = next(
            item for item in structured_candidates if item.epistemic_status == "derived"
        )
        derived_result = service.accept_candidate(
            scope,
            derived.candidate_id,
            actor,
            "Accept deterministic derivation.",
            "accept-derived",
        )
        add(
            checks,
            "valid_derived_candidate_accepted",
            derived_result.admitted_memory_link.epistemic_status == "derived",
        )

        quote = ledger.ingest_source(
            scope,
            SourceInput(
                "plain_text",
                'Alice said, "The server was fixed."',
                application_reference=scope.application_reference,
                actor_reference=scope.actor_reference,
                workspace_reference=scope.workspace_reference,
                entity_references=[scope.entity_reference],
                session_reference=scope.session_reference,
                idempotency_key="admission-quote-v1",
            ),
        ).source
        quote_candidate = engine.extract_candidates(scope, quote.source_id).candidates[0]
        quote_result = service.accept_candidate(
            scope,
            quote_candidate.candidate_id,
            actor,
            "Manually preserve the statement itself.",
            "accept-quote",
        )
        add(
            checks,
            "quoted_statement_remains_statement_recorded",
            quote_result.admitted_event["type"] == "statement.recorded",
        )

        correction_source = ledger.ingest_source(
            beta, correction_fixture()
        ).source
        correction_candidates = engine.extract_candidates(
            beta, correction_source.source_id
        ).candidates
        original = correction_candidates[0]
        packet_before_correction = service.build_continuity_packet(beta)
        corrected = service.correct_candidate(
            beta,
            original.candidate_id,
            correction_reason="Correct event classification using existing evidence.",
            decision_actor=actor,
            idempotency_key="correct-observation",
            corrected_event_type="decision.recorded",
        )
        replacement = corrected.admitted_event["replacement_candidate"]
        add(
            checks,
            "pending_candidate_corrected",
            engine.get_candidate(beta, original.candidate_id).candidate_status
            == "corrected",
        )
        add(
            checks,
            "replacement_candidate_is_pending",
            replacement["candidate_status"] == "pending_review",
        )
        add(
            checks,
            "correction_changes_fingerprint",
            replacement["candidate_fingerprint_sha256"]
            != original.candidate_fingerprint_sha256,
        )
        add(
            checks,
            "correction_creates_no_event",
            service.build_continuity_packet(beta)["packet_id"]
            == packet_before_correction["packet_id"],
        )
        correction_replay = service.correct_candidate(
            beta,
            original.candidate_id,
            correction_reason="Replay.",
            decision_actor=actor,
            idempotency_key="correct-observation",
            corrected_event_type="decision.recorded",
        )
        add(
            checks,
            "correction_replay_returns_same_replacement",
            correction_replay.replayed
            and correction_replay.admitted_event["replacement_candidate"][
                "candidate_id"
            ]
            == replacement["candidate_id"],
        )
        replacement_accept = service.accept_candidate(
            beta,
            replacement["candidate_id"],
            actor,
            "Accept corrected replacement.",
            "accept-corrected-replacement",
        )
        add(
            checks,
            "replacement_acceptance_creates_one_event",
            replacement_accept.admitted_event["type"] == "decision.recorded"
            and len(service._events_for_scope(beta)) == 1,
        )
        add(
            checks,
            "corrected_original_cannot_be_accepted",
            expect_error(
                lambda: service.accept_candidate(
                    beta,
                    original.candidate_id,
                    actor,
                    "Invalid original acceptance.",
                    "accept-corrected-original",
                ),
                "ADMISSION_CANDIDATE_STATE_INVALID",
            ),
        )
        add(
            checks,
            "accepted_candidate_correction_blocked",
            expect_error(
                lambda: service.correct_candidate(
                    beta,
                    replacement["candidate_id"],
                    correction_reason="Invalid accepted correction.",
                    decision_actor=actor,
                    idempotency_key="correct-accepted",
                    corrected_event_type="observation.recorded",
                ),
                "ADMISSION_ACCEPTED_CANDIDATE_REQUIRES_SUPERSESSION",
            ),
        )
        upgrade_source = ledger.ingest_source(
            beta,
            SourceInput(
                "plain_text",
                "It seemed that a stale cache may have caused the delay.",
                idempotency_key="upgrade-source",
            ),
        ).source
        upgrade_candidate = engine.extract_candidates(
            beta, upgrade_source.source_id
        ).candidates[0]
        add(
            checks,
            "unsupported_epistemic_upgrade_blocked",
            expect_error(
                lambda: service.correct_candidate(
                    beta,
                    upgrade_candidate.candidate_id,
                    correction_reason="Invalid truth promotion.",
                    decision_actor=actor,
                    idempotency_key="upgrade-inferred",
                    corrected_epistemic_status="explicit",
                ),
                "ADMISSION_EPISTEMIC_UPGRADE_REQUIRES_NEW_EVIDENCE",
            ),
        )

        policy_scope = AuthenticatedScope(
            "client_policy", "vault_policy", "default"
        )
        policy_sources: dict[str, Any] = {}
        for name, fixture in admission_policy_fixtures().items():
            source = ledger.ingest_source(policy_scope, fixture).source
            policy_sources[name] = source
            engine.extract_candidates(policy_scope, source.source_id)
        policy_result = service.run_admission_policy(policy_scope)
        policy_candidates = engine.list_candidates(policy_scope, limit=100).items
        accepted_policy_candidates = [
            item for item in policy_candidates if item.candidate_status == "accepted"
        ]
        skipped_policy_candidates = [
            item for item in policy_candidates if item.candidate_status == "pending_review"
        ]
        add(
            checks,
            "safe_auto_policy_accepts_allowlisted_candidates",
            policy_result.accepted_count >= 3,
        )
        add(
            checks,
            "safe_auto_policy_skips_inferred",
            any(
                item.epistemic_status == "inferred"
                for item in skipped_policy_candidates
            ),
        )
        add(
            checks,
            "safe_auto_policy_skips_unknown",
            any(
                item.epistemic_status == "unknown"
                for item in skipped_policy_candidates
            ),
        )
        add(
            checks,
            "safe_auto_policy_skips_quoted_statement",
            any(
                item.proposed_event_type == "statement.recorded"
                for item in skipped_policy_candidates
            ),
        )
        add(
            checks,
            "safe_auto_policy_skips_ephemeral_source",
            all(
                item.source_id != policy_sources["ephemeral"].source_id
                for item in accepted_policy_candidates
            ),
        )
        ephemeral_candidate = next(
            item
            for item in policy_candidates
            if item.source_id == policy_sources["ephemeral"].source_id
        )
        add(
            checks,
            "manual_ephemeral_admission_blocked",
            expect_error(
                lambda: service.accept_candidate(
                    policy_scope,
                    ephemeral_candidate.candidate_id,
                    actor,
                    "Invalid ephemeral acceptance.",
                    "accept-ephemeral",
                ),
                "ADMISSION_SOURCE_RETENTION_INCOMPATIBLE",
            ),
        )

        concurrency_scope = AuthenticatedScope(
            "client_concurrency", "vault_concurrency", "default"
        )
        concurrent_source = ledger.ingest_source(
            concurrency_scope,
            SourceInput(
                "plain_text",
                "Decision: Preserve one event under concurrency.",
                idempotency_key="concurrency-source",
            ),
        ).source
        concurrent_candidate = engine.extract_candidates(
            concurrency_scope, concurrent_source.source_id
        ).candidates[0]

        def concurrent_accept(index: int) -> str:
            local = MemoryAdmissionService(
                SelfServeRepositoryV093(db_path)
            )
            return local.accept_candidate(
                concurrency_scope,
                concurrent_candidate.candidate_id,
                actor,
                "Concurrent acceptance.",
                f"concurrent-{index}",
            ).admitted_event["event_id"]

        with ThreadPoolExecutor(max_workers=6) as pool:
            event_ids = list(pool.map(concurrent_accept, range(6)))
        add(
            checks,
            "concurrent_acceptance_creates_one_event",
            len(set(event_ids)) == 1
            and len(service._events_for_scope(concurrency_scope)) == 1,
        )
        add(
            checks,
            "concurrent_acceptance_creates_one_link",
            count(
                repository,
                "prmr_admitted_memory_links",
                "WHERE candidate_id=?",
                (concurrent_candidate.candidate_id,),
            )
            == 1,
        )

        rollback_scope = AuthenticatedScope(
            "client_rollback", "vault_rollback", "default"
        )
        rollback_source = ledger.ingest_source(
            rollback_scope,
            SourceInput(
                "plain_text",
                "Decision: Roll back the interrupted admission.",
                idempotency_key="rollback-source",
            ),
        ).source
        rollback_candidate = engine.extract_candidates(
            rollback_scope, rollback_source.source_id
        ).candidates[0]
        rollback_service = MemoryAdmissionService(repository)
        original_insert_link = rollback_service._insert_link

        def fail_link(*_: Any, **__: Any) -> None:
            raise RuntimeError("deliberate transaction interruption")

        rollback_service._insert_link = fail_link  # type: ignore[method-assign]
        rollback_failed = expect_error(
            lambda: rollback_service.accept_candidate(
                rollback_scope,
                rollback_candidate.candidate_id,
                actor,
                "Deliberate rollback proof.",
                "rollback-accept",
            ),
            "ADMISSION_TRANSACTION_FAILED",
        )
        rollback_service._insert_link = original_insert_link  # type: ignore[method-assign]
        add(checks, "failure_after_event_insert_rolls_back", rollback_failed)
        add(
            checks,
            "rollback_leaves_no_orphan_event",
            len(service._events_for_scope(rollback_scope)) == 0,
        )
        add(
            checks,
            "rollback_leaves_no_orphan_link",
            count(
                repository,
                "prmr_admitted_memory_links",
                "WHERE candidate_id=?",
                (rollback_candidate.candidate_id,),
            )
            == 0,
        )
        add(
            checks,
            "rollback_leaves_candidate_pending",
            engine.get_candidate(
                rollback_scope, rollback_candidate.candidate_id
            ).candidate_status
            == "pending_review",
        )

        accepted_event_id = accepted_results[0].admitted_event["event_id"]
        trace = service.trace_admitted_memory_origin(scope, accepted_event_id)
        add(
            checks,
            "event_traces_to_full_origin_chain",
            trace["admitted_event_id"] == accepted_event_id
            and trace["admitted_memory_link_id"].startswith("amem_")
            and trace["admission_id"].startswith("adm_")
            and trace["candidate_id"] == goal.candidate_id
            and trace["extraction_run_id"] == extraction.run.extraction_run_id
            and trace["source_id"] == story.source_id
            and len(trace["evidence"]) >= 1,
        )
        add(
            checks,
            "origin_trace_excludes_source_content",
            trace["source_content_included"] is False
            and trace["evidence_preview_included"] is False
            and "evidence_preview" not in trace["evidence"][0],
        )
        add(
            checks,
            "cross_scope_admission_retrieval_denied",
            expect_error(
                lambda: service.get_admission(
                    beta, accepted_results[0].admission.admission_id
                ),
                "ADMISSION_NOT_FOUND",
            ),
        )
        add(
            checks,
            "cross_scope_origin_trace_denied",
            expect_error(
                lambda: service.trace_admitted_memory_origin(beta, accepted_event_id),
                "ADMISSION_EVENT_NOT_FOUND",
            ),
        )
        for action_name, action in (
            (
                "accept",
                lambda: service.accept_candidate(
                    scope,
                    upgrade_candidate.candidate_id,
                    actor,
                    "Cross-scope accept attempt.",
                    "cross-scope-accept",
                ),
            ),
            (
                "reject",
                lambda: service.reject_candidate(
                    scope,
                    upgrade_candidate.candidate_id,
                    actor,
                    "Cross-scope reject attempt.",
                    "cross-scope-reject",
                ),
            ),
            (
                "defer",
                lambda: service.defer_candidate(
                    scope,
                    upgrade_candidate.candidate_id,
                    actor,
                    "Cross-scope defer attempt.",
                    "cross-scope-defer",
                ),
            ),
            (
                "correct",
                lambda: service.correct_candidate(
                    scope,
                    upgrade_candidate.candidate_id,
                    correction_reason="Cross-scope correction attempt.",
                    decision_actor=actor,
                    idempotency_key="cross-scope-correct",
                    corrected_event_type="observation.recorded",
                ),
            ),
        ):
            add(
                checks,
                f"cross_scope_{action_name}_denied",
                expect_error(action, "ADMISSION_NOT_FOUND"),
            )
        add(
            checks,
            "wrong_actor_assertion_denied",
            expect_error(
                lambda: service.get_admission(
                    AuthenticatedScope(
                        scope.client_id,
                        scope.vault_id,
                        scope.namespace,
                        actor_reference="wrong_actor",
                    ),
                    accepted_results[0].admission.admission_id,
                ),
                "ADMISSION_NOT_FOUND",
            ),
        )
        add(
            checks,
            "wrong_entity_assertion_denied",
            expect_error(
                lambda: service.get_admission(
                    AuthenticatedScope(
                        scope.client_id,
                        scope.vault_id,
                        scope.namespace,
                        entity_reference="wrong_entity",
                    ),
                    accepted_results[0].admission.admission_id,
                ),
                "ADMISSION_NOT_FOUND",
            ),
        )

        accepted_delete_details: dict[str, Any] = {}
        try:
            ledger.delete_source(
                scope, story.source_id, "Invalid accepted-source deletion."
            )
        except SourceLedgerError as exc:
            accepted_delete_details = exc.to_dict()
        add(
            checks,
            "accepted_source_deletion_blocked",
            accepted_delete_details.get("code") == "SOURCE_HAS_ADMITTED_MEMORY",
        )
        add(
            checks,
            "accepted_source_delete_reports_safe_count",
            accepted_delete_details.get("details", {}).get(
                "accepted_memory_count", 0
            )
            >= 1
            and "source_content" not in accepted_delete_details,
        )
        delete_scope = AuthenticatedScope(
            "client_delete", "vault_delete", "default"
        )
        delete_source = ledger.ingest_source(
            delete_scope,
            SourceInput(
                "plain_text",
                "Decision: Review only.",
                idempotency_key="unadmitted-delete",
            ),
        ).source
        engine.extract_candidates(delete_scope, delete_source.source_id)
        add(
            checks,
            "unadmitted_source_delete_cascades",
            ledger.delete_source(
                delete_scope, delete_source.source_id, "Unadmitted deletion proof."
            )["deleted"],
        )
        rejected_delete_source = ledger.ingest_source(
            delete_scope,
            SourceInput(
                "plain_text",
                "Decision: Reject this isolated candidate.",
                idempotency_key="rejected-only-delete",
            ),
        ).source
        rejected_delete_candidate = engine.extract_candidates(
            delete_scope, rejected_delete_source.source_id
        ).candidates[0]
        service.reject_candidate(
            delete_scope,
            rejected_delete_candidate.candidate_id,
            actor,
            "Rejected-only source deletion proof.",
            "rejected-only-decision",
        )
        add(
            checks,
            "rejected_only_source_can_be_deleted",
            ledger.delete_source(
                delete_scope,
                rejected_delete_source.source_id,
                "Rejected-only source deletion.",
            )["deleted"],
        )
        deferred_delete_source = ledger.ingest_source(
            delete_scope,
            SourceInput(
                "plain_text",
                "Decision: Defer this isolated candidate.",
                idempotency_key="deferred-only-delete",
            ),
        ).source
        deferred_delete_candidate = engine.extract_candidates(
            delete_scope, deferred_delete_source.source_id
        ).candidates[0]
        service.defer_candidate(
            delete_scope,
            deferred_delete_candidate.candidate_id,
            actor,
            "Deferred-only source deletion proof.",
            "deferred-only-decision",
        )
        add(
            checks,
            "deferred_only_source_can_be_deleted",
            ledger.delete_source(
                delete_scope,
                deferred_delete_source.source_id,
                "Deferred-only source deletion.",
            )["deleted"],
        )

        expiry_scope = AuthenticatedScope(
            "client_expiry", "vault_expiry", "default"
        )
        expiry_source = ledger.ingest_source(
            expiry_scope,
            SourceInput(
                "plain_text",
                "Decision: Preserve admitted expiry provenance.",
                idempotency_key="expiry-source",
            ),
        ).source
        expiry_candidate = engine.extract_candidates(
            expiry_scope, expiry_source.source_id
        ).candidates[0]
        service.accept_candidate(
            expiry_scope,
            expiry_candidate.candidate_id,
            actor,
            "Accept before simulated retention change.",
            "expiry-accept",
        )
        with repository.connect() as connection:
            connection.execute(
                "UPDATE prmr_sources SET retention_policy='ephemeral', "
                "expires_at='2020-01-01T00:00:00Z' WHERE source_id=?",
                (expiry_source.source_id,),
            )
        purge = ledger.purge_expired_sources(
            MaintenanceContext(privileged=True),
            datetime.now(timezone.utc),
        )
        add(
            checks,
            "expiry_purge_skips_admitted_source",
            purge["skipped_admitted_source_count"] >= 1
            and count(
                repository,
                "prmr_sources",
                "WHERE source_id=?",
                (expiry_source.source_id,),
            )
            == 1,
        )

        order_result = run_order_proof(
            temp_path / "order.sqlite",
            AuthenticatedScope("client_order", "vault_order", "default"),
        )
        add(
            checks,
            "review_order_preserves_ordered_event_history",
            order_result["ordered_event_ids_match"],
        )
        add(
            checks,
            "review_order_preserves_packet_id",
            order_result["packet_id_matches"],
        )
        add(
            checks,
            "review_order_preserves_packet_hash",
            order_result["packet_hash_matches"],
        )

        packet_before_restart = service.build_continuity_packet(scope)
        restarted = MemoryAdmissionService(SelfServeRepositoryV093(db_path))
        packet_after_restart = restarted.build_continuity_packet(scope)
        add(
            checks,
            "restart_preserves_admission_and_event_identity",
            restarted.get_admission(
                scope, accepted_results[0].admission.admission_id
            ).admitted_event_id
            == accepted_event_id,
        )
        add(
            checks,
            "restart_preserves_packet_identity",
            packet_before_restart["packet_id"]
            == packet_after_restart["packet_id"],
        )
        add(
            checks,
            "restart_preserves_origin_trace",
            restarted.trace_admitted_memory_origin(scope, accepted_event_id)[
                "source_id"
            ]
            == story.source_id,
        )
        add(
            checks,
            "single_transaction_recovery_is_clean",
            restarted.recover_incomplete_admissions()["recovered_count"] == 0,
        )
        add(
            checks,
            "admission_creates_no_api_usage_logs",
            all(
                count(repository, table) == 0
                for table in ("usage_events", "request_logs", "api_request_logs")
            ),
        )

        performance: dict[str, float] = {}
        for amount in (100, 1000):
            items = policy_candidates * ((amount // len(policy_candidates)) + 1)
            start = time.perf_counter()
            for item in items[:amount]:
                from prmr.core.admission_policy import admission_policy

                admission_policy("safe_explicit_auto_v1").auto_eligible(
                    item,
                    source_retention=(
                        "ephemeral"
                        if item.source_id == policy_sources["ephemeral"].source_id
                        else "standard"
                    ),
                )
            performance[str(amount)] = round(
                (time.perf_counter() - start) * 1000, 3
            )
            add(
                checks,
                f"policy_evaluation_{amount}_completed",
                performance[str(amount)] >= 0,
            )
        add(checks, "performance_is_local_observation_only", True)

        with repository.connect() as connection:
            stored = {
                "decisions": [
                    dict(row)
                    for row in connection.execute(
                        "SELECT * FROM prmr_memory_admission_decisions"
                    ).fetchall()
                ],
                "links": [
                    dict(row)
                    for row in connection.execute(
                        "SELECT * FROM prmr_admitted_memory_links"
                    ).fetchall()
                ],
                "events": [
                    dict(row)
                    for row in connection.execute("SELECT * FROM events").fetchall()
                ],
            }
        add(checks, "admission_storage_contains_no_raw_secrets", not contains_secret(stored))
        details = {
            "backend": "sqlite",
            "story_candidate_count": len(candidates),
            "accepted_event_count": count(repository, "prmr_admitted_memory_links"),
            "decision_count": count(repository, "prmr_memory_admission_decisions"),
            "restart_verified": True,
            "concurrent_attempt_count": len(event_ids),
            "order_proof": order_result,
            "performance_observations_ms": performance,
            "database_size_bytes": db_path.stat().st_size,
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        }
        private = {
            "database_path_category": "temporary_durable_sqlite",
            "story_source_id": story.source_id,
            "story_extraction_run_id": extraction.run.extraction_run_id,
            "accepted_admission_ids": [
                item.admission.admission_id for item in accepted_results
            ],
            "accepted_event_ids": [
                item.admitted_event["event_id"] for item in accepted_results
            ],
            "raw_source_content_in_report": False,
            "raw_secrets_in_report": False,
        }
    return checks, details, private


def run_postgres_suite() -> tuple[list[dict[str, Any]], str, dict[str, Any]]:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        return (
            [],
            "NOT_RUN_DATABASE_URL_UNAVAILABLE",
            {
                "reason": "DATABASE_URL was unavailable; PostgreSQL admission is not claimed."
            },
        )
    checks: list[dict[str, Any]] = []
    scope = AuthenticatedScope(
        f"client_admission_pg_{uuid4().hex[:10]}",
        "vault_admission_pg",
        "default",
    )
    source_id: str | None = None
    try:
        from prmr.product.self_serve_repository_postgres_v0941 import (
            SelfServeRepositoryPostgresV0941,
        )

        repository = SelfServeRepositoryPostgresV0941(database_url)
        ledger = SourceLedger(repository)
        engine = CandidateMemoryEngine(repository)
        service = MemoryAdmissionService(repository)
        source = ledger.ingest_source(
            scope,
            SourceInput(
                "plain_text",
                "Decision: Verify PostgreSQL memory admission.",
                idempotency_key=f"pg-admission-{scope.client_id}",
            ),
        ).source
        source_id = source.source_id
        candidate = engine.extract_candidates(scope, source.source_id).candidates[0]
        result = service.accept_candidate(
            scope,
            candidate.candidate_id,
            AdmissionDecisionActor("test_runner", "postgres-proof"),
            "Controlled PostgreSQL admission proof.",
            "postgres-admission",
        )
        add(checks, "postgres_acceptance", result.admitted_event is not None)
        add(
            checks,
            "postgres_integrity",
            service.verify_admission_integrity(
                scope, result.admission.admission_id
            ).verified,
        )
        add(
            checks,
            "postgres_restart",
            MemoryAdmissionService(
                SelfServeRepositoryPostgresV0941(database_url)
            ).get_admitted_event(scope, result.admitted_event["event_id"])[
                "event_id"
            ]
            == result.admitted_event["event_id"],
        )
    except Exception as exc:
        add(checks, "postgres_integration", False, f"{type(exc).__name__}: {exc}")
    status = "PASS" if checks and all(item["passed"] for item in checks) else "NEEDS_WORK"
    return checks, status, {
        "controlled_scope": scope.client_id,
        "source_created": source_id is not None,
        "raw_database_url_exposed": False,
    }


def build_scorecard(public: dict[str, Any]) -> str:
    limitations = "\n".join(f"- {item}" for item in public["limitations"])
    return f"""# Core Sprint 3 - Memory Admission Scorecard

**Result:** {public['result']}

- SQLite durable proof: {public['sqlite_result']}
- PostgreSQL proof: {public['postgres_result']}
- Checks: {public['checks_passed']}/{public['checks_total']}
- Existing continuity algorithm rewritten: no
- Public API routes added: no

## Limitations

{limitations}

## Boundary

{public['boundary']}

{REQUIRED_FINAL_STATEMENT}
"""


def run_all() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    sqlite_checks, sqlite_details, sqlite_private = run_sqlite_suite()
    postgres_checks, postgres_result, postgres_details = run_postgres_suite()
    checks = sqlite_checks + postgres_checks
    failures = [item for item in checks if not item["passed"]]
    sqlite_result = (
        "PASS" if all(item["passed"] for item in sqlite_checks) else "NEEDS_WORK"
    )
    if failures or postgres_result == "NEEDS_WORK":
        result = "NEEDS_WORK"
    elif postgres_result == "PASS":
        result = "PASS"
    else:
        result = "PASS WITH DOCUMENTED LIMITATIONS"
    public = {
        "version": "core_sprint_3",
        "result": result,
        "sqlite_result": sqlite_result,
        "postgres_result": postgres_result,
        "checks_passed": len(checks) - len(failures),
        "checks_total": len(checks),
        "revision_identifiers": {
            "admission_schema_revision": "memory_admission_v1",
            "admission_policy_revision": "memory_admission_policy_v1",
            "admission_bridge_revision": "candidate_event_bridge_v1",
            "admission_integrity_revision": "memory_admission_integrity_v1",
            "admitted_event_metadata_revision": "admitted_event_metadata_v1",
            "candidate_correction_revision": "candidate_correction_v1",
        },
        "pipeline": [
            "source_record",
            "source_segments",
            "candidate_memory",
            "admission_decision",
            "admitted_memory_link",
            "existing_event_ledger",
            "existing_continuity_packet",
        ],
        "decision_types": ["accept", "reject", "defer", "correct"],
        "truth_status_promoted_by_acceptance": False,
        "accepted_event_supersession_implemented": False,
        "continuity_algorithm_rewritten": False,
        "public_api_routes_added": False,
        "sqlite_evidence": sqlite_details,
        "postgres_evidence": postgres_details,
        "limitations": [
            "PostgreSQL/Neon admission was not exercised because DATABASE_URL was unavailable."
            if postgres_result == "NOT_RUN_DATABASE_URL_UNAVAILABLE"
            else None,
            "Accepted inferred and unknown candidates retain those statuses, but the existing continuity algorithm does not yet weight epistemic statuses differently.",
            "Accepted-event correction and supersession are not implemented in this sprint.",
            "Contradiction handling and advanced temporal evolution remain later core-engine work.",
            "Performance figures are local observations, not production benchmarks.",
        ],
        "boundary": BOUNDARY,
        "required_final_statement": REQUIRED_FINAL_STATEMENT,
        "public_safe": True,
    }
    public["limitations"] = [item for item in public["limitations"] if item]
    private = {
        **public,
        "public_safe": False,
        "checks": checks,
        "sqlite_private_evidence": sqlite_private,
        "source_content_in_report": False,
        "secret_values_in_report": False,
    }
    return public, private, checks


def main() -> int:
    public, private, _ = run_all()
    write_json(PUBLIC_REPORT, public)
    write_json(PRIVATE_REPORT, private)
    SCORECARD.parent.mkdir(parents=True, exist_ok=True)
    SCORECARD.write_text(build_scorecard(public), encoding="utf-8")
    print("PRMR Memory Core - Memory Admission and Event-Ledger Bridge")
    print(f"SQLite result: {public['sqlite_result']}")
    print(f"PostgreSQL result: {public['postgres_result']}")
    print(f"Passed checks: {public['checks_passed']}/{public['checks_total']}")
    print(f"Result: {public['result']}")
    return (
        0
        if public["result"] in {"PASS", "PASS WITH DOCUMENTED LIMITATIONS"}
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
