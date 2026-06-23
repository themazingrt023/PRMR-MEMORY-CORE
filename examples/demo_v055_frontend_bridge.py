import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from prmr.product.frontend_demo_bridge_v055 import cli


if __name__ == "__main__":
    raise SystemExit(cli())
