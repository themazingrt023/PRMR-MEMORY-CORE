import json
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class PRMRSceneMemory:
    def __init__(self, canvas_width, canvas_height):
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
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

    def move_object(self, object_id, dx, dy):
        self.transformations.append({
            "t": "move",
            "id": object_id,
            "dx": dx,
            "dy": dy
        })

        self.lineage.append(
            f"Moved '{object_id}' by dx={dx}, dy={dy}."
        )

    def change_colour(self, object_id, colour):
        self.transformations.append({
            "t": "colour",
            "id": object_id,
            "colour": colour
        })

        self.lineage.append(
            f"Changed '{object_id}' colour to {colour}."
        )

    def resize_circle(self, object_id, radius):
        self.transformations.append({
            "t": "resize_circle",
            "id": object_id,
            "radius": radius
        })

        self.lineage.append(
            f"Resized circle '{object_id}' to radius {radius}."
        )

    def resize_rect(self, object_id, width, height):
        self.transformations.append({
            "t": "resize_rect",
            "id": object_id,
            "width": width,
            "height": height
        })

        self.lineage.append(
            f"Resized rectangle '{object_id}' to {width}x{height}."
        )

    def reconstruct_objects(self):
        objects = json.loads(json.dumps(self.origin_objects))

        for transformation in self.transformations:
            object_id = transformation["id"]

            if object_id not in objects:
                continue

            obj = objects[object_id]

            if transformation["t"] == "move":
                obj["x"] += transformation["dx"]
                obj["y"] += transformation["dy"]

            elif transformation["t"] == "colour":
                obj["colour"] = transformation["colour"]

            elif transformation["t"] == "resize_circle":
                if obj["type"] == "circle":
                    obj["radius"] = transformation["radius"]

            elif transformation["t"] == "resize_rect":
                if obj["type"] == "rect":
                    obj["width"] = transformation["width"]
                    obj["height"] = transformation["height"]

        return objects

    def render_svg(self, objects):
        svg = ""
        svg += f'<svg width="{self.canvas_width}" height="{self.canvas_height}" xmlns="http://www.w3.org/2000/svg">\n'
        svg += '<rect width="100%" height="100%" fill="black"/>\n'
        svg += '<text x="20" y="30" fill="white" font-size="20">PRMR Multi-Object Scene V0.15</text>\n'

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

    def reconstruct_svg(self):
        return self.render_svg(self.reconstruct_objects())

    def storage_size(self):
        data = {
            "type": "PRMRSceneMemory",
            "version": "0.15",
            "canvas_width": self.canvas_width,
            "canvas_height": self.canvas_height,
            "origin_objects": self.origin_objects,
            "transformations": self.transformations,
            "lineage": self.lineage
        }

        return len(json.dumps(data, separators=(",", ":")))

    def why(self):
        return self.lineage


def normal_storage_size(svg_versions):
    return sum(len(version) for version in svg_versions)


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


def save_file(filename, content):
    with open(filename, "w", encoding="utf-8") as file:
        file.write(content)


os.makedirs("reports", exist_ok=True)

scene = PRMRSceneMemory(700, 500)

# Origin scene
scene.add_circle("orb", 100, 250, 35, "cyan")
scene.add_circle("sun", 560, 110, 50, "gold")
scene.add_circle("portal", 350, 250, 70, "purple")
scene.add_rect("block", 280, 380, 120, 50, "gray")

origin_svg = scene.render_svg(scene.origin_objects)
save_file("reports/multi_scene_origin_v015.svg", origin_svg)

normal_versions = []
normal_versions.append(origin_svg)

# Snapshot V2
snapshot_scene = PRMRSceneMemory(700, 500)
snapshot_scene.add_circle("orb", 200, 250, 35, "cyan")
snapshot_scene.add_circle("sun", 560, 110, 50, "gold")
snapshot_scene.add_circle("portal", 350, 250, 70, "purple")
snapshot_scene.add_rect("block", 280, 380, 120, 50, "gray")
normal_versions.append(snapshot_scene.render_svg(snapshot_scene.origin_objects))

# Snapshot V3
snapshot_scene = PRMRSceneMemory(700, 500)
snapshot_scene.add_circle("orb", 200, 250, 35, "cyan")
snapshot_scene.add_circle("sun", 560, 110, 80, "gold")
snapshot_scene.add_circle("portal", 350, 250, 70, "magenta")
snapshot_scene.add_rect("block", 280, 380, 120, 50, "gray")
normal_versions.append(snapshot_scene.render_svg(snapshot_scene.origin_objects))

# Snapshot V4 / final
snapshot_scene = PRMRSceneMemory(700, 500)
snapshot_scene.add_circle("orb", 200, 180, 35, "cyan")
snapshot_scene.add_circle("sun", 560, 110, 80, "gold")
snapshot_scene.add_circle("portal", 350, 250, 70, "magenta")
snapshot_scene.add_rect("block", 240, 360, 180, 65, "white")
normal_versions.append(snapshot_scene.render_svg(snapshot_scene.origin_objects))

normal_final_svg = normal_versions[-1]
save_file("reports/multi_scene_normal_final_v015.svg", normal_final_svg)

# PRMR transformations
scene.move_object("orb", 100, 0)
scene.resize_circle("sun", 80)
scene.change_colour("portal", "magenta")
scene.move_object("orb", 0, -70)
scene.move_object("block", -40, -20)
scene.resize_rect("block", 180, 65)
scene.change_colour("block", "white")

prmr_final_svg = scene.reconstruct_svg()
save_file("reports/multi_scene_prmr_reconstructed_v015.svg", prmr_final_svg)

normal_size = normal_storage_size(normal_versions)
prmr_size = scene.storage_size()
saved, ratio, percentage = calculate_score(normal_size, prmr_size)

report = {
    "test_name": "Multi-Object Image Scene V0.15",
    "origin_object_count": len(scene.origin_objects),
    "transformation_count": len(scene.transformations),
    "reconstruction_match": normal_final_svg == prmr_final_svg,
    "normal_storage_size": normal_size,
    "prmr_storage_size": prmr_size,
    "saved_bytes": saved,
    "compression_ratio": ratio,
    "saved_percentage": percentage,
    "lineage": scene.why()
}

with open("reports/multi_object_image_v015.json", "w", encoding="utf-8") as file:
    json.dump(report, file, indent=4)

print("PRMR MULTI-OBJECT IMAGE SCENE V0.15")
print("-----------------------------------")

print("\nOrigin objects:", report["origin_object_count"])
print("Transformations:", report["transformation_count"])
print("Reconstruction match:", report["reconstruction_match"])

print("\nNormal storage:", report["normal_storage_size"])
print("PRMR storage:", report["prmr_storage_size"])
print("Saved bytes:", report["saved_bytes"])

if report["compression_ratio"] is not None:
    print("Compression ratio:", round(report["compression_ratio"], 2), "x")

print("Saved percentage:", round(report["saved_percentage"], 2), "%")

print("\nFILES CREATED:")
print("reports/multi_scene_origin_v015.svg")
print("reports/multi_scene_normal_final_v015.svg")
print("reports/multi_scene_prmr_reconstructed_v015.svg")
print("reports/multi_object_image_v015.json")

print("\nLINEAGE:")
for item in report["lineage"]:
    print("-", item)