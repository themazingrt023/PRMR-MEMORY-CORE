from pathlib import Path

path = Path("benchmarks/runners/run_security_isolation_deep_v0363.py")
text = path.read_text(encoding="utf-8")

if "import re" not in text:
    text = text.replace("import json", "import json\nimport re")

start = text.index("def public_report_is_safe")
end = text.index("def logs_do_not_store_raw_keys")

new_function = r'''def public_report_is_safe(public_report_path):
    if not public_report_path:
        return {
            "passed": False,
            "reason": "No public report path returned."
        }

    path = Path(public_report_path)

    if not path.exists():
        return {
            "passed": False,
            "reason": f"Public report file does not exist: {public_report_path}"
        }

    text = path.read_text(encoding="utf-8", errors="ignore")
    lowered = text.lower()

    # These are genuinely private/internal concepts that should not appear in public reports.
    forbidden_terms = [
        "compressed_package",
        "internal_rule_data",
        "private_internal",
        "x-prmr-api-key",
        "api_key",
        "secret"
    ]

    forbidden_terms_found = [
        term for term in forbidden_terms
        if term.lower() in lowered
    ]

    # Smart key detection:
    # Do NOT fail on safe fields like "prmr_size_estimate".
    # Only fail on actual-looking API keys such as prmr_ + long random token.
    api_key_pattern = re.compile(r"prmr_[A-Za-z0-9]{20,}")
    api_key_matches = api_key_pattern.findall(text)

    return {
        "passed": len(forbidden_terms_found) == 0 and len(api_key_matches) == 0,
        "public_report_path": public_report_path,
        "forbidden_terms_found": forbidden_terms_found,
        "api_key_like_matches_found": len(api_key_matches),
        "note": "Safe PRMR metric names such as prmr_size_estimate are allowed. Actual API-key-like values are blocked."
    }


'''

text = text[:start] + new_function + text[end:]
path.write_text(text, encoding="utf-8")

print("V0.36.3 public report safety scanner patched ✅")
print("Now rerun: python benchmarks/runners/run_security_isolation_deep_v0363.py")