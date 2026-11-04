"""Deterministic text passes. No model calls; each takes and returns the section list."""
import re
from collections import Counter
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING = re.compile(r"^(utm_\w+|fbclid|gclid|dclid|msclkid|mc_cid|mc_eid|igshid|yclid|_hsenc|_hsmi|ref_src)$", re.I)
URL = re.compile(r"https?://[^\s)\]>\"']+")
DATA_URI = re.compile(r"data:[\w/+.-]+;base64,[A-Za-z0-9+/=]+")
BASE64_RUN = re.compile(r"\b[A-Za-z0-9+/]{120,}={0,2}")
ID = re.compile(r"\b(?:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[0-9a-f]{32,64})\b", re.I)


def whitespace(sections):
    for s in sections:
        lines = [ln.rstrip() for ln in s.text.replace("\r\n", "\n").split("\n")]
        s.text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
        s.text = re.sub(r"(?<=\S)[ \t]{2,}", " ", s.text)  # keep leading indentation: it is meaning in code
    return sections


def blobs(sections):
    """Drop data URIs and long base64 runs: they cost ~3x English per character and mean nothing as text."""
    for s in sections:
        s.text = BASE64_RUN.sub("[binary data removed]", DATA_URI.sub("[inline data removed]", s.text))
    return sections


def _clean_url(m):
    parts = urlsplit(m.group(0))
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not TRACKING.match(k)]
    return urlunsplit(parts._replace(query=urlencode(query)))


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


def repeated_lines(sections, min_sections=3):
    """A line on 3+ sections (footers, slide template text) is kept on its first section only."""
    if len(sections) < min_sections:
        return sections
    seen_in = Counter()
    for s in sections:
        seen_in.update({ln.strip() for ln in s.text.split("\n") if len(ln.strip()) >= 4})
    boiler = {ln for ln, n in seen_in.items() if n >= min_sections}
    kept = set()
    for s in sections:
        out = []
        for ln in s.text.split("\n"):
            key = ln.strip()
            if key in boiler:
                if key in kept:
                    continue
                kept.add(key)
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
