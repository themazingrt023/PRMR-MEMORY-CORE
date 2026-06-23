import argparse
import json
import os
import sys
from datetime import datetime

from prmr import PRMRMemoryCore
from prmr.reports import build_public_report, build_private_report


def load_input_file(input_path):
    with open(input_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    if "datasets" not in data:
        raise ValueError("Input file must contain a 'datasets' field.")

    for dataset in data["datasets"]:
        if "name" not in dataset:
            raise ValueError("Each dataset must contain 'name'.")

        if "description" not in dataset:
            raise ValueError("Each dataset must contain 'description'.")

        if "rows" not in dataset:
            raise ValueError("Each dataset must contain 'rows'.")

        if not isinstance(dataset["rows"], list):
            raise ValueError("Dataset 'rows' must be a list.")

    return data


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)


def run_command(args):
    input_data = load_input_file(args.input_file)

    os.makedirs(args.output_dir, exist_ok=True)

    engine = PRMRMemoryCore()
    engine_run = engine.run(input_data["datasets"])

    public_report = build_public_report(engine_run)
    private_report = build_private_report(engine_run)

    public_report["version"] = "0.29"
    private_report["version"] = "0.29"

    public_report["report_type"] = "public_safe_cli_run"
    private_report["report_type"] = "private_internal_cli_run"

    public_report["source_input_file"] = args.input_file
    private_report["source_input_file"] = args.input_file

    public_report["cli_timestamp"] = datetime.now().isoformat()
    private_report["cli_timestamp"] = datetime.now().isoformat()

    public_path = os.path.join(args.output_dir, "public_cli_run_v029.json")
    private_path = os.path.join(args.output_dir, "private_internal_cli_v029.json")

    save_json(public_path, public_report)
    save_json(private_path, private_report)

    print("PRMR MEMORY CORE CLI V0.29")
    print("--------------------------")

    print("\nInput file:")
    print(args.input_file)

    print("\nPublic safe positioning:")
    print(public_report["safe_positioning"])

    print("\nAll reconstructions verified:")
    print(public_report["all_reconstructions_verified"])

    print("\nResults:")

    for result in public_report["results"]:
        print("\nDataset:", result["dataset"])
        print("Selected memory mode:", result["selected_memory_mode"])
        print("Baseline size estimate:", result["baseline_size_estimate"])
        print("PRMR size estimate:", result["prmr_size_estimate"])
        print("Storage reduction:", result["storage_reduction_percent"], "%")
        print("Compression ratio:", result["compression_ratio"], "x")
        print("Reconstruction verified:", result["reconstruction_verified"])

    print("\nFILES CREATED:")
    print(public_path)
    print(private_path)

    print("\nIMPORTANT:")
    print("Public CLI report is safe to show.")
    print("Private internal CLI report is NOT safe to publish.")

    if not public_report["all_reconstructions_verified"]:
        print("\nERROR:")
        print("One or more reconstructions failed.")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="PRMR Memory Core CLI"
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True
    )

    run_parser = subparsers.add_parser(
        "run",
        help="Run PRMR Memory Core on an input JSON file."
    )

    run_parser.add_argument(
        "input_file",
        help="Path to input JSON file."
    )

    run_parser.add_argument(
        "--output-dir",
        default="reports/v029",
        help="Directory for output reports."
    )

    run_parser.set_defaults(func=run_command)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
