"""compress(): extract -> clean -> images -> render, with real token counts at every step."""
import math
from dataclasses import dataclass, field
from pathlib import Path

import tiktoken

from squeeze import passes

ENC = tiktoken.get_encoding("o200k_base")


def count_tokens(text: str) -> int:
    return len(ENC.encode(text, disallowed_special=()))


def image_tokens(width: int, height: int) -> int:
    """Visual tokens for one image on Claude's standard tier: 28px patches,
    long edge <= 1568 px and <= 1568 tokens, downscaled with aspect kept."""
    s = min(1.0, 1568 / max(width, height), math.sqrt(1568 * 784 / (width * height)))
    while True:
        w, h = max(1, int(width * s)), max(1, int(height * s))
        t = math.ceil(w / 28) * math.ceil(h / 28)
        if t <= 1568:
            return t
        s *= 0.99


@dataclass
class Image:
    data: bytes
    width: int
    height: int


@dataclass
class Section:
    anchor: str  # e.g. "slide 3", "p12"; "" for single-section inputs
    text: str
    images: list[Image] = field(default_factory=list)


@dataclass
class Result:
    text: str
    stats: dict
    images: list[dict] = field(default_factory=list)  # one entry per image: class, description, tokens
    fidelity: dict | None = None


def render(sections: list[Section]) -> str:
    parts = []
    for s in sections:
        body = s.text.strip("\n")  # not strip(): a first line's indentation can be code
        if not body.strip():
            continue
        parts.append(f"[{s.anchor}]\n{body}" if s.anchor else body)
    return "\n\n".join(parts) + "\n"


def _text_file(raw: str):
    return [Section("", raw)], count_tokens(raw)


def extract(source: str) -> tuple[str, list[Section], int]:
    """Return (kind, sections, tokens_before). kind names the input for prompts and the UI."""
    from squeeze import extractors

    if source.startswith(("http://", "https://")):
        import httpx

        try:
            r = httpx.get(source, follow_redirects=True, timeout=30, headers={"User-Agent": "squeeze/0.1"})
            r.raise_for_status()
        except (httpx.HTTPError, httpx.InvalidURL) as e:
            raise ValueError(f"could not fetch {source}: {e}") from e
        ctype = r.headers.get("content-type", "")
        if "pdf" in ctype or r.content[:5] == b"%PDF-":  # many hosts label PDFs octet-stream
            return "PDF", *_guard(extractors.pdf, r.content)
        if "json" in ctype or r.url.path.endswith(".json"):  # raw GitHub serves JSON as text/plain
            return "JSON response", *_guard(extractors.json_doc, r.text)
        if ctype.startswith("text/plain"):
            return "text file", *_text_file(r.text)
        return "web page", *extractors.html(r.content)

    path = Path(source)
    suffix = path.suffix.lower()
    if suffix == ".pptx":
        return "slide deck", *_guard(extractors.pptx, source)
    if suffix == ".pdf":
        return "PDF", *_guard(extractors.pdf, source)
    if suffix in (".html", ".htm"):
        return "web page", *extractors.html(path.read_bytes())
    if suffix == ".json":
        return "JSON document", *_guard(extractors.json_doc, path.read_text(encoding="utf-8-sig"))
    if suffix in (".txt", ".md"):
        return "text file", *_text_file(path.read_text(encoding="utf-8", errors="replace"))
    raise ValueError(f"unsupported input type {suffix or source!r}: use .pptx, .pdf, .html, .json, .txt, .md or a URL")


def _guard(fn, arg):
    """Corrupt, encrypted or malformed files become a clear ValueError instead of a crash."""
    try:
        return fn(arg)
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"could not read this file ({type(e).__name__}): {str(e)[:160]}") from e


def compress(source: str, images: str = "describe", fidelity: bool = False) -> Result:
    """images: describe | none (see images.run). fidelity: also run Muse Spark probe QA."""
    from squeeze import fidelity as check
    from squeeze import images as image_pass

    kind, sections, before = extract(source)
    original = render(sections)  # extracted text, before any pass: the reference for fidelity
    if not original.strip() and not any(s.images for s in sections):
        raise ValueError("no readable content found (a page that needs JavaScript, or an empty file?)")

    by_pass = {}
    current = count_tokens(original)
    # PPTX bills each embedded image; credit that to the image step. A PDF's baseline is page images instead.
    img_cost = sum(image_tokens(i.width, i.height) for s in sections for i in s.images) if kind == "slide deck" else 0
    by_pass["extract"] = before - current - img_cost

    for name, fn in passes.TEXT_PASSES:  # before images, so model-written text is never edited
        sections = fn(sections)
        after = count_tokens(render(sections))
        by_pass[name] = current - after
        current = after

    report = image_pass.run(sections, kind, keep=images)
    text = render(sections)
    after = count_tokens(text)
    by_pass["images"] = img_cost + current - after
    fid = {"numbers_kept": check.numbers_kept(original, text)}
    if fidelity:
        try:
            fid["probe_qa"] = check.probe_qa(original, text)
        except Exception as e:  # a failed check must not lose the compression result
            fid["error"] = str(e)[:200]
    stats = {
        "source": str(source),
        "kind": kind,
        "tokens_before": before,
        "tokens_after": after,
        "saved_pct": round(100 * (before - after) / before, 1) if before else 0.0,
        "saved_by_pass": by_pass,
        "image_model_calls": sum(r["called"] for r in report),
    }
    return Result(text=text, stats=stats, images=report, fidelity=fid)
