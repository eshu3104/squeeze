"""Build the demo files used in the video. Every word and picture is made up here.

    python scripts/make_demo.py      # writes demo/
"""
import io
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parents[1] / "demo"
FONT_DIR = Path("/usr/share/fonts/opentype/inter")


def font(size, bold=False):
    try:
        return ImageFont.truetype(str(FONT_DIR / ("Inter-Bold.otf" if bold else "Inter-Regular.otf")), size)
    except OSError:
        return ImageFont.load_default(size)


def png(im) -> bytes:
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def logo() -> bytes:
    im = Image.new("RGB", (56, 56), "#0f766e")
    ImageDraw.Draw(im).text((14, 10), "N", font=font(30, True), fill="white")
    return png(im)


def bar_chart() -> bytes:
    w, h = 1600, 900
    im = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(im)
    d.text((80, 50), "Revenue by region, Q3 2026 ($M)", font=font(44, True), fill="#111827")
    data = [("North", 4.8), ("South", 3.1), ("East", 5.6), ("West", 2.4), ("Online", 6.9)]
    top, base = 180, 780
    for i, (name, v) in enumerate(data):
        x = 140 + i * 280
        y = base - v / 7.5 * (base - top)
        d.rectangle([x, y, x + 170, base], fill="#0f766e" if name == "Online" else "#94a3b8")
        d.text((x + 40, y - 56), f"{v}", font=font(40, True), fill="#111827")
        d.text((x + 20, base + 24), name, font=font(34), fill="#374151")
    d.line([110, base, w - 80, base], fill="#9ca3af", width=3)
    return png(im)


def dashboard() -> bytes:
    w, h = 1400, 800
    im = Image.new("RGB", (w, h), "#f8fafc")
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, w, 70], fill="#0f172a")
    d.text((30, 18), "Northwind Ops  |  Fulfilment", font=font(28, True), fill="white")
    cards = [("Orders today", "12,408"), ("On-time rate", "96.2%"), ("Avg ship time", "1.8 days"), ("Returns", "2.1%")]
    for i, (k, v) in enumerate(cards):
        x = 30 + i * 340
        d.rounded_rectangle([x, 110, x + 310, 260], 16, fill="white", outline="#e2e8f0", width=2)
        d.text((x + 24, 134), k, font=font(24), fill="#64748b")
        d.text((x + 24, 180), v, font=font(48, True), fill="#0f172a")
    d.rounded_rectangle([30, 300, w - 30, h - 30], 16, fill="white", outline="#e2e8f0", width=2)
    d.text((60, 324), "Warehouse backlog (orders)", font=font(26, True), fill="#0f172a")
    pts = [(80 + i * 105, 700 - v) for i, v in enumerate([120, 180, 150, 260, 300, 240, 330, 280, 210, 190, 160, 140])]
    d.line(pts, fill="#0f766e", width=6)
    d.text((pts[6][0] - 40, pts[6][1] - 50), "peak 2,940 on Sep 14", font=font(22), fill="#0f766e")
    return png(im)


