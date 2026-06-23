from pathlib import Path

TARGETS = [
    "benchmarks/runners/run_trust_suite_v036.py",
    "benchmarks/runners/run_realistic_memory_benchmark_v037.py",
    "examples/audit_v0371_result_integrity.py",
    "benchmarks/runners/run_baseline_war_antileak_v0381.py",
    "examples/audit_v0382_baseline_war_integrity.py",
    "benchmarks/runners/run_adversarial_memory_trial_v039.py",
    "examples/audit_v0391_adversarial_integrity.py",
    "examples/run_master_regression_gauntlet_v040.py",
]

REPLACEMENTS = {
    "✅": "[PASS]",
    "❌": "[FAIL]",
    "⚠️": "[WARN]",
    "⚠": "[WARN]",
    "🧠": "",
    "🔥": "",
    "🚀": "",
}


def main():
    print("PRMR V0.40 ASCII-SAFE CLI PATCH")
    print("--------------------------------")

    changed_files = []

    for file_name in TARGETS:
        path = Path(file_name)

        if not path.exists():
            print("Missing:", file_name)
            continue

        text = path.read_text(encoding="utf-8")
        original = text

        for old, new in REPLACEMENTS.items():
            text = text.replace(old, new)

        if text != original:
            path.write_text(text, encoding="utf-8")
            changed_files.append(file_name)
            print("Patched:", file_name)
        else:
            print("No emoji found:", file_name)

    print()
    print("ASCII-safe CLI patch complete.")
    print("Changed files:", len(changed_files))
    print()
    print("Next run:")
    print("python examples/run_master_regression_gauntlet_v040.py")


if __name__ == "__main__":
    main()