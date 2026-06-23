# PRMR UNIFIED MEMORY LAB V0.08
# Goal:
# Combine Core + Text + Image + Video experiments into one report.
#
# This creates:
# 1. A core causal memory test
# 2. A text transformation benchmark
# 3. An image transformation benchmark
# 4. A video transformation benchmark
# 5. A JSON report with all results
#
# Positioning:
# PRMR Memory represents information as:
# Origin + Transformation + Lineage + Reconstruction


import json
from datetime import datetime


# -------------------------
# CORE MEMORY TEST
# -------------------------

class PRMRCoreMemory:
    def __init__(self):
        self.states = {}
        self.transitions = []
        self.branches = []

    def add_state(self, key, data):
        self.states[key] = data

    def add_transition(self, from_state, to_state, rule):
        self.transitions.append({
            "from": from_state,
            "to": to_state,
            "rule": rule
        })

    def add_branch(self, from_state, condition, to_state, rule):
        self.branches.append({
            "from": from_state,
            "condition": condition,
            "to": to_state,
            "rule": rule
        })

    def find_cause(self, target_state):
        for branch in self.branches:
            if branch["to"] == target_state:
                return {
                    "type": "branch",
                    "from": branch["from"],
                    "to": branch["to"],
                    "condition": branch["condition"],
                    "rule": branch["rule"]
                }

        for transition in self.transitions:
            if transition["to"] == target_state:
                return {
                    "type": "transition",
                    "from": transition["from"],
                    "to": transition["to"],
                    "rule": transition["rule"]
                }

        return None

    def why(self, target_state):
        explanation = []
        current = target_state

        while True:
            cause = self.find_cause(current)

            if cause is None:
                explanation.append(f"{current} is an origin state.")
                break

            if cause["type"] == "branch":
                explanation.append(
                    f"{current} exists because {cause['from']} branched under condition {cause['condition']}."
                )
                explanation.append(f"Rule: {cause['rule']}")

            elif cause["type"] == "transition":
                explanation.append(
                    f"{current} exists because {cause['from']} became {cause['to']}."
                )
                explanation.append(f"Rule: {cause['rule']}")

            current = cause["from"]

        return explanation

    def reconstruct(self, target_state):
        path = []
        current = target_state

        while True:
            cause = self.find_cause(current)

            if cause is None:
                path.append({
                    "type": "origin",
                    "state": current
                })
                break

            path.append(cause)
            current = cause["from"]

        path.reverse()

        steps = []
        current_state = None

        for step in path:
            if step["type"] == "origin":
                current_state = step["state"]
                steps.append(f"Origin found: {current_state}")

            elif step["type"] == "transition":
                current_state = step["to"]
                steps.append(
                    f"Apply transition: {step['from']} → {step['to']} because {step['rule']}"
                )

            elif step["type"] == "branch":
                current_state = step["to"]
                steps.append(
                    f"Apply branch: {step['from']} → {step['to']} under condition {step['condition']} because {step['rule']}"
                )

        steps.append(f"Final reconstructed state: {current_state}")

        return steps


def run_core_test():
    memory = PRMRCoreMemory()

    memory.add_state("A", "Origin")
    memory.add_state("B", "Expansion")
    memory.add_state("C", "Stabilisation")
    memory.add_state("D", "Branch outcome")

    memory.add_transition("A", "B", "origin expands")
    memory.add_transition("B", "C", "expansion stabilises")
    memory.add_branch("C", "X", "D", "condition X activates D pathway")

    why_d = memory.why("D")
    reconstruction_d = memory.reconstruct("D")

    return {
        "test_name": "Core Causal Memory",
        "target_state": "D",
        "why": why_d,
        "reconstruction": reconstruction_d,
        "passed": reconstruction_d[-1] == "Final reconstructed state: D"
    }


# -------------------------
# TEXT MEMORY TEST
# -------------------------

