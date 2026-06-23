import json
import re
from pathlib import Path
from datetime import datetime


VERSION = "0.52.0"

DOC_PATH = Path("docs/api_contract_v0520.md")
REPORT_DIR = Path("reports/v0520")
PUBLIC_PATH = REPORT_DIR / "public_api_contract_v0520.json"
PRIVATE_PATH = REPORT_DIR / "private_internal_api_contract_v0520.json"
SCORECARD_PATH = REPORT_DIR / "scorecard_v0520.md"

REQUIRED_ENDPOINTS = [
    "POST /v1/events/ingest",
    "POST /v1/continuity/packet",
    "POST /v1/memory/reconstruct",
    "POST /v1/explain",
    "POST /v1/actions/least-harm",
    "GET /v1/reports/{report_id}",
    "GET /v1/usage",
    "POST /v1/keys/rotate",
    "POST /v1/keys/revoke",
]

REQUIRED_SCHEMA_TERMS = [
    "Common Request Envelope",
    "Event Schema",
    "Continuity Packet Schema",
    "Explanation Packet Schema",
    "Least-Harm Action Schema",
    "client_id",
    "vault_id",
    "namespace",
    "event_id",
    "entity_id",
    "current_state",
    "previous_state",
    "meaningful_changes",
    "evidence_summary",
    "recommended_next_step",
]

REQUIRED_AUTH_TERMS = [
    "API key authentication",
    "Authorization: Bearer <api_key>",
    "X-PRMR-Client-ID",
    "X-PRMR-Vault-ID",
    "X-PRMR-Namespace",
    "Revoked or rotated-out keys must be rejected",
    "Cross-client and cross-vault access must be rejected",
]

REQUIRED_BOUNDARY_TERMS = [
    "Public/private report separation is required",
    "Public reports may include",
    "Private reports may include",
    "Public reports must not include",
    "raw API keys",
]

REQUIRED_SAFETY_TERMS = [
    "No real sensitive data unless explicitly approved",
    "No final punitive decisions",
    "No production certification",
    "No bank approval",
    "No compliance approval",
    "No external security certification",
    "Do not use alpha access as production fraud infrastructure",
]

REQUIRED_ERROR_CODES = [
    "missing_auth",
    "invalid_key",
    "revoked_key",
    "vault_denied",
    "namespace_denied",
    "payload_invalid",
    "payload_too_large",
    "report_not_found",
    "rate_limited",
    "alpha_boundary_violation",
    "unsupported_operation",
]

PUBLIC_FORBIDDEN_TERMS = [
    "truth_private",
    "private_truth",
    "private_packets",
    "private_classifications",
    "private_explanations",
    "private_harm_packets",
    "private_prmr_labels",
    "private_rule_labels",
    "private_rule_actions",
    "private_reconstruction_results",
    "private_checks",
    "private_internal",
    "protected_note",
    "compressed_package",
    "reconstructed_rows",
    "engine_result_snapshot",
    "internal_rule_data",
    "raw_api_key",
    "api_key",
    "do_not_share",
    "do_not_leak",
    "local_test",
]

UNSAFE_PUBLIC_LANGUAGE = [
    "criminal",
    "fraudster",
    "guilty",
    "definitely fraud",
    "blacklist",
    "close account immediately",
]

FALSE_CERTIFICATION_CLAIMS = [
    "production certified",
    "bank-certified",
    "bank certified",
    "compliance approved",
    "legally approved",
    "external security certified",
    "certified fraud engine",
]


def read_text(path):
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def scan_terms(text, terms):
    lowered = text.lower()
    return [term for term in terms if term.lower() in lowered]


def missing_terms(text, terms):
    lowered = text.lower()
    return [term for term in terms if term.lower() not in lowered]


def endpoint_id(endpoint):
    return endpoint.lower().replace(" ", "_").replace("/", "_").replace("{", "").replace("}", "").strip("_")


