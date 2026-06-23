import json


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
            f"Origin circle '{object_id}' at ({x}, {y}), radius {radius}, colour {colour}."
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

    def resize_object(self, object_id, radius):
        self.transformations.append({
            "t": "resize",
            "id": object_id,
            "radius": radius
        })

        self.lineage.append(
            f"Resized '{object_id}' to radius {radius}."
        )

    def reconstruct_objects(self):
        objects = json.loads(json.dumps(self.origin_objects))

        for transformation in self.transformations:
            object_id = transformation["id"]

            if object_id not in objects:
                continue

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

    def reconstruct_svg(self):
        return self.render_svg(self.reconstruct_objects())

    def storage_size(self):
        return len(json.dumps(self.to_dict(), separators=(",", ":")))

    def why(self):
        return self.lineage

    def to_dict(self):
        return {
            "type": "PRMRImageMemory",
            "version": "0.10",
            "canvas_width": self.canvas_width,
            "canvas_height": self.canvas_height,
            "origin_objects": self.origin_objects,
            "transformations": self.transformations,
            "lineage": self.lineage
        }

    def save(self, filename):
        with open(filename, "w", encoding="utf-8") as file:
            json.dump(self.to_dict(), file, indent=4)

    @classmethod
    def from_dict(cls, data):
        memory = cls(data["canvas_width"], data["canvas_height"])
        memory.origin_objects = data["origin_objects"]
        memory.transformations = data["transformations"]
        memory.lineage = data["lineage"]
        return memory

    @classmethod
    def load(cls, filename):
        with open(filename, "r", encoding="utf-8") as file:
            data = json.load(file)

        return cls.from_dict(data)