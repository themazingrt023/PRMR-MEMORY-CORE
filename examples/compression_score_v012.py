import json
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from prmr_memory import PRMRTextMemory
from prmr_memory import PRMRImageMemory
from prmr_memory import PRMRVideoMemory


def calculate_compression_score(normal_size, prmr_size):
    saved = normal_size - prmr_size

    if prmr_size == 0:
        compression_ratio = None
    else:
        compression_ratio = normal_size / prmr_size

    if normal_size == 0:
        saved_percentage = 0
    else:
        saved_percentage = (saved / normal_size) * 100

    if saved > 0:
        result = "PRMR saved storage"
    elif saved < 0:
        result = "PRMR used more storage"
    else:
        result = "PRMR matched normal storage"

    return {
        "normal_storage_size": normal_size,
        "prmr_storage_size": prmr_size,
        "saved_bytes": saved,
        "compression_ratio": compression_ratio,
        "saved_percentage": saved_percentage,
        "result": result
    }


# -------------------------
# TEXT NORMAL SNAPSHOTS
# -------------------------

def run_text_score():
    origin = "PRMR stores information."

    versions = []

    v1 = origin
    versions.append(v1)

    v2 = v1.replace("stores", "translates")
    versions.append(v2)

    v3 = v2 + " It remembers transformation."
    versions.append(v3)

    memory = PRMRTextMemory(origin)
    memory.replace_text("stores", "translates")
    memory.add_text(" It remembers transformation.")

    normal_size = sum(len(v) for v in versions)
    prmr_size = memory.storage_size()

    reconstruction_match = versions[-1] == memory.reconstruct()

    score = calculate_compression_score(normal_size, prmr_size)

    return {
        "test_name": "Text Compression Score",
        "reconstruction_match": reconstruction_match,
        **score
    }


# -------------------------
# IMAGE NORMAL SNAPSHOTS
# -------------------------

def render_circle_svg(x, y, radius, colour):
    svg = ""
    svg += '<svg width="500" height="500" xmlns="http://www.w3.org/2000/svg">\n'
    svg += '<rect width="100%" height="100%" fill="black"/>\n'
    svg += (
        f'<circle id="orb" '
        f'cx="{x}" '
        f'cy="{y}" '
        f'r="{radius}" '
        f'fill="{colour}" />\n'
    )
    svg += "</svg>"
    return svg


def run_image_score():
    normal_versions = [
        render_circle_svg(100, 250, 40, "cyan"),
        render_circle_svg(220, 250, 40, "cyan"),
        render_circle_svg(220, 250, 40, "magenta"),
        render_circle_svg(220, 250, 70, "magenta"),
    ]

    memory = PRMRImageMemory(500, 500)
    memory.add_origin_circle("orb", 100, 250, 40, "cyan")
    memory.move_object("orb", 120, 0)
    memory.change_colour("orb", "magenta")
    memory.resize_object("orb", 70)

    normal_size = sum(len(v) for v in normal_versions)
    prmr_size = memory.storage_size()

    reconstruction_match = normal_versions[-1] == memory.reconstruct_svg()

    score = calculate_compression_score(normal_size, prmr_size)

    return {
        "test_name": "Image Compression Score",
        "reconstruction_match": reconstruction_match,
        **score
    }


# -------------------------
# VIDEO NORMAL SNAPSHOTS
# -------------------------

def render_video_frame(frame_number):
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
    return svg


def run_video_score():
    normal_frames = []

    for frame_number in range(30):
        normal_frames.append(render_video_frame(frame_number))

    memory = PRMRVideoMemory(500, 500, 30)
    memory.add_origin_circle("orb", 80, 250, 35, "cyan")
    memory.add_motion_rule("orb", 0, 29, 10, 0)
    memory.add_colour_change_rule("orb", 10, "magenta")
    memory.add_resize_rule("orb", 20, 60)

    normal_size = sum(len(frame) for frame in normal_frames)
    prmr_size = memory.storage_size()

    reconstruction_match = normal_frames == memory.reconstruct_all_frames()

    score = calculate_compression_score(normal_size, prmr_size)

    return {
        "test_name": "Video Compression Score",
        "reconstruction_match": reconstruction_match,
        **score
    }


# -------------------------
# RUN ALL SCORES
# -------------------------

results = [
    run_text_score(),
    run_image_score(),
    run_video_score()
]

os.makedirs("reports", exist_ok=True)

with open("reports/prmr_compression_score_v012.json", "w", encoding="utf-8") as file:
    json.dump(results, file, indent=4)

print("PRMR COMPRESSION SCORE V0.12")
print("----------------------------")

for result in results:
    print("\n" + result["test_name"])
    print("Reconstruction match:", result["reconstruction_match"])
    print("Normal storage:", result["normal_storage_size"])
    print("PRMR storage:", result["prmr_storage_size"])
    print("Saved bytes:", result["saved_bytes"])

    if result["compression_ratio"] is not None:
        print("Compression ratio:", round(result["compression_ratio"], 2), "x")

    print("Saved percentage:", round(result["saved_percentage"], 2), "%")
    print("Result:", result["result"])

print("\nREPORT CREATED:")
print("reports/prmr_compression_score_v012.json")