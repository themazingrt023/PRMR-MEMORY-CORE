import json
import os
import random


class StrictRuleDiscovery:
    def __init__(self, max_cycle_length=20, min_repeats=2):
        self.max_cycle_length = max_cycle_length
        self.min_repeats = min_repeats

    def discover_linear_rule(self, values):
        if len(values) < 3:
            return {
                "rule_found": False,
                "reason": "Not enough values for trusted linear rule"
            }

        base = values[0]
        step = values[1] - values[0]

        for index, value in enumerate(values):
            expected = base + step * index

            if value != expected:
                return {
                    "rule_found": False,
                    "reason": "Values are not linear"
                }

        return {
            "rule_found": True,
            "type": "linear",
            "base": base,
            "step": step
        }

    def discover_constant_rule(self, values):
        if not values:
            return {
                "rule_found": False,
                "reason": "No values"
            }

        first = values[0]

        for value in values:
            if value != first:
                return {
                    "rule_found": False,
                    "reason": "Values are not constant"
                }

        return {
            "rule_found": True,
            "type": "constant",
            "value": first
        }

    def discover_cycle_rule(self, values):
        if len(values) < 4:
            return {
                "rule_found": False,
                "reason": "Not enough values for trusted cycle"
            }

        max_cycle_length = min(
            self.max_cycle_length,
            len(values) // self.min_repeats
        )

        for cycle_length in range(1, max_cycle_length + 1):
            cycle = values[:cycle_length]
            reconstructed = []

            for index in range(len(values)):
                reconstructed.append(cycle[index % cycle_length])

            if reconstructed == values:
                return {
                    "rule_found": True,
                    "type": "cycle",
                    "cycle": cycle,
                    "cycle_length": cycle_length
                }

        return {
            "rule_found": False,
            "reason": "No simple repeating cycle found"
        }

    def discover_best_rule(self, values):
        constant = self.discover_constant_rule(values)

        if constant["rule_found"]:
            return constant

        if all(isinstance(value, int) for value in values):
            linear = self.discover_linear_rule(values)

            if linear["rule_found"]:
                return linear

            cycle = self.discover_cycle_rule(values)

            if cycle["rule_found"]:
                return cycle

            return {
                "rule_found": False,
                "reason": "No trusted numeric rule found"
            }

        cycle = self.discover_cycle_rule(values)

        if cycle["rule_found"]:
            return cycle

        return {
            "rule_found": False,
            "reason": "No trusted symbolic rule found"
        }


def estimate_raw_snapshot_storage(data_rows):
    return len(json.dumps(data_rows, separators=(",", ":")))


def estimate_transformation_storage(data_rows):
    if not data_rows:
        return 0

    origin = data_rows[0]
    deltas = []

    previous = origin

    for row in data_rows[1:]:
        delta = {}

        for key, value in row.items():
            if previous.get(key) != value:
                delta[key] = value

        deltas.append(delta)
        previous = row

    data = {
        "m": "transform",
        "o": origin,
        "d": deltas
    }

    return len(json.dumps(data, separators=(",", ":")))


def reconstruct_from_rule(rule, count):
    values = []

    if rule["type"] == "constant":
        for _ in range(count):
            values.append(rule["value"])

    elif rule["type"] == "linear":
        base = rule["base"]
        step = rule["step"]

        for index in range(count):
            values.append(base + step * index)

    elif rule["type"] == "cycle":
        cycle = rule["cycle"]

        for index in range(count):
            values.append(cycle[index % len(cycle)])

    return values


def reconstruct_rows_from_rules(rules, count):
    columns = {}

    for field, rule in rules.items():
        columns[field] = reconstruct_from_rule(rule, count)

    rows = []

    for index in range(count):
        row = {}

        for field in columns:
            row[field] = columns[field][index]

        rows.append(row)

    return rows


def estimate_rule_storage(data_rows):
    if not data_rows:
        return {
            "possible": False,
            "size": None,
            "rules": {}
        }

    discovery = StrictRuleDiscovery(
        max_cycle_length=20,
        min_repeats=2
    )

    fields = list(data_rows[0].keys())
    rules = {}

    for field in fields:
        values = [row[field] for row in data_rows]
        rule = discovery.discover_best_rule(values)

        if not rule["rule_found"]:
            return {
                "possible": False,
                "size": None,
                "rules": rules,
                "failed_field": field,
                "reason": rule["reason"]
            }

        rules[field] = rule

    reconstructed = reconstruct_rows_from_rules(
        rules,
        len(data_rows)
    )

    reconstruction_match = reconstructed == data_rows

    data = {
        "m": "rule",
        "n": len(data_rows),
        "r": rules
    }

    size = len(json.dumps(data, separators=(",", ":")))

    return {
        "possible": reconstruction_match,
        "size": size,
        "rules": rules,
        "reconstruction_match": reconstruction_match
    }