class PRMRTextMemory:
    def __init__(self, origin_text):
        self.origin_text = origin_text
        self.transformations = []

    def add_text(self, text_to_add):
        self.transformations.append({
            "t": "add",
            "v": text_to_add
        })

    def replace_text(self, old_text, new_text):
        self.transformations.append({
            "t": "replace",
            "old": old_text,
            "new": new_text
        })

    def reconstruct(self):
        current_text = self.origin_text

        for transformation in self.transformations:
            if transformation["t"] == "add":
                current_text += transformation["v"]

            elif transformation["t"] == "replace":
                current_text = current_text.replace(
                    transformation["old"],
                    transformation["new"]
                )

        return current_text

    def storage_size(self):
        data = {
            "origin": self.origin_text,
            "transformations": self.transformations
        }

        return len(json.dumps(data, separators=(",", ":")))


def run_text_test():
    origin = """
PRMR Memory Core is a system for storing information differently.
It does not only store the final state.
It stores the origin, the transformation path, and the lineage of change.
"""

    versions = []

    v1 = origin
    versions.append(v1)

    v2 = v1.replace(
        "storing information differently",
        "representing information through transformation"
    )
    versions.append(v2)

    v3 = v2 + "\nIt asks how information became what it is."
    versions.append(v3)

    v4 = v3 + "\nThis creates memory with causality instead of flat storage."
    versions.append(v4)

    v5 = v4.replace(
        "flat storage",
        "snapshot-only storage"
    )
    versions.append(v5)

    v6 = v5 + "\nThe long-term goal is to test text, images, video, and AI memory."
    versions.append(v6)

    memory = PRMRTextMemory(origin)

    memory.replace_text(
        "storing information differently",
        "representing information through transformation"
    )

    memory.add_text(
        "\nIt asks how information became what it is."
    )

    memory.add_text(
        "\nThis creates memory with causality instead of flat storage."
    )

    memory.replace_text(
        "flat storage",
        "snapshot-only storage"
    )

    memory.add_text(
        "\nThe long-term goal is to test text, images, video, and AI memory."
    )

    normal_size = sum(len(version) for version in versions)
    prmr_size = memory.storage_size()
    final_normal = versions[-1]
    final_prmr = memory.reconstruct()

    return {
        "test_name": "Text Transformation Memory",
        "normal_storage_size": normal_size,
        "prmr_storage_size": prmr_size,
        "difference": normal_size - prmr_size,
        "reconstruction_match": final_normal == final_prmr,
        "passed": final_normal == final_prmr
    }


# -------------------------
# IMAGE MEMORY TEST
# -------------------------

class PRMRImageMemory:
    def __init__(self, canvas_width, canvas_height):
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        self.origin_objects = {}
        self.transformations = []
        self.lineage = []

    def add_origin_circle(self, object_id, x, y, radius, colour):
        self.origin_objects[object_id] = {
            "type": "circle",
            "x": x,
            "y": y,
            "radius": radius,
            "colour": colour
        }

        self.lineage.append(
            f"Origin object '{object_id}' created."
        )

    def move_object(self, object_id, dx, dy):
        self.transformations.append({
            "t": "move",
            "id": object_id,
            "dx": dx,
            "dy": dy
        })

    def change_colour(self, object_id, colour):
        self.transformations.append({
            "t": "colour",
            "id": object_id,
            "colour": colour
        })

    def resize_object(self, object_id, radius):
        self.transformations.append({
            "t": "resize",
            "id": object_id,
            "radius": radius
        })

    def reconstruct_objects(self):
        objects = json.loads(json.dumps(self.origin_objects))

        for transformation in self.transformations:
            object_id = transformation["id"]

            if transformation["t"] == "move":
                objects[object_id]["x"] += transformation["dx"]
                objects[object_id]["y"] += transformation["dy"]

            elif transformation["t"] == "colour":
                objects[object_id]["colour"] = transformation["colour"]

            elif transformation["t"] == "resize":
                objects[object_id]["radius"] = transformation["radius"]

        return objects

    def render_svg(self, objects):
        svg = ""
        svg += f'<svg width="{self.canvas_width}" height="{self.canvas_height}" xmlns="http://www.w3.org/2000/svg">\n'
        svg += '<rect width="100%" height="100%" fill="black"/>\n'

        for object_id, obj in objects.items():
            svg += (
                f'<circle id="{object_id}" '
                f'cx="{obj["x"]}" '
                f'cy="{obj["y"]}" '
                f'r="{obj["radius"]}" '
                f'fill="{obj["colour"]}" />\n'
            )

        svg += "</svg>"

        return svg

    def reconstruct_svg(self):
        return self.render_svg(self.reconstruct_objects())

    def storage_size(self):
        data = {
            "canvas": {
                "width": self.canvas_width,
                "height": self.canvas_height
            },
            "origin_objects": self.origin_objects,
            "transformations": self.transformations
        }

        return len(json.dumps(data, separators=(",", ":")))


