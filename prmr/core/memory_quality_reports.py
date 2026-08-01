"""Secret-safe reports and separate per-capability scorecard rendering."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .memory_quality_policy import REQUIRED_FINAL_STATEMENT


REPORT_NAMES = (
    "corpus_manifest_memory_quality.json",
    "case_results_sqlite.json",
    "case_results_postgres.json",
    "metrics_memory_quality.json",
    "quality_gates_memory_quality.json",
    "mutation_results_memory_quality.json",
    "backend_parity_memory_quality.json",
    "adversarial_results_memory_quality.json",
    "public_memory_quality.json",
    "private_internal_memory_quality.json",
    "audit_memory_quality.json",
    "benchmark_memory_quality.json",
    "scorecard_memory_quality.md",
)


DOMAIN_TITLES = {
    "source_fidelity": "Source Fidelity",
    "candidate_memory": "Candidate Memory",
    "epistemic_safety": "Epistemic Safety",
    "admission": "Admission",
    "bitemporal_reconstruction": "Bitemporal Reconstruction",
    "temporal_dynamics": "Temporal Dynamics",
    "entity_identity": "Entity Identity",
    "relationships": "Relationships",
    "query_and_evidence": "Query and Evidence",
    "consolidation": "Consolidation",
    "interpretation": "Interpretation",
    "governance": "Governance",
    "runtime_backend_parity": "Runtime and Backend Parity",
}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def build_scorecard(
    *, status: str, metrics: dict[str, Any], gates: list[dict[str, Any]],
    mutations: dict[str, Any], parity: dict[str, Any], limitations: list[str],
) -> str:
    lines = [
        "# Core Sprint 12 - Memory Quality Benchmark",
        "",
        f"**Result:** {status}",
        "",
        "No aggregate intelligence or universal memory-quality score is calculated.",
        "",
    ]
    gate_by_domain: dict[str, list[dict[str, Any]]] = {}
    for gate in gates:
        gate_by_domain.setdefault(gate["domain"], []).append(gate)
    for domain, title in DOMAIN_TITLES.items():
        value = metrics["domains"].get(domain, {})
        lines.extend([
            f"## {title}",
            "",
            f"- Cases: {value.get('cases', 0)}",
            f"- Assertions: {value.get('assertions', 0)}",
            f"- Passed: {value.get('passed_cases', 0)}",
            f"- Failed: {value.get('failed_cases', 0)}",
            f"- Exact assertion accuracy: {value.get('exact_match_accuracy', {}).get('percentage', 0)}%",
            "- Quality gates: " + ", ".join(
                f"{item['metric']}={'PASS' if item['passed'] else 'FAIL'}"
                for item in gate_by_domain.get(domain, [])
            ),
            "- Limitations: Internal synthetic corpus; shared lifecycle fixtures are labelled and do not imply external validation.",
            "",
        ])
    lines.extend([
        "## Mutation Sensitivity",
        "",
        f"- Critical mutations: {mutations.get('critical_mutation_count', 0)}",
        f"- Detected: {mutations.get('detected_count', 0)}",
        f"- Detection rate: {round(float(mutations.get('detection_rate', 0)) * 100, 4)}%",
        "",
        "## Backend Parity",
        "",
        f"- Logical cases compared: {parity.get('compared_case_count', 0)}",
        f"- Mismatches: {parity.get('mismatch_count', 0)}",
        "",
        "## Documented Limitations",
        "",
        *[f"- {item}" for item in limitations],
        "",
        REQUIRED_FINAL_STATEMENT,
        "",
    ])
    return "\n".join(lines)


__all__ = ["DOMAIN_TITLES", "REPORT_NAMES", "build_scorecard", "write_json"]
