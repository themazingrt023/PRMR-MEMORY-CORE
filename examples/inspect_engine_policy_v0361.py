from pathlib import Path

path = Path("prmr/core/engine.py")
text = path.read_text(encoding="utf-8")
lines = text.splitlines()

keywords = [
    "policy_mode",
    "technical_best_mode",
    "technical_saved_percentage",
    "threshold",
    "policy_reason",
    "raw mode",
    "transform",
    "rule_possible"
]

print("PRMR ENGINE POLICY INSPECTION V0.36.1")
print("-------------------------------------")

for index, line in enumerate(lines, start=1):
    if any(keyword in line for keyword in keywords):
        start = max(1, index - 8)
        end = min(len(lines), index + 12)

        print()
        print(f"--- Around line {index} ---")
        for line_number in range(start, end + 1):
            print(f"{line_number}: {lines[line_number - 1]}")