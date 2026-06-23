import json
from pathlib import Path

REPORT = Path("reports/v050/whole_core_truth_gauntlet_v050.json")

data = json.loads(REPORT.read_text(encoding="utf-8"))

print("PRMR V0.50 FAILURE INSPECTOR")
print("----------------------------")
print("Result:", data.get("result"))
print()

print("FAILED CHECKS:")
for check in data.get("checks", []):
    if not check.get("passed"):
        print()
        print("-", check.get("name"))
        details = check.get("details", {})

        if "failed_scripts" in details:
            print("  failed_scripts:")
            for item in details["failed_scripts"]:
                print("  -", item.get("script"))
                print("    returncode:", item.get("returncode"))
                print("    bad_markers:", item.get("bad_markers_found"))
                print("    positive_markers:", item.get("positive_markers_found"))

        if "public_leak_findings" in details:
            print("  public_leak_findings:")
            for item in details["public_leak_findings"][:50]:
                print("  -", item.get("file"))
                print("    terms:", item.get("forbidden_terms_found"))

        if "unsafe_language_findings" in details:
            print("  unsafe_language_findings:")
            for item in details["unsafe_language_findings"][:50]:
                print("  -", item.get("file"))
                print("    terms:", item.get("unsafe_language_found"))

print()
print("SUMMARY:")
print(json.dumps(data.get("summary", {}), indent=4))