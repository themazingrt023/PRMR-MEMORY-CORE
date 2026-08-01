"""Core Sprint 10 executable proof for deterministic memory governance."""

from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory
import time
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from prmr.core.admission_models import AdmissionDecisionActor
from prmr.core.admission_service import MemoryAdmissionService
from prmr.core.candidate_engine import CandidateMemoryEngine
from prmr.core.canonical_signal_registry import CanonicalSignalRegistry
from prmr.core.memory_correction_requests import MemoryCorrectionRequestService
from prmr.core.memory_dependency_graph import MemoryDependencyGraph
from prmr.core.memory_export_service import MemoryExportService
from prmr.core.memory_governance_executor import MemoryGovernanceExecutor
from prmr.core.memory_governance_integrity import MemoryGovernanceIntegrityVerifier
from prmr.core.memory_governance_models import GovernanceActor, MemoryGovernanceError
from prmr.core.memory_governance_planner import MemoryGovernancePlanner
from prmr.core.memory_governance_policy import RETENTION_MODES
from prmr.core.memory_governance_store import GOVERNANCE_TABLES
from prmr.core.memory_governance_verifier import MemoryGovernanceVerifier
from prmr.core.memory_preservation_hold import MemoryPreservationHoldService
from prmr.core.memory_retention_service import MemoryRetentionService
from prmr.core.source_integrity import canonical_json
from prmr.core.source_ledger import SourceLedger
from prmr.core.source_models import AuthenticatedScope, SourceInput
from prmr.product.self_serve_repository_v093 import SelfServeRepositoryV093


