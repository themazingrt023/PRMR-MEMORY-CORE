import json
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from prmr_memory import PRMRTextMemory


def calculate_score(normal_size, prmr_size):
    saved = normal_size - prmr_size

    if prmr_size == 0:
        compression_ratio = None
    else:
        compression_ratio = normal_size / prmr_size

    if normal_size == 0:
        saved_percentage = 0
    else:
        saved_percentage = (saved / normal_size) * 100

    return {
        "normal_storage_size": normal_size,
        "prmr_storage_size": prmr_size,
        "saved_bytes": saved,
        "compression_ratio": compression_ratio,
        "saved_percentage": saved_percentage
    }


def run_document_benchmark():
    origin = """
PRMR Memory Core is an experimental memory architecture designed to represent information differently from traditional snapshot storage.

Traditional systems usually store complete versions of information. A document may be saved as Version 1, Version 2, Version 3, and Version 4. Each version contains a large amount of repeated information.

PRMR Memory asks a different question. Instead of asking only what the final state is, it asks how the final state came to exist.

The core structure is origin, transformation, lineage, and reconstruction.

The origin is the first known state.
The transformation path contains the changes that occurred.
The lineage explains how each state became the next.
The reconstruction process rebuilds the final state from the origin and transformations.

This project does not claim infinite storage. It does not claim to beat every compression system. It is an experiment in representing evolving information differently.

The early goal is to test whether structured information can be stored as changes rather than repeated snapshots.
"""

    versions = []

    v1 = origin
    versions.append(v1)

    v2 = v1.replace(
        "experimental memory architecture",
        "recursive memory architecture"
    )
    versions.append(v2)

    v3 = v2 + """
This becomes important when information changes many times. Long documents, research notes, company knowledge, creative lore, design systems, and AI memories often evolve through repeated revisions.
"""
    versions.append(v3)

    v4 = v3.replace(
        "The core structure is origin, transformation, lineage, and reconstruction.",
        "The core structure is origin, transformation, lineage, compression scoring, and reconstruction."
    )
    versions.append(v4)

    v5 = v4 + """
A PRMR file does not only store the final result. It stores the path that produced the final result. This means the memory can explain why the final state exists.
"""
    versions.append(v5)

    v6 = v5.replace(
        "This project does not claim infinite storage.",
        "This project does not claim infinite storage or magical compression."
    )
    versions.append(v6)

    v7 = v6 + """
The strongest early domains are not tiny pieces of text. The strongest early domains are evolving documents, symbolic images, vector animation, simulation history, and structured memory chains.
"""
    versions.append(v7)

    v8 = v7.replace(
        "The early goal is to test whether structured information can be stored as changes rather than repeated snapshots.",
        "The early goal is to test whether structured evolving information can be stored as changes rather than repeated snapshots, while still reconstructing the final state accurately."
    )
    versions.append(v8)

    v9 = v8 + """
If PRMR can reconstruct final information accurately while using less storage than snapshot-based history, then it may become useful as a representation layer for evolving systems.
"""
    versions.append(v9)

    v10 = v9 + """
The long-term direction is to test larger documents, multi-object images, generated animations, branching timelines, and eventually real-world datasets.
"""
    versions.append(v10)

    memory = PRMRTextMemory(origin)

    memory.replace_text(
        "experimental memory architecture",
        "recursive memory architecture"
    )

    memory.add_text("""
This becomes important when information changes many times. Long documents, research notes, company knowledge, creative lore, design systems, and AI memories often evolve through repeated revisions.
""")

    memory.replace_text(
        "The core structure is origin, transformation, lineage, and reconstruction.",
        "The core structure is origin, transformation, lineage, compression scoring, and reconstruction."
    )

    memory.add_text("""
A PRMR file does not only store the final result. It stores the path that produced the final result. This means the memory can explain why the final state exists.
""")

    memory.replace_text(
        "This project does not claim infinite storage.",
        "This project does not claim infinite storage or magical compression."
    )

    memory.add_text("""
The strongest early domains are not tiny pieces of text. The strongest early domains are evolving documents, symbolic images, vector animation, simulation history, and structured memory chains.
""")

    memory.replace_text(
        "The early goal is to test whether structured information can be stored as changes rather than repeated snapshots.",
        "The early goal is to test whether structured evolving information can be stored as changes rather than repeated snapshots, while still reconstructing the final state accurately."
    )

    memory.add_text("""
If PRMR can reconstruct final information accurately while using less storage than snapshot-based history, then it may become useful as a representation layer for evolving systems.
""")

    memory.add_text("""
The long-term direction is to test larger documents, multi-object images, generated animations, branching timelines, and eventually real-world datasets.
""")

    normal_size = sum(len(version) for version in versions)
    prmr_size = memory.storage_size()

    final_snapshot = versions[-1]
    final_reconstruction = memory.reconstruct()

    score = calculate_score(normal_size, prmr_size)

    report = {
        "test_name": "Document-Scale Text Benchmark V0.13",
        "version_count": len(versions),
        "origin_length": len(origin),
        "final_length": len(final_snapshot),
        "transformation_count": len(memory.transformations),
        "reconstruction_match": final_snapshot == final_reconstruction,
        **score
    }

    os.makedirs("reports", exist_ok=True)

    with open("reports/document_text_benchmark_v013.json", "w", encoding="utf-8") as file:
        json.dump(report, file, indent=4)

    with open("reports/document_reconstruction_v013.txt", "w", encoding="utf-8") as file:
        file.write(final_reconstruction)

    return report


report = run_document_benchmark()

print("PRMR DOCUMENT TEXT BENCHMARK V0.13")
print("----------------------------------")

print("\nVersion count:", report["version_count"])
print("Origin length:", report["origin_length"])
print("Final length:", report["final_length"])
print("Transformation count:", report["transformation_count"])

print("\nReconstruction match:", report["reconstruction_match"])

print("\nNormal storage:", report["normal_storage_size"])
print("PRMR storage:", report["prmr_storage_size"])
print("Saved bytes:", report["saved_bytes"])

if report["compression_ratio"] is not None:
    print("Compression ratio:", round(report["compression_ratio"], 2), "x")

print("Saved percentage:", round(report["saved_percentage"], 2), "%")

print("\nREPORT CREATED:")
print("reports/document_text_benchmark_v013.json")

print("\nRECONSTRUCTED DOCUMENT CREATED:")
print("reports/document_reconstruction_v013.txt")