"""Generate small test inputs. All content is made up here, so the repo owns every byte."""
import io
import json
from pathlib import Path

from PIL import Image, ImageDraw


def chart_png(w=1600, h=900) -> bytes:
    im = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(im)
    for i, v in enumerate([120, 340, 260, 410]):
        d.rectangle([200 + i * 300, h - 100 - v, 380 + i * 300, h - 100], fill="steelblue")
        d.text((230 + i * 300, h - 80), f"Q{i + 1}: {v}", fill="black")
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def logo_png(side=48) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (side, side), "orange").save(buf, "PNG")
    return buf.getvalue()


def make_pptx(path: Path, slides=4):
    from pptx import Presentation
    from pptx.util import Inches

    prs = Presentation()
    for n in range(1, slides + 1):
        s = prs.slides.add_slide(prs.slide_layouts[5])
        s.shapes.title.text = f"Quarter review part {n}"
        box = s.shapes.add_textbox(Inches(1), Inches(2), Inches(6), Inches(1))
        box.text_frame.text = f"Revenue grew {10 + n}% in region {n}."
        foot = s.shapes.add_textbox(Inches(0.5), Inches(7), Inches(6), Inches(0.4))
        foot.text_frame.text = "Northwind Labs | Internal use only"
        s.shapes.add_picture(io.BytesIO(logo_png()), Inches(9), Inches(0.2))
        if n == 2:
            s.shapes.add_picture(io.BytesIO(chart_png()), Inches(1), Inches(3), width=Inches(6))
            t = s.shapes.add_table(3, 2, Inches(1), Inches(5), Inches(4), Inches(1)).table
            for r, row in enumerate([["Region", "Revenue"], ["North", "1.2M"], ["South", "0.9M"]]):
                for c, val in enumerate(row):
                    t.cell(r, c).text = val
            s.notes_slide.notes_text_frame.text = "Mention the South dip."
        if n == 3:  # a native PowerPoint chart: data lives in the file, no picture
            from pptx.chart.data import CategoryChartData
            from pptx.enum.chart import XL_CHART_TYPE

            data = CategoryChartData()
            data.categories = ["Q1", "Q2", "Q3"]
            data.add_series("Revenue", (4.7, 5.9, 6.3))
            s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(1), Inches(3), Inches(6), Inches(3), data)
    pic = prs.slides.add_slide(prs.slide_layouts[8])  # "Picture with Caption": the picture sits in a placeholder
    pic.placeholders[1].insert_picture(io.BytesIO(chart_png()))
    pic.shapes.title.text = "Customer photo wall"
    prs.save(path)


def make_pdf(path: Path, pages=3, scanned_last=False):
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(path), pagesize=letter)
    for n in range(1, pages + 1):
        if scanned_last and n == pages:
            c.drawImage(ImageReader(io.BytesIO(chart_png(1200, 1500))), 0, 0, *letter)
        else:
            c.drawString(72, 720, f"Annual report page {n}: margin was {20 + n}.5%.")
            c.drawString(72, 40, "Northwind Labs Annual Report 2026")
            if n == 1:
                c.drawImage(ImageReader(io.BytesIO(chart_png())), 72, 300, 400, 225)
        c.showPage()
    c.save()


PAGE = """<!doctype html><html><head><title>Field notes</title>
<style>.nav{color:red}.hero{margin:0 auto;padding:40px}</style>
<script>window.dataLayer=[];function track(){console.log('x')}</script></head>
<body><nav class="nav"><a href="/">Home</a> <a href="/blog">Blog</a> <a href="/about">About</a></nav>
<article><h1>Field notes on soil moisture</h1>
<p>Across 14 test plots, drip irrigation cut water use by 31 percent compared with sprinklers,
while yields stayed within 2 percent of the control group.</p>
<p>The largest gains came from clay soils, where evaporation losses were highest.
Read the <a href="https://example.org/data?utm_source=newsletter&amp;utm_medium=email&amp;id=42">raw data</a>.</p>
</article><footer>&copy; 2026 Field Notes. <a href="/privacy">Privacy</a></footer></body></html>"""


def make_html(path: Path):
    path.write_text(PAGE)


def make_json(path: Path):
    users = [{"id": i, "name": f"user{i}", "email": f"u{i}@example.com", "active": i % 2 == 0,
              "manager": None, "tags": [], "note": ""} for i in range(1, 21)]
    path.write_text(json.dumps({"users": users}, indent=2))
