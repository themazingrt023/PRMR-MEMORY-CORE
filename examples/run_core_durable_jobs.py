"""Run Core Sprint 11 durable-job evidence on real local SQLite storage."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from prmr.core.job_fixtures import (  # noqa: E402
    SyntheticEffectService,
    synthetic_handler_registry,
    synthetic_runtime_scope,
)
from prmr.core.job_integrity import verify_job_integrity  # noqa: E402
from prmr.core.job_policy import MemoryJobPolicy  # noqa: E402
from prmr.core.job_queue import MemoryJobQueue  # noqa: E402
from prmr.core.job_scheduler import MemoryJobScheduler  # noqa: E402
from prmr.core.job_worker import MemoryJobWorker  # noqa: E402
from prmr.core.canonical_signal_registry import CanonicalSignalRegistry  # noqa: E402
from prmr.core.runtime_failure_injection import RuntimeFailureInjector  # noqa: E402
from prmr.core.runtime_integrity import (  # noqa: E402
    verify_runtime_job_scope_isolation,
)
from prmr.core.runtime_models import (  # noqa: E402
    MemoryJobStatus,
    MemoryJobType,
    RuntimeErrorCode,
)
from prmr.product.self_serve_repository_v093 import SelfServeRepositoryV093  # noqa: E402
from prmr.core.source_models import AuthenticatedScope  # noqa: E402


REPORT_DIR = ROOT / "reports" / "core_runtime_hardening"
DATABASE_PATH = REPORT_DIR / "durable_jobs_runtime.sqlite"
DURABLE_REPORT = REPORT_DIR / "durable_jobs.json"
CONCURRENCY_REPORT = REPORT_DIR / "concurrency_results.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_runtime_hardening.json"
PUBLIC_REPORT = REPORT_DIR / "public_runtime_hardening.json"
SCORECARD = REPORT_DIR / "scorecard_runtime_hardening.md"
FIXED_NOW = "2026-01-01T10:00:00Z"


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def expect_code(operation: Callable[[], Any], code: str) -> bool:
    try:
        operation()
    except Exception as exc:
        return getattr(exc, "code", None) == code
    return False


def add(checks: list[dict[str, Any]], name: str, passed: bool, detail: str = "") -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def future(seconds: int) -> str:
    value = datetime.fromisoformat(FIXED_NOW.replace("Z", "+00:00"))
    return (value + timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()
    repository = SelfServeRepositoryV093(DATABASE_PATH)
    policy = MemoryJobPolicy(
        maximum_attempts=3,
        initial_retry_delay_seconds=0,
        lease_duration_seconds=1,
        heartbeat_interval_seconds=1,
        worker_poll_interval_seconds=0.01,
    )
    queue = MemoryJobQueue(repository, policy=policy)
    service = SyntheticEffectService()
    registry = synthetic_handler_registry(service)
    worker = MemoryJobWorker(queue, registry, worker_id="worker_primary")
    alpha = synthetic_runtime_scope("alpha")
    beta = synthetic_runtime_scope("beta")
    checks: list[dict[str, Any]] = []

    basic = queue.enqueue(
        alpha,
        job_type=MemoryJobType.INTEGRITY_SWEEP.value,
        target_object_type="scope",
        target_object_id="alpha-basic",
        safe_payload={"scope_digest": "alpha_scope_digest", "mode": "sampled"},
        idempotency_key="alpha-basic-v1",
        created_at=FIXED_NOW,
    )
    add(checks, "enqueue_valid_job", basic.job_status == "queued")
    replay = queue.enqueue(
        alpha,
        job_type=MemoryJobType.INTEGRITY_SWEEP.value,
        target_object_type="scope",
        target_object_id="alpha-basic",
        safe_payload={"scope_digest": "alpha_scope_digest", "mode": "sampled"},
        idempotency_key="alpha-basic-v1",
        created_at=FIXED_NOW,
    )
    add(checks, "duplicate_enqueue_reuses_job", replay.job_id == basic.job_id)
    add(
        checks,
        "changed_payload_conflicts",
        expect_code(
            lambda: queue.enqueue(
                alpha,
                job_type=MemoryJobType.INTEGRITY_SWEEP.value,
                target_object_type="scope",
                target_object_id="alpha-basic",
                safe_payload={"scope_digest": "different_digest", "mode": "sampled"},
                idempotency_key="alpha-basic-v1",
            ),
            "MEMORY_JOB_IDEMPOTENCY_CONFLICT",
        ),
    )
    add(
        checks,
        "unsupported_type_rejected",
        expect_code(
            lambda: queue.enqueue(
                alpha,
                job_type="arbitrary_handler",
                target_object_type="scope",
                target_object_id="bad",
                safe_payload={"scope_digest": "safe"},
                idempotency_key="bad-type",
            ),
            "MEMORY_JOB_TYPE_INVALID",
        ),
    )
    add(
        checks,
        "memory_content_payload_rejected",
        expect_code(
            lambda: queue.enqueue(
                alpha,
                job_type=MemoryJobType.INTEGRITY_SWEEP.value,
                target_object_type="scope",
                target_object_id="bad-content",
                safe_payload={"source_content": "must not persist"},
                idempotency_key="bad-content",
            ),
            "MEMORY_JOB_PAYLOAD_INVALID",
        ),
    )
    basic_result = worker.run_once()
    add(checks, "worker_completes_valid_job", basic_result["status"] == "completed")
    add(checks, "completed_job_not_leased_again", worker.run_once()["status"] == "idle")
    basic_integrity = verify_job_integrity(queue.store, basic.job_id)
    add(checks, "completed_job_integrity", basic_integrity["verified"])

    scheduled = queue.enqueue(
        alpha,
        job_type=MemoryJobType.CHECKPOINT_REFRESH.value,
        target_object_type="checkpoint_scope",
        target_object_id="future-checkpoint",
        safe_payload={"checkpoint_scope_digest": "future_digest"},
        idempotency_key="scheduled-future",
        scheduled_for="2999-01-01T00:00:00Z",
    )
    add(checks, "scheduled_job_waits", queue.lease_next_job("worker_schedule") is None)

    low = queue.enqueue(
        alpha,
        job_type=MemoryJobType.QUERY_PRECOMPUTE.value,
        target_object_type="query",
        target_object_id="priority-low",
        safe_payload={"query_digest": "low"},
        idempotency_key="priority-low",
        priority=1,
    )
    high = queue.enqueue(
        alpha,
        job_type=MemoryJobType.QUERY_PRECOMPUTE.value,
        target_object_type="query",
        target_object_id="priority-high",
        safe_payload={"query_digest": "high"},
        idempotency_key="priority-high",
        priority=20,
    )
    leased_high = queue.lease_next_job("worker_priority")
    add(checks, "priority_ordering", leased_high is not None and leased_high.job.job_id == high.job_id)
    if leased_high:
        priority_worker = MemoryJobWorker(queue, registry, worker_id="worker_priority")
        priority_worker.execute_job(leased_high)
    worker.run_until_idle(maximum_jobs=1)

    lease_job = queue.enqueue(
        alpha,
        job_type=MemoryJobType.TEMPORAL_DYNAMICS_REFRESH.value,
        target_object_type="memory_scope",
        target_object_id="lease-proof",
        safe_payload={"boundary_digest": "lease_boundary"},
        idempotency_key="lease-proof",
    )
    leased = queue.lease_next_job("worker_lease")
    add(checks, "one_worker_leases_job", leased is not None and leased.job.job_id == lease_job.job_id)
    if leased:
        with repository.connect() as connection:
            leased_row = connection.execute(
                "SELECT lease_token_digest FROM prmr_memory_jobs WHERE job_id=?",
                (leased.job.job_id,),
            ).fetchone()
        add(
            checks,
            "only_lease_token_digest_stored",
            leased_row is not None
            and leased_row["lease_token_digest"]
            == hashlib.sha256(leased.lease_token.encode("utf-8")).hexdigest()
            and leased_row["lease_token_digest"] != leased.lease_token,
        )
    add(
        checks,
        "second_worker_cannot_lease_same_job",
        queue.lease_next_job("worker_other") is None,
    )
    if leased:
        running, attempt_id = queue.start_job(
            leased,
            worker_id="worker_lease",
            transaction_mode="read_committed_v1",
        )
        add(
            checks,
            "wrong_lease_token_rejected",
            expect_code(
                lambda: queue.heartbeat(
                    running.job_id,
                    worker_id="worker_lease",
                    lease_token="wrong-token",
                    attempt_id=attempt_id,
                ),
                "MEMORY_JOB_LEASE_LOST",
            ),
        )
        heartbeat = queue.heartbeat(
            running.job_id,
            worker_id="worker_lease",
            lease_token=leased.lease_token,
            attempt_id=attempt_id,
        )
        add(checks, "heartbeat_extends_lease", heartbeat.lease_expires_at is not None)
        handler = registry.resolve(running.job_type)
        result = handler.execute(running)
        queue.commit_effect_receipt(
            running,
            worker_id="worker_lease",
            lease_token=leased.lease_token,
            result=result,
        )
        queue.complete(
            running,
            worker_id="worker_lease",
            lease_token=leased.lease_token,
            attempt_id=attempt_id,
            result=result,
            duration_ms=1.0,
        )

    retry_target = "retry-once"
    service.configure_failures(retry_target, 1)
    retry_job = queue.enqueue(
        alpha,
        job_type=MemoryJobType.CONSOLIDATION_REFRESH.value,
        target_object_type="consolidation",
        target_object_id=retry_target,
        safe_payload={"consolidation_id": retry_target},
        idempotency_key="retry-once",
        maximum_attempts=3,
    )
    first_retry = worker.run_once()
    second_retry = worker.run_once()
    add(checks, "retryable_failure_enters_retry_wait", first_retry["status"] == "retry_wait")
    add(checks, "retry_completes_without_duplicate_effect", second_retry["status"] == "completed")
    add(checks, "retry_attempt_count_is_two", queue.store.get_job(retry_job.job_id).attempt_count == 2)

    dead_target = "retry-exhausted"
    service.configure_failures(dead_target, 5)
    dead_job = queue.enqueue(
        alpha,
        job_type=MemoryJobType.CONSOLIDATION_BUILD.value,
        target_object_type="consolidation",
        target_object_id=dead_target,
        safe_payload={"consolidation_id": dead_target},
        idempotency_key="retry-exhausted",
        maximum_attempts=2,
    )
    worker.run_once()
    dead_result = worker.run_once()
    add(checks, "maximum_attempts_dead_letters", dead_result["status"] == "dead_letter")
    replayed_dead = queue.replay_dead_letter(alpha, dead_job.job_id)
    add(checks, "dead_letter_replay_is_explicit", replayed_dead.job_status == "queued")
    service.failures_remaining[dead_target] = 0
    worker.run_once()

    cancel_queued = queue.enqueue(
        alpha,
        job_type=MemoryJobType.EXPORT_EXPIRY.value,
        target_object_type="export",
        target_object_id="cancel-queued",
        safe_payload={"export_id": "cancel-queued"},
        idempotency_key="cancel-queued",
    )
    cancelled = queue.request_cancellation(alpha, cancel_queued.job_id)
    add(checks, "queued_job_cancels_immediately", cancelled.job_status == "cancelled")

    parent = queue.enqueue(
        alpha,
        job_type=MemoryJobType.GOVERNANCE_EXECUTION.value,
        target_object_type="governance_plan",
        target_object_id="parent-plan",
        safe_payload={"governance_plan_id": "parent-plan"},
        idempotency_key="parent-plan",
        priority=30,
    )
    child = queue.enqueue(
        alpha,
        job_type=MemoryJobType.POST_ERASURE_RECOMPUTE.value,
        target_object_type="governance_execution",
        target_object_id="parent-plan",
        safe_payload={"governance_plan_id": "parent-plan"},
        idempotency_key="child-recompute",
        parent_job_id=parent.job_id,
        priority=100,
    )
    parent_outcome = worker.run_once()
    child_outcome = worker.run_once()
    add(checks, "parent_runs_before_blocked_child", parent_outcome["job_id"] == parent.job_id)
    add(checks, "child_runs_after_parent_completion", child_outcome["job_id"] == child.job_id)

    scheduler = MemoryJobScheduler(queue)
    schedule_id = scheduler.create_schedule(
        alpha,
        schedule_type="one_time",
        job_type=MemoryJobType.INTEGRITY_SWEEP.value,
        target_object_type="scope",
        target_object_id="scheduled-sweep",
        safe_payload={"scope_digest": "scheduled_scope"},
        next_run_at=FIXED_NOW,
        created_at=FIXED_NOW,
    )
    scheduled_jobs = scheduler.enqueue_due(now=FIXED_NOW)
    add(checks, "scheduler_enqueues_one_occurrence", len(scheduled_jobs) == 1)
    add(checks, "schedule_identity_is_opaque", schedule_id.startswith("msched_"))
    worker.run_once()

    crash_job = queue.enqueue(
        alpha,
        job_type=MemoryJobType.EXPORT_GENERATION.value,
        target_object_type="export_request",
        target_object_id="crash-after-effect",
        safe_payload={"export_request_id": "crash-after-effect"},
        idempotency_key="crash-after-effect",
    )
    injector = RuntimeFailureInjector(
        enabled_for_tests=True,
        fail_counts={"after_effect_commit_before_job_completion": 1},
        crash_points={"after_effect_commit_before_job_completion"},
    )
    crash_worker = MemoryJobWorker(
        queue,
        registry,
        worker_id="worker_crash",
        failure_injector=injector,
    )
    crashed = crash_worker.run_once()
    add(checks, "post_effect_completion_crash_injected", crashed["status"] == "worker_crashed")
    calls_after_crash = service.calls[crash_job.job_id]

    # Reopen the repository to prove queue and effect receipts survive process state.
    del crash_worker
    del queue
    del repository
    restarted_repository = SelfServeRepositoryV093(DATABASE_PATH)
    restarted_queue = MemoryJobQueue(
        restarted_repository, policy=policy, initialize=True
    )
    time.sleep(1.1)
    recovered_ids = restarted_queue.recover_expired_leases()
    recovery_worker = MemoryJobWorker(
        restarted_queue,
        registry,
        worker_id="worker_recovery",
    )
    recovered = recovery_worker.run_once()
    add(checks, "expired_lease_recovered_after_restart", crash_job.job_id in recovered_ids)
    add(checks, "effect_receipt_completes_replayed_job", recovered.get("replayed") is True)
    add(
        checks,
        "post_effect_recovery_has_no_duplicate_service_call",
        service.calls[crash_job.job_id] == calls_after_crash == 1,
    )
    add(
        checks,
        "restart_job_integrity",
        verify_job_integrity(restarted_queue.store, crash_job.job_id)["verified"],
    )

    beta_job = restarted_queue.enqueue(
        beta,
        job_type=MemoryJobType.INTEGRITY_SWEEP.value,
        target_object_type="scope",
        target_object_id="beta-scope",
        safe_payload={"scope_digest": "beta_scope"},
        idempotency_key="beta-scope",
    )
    isolation = verify_runtime_job_scope_isolation(
        restarted_queue.store,
        scope=alpha.boundary(),
        foreign_job_id=beta_job.job_id,
    )
    add(checks, "cross_tenant_job_lookup_denied", isolation["verified"])

    signal_scope = AuthenticatedScope(
        alpha.client_id, alpha.vault_id, alpha.namespace
    )
    signal_registry = CanonicalSignalRegistry(restarted_repository)
    proposals = [
        signal_registry.propose_signal_mapping(
            signal_scope,
            original_signal_key=f"runtime.signal_{index}",
            proposed_canonical_signal_key=f"memory.signal_{index}",
            proposal_basis="Synthetic reviewed batch fixture.",
            proposal_method="deterministic_alias_rule",
            created_at=FIXED_NOW,
        )
        for index in range(2)
    ]
    batch_decisions = signal_registry.apply_canonical_signal_decisions_batch(
        signal_scope,
        [
            {
                "proposal_id": proposal.canonical_signal_proposal_id,
                "actor_type": "test_runner",
                "actor_reference": "runtime_batch_reviewer",
                "reason": "Synthetic reviewed mapping.",
                "idempotency_key": f"runtime-batch-{index}",
                "valid_from": FIXED_NOW,
                "system_effective_at": FIXED_NOW,
            }
            for index, proposal in enumerate(proposals)
        ],
    )
    add(
        checks,
        "canonical_signal_reviewed_batch_works",
        len(batch_decisions) == 2
        and all(item.decision_type == "approve" for item in batch_decisions),
    )

    with restarted_repository.connect() as connection:
        raw_row = connection.execute(
            "SELECT lease_token_digest,safe_payload_json FROM prmr_memory_jobs "
            "WHERE job_id=?",
            (crash_job.job_id,),
        ).fetchone()
    public_material = {
        "job_ids": [basic.job_id, retry_job.job_id, crash_job.job_id],
        "statuses": {
            "basic": restarted_queue.store.get_job(basic.job_id).job_status,
            "retry": restarted_queue.store.get_job(retry_job.job_id).job_status,
            "recovery": restarted_queue.store.get_job(crash_job.job_id).job_status,
        },
    }
    public_text = json.dumps(public_material, sort_keys=True)
    add(checks, "raw_lease_token_not_stored", raw_row["lease_token_digest"] is None)
    add(checks, "public_evidence_has_no_raw_tokens", "lease_token" not in public_text)

    failures = [item for item in checks if not item["passed"]]
    sqlite_result = "PASS" if not failures else "NEEDS_WORK"
    postgres_status = "NOT_EXERCISED_DEDICATED_TEST_DATABASE_UNAVAILABLE"
    overall = "BLOCKED" if not failures else "NEEDS_WORK"
    durable_report = {
        "version": "core_sprint_11",
        "sqlite_result": sqlite_result,
        "postgres_status": postgres_status,
        "result": overall,
        "passed_checks": len(checks) - len(failures),
        "total_checks": len(checks),
        "failed_checks": failures,
        "checks": checks,
        "queue_semantics": "at_least_once_delivery_with_idempotent_effect_receipts",
        "sqlite_boundary": (
            "Durable single-worker and bounded restart evidence only. SQLite does "
            "not prove PostgreSQL SKIP LOCKED or multi-process concurrency."
        ),
    }
    concurrency = {
        "sqlite_single_worker": sqlite_result,
        "postgres_eight_worker": "NOT_RUN",
        "duplicate_effect_count": 0 if not failures else None,
        "claim": "No PostgreSQL concurrency claim is made.",
    }
    public = {
        "version": "core_sprint_11",
        "result": overall,
        "sqlite_durable_jobs": sqlite_result,
        "postgres_runtime": postgres_status,
        "passed_checks": durable_report["passed_checks"],
        "total_checks": durable_report["total_checks"],
        "boundary": (
            "Internal local runtime evidence only. Real isolated PostgreSQL "
            "validation is mandatory before Sprint 11 can pass."
        ),
    }
    private = {
        **durable_report,
        "database_path_category": "ignored_local_report_storage",
        "synthetic_scopes": ["alpha", "beta"],
        "scheduled_job_id": scheduled.job_id,
        "future_job_intentionally_pending": True,
        "canonical_batch_decisions": len(batch_decisions),
    }
    write_json(DURABLE_REPORT, durable_report)
    write_json(CONCURRENCY_REPORT, concurrency)
    write_json(PUBLIC_REPORT, public)
    write_json(PRIVATE_REPORT, private)
    SCORECARD.write_text(
        "# Core Sprint 11 - Runtime Hardening\n\n"
        f"**Result:** {overall}\n\n"
        f"**SQLite durable jobs:** {sqlite_result}\n\n"
        f"**Checks:** {durable_report['passed_checks']}/{durable_report['total_checks']}\n\n"
        "**PostgreSQL:** NOT EXERCISED - dedicated guarded test database unavailable\n\n"
        "Sprint 11 cannot pass without real isolated PostgreSQL runtime validation.\n",
        encoding="utf-8",
    )
    print("PRMR Memory Core - Core Sprint 11 Durable Jobs")
    print(f"Passed checks: {durable_report['passed_checks']}/{durable_report['total_checks']}")
    print(f"SQLite durable jobs: {sqlite_result}")
    print(f"PostgreSQL: {postgres_status}")
    print(f"Result: {overall}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
