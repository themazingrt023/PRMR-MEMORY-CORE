from pathlib import Path

TARGET = Path("examples/audit_v0441_api_product_integrity.py")

text = TARGET.read_text(encoding="utf-8")

needle = "import json\nimport importlib.util\nfrom pathlib import Path\nfrom datetime import datetime\n"

replacement = """import json
import importlib.util
import os
import sys
from pathlib import Path
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
"""

if needle not in text:
    raise RuntimeError("Could not find expected import block. Patch manually.")

text = text.replace(needle, replacement, 1)

TARGET.write_text(text, encoding="utf-8")

print("Patched V0.44.1 audit import path.")
print("Now run:")
print("python examples/audit_v0441_api_product_integrity.py")