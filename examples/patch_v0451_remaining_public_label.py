from pathlib import Path

RUNNER = Path("benchmarks/runners/run_fraud_continuity_simulator_v045.py")
AUDIT = Path("examples/audit_v0451_fraud_simulator_integrity.py")

# Patch runner public check label.
runner_text = RUNNER.read_text(encoding="utf-8")
runner_text = runner_text.replace(
    "fraud_continuity_classification_matches_private_truth",
    "fraud_continuity_classification_matches_expected_labels"
)
RUNNER.write_text(runner_text, encoding="utf-8")

# Patch audit check label too, so future audit reports are cleaner.
audit_text = AUDIT.read_text(encoding="utf-8")
audit_text = audit_text.replace(
    "public_report_exposes_no_private_truth_or_engine_internals",
    "public_report_exposes_no_private_labels_or_engine_internals"
)
audit_text = audit_text.replace(
    "private_truth_labels_exist_for_all_accounts",
    "expected_labels_exist_for_all_accounts"
)
AUDIT.write_text(audit_text, encoding="utf-8")

print("Patched remaining public label hygiene.")
print("Now run:")
print("python benchmarks/runners/run_fraud_continuity_simulator_v045.py")
print("python examples/audit_v0451_fraud_simulator_integrity.py")