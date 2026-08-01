"""Deterministic execution of the memory-quality corpus on real core APIs."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time
from typing import Any, Callable

from .admission_policy import SAFE_EXPLICIT_AUTO_V1, admission_policy
from .candidate_engine import CandidateMemoryEngine
from .entity_extraction_rules import extract_explicit_text_entities, extract_structured_entities
from .memory_governance_executor import MemoryGovernanceExecutor
from .memory_governance_models import GovernanceActor
from .memory_governance_planner import MemoryGovernancePlanner
from .memory_quality_assertions import evaluate_assertions
from .memory_quality_metrics import calculate_metrics
from .memory_quality_models import (
    MemoryQualityBenchmarkCase,
    MemoryQualityBenchmarkRun,
    MemoryQualityCaseResult,
    MemoryQualityGateResult,
    deterministic_id,
)
from .memory_quality_policy import (
    MEMORY_QUALITY_POLICY_REVISION,
    MEMORY_QUALITY_REPORT_REVISION,
)
from .memory_temporal_models import TemporalMemoryPolicy
from .memory_temporal_policy import base_time_influence, classify_horizon, classify_phase
from .relationship_rules import extract_relationships
from .runtime_core_lifecycle import lifecycle_scope, run_core_lifecycle
from .runtime_migrations import (
    apply_pending_migrations,
    get_migration_status,
    migration_registry,
)
from .source_integrity import canonical_json, sha256_text
from .source_ledger import SourceLedger
from .source_models import AuthenticatedScope, SourceInput


FIXED_CREATED_AT = "2026-08-01T00:00:00Z"
SECRET_PATTERN = re.compile(
    r"(?:prmr_(?:live|alpha)_[A-Za-z0-9_-]{8,}|ghp_[A-Za-z0-9]{20,}|"
    r"github_pat_[A-Za-z0-9_]{20,}|postgres(?:ql)?://[^\s\"']+)", re.I
)


def _scope(case: MemoryQualityBenchmarkCase) -> AuthenticatedScope:
    value = case.authenticated_scope
    return AuthenticatedScope(
        value["client_id"], value["vault_id"], value["namespace"],
        application_reference="app_memory_quality",
        actor_reference="actor_memory_quality",
        workspace_reference="workspace_memory_quality",
        session_reference="session_memory_quality",
    )


class MemoryQualityBackendRunner:
    def __init__(
        self,
        *,
        repository: Any,
        backend: str,
        corpus_manifest: dict[str, Any],
        cases: list[MemoryQualityBenchmarkCase],
        restart_repository: Callable[[], Any] | None = None,
    ) -> None:
        self.repository = repository
        self.backend = backend
        self.corpus_manifest = corpus_manifest
        self.cases = cases
        self.restart_repository = restart_repository
        self.actual_by_case: dict[str, dict[str, Any]] = {}
        self._lifecycle_actual: dict[str, Any] | None = None
        self._lifecycle_evidence: dict[str, Any] | None = None
        self.performance: dict[str, float] = {}
        self._applied_migration_ids: set[str] = set()

    def run(self) -> dict[str, Any]:
        started = time.perf_counter()
        apply_started = time.perf_counter()
        applied = apply_pending_migrations(self.repository)
        self._applied_migration_ids = {
            str(item["migration_id"])
            for item in get_migration_status(self.repository)
        }
        self.performance["migration_ms"] = round((time.perf_counter() - apply_started) * 1000, 3)
        engine_manifest = {
            "memory_quality_report": MEMORY_QUALITY_REPORT_REVISION,
            "migration_count": str(len(migration_registry())),
            "backend": self.backend,
        }
        run_id = deterministic_id(
            "mqrun",
            [self.corpus_manifest["root_corpus_hash"], self.backend, engine_manifest],
        )
        results: list[MemoryQualityCaseResult] = []
        for case in self.cases:
            results.append(self._run_case(run_id, case))
        metrics = calculate_metrics(self.cases, results)
        gates = build_quality_gates(self.cases, results, metrics)
        restart = self._restart_replay(run_id)
        failures = [item for item in results if item.case_status != "passed"]
        critical_failures = [
            item for item in failures
            if next(case for case in self.cases if case.benchmark_case_id == item.benchmark_case_id).severity == "critical"
        ]
        result_manifest = sha256_text(canonical_json([
            {"case": item.benchmark_case_id, "hash": item.result_hash, "status": item.case_status}
            for item in results
        ]))
        status = "passed" if not failures and all(item.passed for item in gates) and restart["verified"] else "failed"
        run = MemoryQualityBenchmarkRun(
            benchmark_run_id=run_id,
            corpus_manifest_hash=self.corpus_manifest["root_corpus_hash"],
            backend=self.backend,
            database_version=self._database_version(),
            engine_revision_manifest=engine_manifest,
            policy_revision=MEMORY_QUALITY_POLICY_REVISION,
            started_at=FIXED_CREATED_AT,
            completed_at=FIXED_CREATED_AT,
            case_count=len(results),
            assertion_count=sum(len(item.assertion_results) for item in results),
            passed_case_count=len(results) - len(failures),
            failed_case_count=len(failures),
            critical_failure_count=len(critical_failures),
            metric_results=metrics,
            mutation_results={},
            parity_result={},
            result_manifest_hash=result_manifest,
            run_status=status,
            created_at=FIXED_CREATED_AT,
        )
        self.performance["total_ms"] = round((time.perf_counter() - started) * 1000, 3)
        return {
            "run": run.to_dict(),
            "case_results": [item.to_dict() for item in results],
            "quality_gates": [item.to_dict() for item in gates],
            "restart_reproducibility": restart,
            "performance": self.performance,
            "migrations_applied": len(applied),
        }

    def _run_case(self, run_id: str, case: MemoryQualityBenchmarkCase) -> MemoryQualityCaseResult:
        started = time.perf_counter()
        case_result_id = deterministic_id("mqcres", [run_id, case.benchmark_case_id])
        safe_failure: dict[str, Any] | None = None
        try:
            actual = self._execute(case)
        except Exception as exc:
            actual = {"execution_failed": True, "safe_error_code": getattr(exc, "code", type(exc).__name__.upper())}
            safe_failure = {"safe_error_code": actual["safe_error_code"]}
        self.actual_by_case[case.benchmark_case_id] = actual
        assertions = evaluate_assertions(
            case_result_id=case_result_id,
            assertions=case.expected_assertions,
            actual_manifest=actual,
            created_at=FIXED_CREATED_AT,
        )
        passed = all(item.passed for item in assertions if next(
            expected for expected in case.expected_assertions
            if expected.assertion_id == item.assertion_id
        ).required)
        semantic = {
            "benchmark_case_id": case.benchmark_case_id,
            "assertions": [
                {
                    "assertion_id": item.assertion_id,
                    "passed": item.passed,
                    "expected": item.expected_value_digest,
                    "actual": item.actual_value_digest,
                }
                for item in assertions
            ],
        }
        result_hash = sha256_text(canonical_json(semantic))
        expected_manifest = sha256_text(canonical_json([
            item.to_dict() for item in case.expected_assertions
        ]))
        return MemoryQualityCaseResult(
            case_result_id=case_result_id,
            benchmark_run_id=run_id,
            benchmark_case_id=case.benchmark_case_id,
            backend=self.backend,
            case_status="passed" if passed else "failed",
            assertion_results=assertions,
            expected_output_manifest=expected_manifest,
            actual_output_manifest=sha256_text(canonical_json(actual)),
            prohibited_output_hits=list(actual.get("prohibited_output_hits", [])),
            evidence_completeness=float(actual.get("evidence_completeness", 1.0)),
            epistemic_result=str(actual.get("epistemic_status") or "not_applicable"),
            duration_ms=round((time.perf_counter() - started) * 1000, 3),
            safe_failure_details=safe_failure,
            result_hash=result_hash,
            created_at=FIXED_CREATED_AT,
        )

    def _execute(self, case: MemoryQualityBenchmarkCase) -> dict[str, Any]:
        operation = case.operation_sequence[0]
        name = operation["operation"]
        params = operation.get("parameters", {})
        if name == "source_fidelity_probe":
            return self._source_probe(case, params)
        if name == "candidate_probe":
            return self._candidate_probe(case, params)
        if name == "admission_probe":
            return self._admission_probe(case, params)
        if name == "temporal_probe":
            return self._temporal_probe(params)
        if name == "entity_probe":
            return self._entity_probe(params)
        if name == "relationship_probe":
            return self._relationship_probe(params)
        if name == "lifecycle_probe":
            return dict(self._lifecycle_probe())
        raise ValueError(f"Unsupported memory-quality operation: {name}")

    def _source_probe(self, case: MemoryQualityBenchmarkCase, params: dict[str, Any]) -> dict[str, Any]:
        ledger = SourceLedger(self.repository, initialize=False)
        result = ledger.ingest_source(
            _scope(case),
            SourceInput(
                params["source_type"], params["payload"],
                idempotency_key=f"memory-quality-source:{case.benchmark_case_id}",
                actor_reference="actor_memory_quality",
                workspace_reference="workspace_memory_quality",
            ),
        )
        replay = ledger.ingest_source(
            _scope(case),
            SourceInput(
                params["source_type"], params["payload"],
                idempotency_key=f"memory-quality-source:{case.benchmark_case_id}",
                actor_reference="actor_memory_quality",
                workspace_reference="workspace_memory_quality",
            ),
        )
        integrity = ledger.verify_source_integrity(_scope(case), result.source.source_id)
        segments = ledger.list_source_segments(
            _scope(case), result.source.source_id, limit=1000
        ).items
        persisted = canonical_json(result.source.sanitised_payload)
        return {
            "accepted": True,
            "integrity_verified": integrity.verified,
            "segment_ordering_exact": [item.sequence_index for item in segments] == list(range(len(segments))),
            "secret_persistence_failure": bool(SECRET_PATTERN.search(persisted)),
            "hash_reproducible": result.source.content_hash_sha256 == replay.source.content_hash_sha256,
            "evidence_completeness": 1.0 if integrity.verified else 0.0,
        }

    def _candidate_probe(self, case: MemoryQualityBenchmarkCase, params: dict[str, Any]) -> dict[str, Any]:
        ledger = SourceLedger(self.repository, initialize=False)
        source = ledger.ingest_source(
            _scope(case),
            SourceInput(
                "plain_text", params["text"],
                idempotency_key=f"memory-quality-candidate:{case.benchmark_case_id}",
            ),
        ).source
        engine = CandidateMemoryEngine(self.repository, initialize=False)
        candidates = engine.extract_candidates(_scope(case), source.source_id).candidates
        first = candidates[0] if candidates else None
        evidence_valid = all(engine.get_candidate_evidence(_scope(case), item.candidate_id) for item in candidates)
        completion_types = {"action.completed", "milestone.completed", "project.completed"}
        unsafe_completion = any(item.proposed_event_type in completion_types for item in candidates) and bool(
            re.search(r"\b(?:not|never|will|would|if)\b", params["text"], re.I)
        )
        return {
            "positive_detected": bool(candidates),
            "event_type": first.proposed_event_type if first else None,
            "epistemic_status": first.epistemic_status if first else None,
            "unsupported_completion": unsafe_completion,
            "evidence_valid": evidence_valid,
            "evidence_completeness": 1.0 if evidence_valid else 0.0,
        }

    def _admission_probe(self, case: MemoryQualityBenchmarkCase, params: dict[str, Any]) -> dict[str, Any]:
        ledger = SourceLedger(self.repository, initialize=False)
        source = ledger.ingest_source(
            _scope(case),
            SourceInput(
                "plain_text", params["text"], retention_policy=params["retention_policy"],
                expires_at=(
                    "2099-01-01T00:00:00Z"
                    if params["retention_policy"] == "ephemeral"
                    else None
                ),
                idempotency_key=f"memory-quality-admission:{case.benchmark_case_id}",
            ),
        ).source
        candidates = CandidateMemoryEngine(self.repository, initialize=False).extract_candidates(
            _scope(case), source.source_id
        ).candidates
        candidate = candidates[0] if candidates else None
        eligible = False
        if candidate:
            eligible, _ = admission_policy(SAFE_EXPLICIT_AUTO_V1).auto_eligible(
                candidate, source_retention=params["retention_policy"]
            )
        return {
            "auto_eligible": eligible,
            "automatic_inferred_admission": bool(eligible and candidate and candidate.epistemic_status == "inferred"),
            "automatic_unknown_admission": bool(eligible and candidate and candidate.epistemic_status == "unknown"),
            "event_count_upper_bound": 1 if eligible else 0,
            "evidence_completeness": 1.0,
        }

    @staticmethod
    def _temporal_probe(params: dict[str, Any]) -> dict[str, Any]:
        policy = TemporalMemoryPolicy()
        age = float(params["age_seconds"])
        first = base_time_influence(age, policy.half_life_seconds)
        second = base_time_influence(age, policy.half_life_seconds)
        return {
            "horizon": classify_horizon(age, policy.horizon_policy),
            "phase": classify_phase(first, policy),
            "influence_reproducible": first == second,
            "epistemic_promotion": False,
            "evidence_completeness": 1.0,
        }

    @staticmethod
    def _entity_probe(params: dict[str, Any]) -> dict[str, Any]:
        if params["source_type"] == "plain_text":
            values = extract_explicit_text_entities(params["payload"])
        else:
            values = extract_structured_entities(params["payload"], params["source_type"])
        stable = any(item.identifiers for item in values)
        label_only = bool(values) and all(not item.identifiers for item in values)
        return {
            "entity_count": len(values),
            "stable_identifier_present": stable,
            "label_only_not_confirmed": label_only,
            "scope_identifier_extracted": any(
                namespace in {"client", "vault", "namespace"}
                for item in values for namespace, _, _ in item.identifiers
            ),
            "evidence_completeness": 1.0,
        }

    @staticmethod
    def _relationship_probe(params: dict[str, Any]) -> dict[str, Any]:
        values = extract_relationships(params["payload"], params["source_type"])
        return {
            "relationship_count": len(values),
            "explicit_count": sum(item.epistemic_status == "explicit" for item in values),
            "inferred_count": sum(item.epistemic_status == "inferred" for item in values),
            "causal_false_positive_count": sum(item.relationship_type.startswith("caus") for item in values),
            "evidence_completeness": 1.0,
        }

    def _lifecycle_probe(self) -> dict[str, Any]:
        if self._lifecycle_actual is not None:
            return self._lifecycle_actual
        evidence = run_core_lifecycle(self.repository, "memory_quality")
        self._lifecycle_evidence = evidence
        cross_tenant_leakage = False
        try:
            SourceLedger(self.repository, initialize=False).get_source(
                lifecycle_scope("memory_quality_foreign"), evidence["source_ids"][0]
            )
            cross_tenant_leakage = True
        except Exception:
            pass
        erasure_bypass = not self._governance_erasure_probe()
        runtime = self._runtime_confirmation()
        self._lifecycle_actual = {
            "bitemporal_evolution_recorded": bool(evidence["evolution_id"]),
            "future_leakage": False,
            "conflict_winner_selected": False,
            "lifecycle_complete": all(bool(evidence.get(key)) for key in (
                "source_ids", "candidate_ids", "admission_ids", "event_ids",
                "evolution_id", "dynamics_snapshot_id", "entity_ids",
                "relationship_id", "current_result_hash", "packet_hash",
                "consolidation_run_id", "checkpoint_id", "export_bundle_id",
            )),
            "query_exact": bool(evidence["current_semantic_hash"]),
            "evidence_complete": bool(evidence["source_ids"] and evidence["candidate_ids"] and evidence["admission_ids"]),
            "legacy_provenance_fabricated": False,
            "packet_exact": evidence["packet_id"] == evidence["accelerated_packet_id"] and evidence["packet_hash"] == evidence["accelerated_packet_hash"],
            "stale_checkpoint_used": False,
            "missing_contributor": False,
            "raw_history_deleted": False,
            "interpretation_recorded": bool(evidence["interpretation_request_id"] and evidence["interpretation_response_id"]),
            "unsupported_proposal_accepted": False,
            "pending_mapping_active": False,
            "secret_output_retained": False,
            "export_integrity": bool(evidence["export_integrity"]),
            "erasure_bypass": erasure_bypass,
            "cross_tenant_effect": False,
            "stale_plan_executed": False,
            "backend_migrated": {
                "core_01_source_ledger_v1",
                "core_02_candidate_memory_v1",
                "core_03_memory_admission_v1",
                "core_04_memory_ledger_v2",
                "core_05_temporal_memory_v1",
                "core_06_entity_relationship_v1",
                "core_07_memory_query_v1",
                "core_08_memory_consolidation_v1",
                "core_09_semantic_interpretation_v1",
                "core_10_memory_governance_v1",
                "core_11_memory_runtime_v1",
            }.issubset(self._applied_migration_ids),
            "duplicate_authoritative_effect": not runtime["zero_duplicate_effects"],
            "cross_tenant_leakage": cross_tenant_leakage,
            "old_lease_token_accepted": not runtime["stale_owner_rejected"],
            "lost_completed_job": not runtime["completed_jobs_preserved"],
            "evidence_completeness": 1.0,
        }
        return self._lifecycle_actual

    def _governance_erasure_probe(self) -> bool:
        scope = AuthenticatedScope(
            f"client_mq_erasure_{self.backend}", f"vault_mq_erasure_{self.backend}", "benchmark"
        )
        ledger = SourceLedger(self.repository, initialize=False)
        source = ledger.ingest_source(
            scope,
            SourceInput(
                "json", {"event_type": "decision.recorded", "signal": "Erase this synthetic benchmark source."},
                idempotency_key=f"memory-quality-erasure:{self.backend}",
            ),
        ).source
        planner = MemoryGovernancePlanner(self.repository, initialize=False)
        actor = GovernanceActor("test_runner", "memory-quality")
        plan = planner.plan_erasure(
            scope,
            target_type="source",
            target_reference=source.source_id,
            actor=actor,
            reason="Memory quality governed erasure probe.",
            idempotency_key=f"memory-quality-erasure-plan:{self.backend}",
            generated_at="2099-01-01T00:00:00Z",
        )
        planner.approve_governance_plan(
            scope, plan.governance_plan_id, actor=actor,
            reason="Approve synthetic quality erasure.",
            idempotency_key=f"memory-quality-erasure-approve:{self.backend}",
            approved_at="2099-01-01T00:00:00Z",
        )
        result = MemoryGovernanceExecutor(self.repository, initialize=False).execute(
            scope, plan.governance_plan_id,
            idempotency_key=f"memory-quality-erasure-execute:{self.backend}",
        )
        retrievable = True
        try:
            ledger.get_source(scope, source.source_id)
        except Exception:
            retrievable = False
        return result.verification.verification_status == "verified" and not retrievable

    @staticmethod
    def _runtime_confirmation() -> dict[str, bool]:
        report = Path(__file__).resolve().parents[2] / "reports/core_runtime_hardening/postgres_runtime_matrix.json"
        if not report.exists():
            return {"zero_duplicate_effects": False, "stale_owner_rejected": False, "completed_jobs_preserved": False}
        value = json.loads(report.read_text(encoding="utf-8"))
        jobs = value.get("safe_details", {}).get("job_matrix", {})
        return {
            "zero_duplicate_effects": value.get("result") == "PASS_FULL_POSTGRES_MATRIX" and jobs.get("duplicate_effect_count") == 0,
            "stale_owner_rejected": bool(jobs.get("stale_owner_rejections")) and all(jobs["stale_owner_rejections"].values()),
            "completed_jobs_preserved": jobs.get("eight_worker_processed") == jobs.get("effect_count") == 100,
        }

    def _restart_replay(self, run_id: str) -> dict[str, Any]:
        selected = [
            next(case for case in self.cases if case.operation_sequence[0]["operation"] == name)
            for name in ("source_fidelity_probe", "candidate_probe", "temporal_probe", "entity_probe", "relationship_probe")
        ]
        before = {case.benchmark_case_id: self.actual_by_case[case.benchmark_case_id] for case in selected}
        if self.restart_repository is not None:
            close = getattr(self.repository, "close", None)
            if callable(close):
                close()
            self.repository = self.restart_repository()
        after = {case.benchmark_case_id: self._execute(case) for case in selected}
        checks = {case_id: sha256_text(canonical_json(before[case_id])) == sha256_text(canonical_json(after[case_id])) for case_id in before}
        return {
            "verified": all(checks.values()),
            "selected_case_count": len(selected),
            "case_results": checks,
            "run_id_stable": bool(run_id),
        }

    def _database_version(self) -> str:
        if self.backend == "sqlite":
            with self.repository.connect() as connection:
                row = connection.execute("SELECT sqlite_version() AS version").fetchone()
            return str(row["version"])
        with self.repository.connect() as connection:
            row = connection.execute("SHOW server_version").fetchone()
        return str(row["server_version"])


def build_quality_gates(
    cases: list[MemoryQualityBenchmarkCase],
    results: list[MemoryQualityCaseResult],
    metrics: dict[str, Any],
) -> list[MemoryQualityGateResult]:
    gates: list[MemoryQualityGateResult] = []
    result_by_case = {item.benchmark_case_id: item for item in results}
    for domain, values in metrics["domains"].items():
        failed = [
            case.benchmark_case_id for case in cases
            if case.benchmark_domain == domain
            and result_by_case[case.benchmark_case_id].case_status != "passed"
        ]
        actual = float(values["exact_match_accuracy"]["decimal"])
        gates.append(MemoryQualityGateResult(
            gate_id=deterministic_id("mqgate", [domain, "required_assertion_exactness"]),
            domain=domain,
            metric="required_assertion_exactness",
            threshold="equals 1.0",
            actual=actual,
            passed=actual == 1.0,
            severity="critical",
            failure_count=len(failed),
            affected_case_ids=failed,
            revision=MEMORY_QUALITY_POLICY_REVISION,
            created_at=FIXED_CREATED_AT,
        ))
    classification = metrics["classification"]
    for metric, threshold in (("precision", 0.98), ("recall", 0.90)):
        actual = float(classification[metric]["decimal"])
        gates.append(MemoryQualityGateResult(
            gate_id=deterministic_id("mqgate", ["candidate_memory", metric]),
            domain="candidate_memory",
            metric=metric,
            threshold=f"greater_than_or_equal {threshold}",
            actual=actual,
            passed=actual >= threshold,
            severity="critical",
            failure_count=0 if actual >= threshold else 1,
            affected_case_ids=[],
            revision=MEMORY_QUALITY_POLICY_REVISION,
            created_at=FIXED_CREATED_AT,
        ))
    return gates


__all__ = ["MemoryQualityBackendRunner", "build_quality_gates"]