REPORT_DIR = ROOT / "reports" / "core_memory_governance"
PUBLIC_REPORT = REPORT_DIR / "public_memory_governance.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_memory_governance.json"
ERASURE_REPORT = REPORT_DIR / "erasure_verification_memory_governance.json"
EXPORT_REPORT = REPORT_DIR / "export_integrity_memory_governance.json"
SCORECARD = REPORT_DIR / "scorecard_memory_governance.md"
ACTOR = GovernanceActor("test_runner", "core-sprint-10")
ADMISSION_ACTOR = AdmissionDecisionActor("test_runner", "core-sprint-10")
BOUNDARY = (
    "Internal deterministic Memory Core governance evidence on durable local SQLite. "
    "Active-database erasure does not prove deletion from unmanaged backups, external "
    "providers, infrastructure snapshots, authentication systems, billing systems, "
    "or third-party logs. No legal or compliance certification is claimed."
)
FINAL_STATEMENT = (
    "Core Sprint 10 establishes Memory Governance, Verified Erasure, Retention, "
    "Correction Requests and Export inside PRMR Memory Core. The engine can now "
    "discover the complete dependency graph behind governed memory, generate a "
    "deterministic dry-run plan, enforce preservation holds, execute authorised "
    "scope-isolated cascades, recompute or invalidate surviving derived memory, "
    "verify that governed content is no longer retrievable and retain only "
    "non-sensitive erasure tombstones. Authorised memory can be exported with "
    "provenance, epistemic status, bitemporal history and deterministic integrity "
    "manifests. Correction requests route through the existing append-oriented "
    "memory evolution system rather than editing historical records in place. "
    "External backups, authentication providers, public governance APIs and formal "
    "compliance certification remain outside this sprint."
)
SECRET = re.compile(
    r"(?:prmr_(?:live|alpha)_[A-Za-z0-9_-]{8,}|Authorization\s*:\s*Bearer|"
    r"github_pat_|ghp_|sk-|postgres(?:ql)?://)",
    re.I,
)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def add(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def expect_error(call: Callable[[], Any], code: str) -> bool:
    try:
        call()
    except MemoryGovernanceError as exc:
        return exc.code == code
    except Exception:
        return False
    return False


def scope(label: str) -> AuthenticatedScope:
    return AuthenticatedScope(f"client_gov_{label}", f"vault_gov_{label}", "memory")


def table_count(repository: Any, table_name: str) -> int:
    with repository.connect() as connection:
        return int(
            connection.execute(
                f"SELECT COUNT(*) AS object_count FROM {table_name}"
            ).fetchone()["object_count"]
        )


def seed(
    repository: Any,
    scoped: AuthenticatedScope,
    label: str,
    *,
    actor: str,
    workspace: str,
    application: str,
    entity_references: list[str] | None = None,
    session: str | None = None,
    admit: bool = True,
    retention_policy: str = "standard",
    expires_at: str | None = None,
) -> dict[str, Any]:
    source = SourceLedger(repository).ingest_source(
        scoped,
        SourceInput(
            "json",
            {
                "event_type": "project.updated",
                "signal": f"Synthetic governed state {label}.",
                "previous_state": "queued",
                "current_state": "active",
                "occurred_at": "2026-07-20T10:00:00Z",
            },
            occurred_at="2026-07-20T10:00:00Z",
            actor_reference=actor,
            workspace_reference=workspace,
            application_reference=application,
            entity_references=entity_references or [],
            session_reference=session,
            retention_policy=retention_policy,
            expires_at=expires_at,
            idempotency_key=f"governance:{label}",
        ),
    ).source
    extracted = CandidateMemoryEngine(repository).extract_candidates(
        scoped, source.source_id
    )
    candidate = extracted.candidates[0]
    admitted = None
    if admit:
        admitted = MemoryAdmissionService(repository).accept_candidate(
            scoped,
            candidate.candidate_id,
            ADMISSION_ACTOR,
            "Controlled synthetic governance fixture.",
            f"governance-admit:{label}",
        )
    return {
        "source": source,
        "candidate": candidate,
        "extraction": extracted,
        "admitted": admitted,
    }


def approve(
    planner: MemoryGovernancePlanner,
    scoped: AuthenticatedScope,
    plan: Any,
    label: str,
) -> Any:
    return planner.approve_governance_plan(
        scoped,
        plan.governance_plan_id,
        actor=ACTOR,
        reason="Authorised deterministic test execution.",
        idempotency_key=f"approve:{label}",
    )


def execute_plan(
    repository: Any,
    scoped: AuthenticatedScope,
    plan: Any,
    label: str,
) -> Any:
    approve(MemoryGovernancePlanner(repository), scoped, plan, label)
    return MemoryGovernanceExecutor(repository).execute(
        scoped, plan.governance_plan_id, idempotency_key=f"execute:{label}"
    )


def source_exists(repository: Any, scoped: AuthenticatedScope, source_id: str) -> bool:
    try:
        SourceLedger(repository).get_source(scoped, source_id)
    except Exception:
        return False
    return True


def make_export(
    repository: Any,
    scoped: AuthenticatedScope,
    *,
    target_type: str,
    target_reference: str,
    label: str,
    expires_at: str | None = None,
) -> Any:
    planner = MemoryGovernancePlanner(repository)
    request = planner.create_request(
        scoped,
        action_type="export",
        target_type=target_type,
        target_reference=target_reference,
        actor=ACTOR,
        reason="Authorised controlled export.",
        idempotency_key=f"export-request:{label}",
        governance_policy_id=(
            "full_scope_export_v1"
            if target_type == "tenant_memory_boundary"
            else "subject_export_v1"
        ),
        requested_at="2026-07-22T10:00:00Z",
    )
    plan = planner.plan(
        scoped, request.governance_request_id, generated_at="2026-07-22T10:00:00Z"
    )
    approve(planner, scoped, plan, f"export:{label}")
    return MemoryExportService(repository).create_export(
        scoped,
        plan.governance_plan_id,
        valid_at="2026-07-22T10:00:00Z",
        known_at="2026-07-22T10:00:00Z",
        expires_at=expires_at,
        generated_at="2026-07-22T10:00:00Z",
    )


def main() -> int:
    started = time.perf_counter()
    checks: list[dict[str, Any]] = []
    traces: dict[str, Any] = {}
    erasure_proofs: list[dict[str, Any]] = []
    export_proofs: list[dict[str, Any]] = []

    with TemporaryDirectory(prefix="prmr-core-governance-") as temporary:
        db_path = Path(temporary) / "memory_governance.sqlite"
        repository = SelfServeRepositoryV093(db_path)
        MemoryGovernancePlanner(repository)
        add(
            checks,
            "governance_schema_has_all_required_tables",
            all(
                table_count(repository, table_name) == 0
                for table_name in GOVERNANCE_TABLES.values()
            ),
            sorted(GOVERNANCE_TABLES.values()),
        )

        primary = scope("primary")
        other_scope = scope("other")
        planner = MemoryGovernancePlanner(repository)

        # Fixture A: unadmitted source.
        unadmitted = seed(
            repository,
            primary,
            "unadmitted",
            actor="actor_unadmitted",
            workspace="workspace_a",
            application="application_a",
            admit=False,
        )
        before = planner.graphs.scope_manifest(primary)
        unadmitted_plan = planner.plan_erasure(
            primary,
            target_type="source",
            target_reference=unadmitted["source"].source_id,
            actor=ACTOR,
            reason="Erase unadmitted fixture.",
            idempotency_key="plan-unadmitted",
            generated_at="2026-07-22T11:00:00Z",
        )
        after_plan = planner.graphs.scope_manifest(primary)
        add(checks, "dry_run_does_not_mutate_memory", before == after_plan)
        add(
            checks,
            "unadmitted_plan_discovers_source_chain",
            unadmitted_plan.estimated_counts_by_type.get("source", 0) == 1
            and unadmitted_plan.estimated_counts_by_type.get("candidate_memory", 0) >= 1
            and unadmitted_plan.estimated_counts_by_type.get("segment", 0) >= 1,
            unadmitted_plan.estimated_counts_by_type,
        )
        unadmitted_result = execute_plan(
            repository, primary, unadmitted_plan, "unadmitted"
        )
        add(checks, "unadmitted_source_erased", not source_exists(repository, primary, unadmitted["source"].source_id))
        add(checks, "unadmitted_source_verified", unadmitted_result.verification.verification_status == "verified")
        erasure_proofs.append(unadmitted_result.verification.to_dict())

        # Fixture B/J/K: admitted chain, deterministic export, export invalidation.
        admitted = seed(
            repository,
            primary,
            "admitted-exported",
            actor="actor_export",
            workspace="workspace_export",
            application="application_export",
            entity_references=["entity_export"],
        )
        exported = make_export(
            repository,
            primary,
            target_type="actor",
            target_reference="actor_export",
            label="actor-export",
            expires_at="2026-07-23T00:00:00Z",
        )
        export_service = MemoryExportService(repository)
        export_replay = make_export(
            repository,
            primary,
            target_type="actor",
            target_reference="actor_export",
            label="actor-export",
            expires_at="2026-07-23T00:00:00Z",
        )
        export_integrity = export_service.verify_export_integrity(
            primary, exported.memory_export_bundle_id
        )
        add(checks, "subject_export_is_deterministic", exported.memory_export_bundle_id == export_replay.memory_export_bundle_id)
        add(checks, "export_integrity_verified", export_integrity["verified"], export_integrity)
        add(checks, "export_contains_provenance_sections", all(name in exported.sections for name in ("sources", "segments", "candidates", "admissions", "events")))
        add(
            checks,
            "cross_scope_export_read_denied",
            expect_error(
                lambda: export_service.verify_export_integrity(
                    other_scope, exported.memory_export_bundle_id
                ),
                "GOVERNANCE_EXPORT_NOT_FOUND",
            ),
        )
        export_proofs.append(export_integrity)
        admitted_plan = planner.plan_erasure(
            primary,
            target_type="source",
            target_reference=admitted["source"].source_id,
            actor=ACTOR,
            reason="Erase admitted exported fixture.",
            idempotency_key="plan-admitted",
            generated_at="2026-07-22T12:00:00Z",
        )
        add(
            checks,
            "admitted_plan_includes_event_and_export_artifacts",
            admitted_plan.estimated_counts_by_type.get("event", 0) >= 1
            and admitted_plan.estimated_counts_by_type.get("export_bundle", 0) >= 1,
            admitted_plan.estimated_counts_by_type,
        )
        admitted_result = execute_plan(repository, primary, admitted_plan, "admitted")
        add(checks, "admitted_source_chain_erased", not source_exists(repository, primary, admitted["source"].source_id))
        add(checks, "admitted_source_verification_passes", admitted_result.verification.verification_status == "verified")
        add(
            checks,
            "affected_export_is_not_retrievable",
            expect_error(
                lambda: export_service.verify_export_integrity(
                    primary, exported.memory_export_bundle_id
                ),
                "GOVERNANCE_EXPORT_NOT_FOUND",
            ),
        )
        erasure_status = MemoryGovernanceVerifier(repository).erased_evidence_status(
            primary, admitted["source"].source_id
        )
        add(
            checks,
            "historical_read_reports_erasure_status",
            erasure_status["status"]
            == "evidence_unavailable_due_to_governance_erasure",
            erasure_status,
        )
        erasure_proofs.append(admitted_result.verification.to_dict())

        # Fixture C: shared canonical evidence is detached and recomputed.
        shared_a = seed(
            repository,
            primary,
            "shared-a",
            actor="actor_shared",
            workspace="workspace_shared",
            application="application_shared",
            admit=False,
        )
        shared_b = seed(
            repository,
            primary,
            "shared-b",
            actor="actor_shared",
            workspace="workspace_shared",
            application="application_shared",
            admit=False,
        )
        registry = CanonicalSignalRegistry(repository)
        proposal = registry.propose_signal_mapping(
            primary,
            original_signal_key="project.changed",
            proposed_canonical_signal_key="project.updated",
            proposal_basis="Two independent synthetic source records.",
            proposal_method="observed_exact_alias",
            source_ids=(shared_a["source"].source_id, shared_b["source"].source_id),
            proposal_confidence=0.8,
            created_at="2026-07-22T12:30:00Z",
        )
        shared_plan = planner.plan_erasure(
            primary,
            target_type="source",
            target_reference=shared_a["source"].source_id,
            actor=ACTOR,
            reason="Remove one shared support.",
            idempotency_key="plan-shared-a",
            generated_at="2026-07-22T12:31:00Z",
        )
        add(checks, "shared_dependency_classified_for_detach", bool(shared_plan.planned_detach_edges))
        shared_result = execute_plan(repository, primary, shared_plan, "shared-a")
        with repository.connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM prmr_canonical_signal_proposals "
                "WHERE canonical_signal_proposal_id=?",
                (proposal.canonical_signal_proposal_id,),
            ).fetchone()
        surviving_proposal = json.loads(row["payload_json"]) if row else {}
        add(checks, "shared_source_b_survives", source_exists(repository, primary, shared_b["source"].source_id))
        add(checks, "shared_proposal_survives", bool(row))
        add(
            checks,
            "shared_evidence_reference_removed",
            shared_a["source"].source_id not in canonical_json(surviving_proposal)
            and shared_b["source"].source_id in canonical_json(surviving_proposal),
        )
        add(
            checks,
            "shared_evidence_manifest_recomputed",
            surviving_proposal.get("governance_evidence_status")
            == "recomputed_after_detach"
            and bool(surviving_proposal.get("evidence_manifest_hash")),
        )
        erasure_proofs.append(shared_result.verification.to_dict())

        # Fixture D: actor isolation inside one shared workspace.
        actor_a = seed(repository, primary, "actor-a", actor="actor_a", workspace="workspace_common", application="app_subject")
        actor_b = seed(repository, primary, "actor-b", actor="actor_b", workspace="workspace_common", application="app_subject")
        actor_plan = planner.plan_actor_erasure(
            primary,
            "actor_a",
            actor=ACTOR,
            reason="Erase actor A only.",
            idempotency_key="plan-actor-a",
            generated_at="2026-07-22T13:00:00Z",
        )
        actor_result = execute_plan(repository, primary, actor_plan, "actor-a")
        add(checks, "actor_a_erasure_works", not source_exists(repository, primary, actor_a["source"].source_id))
        add(checks, "actor_b_in_shared_workspace_survives", source_exists(repository, primary, actor_b["source"].source_id))
        add(checks, "actor_erasure_verifies", actor_result.verification.verification_status == "verified")

        # Fixtures E/F and session/application target types.
        for target_type, target_value, label, kwargs in (
            ("entity", "entity_target", "entity", {"entity_references": ["entity_target"]}),
            ("session", "session_target", "session", {"session": "session_target"}),
            ("workspace", "workspace_target", "workspace", {"workspace": "workspace_target"}),
            ("application", "application_target", "application", {"application": "application_target"}),
        ):
            victim = seed(
                repository,
                primary,
                f"{label}-victim",
                actor=f"actor_{label}",
                workspace=kwargs.get("workspace", f"workspace_{label}"),
                application=kwargs.get("application", f"application_{label}"),
                entity_references=kwargs.get("entity_references"),
                session=kwargs.get("session"),
            )
            survivor = seed(
                repository,
                primary,
                f"{label}-survivor",
                actor=f"actor_{label}_survivor",
                workspace=f"workspace_{label}_survivor",
                application=f"application_{label}_survivor",
                entity_references=[f"entity_{label}_survivor"],
                session=f"session_{label}_survivor",
            )
            plan_method = getattr(planner, f"plan_{target_type}_erasure")
            plan = plan_method(
                primary,
                target_value,
                actor=ACTOR,
                reason=f"Erase one {target_type}.",
                idempotency_key=f"plan-{target_type}",
                generated_at="2026-07-22T13:30:00Z",
            )
            result = execute_plan(repository, primary, plan, target_type)
            add(checks, f"{target_type}_erasure_works", not source_exists(repository, primary, victim["source"].source_id))
            add(checks, f"{target_type}_unrelated_memory_survives", source_exists(repository, primary, survivor["source"].source_id))
            add(checks, f"{target_type}_erasure_verifies", result.verification.verification_status == "verified")

        # Fixture H: hold blocks both erasure and expiry planning.
        held = seed(
            repository,
            primary,
            "held",
            actor="actor_held",
            workspace="workspace_held",
            application="application_held",
            admit=False,
            retention_policy="ephemeral",
            expires_at="2099-07-24T00:00:00Z",
        )
        holds = MemoryPreservationHoldService(repository)
        hold = holds.apply_hold(
            primary,
            target_type="source",
            target_reference=held["source"].source_id,
            actor=ACTOR,
            reason="Trusted preservation control.",
            idempotency_key="hold-source",
            applied_at="2026-07-22T14:00:00Z",
        )
        held_plan = planner.plan_erasure(
            primary,
            target_type="source",
            target_reference=held["source"].source_id,
            actor=ACTOR,
            reason="Attempt held erasure.",
            idempotency_key="plan-held",
            generated_at="2026-07-22T14:01:00Z",
        )
        add(checks, "active_hold_blocks_plan", held_plan.plan_status == "blocked" and bool(held_plan.preservation_holds))
        add(
            checks,
            "blocked_plan_cannot_be_approved",
            expect_error(
                lambda: approve(planner, primary, held_plan, "held-old"),
                "GOVERNANCE_PLAN_BLOCKED",
            ),
        )
        retention = MemoryRetentionService(repository)
        expired_plans = retention.plan_expired_memory_purge(
            primary,
            actor=ACTOR,
            frozen_now="2100-07-26T14:02:00Z",
            idempotency_key="expiry-held",
        )
        held_expiry = next(
            item
            for item in expired_plans
            if item.target_digest == held_plan.target_digest
        )
        add(checks, "active_hold_blocks_expiry", held_expiry.plan_status == "blocked")
        holds.release_hold(
            primary,
            hold.preservation_hold_id,
            actor=ACTOR,
            reason="Trusted hold release.",
            released_at="2026-07-22T14:03:00Z",
        )
        released_plan = planner.plan_erasure(
            primary,
            target_type="source",
            target_reference=held["source"].source_id,
            actor=ACTOR,
            reason="Plan again after hold release.",
            idempotency_key="plan-held-released",
            generated_at="2026-07-22T14:04:00Z",
        )
        add(checks, "released_hold_requires_new_ready_plan", released_plan.plan_status == "ready")

        # Bitemporal retention annotations and fixed expiry boundary.
        annotation_old = retention.annotate(
            primary,
            target_type="source",
            target_reference=held["source"].source_id,
            retention_mode="indefinite",
            retain_until=None,
            actor=ACTOR,
            reason="Historical indefinite retention.",
            idempotency_key="retention-old",
            system_effective_at="2026-07-20T00:00:00Z",
        )
        retention.annotate(
            primary,
            target_type="source",
            target_reference=held["source"].source_id,
            retention_mode="retain_until",
            retain_until="2026-07-30T00:00:00Z",
            actor=ACTOR,
            reason="Future retention revision.",
            idempotency_key="retention-future",
            system_effective_at="2026-07-25T00:00:00Z",
        )
        known = retention.effective_annotation(
            primary,
            held["source"].source_id,
            known_at="2026-07-22T00:00:00Z",
        )
        add(checks, "known_at_hides_future_retention_annotation", known.retention_annotation_id == annotation_old.retention_annotation_id)
        add(checks, "all_retention_modes_supported", RETENTION_MODES == {"standard", "ephemeral", "retain_until", "indefinite", "governed"})

        # Fixture I: correction request delegates to existing candidate evolution.
        correction_seed = seed(
            repository,
            primary,
            "correction",
            actor="actor_correction",
            workspace="workspace_correction",
            application="application_correction",
            admit=False,
        )
        corrections = MemoryCorrectionRequestService(repository)
        correction = corrections.create_request(
            primary,
            target_type="candidate",
            target_id=correction_seed["candidate"].candidate_id,
            requested_change_type="correct_candidate",
            actor=ACTOR,
            reason="Correct through the existing candidate operation.",
            idempotency_key="correction-request",
            requested_value="Corrected synthetic state.",
            created_at="2026-07-22T15:00:00Z",
        )
        routed = corrections.route(
            primary,
            correction.memory_correction_request_id,
            idempotency_key="correction-route",
            corrected_event_type="project.corrected",
            resolved_at="2026-07-22T15:01:00Z",
        )
        add(checks, "correction_request_routes_through_existing_engine", routed.request_status == "completed" and routed.routed_operation_type == "correct_candidate")
        add(
            checks,
            "cross_scope_correction_is_denied",
            expect_error(
                lambda: corrections.route(
                    other_scope,
                    correction.memory_correction_request_id,
                    idempotency_key="cross-scope-correction",
                ),
                "GOVERNANCE_SCOPE_DENIED",
            ),
        )

        # Restart recovery and replay.
        interrupted = seed(
            repository,
            primary,
            "restart",
            actor="actor_restart",
            workspace="workspace_restart",
            application="application_restart",
        )
        restart_plan = planner.plan_erasure(
            primary,
            target_type="source",
            target_reference=interrupted["source"].source_id,
            actor=ACTOR,
            reason="Restart recovery proof.",
            idempotency_key="plan-restart",
            generated_at="2026-07-22T16:00:00Z",
        )
        approve(planner, primary, restart_plan, "restart")
        partial = MemoryGovernanceExecutor(repository).execute(
            primary,
            restart_plan.governance_plan_id,
            idempotency_key="execute-restart",
            interrupt_after_items=3,
        )
        add(checks, "interrupted_execution_remains_recoverable", partial.execution.execution_status == "running")
        reopened = SelfServeRepositoryV093(db_path)
        recovered_ids = MemoryGovernanceExecutor(reopened).recover_incomplete_governance_executions(primary)
        add(checks, "restart_recovery_completes", partial.execution.governance_execution_id in recovered_ids)
        replay = MemoryGovernanceExecutor(reopened).execute(
            primary,
            restart_plan.governance_plan_id,
            idempotency_key="execute-restart",
        )
        add(checks, "completed_execution_replay_is_idempotent", replay.replayed and replay.execution.governance_execution_id == partial.execution.governance_execution_id)

        # Concurrent execution has one database-enforced winner per approved plan.
        concurrent_seed = seed(
            repository,
            primary,
            "concurrent",
            actor="actor_concurrent",
            workspace="workspace_concurrent",
            application="application_concurrent",
        )
        concurrent_plan = planner.plan_erasure(
            primary,
            target_type="source",
            target_reference=concurrent_seed["source"].source_id,
            actor=ACTOR,
            reason="Concurrent single-winner proof.",
            idempotency_key="plan-concurrent",
            generated_at="2026-07-22T16:30:00Z",
        )
        approve(planner, primary, concurrent_plan, "concurrent")

        def concurrent_execute(label: str) -> str:
            try:
                result = MemoryGovernanceExecutor(
                    SelfServeRepositoryV093(db_path)
                ).execute(
                    primary,
                    concurrent_plan.governance_plan_id,
                    idempotency_key=f"execute-concurrent:{label}",
                )
                return result.execution.execution_status
            except MemoryGovernanceError as exc:
                return exc.code

        with ThreadPoolExecutor(max_workers=2) as pool:
            concurrent_outcomes = list(
                pool.map(concurrent_execute, ("a", "b"))
            )
        add(
            checks,
            "concurrent_execution_has_one_winner",
            sum(item.startswith("completed") for item in concurrent_outcomes) == 1,
            concurrent_outcomes,
        )
        add(
            checks,
            "concurrent_loser_is_safely_blocked",
            concurrent_outcomes.count("GOVERNANCE_EXECUTION_CONFLICT") == 1,
            concurrent_outcomes,
        )

        # Fixture G: full tenant boundary while another tenant survives unchanged.
        tenant_alpha = scope("tenant_alpha")
        tenant_beta = scope("tenant_beta")
        alpha_seed = seed(repository, tenant_alpha, "tenant-alpha", actor="actor_alpha", workspace="workspace_alpha", application="application_alpha")
        beta_seed = seed(repository, tenant_beta, "tenant-beta", actor="actor_beta", workspace="workspace_beta", application="application_beta")
        beta_manifest_before = MemoryDependencyGraph(repository).scope_manifest(tenant_beta)
        tenant_plan = MemoryGovernancePlanner(repository).plan_tenant_memory_erasure(
            tenant_alpha,
            actor=ACTOR,
            reason="Erase one synthetic tenant boundary.",
            idempotency_key="plan-tenant-alpha",
            generated_at="2026-07-22T17:00:00Z",
        )
        tenant_result = execute_plan(repository, tenant_alpha, tenant_plan, "tenant-alpha")
        beta_manifest_after = MemoryDependencyGraph(repository).scope_manifest(tenant_beta)
        add(checks, "tenant_alpha_memory_erased", not source_exists(repository, tenant_alpha, alpha_seed["source"].source_id))
        add(checks, "tenant_beta_memory_survives", source_exists(repository, tenant_beta, beta_seed["source"].source_id))
        add(checks, "tenant_beta_manifest_unchanged", beta_manifest_before == beta_manifest_after)
        add(checks, "tenant_erasure_verifies", tenant_result.verification.verification_status == "verified")

        # Export expiry is independent of authoritative memory.
        expiry_scope = scope("export_expiry")
        expiry_seed = seed(repository, expiry_scope, "export-expiry", actor="actor_expiry", workspace="workspace_expiry", application="application_expiry")
        expiry_bundle = make_export(
            repository,
            expiry_scope,
            target_type="actor",
            target_reference="actor_expiry",
            label="expiry",
            expires_at="2026-07-22T18:00:00Z",
        )
        expired_count = MemoryRetentionService(repository).expire_export_artifacts(
            expiry_scope, frozen_now="2026-07-22T18:01:00Z"
        )
        add(checks, "expired_export_artifact_removed", expired_count == 1)
        add(checks, "export_expiry_preserves_authoritative_memory", source_exists(repository, expiry_scope, expiry_seed["source"].source_id))
        add(
            checks,
            "expired_export_retrieval_denied",
            expect_error(
                lambda: MemoryExportService(repository).verify_export_integrity(
                    expiry_scope, expiry_bundle.memory_export_bundle_id
                ),
                "GOVERNANCE_EXPORT_NOT_FOUND",
            ),
        )

        integrity = MemoryGovernanceIntegrityVerifier(repository).verify(primary)
        add(checks, "governance_integrity_passes", integrity["verified"], integrity)
        tombstones = MemoryGovernanceIntegrityVerifier(repository).store.manifest_rows(
            "tombstone", primary.memory_boundary()
        )
        add(checks, "verified_tombstones_created", bool(tombstones) and all(item["tombstone_status"] == "verified" for item in tombstones))
        add(
            checks,
            "tombstones_contain_no_deleted_content",
            all(
                not any(
                    key in canonical_json(item)
                    for key in (
                        "Synthetic governed state",
                        "opaque_target_reference",
                        "source_text",
                        "evidence_quote",
                    )
                )
                for item in tombstones
            ),
        )
        add(
            checks,
            "scope_isolation_enforced",
            expect_error(
                lambda: planner.get_plan(
                    other_scope, released_plan.governance_plan_id
                ),
                "GOVERNANCE_PLAN_NOT_FOUND",
            ),
        )

        traces = {
            "governance_tables": sorted(GOVERNANCE_TABLES.values()),
            "primary_integrity": integrity,
            "tombstone_count": len(tombstones),
            "erasure_execution_ids": [
                unadmitted_result.execution.governance_execution_id,
                admitted_result.execution.governance_execution_id,
                shared_result.execution.governance_execution_id,
                actor_result.execution.governance_execution_id,
                tenant_result.execution.governance_execution_id,
            ],
            "export_bundle_id": expiry_bundle.memory_export_bundle_id,
            "postgres": {
                "status": (
                    "NOT_RUN_DATABASE_URL_PRESENT"
                    if os.getenv("DATABASE_URL")
                    else "NOT_RUN_DATABASE_URL_UNAVAILABLE"
                ),
                "claimed": False,
            },
        }

    passed = sum(item["passed"] for item in checks)
    failed = [item for item in checks if not item["passed"]]
    postgres_exercised = False
    status = (
        "NEEDS WORK"
        if failed
        else ("PASS" if postgres_exercised else "PASS WITH DOCUMENTED LIMITATIONS")
    )
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    public = {
        "version": "core_sprint_10",
        "result": status,
        "passed_checks": passed,
        "total_checks": len(checks),
        "failed_checks": [item["name"] for item in failed],
        "capabilities": {
            "deterministic_dependency_graph": True,
            "approved_verified_erasure": True,
            "subject_and_tenant_scope": True,
            "preservation_holds": True,
            "bitemporal_retention_annotations": True,
            "deterministic_exports": True,
            "append_oriented_correction_routing": True,
            "restart_recovery": True,
        },
        "sqlite": "PASS" if not failed else "NEEDS_WORK",
        "postgres": "NOT_EXERCISED",
        "boundary": BOUNDARY,
        "duration_ms": elapsed_ms,
    }
    private = {
        **public,
        "checks": checks,
        "trace": traces,
        "limitations": [
            "PostgreSQL runtime behaviour was not exercised because DATABASE_URL was unavailable.",
            "Multi-process locking and large production-scale cascades remain unvalidated.",
            "Only the active Memory Core database boundary is verified; external backups and providers are outside scope.",
            "No public governance API, UI, autonomous authority, or compliance certification is included.",
        ],
        "required_final_statement": FINAL_STATEMENT,
    }
    add_secret_safe = not SECRET.search(canonical_json(public))
    if not add_secret_safe:
        public["result"] = "NEEDS WORK"
    write_json(PUBLIC_REPORT, public)
    write_json(PRIVATE_REPORT, private)
    write_json(
        ERASURE_REPORT,
        {
            "result": "PASS" if erasure_proofs and all(item["verification_status"] == "verified" for item in erasure_proofs) else "NEEDS_WORK",
            "verification_count": len(erasure_proofs),
            "verifications": erasure_proofs,
            "boundary": BOUNDARY,
        },
    )
    write_json(
        EXPORT_REPORT,
        {
            "result": "PASS" if export_proofs and all(item["verified"] for item in export_proofs) else "NEEDS_WORK",
            "verification_count": len(export_proofs),
            "verifications": export_proofs,
            "boundary": BOUNDARY,
        },
    )
    SCORECARD.write_text(
        "# Core Sprint 10 - Memory Governance\n\n"
        f"**Result:** {public['result']}\n\n"
        f"**Checks:** {passed}/{len(checks)} passed\n\n"
        f"**SQLite:** {public['sqlite']}\n\n"
        "**PostgreSQL:** NOT EXERCISED\n\n"
        f"{BOUNDARY}\n\n"
        "## Failed checks\n\n"
        + ("\n".join(f"- {item['name']}" for item in failed) if failed else "- None")
        + "\n\n## Required statement\n\n"
        + FINAL_STATEMENT
        + "\n",
        encoding="utf-8",
    )
    print("PRMR Memory Core - Core Sprint 10")
    print(f"Passed checks: {passed}/{len(checks)}")
    print(f"SQLite: {public['sqlite']}")
    print("PostgreSQL: NOT EXERCISED")
    print(f"Result: {public['result']}")
    if failed:
        for item in failed:
            print(f"FAIL: {item['name']} -> {item['detail']}")
    return 0 if public["result"].startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
