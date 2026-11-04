"""Image pass: Muse Spark decides what each image is worth and replaces it with text."""
import base64
import io

import imagehash
from PIL import Image as PILImage

from squeeze import muse
from squeeze.core import count_tokens, image_tokens

MIN_SIDE = 64
MAX_SIDE = 1024

PROMPT = """You see one image taken from a {where}. Text near it: \"\"\"{context}\"\"\"
Classify it:
- "informative": a chart, diagram, table, screenshot or photo that carries content
- "decorative": a logo, icon, stock photo, background or ornament
- "text": an image that is mostly words
Reply with JSON only: {{"class": "...", "description": "..."}}.
description rules: for a chart, give its data as a compact Markdown table with a one-line title;
for "text", transcribe the words; otherwise state the facts a reader needs, keep every number
and label, no visual adjectives, at most 80 words. For "decorative", at most 5 words."""


def _png(img, max_side=MAX_SIDE) -> tuple[bytes, PILImage.Image]:
    pil = PILImage.open(io.BytesIO(img.data)).convert("RGB")
    pil.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    pil.save(buf, "PNG")
    return buf.getvalue(), pil


def _thumb(pil) -> str:
    t = pil.copy()
    t.thumbnail((240, 240))
    buf = io.BytesIO()
    t.save(buf, "JPEG", quality=70)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def run(sections, where: str, keep: str = "describe") -> list[dict]:
    """keep: "describe" drops decorative images, "all" keeps every description, "none" drops all images.
    Appends image text to each section and returns one report entry per image."""
    report, by_hash = [], {}
    for s in sections:
        for img in s.images:
            entry = {"anchor": s.anchor, "tokens_as_image": image_tokens(img.width, img.height),
                     "cached": False, "called": False, "thumb": None}
            if keep == "none":
                entry.update({"class": "dropped", "description": ""})
            elif min(img.width, img.height) < MIN_SIDE:
                entry.update({"class": "decorative", "description": "tiny graphic"})
            else:
                png, pil = _png(img)
                entry["thumb"] = _thumb(pil)
                h = str(imagehash.phash(pil))
                if h in by_hash:  # same picture again (template art, repeated logo): no second call
                    entry.update({k: by_hash[h][k] for k in ("class", "description")}, cached=True)
                else:
                    try:
                        data, cached = muse.ask_json(PROMPT.format(where=where, context=s.text[:600]), png)
                        cls = data.get("class", "informative")
                        entry.update({"class": cls if cls in ("informative", "decorative", "text") else "informative",
                                      "description": str(data.get("description", "")).strip(),
                                      "cached": cached, "called": not cached})
                    except (muse.MuseError, OSError) as e:  # model down: say so in the output, never guess
                        entry.update({"class": "error", "description": "", "error": str(e)[:200]})
                    by_hash[h] = entry
            show = entry["class"] in ("informative", "text", "error") or (keep == "all" and entry["class"] == "decorative")
            if show:
                body = entry["description"] or "image omitted: model unavailable"
                s.text += f"\n[image: {body}]" if "\n" not in body else f"\n[image]\n{body}"
            entry["tokens_as_text"] = count_tokens(body) if show else 0
            report.append(entry)
        s.images = []
    return report