def run_image_test():
    memory = PRMRImageMemory(500, 500)

    memory.add_origin_circle("orb", 120, 250, 40, "cyan")

    origin_svg = memory.render_svg(memory.origin_objects)

    normal_versions = []

    normal_versions.append(origin_svg)

    normal_versions.append(
        PRMRImageMemory(500, 500).render_svg({
            "orb": {
                "type": "circle",
                "x": 220,
                "y": 250,
                "radius": 40,
                "colour": "cyan"
            }
        })
    )

    normal_versions.append(
        PRMRImageMemory(500, 500).render_svg({
            "orb": {
                "type": "circle",
                "x": 220,
                "y": 250,
                "radius": 40,
                "colour": "magenta"
            }
        })
    )

    normal_versions.append(
        PRMRImageMemory(500, 500).render_svg({
            "orb": {
                "type": "circle",
                "x": 220,
                "y": 330,
                "radius": 70,
                "colour": "magenta"
            }
        })
    )

    memory.move_object("orb", 100, 0)
    memory.change_colour("orb", "magenta")
    memory.resize_object("orb", 70)
    memory.move_object("orb", 0, 80)

    final_normal = normal_versions[-1]
    final_prmr = memory.reconstruct_svg()

    return {
        "test_name": "Image Transformation Memory",
        "normal_storage_size": sum(len(version) for version in normal_versions),
        "prmr_storage_size": memory.storage_size(),
        "difference": sum(len(version) for version in normal_versions) - memory.storage_size(),
        "reconstruction_match": final_normal == final_prmr,
        "passed": final_normal == final_prmr
    }


# -------------------------
# VIDEO MEMORY TEST
# -------------------------

