import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from squeeze.core import compress


def main(argv=None):
    p = argparse.ArgumentParser(prog="squeeze", description="Compress files and URLs into compact, LLM-ready Markdown.")
    p.add_argument("inputs", nargs="+", help="files or URLs")
    p.add_argument("--images", choices=["describe", "all", "none"], default="describe",
                   help="describe: Muse Spark describes useful images and drops decorative ones (default)")
    p.add_argument("--fidelity", action="store_true", help="also check facts survived (3 extra model calls)")
    p.add_argument("--out", default="out", help="folder for <name>.md and <name>.manifest.json")
    args = p.parse_args(argv)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for src in args.inputs:
        try:
            r = compress(src, images=args.images, fidelity=args.fidelity)
        except (ValueError, OSError) as e:
            print(f"{src}: {e}", file=sys.stderr)
            continue
        stem = Path(src.rstrip("/")).stem or "page"
        (out / f"{stem}.md").write_text(r.text)
        manifest = asdict(r)
        manifest.pop("text")
        for im in manifest["images"]:
            im.pop("thumb", None)
        (out / f"{stem}.manifest.json").write_text(json.dumps(manifest, indent=2))
        s = r.stats
        print(f"{src}: {s['tokens_before']:,} -> {s['tokens_after']:,} tokens ({s['saved_pct']}% smaller) -> {out / (stem + '.md')}")


if __name__ == "__main__":
    main()
