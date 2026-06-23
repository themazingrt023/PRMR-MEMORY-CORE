import json
import os


class LinearRuleDiscovery:
    def __init__(self):
        self.discovered_rules = {}

    def discover_linear_rule(self, values):
        """
        Detects simple linear rule:
        value = base + step * index

        Example:
        [0, 10, 20, 30] -> base=0, step=10
        [5, 8, 11, 14] -> base=5, step=3
        """

        if len(values) < 2:
            return {
                "rule_found": False,
                "reason": "Not enough values"
            }

        base = values[0]
        step = values[1] - values[0]

        for index, value in enumerate(values):
            expected = base + step * index

            if value != expected:
                return {
                    "rule_found": False,
                    "reason": "Values are not linear",
                    "values": values
                }

        return {
            "rule_found": True,
            "type": "linear",
            "base": base,
            "step": step,
            "formula": f"value = {base} + ({step} * branch_index)"
        }

    def discover_cycle_rule(self, values):
        """
        Detects repeating cycle.

        Example:
        ["red", "gold", "red", "gold"] -> cycle ["red", "gold"]
        """

        if len(values) < 2:
            return {
                "rule_found": False,
                "reason": "Not enough values"
            }

        for cycle_length in range(1, len(values) + 1):
            cycle = values[:cycle_length]
            reconstructed = []

            for index in range(len(values)):
                reconstructed.append(cycle[index % cycle_length])

            if reconstructed == values:
                return {
                    "rule_found": True,
                    "type": "cycle",
                    "cycle": cycle,
                    "formula": f"value = cycle[branch_index % {cycle_length}]"
                }

        return {
            "rule_found": False,
            "reason": "No cycle found",
            "values": values
        }


def generate_training_data(branch_count):
    """
    This simulates transformation data across branches.

    This is what PRMR sees BEFORE discovering the rule.
    """

    colours = [
        "red", "gold", "magenta", "lime", "orange",
        "white", "purple", "cyan", "pink", "yellow"
    ]

    data = {
        "orb_dx": [],
        "orb_dy": [],
        "sun_dx": [],
        "sun_dy": [],
        "block_width": [],
        "gate_height": [],
        "orb_colour": [],
        "portal_colour": []
    }

    for branch_index in range(branch_count):
        colour_offset = branch_index % len(colours)

        data["orb_dx"].append(10 * branch_index)
        data["orb_dy"].append(-5 * branch_index)

        data["sun_dx"].append(-4 * branch_index)
        data["sun_dy"].append(3 * branch_index)

        data["block_width"].append(120 + (branch_index % 20) * 6)
        data["gate_height"].append(120 + (branch_index % 20) * 5)

        data["orb_colour"].append(colours[colour_offset])
        data["portal_colour"].append(colours[(colour_offset + 8) % len(colours)])

    return data


def reconstruct_values_from_rule(rule, count):
    values = []

    if rule["type"] == "linear":
        base = rule["base"]
        step = rule["step"]

        for index in range(count):
            values.append(base + step * index)

    elif rule["type"] == "cycle":
        cycle = rule["cycle"]

        for index in range(count):
            values.append(cycle[index % len(cycle)])

    return values


def run_rule_discovery_test(branch_count):
    discovery = LinearRuleDiscovery()
    training_data = generate_training_data(branch_count)

    discovered = {}

    for key, values in training_data.items():
        if isinstance(values[0], int):
            discovered[key] = discovery.discover_linear_rule(values)

            # If linear fails, try cycle
            if not discovered[key]["rule_found"]:
                discovered[key] = discovery.discover_cycle_rule(values)

        else:
            discovered[key] = discovery.discover_cycle_rule(values)

    reconstruction_results = {}

    for key, rule in discovered.items():
        original_values = training_data[key]

        if rule["rule_found"]:
            reconstructed_values = reconstruct_values_from_rule(rule, branch_count)

            reconstruction_results[key] = {
                "match": original_values == reconstructed_values,
                "original": original_values,
                "reconstructed": reconstructed_values,
                "rule": rule
            }

        else:
            reconstruction_results[key] = {
                "match": False,
                "original": original_values,
                "reconstructed": None,
                "rule": rule
            }

    all_rules_found = all(rule["rule_found"] for rule in discovered.values())
    all_reconstructions_match = all(result["match"] for result in reconstruction_results.values())

    return {
        "test_name": "Rule Discovery V0.22",
        "branch_count": branch_count,
        "fields_tested": list(training_data.keys()),
        "rules_discovered": discovered,
        "all_rules_found": all_rules_found,
        "all_reconstructions_match": all_reconstructions_match,
        "reconstruction_results": reconstruction_results
    }


os.makedirs("reports", exist_ok=True)

branch_counts = [5, 10, 25, 50, 100]

results = []

for branch_count in branch_counts:
    result = run_rule_discovery_test(branch_count)
    results.append(result)

with open("reports/rule_discovery_v022.json", "w", encoding="utf-8") as file:
    json.dump(results, file, indent=4)

print("PRMR RULE DISCOVERY V0.22")
print("------------------------")

for result in results:
    print("\nBranches:", result["branch_count"])
    print("Fields tested:", len(result["fields_tested"]))
    print("All rules found:", result["all_rules_found"])
    print("All reconstructions match:", result["all_reconstructions_match"])

    print("\nDiscovered Rules:")

    for field_name, rule in result["rules_discovered"].items():
        print("-", field_name + ":", rule["formula"] if rule["rule_found"] else rule["reason"])

print("\nREPORT CREATED:")
print("reports/rule_discovery_v022.json")