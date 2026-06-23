import json
import os


class RuleCompressedPRMRMemory:
    def __init__(self, canvas_width, canvas_height, branch_count):
        self.w = canvas_width
        self.h = canvas_height
        self.branch_count = branch_count

        self.objects = {}
        self.colours = [
            "red", "gold", "magenta", "lime", "orange",
            "white", "purple", "cyan", "pink", "yellow"
        ]

        self.rules = {
            "version": "0.21",
            "rule_set": "branch_index_parametric_scene_evolution",
            "description": "Each branch is reconstructed from branch index using deterministic transformation rules."
        }

    def add_circle(self, object_id, x, y, radius, colour):
        self.objects[object_id] = ["circle", x, y, radius, colour]

    def add_rect(self, object_id, x, y, width, height, colour):
        self.objects[object_id] = ["rect", x, y, width, height, colour]

    def reconstruct_branch_objects(self, branch_index):
        objects = json.loads(json.dumps(self.objects))
        colours = self.colours

        colour_offset = branch_index % len(colours)

        # orb rules
        objects["orb"][1] += 10 * branch_index
        objects["orb"][2] += -5 * branch_index
        objects["orb"][-1] = colours[colour_offset]
        objects["orb"][3] = 35 + (branch_index % 20) * 3
        objects["orb"][1] += 3
        objects["orb"][2] += -2
        objects["orb"][1] += 2
        objects["orb"][2] += -1

        # sun rules
        objects["sun"][1] += -4 * branch_index
        objects["sun"][2] += 3 * branch_index
        objects["sun"][3] = 50 + (branch_index % 15) * 4
        objects["sun"][1] += -1
        objects["sun"][2] += 2

        # portal rules
        objects["portal"][-1] = colours[(colour_offset + 2) % len(colours)]
        objects["portal"][3] = 70 + (branch_index % 12) * 2
        objects["portal"][1] += -2
        objects["portal"][2] += 1
        objects["portal"][-1] = colours[(colour_offset + 8) % len(colours)]

        # block rules
        objects["block"][1] += -8 * branch_index
        objects["block"][2] += -3 * branch_index
        objects["block"][3] = 120 + (branch_index % 20) * 6
        objects["block"][4] = 50 + (branch_index % 20) * 2
        objects["block"][-1] = colours[(colour_offset + 4) % len(colours)]
        objects["block"][1] += 1
        objects["block"][2] += -1

        # gate rules
        objects["gate"][1] += 5 * branch_index
        objects["gate"][2] += -6 * branch_index
        objects["gate"][3] = 80 + (branch_index % 20) * 4
        objects["gate"][4] = 120 + (branch_index % 20) * 5
        objects["gate"][-1] = colours[(colour_offset + 6) % len(colours)]
        objects["gate"][1] += -1
        objects["gate"][2] += 1

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

    def reconstruct_branch_svg(self, branch_index):
        objects = self.reconstruct_branch_objects(branch_index)
        branch_name = f"branch_{branch_index:03d}"
        return self.render_svg(objects, f"Rule-Compressed PRMR Branch: {branch_name}")

    def storage_size(self):
        data = {
            "t": "RuleCompressedPRMRMemory",
            "v": "0.21",
            "w": self.w,
            "h": self.h,
            "n": self.branch_count,
            "o": self.objects,
            "c": self.colours,
            "r": self.rules
        }

        return len(json.dumps(data, separators=(",", ":")))


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
        return self.render_svg(objects, f"Rule-Compressed PRMR Branch: {branch_name}")

    def storage_size(self):
        data = {
            "t": "CompactPRMRBranchingMemory",
            "v": "0.20",
            "w": self.w,
            "h": self.h,
            "o": self.objects,
            "b": self.branches
        }

        return len(json.dumps(data, separators=(",", ":")))


def build_compact_memory(branch_count):
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

    for branch_index in range(branch_count):
        branch_name = f"branch_{branch_index:03d}"
        branch_names.append(branch_name)
        memory.create_branch(branch_name)

        colour_offset = branch_index % len(colours)

        memory.move(branch_name, "orb", 10 * branch_index, -5 * branch_index)
        memory.colour(branch_name, "orb", colours[colour_offset])
        memory.resize_circle(branch_name, "orb", 35 + (branch_index % 20) * 3)

        memory.move(branch_name, "sun", -4 * branch_index, 3 * branch_index)
        memory.resize_circle(branch_name, "sun", 50 + (branch_index % 15) * 4)

        memory.colour(branch_name, "portal", colours[(colour_offset + 2) % len(colours)])
        memory.resize_circle(branch_name, "portal", 70 + (branch_index % 12) * 2)

        memory.move(branch_name, "block", -8 * branch_index, -3 * branch_index)
        memory.resize_rect(branch_name, "block", 120 + (branch_index % 20) * 6, 50 + (branch_index % 20) * 2)
        memory.colour(branch_name, "block", colours[(colour_offset + 4) % len(colours)])

        memory.move(branch_name, "gate", 5 * branch_index, -6 * branch_index)
        memory.resize_rect(branch_name, "gate", 80 + (branch_index % 20) * 4, 120 + (branch_index % 20) * 5)
        memory.colour(branch_name, "gate", colours[(colour_offset + 6) % len(colours)])

        memory.move(branch_name, "orb", 3, -2)
        memory.move(branch_name, "orb", 2, -1)
        memory.move(branch_name, "portal", -2, 1)
        memory.move(branch_name, "sun", -1, 2)
        memory.move(branch_name, "block", 1, -1)
        memory.move(branch_name, "gate", -1, 1)
        memory.colour(branch_name, "portal", colours[(colour_offset + 8) % len(colours)])

    return memory, branch_names


