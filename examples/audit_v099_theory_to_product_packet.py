"""Audit V0.99 theory-to-product continuity packet upgrade."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from examples.run_v099_theory_to_product_packet import (
    BOUNDARY_V099,
    REPORT_DIR,
    SMOKE_REPORT,
    run_flow,
    write_json,
)


PUBLIC_REPORT = REPORT_DIR / "public_theory_to_product_packet_v099.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_theory_to_product_packet_v099.json"
SCORECARD = REPORT_DIR / "scorecard_v099.md"
DOC_PATH = ROOT / "docs" / "theory_to_product_packet_v099.md"
CORE_PATH = ROOT / "prmr" / "product" / "controlled_alpha_api_v071.py"


def add(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def command(command_args: list[str]) -> tuple[bool, str]:
    completed = subprocess.run(
        command_args,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.returncode == 0, (completed.stdout + "\n" + completed.stderr).strip()[-1400:]


def contains_secret(payload: Any) -> bool:
    text = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True)
    patterns = [
        r"\bsk-[A-Za-z0-9_\-]{8,}\b",
        r"\bghp_[A-Za-z0-9]{20,}\b",
        r"\bgithub_pat_[A-Za-z0-9_]{20,}\b",
        r"Authorization:\s*Bearer\s+(?!<PRMR_API_KEY>)[A-Za-z0-9_\-\.]{20,}",
        r"prmr_alpha_[A-Za-z0-9_\-]{16,}",
        r"postgres(?:ql)?://[^\\s]+",
    ]
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def build_scorecard(public: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# V0.99 Theory-to-Product Continuity Packet",
            "",
            f"Result: {public['result']}",
            f"Checks: {public['checks_passed']}/{public['checks_total']}",
            "",
            "Packet fields added:",
            "- current_state",
            "- active_information",
            "- latent_information",
            "- lineage_information",
            "- causal_signature",
            "- recursive_horizon",
            "- coherence_score",
            "- recoverability_score",
            "- re_emergence_signals",
            "- decayed_signals",
            "- repeated_patterns",
            "- state_transition_summary",
            "",
            "Boundary: deterministic product approximation only; no scientific validation or certification claim.",
            "",
        ]
    )


def main() -> int:
    checks: list[dict[str, Any]] = []
    core_text = read(CORE_PATH)
    doc_text = read(DOC_PATH)
    smoke_checks, smoke_details, private_trace = run_flow()
    smoke_passed = sum(1 for check in smoke_checks if check["passed"])
    smoke_result = "PASS" if smoke_passed == len(smoke_checks) else "NEEDS_WORK"
    write_json(
        SMOKE_REPORT,
        {
            "version": "0.99",
            "title": "Theory-to-Product Continuity Packet Smoke",
            "result": smoke_result,
            "checks_passed": smoke_passed,
            "checks_total": len(smoke_checks),
            "details": smoke_details,
            "public_safe": True,
            "boundary": BOUNDARY_V099,
        },
    )
    smoke_by_name = {check["name"]: check["passed"] for check in smoke_checks}
    for name in [
        "empty_scope_returns_safe_empty_packet",
        "single_event_creates_current_state_and_active_information",
        "repeated_events_create_lineage_information",
        "dormant_old_signals_become_latent_information",
        "returning_dormant_signal_becomes_re_emergence",
        "missing_old_signal_becomes_decayed",
        "causal_signature_includes_stable_patterns",
        "recursive_horizon_separates_recent_and_historical",
        "stable_repeated_patterns_improve_coherence_score",
        "ordered_complete_events_improve_recoverability_score",
        "generic_v098_events_contribute_correctly",
        "legacy_type_content_events_contribute_correctly",
        "metadata_is_sanitized",
        "unsafe_metadata_is_redacted",
        "bearer_auth_still_required",
        "wrong_and_malformed_keys_fail",
        "revoked_key_fails",
    ]:
        add(checks, name, smoke_by_name.get(name, False))

    add(checks, "engine_fields_computed_in_core", all(term in core_text for term in ["build_theory_packet", "coherence_score", "recoverability_score", "re_emergence_signals"]))
    add(checks, "docs_exist", DOC_PATH.exists())
    add(checks, "docs_explain_deterministic_approximation", "deterministic product approximation" in doc_text and "does not claim full empirical validation" in doc_text)
    add(checks, "public_report_contains_no_secrets", not contains_secret(smoke_details))

    v098_ok, v098_output = command(["python", "examples/audit_v098_external_event_contract.py"])
    add(checks, "existing_v098_external_event_contract_audit_passes", v098_ok, v098_output)
    key_ok, key_output = command(["python", "examples/audit_external_api_key_usability.py"])
    add(checks, "existing_external_api_key_usability_audit_passes", key_ok, key_output)
    isolation_ok, isolation_output = command(["python", "examples/audit_v084_multi_client_isolation.py"])
    add(checks, "multi_client_isolation_still_passes", isolation_ok, isolation_output)
    secret_ok, secret_output = command(["python", "examples/audit_v0782_secret_cleanup.py"])
    add(checks, "secret_audit_still_passes", secret_ok, secret_output)

    failures = [check for check in checks if not check["passed"]]
    result = "PASS" if not failures else "NEEDS_WORK"
    public = {
        "version": "0.99",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "Theory-to-Product Continuity Packet Audit",
        "result": result,
        "checks_passed": len(checks) - len(failures),
        "checks_total": len(checks),
        "public_safe": True,
        "truth_label": "deterministic PRMR theory-to-product packet evidence only",
        "packet_fields": [
            "current_state",
            "active_information",
            "latent_information",
            "lineage_information",
            "causal_signature",
            "recursive_horizon",
            "coherence_score",
            "recoverability_score",
            "re_emergence_signals",
            "decayed_signals",
            "repeated_patterns",
            "state_transition_summary",
            "event_count",
            "last_updated",
        ],
        "deterministic_rules": {
            "active_information": "signals inside recent horizon",
            "latent_information": "historical signals absent from recent horizon",
            "lineage_information": "repeated signal traces with first/latest anchors",
            "causal_signature": "frequency, transitions, source distribution, stable repeated patterns",
            "recursive_horizon": "short recent window versus long historical signal set",
            "coherence_score": "weighted repeat, overlap, actor/workspace consistency, and volume score",
            "recoverability_score": "weighted content, ordering, anchors, timestamps, lineage, and volume score",
        },
        "smoke_details": smoke_details,
        "raw_key_exposed": False,
        "boundary": BOUNDARY_V099,
        "remaining_gaps": [
            "full scientific validation of PRMR theory",
            "longitudinal memory quality testing",
            "richer metadata-aware packet evolution",
            "external approved non-sensitive alpha evidence",
        ],
    }
    private = {**public, "public_safe": False, "checks": checks, "smoke_checks": smoke_checks, "private_trace": private_trace}
    write_json(PUBLIC_REPORT, public)
    write_json(PRIVATE_REPORT, private)
    SCORECARD.write_text(build_scorecard(public), encoding="utf-8")
    print("PRMR V0.99 Theory-to-Product Packet Audit")
    print(f"Passed checks: {public['checks_passed']}/{public['checks_total']}")
    print(f"Result: {result}")
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