def build_public_report(doc_text):
    documented_endpoints = [
        {
            "endpoint": endpoint,
            "documented": endpoint.lower() in doc_text.lower(),
            "purpose": endpoint_purpose(endpoint),
        }
        for endpoint in REQUIRED_ENDPOINTS
    ]

    return {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": VERSION,
        "report_type": "alpha_api_contract",
        "timestamp": datetime.now().isoformat(),
        "public_safe": True,
        "result": "NEEDS_WORK",
        "passed_checks": 0,
        "total_checks": 0,
        "all_checks_passed": False,
        "contract_status": "specified_not_hosted",
        "truth_state": {
            "v050_whole_core_truth_gauntlet": "PASS",
            "v051_product_clarity_pack": "complete",
            "v0511_architecture_coverage": "PASS",
        },
        "endpoints": documented_endpoints,
        "schema_groups": [
            "request envelope",
            "event schema",
            "continuity packet schema",
            "explanation packet schema",
            "least-harm action schema",
            "error response schema",
        ],
        "auth_summary": "Access-key auth with client, vault, and namespace scoping is required for every endpoint.",
        "report_boundary_summary": "Public and restricted reports are separated; public outputs must not expose restricted fields, raw keys, sensitive evidence, or detection details.",
        "alpha_safety_summary": (
            "Controlled alpha only: synthetic or approved datasets, human review preserved, no production use, "
            "no bank approval claim, no compliance approval claim, and no final punitive use."
        ),
        "current_limitations": [
            "Contract only; full hosted API is not implemented here.",
            "No real sensitive data unless approved.",
            "No production, bank, compliance, or external security certification claim.",
            "Entity resolution, dormant chain memory, recurrence detection, and federated PRMR remain future or partial layers.",
        ],
        "honest_boundary": (
            "This V0.52.0 artifact defines a controlled alpha API contract. "
            "It does not claim hosted production readiness or external certification."
        ),
    }


def endpoint_purpose(endpoint):
    purposes = {
        "POST /v1/events/ingest": "Accept scoped alpha events.",
        "POST /v1/continuity/packet": "Generate scoped continuity packets.",
        "POST /v1/memory/reconstruct": "Reconstruct scoped continuity state for verification.",
        "POST /v1/explain": "Create internal or customer-safe explanation packets.",
        "POST /v1/actions/least-harm": "Recommend proportionate next actions with human review.",
        "GET /v1/reports/{report_id}": "Return accessible public-safe reports.",
        "GET /v1/usage": "Return scoped alpha usage.",
        "POST /v1/keys/rotate": "Rotate access keys.",
        "POST /v1/keys/revoke": "Revoke access keys.",
    }
    return purposes[endpoint]


def validate_contract(doc_text, public_report):
    checks = []

    missing_endpoints = [
        endpoint
        for endpoint in REQUIRED_ENDPOINTS
        if endpoint.lower() not in doc_text.lower()
    ]
    checks.append({
        "name": "all_required_endpoints_documented",
        "passed": len(missing_endpoints) == 0,
        "details": {"missing_endpoints": missing_endpoints},
    })

    missing_schema_terms = missing_terms(doc_text, REQUIRED_SCHEMA_TERMS)
    checks.append({
        "name": "all_required_schemas_present",
        "passed": len(missing_schema_terms) == 0,
        "details": {"missing_schema_terms": missing_schema_terms},
    })

    missing_auth_terms = missing_terms(doc_text, REQUIRED_AUTH_TERMS)
    checks.append({
        "name": "auth_and_key_rules_present",
        "passed": len(missing_auth_terms) == 0,
        "details": {"missing_auth_terms": missing_auth_terms},
    })

    missing_boundary_terms = missing_terms(doc_text, REQUIRED_BOUNDARY_TERMS)
    checks.append({
        "name": "public_private_report_boundary_present",
        "passed": len(missing_boundary_terms) == 0,
        "details": {"missing_boundary_terms": missing_boundary_terms},
    })

    missing_safety_terms = missing_terms(doc_text, REQUIRED_SAFETY_TERMS)
    checks.append({
        "name": "alpha_safety_limits_present",
        "passed": len(missing_safety_terms) == 0,
        "details": {"missing_safety_terms": missing_safety_terms},
    })

    missing_error_codes = missing_terms(doc_text, REQUIRED_ERROR_CODES)
    checks.append({
        "name": "required_error_codes_present",
        "passed": len(missing_error_codes) == 0,
        "details": {"missing_error_codes": missing_error_codes},
    })

    public_text = json.dumps(public_report, sort_keys=True)
    public_forbidden = scan_terms(public_text, PUBLIC_FORBIDDEN_TERMS)
    public_unsafe = scan_terms(public_text, UNSAFE_PUBLIC_LANGUAGE)

    checks.append({
        "name": "public_report_has_no_restricted_packet_terms",
        "passed": len(public_forbidden) == 0,
        "details": {"forbidden_terms_found": public_forbidden},
    })

    checks.append({
        "name": "public_report_avoids_punitive_or_certain_guilt_language",
        "passed": len(public_unsafe) == 0,
        "details": {"unsafe_language_found": public_unsafe},
    })

    false_claim_hits = [
        claim
        for claim in FALSE_CERTIFICATION_CLAIMS
        if re.search(r"(?<!no )(?<!not )" + re.escape(claim), doc_text.lower())
    ]
    required_disclaimers_present = all(
        phrase.lower() in doc_text.lower()
        for phrase in [
            "No production certification",
            "No bank approval",
            "No compliance approval",
            "No external security certification",
        ]
    )

    checks.append({
        "name": "contract_does_not_claim_production_certification",
        "passed": len(false_claim_hits) == 0 and required_disclaimers_present,
        "details": {
            "false_claim_hits": false_claim_hits,
            "required_disclaimers_present": required_disclaimers_present,
        },
    })

    return checks


