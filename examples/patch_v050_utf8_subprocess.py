from pathlib import Path

V050 = Path("examples/run_whole_core_truth_gauntlet_v050.py")

text = V050.read_text(encoding="utf-8")

# Ensure os is imported for environment patch.
if "import os" not in text:
    text = text.replace("import json\n", "import json\nimport os\n")

old = '''def run_script(path: Path):
    completed = subprocess.run(
        ["python", str(path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
'''

new = '''def run_script(path: Path):
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    completed = subprocess.run(
        ["python", str(path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
'''

if old not in text:
    raise SystemExit("Could not find run_script subprocess block to patch.")

text = text.replace(old, new)

V050.write_text(text, encoding="utf-8")

print("Patched V0.50 to force UTF-8 child process output.")
print("Now rerun:")
print("python examples/run_whole_core_truth_gauntlet_v050.py")