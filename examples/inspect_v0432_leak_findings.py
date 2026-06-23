import json
from pathlib import Path

REPORT_PATH = Path("reports/v0432/report_leak_scan_v0432.json")


def main():
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))

    print("PRMR V0.43.2 LEAK FINDINGS INSPECTOR")
    print("------------------------------------")

    for check in report["checks"]:
        if check["name"] == "public_facing_reports_contain_no_private_internal_terms":
            leaks = check["details"].get("public_internal_leaks", [])

            print("Public/internal leak findings:", len(leaks))
            print()

            for leak in leaks:
                print("FILE:", leak["file"])
                print("TERMS:", ", ".join(leak["forbidden_terms_found"]))
                print("-" * 80)

    print()
    print("Done.")


if __name__ == "__main__":
    main()