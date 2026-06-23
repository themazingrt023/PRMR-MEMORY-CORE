import json
import os


class CompactPRMRBranchingMemory:
    def __init__(self, canvas_width, canvas_height):
        self.w = canvas_width
        self.h = canvas_height
        self.objects = {}
        self.branches = {}

    def add_circle(self, object_id, x, y, radius, colour):
        self.objects[object_id] = ["circle", x, y, radius, colour]

    def add_rect(self, object_id, x, y, width, height, colour):
        self.objects[object_id] = ["rect", x, y, width, height, colour]

    def create_branch(self, branch_name):
        self.branches[branch_name] = []

    def move(self, branch_name, object_id, dx, dy):
        self.branches[branch_name].append(["m", object_id, dx, dy])

    def colour(self, branch_name, object_id, colour):
        self.branches[branch_name].append(["c", object_id, colour])

    def resize_circle(self, branch_name, object_id, radius):
        self.branches[branch_name].append(["rc", object_id, radius])

    def resize_rect(self, branch_name, object_id, width, height):
        self.branches[branch_name].append(["rr", object_id, width, height])

    def reconstruct_branch_objects(self, branch_name):
        objects = json.loads(json.dumps(self.objects))

        for t in self.branches[branch_name]:
            code = t[0]
            object_id = t[1]

            if object_id not in objects:
                continue

            obj = objects[object_id]

            if code == "m":
                obj[1] += t[2]
                obj[2] += t[3]

            elif code == "c":
                obj[-1] = t[2]

            elif code == "rc":
                if obj[0] == "circle":
                    obj[3] = t[2]

            elif code == "rr":
                if obj[0] == "rect":
                    obj[3] = t[2]
                    obj[4] = t[3]

        return objects

    def render_svg(self, objects, title):
        svg = ""
        svg += f'<svg width="{self.w}" height="{self.h}" xmlns="http://www.w3.org/2000/svg">\n'
        svg += '<rect width="100%" height="100%" fill="black"/>\n'
        svg += f'<text x="20" y="30" fill="white" font-size="20">{title}</text>\n'

        for object_id, obj in objects.items():
            if obj[0] == "circle":
                _, x, y, radius, colour = obj
                svg += f'<circle id="{object_id}" cx="{x}" cy="{y}" r="{radius}" fill="{colour}" />\n'

            elif obj[0] == "rect":
                _, x, y, width, height, colour = obj
                svg += f'<rect id="{object_id}" x="{x}" y="{y}" width="{width}" height="{height}" fill="{colour}" />\n'

        svg += "</svg>"
        return svg

    def reconstruct_branch_svg(self, branch_name):
        objects = self.reconstruct_branch_objects(branch_name)
        return self.render_svg(objects, f"Compact PRMR Branch: {branch_name}")

    def storage_size(self):
        data = {
            "t": "CompactPRMRBranchingMemory",
            "v": "0.19",
            "w": self.w,
            "h": self.h,
            "o": self.objects,
            "b": self.branches
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


def run_test():
    os.makedirs("reports", exist_ok=True)
    os.makedirs("reports/v019_compact_branches", exist_ok=True)

    memory = CompactPRMRBranchingMemory(900, 600)

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

        memory.move(branch_name, "orb", 10 * branch_index, -5 * branch_index)
        memory.colour(branch_name, "orb", colours[branch_index])
        memory.resize_circle(branch_name, "orb", 35 + branch_index * 3)

        memory.move(branch_name, "sun", -4 * branch_index, 3 * branch_index)
        memory.resize_circle(branch_name, "sun", 50 + branch_index * 4)

        memory.colour(branch_name, "portal", colours[(branch_index + 2) % len(colours)])
        memory.resize_circle(branch_name, "portal", 70 + branch_index * 2)

        memory.move(branch_name, "block", -8 * branch_index, -3 * branch_index)
        memory.resize_rect(branch_name, "block", 120 + branch_index * 6, 50 + branch_index * 2)
        memory.colour(branch_name, "block", colours[(branch_index + 4) % len(colours)])

        memory.move(branch_name, "gate", 5 * branch_index, -6 * branch_index)
        memory.resize_rect(branch_name, "gate", 80 + branch_index * 4, 120 + branch_index * 5)
        memory.colour(branch_name, "gate", colours[(branch_index + 6) % len(colours)])

        memory.move(branch_name, "orb", 3, -2)
        memory.move(branch_name, "orb", 2, -1)
        memory.move(branch_name, "portal", -2, 1)
        memory.move(branch_name, "sun", -1, 2)
        memory.move(branch_name, "block", 1, -1)
        memory.move(branch_name, "gate", -1, 1)
        memory.colour(branch_name, "portal", colours[(branch_index + 8) % len(colours)])

    prmr_svgs = []
    normal_svgs = []

    origin_svg = memory.render_svg(memory.objects, "Compact PRMR Origin")
    normal_svgs.append(origin_svg)
    save_file("reports/v019_compact_branches/origin.svg", origin_svg)

    for branch_name in branch_names:
        prmr_svg = memory.reconstruct_branch_svg(branch_name)
        prmr_svgs.append(prmr_svg)
        save_file(f"reports/v019_compact_branches/prmr_{branch_name}.svg", prmr_svg)

        normal_objects = memory.reconstruct_branch_objects(branch_name)
        normal_svg = memory.render_svg(normal_objects, f"Compact PRMR Branch: {branch_name}")
        normal_svgs.append(normal_svg)
        save_file(f"reports/v019_compact_branches/normal_{branch_name}.svg", normal_svg)

    normal_size = sum(len(svg) for svg in normal_svgs)
    prmr_size = memory.storage_size()

    saved, ratio, percentage = calculate_score(normal_size, prmr_size)

    reconstruction_match = True

    for index, branch_name in enumerate(branch_names):
        if prmr_svgs[index] != normal_svgs[index + 1]:
            reconstruction_match = False
            break

    report = {
        "test_name": "Compact Branching Timeline Encoding V0.19",
        "branch_count": len(branch_names),
        "origin_object_count": len(memory.objects),
        "total_transformations": sum(len(memory.branches[name]) for name in branch_names),
        "reconstruction_match": reconstruction_match,
        "normal_storage_size": normal_size,
        "compact_prmr_storage_size": prmr_size,
        "saved_bytes": saved,
        "compression_ratio": ratio,
        "saved_percentage": percentage
    }

    with open("reports/compact_branching_v019.json", "w", encoding="utf-8") as file:
        json.dump(report, file, indent=4)

    return report


report = run_test()

print("COMPACT PRMR BRANCHING ENCODING V0.19")
print("-------------------------------------")

print("\nBranches:", report["branch_count"])
print("Origin objects:", report["origin_object_count"])
print("Total transformations:", report["total_transformations"])
print("Reconstruction match:", report["reconstruction_match"])

print("\nNormal storage:", report["normal_storage_size"])
print("Compact PRMR storage:", report["compact_prmr_storage_size"])
print("Saved bytes:", report["saved_bytes"])

if report["compression_ratio"] is not None:
    print("Compression ratio:", round(report["compression_ratio"], 2), "x")

print("Saved percentage:", round(report["saved_percentage"], 2), "%")

print("\nREPORT CREATED:")
print("reports/compact_branching_v019.json")