"""Read-only, scope-isolated deterministic Memory Core exports."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json
import logging
import re
from typing import Any

from .entity_store import json_value
from .memory_governance_models import (
    MEMORY_EXPORT_MANIFEST_REVISION,
    MEMORY_EXPORT_SCHEMA_REVISION,
    MemoryExportBundle,
    MemoryExportRequest,
    MemoryGovernanceError,
)
from .memory_governance_planner import MemoryGovernancePlanner
from .memory_governance_store import MemoryGovernanceStore
from .runtime_failure_injection import RuntimeFailureInjector
from .source_integrity import canonical_json, sha256_text
from .source_models import AuthenticatedScope


LOGGER = logging.getLogger("prmr.core.memory_governance")
SECRET_VALUE = re.compile(
    r"(?:prmr_(?:live|alpha)_|authorization\s*:\s*bearer|github_pat_|ghp_|sk-)",
    re.I,
)
SECRET_KEYS = {
    "api_key",
    "authorization",
    "token",
    "access_token",
    "refresh_token",
    "database_url",
    "provider_credentials",
}

SECTION_TYPES = {
    "sources": {"source"},
    "segments": {"segment"},
    "candidates": {"candidate_memory", "candidate_evidence", "extraction_run"},
    "admissions": {"admission", "admitted_memory_link"},
    "events": {"event"},
    "evolutions": {"event_evolution"},
    "dynamics": {"dynamics_snapshot", "signal_dynamics", "importance_annotation"},
    "entities": {
        "entity",
        "entity_candidate",
        "entity_evidence",
        "entity_alias",
        "entity_identifier",
        "entity_mention",
        "entity_resolution",
        "event_entity_link",
    },
    "relationships": {
        "relationship",
        "relationship_candidate",
        "relationship_evidence",
        "relationship_admission",
        "relationship_evolution",
    },
    "conflicts": {"memory_conflict", "relationship_conflict"},
    "queries": {"query_run", "query_result", "evidence_bundle", "evidence_item", "explanation"},
    "consolidations": {
        "consolidation_run",
        "consolidation_plan",
        "consolidated_memory",
        "consolidation_member",
        "checkpoint",
        "checkpoint_delta",
    },
    "interpretation": {
        "interpretation_request",
        "interpretation_attempt",
        "interpretation_response",
        "interpretation_unknown",
        "interpretation_validation_failure",
        "interpretation_proposal_link",
    },
    "canonical_signals": {
        "canonical_signal_definition",
        "canonical_signal_proposal",
        "canonical_signal_decision",
        "canonical_signal_alias",
        "event_signal_projection",
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class MemoryExportService:
    def __init__(
        self,
        repository: Any,
        *,
        initialize: bool = True,
        failure_injector: RuntimeFailureInjector | None = None,
    ) -> None:
        self.repository = repository
        self.store = MemoryGovernanceStore(repository, initialize=initialize)
        self.planner = MemoryGovernancePlanner(repository, initialize=False)
        self.failure_injector = failure_injector or RuntimeFailureInjector()

    def create_export(
        self,
        scope: AuthenticatedScope,
        governance_plan_id: str,
        *,
        valid_at: str | None = None,
        known_at: str | None = None,
        include_raw_sources: bool = True,
        expires_at: str | None = None,
        generated_at: str | None = None,
    ) -> MemoryExportBundle:
        plan = self.planner.get_plan(scope, governance_plan_id)
        if plan.action_type != "export" or plan.plan_status != "approved":
            raise MemoryGovernanceError(
                "GOVERNANCE_PLAN_NOT_APPROVED",
                "Export requires an approved read-only governance plan.",
            )
        request = self.planner.get_request(scope, plan.governance_request_id)
        now = generated_at or utc_now()
        export_material = {
            "governance_request": request.governance_request_id,
            "plan": plan.plan_hash_sha256,
            "valid_at": valid_at,
            "known_at": known_at,
            "include_raw_sources": include_raw_sources,
            "revision": MEMORY_EXPORT_SCHEMA_REVISION,
        }
        export_request_id = (
            f"expreq_{sha256_text(canonical_json(export_material))[:24]}"
        )
        retained = set(plan.planned_retain_nodes)
        sections: dict[str, list[dict[str, Any]]] = {
            name: [] for name in SECTION_TYPES
        }
        redactions = 0
        for node, payload, _ in self.planner.graphs._scope_records(scope):
            if node.node_id not in retained:
                continue
            section = next(
                (
                    name
                    for name, node_types in SECTION_TYPES.items()
                    if node.node_type in node_types
                ),
                None,
            )
            if not section:
                continue
            if section == "sources" and not include_raw_sources:
                safe_payload = {
                    key: value
                    for key, value in payload.items()
                    if key
                    not in {
                        "sanitised_payload",
                        "sanitised_payload_json",
                        "content",
                    }
                }
                redactions += 1
            else:
                safe_payload, count = self._redact(payload)
                redactions += count
            sections[section].append(
                {
                    "node_type": node.node_type,
                    "storage_key_digest": sha256_text(node.storage_key),
                    "content": safe_payload,
                    "content_hash_sha256": sha256_text(
                        canonical_json(safe_payload)
                    ),
                }
            )
        ordered_sections = {
            key: tuple(
                sorted(
                    values,
                    key=lambda item: (
                        item["node_type"],
                        item["storage_key_digest"],
                    ),
                )
            )
            for key, values in sections.items()
            if values
        }
        section_hashes = {
            key: sha256_text(canonical_json(values))
            for key, values in ordered_sections.items()
        }
        object_counts = {
            key: len(values) for key, values in ordered_sections.items()
        }
        completeness = (
            "policy_limited" if not include_raw_sources else "complete_retained_scope"
        )
        manifest_material = {
            "request": export_request_id,
            "scope": scope.memory_boundary(),
            "target_type": request.target_type,
            "target_digest": request.target_reference_digest,
            "valid_at": valid_at,
            "known_at": known_at,
            "section_hashes": section_hashes,
            "object_counts": object_counts,
            "completeness": completeness,
            "legacy_provenance_limitations": (
                "Legacy records may have legacy_unclassified epistemic status."
            ),
            "erased_evidence_markers": True,
            "truncated": False,
            "redaction_count": redactions,
            "revision": MEMORY_EXPORT_MANIFEST_REVISION,
        }
        manifest_hash = sha256_text(canonical_json(manifest_material))
        bundle_id = f"expbun_{manifest_hash[:24]}"
        existing = self.store.get(
            "export_bundle",
            "memory_export_bundle_id",
            bundle_id,
            scope.memory_boundary(),
        )
        if existing:
            return self._bundle(existing)
        export_request = MemoryExportRequest(
            memory_export_request_id=export_request_id,
            governance_request_id=request.governance_request_id,
            export_type="canonical_json_manifest_jsonl_sections",
            target_type=request.target_type,
            target_reference_digest=request.target_reference_digest,
            scope=scope.memory_boundary(),
            export_policy_id=request.governance_policy_id,
            valid_at=valid_at,
            known_at=known_at,
            include_raw_sources=include_raw_sources,
            include_segments=True,
            include_candidates=True,
            include_admissions=True,
            include_events=True,
            include_evolutions=True,
            include_temporal_dynamics=True,
            include_entities=True,
            include_relationships=True,
            include_conflicts=True,
            include_queries=True,
            include_consolidations=True,
            include_interpretation=True,
            include_canonical_mappings=True,
            export_status="completed",
            created_at=now,
            completed_at=now,
        )
        bundle = MemoryExportBundle(
            memory_export_bundle_id=bundle_id,
            memory_export_request_id=export_request_id,
            scope=scope.memory_boundary(),
            target_type=request.target_type,
            valid_at=valid_at,
            known_at=known_at,
            export_schema_revision=MEMORY_EXPORT_SCHEMA_REVISION,
            export_policy_revision=request.governance_policy_id,
            sections=ordered_sections,
            object_counts=object_counts,
            completeness_status=completeness,
            redaction_count=redactions,
            bundle_manifest_hash_sha256=manifest_hash,
            generated_at=now,
            expires_at=expires_at,
            storage_reference=None,
            created_at=now,
        )
        request_columns = (
            "memory_export_request_id",
            "governance_request_id",
            "client_id",
            "vault_id",
            "namespace",
            "target_type",
            "target_reference_digest",
            "export_status",
            "created_at",
            "completed_at",
        )
        request_values = (
            export_request_id,
            request.governance_request_id,
            scope.client_id,
            scope.vault_id,
            scope.namespace,
            request.target_type,
            request.target_reference_digest,
            "completed",
            now,
            now,
        )
        bundle_columns = (
            "memory_export_bundle_id",
            "memory_export_request_id",
            "client_id",
            "vault_id",
            "namespace",
            "target_type",
            "target_reference_digest",
            "bundle_manifest_hash_sha256",
            "expires_at",
            "created_at",
        )
        bundle_values = (
            bundle_id,
            export_request_id,
            scope.client_id,
            scope.vault_id,
            scope.namespace,
            request.target_type,
            request.target_reference_digest,
            manifest_hash,
            expires_at,
            now,
        )
        bundle_payload = {
            **bundle.to_dict(),
            "manifest": manifest_material,
            "section_hashes": section_hashes,
        }
        try:
            self._insert_export_atomically(
                request_columns,
                request_values,
                export_request.to_dict(),
                bundle_columns,
                bundle_values,
                bundle_payload,
            )
        except Exception as exc:
            if not self._is_unique_conflict(exc):
                raise
            replay = self.store.get(
                "export_bundle",
                "memory_export_bundle_id",
                bundle_id,
                scope.memory_boundary(),
            )
            if not replay:
                raise
            return self._bundle(replay)
        LOGGER.info(
            "memory_export_created",
            extra={
                "memory_export_bundle_id": bundle_id,
                "object_count": sum(object_counts.values()),
            },
        )
        return bundle

    def _insert_export_atomically(
        self,
        request_columns: tuple[str, ...],
        request_values: tuple[Any, ...],
        request_payload: dict[str, Any],
        bundle_columns: tuple[str, ...],
        bundle_values: tuple[Any, ...],
        bundle_payload: dict[str, Any],
    ) -> None:
        """Commit the request and bundle together or leave neither behind."""

        with self.repository.connect() as connection:
            request_all_columns = (*request_columns, "payload_json")
            connection.execute(
                f"INSERT INTO {self.store.tables['export_request']}"
                f"({','.join(request_all_columns)}) "
                f"VALUES({','.join([self.store.p] * len(request_all_columns))})",
                (*request_values, json_value(self.repository, request_payload)),
            )
            self.failure_injector.inject("after_first_write")
            bundle_all_columns = (*bundle_columns, "payload_json")
            connection.execute(
                f"INSERT INTO {self.store.tables['export_bundle']}"
                f"({','.join(bundle_all_columns)}) "
                f"VALUES({','.join([self.store.p] * len(bundle_all_columns))})",
                (*bundle_values, json_value(self.repository, bundle_payload)),
            )

    @staticmethod
    def _is_unique_conflict(error: BaseException) -> bool:
        if getattr(error, "sqlstate", None) == "23505":
            return True
        return "unique constraint" in str(error).lower()

    def verify_export_integrity(
        self, scope: AuthenticatedScope, export_bundle_id: str
    ) -> dict[str, Any]:
        payload = self.store.get(
            "export_bundle",
            "memory_export_bundle_id",
            export_bundle_id,
            scope.memory_boundary(),
        )
        if not payload:
            raise MemoryGovernanceError(
                "GOVERNANCE_EXPORT_NOT_FOUND",
                "Export bundle was not found in scope.",
            )
        section_hashes = {
            key: sha256_text(canonical_json(values))
            for key, values in payload["sections"].items()
        }
        manifest = dict(payload["manifest"])
        checks = {
            "section_hashes": section_hashes == payload["section_hashes"],
            "object_counts": {
                key: len(values) for key, values in payload["sections"].items()
            }
            == payload["object_counts"],
            "scope": tuple(payload["scope"]) == scope.memory_boundary(),
            "manifest_hash": sha256_text(canonical_json(manifest))
            == payload["bundle_manifest_hash_sha256"],
            "revision": payload["export_schema_revision"]
            == MEMORY_EXPORT_SCHEMA_REVISION,
            "secret_safe": not SECRET_VALUE.search(canonical_json(payload)),
        }
        verified = all(checks.values())
        LOGGER.info(
            "memory_export_verified",
            extra={
                "memory_export_bundle_id": export_bundle_id,
                "status": "verified" if verified else "failed",
            },
        )
        return {
            "verified": verified,
            "checks": checks,
            "bundle_manifest_hash_sha256": payload[
                "bundle_manifest_hash_sha256"
            ],
        }

    @classmethod
    def _redact(cls, value: Any, key: str | None = None) -> tuple[Any, int]:
        if key and key.lower() in SECRET_KEYS:
            return "[REDACTED]", 1
        if isinstance(value, dict):
            output = {}
            count = 0
            for child_key, child in value.items():
                output[child_key], child_count = cls._redact(child, child_key)
                count += child_count
            return output, count
        if isinstance(value, list):
            output = []
            count = 0
            for child in value:
                item, child_count = cls._redact(child, key)
                output.append(item)
                count += child_count
            return output, count
        if isinstance(value, str) and SECRET_VALUE.search(value):
            return "[REDACTED]", 1
        return value, 0

    @staticmethod
    def _bundle(payload: dict[str, Any]) -> MemoryExportBundle:
        allowed = {
            field
            for field in MemoryExportBundle.__dataclass_fields__
        }
        filtered = {key: value for key, value in payload.items() if key in allowed}
        filtered["scope"] = tuple(filtered["scope"])
        filtered["sections"] = {
            key: tuple(items) for key, items in filtered["sections"].items()
        }
        return MemoryExportBundle(**filtered)


__all__ = ["MemoryExportService"]
