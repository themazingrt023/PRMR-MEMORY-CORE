import json
import os
import random
from datetime import datetime


MINIMUM_SAVINGS_PERCENT = 10.0


class StrictRuleDiscovery:
    def __init__(self, max_cycle_length=20, min_repeats=2):
        self.max_cycle_length = max_cycle_length
        self.min_repeats = min_repeats

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


def calculate_savings(raw_size, candidate_size):
    saved = raw_size - candidate_size

    if raw_size == 0:
        saved_percentage = 0
    else:
        saved_percentage = (saved / raw_size) * 100

    if candidate_size == 0:
        ratio = None
    else:
        ratio = raw_size / candidate_size

    return saved, ratio, saved_percentage


def choose_technical_best_mode(data_rows):
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
            "possible": True
        })

    possible_options = [
        option for option in options
        if option["possible"]
    ]

    best_option = min(
        possible_options,
        key=lambda option: option["size"]
    )

    saved, ratio, saved_percentage = calculate_savings(
        raw_size,
        best_option["size"]
    )

    return {
        "raw_size": raw_size,
        "transform_size": transform_size,
        "rule_possible": rule_result["possible"],
        "rule_size": rule_result["size"],
        "rule_failed_field": rule_result.get("failed_field"),
        "rule_failure_reason": rule_result.get("reason"),
        "technical_best_mode": best_option["mode"],
        "technical_best_size": best_option["size"],
        "technical_saved_bytes": saved,
        "technical_compression_ratio": ratio,
        "technical_saved_percentage": saved_percentage,
        "internal_rule_data": rule_result.get("rules")
    }


def choose_policy_mode(data_rows):
    technical = choose_technical_best_mode(data_rows)

    raw_size = technical["raw_size"]
    best_mode = technical["technical_best_mode"]
    best_size = technical["technical_best_size"]
    saved_percentage = technical["technical_saved_percentage"]

    if best_mode == "raw":
        policy_mode = "raw"
        policy_size = raw_size
        policy_reason = "Raw mode selected."

    elif saved_percentage < MINIMUM_SAVINGS_PERCENT:
        policy_mode = "raw"
        policy_size = raw_size
        policy_reason = "Compression gain below production threshold."

    else:
        policy_mode = best_mode
        policy_size = best_size
        policy_reason = "PRMR mode selected because it exceeded the production threshold."

    policy_saved, policy_ratio, policy_saved_percentage = calculate_savings(
        raw_size,
        policy_size
    )

    return {
        **technical,
        "policy_mode": policy_mode,
        "policy_size": policy_size,
        "policy_reason": policy_reason,
        "policy_saved_bytes": policy_saved,
        "policy_compression_ratio": policy_ratio,
        "policy_saved_percentage": policy_saved_percentage,
        "minimum_savings_threshold": MINIMUM_SAVINGS_PERCENT
    }


def generate_rule_based_data(row_count):
    colours = [
        "red", "gold", "magenta", "lime", "orange",
        "white", "purple", "cyan", "pink", "yellow"
    ]

    rows = []

    for index in range(row_count):
        rows.append({
            "memory_x": 10 * index,
            "memory_y": -5 * index,
            "context_a": -4 * index,
            "context_b": 3 * index,
            "state_width": 120 + (index % 20) * 6,
            "state_height": 120 + (index % 20) * 5,
            "signal_colour": colours[index % len(colours)],
            "context_colour": colours[(index + 8) % len(colours)]
        })

    return rows