class PRMRVideoMemory:
    def __init__(self, canvas_width, canvas_height, total_frames):
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        self.total_frames = total_frames
        self.origin_objects = {}
        self.transformations = []

    def add_origin_circle(self, object_id, x, y, radius, colour):
        self.origin_objects[object_id] = {
            "type": "circle",
            "x": x,
            "y": y,
            "radius": radius,
            "colour": colour
        }

    def add_motion_rule(self, object_id, start_frame, end_frame, dx_per_frame, dy_per_frame):
        self.transformations.append({
            "t": "motion",
            "id": object_id,
            "start": start_frame,
            "end": end_frame,
            "dx": dx_per_frame,
            "dy": dy_per_frame
        })

    def add_colour_change_rule(self, object_id, frame, colour):
        self.transformations.append({
            "t": "colour_at_frame",
            "id": object_id,
            "frame": frame,
            "colour": colour
        })

    def add_resize_rule(self, object_id, frame, radius):
        self.transformations.append({
            "t": "resize_at_frame",
            "id": object_id,
            "frame": frame,
            "radius": radius
        })

    def reconstruct_frame_objects(self, frame_number):
        objects = json.loads(json.dumps(self.origin_objects))

        for transformation in self.transformations:
            object_id = transformation["id"]

            if transformation["t"] == "motion":
                if frame_number >= transformation["start"]:
                    active_frame = min(frame_number, transformation["end"])
                    frames_elapsed = active_frame - transformation["start"]

                    objects[object_id]["x"] += transformation["dx"] * frames_elapsed
                    objects[object_id]["y"] += transformation["dy"] * frames_elapsed

            elif transformation["t"] == "colour_at_frame":
                if frame_number >= transformation["frame"]:
                    objects[object_id]["colour"] = transformation["colour"]

            elif transformation["t"] == "resize_at_frame":
                if frame_number >= transformation["frame"]:
                    objects[object_id]["radius"] = transformation["radius"]

        return objects

    def render_svg_frame(self, objects, frame_number):
        svg = ""
        svg += f'<svg width="{self.canvas_width}" height="{self.canvas_height}" xmlns="http://www.w3.org/2000/svg">\n'
        svg += '<rect width="100%" height="100%" fill="black"/>\n'
        svg += f'<text x="20" y="30" fill="white" font-size="20">Frame {frame_number}</text>\n'

        for object_id, obj in objects.items():
            svg += (
                f'<circle id="{object_id}" '
                f'cx="{obj["x"]}" '
                f'cy="{obj["y"]}" '
                f'r="{obj["radius"]}" '
                f'fill="{obj["colour"]}" />\n'
            )

        svg += "</svg>"

        return svg

    def reconstruct_all_frames(self):
        frames = []

        for frame_number in range(self.total_frames):
            objects = self.reconstruct_frame_objects(frame_number)
            frames.append(self.render_svg_frame(objects, frame_number))

        return frames

    def storage_size(self):
        data = {
            "canvas": {
                "width": self.canvas_width,
                "height": self.canvas_height
            },
            "total_frames": self.total_frames,
            "origin_objects": self.origin_objects,
            "transformations": self.transformations
        }

        return len(json.dumps(data, separators=(",", ":")))


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


# -------------------------
# RUN FULL LAB
# -------------------------

def run_full_lab():
    core_result = run_core_test()
    text_result = run_text_test()
    image_result = run_image_test()
    video_result = run_video_test()

    results = [
        core_result,
        text_result,
        image_result,
        video_result
    ]

    passed_count = sum(1 for result in results if result["passed"])

    report = {
        "project": "PRMR Memory Core",
        "version": "0.08",
        "timestamp": datetime.now().isoformat(),
        "hypothesis": "Information can be represented as origin, transformation, lineage, and reconstruction rather than only snapshot storage.",
        "tests": results,
        "summary": {
            "tests_run": len(results),
            "tests_passed": passed_count,
            "all_tests_passed": passed_count == len(results)
        }
    }

    with open("prmr_lab_report_v008.json", "w", encoding="utf-8") as file:
        json.dump(report, file, indent=4)

    return report


report = run_full_lab()

print("PRMR UNIFIED MEMORY LAB V0.08")
print("-----------------------------")

print("\nHYPOTHESIS:")
print(report["hypothesis"])

print("\nTEST RESULTS:")

for test in report["tests"]:
    print("\n" + test["test_name"])
    print("Passed:", test["passed"])

    if "normal_storage_size" in test:
        print("Normal storage:", test["normal_storage_size"])
        print("PRMR storage:", test["prmr_storage_size"])
        print("Difference:", test["difference"])
        print("Reconstruction match:", test["reconstruction_match"])

print("\nSUMMARY:")
print("Tests run:", report["summary"]["tests_run"])
print("Tests passed:", report["summary"]["tests_passed"])
print("All tests passed:", report["summary"]["all_tests_passed"])

print("\nREPORT CREATED:")
print("prmr_lab_report_v008.json")