from pathlib import Path

path = Path("prmr/core/modes.py")

if not path.exists():
    print("Could not find:", path)
    raise SystemExit

text = path.read_text(encoding="utf-8")
lines = text.splitlines()

keywords = [
    "build_mode_options",
    "rule",
    "symbolic",
    "field",
    "No trusted symbolic rule found",
    "raw",
    "transform",
    "package",
    "reconstruct",
]

print("PRMR V0.36.4 MODES/RULE ENGINE INSPECTION")
print("-----------------------------------------")
print("File:", path)
print("Total lines:", len(lines))

shown_blocks = set()

for index, line in enumerate(lines, start=1):
    if any(keyword.lower() in line.lower() for keyword in keywords):
        start = max(1, index - 12)
        end = min(len(lines), index + 25)
        block_key = (start, end)

        if block_key in shown_blocks:
            continue

        shown_blocks.add(block_key)

        print()
        print(f"--- Around line {index} ---")
        for line_number in range(start, end + 1):
            print(f"{line_number}: {lines[line_number - 1]}")