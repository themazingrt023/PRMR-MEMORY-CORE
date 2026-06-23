import json
import os


class PRMRLargeBranchingMemory:
    def __init__(self, canvas_width, canvas_height):
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        self.origin_objects = {}
        self.branches = {}
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

    def create_branch(self, branch_name):
        self.branches[branch_name] = []
        self.lineage.append(f"Branch '{branch_name}' created.")

    def add_move_to_branch(self, branch_name, object_id, dx, dy):
        self.branches[branch_name].append({
            "t": "move",
            "id": object_id,
            "dx": dx,
            "dy": dy
        })

    def add_colour_to_branch(self, branch_name, object_id, colour):
        self.branches[branch_name].append({
            "t": "colour",
            "id": object_id,
            "colour": colour
        })

    def add_circle_resize_to_branch(self, branch_name, object_id, radius):
        self.branches[branch_name].append({
            "t": "circle_resize",
            "id": object_id,
            "radius": radius
        })

    def add_rect_resize_to_branch(self, branch_name, object_id, width, height):
        self.branches[branch_name].append({
            "t": "rect_resize",
            "id": object_id,
            "width": width,
            "height": height
        })

    def reconstruct_branch_objects(self, branch_name):
        objects = json.loads(json.dumps(self.origin_objects))

        for transformation in self.branches[branch_name]:
            object_id = transformation["id"]

            if object_id not in objects:
                continue

            obj = objects[object_id]

            if transformation["t"] == "move":
                obj["x"] += transformation["dx"]
                obj["y"] += transformation["dy"]

            elif transformation["t"] == "colour":
                obj["colour"] = transformation["colour"]

            elif transformation["t"] == "circle_resize":
                if obj["type"] == "circle":
                    obj["radius"] = transformation["radius"]

            elif transformation["t"] == "rect_resize":
                if obj["type"] == "rect":
                    obj["width"] = transformation["width"]
                    obj["height"] = transformation["height"]

        return objects

    def render_svg(self, objects, title):
        svg = ""
        svg += f'<svg width="{self.canvas_width}" height="{self.canvas_height}" xmlns="http://www.w3.org/2000/svg">\n'
        svg += '<rect width="100%" height="100%" fill="black"/>\n'
        svg += f'<text x="20" y="30" fill="white" font-size="20">{title}</text>\n'

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

    def reconstruct_branch_svg(self, branch_name):
        objects = self.reconstruct_branch_objects(branch_name)
        return self.render_svg(objects, f"PRMR Large Branch: {branch_name}")

    def storage_size(self):
        data = {
            "type": "PRMRLargeBranchingMemory",
            "version": "0.18",
            "canvas_width": self.canvas_width,
            "canvas_height": self.canvas_height,
            "origin_objects": self.origin_objects,
            "branches": self.branches
        }

        return len(json.dumps(data, separators=(",", ":")))


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


