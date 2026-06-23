import json
import os
import random
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from prmr import PRMRMemoryCore
from prmr.reports import build_public_report, build_private_report


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


def run_demo():
    os.makedirs("reports", exist_ok=True)
    os.makedirs("reports/v028", exist_ok=True)

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

    engine = PRMRMemoryCore()
    engine_run = engine.run(datasets)

    public_report = build_public_report(engine_run)
    private_report = build_private_report(engine_run)

    with open("reports/v028/public_engine_demo_v028.json", "w", encoding="utf-8") as file:
        json.dump(public_report, file, indent=4)

    with open("reports/v028/private_internal_engine_v028.json", "w", encoding="utf-8") as file:
        json.dump(private_report, file, indent=4)

    return public_report, private_report


public_report, private_report = run_demo()

print("PRMR MEMORY CORE CLEAN ENGINE V0.28")
print("-----------------------------------")

print("\nPUBLIC SAFE POSITIONING:")
print(public_report["safe_positioning"])

print("\nALL RECONSTRUCTIONS VERIFIED:")
print(public_report["all_reconstructions_verified"])

print("\nPUBLIC RESULTS:")

for result in public_report["results"]:
    print("\nDataset:", result["dataset"])
    print("Description:", result["description"])
    print("Selected memory mode:", result["selected_memory_mode"])
    print("Baseline size estimate:", result["baseline_size_estimate"])
    print("PRMR size estimate:", result["prmr_size_estimate"])
    print("Storage reduction:", result["storage_reduction_percent"], "%")
    print("Compression ratio:", result["compression_ratio"], "x")
    print("Reconstruction verified:", result["reconstruction_verified"])

print("\nFILES CREATED:")
print("reports/v028/public_engine_demo_v028.json")
print("reports/v028/private_internal_engine_v028.json")

print("\nIMPORTANT:")
print("Public engine demo is safe to show.")
print("Private internal report is NOT safe to publish.")
print("No standalone compressed .prmr files were exported in this version.")
