"""Build the eval set (all content generated here) and print a results table.

    python scripts/eval.py                 # uses SQUEEZE_BACKEND from the environment
    SQUEEZE_BACKEND=mock python scripts/eval.py   # offline dry run; image text is placeholder
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from squeeze.core import compress  # noqa: E402
from tests import make_fixtures as fx  # noqa: E402


def build(d: Path) -> list[Path]:
    files = {
        "deck.pptx": lambda p: fx.make_pptx(p, slides=12),
        "report.pdf": lambda p: fx.make_pdf(p, pages=8),
        "scanned.pdf": lambda p: fx.make_pdf(p, pages=2, scanned_last=True),
        "page.html": fx.make_html,
        "users.json": fx.make_json,
    }
    out = []
    for name, make in files.items():
        make(d / name)
        out.append(d / name)
    return out


def main():
    fidelity = "--fidelity" in sys.argv
    with tempfile.TemporaryDirectory() as tmp:
        rows = []
        for f in build(Path(tmp)):
            r = compress(str(f), fidelity=fidelity)
            if any(i["class"] == "error" for i in r.images) or "error" in (r.fidelity or {}):
                sys.exit(f"{f.name}: model calls failed; not printing results from a broken run")
            s, fid = r.stats, r.fidelity or {}
            qa = fid.get("probe_qa", {}).get("score")
            rows.append((f.name, s["tokens_before"], s["tokens_after"], s["saved_pct"],
                         fid.get("numbers_kept"), qa))
    print("| File | Tokens before | Tokens after | Saved | Numbers kept | Probe QA |")
    print("|---|---:|---:|---:|---:|---:|")
    for name, b, a, pct, nums, qa in rows:
        show = lambda x: "-" if x is None else f"{x:.0%}"
        print(f"| {name} | {b:,} | {a:,} | {pct}% | {show(nums)} | {show(qa)} |")


if __name__ == "__main__":
    main()