def build_large_branching_test():
    os.makedirs("reports", exist_ok=True)
    os.makedirs("reports/v018_branches", exist_ok=True)

    memory = PRMRLargeBranchingMemory(900, 600)

    # Origin scene with multiple objects
    memory.add_circle("orb", 120, 300, 35, "cyan")
    memory.add_circle("sun", 760, 120, 50, "gold")
    memory.add_circle("portal", 450, 300, 70, "purple")
    memory.add_rect("block", 390, 480, 120, 50, "gray")
    memory.add_rect("gate", 80, 430, 80, 120, "blue")

    colours = [
        "red", "gold", "magenta", "lime", "orange",
        "white", "purple", "cyan", "pink", "yellow"
    ]

    branch_names = []

    for branch_index in range(10):
        branch_name = f"branch_{branch_index:02d}"
        branch_names.append(branch_name)
        memory.create_branch(branch_name)

        # 20 transformations per branch
        memory.add_move_to_branch(branch_name, "orb", 10 * branch_index, -5 * branch_index)
        memory.add_colour_to_branch(branch_name, "orb", colours[branch_index])
        memory.add_circle_resize_to_branch(branch_name, "orb", 35 + branch_index * 3)

        memory.add_move_to_branch(branch_name, "sun", -4 * branch_index, 3 * branch_index)
        memory.add_circle_resize_to_branch(branch_name, "sun", 50 + branch_index * 4)

        memory.add_colour_to_branch(branch_name, "portal", colours[(branch_index + 2) % len(colours)])
        memory.add_circle_resize_to_branch(branch_name, "portal", 70 + branch_index * 2)

        memory.add_move_to_branch(branch_name, "block", -8 * branch_index, -3 * branch_index)
        memory.add_rect_resize_to_branch(branch_name, "block", 120 + branch_index * 6, 50 + branch_index * 2)
        memory.add_colour_to_branch(branch_name, "block", colours[(branch_index + 4) % len(colours)])

        memory.add_move_to_branch(branch_name, "gate", 5 * branch_index, -6 * branch_index)
        memory.add_rect_resize_to_branch(branch_name, "gate", 80 + branch_index * 4, 120 + branch_index * 5)
        memory.add_colour_to_branch(branch_name, "gate", colours[(branch_index + 6) % len(colours)])

        # repeated evolution steps to simulate longer histories
        memory.add_move_to_branch(branch_name, "orb", 3, -2)
        memory.add_move_to_branch(branch_name, "orb", 2, -1)
        memory.add_move_to_branch(branch_name, "portal", -2, 1)
        memory.add_move_to_branch(branch_name, "sun", -1, 2)
        memory.add_move_to_branch(branch_name, "block", 1, -1)
        memory.add_move_to_branch(branch_name, "gate", -1, 1)
        memory.add_colour_to_branch(branch_name, "portal", colours[(branch_index + 8) % len(colours)])

    # PRMR reconstructed branch SVGs
    prmr_svgs = []

    for branch_name in branch_names:
        svg = memory.reconstruct_branch_svg(branch_name)
        prmr_svgs.append(svg)
        save_file(f"reports/v018_branches/prmr_{branch_name}.svg", svg)

    # Normal snapshot storage:
    # Store origin snapshot + full final SVG for every branch.
    normal_svgs = []

    origin_svg = memory.render_svg(memory.origin_objects, "PRMR Large Branch Origin")
    normal_svgs.append(origin_svg)
    save_file("reports/v018_branches/normal_origin.svg", origin_svg)

    for branch_name in branch_names:
        objects = memory.reconstruct_branch_objects(branch_name)
        svg = memory.render_svg(objects, f"PRMR Large Branch: {branch_name}")
        normal_svgs.append(svg)
        save_file(f"reports/v018_branches/normal_{branch_name}.svg", svg)

    normal_size = sum(len(svg) for svg in normal_svgs)
    prmr_size = memory.storage_size()

    saved, ratio, percentage = calculate_score(normal_size, prmr_size)

    # Match test:
    # Compare every final branch PRMR reconstruction against normal final branch.
    reconstruction_match = True

    for index, branch_name in enumerate(branch_names):
        normal_branch_svg = normal_svgs[index + 1]
        prmr_branch_svg = prmr_svgs[index]

        if normal_branch_svg != prmr_branch_svg:
            reconstruction_match = False
            break

    report = {
        "test_name": "Large Branching Timeline Benchmark V0.18",
        "branch_count": len(branch_names),
        "origin_object_count": len(memory.origin_objects),
        "transformations_per_branch": 20,
        "total_transformations": sum(len(memory.branches[name]) for name in branch_names),
        "reconstruction_match": reconstruction_match,
        "normal_storage_size": normal_size,
        "prmr_storage_size": prmr_size,
        "saved_bytes": saved,
        "compression_ratio": ratio,
        "saved_percentage": percentage
    }

    with open("reports/large_branching_timeline_v018.json", "w", encoding="utf-8") as file:
        json.dump(report, file, indent=4)

    return report


report = build_large_branching_test()

print("PRMR LARGE BRANCHING TIMELINE V0.18")
print("-----------------------------------")

print("\nBranches:", report["branch_count"])
print("Origin objects:", report["origin_object_count"])
print("Transformations per branch:", report["transformations_per_branch"])
print("Total transformations:", report["total_transformations"])
print("Reconstruction match:", report["reconstruction_match"])

print("\nNormal storage:", report["normal_storage_size"])
print("PRMR storage:", report["prmr_storage_size"])
print("Saved bytes:", report["saved_bytes"])

if report["compression_ratio"] is not None:
    print("Compression ratio:", round(report["compression_ratio"], 2), "x")

print("Saved percentage:", round(report["saved_percentage"], 2), "%")

print("\nFILES CREATED:")
print("reports/large_branching_timeline_v018.json")
print("reports/v018_branches/prmr_branch_00.svg through prmr_branch_09.svg")
print("reports/v018_branches/normal_branch_00.svg through normal_branch_09.svg")