def build_scorecard(public_report):
    lines = [
        "# PRMR V0.52.0 Alpha API Contract Audit",
        "",
        "Company: Afternum Industries  ",
        "Product: PRMR Memory Core  ",
        "Version: V0.52.0  ",
        "",
        "## Result",
        "",
        f"**{public_report['result']}**",
        "",
        f"Passed checks: **{public_report['passed_checks']}/{public_report['total_checks']}**",
        "",
        "## Endpoints",
        "",
    ]

    for item in public_report["endpoints"]:
        status = "documented" if item["documented"] else "missing"
        lines.append(f"- {item['endpoint']}: {status}")

    lines.extend([
        "",
        "## Boundary",
        "",
        public_report["honest_boundary"],
        "",
        "This is not a production, bank, compliance, or external security certification claim.",
        "",
    ])

    return "\n".join(lines)


def main():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    doc_text = read_text(DOC_PATH)
    public_report = build_public_report(doc_text)

    private_report = {
        **public_report,
        "public_safe": False,
        "doc_path": str(DOC_PATH),
        "required_endpoints": REQUIRED_ENDPOINTS,
        "required_schema_terms": REQUIRED_SCHEMA_TERMS,
        "required_auth_terms": REQUIRED_AUTH_TERMS,
        "required_boundary_terms": REQUIRED_BOUNDARY_TERMS,
        "required_safety_terms": REQUIRED_SAFETY_TERMS,
        "required_error_codes": REQUIRED_ERROR_CODES,
        "restricted_note": "Restricted audit report includes exact term requirements and check details.",
    }

    checks = validate_contract(doc_text, public_report)
    passed_count = sum(1 for check in checks if check["passed"])
    total_checks = len(checks)
    all_passed = passed_count == total_checks

    public_report["checks"] = [
        {
            "name": check["name"],
            "passed": check["passed"],
        }
        for check in checks
    ]
    public_report["passed_checks"] = passed_count
    public_report["total_checks"] = total_checks
    public_report["all_checks_passed"] = all_passed
    public_report["result"] = "PASS" if all_passed else "NEEDS_WORK"

    private_report["checks"] = checks
    private_report["passed_checks"] = passed_count
    private_report["total_checks"] = total_checks
    private_report["all_checks_passed"] = all_passed
    private_report["result"] = public_report["result"]

    PUBLIC_PATH.write_text(json.dumps(public_report, indent=4), encoding="utf-8")
    PRIVATE_PATH.write_text(json.dumps(private_report, indent=4), encoding="utf-8")
    SCORECARD_PATH.write_text(build_scorecard(public_report), encoding="utf-8")

    print("PRMR V0.52.0 ALPHA API CONTRACT AUDIT")
    print("-------------------------------------")
    print("Result:", public_report["result"])
    print("Passed checks:", f"{passed_count}/{total_checks}")
    print()
    print("Endpoint coverage:")
    for item in public_report["endpoints"]:
        status = "documented" if item["documented"] else "missing"
        print("-", item["endpoint"] + ":", status)
    print()
    print("Check list:")
    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        print("-", check["name"] + ":", status)
    print()
    print("Created:")
    print(PUBLIC_PATH)
    print(PRIVATE_PATH)
    print(SCORECARD_PATH)


if __name__ == "__main__":
    main()
