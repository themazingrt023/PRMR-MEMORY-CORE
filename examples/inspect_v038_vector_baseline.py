import json
from pathlib import Path

PRIVATE = Path("reports/v038/private_internal_baseline_war_v038.json")

data = json.loads(PRIVATE.read_text(encoding="utf-8"))

details = data["details"]["vector_like"]

print("V0.38 VECTOR-LIKE BASELINE INSPECTION")
print("------------------------------------")

for topic, item in details.items():
    print("Topic:", topic)
    print("Score:", item["score"])
    print("Answer:", item["answer"])
    print("Expected:", item["expected"])
    print()