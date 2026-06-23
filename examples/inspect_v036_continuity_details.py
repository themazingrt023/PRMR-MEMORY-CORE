import json
from pathlib import Path

path = Path("reports/v036/public_trust_benchmark_v036.json")
data = json.loads(path.read_text(encoding="utf-8"))

continuity = data.get("continuity_preservation", {})

print("PRMR V0.36 CONTINUITY DETAILS")
print("-----------------------------")
print("Points:", continuity.get("points"), "/", continuity.get("max_points"))
print("Average score:", continuity.get("average_continuity_score"))
print("Passed checks:", continuity.get("passed_checks"), "/", continuity.get("total_checks"))
print()
print("Note:", continuity.get("note"))
print()

for check in continuity.get("checks", []):
    print("Scenario:", check.get("scenario"))
    print("Passed:", check.get("passed"))
    print("Score:", check.get("score"))
    print("Description:", check.get("description"))

    print("Channels:")
    for name, channel in check.get("channels", {}).items():
        print(" -", name, "=", channel.get("passed"), "| missing:", channel.get("missing"))

    print("PRMR interpretation:")
    for key, value in check.get("prmr_interpretation", {}).items():
        print(" -", key + ":", value)

    print()