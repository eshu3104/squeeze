from squeeze import passes
from squeeze.core import Section, compress, count_tokens, image_tokens


def test_image_tokens_matches_anthropic_table():
    # Worked examples from Anthropic's vision docs (standard tier).
    assert image_tokens(200, 200) == 64
    assert image_tokens(1000, 1000) == 1296
    assert 1500 <= image_tokens(1920, 1080) <= 1568


def test_tracking_params_removed_others_kept():
    s = [Section("", "see https://x.com/a?utm_source=news&id=7&fbclid=abc")]
    out = passes.tracking_urls(s)[0].text
    assert out == "see https://x.com/a?id=7"


def test_repeated_ids_aliased_with_legend():
    u = "123e4567-e89b-12d3-a456-426614174000"
    s = [Section("1", f"order {u}"), Section("2", f"refund {u}"), Section("3", "other 9f86d081884c7d659a2feaa0c55ad015")]
    out = passes.alias_ids(s)
    assert out[0].text == "order {id1}"
    assert out[1].text == "refund {id1}"
    assert "9f86d081884c7d659a2feaa0c55ad015" in out[2].text  # seen once: left alone
    assert f"{{id1}} = {u}" in out[2].text


def test_footer_kept_once():
    s = [Section(str(i), f"Slide body {i}\nACME Confidential 2026") for i in range(4)]
    out = passes.repeated_lines(s)
    assert "ACME Confidential 2026" in out[0].text
    assert all("ACME Confidential" not in x.text for x in out[1:])
    assert all(f"Slide body {i}" in x.text for i, x in enumerate(out))


def test_blobs_removed():
    s = [Section("", "img: data:image/png;base64," + "A" * 400 + " end")]
    assert passes.blobs(s)[0].text == "img: [inline data removed] end"


def test_whitespace_keeps_indentation():
    s = [Section("", "def f():\n    return 1   \n\n\n\nx  =  2")]
    assert passes.whitespace(s)[0].text == "def f():\n    return 1\n\nx = 2"


def test_compress_text_file_reports_real_counts(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("hello   world\n\n\n\n" + "data:image/png;base64," + "Q" * 600)
    r = compress(str(f))
    assert r.stats["tokens_after"] == count_tokens(r.text)
    assert r.stats["tokens_before"] > r.stats["tokens_after"]
    assert sum(r.stats["saved_by_pass"].values()) == r.stats["tokens_before"] - r.stats["tokens_after"]
