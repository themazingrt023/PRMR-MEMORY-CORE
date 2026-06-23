import json
import os
import random


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


os.makedirs("inputs", exist_ok=True)

input_data = {
    "company": "Afternum Industries",
    "product": "PRMR Memory Core",
    "version": "0.29",
    "datasets": [
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
}

with open("inputs/demo_input_v029.json", "w", encoding="utf-8") as file:
    json.dump(input_data, file, indent=4)

print("V0.29 input file created:")
print("inputs/demo_input_v029.json")

