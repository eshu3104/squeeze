import pytest

from squeeze import images, muse
from squeeze.core import Image, Section
from tests import make_fixtures as fx


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(muse, "CACHE", tmp_path / "cache")


def _sec(*imgs):
    return [Section("slide 1", "Revenue by quarter", [Image(d, w, h) for d, w, h in imgs])]


CHART = (fx.chart_png(), 1600, 900)


def test_informative_described_decorative_dropped(monkeypatch):
    calls = []

    def fake(prompt, image=None):
        calls.append(prompt)
        return {"class": "informative", "description": "| Q | Rev |\n|---|---|\n| Q1 | 120 |"}, False

    monkeypatch.setattr(muse, "ask_json", fake)
    s = _sec(CHART, (fx.logo_png(48), 48, 48))
    report = images.run(s, "slide deck")
    assert [r["class"] for r in report] == ["informative", "decorative"]
    assert len(calls) == 1  # the 48px logo never reaches the model
    assert "| Q1 | 120 |" in s[0].text and "tiny graphic" not in s[0].text
    assert report[0]["tokens_as_image"] > 1000 > report[0]["tokens_as_text"]
    assert s[0].images == []


def test_same_image_twice_is_one_call(monkeypatch):
    calls = []
    monkeypatch.setattr(muse, "ask_json", lambda p, i=None: (calls.append(1), ({"class": "informative", "description": "chart"}, False))[1])
    s = [Section("slide 1", "", [Image(*CHART)]), Section("slide 2", "", [Image(*CHART)])]
    report = images.run(s, "slide deck")
    assert len(calls) == 1 and report[1]["cached"] is True
    assert "[image: chart]" in s[1].text


def test_model_failure_is_visible_not_guessed(monkeypatch):
    def boom(prompt, image=None):
        raise muse.MuseError("503")

    monkeypatch.setattr(muse, "ask_json", boom)
    s = _sec(CHART)
    report = images.run(s, "slide deck")
    assert report[0]["class"] == "error"
    assert "[image: image omitted: model unavailable]" in s[0].text


def test_none_setting_makes_no_calls(monkeypatch):
    monkeypatch.setattr(muse, "ask_json", lambda *a: pytest.fail("no model call expected"))
    s = _sec(CHART)
    assert images.run(s, "slide deck", keep="none")[0]["class"] == "dropped"
    assert "[image" not in s[0].text


def test_mock_backend_end_to_end_and_cache(monkeypatch):
    monkeypatch.setenv("SQUEEZE_BACKEND", "mock")
    first = images.run(_sec(CHART), "slide deck")
    again = images.run(_sec(CHART), "slide deck")
    assert first[0]["class"] == "informative" and first[0]["cached"] is False
    assert again[0]["cached"] is True


def test_dotenv_loads_values_and_shell_wins(tmp_path, monkeypatch):
    f = tmp_path / ".env"
    f.write_text('# comment\nSQZ_A="one"\nSQZ_B=two\nSQZ_EMPTY=\n')
    monkeypatch.setenv("SQZ_B", "shell")
    monkeypatch.delenv("SQZ_A", raising=False)
    monkeypatch.delenv("SQZ_EMPTY", raising=False)
    muse._load_dotenv(f)
    import os
    assert os.environ["SQZ_A"] == "one" and os.environ["SQZ_B"] == "shell" and "SQZ_EMPTY" not in os.environ
    monkeypatch.delenv("SQZ_A")


def test_missing_key_raises_clear_error(monkeypatch):
    monkeypatch.setenv("SQUEEZE_BACKEND", "meta-api")
    monkeypatch.delenv("META_API_KEY", raising=False)
    with pytest.raises(muse.MuseError, match="META_API_KEY"):
        muse.ask_json("hi")
