from pathlib import Path

AUDIT_PATH = Path("examples/audit_v0431_security_integrity.py")

NEW_FUNCTION = r'''def hardcode_scan(text):
    """
    Conservative hardcode scan.

    This should flag direct final-result forcing, but should NOT flag:
    - normal test dictionaries
    - expected PASS/FAIL strings
    - conditional result lines such as:
      "PASS" if all(...) else "NEEDS_WORK"
    """

    suspicious = []

    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        lowered = stripped.lower()

        # Ignore comments and empty lines.
        if not stripped or stripped.startswith("#"):
            continue

        # Direct final result hardcoding without conditional logic.
        if (
            ("result" in lowered)
            and ("pass" in lowered)
            and (" if " not in lowered)
            and ("all(" not in lowered)
            and ("else" not in lowered)
            and (
                "public_report" in lowered
                or "private_report" in lowered
                or "report" in lowered
            )
        ):
            suspicious.append({
                "line": line_number,
                "reason": "possible_direct_result_pass_assignment",
                "text": stripped
            })

        # Direct fixed test count hardcoding.
        if (
            ("tests_passed" in lowered or "passed_checks" in lowered)
            and ("= 14" in lowered or ": 14" in lowered)
            and ("sum(" not in lowered)
        ):
            suspicious.append({
                "line": line_number,
                "reason": "possible_fixed_pass_count",
                "text": stripped
            })

        # Direct forced all-passed hardcoding.
        if (
            ("all_integrity_checks_passed" in lowered or "all_passed" in lowered)
            and ("true" in lowered)
            and ("==" not in lowered)
            and ("=" in lowered or ":" in lowered)
            and ("passed_count" not in lowered)
            and ("total_checks" not in lowered)
        ):
            suspicious.append({
                "line": line_number,
                "reason": "possible_forced_all_passed",
                "text": stripped
            })

    return suspicious
'''


def replace_function(text, function_name, new_function):
    start_marker = f"def {function_name}("
    start = text.index(start_marker)

    next_def = text.find("\ndef ", start + 1)

    if next_def == -1:
        end = len(text)
    else:
        end = next_def + 1

    return text[:start] + new_function + "\n\n" + text[end:]


def main():
    if not AUDIT_PATH.exists():
        raise FileNotFoundError(f"Missing audit file: {AUDIT_PATH}")

    text = AUDIT_PATH.read_text(encoding="utf-8")

    if "def hardcode_scan(text):" not in text:
        raise RuntimeError("Could not find hardcode_scan function.")

    patched = replace_function(text, "hardcode_scan", NEW_FUNCTION)

    AUDIT_PATH.write_text(patched, encoding="utf-8")

    print("V0.43.1 hardcode scan patched.")
    print("Patched:", AUDIT_PATH)
    print()
    print("Next run:")
    print("python examples/audit_v0431_security_integrity.py")


if __name__ == "__main__":
    main()