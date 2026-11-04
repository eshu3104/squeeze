"""One function per input type. Each returns (sections, tokens_before).

tokens_before is what the input costs when sent the usual way: the raw text
for HTML and JSON; for PPTX the slide text plus every embedded image; for PDF
the page text plus one page image per page (native PDF input bills both)."""
import io
import json

from PIL import Image as PILImage

from squeeze.core import Image, Section, count_tokens, image_tokens, render
from squeeze.images import MIN_SIDE


MAX_PDF_PAGES = 100  # shortcut: one page image each in memory; raise if real decks need more


def _image(data: bytes) -> Image | None:
    try:
        with PILImage.open(io.BytesIO(data)) as im:
            im.load()  # decode now: Pillow opens EMF/WMF headers but cannot draw them
            w, h = im.size
    except Exception:  # unreadable formats (EMF/WMF) are skipped, not fatal
        return None
    return Image(data, w, h)


def _num(v) -> str:
    return "" if v is None else f"{v:g}" if isinstance(v, float) else str(v)


def _md_table(rows: list[list[str]]) -> str:
    rows = [[str(c).replace("|", "\\|").replace("\n", " ").strip() for c in r] for r in rows]
    head, body = rows[0], rows[1:]
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    lines += ["| " + " | ".join(r) + " |" for r in body]
    return "\n".join(lines)


def pptx(path: str):
    from pptx import Presentation
    from pptx.shapes.group import GroupShape
    from pptx.shapes.picture import Picture  # also covers pictures in layout placeholders

    sections, baseline = [], 0

    def walk(shapes, texts, images):
        for sh in shapes:
            if isinstance(sh, GroupShape):  # not shape_type: it raises on shapes with no geometry
                walk(sh.shapes, texts, images)
            elif sh.has_text_frame and sh.text_frame.text.strip():
                texts.append(sh.text_frame.text.replace("\x0b", "\n"))  # \x0b = soft line break
            elif getattr(sh, "has_table", False):
                texts.append(_md_table([[c.text for c in r.cells] for r in sh.table.rows]))
            elif getattr(sh, "has_chart", False):  # native chart: its data is right there, no model needed
                try:
                    for plot in sh.chart.plots:
                        rows = [["", *map(str, plot.categories)]] + [[s.name, *map(_num, s.values)] for s in plot.series]
                        texts.append("Chart:\n" + _md_table(rows))
                except ValueError:  # 3D, stock and surface charts: python-pptx can't read their data
                    texts.append("[chart: type not readable]")
            elif isinstance(sh, Picture):
                try:
                    im = _image(sh.image.blob)
                except (ValueError, KeyError):  # a picture inserted as "link to file" has no bytes here
                    im = None
                if im:
                    images.append(im)

    for n, slide in enumerate(Presentation(path).slides, 1):
        texts, images = [], []
        walk(slide.shapes, texts, images)
        notes = slide.notes_slide.notes_text_frame if slide.has_notes_slide else None
        if notes is not None and notes.text.strip():
            texts.append("Notes: " + notes.text.replace("\x0b", "\n"))
        baseline += sum(image_tokens(i.width, i.height) for i in images)
        sections.append(Section(f"slide {n}", "\n".join(texts), images))
    return sections, baseline + count_tokens(render(sections))


def pdf(path):  # a path or the PDF's bytes
    import pypdfium2 as pdfium
    import pypdfium2.raw as pdfium_c

    sections, baseline = [], 0
    doc = pdfium.PdfDocument(path)
    if len(doc) > MAX_PDF_PAGES:
        raise ValueError(f"PDF has {len(doc)} pages; Squeeze handles up to {MAX_PDF_PAGES}")
    for n, page in enumerate(doc, 1):
        w, h = page.get_size()  # points
        baseline += image_tokens(int(w * 150 / 72), int(h * 150 / 72))
        text = page.get_textpage().get_text_range().replace("\r\n", "\n")
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


def html(data: bytes):
    import trafilatura
    from trafilatura.utils import decode_file

    raw = decode_file(data)  # honours the page's charset instead of assuming UTF-8
    md = trafilatura.extract(raw, output_format="markdown", include_tables=True, include_links=True) or ""
    return [Section("", md)], count_tokens(raw)


def _prune(x):
    """Drop object keys whose value is null or empty. Lists keep every item: position is meaning."""
    if isinstance(x, dict):
        out = {k: _prune(v) for k, v in x.items()}
        return {k: v for k, v in out.items() if v not in (None, "", [], {})}
    if isinstance(x, list):
        return [_prune(v) for v in x]
    return x


def _render_json(x) -> str:
    # Uniform arrays of flat objects read best (and cheapest) as a table.
    if (isinstance(x, list) and len(x) >= 5 and all(isinstance(r, dict) for r in x)
            and all(not isinstance(v, (dict, list)) and "\n" not in str(v) for r in x for v in r.values())):
        keys = list(dict.fromkeys(k for r in x for k in r))
        return _md_table([keys] + [[r.get(k, "") for k in keys] for r in x])
    if isinstance(x, dict) and len(x) == 1 and isinstance(next(iter(x.values())), list):
        (k, v), = x.items()
        return f"{k}:\n{_render_json(v)}"
    return json.dumps(x, separators=(",", ":"), ensure_ascii=False)


def json_doc(raw: str):
    return [Section("", _render_json(_prune(json.loads(raw))))], count_tokens(raw)
