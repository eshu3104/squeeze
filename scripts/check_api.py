"""One real Muse Spark call with an image, to confirm your key, URL and request format.

    python scripts/check_api.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from squeeze import images, muse  # noqa: E402
from squeeze.core import Image, Section  # noqa: E402
from tests.make_fixtures import chart_png  # noqa: E402

muse.CACHE = Path(".squeeze-cache/check")  # never reuse an old answer here
for f in muse.CACHE.glob("*.json"):
    f.unlink()

print(f"backend: {muse.backend()}")
s = [Section("slide 1", "Revenue by quarter, 2026", [Image(chart_png(), 1600, 900)])]
entry = images.run(s, "slide deck")[0]
if entry["class"] == "error":
    print("FAILED:", entry["error"])
    sys.exit(1)
print(f"class: {entry['class']}\n{entry['description']}\nOK: Muse Spark answered.")
