import json
from pathlib import Path

path = Path("reports/v036/private_internal_trust_benchmark_v036.json")
data = json.loads(path.read_text(encoding="utf-8"))

snapshot = data.get("prmr_engine_public_result_snapshot")

print("TOP LEVEL TYPE:", type(snapshot))
print()

if isinstance(snapshot, dict):
    print("TOP LEVEL KEYS:")
    for key in snapshot.keys():
        print("-", key)

    print("\nFULL SNAPSHOT PREVIEW:")
    print(json.dumps(snapshot, indent=4)[:5000])
else:
    print(snapshot)