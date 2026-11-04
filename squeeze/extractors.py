"""One function per input type. Each returns (sections, tokens_before).

tokens_before is what the input costs when sent the usual way: the raw text
for HTML and JSON; for PPTX the slide text plus every embedded image; for PDF
the page text plus one page image per page (native PDF input bills both)."""
import io
import json

from PIL import Image as PILImage

from squeeze.core import Image, Section, count_tokens, image_tokens, render

MIN_SIDE = 64  # smaller images are icons or bullets; never worth a model call


def _image(data: bytes) -> Image | None:
    try:
        with PILImage.open(io.BytesIO(data)) as im:
            w, h = im.size
    except Exception:  # unreadable formats (EMF/WMF) are skipped, not fatal
        return None
    return Image(data, w, h)


def _md_table(rows: list[list[str]]) -> str:
    rows = [[str(c).replace("|", "\\|").replace("\n", " ").strip() for c in r] for r in rows]
    head, body = rows[0], rows[1:]
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    lines += ["| " + " | ".join(r) + " |" for r in body]
    return "\n".join(lines)


def pptx(path: str):
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    sections, baseline = [], 0

    def walk(shapes, texts, images):
        for sh in shapes:
            if sh.shape_type == MSO_SHAPE_TYPE.GROUP:
                walk(sh.shapes, texts, images)
            elif sh.has_text_frame and sh.text_frame.text.strip():
                texts.append(sh.text_frame.text)
            elif getattr(sh, "has_table", False) and sh.has_table:
                texts.append(_md_table([[c.text for c in r.cells] for r in sh.table.rows]))
            elif sh.shape_type == MSO_SHAPE_TYPE.PICTURE:
                im = _image(sh.image.blob)
                if im:
                    images.append(im)

    for n, slide in enumerate(Presentation(path).slides, 1):
        texts, images = [], []
        walk(slide.shapes, texts, images)
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame.text.strip():
            texts.append("Notes: " + slide.notes_slide.notes_text_frame.text)
        baseline += sum(image_tokens(i.width, i.height) for i in images)
        sections.append(Section(f"slide {n}", "\n".join(texts), images))
    return sections, baseline + count_tokens(render(sections))


def pdf(path: str):
    import pypdfium2 as pdfium
    import pypdfium2.raw as pdfium_c

    sections, baseline = [], 0
    doc = pdfium.PdfDocument(path)
    for n, page in enumerate(doc, 1):
        w, h = page.get_size()  # points
        baseline += image_tokens(int(w * 150 / 72), int(h * 150 / 72))
        text = page.get_textpage().get_text_range()
        images = []
        if text.strip():
            for obj in page.get_objects(filter=[pdfium_c.FPDF_PAGEOBJ_IMAGE]):
                pil = obj.get_bitmap().to_pil()
                if min(pil.size) >= MIN_SIDE:
                    buf = io.BytesIO()
                    pil.convert("RGB").save(buf, "PNG")
                    images.append(Image(buf.getvalue(), *pil.size))
        else:  # scanned page: the whole page is the image
            pil = page.render(scale=150 / 72).to_pil()
            buf = io.BytesIO()
            pil.convert("RGB").save(buf, "PNG")
            images.append(Image(buf.getvalue(), *pil.size))
        sections.append(Section(f"p{n}", text, images))
    doc.close()
    return sections, baseline + count_tokens(render(sections))


def html(raw: str):
    import trafilatura

    md = trafilatura.extract(raw, output_format="markdown", include_tables=True, include_links=True) or ""
    return [Section("", md)], count_tokens(raw)


def _prune(x):
    """Drop null, empty strings, empty lists and dicts; truncate very long strings."""
    if isinstance(x, dict):
        out = {k: _prune(v) for k, v in x.items()}
        return {k: v for k, v in out.items() if v not in (None, "", [], {})}
    if isinstance(x, list):
        return [v for v in (_prune(v) for v in x) if v not in (None, "", [], {})]
    if isinstance(x, str) and len(x) > 500:
        return x[:500] + f"…[{len(x)} chars]"
    return x


def _render_json(x) -> str:
    # Uniform arrays of flat objects read best (and cheapest) as a table.
    if (isinstance(x, list) and len(x) >= 5 and all(isinstance(r, dict) for r in x)
            and all(not isinstance(v, (dict, list)) for r in x for v in r.values())):
        keys = list(dict.fromkeys(k for r in x for k in r))
        return _md_table([keys] + [[r.get(k, "") for k in keys] for r in x])
    if isinstance(x, dict) and len(x) == 1:
        (k, v), = x.items()
        return f"{k}:\n{_render_json(v)}"
    return json.dumps(x, separators=(",", ":"), ensure_ascii=False)


def json_doc(raw: str):
    return [Section("", _render_json(_prune(json.loads(raw))))], count_tokens(raw)
