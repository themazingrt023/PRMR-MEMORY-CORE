from pathlib import Path

path = Path("benchmarks/runners/run_trust_suite_v036.py")
text = path.read_text(encoding="utf-8")

start = text.index("def score_security_and_isolation")
end = text.index("def score_latency_cost")

new_function = r'''def score_security_and_isolation():
    checks = []

    deep_security_report = Path("reports/v0363/security_isolation_deep_test_v0363.json")

    if deep_security_report.exists():
        data = load_json(deep_security_report)
        deep_passed = bool(data.get("all_security_checks_passed"))

        for check in data.get("checks", []):
            checks.append({
                "check": check.get("name"),
                "passed": bool(check.get("passed")),
                "source": "v0363_deep_security_test"
            })

        points = 15 if deep_passed else round(
            15 * (
                sum(1 for check in checks if check["passed"])
                / max(len(checks), 1)
            ),
            2
        )

        return points, {
            "max_points": 15,
            "points": points,
            "passed_checks": sum(1 for check in checks if check["passed"]),
            "total_checks": len(checks),
            "checks": checks,
            "deep_security_report": str(deep_security_report),
            "note": "V0.36.3 deep security/client isolation test checks client A/B vault isolation, missing/invalid/revoked/rotated keys, public report safety, and raw-key log exposure."
        }

    # Fallback to older local hardening checks if V0.36.3 has not been run.
    hardening_v0325 = Path("reports/v0325/hardening_check_v0325.json")
    key_v0345 = Path("reports/v0345/key_management_hardening_v0345.json")

    if hardening_v0325.exists():
        data = load_json(hardening_v0325)
        checks.append({
            "check": "v0325_product_hardening",
            "passed": bool(data.get("all_hardening_checks_passed") or data.get("all_checks_passed"))
        })
    else:
        checks.append({
            "check": "v0325_product_hardening",
            "passed": False,
            "note": "Missing reports/v0325/hardening_check_v0325.json"
        })

    if key_v0345.exists():
        data = load_json(key_v0345)
        checks.append({
            "check": "v0345_key_management",
            "passed": bool(data.get("all_key_management_checks_passed"))
        })
    else:
        checks.append({
            "check": "v0345_key_management",
            "passed": False,
            "note": "Missing reports/v0345/key_management_hardening_v0345.json"
        })

    onboarding_file = Path("prmr_onboarding.py")
    if onboarding_file.exists():
        onboarding_text = onboarding_file.read_text(encoding="utf-8")
        checks.append({
            "check": "client_access_has_masked_key_ui",
            "passed": "apiKeyMasked" in onboarding_text and "Reveal API Key" in onboarding_text
        })
        checks.append({
            "check": "quickstart_uses_placeholder",
            "passed": "YOUR_API_KEY" in onboarding_text
        })
    else:
        checks.append({
            "check": "onboarding_file_exists",
            "passed": False
        })

    passed = sum(1 for check in checks if check["passed"])
    ratio = passed / max(len(checks), 1)
    points = round(ratio * 15, 2)

    return points, {
        "max_points": 15,
        "points": points,
        "passed_checks": passed,
        "total_checks": len(checks),
        "checks": checks,
        "note": "Fallback security score. Run V0.36.3 deep security test for full isolation proof."
    }


'''

text = text[:start] + new_function + text[end:]
path.write_text(text, encoding="utf-8")

print("V0.36.3 security scorer patched ✅")
print("Now rerun the trust suite.")