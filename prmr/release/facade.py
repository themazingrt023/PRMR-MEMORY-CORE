"""Conservative stable facade over authoritative Core 1-13 services."""

from __future__ import annotations

from typing import Any

from prmr.core.admission_service import MemoryAdmissionService
from prmr.core.candidate_engine import CandidateMemoryEngine
from prmr.core.continuity_v2_packet import ContinuityPacketV2Service
from prmr.core.entity_admission import EntityAdmissionService
from prmr.core.entity_candidates import EntityCandidateEngine
from prmr.core.interpretation_engine import InterpretationEngine
from prmr.core.memory_consolidation_engine import MemoryConsolidationEngine
from prmr.core.memory_export_service import MemoryExportService
from prmr.core.memory_governance_executor import MemoryGovernanceExecutor
from prmr.core.memory_governance_planner import MemoryGovernancePlanner
from prmr.core.memory_ledger_service import MemoryLedgerService
from prmr.core.memory_query_engine import MemoryQueryEngine
from prmr.core.relationship_admission import RelationshipAdmissionService
from prmr.core.relationship_candidates import RelationshipCandidateEngine
from prmr.core.source_ledger import SourceLedger


class PRMRMemoryCore:
    """RC1 stable-internal service boundary; methods delegate without reimplementation."""

    INTERFACE_CATEGORIES = {
        "source_ingestion": "stable_internal",
        "candidate_extraction": "stable_internal",
        "admission": "stable_internal",
        "memory_evolution": "stable_internal",
        "entities": "stable_internal",
        "relationships": "stable_internal",
        "query": "stable_internal",
        "consolidation": "stable_internal",
        "interpretation": "experimental_internal",
        "governance": "stable_internal",
        "export": "stable_internal",
        "continuity_packet_v1": "legacy_compatible",
        "continuity_packet_v2": "stable_internal",
        "repository_helpers": "test_only",
    }

    def __init__(self, repository: Any) -> None:
        self.repository = repository
        self.sources = SourceLedger(repository, initialize=False)
        self.candidates = CandidateMemoryEngine(repository, initialize=False)
        self.admissions = MemoryAdmissionService(repository, initialize=False)
        self.ledger = MemoryLedgerService(repository, initialize=False)
        self.entities = EntityCandidateEngine(repository, initialize=False)
        self.entity_admission = EntityAdmissionService(repository, initialize=False)
        self.relationships = RelationshipCandidateEngine(repository, initialize=False)
        self.relationship_admission = RelationshipAdmissionService(repository, initialize=False)
        self.queries = MemoryQueryEngine(repository, initialize=False)
        self.consolidation = MemoryConsolidationEngine(repository, initialize=False)
        self.interpretation = InterpretationEngine(repository, initialize=False)
        self.governance = MemoryGovernancePlanner(repository, initialize=False)
        self.governance_execution = MemoryGovernanceExecutor(repository, initialize=False)
        self.exports = MemoryExportService(repository, initialize=False)
        self.continuity_v2 = ContinuityPacketV2Service(repository, initialize=False)

    def ingest_source(self, scope: Any, source_input: Any) -> Any:
        return self.sources.ingest_source(scope, source_input)

    def extract_candidates(self, scope: Any, source_id: str) -> Any:
        return self.candidates.extract_candidates(scope, source_id)

    def admit_candidate(self, scope: Any, candidate_id: str, actor: Any, reason: str, idempotency_key: str) -> Any:
        return self.admissions.accept_candidate(scope, candidate_id, actor, reason, idempotency_key)

    def query_memory(self, scope: Any, request: Any) -> Any:
        return self.queries.query_memory(scope, request)

    def generate_continuity_packet_v2(self, scope: Any, *, temporal_boundary: Any) -> Any:
        return self.continuity_v2.generate_packet_v2(scope, temporal_boundary=temporal_boundary)

    def interface_manifest(self) -> dict[str, str]:
        return dict(sorted(self.INTERFACE_CATEGORIES.items()))


__all__ = ["PRMRMemoryCore"]
