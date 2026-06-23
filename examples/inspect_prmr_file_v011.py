import json
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from prmr_memory import PRMRTextMemory
from prmr_memory import PRMRImageMemory
from prmr_memory import PRMRVideoMemory


def load_raw_prmr_file(filename):
    with open(filename, "r", encoding="utf-8") as file:
        return json.load(file)


def inspect_text_memory(filename):
    memory = PRMRTextMemory.load(filename)

    report = {
        "file": filename,
        "type": "Text Memory",
        "origin_preview": memory.origin_text[:100],
        "transformation_count": len(memory.transformations),
        "reconstructed_preview": memory.reconstruct()[:200],
        "storage_size": memory.storage_size()
    }

    return report


def inspect_image_memory(filename):
    memory = PRMRImageMemory.load(filename)

    report = {
        "file": filename,
        "type": "Image Memory",
        "canvas": {
            "width": memory.canvas_width,
            "height": memory.canvas_height
        },
        "origin_object_count": len(memory.origin_objects),
        "transformation_count": len(memory.transformations),
        "lineage": memory.why(),
        "storage_size": memory.storage_size()
    }

    return report


def inspect_video_memory(filename):
    memory = PRMRVideoMemory.load(filename)

    report = {
        "file": filename,
        "type": "Video Memory",
        "canvas": {
            "width": memory.canvas_width,
            "height": memory.canvas_height
        },
        "total_frames": memory.total_frames,
        "origin_object_count": len(memory.origin_objects),
        "transformation_count": len(memory.transformations),
        "lineage": memory.why(),
        "storage_size": memory.storage_size()
    }

    return report


def inspect_prmr_file(filename):
    raw_data = load_raw_prmr_file(filename)

    memory_type = raw_data.get("type")

    if memory_type == "PRMRTextMemory":
        return inspect_text_memory(filename)

    if memory_type == "PRMRImageMemory":
        return inspect_image_memory(filename)

    if memory_type == "PRMRVideoMemory":
        return inspect_video_memory(filename)

    return {
        "file": filename,
        "type": "Unknown PRMR Memory",
        "error": "This file type is not recognised by the inspector."
    }


def print_report(report):
    print("\nPRMR FILE INSPECTION REPORT")
    print("---------------------------")

    print("\nFile:")
    print(report["file"])

    print("\nType:")
    print(report["type"])

    if "origin_preview" in report:
        print("\nOrigin Preview:")
        print(report["origin_preview"])

    if "reconstructed_preview" in report:
        print("\nReconstructed Preview:")
        print(report["reconstructed_preview"])

    if "canvas" in report:
        print("\nCanvas:")
        print(report["canvas"])

    if "total_frames" in report:
        print("\nTotal Frames:")
        print(report["total_frames"])

    if "origin_object_count" in report:
        print("\nOrigin Object Count:")
        print(report["origin_object_count"])

    if "transformation_count" in report:
        print("\nTransformation Count:")
        print(report["transformation_count"])

    if "storage_size" in report:
        print("\nPRMR Storage Size:")
        print(report["storage_size"])

    if "lineage" in report:
        print("\nLineage:")
        for item in report["lineage"]:
            print("-", item)

    if "error" in report:
        print("\nError:")
        print(report["error"])


# -------------------------
# TEST INSPECTIONS
# -------------------------

files_to_inspect = [
    "reports/text_memory_v010.prmr.json",
    "reports/image_memory_v010.prmr.json",
    "reports/video_memory_v010.prmr.json"
]

all_reports = []

for filename in files_to_inspect:
    report = inspect_prmr_file(filename)
    all_reports.append(report)
    print_report(report)


with open("reports/prmr_inspection_report_v011.json", "w", encoding="utf-8") as file:
    json.dump(all_reports, file, indent=4)

print("\nFULL INSPECTION REPORT SAVED:")
print("reports/prmr_inspection_report_v011.json")