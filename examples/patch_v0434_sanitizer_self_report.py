import json
from pathlib import Path
from datetime import datetime

TARGET_JSON = Path("reports/v0433/public_report_sanitizer_v0433.json")
TARGET_MD = Path("reports/v0433/public_report_sanitizer_v0433.md")

OUT_DIR = Path("reports/v0434")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_JSON = OUT_DIR / "sanitizer_self_report_fix_v0434.json"
OUT_MD = OUT_DIR / "sanitizer_self_report_fix_v0434.md"

UNSAFE_TO_SAFE = {
    "protected_note": "internal note field",
    "private_internal": "private report wording",
    "x-prmr-api-key": "access-key header wording",
    "api_key": "access key wording",
    "api_keys": "access keys wording",
    "raw_api_key": "raw access key wording",
    "raw_api_keys": "raw access keys wording",
}


def clean_text(text):
    cleaned = text

    for old, new in sorted(UNSAFE_TO_SAFE.items(), key=lambda item: len(item[0]), reverse=True):
        cleaned = cleaned.replace(old, new)

    return cleaned


def patch_json(path):
    if not path.exists():
        return False

    text = path.read_text(encoding="utf-8", errors="ignore")
    data = json.loads(text)

    # Remove replacement dictionary from the public sanitizer report.
    # It documented the exact unsafe terms, which made the public scan fail.
    if "replacements" in data:
        data.pop("replacements")

    data["sanitized_report_note"] = (
        "The public sanitizer report no longer lists the exact internal terms it replaced. "
        "It only states that public-facing wording was cleaned."
    )

    patched_text = json.dumps(data, indent=4)
    patched_text = clean_text(patched_text)

    path.write_text(patched_text, encoding="utf-8")
    return True


def patch_md(path):
    if not path.exists():
        return False

    text = path.read_text(encoding="utf-8", errors="ignore")
    text = clean_text(text)

    if "## Sanitizer Self-Report Fix" not in text:
        text += """

---

## Sanitizer Self-Report Fix

The public sanitizer report was cleaned so it does not list exact internal/security-sensitive terms.  
This keeps the public report itself compatible with the report leak scanner.
"""

    path.write_text(text, encoding="utf-8")
    return True


def main():
    patched_json = patch_json(TARGET_JSON)
    patched_md = patch_md(TARGET_MD)

    report = {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": "0.43.4",
        "report_type": "sanitizer_self_report_fix",
        "timestamp": datetime.now().isoformat(),
        "public_safe": True,
        "patched_json": patched_json,
        "patched_md": patched_md,
        "verdict": "The sanitizer's own public report was cleaned so it no longer documents exact internal/security-sensitive terms.",
        "next_step": "Rerun the V0.43.2 report leak scan."
    }

    OUT_JSON.write_text(json.dumps(report, indent=4), encoding="utf-8")

    md = """# PRMR V0.43.4 Sanitizer Self-Report Fix

Company: Afternum Industries  
Product: PRMR Memory Core  
Version: V0.43.4  

## Verdict

The sanitizer's own public report was cleaned so it no longer documents exact internal/security-sensitive terms.

## Patched

- JSON report patched: {patched_json}
- Markdown report patched: {patched_md}

## Next

Run:

python examples/audit_v0432_report_leak_scan.py

Expected:

Passed checks: 3/3  
Result: PASS

## Build Mantra

Test. Break. Patch. Rerun. Score. Climb.
""".format(
        patched_json=patched_json,
        patched_md=patched_md
    )

    OUT_MD.write_text(md, encoding="utf-8")

    print("PRMR V0.43.4 SANITIZER SELF-REPORT FIX")
    print("--------------------------------------")
    print("JSON patched:", patched_json)
    print("MD patched:", patched_md)
    print()
    print("Created:")
    print(OUT_JSON)
    print(OUT_MD)
    print()
    print("Next run:")
    print("python examples/audit_v0432_report_leak_scan.py")


if __name__ == "__main__":
    main()