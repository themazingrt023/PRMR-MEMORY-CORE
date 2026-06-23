import json
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class PRMRMultiObjectVideoMemory:
    def __init__(self, canvas_width, canvas_height, total_frames):
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        self.total_frames = total_frames
        self.origin_objects = {}
        self.transformations = []
        self.lineage = []

    def add_circle(self, object_id, x, y, radius, colour):
        self.origin_objects[object_id] = {
            "type": "circle",
            "x": x,
            "y": y,
            "radius": radius,
            "colour": colour
        }

        self.lineage.append(
            f"Origin circle '{object_id}' created at ({x}, {y}), radius {radius}, colour {colour}."
        )

    def add_rect(self, object_id, x, y, width, height, colour):
        self.origin_objects[object_id] = {
            "type": "rect",
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "colour": colour
        }

        self.lineage.append(
            f"Origin rectangle '{object_id}' created at ({x}, {y}), size {width}x{height}, colour {colour}."
        )

    def add_motion_rule(self, object_id, start_frame, end_frame, dx_per_frame, dy_per_frame):
        self.transformations.append({
            "t": "motion",
            "id": object_id,
            "start": start_frame,
            "end": end_frame,
            "dx": dx_per_frame,
            "dy": dy_per_frame
        })

        self.lineage.append(
            f"'{object_id}' moves from frame {start_frame} to {end_frame} by dx={dx_per_frame}, dy={dy_per_frame} per frame."
        )

    def add_colour_rule(self, object_id, frame, colour):
        self.transformations.append({
            "t": "colour_at_frame",
            "id": object_id,
            "frame": frame,
            "colour": colour
        })

        self.lineage.append(
            f"'{object_id}' changes colour to {colour} at frame {frame}."
        )

    def add_circle_resize_rule(self, object_id, frame, radius):
        self.transformations.append({
            "t": "circle_resize_at_frame",
            "id": object_id,
            "frame": frame,
            "radius": radius
        })

        self.lineage.append(
            f"Circle '{object_id}' resizes to radius {radius} at frame {frame}."
        )

    def add_rect_resize_rule(self, object_id, frame, width, height):
        self.transformations.append({
            "t": "rect_resize_at_frame",
            "id": object_id,
            "frame": frame,
            "width": width,
            "height": height
        })

        self.lineage.append(
            f"Rectangle '{object_id}' resizes to {width}x{height} at frame {frame}."
        )

    def reconstruct_frame_objects(self, frame_number):
        objects = json.loads(json.dumps(self.origin_objects))

        for transformation in self.transformations:
            object_id = transformation["id"]

            if object_id not in objects:
                continue

            obj = objects[object_id]

            if transformation["t"] == "motion":
                if frame_number >= transformation["start"]:
                    active_frame = min(frame_number, transformation["end"])
                    frames_elapsed = active_frame - transformation["start"]

                    obj["x"] += transformation["dx"] * frames_elapsed
                    obj["y"] += transformation["dy"] * frames_elapsed

            elif transformation["t"] == "colour_at_frame":
                if frame_number >= transformation["frame"]:
                    obj["colour"] = transformation["colour"]

            elif transformation["t"] == "circle_resize_at_frame":
                if frame_number >= transformation["frame"] and obj["type"] == "circle":
                    obj["radius"] = transformation["radius"]

            elif transformation["t"] == "rect_resize_at_frame":
                if frame_number >= transformation["frame"] and obj["type"] == "rect":
                    obj["width"] = transformation["width"]
                    obj["height"] = transformation["height"]

        return objects

    def render_svg_frame(self, objects, frame_number):
        svg = ""
        svg += f'<svg width="{self.canvas_width}" height="{self.canvas_height}" xmlns="http://www.w3.org/2000/svg">\n'
        svg += '<rect width="100%" height="100%" fill="black"/>\n'
        svg += f'<text x="20" y="30" fill="white" font-size="20">PRMR Multi-Object Video V0.16 — Frame {frame_number}</text>\n'

        for object_id, obj in objects.items():
            if obj["type"] == "circle":
                svg += (
                    f'<circle id="{object_id}" '
                    f'cx="{obj["x"]}" '
                    f'cy="{obj["y"]}" '
                    f'r="{obj["radius"]}" '
                    f'fill="{obj["colour"]}" />\n'
                )

            elif obj["type"] == "rect":
                svg += (
                    f'<rect id="{object_id}" '
                    f'x="{obj["x"]}" '
                    f'y="{obj["y"]}" '
                    f'width="{obj["width"]}" '
                    f'height="{obj["height"]}" '
                    f'fill="{obj["colour"]}" />\n'
                )

        svg += "</svg>"
        return svg

    def reconstruct_all_frames(self):
        frames = []

        for frame_number in range(self.total_frames):
            objects = self.reconstruct_frame_objects(frame_number)
            frame_svg = self.render_svg_frame(objects, frame_number)
            frames.append(frame_svg)

        return frames

    def storage_size(self):
        data = {
            "type": "PRMRMultiObjectVideoMemory",
            "version": "0.16",
            "canvas_width": self.canvas_width,
            "canvas_height": self.canvas_height,
            "total_frames": self.total_frames,
            "origin_objects": self.origin_objects,
            "transformations": self.transformations,
            "lineage": self.lineage
        }

        return len(json.dumps(data, separators=(",", ":")))

    def why(self):
        return self.lineage