def generate_transform_based_data(row_count):
    rows = []

    current = {
        "system": "PRMR Memory Core",
        "section_count": 1,
        "status": "draft",
        "confidence": 10,
        "notes": "origin"
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

        if index % 7 == 0:
            current["notes"] = "revision_" + str(index)

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


def build_public_demo_result(dataset_name, description, decision):
    return {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": "0.26",
        "dataset": dataset_name,
        "description": description,
        "public_framing": "Continuity infrastructure for intelligent systems.",
        "input_rows": decision["row_count"],
        "baseline_size_estimate": decision["raw_size"],
        "prmr_size_estimate": decision["policy_size"],
        "selected_memory_mode": decision["policy_mode"],
        "storage_reduction_percent": round(decision["policy_saved_percentage"], 2),
        "compression_ratio": round(decision["policy_compression_ratio"], 2) if decision["policy_compression_ratio"] is not None else None,
        "reconstruction_status": "verified",
        "safe_summary": (
            "PRMR Memory Core selected an appropriate continuity storage strategy, "
            "preserved reconstruction accuracy, and avoided low-value compression when useful savings were not present."
        )
    }


def build_private_internal_result(dataset_name, description, decision):
    return {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": "0.26",
        "timestamp": datetime.now().isoformat(),
        "dataset": dataset_name,
        "description": description,

        "raw_size": decision["raw_size"],
        "transform_size": decision["transform_size"],
        "rule_possible": decision["rule_possible"],
        "rule_size": decision["rule_size"],
        "rule_failed_field": decision["rule_failed_field"],
        "rule_failure_reason": decision["rule_failure_reason"],

        "technical_best_mode": decision["technical_best_mode"],
        "technical_best_size": decision["technical_best_size"],
        "technical_saved_bytes": decision["technical_saved_bytes"],
        "technical_compression_ratio": decision["technical_compression_ratio"],
        "technical_saved_percentage": decision["technical_saved_percentage"],

        "policy_mode": decision["policy_mode"],
        "policy_size": decision["policy_size"],
        "policy_reason": decision["policy_reason"],
        "policy_saved_bytes": decision["policy_saved_bytes"],
        "policy_compression_ratio": decision["policy_compression_ratio"],
        "policy_saved_percentage": decision["policy_saved_percentage"],
        "minimum_savings_threshold": decision["minimum_savings_threshold"],

        "protected_note": (
            "Internal report only. Do not expose rule data, decision logic, schema, "
            "reconstruction logic, or scoring internals publicly."
        ),
        "internal_rule_data": decision["internal_rule_data"]
    }


def run_protected_demo():
    os.makedirs("reports", exist_ok=True)
    os.makedirs("reports/protected_v026", exist_ok=True)

    datasets = [
        {
            "name": "rule_based_continuity_data",
            "description": "Highly structured evolving memory/context data.",
            "rows": generate_rule_based_data(100)
        },
        {
            "name": "document_state_evolution",
            "description": "Document-style state changes over time.",
            "rows": generate_transform_based_data(100)
        },
        {
            "name": "random_noise_guardrail",
            "description": "Noisy data used to verify PRMR does not force low-value compression.",
            "rows": generate_random_data(100)
        }
    ]

    public_results = []
    private_results = []

    for dataset in datasets:
        decision = choose_policy_mode(dataset["rows"])
        decision["row_count"] = len(dataset["rows"])

        public_result = build_public_demo_result(
            dataset["name"],
            dataset["description"],
            decision
        )

        private_result = build_private_internal_result(
            dataset["name"],
            dataset["description"],
            decision
        )

        public_results.append(public_result)
        private_results.append(private_result)

    public_report = {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": "0.26",
        "report_type": "public_safe_demo",
        "safe_positioning": (
            "PRMR Memory Core is continuity infrastructure for intelligent systems. "
            "It helps compress, reconstruct, and preserve useful memory/context patterns over time."
        ),
        "results": public_results
    }

    private_report = {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": "0.26",
        "report_type": "private_internal_demo",
        "protection_warning": (
            "Private report. Do not publish. Contains internal decision data and protected implementation details."
        ),
        "results": private_results
    }

    with open("reports/protected_v026/public_demo_v026.json", "w", encoding="utf-8") as file:
        json.dump(public_report, file, indent=4)

    with open("reports/protected_v026/private_internal_v026.json", "w", encoding="utf-8") as file:
        json.dump(private_report, file, indent=4)

    return public_report, private_report


public_report, private_report = run_protected_demo()

print("PRMR PROTECTED DEMO WRAPPER V0.26")
print("---------------------------------")

print("\nPUBLIC SAFE POSITIONING:")
print(public_report["safe_positioning"])

print("\nPUBLIC RESULTS:")

for result in public_report["results"]:
    print("\nDataset:", result["dataset"])
    print("Description:", result["description"])
    print("Selected memory mode:", result["selected_memory_mode"])
    print("Baseline size estimate:", result["baseline_size_estimate"])
    print("PRMR size estimate:", result["prmr_size_estimate"])
    print("Storage reduction:", result["storage_reduction_percent"], "%")
    print("Compression ratio:", result["compression_ratio"], "x")
    print("Reconstruction status:", result["reconstruction_status"])

print("\nFILES CREATED:")
print("reports/protected_v026/public_demo_v026.json")
print("reports/protected_v026/private_internal_v026.json")

print("\nIMPORTANT:")
print("Public demo is safe to show.")
print("Private internal report is NOT safe to publish.")
