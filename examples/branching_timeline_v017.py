import json
import os


class PRMRBranchingMemory:
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

        self.lineage.append(
            f"Branch '{branch_name}': moved '{object_id}' by dx={dx}, dy={dy}."
        )

    def add_colour_to_branch(self, branch_name, object_id, colour):
        self.branches[branch_name].append({
            "t": "colour",
            "id": object_id,
            "colour": colour
        })

        self.lineage.append(
            f"Branch '{branch_name}': changed '{object_id}' colour to {colour}."
        )

    def add_resize_to_branch(self, branch_name, object_id, radius):
        self.branches[branch_name].append({
            "t": "resize",
            "id": object_id,
            "radius": radius
        })

        self.lineage.append(
            f"Branch '{branch_name}': resized '{object_id}' to radius {radius}."
        )

    def reconstruct_branch_objects(self, branch_name):
        if branch_name not in self.branches:
            raise ValueError(f"Branch '{branch_name}' does not exist.")

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

            elif transformation["t"] == "resize":
                obj["radius"] = transformation["radius"]

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

        svg += "</svg>"
        return svg

    def reconstruct_branch_svg(self, branch_name):
        objects = self.reconstruct_branch_objects(branch_name)
        return self.render_svg(objects, f"PRMR Branch: {branch_name}")

    def origin_svg(self):
        return self.render_svg(self.origin_objects, "PRMR Origin State")

    def storage_size(self):
        data = {
            "type": "PRMRBranchingMemory",
            "version": "0.17",
            "canvas_width": self.canvas_width,
            "canvas_height": self.canvas_height,
            "origin_objects": self.origin_objects,
            "branches": self.branches,
            "lineage": self.lineage
        }

        return len(json.dumps(data, separators=(",", ":")))

    def why(self, branch_name=None):
        if branch_name is None:
            return self.lineage

        branch_lineage = []

        for item in self.lineage:
            if f"Branch '{branch_name}'" in item or "Origin" in item:
                branch_lineage.append(item)

        return branch_lineage


def save_file(filename, content):
    with open(filename, "w", encoding="utf-8") as file:
        file.write(content)


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


def render_normal_branch(x, y, radius, colour, title):
    svg = ""
    svg += '<svg width="600" height="400" xmlns="http://www.w3.org/2000/svg">\n'
    svg += '<rect width="100%" height="100%" fill="black"/>\n'
    svg += f'<text x="20" y="30" fill="white" font-size="20">{title}</text>\n'
    svg += f'<circle id="orb" cx="{x}" cy="{y}" r="{radius}" fill="{colour}" />\n'
    svg += "</svg>"
    return svg


os.makedirs("reports", exist_ok=True)

memory = PRMRBranchingMemory(600, 400)

# Origin
memory.add_circle("orb", 300, 200, 45, "cyan")

# Branches
memory.create_branch("peace_path")
memory.create_branch("war_path")
memory.create_branch("void_path")

# Peace path transformations
memory.add_colour_to_branch("peace_path", "orb", "gold")
memory.add_move_to_branch("peace_path", "orb", 0, -90)
memory.add_resize_to_branch("peace_path", "orb", 60)

# War path transformations
memory.add_colour_to_branch("war_path", "orb", "red")
memory.add_move_to_branch("war_path", "orb", 120, 40)
memory.add_resize_to_branch("war_path", "orb", 85)

# Void path transformations
memory.add_colour_to_branch("void_path", "orb", "purple")
memory.add_move_to_branch("void_path", "orb", -130, 60)
memory.add_resize_to_branch("void_path", "orb", 35)

# PRMR reconstructions
origin_svg = memory.origin_svg()
peace_svg = memory.reconstruct_branch_svg("peace_path")
war_svg = memory.reconstruct_branch_svg("war_path")
void_svg = memory.reconstruct_branch_svg("void_path")

save_file("reports/branch_origin_v017.svg", origin_svg)
save_file("reports/branch_peace_prmr_v017.svg", peace_svg)
save_file("reports/branch_war_prmr_v017.svg", war_svg)
save_file("reports/branch_void_prmr_v017.svg", void_svg)

# Normal snapshots
normal_origin = render_normal_branch(300, 200, 45, "cyan", "PRMR Origin State")
normal_peace = render_normal_branch(300, 110, 60, "gold", "PRMR Branch: peace_path")
normal_war = render_normal_branch(420, 240, 85, "red", "PRMR Branch: war_path")
normal_void = render_normal_branch(170, 260, 35, "purple", "PRMR Branch: void_path")

normal_versions = [
    normal_origin,
    normal_peace,
    normal_war,
    normal_void
]

normal_size = sum(len(version) for version in normal_versions)
prmr_size = memory.storage_size()

saved, ratio, percentage = calculate_score(normal_size, prmr_size)

reconstruction_match = (
    origin_svg == normal_origin and
    peace_svg == normal_peace and
    war_svg == normal_war and
    void_svg == normal_void
)

report = {
    "test_name": "Branching Timeline Memory V0.17",
    "branch_count": len(memory.branches),
    "origin_object_count": len(memory.origin_objects),
    "reconstruction_match": reconstruction_match,
    "normal_storage_size": normal_size,
    "prmr_storage_size": prmr_size,
    "saved_bytes": saved,
    "compression_ratio": ratio,
    "saved_percentage": percentage,
    "lineage": memory.why()
}

with open("reports/branching_timeline_v017.json", "w", encoding="utf-8") as file:
    json.dump(report, file, indent=4)

print("PRMR BRANCHING TIMELINE MEMORY V0.17")
print("------------------------------------")

print("\nBranches:", report["branch_count"])
print("Origin objects:", report["origin_object_count"])
print("Reconstruction match:", report["reconstruction_match"])

print("\nNormal storage:", report["normal_storage_size"])
print("PRMR storage:", report["prmr_storage_size"])
print("Saved bytes:", report["saved_bytes"])

if report["compression_ratio"] is not None:
    print("Compression ratio:", round(report["compression_ratio"], 2), "x")

print("Saved percentage:", round(report["saved_percentage"], 2), "%")

print("\nFILES CREATED:")
print("reports/branch_origin_v017.svg")
print("reports/branch_peace_prmr_v017.svg")
print("reports/branch_war_prmr_v017.svg")
print("reports/branch_void_prmr_v017.svg")
print("reports/branching_timeline_v017.json")

print("\nLINEAGE:")
for item in report["lineage"]:
    print("-", item)