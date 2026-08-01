"""Audit V0.78.2 local secret cleanup and key revocation posture."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports" / "v0782"
PUBLIC_REPORT = REPORT_DIR / "public_secret_cleanup_v0782.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_secret_cleanup_v0782.json"
SCORECARD = REPORT_DIR / "scorecard_v0782.md"
REVOCATION_RECORD = ROOT / "docs" / "key_revocation_record_v0782.md"

BOUNDARY_V0782 = (
    "V0.78.2 is local secret hygiene and revocation evidence only. It is not "
    "external security certification, production readiness, compliance approval, "
    "legal approval, bank approval, external validation, or real-world validation."
)

IGNORED_ROOTS = [
    ".env",
    "reports/",
    "logs/",
    "config/",
    "data/",
    "inputs/",
    "design_sources/",
    "node_modules/",
    ".next/",
]

ALLOWED_TRACKED_PREFIXES = [
    "frontend/data/",
]

ALLOWED_TRACKED_REPORTS = {
    "reports/core_release_candidate/km1_release_lock.json",
    "reports/core_release_candidate/km1_release_file_manifest.json",
}

ALLOWED_TRACKED_CONFIGS = {
    "config/prmr.postgres.example.toml",
    "config/prmr.sqlite.example.toml",
    "config/prmr.worker.example.toml",
}

SYNTHETIC_SECRET_FIXTURES = {
    "examples/run_core_release_candidate.py": (
        "prmr_live_example_secret",
    ),
    "examples/run_core_source_ledger_provenance.py": (
        "malicious_bearer_1234567890",
        "ghp_" + "ABCDEFGHIJKLMNOPQRSTUVWXYZ123456",
        "-----BEGIN " + "PRIVATE KEY-----",
    ),
    "prmr/core/candidate_fixtures.py": (
        "prmr_live_candidate_fixture_secret_1234567890",
    ),
    "prmr/core/source_fixtures.py": (
        "fixture_token_1234567890",
    ),
}

DATABASE_SUFFIXES = [
    ".sqlite",
    ".sqlite3",
    ".db",
    ".db3",
]

SECRET_PATTERNS = [
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}\b")),
    ("github_pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("github_ghp", re.compile(r"\bghp_[A-Za-z0-9]{20,}\b")),
    ("github_gho", re.compile(r"\bgho_[A-Za-z0-9]{20,}\b")),
    ("github_ghu", re.compile(r"\bghu_[A-Za-z0-9]{20,}\b")),
    ("github_ghs", re.compile(r"\bghs_[A-Za-z0-9]{20,}\b")),
    ("github_ghr", re.compile(r"\bghr_[A-Za-z0-9]{20,}\b")),
    ("private_key_block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("real_bearer_token", re.compile(r"Authorization:\s*Bearer\s+(?!<)(?!TOKEN)(?!CONTROLLED)(?!YOUR)(?!not-a-bearer-token)[A-Za-z0-9_\-\.]{20,}", re.IGNORECASE)),
    ("real_looking_api_key_json", re.compile(r'"api_key"\s*:\s*"(?!<)(?!CONTROLLED)(?!YOUR)(?!not-a-real)(?!prmr_alpha_dev_wrong)[^"\n]{12,}"', re.IGNORECASE)),
]

PLACEHOLDER_OK = [
    "<api_key>",
    "CONTROLLED_TEST_KEY",
    "YOUR-HOSTED",
    "YOUR_HOSTED",
    "not-a-bearer-token",
    "prmr_alpha_dev_wrong",
    "wrong_",
    "LOCAL_TEST_DO_NOT_SHARE",
    "access key wording",
    "PRMR_TEST_API_KEY=",
    "PRMR_HOSTED_API_KEY=",
]


def run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def tracked_files() -> list[str]:
    completed = run_git(["ls-files"])
    if completed.returncode != 0:
        return []
    return [line.strip().replace("\\", "/") for line in completed.stdout.splitlines() if line.strip()]


def tracked_matching(files: list[str], prefix: str) -> list[str]:
    if prefix == ".env":
        return [path for path in files if path == ".env" or path.startswith(".env.") and path != ".env.example"]
    return [path for path in files if path == prefix.rstrip("/") or path.startswith(prefix)]


def read_tracked_text(path: str) -> str | None:
    full = ROOT / path
    try:
        raw = full.read_bytes()
    except OSError:
        return None
    if b"\x00" in raw[:4096]:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return raw.decode("utf-8", errors="replace")
        except Exception:
            return None


def line_is_placeholder(line: str) -> bool:
    return any(token in line for token in PLACEHOLDER_OK)


def scan_tracked_secrets(files: list[str]) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for path in files:
        text = read_tracked_text(path)
        if text is None:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            if line_is_placeholder(line):
                continue
            fixture_markers = SYNTHETIC_SECRET_FIXTURES.get(path, ())
            if any(marker in line for marker in fixture_markers):
                continue
            for name, pattern in SECRET_PATTERNS:
                if pattern.search(line):
                    hits.append({"file": path, "line": line_number, "pattern": name})
    return hits


def scan_public_reports() -> dict[str, Any]:
    public_reports = [
        path
        for path in (ROOT / "reports").glob("**/public*.json")
        if path.is_file()
    ] if (ROOT / "reports").exists() else []
    hits: list[dict[str, Any]] = []
    for report in public_reports:
        try:
            text = report.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            if line_is_placeholder(line):
                continue
            for name, pattern in SECRET_PATTERNS:
                if pattern.search(line):
                    hits.append({"file": str(report.relative_to(ROOT)).replace("\\", "/"), "line": line_number, "pattern": name})
    return {"public_report_count": len(public_reports), "secret_hits": hits}


def km1_lock_artifact_safe() -> tuple[bool, dict[str, Any]]:
    relative = "reports/core_release_candidate/km1_release_lock.json"
    path = ROOT / relative
    if not path.is_file():
        return False, {"path": relative, "reason": "missing"}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, {"path": relative, "reason": "invalid_json"}
    text = json.dumps(payload, sort_keys=True)
    hits = [name for name, pattern in SECRET_PATTERNS if pattern.search(text)]
    safe_shape = (
        payload.get("package_version") == "1.0.0rc1"
        and payload.get("database_url_recorded") is False
        and payload.get("private_evidence_included") is False
        and bool(payload.get("artifact_hashes", {}).get("wheel_sha256"))
        and bool(payload.get("manifest_hashes", {}).get("release_manifest_hash"))
    )
    return safe_shape and not hits, {
        "path": relative,
        "secret_pattern_hits": hits,
        "safe_shape": safe_shape,
    }


def km1_file_manifest_safe() -> tuple[bool, dict[str, Any]]:
    relative = "reports/core_release_candidate/km1_release_file_manifest.json"
    path = ROOT / relative
    if not path.is_file():
        return False, {"path": relative, "reason": "missing"}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, {"path": relative, "reason": "invalid_json"}
    text = json.dumps(payload, sort_keys=True)
    hits = [name for name, pattern in SECRET_PATTERNS if pattern.search(text)]
    entries = payload.get("entries", [])
    safe_shape = (
        payload.get("manifest_revision") == "km1_release_file_manifest_v1"
        and payload.get("secret_values_recorded") is False
        and isinstance(entries, list)
        and payload.get("changed_or_untracked_path_count") == len(entries)
    )
    return safe_shape and not hits, {
        "path": relative,
        "secret_pattern_hits": hits,
        "safe_shape": safe_shape,
        "classified_path_count": len(entries),
    }


def env_example_placeholder_only() -> tuple[bool, list[str]]:
    path = ROOT / ".env.example"
    if not path.exists():
        return False, [".env.example missing"]
    bad: list[str] = []
    sensitive_names = [
        "PRMR_TEST_API_KEY",
        "PRMR_HOSTED_API_KEY",
        "SERVER_ONLY_API_SECRET",
        "BILLING_PROVIDER_SECRET",
        "HOSTED_DATABASE_URL",
    ]
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        if key in sensitive_names and value.strip():
            bad.append(key)
    return not bad, bad


def revocation_record_ok() -> tuple[bool, list[str]]:
    required = [
        "GitHub personal access tokens were checked manually",
        "old local/dev keys are considered revoked",
        "external provider keys must be revoked manually",
        "fresh",
        "No old local key should be reused",
        "No raw key value should be committed",
        "Only `.env.example` placeholders may be tracked",
    ]
    if not REVOCATION_RECORD.exists():
        return False, required
    text = REVOCATION_RECORD.read_text(encoding="utf-8", errors="replace")
    text_lower = text.lower()
    missing = [item for item in required if item.lower() not in text_lower]
    return not missing, missing


def real_client_data_hits(files: list[str]) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    suspicious = [
        re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        re.compile(r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14})\b"),
        re.compile(r"\b[A-Za-z0-9._%+-]+@(?!example\.test\b)(?!example\.com\b)(?!afternum\.test\b)(?![A-Za-z0-9.-]+\.example\b)(?![A-Za-z0-9.-]+\.invalid\b)[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    ]
    allowed_prefixes = ("frontend/package-lock.json",)
    for path in files:
        if path.startswith(allowed_prefixes):
            continue
        text = read_tracked_text(path)
        if text is None:
            continue
        for line in text.splitlines():
            if "prmr-memory-core.vercel.app" in line or "localhost" in line or "render.com" in line:
                continue
            if "@app." in line:
                continue
            if any(pattern.search(line) for pattern in suspicious):
                hits.append({"file": path, "reason": "real_data_pattern"})
                break
    return hits


def build_reports(checks: list[dict[str, Any]], tracked: list[str], secret_hits: list[dict[str, Any]], public_report_scan: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], str]:
    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    public_report = {
        "version": "0.78.2",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "Secret Exposure Cleanup + Key Revocation Audit",
        "result": "PASS" if passed == total else "NEEDS_WORK",
        "checks_passed": passed,
        "checks_total": total,
        "public_safe": True,
        "boundary": BOUNDARY_V0782,
        "tracked_file_count": len(tracked),
        "secret_pattern_hit_count": len(secret_hits),
        "public_report_secret_hit_count": len(public_report_scan["secret_hits"]),
        "revocation_record": "docs/key_revocation_record_v0782.md",
        "ignored_path_categories_checked": IGNORED_ROOTS,
        "allowed_tracked_public_source_exception": "frontend/data/*",
    }
    private_report = {
        **public_report,
        "public_safe": False,
        "checks": checks,
        "secret_hits": secret_hits,
        "public_report_scan": public_report_scan,
        "tracked_files_checked": tracked,
        "restricted_note": "Private report lists tracked paths and pattern categories only; no secret values are printed.",
    }
    lines = [
        "# V0.78.2 Secret Cleanup + Key Revocation Audit",
        "",
        f"Result: {public_report['result']}",
        f"Passed checks: {passed}/{total}",
        "",
        f"Boundary: {BOUNDARY_V0782}",
        "",
        "## Checks",
        "",
    ]
    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        lines.append(f"- {status}: {check['name']}")
    lines.extend(["", "## Command Results", "", "- RUN: python examples/audit_v0782_secret_cleanup.py", ""])
    return public_report, private_report, "\n".join(lines)


def main() -> int:
    checks: list[dict[str, Any]] = []
    tracked = tracked_files()

    add_check(checks, "git_repository_available", bool(tracked), f"{len(tracked)} tracked files")
    add_check(checks, "gitignore_exists", (ROOT / ".gitignore").exists(), ".gitignore")

    for prefix in IGNORED_ROOTS:
        matches = tracked_matching(tracked, prefix)
        if prefix == "data/":
            matches = [path for path in matches if not path.startswith("frontend/data/")]
        if prefix == "config/":
            matches = [path for path in matches if path not in ALLOWED_TRACKED_CONFIGS]
        if prefix == "reports/":
            matches = [path for path in matches if path not in ALLOWED_TRACKED_REPORTS]
        add_check(checks, f"{prefix.replace('/', '').replace('.', 'dot')}_not_tracked", not matches, {"count": len(matches), "paths": matches[:10]})

    km1_safe, km1_detail = km1_lock_artifact_safe()
    add_check(checks, "allowed_km1_release_lock_is_public_safe", km1_safe, km1_detail)
    file_manifest_safe, file_manifest_detail = km1_file_manifest_safe()
    add_check(
        checks,
        "allowed_km1_release_file_manifest_is_secret_safe",
        file_manifest_safe,
        file_manifest_detail,
    )

    frontend_data = [path for path in tracked if path.startswith("frontend/data/")]
    add_check(checks, "frontend_data_public_source_allowed", bool(frontend_data), {"count": len(frontend_data), "sample": frontend_data[:10]})

    db_files = [path for path in tracked if any(path.lower().endswith(suffix) for suffix in DATABASE_SUFFIXES)]
    add_check(checks, "sqlite_database_files_not_tracked", not db_files, db_files)

    secret_hits = scan_tracked_secrets(tracked)
    add_check(checks, "tracked_files_have_no_obvious_raw_secret_patterns", not secret_hits, {"count": len(secret_hits), "hits": secret_hits[:20]})

    public_report_scan = scan_public_reports()
    add_check(checks, "public_reports_have_no_secret_patterns", not public_report_scan["secret_hits"], {"count": len(public_report_scan["secret_hits"]), "reports_scanned": public_report_scan["public_report_count"]})

    env_ok, env_bad = env_example_placeholder_only()
    add_check(checks, "env_example_uses_placeholders_only", env_ok, env_bad)

    revoke_ok, revoke_missing = revocation_record_ok()
    add_check(checks, "revocation_record_exists_and_covers_required_points", revoke_ok, revoke_missing)

    gitignore_text = (ROOT / ".gitignore").read_text(encoding="utf-8", errors="replace") if (ROOT / ".gitignore").exists() else ""
    for term in ["reports/", "/logs/", "/config/", "/data/", "/inputs/", "/design_sources/", "node_modules/", ".next/", "*.sqlite", "*.db"]:
        add_check(checks, f"gitignore_contains_{term.replace('/', '_').replace('*', 'star').replace('.', 'dot')}", term in gitignore_text, term)

    revoked_or_ignored = all(term in gitignore_text for term in ["config_REVOKED_DO_NOT_USE_", "logs_REVOKED_DO_NOT_USE_"]) and revoke_ok
    add_check(checks, "old_key_config_log_paths_marked_revoked_or_ignored", revoked_or_ignored, None)

    real_data = real_client_data_hits(tracked)
    add_check(checks, "no_real_client_data_patterns_in_tracked_files", not real_data, real_data[:20])

    public_report, private_report, scorecard = build_reports(checks, tracked, secret_hits, public_report_scan)
    write_json(PUBLIC_REPORT, public_report)
    write_json(PRIVATE_REPORT, private_report)
    SCORECARD.write_text(scorecard, encoding="utf-8")

    print("PRMR Memory Core V0.78.2 Secret Cleanup + Key Revocation Audit")
    print(f"Tracked files checked: {len(tracked)}")
    print(f"Secret pattern hits: {len(secret_hits)}")
    print(f"Public report secret hits: {len(public_report_scan['secret_hits'])}")
    print(f"Revocation record: {REVOCATION_RECORD.as_posix()}")
    print(f"Public report: {PUBLIC_REPORT.as_posix()}")
    print(f"Private report: {PRIVATE_REPORT.as_posix()}")
    print(f"Scorecard: {SCORECARD.as_posix()}")
    print(f"Passed checks: {public_report['checks_passed']}/{public_report['checks_total']}")
    print(f"Result: {public_report['result']}")
    if public_report["result"] != "PASS":
        print(json.dumps([check for check in checks if not check["passed"]], indent=2, sort_keys=True))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
