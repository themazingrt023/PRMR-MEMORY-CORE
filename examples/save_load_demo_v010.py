import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from prmr_memory import PRMRTextMemory
from prmr_memory import PRMRImageMemory
from prmr_memory import PRMRVideoMemory


os.makedirs("reports", exist_ok=True)


# -------------------------
# TEXT SAVE / LOAD TEST
# -------------------------

text_memory = PRMRTextMemory("PRMR stores information.")
text_memory.replace_text("stores", "translates")
text_memory.add_text(" It remembers transformation.")

text_memory.save("reports/text_memory_v010.prmr.json")

loaded_text_memory = PRMRTextMemory.load("reports/text_memory_v010.prmr.json")

text_match = text_memory.reconstruct() == loaded_text_memory.reconstruct()


# -------------------------
# IMAGE SAVE / LOAD TEST
# -------------------------

image_memory = PRMRImageMemory(500, 500)
image_memory.add_origin_circle("orb", 100, 250, 40, "cyan")
image_memory.move_object("orb", 120, 0)
image_memory.change_colour("orb", "magenta")
image_memory.resize_object("orb", 70)

image_memory.save("reports/image_memory_v010.prmr.json")

loaded_image_memory = PRMRImageMemory.load("reports/image_memory_v010.prmr.json")

image_match = image_memory.reconstruct_svg() == loaded_image_memory.reconstruct_svg()


# -------------------------
# VIDEO SAVE / LOAD TEST
# -------------------------

video_memory = PRMRVideoMemory(500, 500, 30)
video_memory.add_origin_circle("orb", 80, 250, 35, "cyan")
video_memory.add_motion_rule("orb", 0, 29, 10, 0)
video_memory.add_colour_change_rule("orb", 10, "magenta")
video_memory.add_resize_rule("orb", 20, 60)

video_memory.save("reports/video_memory_v010.prmr.json")

loaded_video_memory = PRMRVideoMemory.load("reports/video_memory_v010.prmr.json")

video_match = video_memory.reconstruct_all_frames() == loaded_video_memory.reconstruct_all_frames()


# -------------------------
# OUTPUT
# -------------------------

print("PRMR MEMORY SAVE / LOAD DEMO V0.10")
print("----------------------------------")

print("\nTEXT MEMORY")
print("Saved file: reports/text_memory_v010.prmr.json")
print("Reconstruction match after load:", text_match)
print("Loaded reconstruction:", loaded_text_memory.reconstruct())

print("\nIMAGE MEMORY")
print("Saved file: reports/image_memory_v010.prmr.json")
print("Reconstruction match after load:", image_match)

with open("reports/loaded_image_reconstruction_v010.svg", "w", encoding="utf-8") as file:
    file.write(loaded_image_memory.reconstruct_svg())

print("Loaded image reconstruction saved: reports/loaded_image_reconstruction_v010.svg")

print("\nVIDEO MEMORY")
print("Saved file: reports/video_memory_v010.prmr.json")
print("Reconstruction match after load:", video_match)

loaded_frames = loaded_video_memory.reconstruct_all_frames()

for index, frame in enumerate(loaded_frames):
    filename = f"reports/loaded_video_frame_{index:03d}_v010.svg"

    with open(filename, "w", encoding="utf-8") as file:
        file.write(frame)

print("Loaded video frames saved: reports/loaded_video_frame_000_v010.svg through loaded_video_frame_029_v010.svg")

print("\nSUMMARY")
print("All save/load tests passed:", text_match and image_match and video_match)