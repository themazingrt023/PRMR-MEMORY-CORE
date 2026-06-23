import sys
import os
import json
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from prmr_memory import PRMRCoreMemory
from prmr_memory import PRMRTextMemory
from prmr_memory import PRMRImageMemory
from prmr_memory import PRMRVideoMemory


def run_core_test():
    memory = PRMRCoreMemory()

    memory.add_state("A", "Origin")
    memory.add_state("B", "Expansion")
    memory.add_state("C", "Stabilisation")
    memory.add_state("D", "Branch outcome")

    memory.add_transition("A", "B", "origin expands")
    memory.add_transition("B", "C", "expansion stabilises")
    memory.add_branch("C", "X", "D", "condition X activates D pathway")

    reconstruction = memory.reconstruct("D")

    return {
        "test_name": "Core Causal Memory",
        "passed": reconstruction[-1] == "Final reconstructed state: D",
        "why": memory.why("D"),
        "reconstruction": reconstruction
    }


def run_text_test():
    origin = "PRMR Memory stores information differently."

    versions = []
    v1 = origin
    versions.append(v1)

    v2 = v1.replace("stores", "translates")
    versions.append(v2)

    v3 = v2 + " It tracks transformation."
    versions.append(v3)

    v4 = v3 + " It reconstructs final meaning."
    versions.append(v4)

    memory = PRMRTextMemory(origin)
    memory.replace_text("stores", "translates")
    memory.add_text(" It tracks transformation.")
    memory.add_text(" It reconstructs final meaning.")

    normal_size = memory.normal_storage_size(versions)
    prmr_size = memory.storage_size()

    return {
        "test_name": "Text Transformation Memory",
        "normal_storage_size": normal_size,
        "prmr_storage_size": prmr_size,
        "difference": normal_size - prmr_size,
        "reconstruction_match": versions[-1] == memory.reconstruct(),
        "passed": versions[-1] == memory.reconstruct()
    }


def run_image_test():
    memory = PRMRImageMemory(500, 500)

    memory.add_origin_circle("orb", 120, 250, 40, "cyan")
    origin_svg = memory.render_svg(memory.origin_objects)

    normal_versions = [
        origin_svg,
        memory.render_svg({
            "orb": {
                "type": "circle",
                "x": 220,
                "y": 250,
                "radius": 40,
                "colour": "cyan"
            }
        }),
        memory.render_svg({
            "orb": {
                "type": "circle",
                "x": 220,
                "y": 330,
                "radius": 70,
                "colour": "magenta"
            }
        })
    ]

    memory.move_object("orb", 100, 0)
    memory.change_colour("orb", "magenta")
    memory.resize_object("orb", 70)
    memory.move_object("orb", 0, 80)

    final_prmr = memory.reconstruct_svg()

    return {
        "test_name": "Image Transformation Memory",
        "normal_storage_size": sum(len(v) for v in normal_versions),
        "prmr_storage_size": memory.storage_size(),
        "difference": sum(len(v) for v in normal_versions) - memory.storage_size(),
        "reconstruction_match": normal_versions[-1] == final_prmr,
        "passed": normal_versions[-1] == final_prmr
    }


def create_normal_video_frames():
    frames = []

    for frame_number in range(30):
        x = 80 + frame_number * 10
        y = 250
        radius = 35
        colour = "cyan"

        if frame_number >= 10:
            colour = "magenta"

        if frame_number >= 20:
            radius = 60

        svg = ""
        svg += '<svg width="500" height="500" xmlns="http://www.w3.org/2000/svg">\n'
        svg += '<rect width="100%" height="100%" fill="black"/>\n'
        svg += f'<text x="20" y="30" fill="white" font-size="20">Frame {frame_number}</text>\n'
        svg += (
            f'<circle id="orb" '
            f'cx="{x}" '
            f'cy="{y}" '
            f'r="{radius}" '
            f'fill="{colour}" />\n'
        )
        svg += "</svg>"

        frames.append(svg)

    return frames


def run_video_test():
    memory = PRMRVideoMemory(500, 500, 30)

    memory.add_origin_circle("orb", 80, 250, 35, "cyan")
    memory.add_motion_rule("orb", 0, 29, 10, 0)
    memory.add_colour_change_rule("orb", 10, "magenta")
    memory.add_resize_rule("orb", 20, 60)

    normal_frames = create_normal_video_frames()
    prmr_frames = memory.reconstruct_all_frames()

    normal_size = sum(len(frame) for frame in normal_frames)
    prmr_size = memory.storage_size()

    return {
        "test_name": "Video Transformation Memory",
        "normal_storage_size": normal_size,
        "prmr_storage_size": prmr_size,
        "difference": normal_size - prmr_size,
        "reconstruction_match": normal_frames == prmr_frames,
        "passed": normal_frames == prmr_frames
    }


def run_lab():
    results = [
        run_core_test(),
        run_text_test(),
        run_image_test(),
        run_video_test()
    ]

    passed_count = sum(1 for result in results if result["passed"])

    report = {
        "project": "PRMR Memory SDK",
        "version": "0.09",
        "timestamp": datetime.now().isoformat(),
        "hypothesis": "Information can be represented as origin, transformation, lineage, and reconstruction.",
        "results": results,
        "summary": {
            "tests_run": len(results),
            "tests_passed": passed_count,
            "all_tests_passed": passed_count == len(results)
        }
    }

    os.makedirs("reports", exist_ok=True)

    with open("reports/prmr_lab_report_v009.json", "w", encoding="utf-8") as file:
        json.dump(report, file, indent=4)

    return report


report = run_lab()

print("PRMR MEMORY SDK LAB V0.09")
print("------------------------")

for result in report["results"]:
    print("\n" + result["test_name"])
    print("Passed:", result["passed"])

    if "normal_storage_size" in result:
        print("Normal storage:", result["normal_storage_size"])
        print("PRMR storage:", result["prmr_storage_size"])
        print("Difference:", result["difference"])
        print("Reconstruction match:", result["reconstruction_match"])

print("\nSUMMARY:")
print("Tests run:", report["summary"]["tests_run"])
print("Tests passed:", report["summary"]["tests_passed"])
print("All tests passed:", report["summary"]["all_tests_passed"])

print("\nREPORT CREATED:")
print("reports/prmr_lab_report_v009.json")