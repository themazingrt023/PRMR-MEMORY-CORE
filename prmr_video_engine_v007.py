import json


class PRMRVideoMemory:
    def __init__(self, canvas_width, canvas_height, total_frames):
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        self.total_frames = total_frames
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
            f"'{object_id}' moves frames {start_frame}-{end_frame} by dx={dx_per_frame}, dy={dy_per_frame} per frame."
        )

    def add_colour_change_rule(self, object_id, frame, colour):
        self.transformations.append({
            "t": "colour_at_frame",
            "id": object_id,
            "frame": frame,
            "colour": colour
        })

        self.lineage.append(
            f"'{object_id}' changes colour to {colour} at frame {frame}."
        )

    def add_resize_rule(self, object_id, frame, radius):
        self.transformations.append({
            "t": "resize_at_frame",
            "id": object_id,
            "frame": frame,
            "radius": radius
        })

        self.lineage.append(
            f"'{object_id}' resizes to radius {radius} at frame {frame}."
        )

    def reconstruct_frame_objects(self, frame_number):
        objects = json.loads(json.dumps(self.origin_objects))

        for transformation in self.transformations:
            object_id = transformation["id"]

            if object_id not in objects:
                continue

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

    def reconstruct_all_frames(self):
        frames = []

        for frame_number in range(self.total_frames):
            objects = self.reconstruct_frame_objects(frame_number)
            frames.append(self.render_svg_frame(objects, frame_number))

        return frames

    def storage_size(self):
        return len(json.dumps(self.to_dict(), separators=(",", ":")))

    def why(self):
        return self.lineage

    def to_dict(self):
        return {
            "type": "PRMRVideoMemory",
            "version": "0.10",
            "canvas_width": self.canvas_width,
            "canvas_height": self.canvas_height,
            "total_frames": self.total_frames,
            "origin_objects": self.origin_objects,
            "transformations": self.transformations,
            "lineage": self.lineage
        }

    def save(self, filename):
        with open(filename, "w", encoding="utf-8") as file:
            json.dump(self.to_dict(), file, indent=4)

    @classmethod
    def from_dict(cls, data):
        memory = cls(
            data["canvas_width"],
            data["canvas_height"],
            data["total_frames"]
        )

        memory.origin_objects = data["origin_objects"]
        memory.transformations = data["transformations"]
        memory.lineage = data["lineage"]

        return memory

    @classmethod
    def load(cls, filename):
        with open(filename, "r", encoding="utf-8") as file:
            data = json.load(file)

        return cls.from_dict(data)