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
        body = s.text.strip()
        if not body:
            continue
        parts.append(f"[{s.anchor}]\n{body}" if s.anchor else body)
    return "\n\n".join(parts) + "\n"


def extract(source: str) -> tuple[str, list[Section], int]:
    """Return (kind, sections, tokens_before). kind names the input for prompts and the UI."""
    from squeeze import extractors

    if source.startswith(("http://", "https://")):
        import httpx

        try:
            r = httpx.get(source, follow_redirects=True, timeout=30, headers={"User-Agent": "squeeze/0.1"})
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise ValueError(f"could not fetch {source}: {e}") from e
        if "json" in r.headers.get("content-type", ""):
            return "JSON response", *extractors.json_doc(r.text)
        return "web page", *extractors.html(r.text)

    path = Path(source)
    suffix = path.suffix.lower()
    if suffix == ".pptx":
        return "slide deck", *extractors.pptx(source)
    if suffix == ".pdf":
        return "PDF", *extractors.pdf(source)
    if suffix in (".html", ".htm"):
        return "web page", *extractors.html(path.read_text(encoding="utf-8", errors="replace"))
    if suffix == ".json":
        try:
            return "JSON document", *extractors.json_doc(path.read_text(encoding="utf-8"))
        except ValueError as e:
            raise ValueError(f"not valid JSON: {e}") from e
    if suffix in (".txt", ".md"):
        raw = path.read_text(encoding="utf-8", errors="replace")
        return "text file", [Section("", raw)], count_tokens(raw)
    raise ValueError(f"unsupported input type {suffix or source!r}: use .pptx, .pdf, .html, .json, .txt, .md or a URL")


def compress(source: str, images: str = "describe", fidelity: bool = False) -> Result:
    """images: describe | all | none (see images.run). fidelity: also run Muse Spark probe QA."""
    from squeeze import fidelity as check
    from squeeze import images as image_pass

    kind, sections, before = extract(source)
    original = render(sections)  # extracted text, before any pass: the reference for fidelity

    by_pass = {}
    current = count_tokens(original)
    by_pass["extract"] = before - current

    report = image_pass.run(sections, kind, keep=images)
    after = count_tokens(render(sections))
    by_pass["images"] = current - after  # negative: descriptions add text back
    current = after

    for name, fn in passes.TEXT_PASSES:
        sections = fn(sections)
        after = count_tokens(render(sections))
        by_pass[name] = current - after
        current = after

    text = render(sections)
    after = count_tokens(text)
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
