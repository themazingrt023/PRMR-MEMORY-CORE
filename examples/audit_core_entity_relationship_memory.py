"""Independent Core Sprint 6 implementation and evidence audit."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from prmr.core.entity_admission import EntityAdmissionService
from prmr.core.entity_candidates import EntityCandidateEngine
from prmr.core.entity_models import EntityMemoryError
from prmr.core.relationship_candidates import RelationshipCandidateEngine
from prmr.core.source_ledger import SourceLedger
from prmr.core.source_models import AuthenticatedScope, SourceInput
from prmr.product.self_serve_repository_v093 import SelfServeRepositoryV093


REPORT_DIR = ROOT / "reports" / "core_entity_relationship_memory"
PUBLIC_REPORT = REPORT_DIR / "public_entity_relationship_memory.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_entity_relationship_memory.json"
SCORECARD = REPORT_DIR / "scorecard_entity_relationship_memory.md"
FINAL_STATEMENT = (
    "Core Sprint 6 establishes Evidence-Backed Entity Identity and Relationship "
    "Memory inside PRMR Memory Core. Sources and admitted events can now support "
    "scoped canonical entities, stable identifiers, exact mentions, explicit "
    "aliases, controlled identity resolution, event/entity links and bitemporal "
    "relationships without treating names as proof of identity or associations as "
    "causation. Entity-scoped continuity and historical relationship reconstruction "
    "remain fully provenance-backed. Semantic entity matching, automatic causal "
    "reasoning, graph consolidation and public entity APIs remain later core-engine "
    "milestones."
)


def add(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> int:
    checks: list[dict[str, Any]] = []
    required_modules = [
        "entity_models.py",
        "entity_store.py",
        "entity_extraction_rules.py",
        "entity_candidates.py",
        "entity_admission.py",
        "entity_identity_service.py",
        "entity_resolution.py",
        "entity_mentions.py",
        "entity_memory.py",
        "entity_reconstruction.py",
        "entity_integrity.py",
        "entity_memory_fixtures.py",
        "relationship_models.py",
        "relationship_rules.py",
        "relationship_candidates.py",
        "relationship_admission.py",
        "relationship_memory.py",
        "relationship_integrity.py",
    ]
    for name in required_modules:
        add(
            checks,
            f"module_exists_{name.removesuffix('.py')}",
            (ROOT / "prmr" / "core" / name).exists(),
        )
    sqlite_migration = ROOT / "migrations" / "core_entity_relationship_memory_v1_sqlite.sql"
    postgres_migration = ROOT / "migrations" / "core_entity_relationship_memory_v1_postgres.sql"
    add(checks, "sqlite_migration_exists", sqlite_migration.exists())
    add(checks, "postgres_migration_exists", postgres_migration.exists())
    sqlite_sql = read(sqlite_migration)
    required_tables = [
        "prmr_entity_candidates",
        "prmr_entity_evidence",
        "prmr_entities",
        "prmr_entity_identifiers",
        "prmr_entity_mentions",
        "prmr_entity_alias_assertions",
        "prmr_entity_resolution_decisions",
        "prmr_entity_distinctness_assertions",
        "prmr_entity_merges",
        "prmr_event_entity_links",
        "prmr_relationship_candidates",
        "prmr_relationship_evidence",
        "prmr_relationship_admission_decisions",
        "prmr_relationships",
        "prmr_relationship_evolution_records",
        "prmr_relationship_conflicts",
        "prmr_entity_relationship_reconstructions",
    ]
    add(
        checks,
        "sqlite_migration_has_all_tables",
        all(f"CREATE TABLE IF NOT EXISTS {table}" in sqlite_sql for table in required_tables),
    )
    postgres_sql = read(postgres_migration)
    add(
        checks,
        "postgres_migration_has_all_tables",
        all(f"CREATE TABLE IF NOT EXISTS {table}" in postgres_sql for table in required_tables),
    )
    add(
        checks,
        "identifier_active_uniqueness_present",
        "prmr_entity_identifiers_active_unique_idx" in sqlite_sql
        and "identifier_value_digest" in sqlite_sql,
    )
    add(
        checks,
        "event_link_active_uniqueness_present",
        "prmr_event_entity_links_active_unique_idx" in sqlite_sql,
    )
    source_text = "\n".join(
        read(ROOT / "prmr" / "core" / name) for name in required_modules
    )
    revisions = [
        "entity_memory_v1",
        "entity_candidate_v1",
        "entity_extractor_v1",
        "entity_admission_v1",
        "entity_identity_v1",
        "entity_resolution_v1",
        "entity_alias_v1",
        "entity_mention_v1",
        "event_entity_link_v1",
        "relationship_memory_v1",
        "relationship_candidate_v1",
        "relationship_extractor_v1",
        "relationship_admission_v1",
        "relationship_evolution_v1",
        "relationship_resolver_v1",
        "entity_continuity_adapter_v1",
    ]
    add(checks, "all_revision_identifiers_present", all(item in source_text for item in revisions))
    add(checks, "no_python_hash_identity", "hash(" not in source_text.replace("sha256_hash(", ""))
    add(checks, "no_llm_dependency", not re.search(r"\b(openai|anthropic|embedding|spacy)\b", source_text, re.I))
    add(
        checks,
        "no_fuzzy_auto_matching",
        not re.search(r"\bfuzz(?:y|ratio|match)\s*\(", source_text, re.I),
    )
    add(
        checks,
        "source_deletion_dependencies_extended",
        "_entity_relationship_dependency_counts" in read(ROOT / "prmr" / "core" / "source_ledger.py"),
    )
    dynamics_text = read(ROOT / "prmr" / "core" / "memory_dynamics_engine.py")
    add(checks, "entity_adapter_filters_existing_resolver", "event_ids=event_ids" in dynamics_text)
    add(
        checks,
        "existing_formula_services_still_used",
        "recurrence_boost" in dynamics_text
        and "base_time_influence" in dynamics_text
        and "cross_horizon_boost" in dynamics_text,
    )

    add(checks, "public_report_exists", PUBLIC_REPORT.exists())
    add(checks, "private_report_exists", PRIVATE_REPORT.exists())
    add(checks, "scorecard_exists", SCORECARD.exists())
    public = json.loads(read(PUBLIC_REPORT)) if PUBLIC_REPORT.exists() else {}
    private = json.loads(read(PRIVATE_REPORT)) if PRIVATE_REPORT.exists() else {}
    add(checks, "runner_result_pass_with_limitations", public.get("result") == "PASS WITH DOCUMENTED LIMITATIONS")
    add(checks, "runner_checks_all_pass", public.get("passed_checks") == public.get("total_checks") and public.get("total_checks", 0) >= 30)
    add(checks, "sqlite_evidence_passes", public.get("sqlite") == "PASS")
    add(
        checks,
        "postgres_not_faked",
        public.get("postgres") == "NOT_RUN_DATABASE_URL_UNAVAILABLE"
        if not os.getenv("DATABASE_URL")
        else True,
    )
    add(checks, "required_final_statement_present", public.get("final_statement") == FINAL_STATEMENT)
    public_text = json.dumps(public, sort_keys=True)
    secret_patterns = [
        r"(?i)authorization\s*:\s*bearer\s+\S+",
        r"\bsk-[A-Za-z0-9_-]{12,}\b",
        r"\bghp_[A-Za-z0-9]{12,}\b",
        r"\bgithub_pat_[A-Za-z0-9_]{12,}\b",
        r"(?i)api[_-]?key[\"']?\s*[:=]\s*[\"'][^<][^\"']{8,}",
    ]
    add(checks, "public_report_secret_safe", not any(re.search(pattern, public_text) for pattern in secret_patterns))
    add(
        checks,
        "public_report_omits_private_ids",
        "entity_ids" not in public and "relationship_ids" not in public and "source_ids" not in public,
    )
    affirmative_claim_patterns = [
        r'"automatic_causal_discovery"\s*:\s*true',
        r'"semantic_identity_resolution"\s*:\s*true',
        r"\bis production[- ]ready\b",
        r"\bis scientifically validated\b",
        r"\bprovides human-level entity understanding\b",
        r"\bautomatically determines truth\b",
    ]
    add(
        checks,
        "public_claims_honest",
        not any(
            re.search(pattern, public_text, re.I)
            for pattern in affirmative_claim_patterns
        ),
    )

    with TemporaryDirectory(prefix="prmr-s6-audit-") as temporary:
        repository = SelfServeRepositoryV093(Path(temporary) / "audit.sqlite")
        scoped = AuthenticatedScope("audit_client", "audit_vault", "default")
        label_source = SourceLedger(repository).ingest_source(
            scoped,
            SourceInput(
                "plain_text",
                "Project: Audit Project",
                idempotency_key="audit-label-only",
            ),
        ).source
        label_candidates = EntityCandidateEngine(repository).extract_source_entities(
            scoped, label_source.source_id
        )
        auto = EntityAdmissionService(repository).auto_admit_safe_candidates(scoped)
        add(checks, "label_only_candidate_extracted", len(label_candidates) == 1)
        add(
            checks,
            "label_only_candidate_not_auto_admitted",
            label_candidates[0].entity_candidate_id in auto["skipped_candidate_ids"],
        )
        capitals_source = SourceLedger(repository).ingest_source(
            scoped,
            SourceInput(
                "plain_text",
                "Mercury Thursday Silver Mountain.",
                idempotency_key="audit-capitals",
            ),
        ).source
        capitals = EntityCandidateEngine(repository).extract_source_entities(
            scoped, capitals_source.source_id
        )
        add(checks, "plain_capitals_remain_unextracted", len(capitals) == 0)
        negated_source = SourceLedger(repository).ingest_source(
            scoped,
            SourceInput(
                "plain_text",
                "Audit Project does not depend on Legacy System.",
                idempotency_key="audit-negated",
            ),
        ).source
        negated = RelationshipCandidateEngine(repository).extract_source_relationships(
            scoped, negated_source.source_id
        )
        add(checks, "negation_blocks_relationship_candidate", len(negated) == 0)

    compile_result = subprocess.run(
        [sys.executable, "-m", "compileall", "-q", "prmr/core"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    add(checks, "python_compilation_passes", compile_result.returncode == 0, compile_result.stderr.strip())
    diff_check = subprocess.run(
        ["git", "diff", "--check"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    add(checks, "git_diff_check_passes", diff_check.returncode == 0, diff_check.stdout.strip())

    failed = [item for item in checks if not item["passed"]]
    result = "PASS WITH DOCUMENTED LIMITATIONS" if not failed else "NEEDS WORK"
    audit_payload = {
        "audit_result": result,
        "passed_checks": len(checks) - len(failed),
        "total_checks": len(checks),
        "failed_checks": [item["name"] for item in failed],
        "checks": checks,
    }
    private["independent_audit"] = audit_payload
    PRIVATE_REPORT.write_text(
        json.dumps(private, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print("PRMR Memory Core — Core Sprint 6 Independent Audit")
    print(f"Passed checks: {audit_payload['passed_checks']}/{audit_payload['total_checks']}")
    if failed:
        print("Failed checks: " + ", ".join(item["name"] for item in failed))
    print(f"Result: {result}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
