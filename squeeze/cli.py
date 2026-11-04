import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from squeeze.core import compress


def main(argv=None):
    p = argparse.ArgumentParser(prog="squeeze", description="Compress files and URLs into compact, LLM-ready Markdown.")
    p.add_argument("inputs", nargs="+", help="files or URLs")
    p.add_argument("--images", choices=["describe", "none"], default="describe",
                   help="describe: Muse Spark describes useful images, drops decorative ones (default); none: drop all")
    p.add_argument("--fidelity", action="store_true", help="also check facts survived (3 extra model calls)")
    p.add_argument("--out", default="out", help="folder for <file>.md and <file>.manifest.json")
    args = p.parse_args(argv)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for src in args.inputs:
        try:
            r = compress(src, images=args.images, fidelity=args.fidelity)
        except Exception as e:  # one bad input must not stop the batch
            print(f"{src}: {e}", file=sys.stderr)
            continue
        stem = Path(src.rstrip("/")).name or "page"  # deck.pptx.md and deck.pdf.md never collide
        (out / f"{stem}.md").write_text(r.text)
        manifest = asdict(r)
        manifest.pop("text")
        for im in manifest["images"]:
            im.pop("thumb", None)
        (out / f"{stem}.manifest.json").write_text(json.dumps(manifest, indent=2))
        s, u = r.stats, r.stats["model_usage"]
        spent = sum(u[k]["input_tokens"] + u[k]["output_tokens"] for k in ("image", "fact_check"))
        cost = f", Muse Spark used {spent:,}" if u["calls"] and u["complete"] else ""
        print(f"{src}: {s['tokens_before']:,} -> {s['tokens_after']:,} tokens ({s['saved_pct']}% smaller{cost}) -> {out / (stem + '.md')}")


if __name__ == "__main__":
    main()