def team_photo() -> bytes:
    # A decorative "office" picture: soft shapes, no information.
    w, h = 1200, 800
    im = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(im)
    for y in range(h):
        d.line([0, y, w, y], fill=(200 - y // 8, 214 - y // 10, 230 - y // 12))
    for i, c in enumerate(["#f59e0b", "#10b981", "#6366f1", "#ef4444", "#14b8a6"]):
        d.ellipse([150 + i * 200, 300, 290 + i * 200, 440], fill=c)
        d.rounded_rectangle([130 + i * 200, 450, 310 + i * 200, 760], 40, fill=c)
    return png(im)


def scanned_memo() -> bytes:
    w, h = 1275, 1650  # letter at 150 dpi
    im = Image.new("RGB", (w, h), "#fbfaf6")
    d = ImageDraw.Draw(im)
    lines = ["MEMO: Carrier contract renewal", "", "To: Operations leadership", "Date: October 2, 2026", "",
             "We recommend renewing with Atlas Freight for 24 months.",
             "Their bid of $2.35 per parcel is 11% below the next offer.",
             "Penalty clauses cap late deliveries at 3% of volume.",
             "", "Decision needed by October 20, 2026.", "", "Signed, M. Okafor, Head of Logistics"]
    for i, ln in enumerate(lines):
        d.text((120, 150 + i * 70), ln, font=font(40, bold=i == 0), fill="#1f2937")
    return png(im.rotate(0.6, fillcolor="#fbfaf6"))


def make_deck(path: Path):
    from pptx import Presentation
    from pptx.chart.data import CategoryChartData
    from pptx.enum.chart import XL_CHART_TYPE
    from pptx.util import Inches, Pt

    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    slides = [
        ("Q3 2026 Business Review", "Northwind Labs, operations and growth", None),
        ("Headline numbers", "Revenue reached $22.8M, up 14% on Q2.\nGross margin held at 41%.\nOnline overtook every region for the first time.", "bar"),
        ("Regional detail", None, "table"),
        ("Monthly active customers", "Growth slowed in September after the price change.", "line"),
        ("Fulfilment", "On-time delivery improved to 96.2%.\nBacklog peaked mid-September, then cleared.", "dash"),
        ("Our team", "Hiring: 6 engineers and 4 analysts joined in Q3.", "photo"),
        ("Q4 priorities", "1. Renew the Atlas Freight contract (decision by Oct 20)\n2. Launch the loyalty programme in November\n3. Cut average ship time below 1.5 days", None),
        ("Questions", "ops@northwind.example", None),
    ]
    for n, (title, body, kind) in enumerate(slides, 1):
        s = prs.slides.add_slide(prs.slide_layouts[6])
        s.shapes.add_picture(io.BytesIO(logo()), Inches(12.4), Inches(0.3))
        tb = s.shapes.add_textbox(Inches(0.6), Inches(0.4), Inches(11), Inches(1)).text_frame
        tb.text = title
        tb.paragraphs[0].runs[0].font.size = Pt(36)
        tb.paragraphs[0].runs[0].font.bold = True
        if body:
            s.shapes.add_textbox(Inches(0.6), Inches(1.5), Inches(6.2), Inches(3)).text_frame.text = body
        if kind == "bar":
            s.shapes.add_picture(io.BytesIO(bar_chart()), Inches(6.8), Inches(1.5), width=Inches(6))
        elif kind == "table":
            rows = [["Region", "Revenue", "vs Q2", "Margin"], ["North", "$4.8M", "+9%", "43%"], ["South", "$3.1M", "-4%", "37%"],
                    ["East", "$5.6M", "+12%", "44%"], ["West", "$2.4M", "+2%", "35%"], ["Online", "$6.9M", "+38%", "42%"]]
            t = s.shapes.add_table(len(rows), 4, Inches(0.6), Inches(1.6), Inches(10), Inches(3.5)).table
            for r, row in enumerate(rows):
                for c, v in enumerate(row):
                    t.cell(r, c).text = v
        elif kind == "line":
            data = CategoryChartData()
            data.categories = ["Jul", "Aug", "Sep"]
            data.add_series("Active customers (thousands)", (182, 197, 199))
            s.shapes.add_chart(XL_CHART_TYPE.LINE_MARKERS, Inches(6.8), Inches(1.5), Inches(6), Inches(4.5), data)
        elif kind == "dash":
            s.shapes.add_picture(io.BytesIO(dashboard()), Inches(6.6), Inches(1.5), width=Inches(6.3))
        elif kind == "photo":
            s.shapes.add_picture(io.BytesIO(team_photo()), Inches(6.8), Inches(1.5), width=Inches(5.8))
        foot = s.shapes.add_textbox(Inches(0.6), Inches(6.9), Inches(8), Inches(0.4)).text_frame
        foot.text = "Northwind Labs | Confidential | Q3 2026 Business Review"
        if n == 2:
            s.notes_slide.notes_text_frame.text = "Stress that Online grew 38% while South shrank."
    prs.save(path)


def make_pdf(path: Path):
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(path), pagesize=letter)
    pages = [
        ["Northwind Labs Annual Logistics Report 2026", "", "Parcels shipped: 4.6 million (+18%).",
         "Average cost per parcel fell from $2.71 to $2.48.", "Carbon per parcel down 9% after the EV van pilot."],
        ["Carrier performance", "", "Atlas Freight delivered 97.1% on time.", "Bluebird Post delivered 93.4% on time.",
         "Late-delivery refunds totalled $184,000."],
        ["Warehouses", "", "Reno handled 41% of volume; Columbus 36%; Atlanta 23%.",
         "Pick accuracy rose to 99.6% after scanner upgrades."],
        ["Outlook", "", "2027 target: 5.3 million parcels at $2.40 each.", "Open question: second West Coast site."],
    ]
    for n, lines in enumerate(pages, 1):
        c.setFont("Helvetica", 9)
        c.drawString(72, 750, "Northwind Labs | Annual Logistics Report 2026 | Internal")
        c.setFont("Helvetica-Bold" if n == 1 else "Helvetica", 18 if n == 1 else 12)
        for i, ln in enumerate(lines):
            c.drawString(72, 700 - i * 22, ln)
            c.setFont("Helvetica", 12)
        if n == 1:
            c.drawImage(ImageReader(io.BytesIO(bar_chart())), 72, 260, 468, 263)
        c.setFont("Helvetica", 9)
        c.drawString(72, 40, f"Page {n}")
        c.showPage()
    c.drawImage(ImageReader(io.BytesIO(scanned_memo())), 0, 0, *letter)  # a scanned page: no text layer
    c.showPage()
    c.save()


NAV = "".join(f'<li><a href="/section/{s}?ref=nav">{s.title()}</a></li>' for s in
              ["news", "farming", "climate", "water", "tech", "markets", "opinion", "video", "podcasts", "events"])
CSS = ".hdr{display:flex;gap:24px;padding:12px 24px;background:#0b3d2e}" * 40
JS = "window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments)}gtag('js',new Date());" * 30

PAGE = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Drip irrigation cut water use by a third</title>
<style>{CSS}</style><script>{JS}</script></head><body>
<header class="hdr"><a href="/">Field Notes</a><ul class="menu">{NAV}</ul><button>Subscribe</button></header>
<aside class="promo"><a href="/subscribe?utm_source=site&utm_campaign=fall">Get 3 months for $1</a></aside>
<main><article>
<h1>Drip irrigation cut water use by a third across 14 test farms</h1>
<p class="byline">By A. Rivera, October 28, 2026</p>
<p>Across 14 test plots in California's Central Valley, drip irrigation cut water use by 31 percent compared with
sprinklers, while yields stayed within 2 percent of the control group.</p>
<p>The largest gains came from clay soils, where evaporation losses were highest. Sandy plots saved 19 percent.</p>
<h2>What it cost</h2>
<p>Installation averaged $1,850 per acre. At current water prices, farmers recovered the cost in about 3 growing seasons.</p>
<table><tr><th>Soil</th><th>Water saved</th><th>Yield change</th></tr>
<tr><td>Clay</td><td>38%</td><td>-1%</td></tr><tr><td>Loam</td><td>31%</td><td>+1%</td></tr><tr><td>Sand</td><td>19%</td><td>-2%</td></tr></table>
<p>Read the <a href="https://example.org/study?utm_source=newsletter&utm_medium=email&fbclid=IwAR0xyz&id=42">full study data</a>.</p>
</article></main>
<aside class="related"><h3>Related</h3><ul>{NAV}</ul></aside>
<footer><p>&copy; 2026 Field Notes Media. All rights reserved.</p><ul>{NAV}</ul></footer>
<div id="cookie">We use cookies to improve your experience. <button>Accept all</button></div></body></html>"""


def make_json(path: Path):
    issues = [{"id": 9000 + i, "number": 100 + i, "title": t, "state": "open" if i % 3 else "closed",
               "user": {"login": u, "id": 7000 + i, "avatar_url": f"https://avatars.example/u/{7000 + i}?v=4",
                        "gravatar_id": "", "site_admin": False},
               "labels": [{"name": l} for l in ([] if i % 2 else ["bug"])], "assignee": None, "milestone": None,
               "comments": i % 5, "created_at": f"2026-10-{1 + i % 28:02d}T09:{i % 60:02d}:00Z", "closed_at": None,
               "body": "", "reactions": {"total_count": 0, "+1": 0, "-1": 0, "laugh": 0}, "performed_via_github_app": None}
              for i, (t, u) in enumerate([("Export fails on large decks", "kim"), ("Add dark mode", "raj"),
                                          ("PDF tables lose borders", "ana"), ("Login timeout too short", "lee"),
                                          ("Typo on pricing page", "sam"), ("CSV import drops last row", "kim"),
                                          ("Slow search on mobile", "ana"), ("Add SSO for teams", "raj")] * 3)]
    path.write_text(json.dumps(issues, indent=2))


def main():
    OUT.mkdir(exist_ok=True)
    make_deck(OUT / "q3-review.pptx")
    make_pdf(OUT / "logistics-report.pdf")
    (OUT / "field-notes.html").write_text(PAGE)
    make_json(OUT / "github-issues.json")
    print("wrote", ", ".join(p.name for p in sorted(OUT.iterdir())))


if __name__ == "__main__":
    main()
