import json
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from prmr import PRMRMemoryCore
from prmr.reports import build_public_report, build_private_report


def build_realistic_memory_events():
    """
    Manually written continuity/product events.

    This is not generated formula data.
    This is a reality check for product-style memory records.
    """

    return [
        {
            "event_id": 1,
            "project": "PRMR Memory Core",
            "layer": "theory_to_product",
            "version": "V0.21",
            "state": "rule compression benchmark completed",
            "decision": "treat rule compression as promising but controlled",
            "protection_level": "private",
            "public_safe": "Rule-governed symbolic tests showed strong compression with verified reconstruction."
        },
        {
            "event_id": 2,
            "project": "PRMR Memory Core",
            "layer": "prototype",
            "version": "V0.22",
            "state": "rule discovery completed",
            "decision": "detect simple linear and cycle rules from examples",
            "protection_level": "private",
            "public_safe": "The prototype can identify simple recurring structure in controlled tests."
        },
        {
            "event_id": 3,
            "project": "PRMR Memory Core",
            "layer": "prototype",
            "version": "V0.23",
            "state": "auto storage mode created",
            "decision": "compare raw, transform, and rule storage modes",
            "protection_level": "private",
            "public_safe": "The system can select an efficient memory strategy based on data structure."
        },
        {
            "event_id": 4,
            "project": "PRMR Memory Core",
            "layer": "guardrail",
            "version": "V0.24",
            "state": "anti-overfit mode added",
            "decision": "reject fake rules on noisy data",
            "protection_level": "private",
            "public_safe": "The system avoids forcing low-quality compression on noisy data."
        },
        {
            "event_id": 5,
            "project": "PRMR Memory Core",
            "layer": "policy",
            "version": "V0.25",
            "state": "production storage policy added",
            "decision": "only use PRMR compression when savings exceed threshold",
            "protection_level": "private",
            "public_safe": "The system applies a usefulness threshold before compressing."
        },
        {
            "event_id": 6,
            "project": "PRMR Memory Core",
            "layer": "protected_demo",
            "version": "V0.26",
            "state": "public/private report wrapper created",
            "decision": "show outcomes publicly but protect internals",
            "protection_level": "private",
            "public_safe": "Public-safe reports show results without exposing protected mechanisms."
        },
        {
            "event_id": 7,
            "project": "PRMR Memory Core",
            "layer": "verification",
            "version": "V0.27",
            "state": "unified reconstruction verification completed",
            "decision": "compress, reconstruct, verify, then report",
            "protection_level": "private",
            "public_safe": "All reconstructions were verified in the unified demo."
        },
        {
            "event_id": 8,
            "project": "PRMR Memory Core",
            "layer": "engine",
            "version": "V0.28",
            "state": "clean reusable engine class created",
            "decision": "wrap core behaviour in PRMRMemoryCore",
            "protection_level": "private",
            "public_safe": "The prototype now exposes a reusable local engine interface."
        },
        {
            "event_id": 9,
            "project": "PRMR Memory Core",
            "layer": "cli",
            "version": "V0.29",
            "state": "command line runner completed",
            "decision": "allow input JSON files to run through the engine",
            "protection_level": "private",
            "public_safe": "The engine can now be called through a local CLI command."
        },
        {
            "event_id": 10,
            "project": "PRMR Memory Core",
            "layer": "strategy",
            "version": "V0.29.5",
            "state": "reality check test added",
            "decision": "test manually written product memory events before API server",
            "protection_level": "private",
            "public_safe": "The project is testing manually written memory events before moving to API infrastructure."
        },
        {
            "event_id": 11,
            "project": "PRMR Memory Core",
            "layer": "product_positioning",
            "version": "V0.29.5",
            "state": "model agnostic product direction confirmed",
            "decision": "core remains deterministic and not an LLM",
            "protection_level": "private",
            "public_safe": "PRMR Memory Core is model-agnostic continuity infrastructure."
        },
        {
            "event_id": 12,
            "project": "PRMR Memory Core",
            "layer": "company_architecture",
            "version": "V0.29.5",
            "state": "Afternum Industries product hierarchy clarified",
            "decision": "PRMR Memory Core is first public blade before Goliath, EION, and VANTA",
            "protection_level": "private",
            "public_safe": "Afternum Industries is building continuity infrastructure, starting with PRMR Memory Core."
        }
    ]


def run_reality_check():
    os.makedirs("reports", exist_ok=True)
    os.makedirs("reports/v0295", exist_ok=True)

    rows = build_realistic_memory_events()

    datasets = [
        {
            "name": "manual_product_memory_events",
            "description": "Manually written PRMR Memory Core continuity/product events used as a reality check before local API server development.",
            "rows": rows
        }
    ]

    engine = PRMRMemoryCore()
    engine_run = engine.run(datasets)

    public_report = build_public_report(engine_run)
    private_report = build_private_report(engine_run)

    public_report["version"] = "0.29.5"
    private_report["version"] = "0.29.5"

    public_report["report_type"] = "public_safe_reality_check"
    private_report["report_type"] = "private_internal_reality_check"

    with open("reports/v0295/public_reality_check_v0295.json", "w", encoding="utf-8") as file:
        json.dump(public_report, file, indent=4)

    with open("reports/v0295/private_internal_reality_check_v0295.json", "w", encoding="utf-8") as file:
        json.dump(private_report, file, indent=4)

    with open("reports/v0295/manual_memory_events_input_v0295.json", "w", encoding="utf-8") as file:
        json.dump(rows, file, indent=4)

    return public_report, private_report


public_report, private_report = run_reality_check()

print("PRMR MEMORY CORE REALITY CHECK V0.29.5")
print("--------------------------------------")

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
print("reports/v0295/public_reality_check_v0295.json")
print("reports/v0295/private_internal_reality_check_v0295.json")
print("reports/v0295/manual_memory_events_input_v0295.json")

print("\nIMPORTANT:")
print("Public reality check report is safe to show.")
print("Private internal reality check report is NOT safe to publish.")
print("Manual memory events input should be treated carefully if it contains strategic/private context.")
