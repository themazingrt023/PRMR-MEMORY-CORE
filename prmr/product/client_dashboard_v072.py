"""V0.72 local client dashboard MVP aggregation.

This module turns the existing V0.69-V0.71 local controlled-alpha evidence into
public-safe dashboard data. It does not create live access, issue keys, connect
billing, or assert production readiness.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "reports" / "v072"

SOURCE_REPORTS = {
    "v069_public": ROOT / "reports" / "v069" / "public_hosted_backend_foundation_v069.json",
    "v069_restricted": ROOT / "reports" / "v069" / "private_internal_hosted_backend_foundation_v069.json",
    "v070_public": ROOT / "reports" / "v070" / "public_api_key_lifecycle_v070.json",
    "v070_restricted": ROOT / "reports" / "v070" / "private_internal_api_key_lifecycle_v070.json",
    "v071_public": ROOT / "reports" / "v071" / "public_controlled_alpha_api_v071.json",
    "v071_restricted": ROOT / "reports" / "v071" / "private_internal_controlled_alpha_api_v071.json",
}

BOUNDARY_V072 = (
    "V0.72 is a local/deployable client dashboard MVP only. It uses synthetic/dev-only "
    "controlled-alpha evidence from V0.69 through V0.71. It is not hosted customer "
    "authentication, not a production portal, not billing, not self-serve access, not "
    "live API access, not external validation, not bank approval, not compliance "
    "approval, not legal approval, not external security certification, and not "
    "real-world validation."
)

DASHBOARD_NOTICE = (
    "This dashboard is a local controlled-alpha dashboard MVP. It uses synthetic/dev-only "
    "data and does not provide hosted customer authentication, billing, live API access, "
    "or production guarantees."
)

REQUIRED_BLOCKED_REASONS = {
    "missing_key",
    "invalid_key",
    "key_client_mismatch",
    "vault_denied",
    "namespace_denied",
    "rotated_key",
    "revoked_key",
    "usage_limit_exceeded",
}

PUBLIC_RESTRICTED_TERMS = [
    "raw_api_key",
    "full_api_key",
    "private_internal",
    "private packet",
    "internal packet",
    "key_hash",
    "validation_outcomes",
    "debug_trace",
    "private_trace",
]

OVERCLAIMS = [
    "production-ready",
    "production ready",
    "hosted dashboard is live",
    "hosted api is live",
    "live api access granted",
    "billing enabled",
    "self-serve access enabled",
    "bank-approved",
    "bank approved",
    "compliance-certified",
    "compliance certified",
    "legal-approved",
    "legal approved",
    "security-certified",
    "security certified",
    "external validation complete",
    "real-world validated",
    "real client data",
]

PUNITIVE_TERMS = [
    "fraudster",
    "criminal",
    "guilty",
    "definitely fraud",
    "blacklist",
    "close account immediately",
]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def missing_source_reports() -> list[str]:
    return [name for name, path in SOURCE_REPORTS.items() if not path.exists()]


def scan_terms(payload: Any, terms: list[str]) -> list[str]:
    text = json.dumps(payload, sort_keys=True).lower()
    return [term for term in terms if term.lower() in text]


def contains_full_dev_key(payload: Any) -> bool:
    text = json.dumps(payload, sort_keys=True)
    return bool(re.search(r"prmr_alpha_dev_[a-f0-9]{16,}", text))


def load_sources() -> dict[str, dict[str, Any]]:
    missing = missing_source_reports()
    if missing:
        raise FileNotFoundError(f"Missing V0.72 dashboard source reports: {', '.join(missing)}")
    return {name: read_json(path) for name, path in SOURCE_REPORTS.items()}


def build_api_key_panel(v070_restricted: dict[str, Any], v070_public: dict[str, Any]) -> dict[str, Any]:
    key_records = v070_restricted.get("lifecycle_key_records", {})
    records = []
    for key_id, record in sorted(key_records.items()):
        records.append(
            {
                "key_id": key_id,
                "client_id": record.get("client_id"),
                "safe_key_preview": record.get("safe_key_preview"),
                "status": record.get("status"),
                "vault_id": record.get("vault_id"),
                "namespace": record.get("namespace"),
                "created_at": record.get("created_at"),
                "last_used_at": record.get("last_used_at"),
                "usage_limit_id": record.get("usage_limit_id"),
                "operator_note": "Display uses preview only. Full key values are not present in dashboard data.",
            }
        )
    return {
        "title": "API key lifecycle",
        "manual_operator_approval_required": True,
        "automatic_key_issuing": False,
        "safe_key_status_counts": v070_public.get("safe_key_lifecycle_summary", {}).get("key_status_counts", {}),
        "records": records,
    }


def build_usage_overview(v069_public: dict[str, Any], v070_public: dict[str, Any], v071_public: dict[str, Any]) -> dict[str, Any]:
    v071_usage = v071_public.get("usage_summary", {})
    v070_usage = v070_public.get("usage_summary", {}).get("usage_summary", {})
    return {
        "title": "Usage overview",
        "current_source_version": "0.71",
        "allowed_request_count": v071_usage.get("allowed_request_count", 0),
        "blocked_request_count": v071_usage.get("blocked_request_count", 0),
        "total_request_count": v071_usage.get("allowed_request_count", 0) + v071_usage.get("blocked_request_count", 0),
        "by_client": v071_usage.get("by_client", {}),
        "by_vault": v071_usage.get("by_vault", {}),
        "by_namespace": v071_usage.get("by_namespace", {}),
        "prior_milestone_comparison": {
            "v069_total": v069_public.get("usage_summary", {}).get("allowed_request_count", 0)
            + v069_public.get("usage_summary", {}).get("blocked_request_count", 0),
            "v070_total": v070_usage.get("allowed_request_count", 0) + v070_usage.get("blocked_request_count", 0),
            "v071_total": v071_usage.get("allowed_request_count", 0) + v071_usage.get("blocked_request_count", 0),
        },
    }


def build_request_log_summary(v071_restricted: dict[str, Any]) -> dict[str, Any]:
    rows = []
    endpoint_counts: Counter[str] = Counter()
    blocked_reasons: Counter[str] = Counter()
    for item in v071_restricted.get("api_request_log", []):
        endpoint = item.get("endpoint", "unknown")
        status = item.get("status", "unknown")
        reason = item.get("reason", "unknown")
        endpoint_counts[endpoint] += 1
        if status == "blocked":
            blocked_reasons[reason] += 1
        rows.append(
            {
                "timestamp": item.get("timestamp"),
                "client_id": item.get("client_id"),
                "endpoint": endpoint,
                "vault_id": item.get("vault_id"),
                "namespace": item.get("namespace"),
                "status": status,
                "reason": reason,
                "public_safe_message": item.get("public_safe_message"),
            }
        )
    return {
        "title": "Request log",
        "rows": rows,
        "endpoint_counts": dict(sorted(endpoint_counts.items())),
        "blocked_reasons": dict(sorted(blocked_reasons.items())),
        "blocked_reason_policy": "Blocked requests are logged as denied attempts, but failed authentication does not create successful work artifacts.",
    }


def build_vault_namespace_panel(v071_restricted: dict[str, Any]) -> dict[str, Any]:
    packets = list(v071_restricted.get("synthetic_packets", {}).values())
    reports = list(v071_restricted.get("synthetic_public_reports", {}).values())
    event_counts: Counter[tuple[str, str]] = Counter()
    packet_counts: Counter[tuple[str, str]] = Counter()
    report_counts: Counter[tuple[str, str]] = Counter()
    for packet in packets:
        key = (packet.get("vault_id", ""), packet.get("namespace", ""))
        event_counts[key] += int(packet.get("event_count", 0))
        packet_counts[key] += 1
    for report in reports:
        report_counts[(report.get("vault_id", ""), report.get("namespace", ""))] += 1

    namespaces = []
    for namespace_id, namespace in sorted(v071_restricted.get("synthetic_namespaces", {}).items()):
        key = (namespace.get("vault_id", ""), namespace.get("namespace", ""))
        namespaces.append(
            {
                "namespace_id": namespace_id,
                "client_id": namespace.get("client_id"),
                "vault_id": namespace.get("vault_id"),
                "namespace": namespace.get("namespace"),
                "status": namespace.get("status"),
                "event_count": event_counts[key],
                "packet_count": packet_counts[key],
                "public_report_count": report_counts[key],
            }
        )
    return {
        "title": "Vaults and namespaces",
        "vaults": list(v071_restricted.get("synthetic_vaults", {}).values()),
        "namespaces": namespaces,
        "cross_client_boundary": "Dashboard data is scoped to synthetic owner records; cross-client access remains denied by V0.71 evidence.",
    }


def build_reports_panel(v071_restricted: dict[str, Any]) -> dict[str, Any]:
    reports = []
    for report_id, report in sorted(v071_restricted.get("synthetic_public_reports", {}).items()):
        reports.append(
            {
                "report_id": report_id,
                "client_id": report.get("client_id"),
                "vault_id": report.get("vault_id"),
                "namespace": report.get("namespace"),
                "packet_id": report.get("packet_id"),
                "public_safe": report.get("public_safe") is True,
                "summary": report.get("summary"),
                "event_count": report.get("event_count"),
            }
        )
    return {
        "title": "Public-safe report previews",
        "reports": reports,
        "public_private_boundary": "Dashboard previews use public-safe report summaries only.",
    }


def build_memory_health(v071_restricted: dict[str, Any]) -> dict[str, Any]:
    packets = list(v071_restricted.get("synthetic_packets", {}).values())
    request_log = v071_restricted.get("api_request_log", [])
    endpoints_seen = {row.get("endpoint") for row in request_log if row.get("status") == "ok"}
    blocked_count = sum(1 for row in request_log if row.get("status") == "blocked")
    return {
        "title": "Memory health",
        "status": "limited_local_mvp",
        "events_received": sum(int(packet.get("event_count", 0)) for packet in packets),
        "packets_generated": len(packets),
        "reconstruction_available": "POST /v1/memory/reconstruct" in endpoints_seen,
        "explanation_available": "POST /v1/explain" in endpoints_seen,
        "least_harm_available": "POST /v1/actions/least-harm" in endpoints_seen,
        "public_report_available": bool(v071_restricted.get("synthetic_public_reports")),
        "blocked_request_count": blocked_count,
        "health_note": "Healthy enough for local synthetic dashboard review; not evidence of production readiness.",
    }


def build_dashboard_data() -> dict[str, Any]:
    sources = load_sources()
    v071_clients = sources["v071_restricted"].get("synthetic_clients", {})
    client = next(iter(v071_clients.values()), {})

    dashboard = {
        "version": "0.72",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "Client Dashboard MVP",
        "result_basis": "local synthetic/dev-only evidence",
        "boundary": BOUNDARY_V072,
        "dashboard_notice": DASHBOARD_NOTICE,
        "source_versions": ["0.69", "0.70", "0.71"],
        "client_overview": {
            "client_id": client.get("client_id", "client_v071_synthetic_alpha"),
            "organisation": client.get("organisation", "Synthetic V0.71 Alpha Client"),
            "status": client.get("status", "active"),
            "created_at": client.get("created_at"),
            "synthetic_only": True,
            "active_vault_count": len(sources["v071_restricted"].get("synthetic_vaults", {})),
            "active_namespace_count": len(sources["v071_restricted"].get("synthetic_namespaces", {})),
            "public_mode_access": "blocked_or_placeholder",
            "local_mode_access": "enabled_for_mvp_review",
        },
        "api_key_panel": build_api_key_panel(sources["v070_restricted"], sources["v070_public"]),
        "vault_namespace_panel": build_vault_namespace_panel(sources["v071_restricted"]),
        "usage_overview": build_usage_overview(sources["v069_public"], sources["v070_public"], sources["v071_public"]),
        "request_log_summary": build_request_log_summary(sources["v071_restricted"]),
        "reports_panel": build_reports_panel(sources["v071_restricted"]),
        "memory_health_panel": build_memory_health(sources["v071_restricted"]),
    }
    return dashboard


def build_public_report(dashboard_data: dict[str, Any], checks: list[dict[str, Any]]) -> dict[str, Any]:
    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    return {
        "version": "0.72",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "Client Dashboard MVP",
        "result": "PASS" if passed == total else "NEEDS_WORK",
        "checks_passed": passed,
        "checks_total": total,
        "public_safe": True,
        "boundary": BOUNDARY_V072,
        "dashboard_notice": DASHBOARD_NOTICE,
        "panels": [
            "client_overview",
            "api_key_panel",
            "vault_namespace_panel",
            "usage_overview",
            "request_log_summary",
            "reports_panel",
            "memory_health_panel",
        ],
        "safe_summary": {
            "source_versions": dashboard_data["source_versions"],
            "client_status": dashboard_data["client_overview"]["status"],
            "safe_key_status_counts": dashboard_data["api_key_panel"]["safe_key_status_counts"],
            "usage": {
                "allowed_request_count": dashboard_data["usage_overview"]["allowed_request_count"],
                "blocked_request_count": dashboard_data["usage_overview"]["blocked_request_count"],
            },
            "blocked_reasons": sorted(dashboard_data["request_log_summary"]["blocked_reasons"].keys()),
            "memory_health_status": dashboard_data["memory_health_panel"]["status"],
        },
    }


def build_private_report(dashboard_data: dict[str, Any], checks: list[dict[str, Any]]) -> dict[str, Any]:
    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    return {
        "version": "0.72",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "Client Dashboard MVP Restricted Evidence",
        "result": "PASS" if passed == total else "NEEDS_WORK",
        "checks_passed": passed,
        "checks_total": total,
        "boundary": BOUNDARY_V072,
        "checks": checks,
        "source_report_paths": {name: str(path.relative_to(ROOT)) for name, path in SOURCE_REPORTS.items()},
        "dashboard_data": dashboard_data,
        "restricted_note": "This report can include source paths and detailed local dashboard checks. Public report stays summary-only.",
    }


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, details: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "details": details})


def validate_dashboard_data(dashboard_data: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    required_panels = [
        "client_overview",
        "api_key_panel",
        "vault_namespace_panel",
        "usage_overview",
        "request_log_summary",
        "reports_panel",
        "memory_health_panel",
    ]
    for name in required_panels:
        add_check(checks, f"{name}_present", name in dashboard_data, name)

    key_text = json.dumps(dashboard_data.get("api_key_panel", {}), sort_keys=True)
    add_check(checks, "api_key_panel_uses_safe_preview", "safe_key_preview" in key_text and "key_hash" not in key_text, None)
    add_check(checks, "dashboard_data_contains_no_full_dev_key", not contains_full_dev_key(dashboard_data), None)

    blocked_reasons = set(dashboard_data.get("request_log_summary", {}).get("blocked_reasons", {}).keys())
    add_check(
        checks,
        "required_blocked_reasons_present",
        REQUIRED_BLOCKED_REASONS.issubset(blocked_reasons),
        sorted(blocked_reasons),
    )
    add_check(checks, "boundary_notice_present", DASHBOARD_NOTICE in dashboard_data.get("dashboard_notice", ""), None)
    add_check(
        checks,
        "memory_health_present",
        dashboard_data.get("memory_health_panel", {}).get("packets_generated", 0) >= 1,
        dashboard_data.get("memory_health_panel"),
    )
    add_check(
        checks,
        "public_reports_are_preview_only",
        all(report.get("public_safe") is True for report in dashboard_data.get("reports_panel", {}).get("reports", [])),
        dashboard_data.get("reports_panel", {}).get("reports", []),
    )
    add_check(
        checks,
        "public_restricted_terms_absent_from_dashboard_data",
        not scan_terms(dashboard_data, PUBLIC_RESTRICTED_TERMS),
        scan_terms(dashboard_data, PUBLIC_RESTRICTED_TERMS),
    )
    add_check(checks, "overclaims_absent_from_dashboard_data", not scan_terms(dashboard_data, OVERCLAIMS), scan_terms(dashboard_data, OVERCLAIMS))
    add_check(checks, "punitive_terms_absent_from_dashboard_data", not scan_terms(dashboard_data, PUNITIVE_TERMS), scan_terms(dashboard_data, PUNITIVE_TERMS))
    return checks


def build_scorecard(public_report: dict[str, Any], checks: list[dict[str, Any]]) -> str:
    lines = [
        "# V0.72 Client Dashboard MVP Scorecard",
        "",
        f"Result: {public_report['result']}",
        f"Passed checks: {public_report['checks_passed']}/{public_report['checks_total']}",
        "",
        f"Boundary: {BOUNDARY_V072}",
        "",
        "## Panels",
        "",
    ]
    lines.extend([f"- {panel}" for panel in public_report["panels"]])
    lines.extend(["", "## Checks", ""])
    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        lines.append(f"- {status}: {check['name']}")
    lines.extend(["", "## Command Results", "", "- RUN: python examples/run_client_dashboard_mvp_v072.py", "", BOUNDARY_V072, ""])
    return "\n".join(lines)


def generate_dashboard_reports() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    dashboard_data = build_dashboard_data()
    checks = validate_dashboard_data(dashboard_data)
    public_report = build_public_report(dashboard_data, checks)
    private_report = build_private_report(dashboard_data, checks)
    return dashboard_data, public_report, private_report, checks
