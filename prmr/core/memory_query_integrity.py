"""Independent integrity verification for durable deterministic query artifacts."""

from __future__ import annotations

from .memory_explanation import build_memory_explanation
from .memory_query_models import (
    MEMORY_EVIDENCE_BUNDLE_REVISION,
    MEMORY_EXPLANATION_REVISION,
    MEMORY_QUERY_INTEGRITY_REVISION,
    MEMORY_QUERY_RESULT_REVISION,
    MemoryQueryIntegrityResult,
)
from .memory_query_planner import MemoryQueryPlanner
from .memory_query_results import build_epistemic_summary
from .source_integrity import canonical_json, sha256_text
from .source_models import AuthenticatedScope


class MemoryQueryIntegrityVerifier:
    def __init__(self, engine: object) -> None:
        self.engine = engine

    def verify(
        self, scope: AuthenticatedScope, query_run_id: str
    ) -> MemoryQueryIntegrityResult:
        checks: dict[str, bool] = {}
        details: dict[str, object] = {}
        run = self.engine.get_query_run(scope, query_run_id)
        checks["query_run_exists"] = True
        checks["authenticated_scope_matches"] = (
            (run.client_id, run.vault_id, run.namespace) == scope.memory_boundary()
        )
        request = _request_from_payload(run.normalised_query_payload)
        resolved, policy, plan = MemoryQueryPlanner().plan(
            scope, request, frozen_now=run.started_at
        )
        checks["query_plan_hash_reproduces"] = (
            plan.query_plan_hash_sha256 == run.query_plan_hash_sha256
        )
        checks["temporal_boundaries_reproduce"] = (
            plan.valid_at == run.valid_at and plan.known_at == run.known_at
        )
        expected_fingerprint = self.engine._query_fingerprint(
            scope, plan, run.relevant_memory_manifest_hash
        )
        checks["query_fingerprint_reproduces"] = (
            expected_fingerprint == run.query_fingerprint_sha256
            and run.query_run_id == f"qrun_{expected_fingerprint[:24]}"
        )
        checks["historical_memory_manifest_available"] = bool(
            run.resolved_event_manifest_hash and run.relevant_memory_manifest_hash
        )
        result = (
            self.engine.get_query_result(scope, run.result_id)
            if run.result_id
            else None
        )
        checks["completed_run_has_result"] = (
            run.query_status != "completed" or result is not None
        )
        bundle = (
            self.engine.get_evidence_bundle(scope, run.evidence_bundle_id)
            if run.evidence_bundle_id
            else None
        )
        explanation = (
            self.engine.get_explanation(scope, result.explanation_id)
            if result and result.explanation_id
            else None
        )
        if result:
            result_material = {
                "query_run_id": run.query_run_id,
                "query_type": result.query_type,
                "status": result.result_status,
                "answer": result.answer_payload,
                "epistemic_summary": result.epistemic_summary,
                "temporal_boundary": result.temporal_boundary,
                "subject_scope": result.subject_scope,
                "evidence_manifest": (
                    bundle.evidence_manifest_hash_sha256 if bundle else None
                ),
                "result_revision": MEMORY_QUERY_RESULT_REVISION,
            }
            manifest = sha256_text(canonical_json(result_material))
            result_payload = {
                **result_material,
                "query_result_id": result.query_result_id,
                "evidence_bundle_id": result.evidence_bundle_id,
                "explanation_id": result.explanation_id,
            }
            result_hash = sha256_text(canonical_json(result_payload))
            checks["result_manifest_reproduces"] = (
                manifest == result.result_manifest_hash_sha256
                and result.query_result_id == f"qres_{manifest[:24]}"
            )
            checks["result_hash_reproduces"] = (
                result_hash == result.result_hash_sha256
                and result_hash == run.result_hash_sha256
            )
            checks["epistemic_summary_matches"] = (
                build_epistemic_summary(result.answer_payload).to_dict()
                == result.epistemic_summary
            )
        else:
            checks["result_manifest_reproduces"] = run.query_status != "completed"
            checks["result_hash_reproduces"] = run.query_status != "completed"
            checks["epistemic_summary_matches"] = run.query_status != "completed"
        if bundle:
            manifest_items = [
                {
                    "evidence_item_id": item.evidence_item_id,
                    "content_hash_sha256": item.content_hash_sha256,
                    "integrity_status": item.integrity_status,
                    "sequence_index": item.sequence_index,
                }
                for item in bundle.evidence_items
            ]
            checks["evidence_bundle_manifest_reproduces"] = (
                sha256_text(canonical_json(manifest_items))
                == bundle.evidence_manifest_hash_sha256
            )
            checks["evidence_items_resolve"] = all(
                item.integrity_status == "verified"
                for item in bundle.evidence_items
            ) or bundle.completeness_status in {
                "legacy_without_source",
                "partial",
                "unavailable",
                "truncated",
            }
            checks["evidence_scope_matches"] = (
                (bundle.client_id, bundle.vault_id, bundle.namespace)
                == scope.memory_boundary()
            )
            checks["evidence_revision_matches"] = (
                bundle.memory_evidence_bundle_revision
                == MEMORY_EVIDENCE_BUNDLE_REVISION
            )
        else:
            checks["evidence_bundle_manifest_reproduces"] = True
            checks["evidence_items_resolve"] = True
            checks["evidence_scope_matches"] = True
            checks["evidence_revision_matches"] = True
        if result and explanation:
            rebuilt = build_memory_explanation(
                query_run_id=run.query_run_id,
                query_result_id=result.query_result_id,
                query_type=result.query_type,
                result_status=result.result_status,
                answer_payload=result.answer_payload,
                plan=plan,
                evidence_bundle=bundle,
                excluded_counts=result.excluded_event_counts,
            )
            checks["explanation_hash_reproduces"] = (
                rebuilt.explanation_hash_sha256
                == explanation.explanation_hash_sha256
                and rebuilt.explanation_id == explanation.explanation_id
            )
            checks["explanation_references_result"] = (
                explanation.query_result_id == result.query_result_id
                and explanation.query_run_id == run.query_run_id
            )
            checks["explanation_revision_matches"] = (
                explanation.memory_explanation_revision
                == MEMORY_EXPLANATION_REVISION
            )
        else:
            checks["explanation_hash_reproduces"] = True
            checks["explanation_references_result"] = True
            checks["explanation_revision_matches"] = True
        checks["pagination_state_valid"] = (
            result is None
            or result.next_cursor is None
            or isinstance(result.next_cursor, str)
        )
        checks["no_future_leakage_boundary_recorded"] = bool(
            run.valid_at and run.known_at
        )
        checks["no_cross_scope_reference"] = self._artifact_scope_check(
            scope, run, result, bundle, explanation
        )
        checks["query_integrity_revision_current"] = (
            run.memory_query_schema_revision == "memory_query_v1"
        )
        failures = [name for name, passed in checks.items() if not passed]
        details.update(
            {
                "query_type": run.query_type,
                "result_status": run.result_status,
                "evidence_count": run.evidence_count,
                "integrity_revision": MEMORY_QUERY_INTEGRITY_REVISION,
            }
        )
        return MemoryQueryIntegrityResult(
            query_run_id=query_run_id,
            verified=not failures,
            checks=checks,
            failures=failures,
            details=details,
        )

    @staticmethod
    def _artifact_scope_check(
        scope: AuthenticatedScope,
        run: object,
        result: object | None,
        bundle: object | None,
        explanation: object | None,
    ) -> bool:
        expected = scope.memory_boundary()
        scoped = [(run.client_id, run.vault_id, run.namespace)]
        if bundle:
            scoped.append((bundle.client_id, bundle.vault_id, bundle.namespace))
        if result:
            run_scope = (
                result.subject_scope.get("client_id"),
                result.subject_scope.get("vault_id"),
                result.subject_scope.get("namespace"),
            )
            if all(run_scope):
                scoped.append(run_scope)
        return all(item == expected for item in scoped)


def _request_from_payload(payload: dict[str, object]):
    from .memory_query_engine import _request_from_payload as build

    return build(payload)


__all__ = ["MemoryQueryIntegrityVerifier"]
