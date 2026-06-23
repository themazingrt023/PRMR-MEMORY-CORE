from pathlib import Path

FILES = [
    Path("examples/audit_v0481_human_harm_integrity.py"),
    Path("examples/audit_v0482_human_harm_report_leak_scan.py"),
]

REPLACEMENTS = {
    "public_report_exposes_no_private_harm_packets_or_engine_terms":
        "public_report_exposes_no_hidden_harm_packets_or_engine_terms",

    "human_harm_public_reports_expose_no_private_packets_or_engine_internals":
        "human_harm_public_reports_expose_no_hidden_packets_or_engine_internals",
}

for path in FILES:
    text = path.read_text(encoding="utf-8")

    for old, new in REPLACEMENTS.items():
        text = text.replace(old, new)

    path.write_text(text, encoding="utf-8")
    print("Patched:", path)

print()
print("Now rerun:")
print("python examples/audit_v0481_human_harm_integrity.py")
print("python examples/audit_v0482_human_harm_report_leak_scan.py")