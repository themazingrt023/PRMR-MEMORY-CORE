from pathlib import Path

path = Path("prmr/core/engine.py")
text = path.read_text(encoding="utf-8")
lines = text.splitlines()

keywords = [
    "rule",
    "rule_possible",
    "internal_rule_data",
    "No trusted symbolic rule found",
    "compress",
    "transform"
]

print("PRMR V0.36.4 RULE ENGINE INSPECTION")
print("-----------------------------------")

shown_blocks = set()

for index, line in enumerate(lines, start=1):
    if any(keyword.lower() in line.lower() for keyword in keywords):
        start = max(1, index - 10)
        end = min(len(lines), index + 18)
        block_key = (start, end)

        if block_key in shown_blocks:
            continue

        shown_blocks.add(block_key)

        print()
        print(f"--- Around line {index} ---")
        for line_number in range(start, end + 1):
            print(f"{line_number}: {lines[line_number - 1]}")