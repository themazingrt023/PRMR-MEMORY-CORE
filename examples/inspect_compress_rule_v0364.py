from pathlib import Path

path = Path("prmr/core/modes.py")
text = path.read_text(encoding="utf-8")
lines = text.splitlines()

targets = [
    "def compress_rule",
    "def reconstruct_rule",
    "def compress_transform",
    "def reconstruct_transform",
]

print("PRMR V0.36.4 COMPRESS RULE FOCUSED INSPECTION")
print("---------------------------------------------")

for target in targets:
    print()
    print("=" * 80)
    print("TARGET:", target)
    print("=" * 80)

    found = False

    for index, line in enumerate(lines, start=1):
        if target in line:
            found = True
            start = max(1, index - 10)
            end = min(len(lines), index + 90)

            for line_number in range(start, end + 1):
                print(f"{line_number}: {lines[line_number - 1]}")

            break

    if not found:
        print("Not found.")