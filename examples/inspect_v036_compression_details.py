import json
from pathlib import Path

path = Path("reports/v036/private_internal_trust_benchmark_v036.json")
data = json.loads(path.read_text(encoding="utf-8"))

snapshot = data["prmr_engine_public_result_snapshot"]
results = snapshot.get("results", [])

print("PRMR V0.36 COMPRESSION DETAILS")
print("--------------------------------")

for item in results:
    decision = item.get("decision", {})

    print()
    print("Dataset:", item.get("dataset"))
    print("Rows:", item.get("row_count"))
    print("Policy mode:", decision.get("policy_mode"))
    print("Technical best mode:", decision.get("technical_best_mode"))
    print("Raw size:", decision.get("raw_size"))
    print("Transform size:", decision.get("transform_size"))
    print("Rule possible:", decision.get("rule_possible"))
    print("Rule size:", decision.get("rule_size"))
    print("Rule failed field:", decision.get("rule_failed_field"))
    print("Rule failure reason:", decision.get("rule_failure_reason"))
    print("Policy compression ratio:", decision.get("policy_compression_ratio"))
    print("Policy saved percentage:", decision.get("policy_saved_percentage"))
    print("Policy reason:", decision.get("policy_reason"))