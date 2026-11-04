import json

import pytest
from fastapi.testclient import TestClient

from squeeze import muse
from squeeze.app import app
from squeeze.cli import main
from squeeze.core import compress, count_tokens
from tests import make_fixtures as fx


@pytest.fixture(autouse=True)
def offline(tmp_path, monkeypatch):
    monkeypatch.setenv("SQUEEZE_BACKEND", "mock")
    monkeypatch.setattr(muse, "CACHE", tmp_path / "cache")


@pytest.mark.parametrize("name,make", [("deck.pptx", fx.make_pptx), ("report.pdf", fx.make_pdf),
                                       ("page.html", fx.make_html), ("users.json", fx.make_json)])
def test_every_format_shrinks_and_accounts_exactly(tmp_path, name, make):
    f = tmp_path / name
    make(f)
    r = compress(str(f))
    s = r.stats
    assert s["tokens_after"] == count_tokens(r.text)
    assert s["tokens_after"] < s["tokens_before"]
    assert sum(s["saved_by_pass"].values()) == s["tokens_before"] - s["tokens_after"]
    assert r.fidelity["numbers_kept"] == 1.0  # deterministic passes keep every number


def test_deck_drops_logos_keeps_chart_and_footer_once(tmp_path):
    f = tmp_path / "deck.pptx"
    fx.make_pptx(f)
    r = compress(str(f))
    classes = [i["class"] for i in r.images]
    assert classes.count("decorative") == 4 and classes.count("informative") == 2
    assert r.text.count("Northwind Labs | Internal use only") == 1
    assert r.stats["image_model_calls"] == 1  # logos are tiny: never sent; the repeated chart is sent once
    assert r.stats["saved_by_pass"]["images"] > 1000  # image savings credited to the image step


def test_api_compresses_upload(tmp_path):
    f = tmp_path / "users.json"
    fx.make_json(f)
    with f.open("rb") as fh:
        res = TestClient(app).post("/compress", files={"file": ("users.json", fh)}, data={"images": "describe"})
    assert res.status_code == 200
    body = res.json()
    assert body["stats"]["source"] == "users.json" and "| user7 |" in body["text"]


def test_api_rejects_bad_input(tmp_path):
    c = TestClient(app)
    assert c.post("/compress", data={"url": "ftp://x"}).status_code == 400
    assert c.post("/compress", files={"file": ("a.exe", b"MZ")}).status_code == 400
    assert c.post("/compress", files={"file": ("a.json", b"{nope")}).status_code == 400
    assert c.get("/").status_code == 200


def test_cli_writes_markdown_and_manifest(tmp_path, capsys):
    f = tmp_path / "deck.pptx"
    fx.make_pptx(f)
    main([str(f), "--out", str(tmp_path / "out")])
    assert (tmp_path / "out" / "deck.md").read_text().startswith("[slide 1]")
    manifest = json.loads((tmp_path / "out" / "deck.manifest.json").read_text())
    assert "thumb" not in manifest["images"][0]
    assert "% smaller" in capsys.readouterr().out


def test_bom_json_url_pdf_and_empty_inputs(tmp_path, monkeypatch):
    import httpx

    j = tmp_path / "bom.json"
    j.write_bytes(b"\xef\xbb\xbf" + json.dumps({"a": 1}).encode())
    assert compress(str(j)).text.strip() == '{"a":1}'

    p = tmp_path / "r.pdf"
    fx.make_pdf(p)
    monkeypatch.setattr(httpx, "get", lambda *a, **k: httpx.Response(
        200, content=p.read_bytes(), headers={"content-type": "application/pdf"}, request=httpx.Request("GET", a[0])))
    assert "margin was 21.5%" in compress("https://example.org/r.pdf").text

    empty = tmp_path / "e.html"
    empty.write_text("<html><body><script>app()</script></body></html>")
    with pytest.raises(ValueError, match="no readable content"):
        compress(str(empty))

    bad = tmp_path / "bad.pptx"
    bad.write_bytes(b"not a zip")
    with pytest.raises(ValueError, match="could not read this file"):
        compress(str(bad))
