from pathlib import Path

V050 = Path("examples/run_whole_core_truth_gauntlet_v050.py")

text = V050.read_text(encoding="utf-8")

# Add superseded V0.38 original baseline war to the exclusion list.
# V0.38 original is historical NEEDS_WORK because vector_like tied PRMR due leakage.
# V0.38.1 and V0.38.2 are the corrected active proof.
if '"run_baseline_war_v038.py"' not in text:
    text = text.replace(
        '    "run_whole_core_truth_gauntlet_v050.py",\n]',
        '    "run_whole_core_truth_gauntlet_v050.py",\n'
        '    "run_baseline_war_v038.py",  # superseded by V0.38.1 anti-leak + V0.38.2 integrity audit\n'
        ']'
    )

# Do not treat original reports/v038 as current public proof.
# They remain historical evidence of the flaw that V0.38.1 fixed.
if "V0.38 original is a superseded diagnostic" not in text:
    text = text.replace(
        '    lower = str(path).lower()\n    name = path.name.lower()\n\n    if "private" in lower or "internal" in lower:',
        '    lower = str(path).lower()\n'
        '    name = path.name.lower()\n\n'
        '    # V0.38 original is a superseded diagnostic that intentionally returned NEEDS_WORK.\n'
        '    # Current proof is V0.38.1/V0.38.2.\n'
        '    if ("reports\\\\v038\\\\" in lower or "reports/v038/" in lower) and "v0381" not in lower and "v0382" not in lower:\n'
        '        return False\n\n'
        '    if "private" in lower or "internal" in lower:'
    )

# Also skip original reports/v038 markdown during public markdown scan.
if "V0.38 original is a superseded diagnostic artifact" not in text:
    text = text.replace(
        '    for path in md_reports:\n        lower = str(path).lower()\n\n        if "private" in lower or "internal" in lower:\n            continue',
        '    for path in md_reports:\n'
        '        lower = str(path).lower()\n\n'
        '        # V0.38 original is a superseded diagnostic artifact, not current public proof.\n'
        '        if ("reports\\\\v038\\\\" in lower or "reports/v038/" in lower) and "v0381" not in lower and "v0382" not in lower:\n'
        '            continue\n\n'
        '        if "private" in lower or "internal" in lower:\n'
        '            continue'
    )

V050.write_text(text, encoding="utf-8")

print("Patched V0.50 superseded diagnostic handling.")
print("Original V0.38 remains historical NEEDS_WORK evidence.")
print("Active proof remains V0.38.1 + V0.38.2.")
print()
print("Now run:")
print("python examples/run_whole_core_truth_gauntlet_v050.py")