def render_normal_frame(frame_number):
    canvas_width = 700
    canvas_height = 500

    # Origin values
    orb_x = 80
    orb_y = 250
    orb_radius = 35
    orb_colour = "cyan"

    sun_x = 560
    sun_y = 110
    sun_radius = 50
    sun_colour = "gold"

    portal_x = 350
    portal_y = 250
    portal_radius = 70
    portal_colour = "purple"

    block_x = 280
    block_y = 380
    block_width = 120
    block_height = 50
    block_colour = "gray"

    # Motion rules
    orb_x += frame_number * 8

    if frame_number >= 5:
        portal_colour = "magenta"

    if frame_number >= 10:
        sun_radius = 80

    if frame_number >= 15:
        block_x += -3 * (frame_number - 15)
        block_y += -2 * (frame_number - 15)

    if frame_number >= 20:
        block_width = 180
        block_height = 65
        block_colour = "white"

    if frame_number >= 25:
        orb_y += -5 * (frame_number - 25)

    svg = ""
    svg += f'<svg width="{canvas_width}" height="{canvas_height}" xmlns="http://www.w3.org/2000/svg">\n'
    svg += '<rect width="100%" height="100%" fill="black"/>\n'
    svg += f'<text x="20" y="30" fill="white" font-size="20">PRMR Multi-Object Video V0.16 — Frame {frame_number}</text>\n'

    svg += f'<circle id="orb" cx="{orb_x}" cy="{orb_y}" r="{orb_radius}" fill="{orb_colour}" />\n'
    svg += f'<circle id="sun" cx="{sun_x}" cy="{sun_y}" r="{sun_radius}" fill="{sun_colour}" />\n'
    svg += f'<circle id="portal" cx="{portal_x}" cy="{portal_y}" r="{portal_radius}" fill="{portal_colour}" />\n'
    svg += f'<rect id="block" x="{block_x}" y="{block_y}" width="{block_width}" height="{block_height}" fill="{block_colour}" />\n'

    svg += "</svg>"
    return svg


def create_normal_frames(total_frames):
    frames = []

    for frame_number in range(total_frames):
        frames.append(render_normal_frame(frame_number))

    return frames


def calculate_score(normal_size, prmr_size):
    saved = normal_size - prmr_size

    if prmr_size == 0:
        ratio = None
    else:
        ratio = normal_size / prmr_size

    if normal_size == 0:
        percentage = 0
    else:
        percentage = (saved / normal_size) * 100

    return saved, ratio, percentage


def save_frames(frames, folder, prefix):
    os.makedirs(folder, exist_ok=True)

    for index, frame in enumerate(frames):
        filename = os.path.join(folder, f"{prefix}_{index:03d}.svg")

        with open(filename, "w", encoding="utf-8") as file:
            file.write(frame)


os.makedirs("reports", exist_ok=True)
os.makedirs("reports/v016_frames", exist_ok=True)

total_frames = 40

memory = PRMRMultiObjectVideoMemory(700, 500, total_frames)

# Origin scene
memory.add_circle("orb", 80, 250, 35, "cyan")
memory.add_circle("sun", 560, 110, 50, "gold")
memory.add_circle("portal", 350, 250, 70, "purple")
memory.add_rect("block", 280, 380, 120, 50, "gray")

# PRMR time-based transformations
memory.add_motion_rule("orb", 0, 39, 8, 0)
memory.add_colour_rule("portal", 5, "magenta")
memory.add_circle_resize_rule("sun", 10, 80)
memory.add_motion_rule("block", 15, 39, -3, -2)
memory.add_rect_resize_rule("block", 20, 180, 65)
memory.add_colour_rule("block", 20, "white")
memory.add_motion_rule("orb", 25, 39, 0, -5)

prmr_frames = memory.reconstruct_all_frames()
normal_frames = create_normal_frames(total_frames)

save_frames(prmr_frames, "reports/v016_frames", "prmr_frame")
save_frames(normal_frames, "reports/v016_frames", "normal_frame")

normal_size = sum(len(frame) for frame in normal_frames)
prmr_size = memory.storage_size()

saved, ratio, percentage = calculate_score(normal_size, prmr_size)

report = {
    "test_name": "Multi-Object Video Scene V0.16",
    "total_frames": total_frames,
    "origin_object_count": len(memory.origin_objects),
    "transformation_count": len(memory.transformations),
    "reconstruction_match": normal_frames == prmr_frames,
    "normal_storage_size": normal_size,
    "prmr_storage_size": prmr_size,
    "saved_bytes": saved,
    "compression_ratio": ratio,
    "saved_percentage": percentage,
    "lineage": memory.why()
}

with open("reports/multi_object_video_v016.json", "w", encoding="utf-8") as file:
    json.dump(report, file, indent=4)

print("PRMR MULTI-OBJECT VIDEO SCENE V0.16")
print("-----------------------------------")

print("\nTotal frames:", report["total_frames"])
print("Origin objects:", report["origin_object_count"])
print("Transformations:", report["transformation_count"])
print("Reconstruction match:", report["reconstruction_match"])

print("\nNormal storage:", report["normal_storage_size"])
print("PRMR storage:", report["prmr_storage_size"])
print("Saved bytes:", report["saved_bytes"])

if report["compression_ratio"] is not None:
    print("Compression ratio:", round(report["compression_ratio"], 2), "x")

print("Saved percentage:", round(report["saved_percentage"], 2), "%")

print("\nFILES CREATED:")
print("reports/multi_object_video_v016.json")
print("reports/v016_frames/prmr_frame_000.svg through prmr_frame_039.svg")
print("reports/v016_frames/normal_frame_000.svg through normal_frame_039.svg")

print("\nLINEAGE:")
for item in report["lineage"]:
    print("-", item)