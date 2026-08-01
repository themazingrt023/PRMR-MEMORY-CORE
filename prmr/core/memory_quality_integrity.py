"""Corpus and benchmark-evidence integrity verification."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .memory_quality_corpus import load_corpus
from .memory_quality_oracle import validate_gold_oracle
from .memory_quality_policy import MEMORY_QUALITY_INTEGRITY_REVISION
from .source_integrity import canonical_json, sha256_text


def verify_memory_quality_corpus_integrity(root: Path) -> dict[str, Any]:
    manifest, cases = load_corpus(root)
    file_checks = []
    for record in manifest["case_files"]:
        text = (root / record["file"]).read_text(encoding="utf-8")
        rows = [line for line in text.splitlines() if line.strip()]
        file_checks.append({
            "file": record["file"],
            "hash_verified": sha256_text(text) == record["sha256"],
            "case_count_verified": len(rows) == record["case_count"],
            "assertion_count_verified": sum(
                len(json.loads(line)["expected_assertions"]) for line in rows
            ) == record["assertion_count"],
        })
    root_payload = {key: value for key, value in manifest.items() if key != "root_corpus_hash"}
    oracle = validate_gold_oracle(cases)
    verified = (
        all(all(value for key, value in item.items() if key != "file") for item in file_checks)
        and sha256_text(canonical_json(root_payload)) == manifest["root_corpus_hash"]
        and len(cases) == manifest["case_count"]
        and sum(len(case.expected_assertions) for case in cases) == manifest["assertion_count"]
        and oracle["verified"]
    )
    return {
        "verified": verified,
        "root_hash_verified": sha256_text(canonical_json(root_payload)) == manifest["root_corpus_hash"],
        "file_checks": file_checks,
        "oracle": oracle,
        "revision": MEMORY_QUALITY_INTEGRITY_REVISION,
    }


def verify_memory_quality_run_integrity(
    *, corpus_manifest: dict[str, Any], run: dict[str, Any], case_results: list[dict[str, Any]]
) -> dict[str, Any]:
    case_ids = [item["benchmark_case_id"] for item in case_results]
    required_not_skipped = all(item["case_status"] != "skipped_with_reason" for item in case_results)
    checks = {
        "corpus_hash": run["corpus_manifest_hash"] == corpus_manifest["root_corpus_hash"],
        "case_count": run["case_count"] == len(case_results) == corpus_manifest["case_count"],
        "unique_case_execution": len(case_ids) == len(set(case_ids)),
        "no_required_skip": required_not_skipped,
        "result_hashes_present": all(item.get("result_hash") for item in case_results),
        "assertion_identities_present": all(
            assertion.get("assertion_id")
            for item in case_results for assertion in item["assertion_results"]
        ),
        "backend_identity": run["backend"] in {"sqlite", "postgres"},
        "engine_revision_manifest": bool(run["engine_revision_manifest"]),
        "metrics_present": bool(run["metric_results"]),
    }
    return {
        "verified": all(checks.values()),
        "checks": checks,
        "revision": MEMORY_QUALITY_INTEGRITY_REVISION,
    }


__all__ = ["verify_memory_quality_corpus_integrity", "verify_memory_quality_run_integrity"]
