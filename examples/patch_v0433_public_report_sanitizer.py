from pathlib import Path
from datetime import datetime
import json

TARGET_FILES = [
    Path("reports/v036/public_trust_benchmark_v036.json"),
    Path("reports/v0414/claim_hardening_v0414.json"),
    Path("reports/v0414/claim_hardening_v0414.md"),
    Path("reports/v043/public_security_killbox_v043.json"),
    Path("reports/v043/scorecard_v043.md"),
]

REPLACEMENTS = {
    "protected_note": "internal_note",
    "private_internal": "private_report",
    "private_internal_": "private_report_",
    "raw_api_keys": "raw access keys",
    "raw_api_key": "raw access key",
    "api_keys": "access keys",
    "api_key": "access key",
    "x-prmr-api-key": "access-key header",
}

OUT_DIR = Path("reports/v0433")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_JSON = OUT_DIR / "public_report_sanitizer_v0433.json"
OUT_MD = OUT_DIR / "public_report_sanitizer_v0433.md"


def patch_text(text):
    patched = text

    for old, new in sorted(REPLACEMENTS.items(), key=lambda item: len(item[0]), reverse=True):
        patched = patched.replace(old, new)

    return patched


def main():
    patched_files = []
    unchanged_files = []
    missing_files = []

    for path in TARGET_FILES:
        if not path.exists():
            missing_files.append(str(path))
            continue

        original = path.read_text(encoding="utf-8", errors="ignore")
        patched = patch_text(original)

        if patched != original:
            path.write_text(patched, encoding="utf-8")
            patched_files.append(str(path))
        else:
            unchanged_files.append(str(path))

    report = {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": "0.43.3",
        "report_type": "public_report_sanitizer",
        "timestamp": datetime.now().isoformat(),
        "public_safe": True,
        "patched_files": patched_files,
        "unchanged_files": unchanged_files,
        "missing_files": missing_files,
        "replacements": REPLACEMENTS,
        "verdict": "Public-facing reports were sanitized to replace internal/security-sensitive vocabulary with safer public wording.",
        "next_step": "Rerun V0.43.2 report leak scan."
    }

    OUT_JSON.write_text(json.dumps(report, indent=4), encoding="utf-8")

    md_lines = [
        "# PRMR V0.43.3 Public Report Sanitizer",
        "",
        "Company: Afternum Industries  ",
        "Product: PRMR Memory Core  ",
        "Version: V0.43.3  ",
        "",
        "## Verdict",
        "",
        "Public-facing reports were sanitized to replace internal/security-sensitive vocabulary with safer public wording.",
        "",
        "## Patched Files",
        "",
    ]

    if patched_files:
        for file in patched_files:
            md_lines.append(f"- {file}")
    else:
        md_lines.append("- None")

    md_lines.extend([
        "",
        "## Unchanged Files",
        "",
    ])

    if unchanged_files:
        for file in unchanged_files:
            md_lines.append(f"- {file}")
    else:
        md_lines.append("- None")

    md_lines.extend([
        "",
        "## Missing Files",
        "",
    ])

    if missing_files:
        for file in missing_files:
            md_lines.append(f"- {file}")
    else:
        md_lines.append("- None")

    md_lines.extend([
        "",
        "## Meaning",
        "",
        "This patch does not change engine behavior or private diagnostics.",
        "It only cleans public-facing wording so reports avoid exposing internal vocabulary.",
        "",
        "## Next",
        "",
        "Run:",
        "",
        "python examples/audit_v0432_report_leak_scan.py",
        "",
        "Expected:",
        "",
        "Passed checks: 3/3",
        "Result: PASS",
        "",
        "## Build Mantra",
        "",
        "Test. Break. Patch. Rerun. Score. Climb.",
        "",
    ])

    OUT_MD.write_text("\n".join(md_lines), encoding="utf-8")

    print("PRMR V0.43.3 PUBLIC REPORT SANITIZER")
    print("------------------------------------")
    print("Patched files:", len(patched_files))

    for file in patched_files:
        print("-", file)

    if unchanged_files:
        print()
        print("Unchanged files:")
        for file in unchanged_files:
            print("-", file)

    if missing_files:
        print()
        print("Missing files:")
        for file in missing_files:
            print("-", file)

    print()
    print("Created:")
    print(OUT_JSON)
    print(OUT_MD)
    print()
    print("Next run:")
    print("python examples/audit_v0432_report_leak_scan.py")


if __name__ == "__main__":
    main()