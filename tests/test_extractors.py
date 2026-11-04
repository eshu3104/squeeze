import json

from squeeze import extractors
from squeeze.core import count_tokens
from tests import make_fixtures as fx


def test_pptx_text_tables_notes_images(tmp_path):
    f = tmp_path / "deck.pptx"
    fx.make_pptx(f)
    sections, before = extractors.pptx(str(f))
    assert [s.anchor for s in sections] == ["slide 1", "slide 2", "slide 3", "slide 4"]
    s2 = sections[1]
    assert "Revenue grew 12% in region 2." in s2.text
    assert "| North | 1.2M |" in s2.text
    assert "Notes: Mention the South dip." in s2.text
    assert len(s2.images) == 2  # logo + chart
    assert before > count_tokens("".join(s.text for s in sections))  # images are billed


def test_pdf_text_images_and_scanned_page(tmp_path):
    f = tmp_path / "report.pdf"
    fx.make_pdf(f, scanned_last=True)
    sections, before = extractors.pdf(str(f))
    assert [s.anchor for s in sections] == ["p1", "p2", "p3"]
    assert "margin was 21.5%" in sections[0].text
    assert len(sections[0].images) == 1  # embedded chart
    assert sections[2].text.strip() == "" and len(sections[2].images) == 1  # scanned: whole page
    assert before >= 3 * 1000  # a page image per page


def test_html_keeps_article_drops_chrome(tmp_path):
    f = tmp_path / "page.html"
    fx.make_html(f)
    sections, before = extractors.html(f.read_text())
    md = sections[0].text
    assert "31 percent" in md and "clay soils" in md
    assert "dataLayer" not in md and "Privacy" not in md
    assert before > 2 * count_tokens(md)


def test_json_prunes_and_tables(tmp_path):
    f = tmp_path / "users.json"
    fx.make_json(f)
    sections, before = extractors.json_doc(f.read_text())
    out = sections[0].text
    assert out.startswith("users:\n| id | name | email | active |")
    assert "manager" not in out and "null" not in out
    assert "| 7 | user7 | u7@example.com | False |" in out
    assert count_tokens(out) < before / 2


def test_json_nested_stays_compact_json():
    raw = json.dumps({"a": {"b": [1, 2, {"c": None}]}, "d": "x"}, indent=2)
    sections, _ = extractors.json_doc(raw)
    assert sections[0].text == '{"a":{"b":[1,2]},"d":"x"}'
