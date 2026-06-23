import json
from pathlib import Path


SECURITY_REPORT = Path("reports/v0363/security_isolation_deep_test_v0363.json")


def main():
    data = json.loads(SECURITY_REPORT.read_text(encoding="utf-8"))

    print("PRMR V0.36.3 PUBLIC REPORT SAFETY FAILURE INSPECTION")
    print("----------------------------------------------------")

    public_check = None

    for check in data.get("checks", []):
        if check.get("name") == "public_report_exposes_no_private_internals_or_keys":
            public_check = check
            break

    if public_check is None:
        print("Could not find public report safety check.")
        return

    details = public_check.get("details", {})

    print("Passed:", public_check.get("passed"))
    print("Public report path:", details.get("public_report_path"))
    print("Forbidden terms found:", details.get("forbidden_terms_found"))
    print()

    public_path = details.get("public_report_path")

    if not public_path:
        print("No public report path found.")
        return

    path = Path(public_path)

    if not path.exists():
        print("Public report file does not exist:", path)
        return

    text = path.read_text(encoding="utf-8", errors="ignore")

    forbidden_terms = details.get("forbidden_terms_found") or []

    for term in forbidden_terms:
        print()
        print("TERM:", term)
        lowered = text.lower()
        term_lower = term.lower()
        index = lowered.find(term_lower)

        if index == -1:
            print("Term not found in raw text even though it was reported.")
            continue

        start = max(0, index - 400)
        end = min(len(text), index + 700)

        print("CONTEXT:")
        print(text[start:end])

    print()
    print("Inspection complete.")


if __name__ == "__main__":
    main()