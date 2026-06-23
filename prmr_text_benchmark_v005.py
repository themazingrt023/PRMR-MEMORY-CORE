# PRMR TEXT BENCHMARK V0.05
# Goal:
# Compare normal version storage vs PRMR transformation storage.
#
# Normal storage:
# Stores every full text version.
#
# PRMR storage:
# Stores the origin text + transformation instructions.
#
# This tests whether PRMR becomes more useful as information evolves over many versions.


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

    def prmr_storage_size(self):
        transformation_data = json.dumps(
            self.transformations,
            separators=(",", ":")
        )

        return len(self.origin_text) + len(transformation_data)

    def show_transformations(self):
        return self.transformations


def normal_storage_size(versions):
    total = 0

    for version in versions:
        total += len(version)

    return total


# -------------------------
# TEST SYSTEM
# -------------------------

origin = """
PRMR Memory Core is a system for storing information differently.
It does not only store the final state.
It stores the origin, the transformation path, and the lineage of change.
"""

# Normal versions stored as complete snapshots
versions = []

v1 = origin
versions.append(v1)

v2 = v1.replace(
    "storing information differently",
    "representing information through transformation"
)
versions.append(v2)

v3 = v2 + "\nIt asks how information became what it is."
versions.append(v3)

v4 = v3 + "\nThis creates memory with causality instead of flat storage."
versions.append(v4)

v5 = v4.replace(
    "flat storage",
    "snapshot-only storage"
)
versions.append(v5)

v6 = v5 + "\nThe long-term goal is to test text, images, video, and AI memory."
versions.append(v6)

v7 = v6 + "\nIf successful, PRMR could become a new memory representation layer."
versions.append(v7)


# PRMR transformation storage
memory = PRMRTextMemory(origin)

memory.replace_text(
    "storing information differently",
    "representing information through transformation"
)

memory.add_text(
    "\nIt asks how information became what it is."
)

memory.add_text(
    "\nThis creates memory with causality instead of flat storage."
)

memory.replace_text(
    "flat storage",
    "snapshot-only storage"
)

memory.add_text(
    "\nThe long-term goal is to test text, images, video, and AI memory."
)

memory.add_text(
    "\nIf successful, PRMR could become a new memory representation layer."
)


# -------------------------
# BENCHMARK
# -------------------------

normal_size = normal_storage_size(versions)
prmr_size = memory.prmr_storage_size()
difference = normal_size - prmr_size

final_normal_version = versions[-1]
final_prmr_reconstruction = memory.reconstruct()

print("PRMR TEXT BENCHMARK V0.05")
print("------------------------")

print("\nNORMAL STORAGE SIZE:")
print(normal_size)

print("\nPRMR STORAGE SIZE:")
print(prmr_size)

print("\nDIFFERENCE:")
print(difference)

if difference > 0:
    print("\nRESULT:")
    print("PRMR used less storage in this test.")
else:
    print("\nRESULT:")
    print("PRMR used more storage in this test.")

print("\nRECONSTRUCTION MATCH:")
print(final_normal_version == final_prmr_reconstruction)

print("\nFINAL RECONSTRUCTED TEXT:")
print(final_prmr_reconstruction)

print("\nTRANSFORMATIONS:")
for transformation in memory.show_transformations():
    print(transformation)