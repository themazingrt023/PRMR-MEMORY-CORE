import json
from pathlib import Path

path = Path("reports/v037/public_realistic_memory_benchmark_v037.json")
data = json.loads(path.read_text(encoding="utf-8"))

compression = data["details"]["compression_judgment"]

print("PRMR V0.37 COMPRESSION GAP INSPECTION")
print("-------------------------------------")
print("Points:", compression["points"], "/", compression["max_points"])
print("Average:", compression["average"])
print()

for item in compression["details"]:
    print("Dataset:", item["dataset"])
    print("Score:", item["score"])
    print("Policy mode:", item["policy_mode"])
    print("Compression ratio:", item["compression_ratio"])
    print("Saved percentage:", item["saved_percentage"])
    print()