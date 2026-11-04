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


def render(sections: list[Section]) -> str:
    parts = []
    for s in sections:
        body = s.text.strip()
        if not body:
            continue
        parts.append(f"[{s.anchor}]\n{body}" if s.anchor else body)
    return "\n\n".join(parts) + "\n"


def extract(source: str) -> tuple[str, list[Section]]:
    """Return (kind, sections). Kinds grow as extractors are added."""
    path = Path(source)
    if path.suffix.lower() in {".txt", ".md"}:
        return "text", [Section("", path.read_text(encoding="utf-8", errors="replace"))]
    raise ValueError(f"unsupported input: {source}")


def compress(source: str) -> Result:
    kind, sections = extract(source)
    text_before = count_tokens(render(sections))
    img_before = sum(image_tokens(i.width, i.height) for s in sections for i in s.images)

    by_pass = {}
    current = text_before
    for name, fn in passes.TEXT_PASSES:
        sections = fn(sections)
        after = count_tokens(render(sections))
        by_pass[name] = current - after
        current = after

    text = render(sections)
    after = count_tokens(text)
    before = text_before + img_before
    stats = {
        "source": str(source),
        "kind": kind,
        "tokens_before": before,
        "tokens_after": after,
        "saved_pct": round(100 * (before - after) / before, 1) if before else 0.0,
        "saved_by_pass": by_pass,
    }
    return Result(text=text, stats=stats)
