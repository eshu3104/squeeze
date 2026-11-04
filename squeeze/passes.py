"""Deterministic text passes. No model calls; each takes and returns the section list."""
import re
from collections import Counter

TRACKING = re.compile(r"^(utm_\w+|fbclid|gclid|dclid|msclkid|mc_cid|mc_eid|igshid|yclid|_hsenc|_hsmi|ref_src)$", re.I)
URL = re.compile(r"https?://[^\s)\]>\"']+")
DATA_URI = re.compile(r"data:[\w/+.-]+;base64,[A-Za-z0-9+/=]+")
# Mixed case and a digit, not inside a word or URL: real base64, not hashes, DNA or space-less PDF text.
BASE64_RUN = re.compile(r"(?<![\w.:/-])(?=[A-Za-z0-9+/]*[a-z])(?=[A-Za-z0-9+/]*[A-Z])(?=[A-Za-z0-9+/]*\d)[A-Za-z0-9+/]{120,}={0,2}")
ID = re.compile(r"\b(?:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[0-9a-f]{32,64})\b", re.I)


def whitespace(sections):
    for s in sections:
        lines = [ln.rstrip() for ln in s.text.replace("\r\n", "\n").split("\n")]
        # Only trailing spaces and blank runs: spacing inside a line can be columns or code.
        s.text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip("\n")
    return sections


def blobs(sections):
    """Drop data URIs and long base64 runs: they cost ~3x English per character and mean nothing as text."""
    for s in sections:
        s.text = BASE64_RUN.sub("[binary data removed]", DATA_URI.sub("[inline data removed]", s.text))
    return sections


def _clean_url(m):
    # Plain string surgery: decoding and re-encoding would change (and lengthen) URLs with no tracking at all.
    url, hash_, frag = m.group(0).partition("#")
    base, _, query = url.partition("?")
    kept = [p for p in query.split("&") if p and not TRACKING.match(p.split("=", 1)[0])]
    return base + ("?" + "&".join(kept) if kept else "") + hash_ + frag


def tracking_urls(sections):
    for s in sections:
        s.text = URL.sub(_clean_url, s.text)
    return sections


def alias_ids(sections):
    """Replace UUIDs and long hashes seen 2+ times with {idN}; a legend in the last section keeps them recoverable."""
    counts = Counter(m.group(0) for s in sections for m in ID.finditer(s.text))
    repeated = [v for v, n in counts.items() if n >= 2]
    if not repeated:
        return sections
    names = {v: f"{{id{i}}}" for i, v in enumerate(repeated, 1)}
    for s in sections:
        s.text = ID.sub(lambda m: names.get(m.group(0), m.group(0)), s.text)
    sections[-1].text += "\n\nIDs: " + "; ".join(f"{n} = {v}" for v, n in names.items())
    return sections


def _plain(ln):
    """Not a table row or code: those repeat legitimately and must stay."""
    return len(ln.strip()) >= 4 and not ln.startswith((" ", "\t", "|", "`"))


def _edges(text):
    # Labels Squeeze adds itself (speaker notes, chart data) are never a footer, so look past them.
    lines = [ln for ln in text.split("\n") if _plain(ln) and not ln.startswith(("Notes:", "Chart:"))]
    return {ln.strip() for ln in lines[:1] + lines[-1:]}


def repeated_lines(sections):
    """A line that opens or closes 3+ sections is a header or footer: kept once, marked, where it first appears."""
    if len(sections) < 3:
        return sections
    seen_in = Counter(ln for s in sections for ln in _edges(s.text))
    lines_of = [{ln.strip() for ln in s.text.split("\n")} for s in sections]
    boiler = {ln: sum(ln in ls for ls in lines_of) for ln, n in seen_in.items() if n >= 3}
    kept = set()
    for s in sections:
        out = []
        for ln in s.text.split("\n"):
            key = ln.strip()
            if key in boiler and _plain(ln):
                if key in kept:
                    continue
                kept.add(key)
                ln = f"{ln} [repeated {boiler[key]}x]"
            out.append(ln)
        s.text = "\n".join(out)
    return sections


# Order matters: strip blobs and URLs before counting repeats, whitespace last.
TEXT_PASSES = [
    ("blobs", blobs),
    ("tracking_urls", tracking_urls),
    ("alias_ids", alias_ids),
    ("repeated_lines", repeated_lines),
    ("whitespace", whitespace),
]