def choose_storage_mode(data_rows):
    raw_size = estimate_raw_snapshot_storage(data_rows)
    transform_size = estimate_transformation_storage(data_rows)
    rule_result = estimate_rule_storage(data_rows)

    options = [
        {
            "mode": "raw",
            "size": raw_size,
            "possible": True
        },
        {
            "mode": "transform",
            "size": transform_size,
            "possible": True
        }
    ]

    if rule_result["possible"]:
        options.append({
            "mode": "rule",
            "size": rule_result["size"],
            "possible": True,
            "rules": rule_result["rules"]
        })

    best_option = min(
        options,
        key=lambda option: option["size"]
    )

    return {
        "row_count": len(data_rows),
        "raw_size": raw_size,
        "transform_size": transform_size,
        "rule_possible": rule_result["possible"],
        "rule_size": rule_result["size"],
        "rule_failure_reason": rule_result.get("reason"),
        "rule_failed_field": rule_result.get("failed_field"),
        "best_mode": best_option["mode"],
        "best_size": best_option["size"],
        "options": options
    }


def generate_rule_based_data(row_count):
    colours = [
        "red", "gold", "magenta", "lime", "orange",
        "white", "purple", "cyan", "pink", "yellow"
    ]

    rows = []

    for index in range(row_count):
        rows.append({
            "orb_dx": 10 * index,
            "orb_dy": -5 * index,
            "sun_dx": -4 * index,
            "sun_dy": 3 * index,
            "block_width": 120 + (index % 20) * 6,
            "gate_height": 120 + (index % 20) * 5,
            "orb_colour": colours[index % len(colours)],
            "portal_colour": colours[(index + 8) % len(colours)]
        })

    return rows


def generate_transform_based_data(row_count):
    rows = []

    current = {
        "title": "PRMR Memory Core",
        "section_count": 1,
        "status": "draft",
        "confidence": 10
    }

    statuses = ["draft", "review", "edited", "approved"]

    for index in range(row_count):
        current = dict(current)

        if index % 2 == 0:
            current["section_count"] += 1

        if index % 3 == 0:
            current["status"] = statuses[index % len(statuses)]

        if index % 5 == 0:
            current["confidence"] += 2

        rows.append(dict(current))

    return rows


def generate_random_data(row_count):
    rows = []

    colours = [
        "red", "gold", "magenta", "lime", "orange",
        "white", "purple", "cyan", "pink", "yellow"
    ]

    random.seed(23)

    for _ in range(row_count):
        rows.append({
            "x": random.randint(0, 9999),
            "y": random.randint(0, 9999),
            "size": random.randint(10, 500),
            "colour": random.choice(colours)
        })

    return rows


def calculate_savings(raw_size, best_size):
    saved = raw_size - best_size

    if raw_size == 0:
        saved_percentage = 0
    else:
        saved_percentage = (saved / raw_size) * 100

    if best_size == 0:
        ratio = None
    else:
        ratio = raw_size / best_size

    return saved, ratio, saved_percentage


def run_test_suite():
    os.makedirs("reports", exist_ok=True)

    datasets = [
        {
            "name": "rule_based_branch_data",
            "description": "Highly rule-governed evolution.",
            "rows": generate_rule_based_data(100)
        },
        {
            "name": "transform_based_document_state",
            "description": "Small evolving changes, less cleanly rule-based.",
            "rows": generate_transform_based_data(100)
        },
        {
            "name": "random_noise_data",
            "description": "Random/noisy data where PRMR should avoid fake rules.",
            "rows": generate_random_data(100)
        }
    ]

    results = []

    for dataset in datasets:
        choice = choose_storage_mode(dataset["rows"])

        saved, ratio, percentage = calculate_savings(
            choice["raw_size"],
            choice["best_size"]
        )

        result = {
            "dataset": dataset["name"],
            "description": dataset["description"],
            "row_count": choice["row_count"],
            "raw_size": choice["raw_size"],
            "transform_size": choice["transform_size"],
            "rule_possible": choice["rule_possible"],
            "rule_size": choice["rule_size"],
            "rule_failed_field": choice["rule_failed_field"],
            "rule_failure_reason": choice["rule_failure_reason"],
            "best_mode": choice["best_mode"],
            "best_size": choice["best_size"],
            "saved_bytes": saved,
            "compression_ratio": ratio,
            "saved_percentage": percentage
        }

        results.append(result)

    with open("reports/auto_storage_mode_v024.json", "w", encoding="utf-8") as file:
        json.dump(results, file, indent=4)

    return results


results = run_test_suite()

print("PRMR ANTI-OVERFIT AUTO STORAGE MODE V0.24")
print("-----------------------------------------")

for result in results:
    print("\nDataset:", result["dataset"])
    print("Description:", result["description"])
    print("Rows:", result["row_count"])

    print("Raw size:", result["raw_size"])
    print("Transform size:", result["transform_size"])
    print("Rule possible:", result["rule_possible"])
    print("Rule size:", result["rule_size"])

    if not result["rule_possible"]:
        print("Rule failed field:", result["rule_failed_field"])
        print("Rule failure reason:", result["rule_failure_reason"])

    print("Best mode:", result["best_mode"])
    print("Best size:", result["best_size"])
    print("Saved bytes:", result["saved_bytes"])

    if result["compression_ratio"] is not None:
        print("Compression ratio:", round(result["compression_ratio"], 2), "x")

    print("Saved percentage:", round(result["saved_percentage"], 2), "%")

print("\nREPORT CREATED:")
print("reports/auto_storage_mode_v024.json")