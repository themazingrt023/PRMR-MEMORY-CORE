"""Audit V0.98 generic external event contract."""

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

from examples.run_external_event_contract_smoke_v098 import (
    BOUNDARY_V098,
    REPORT_DIR,
    SMOKE_REPORT,
    run_smoke,
    write_json,
)


PUBLIC_REPORT = REPORT_DIR / "public_external_event_contract_v098.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_external_event_contract_v098.json"
SCORECARD = REPORT_DIR / "scorecard_v098.md"
DOC_PATH = ROOT / "docs" / "external_event_contract_v098.md"
API_PATH = ROOT / "prmr" / "product" / "controlled_alpha_api_v071.py"
SERVER_PATH = ROOT / "prmr" / "product" / "api_server_v094.py"


def add(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


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


def has_false_claim(payload: Any) -> bool:
    text = payload.lower() if isinstance(payload, str) else json.dumps(payload, sort_keys=True).lower()
    claims = [
        "production ready",
        "security certified",
        "externally validated",
        "compliance approved",
        "legal approved",
        "guaranteed",
        "bank approved",
    ]
    for claim in claims:
        for paragraph in re.split(r"\n\s*\n", text):
            if claim in paragraph and not re.search(r"\b(not|no|does not|is not|without|later|future)\b", paragraph):
                return True
    return False


def command(command: list[str]) -> tuple[bool, str]:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.returncode == 0, (completed.stdout + "\n" + completed.stderr).strip()[-1600:]


def build_scorecard(public: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# V0.98 Generic External Event Contract",
            "",
            f"Result: {public['result']}",
            f"Checks: {public['checks_passed']}/{public['checks_total']}",
            "",
            "Truth label: generic external event contract evidence only.",
            "",
            "Supported ingest shapes:",
            "- legacy events[] type/content batch",
            "- generic external events[] event_type/signal batch",
            "- generic external single event convenience envelope",
            "",
            "Boundary: This does not claim long-term memory quality, production security certification, compliance approval, legal approval, or external validation.",
            "",
        ]
    )


def main() -> int:
    checks: list[dict[str, Any]] = []
    api_text = read(API_PATH)
    server_text = read(SERVER_PATH)
    doc_text = read(DOC_PATH)

    smoke_checks, smoke_details, private_trace = run_smoke()
    smoke_passed = sum(1 for check in smoke_checks if check["passed"])
    smoke_result = "PASS" if smoke_passed == len(smoke_checks) else "NEEDS_WORK"
    write_json(
        SMOKE_REPORT,
        {
            "version": "0.98",
            "title": "Generic External Event Contract Smoke",
            "result": smoke_result,
            "checks_passed": smoke_passed,
            "checks_total": len(smoke_checks),
            "details": smoke_details,
            "public_safe": True,
            "boundary": BOUNDARY_V098,
        },
    )

    by_name = {check["name"]: check["passed"] for check in smoke_checks}
    for name in [
        "legacy_type_content_payload_works",
        "batch_generic_payload_works",
        "single_generic_payload_works",
        "event_type_normalizes_to_type",
        "signal_normalizes_to_content",
        "occurred_at_normalizes_to_timestamp",
        "actor_reference_maps_to_user_id",
        "workspace_reference_preserved_safely",
        "idempotency_key_used_as_event_id",
        "unknown_fields_do_not_crash_and_are_sanitized",
        "unsafe_metadata_redacted",
        "continuity_packet_reflects_normalized_generic_events",
        "bearer_auth_required",
        "malformed_authorization_blocked",
        "wrong_key_blocked",
        "x_api_key_unsupported",
        "revoked_key_blocked",
        "raw_key_not_stored",
    ]:
        add(checks, name, by_name.get(name, False))

    add(checks, "normalization_code_exists", all(term in api_text for term in ["event_batch_from_payload", "normalize_event", "safe_external_metadata"]))
    add(checks, "auth_contract_unchanged", "Authorization must use the Bearer scheme" in server_text and "x-api-key" not in server_text.lower())
    add(checks, "docs_exist", DOC_PATH.exists())
    add(checks, "docs_include_legacy_shape", '"type": "project_updated"' in doc_text and '"content": "Synthetic update."' in doc_text)
    add(checks, "docs_include_generic_shape", '"event_type": "external.project.updated"' in doc_text and '"signal": "User updated a project' in doc_text)
    add(checks, "docs_warn_server_side_keys", "server-side only" in doc_text and "NEXT_PUBLIC_" in doc_text)
    add(checks, "docs_state_x_api_key_unsupported", "x-api-key" in doc_text and "not supported" in doc_text)
    add(checks, "public_report_has_no_secrets", not contains_secret(smoke_details))
    add(checks, "docs_have_no_real_secrets", not contains_secret(doc_text))
    add(checks, "no_false_claims", not has_false_claim(doc_text))

    failures = [check for check in checks if not check["passed"]]
    result = "PASS" if not failures else "NEEDS_WORK"
    public = {
        "version": "0.98",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "Generic External Event Contract Audit",
        "result": result,
        "checks_passed": len(checks) - len(failures),
        "checks_total": len(checks),
        "public_safe": True,
        "truth_label": "generic external event contract evidence only",
        "supported_shapes": [
            "legacy events[] type/content batch",
            "generic external events[] event_type/signal batch",
            "generic external single-event envelope",
        ],
        "auth_contract": "Authorization: Bearer <PRMR_API_KEY>",
        "x_api_key_supported": False,
        "scope_behavior": "client/vault/namespace inferred from key; explicit mismatches denied",
        "smoke_details": smoke_details,
        "raw_key_exposed": False,
        "boundary": BOUNDARY_V098,
        "remaining_gaps": [
            "longitudinal memory quality proof",
            "richer metadata-aware packet synthesis",
            "external validation with approved non-sensitive client tests",
        ],
    }
    private = {
        **public,
        "public_safe": False,
        "checks": checks,
        "smoke_checks": smoke_checks,
        "private_trace": private_trace,
    }
    write_json(PUBLIC_REPORT, public)
    write_json(PRIVATE_REPORT, private)
    SCORECARD.write_text(build_scorecard(public), encoding="utf-8")

    print("PRMR V0.98 External Event Contract Audit")
    print(f"Passed checks: {public['checks_passed']}/{public['checks_total']}")
    print(f"Result: {result}")
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