def build_rule_memory(branch_count):
    memory = RuleCompressedPRMRMemory(900, 600, branch_count)

    memory.add_circle("orb", 120, 300, 35, "cyan")
    memory.add_circle("sun", 760, 120, 50, "gold")
    memory.add_circle("portal", 450, 300, 70, "purple")
    memory.add_rect("block", 390, 480, 120, 50, "gray")
    memory.add_rect("gate", 80, 430, 80, 120, "blue")

    return memory


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


def run_test(branch_count):
    compact_memory, branch_names = build_compact_memory(branch_count)
    rule_memory = build_rule_memory(branch_count)

    normal_svgs = []
    compact_svgs = []
    rule_svgs = []

    origin_svg = compact_memory.render_svg(compact_memory.objects, "Rule-Compressed PRMR Origin")
    normal_svgs.append(origin_svg)

    reconstruction_match = True

    for branch_index, branch_name in enumerate(branch_names):
        compact_svg = compact_memory.reconstruct_branch_svg(branch_name)
        rule_svg = rule_memory.reconstruct_branch_svg(branch_index)

        compact_svgs.append(compact_svg)
        rule_svgs.append(rule_svg)
        normal_svgs.append(compact_svg)

        if compact_svg != rule_svg:
            reconstruction_match = False

    normal_size = sum(len(svg) for svg in normal_svgs)
    compact_size = compact_memory.storage_size()
    rule_size = rule_memory.storage_size()

    compact_saved, compact_ratio, compact_percentage = calculate_score(normal_size, compact_size)
    rule_saved, rule_ratio, rule_percentage = calculate_score(normal_size, rule_size)

    rule_vs_compact_saved, rule_vs_compact_ratio, rule_vs_compact_percentage = calculate_score(compact_size, rule_size)

    return {
        "branch_count": branch_count,
        "reconstruction_match": reconstruction_match,
        "normal_storage_size": normal_size,
        "compact_prmr_storage_size": compact_size,
        "rule_prmr_storage_size": rule_size,
        "compact_saved_bytes": compact_saved,
        "compact_compression_ratio": compact_ratio,
        "compact_saved_percentage": compact_percentage,
        "rule_saved_bytes": rule_saved,
        "rule_compression_ratio": rule_ratio,
        "rule_saved_percentage": rule_percentage,
        "rule_vs_compact_saved_bytes": rule_vs_compact_saved,
        "rule_vs_compact_ratio": rule_vs_compact_ratio,
        "rule_vs_compact_saved_percentage": rule_vs_compact_percentage
    }


os.makedirs("reports", exist_ok=True)

branch_counts = [5, 10, 25, 50, 100, 250, 500]

results = []

for branch_count in branch_counts:
    results.append(run_test(branch_count))

with open("reports/rule_compression_v021.json", "w", encoding="utf-8") as file:
    json.dump(results, file, indent=4)

print("PRMR RULE COMPRESSION BENCHMARK V0.21")
print("-------------------------------------")

for result in results:
    print("\nBranches:", result["branch_count"])
    print("Reconstruction match:", result["reconstruction_match"])

    print("Normal storage:", result["normal_storage_size"])
    print("Compact PRMR storage:", result["compact_prmr_storage_size"])
    print("Rule PRMR storage:", result["rule_prmr_storage_size"])

    print("Compact saved %:", round(result["compact_saved_percentage"], 2), "%")
    print("Rule saved %:", round(result["rule_saved_percentage"], 2), "%")

    if result["rule_compression_ratio"] is not None:
        print("Rule compression ratio:", round(result["rule_compression_ratio"], 2), "x")

    print("Rule vs compact saved:", result["rule_vs_compact_saved_bytes"])
    print("Rule vs compact saved %:", round(result["rule_vs_compact_saved_percentage"], 2), "%")

print("\nREPORT CREATED:")
print("reports/rule_compression_v021.json")