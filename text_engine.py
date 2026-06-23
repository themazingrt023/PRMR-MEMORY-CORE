import json


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

    def remove_text(self, text_to_remove):
        self.transformations.append({
            "t": "remove",
            "v": text_to_remove
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

            elif transformation["t"] == "remove":
                current_text = current_text.replace(
                    transformation["v"],
                    ""
                )

        return current_text

    def storage_size(self):
        return len(json.dumps(self.to_dict(), separators=(",", ":")))

    def normal_storage_size(self, versions):
        return sum(len(version) for version in versions)

    def to_dict(self):
        return {
            "type": "PRMRTextMemory",
            "version": "0.10",
            "origin_text": self.origin_text,
            "transformations": self.transformations
        }

    def save(self, filename):
        with open(filename, "w", encoding="utf-8") as file:
            json.dump(self.to_dict(), file, indent=4)

    @classmethod
    def from_dict(cls, data):
        memory = cls(data["origin_text"])
        memory.transformations = data["transformations"]
        return memory

    @classmethod
    def load(cls, filename):
        with open(filename, "r", encoding="utf-8") as file:
            data = json.load(file)

        return cls.from_dict(data)