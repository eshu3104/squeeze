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
    assert [r["class"] for r in report] == ["informative", "tiny"]
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
    assert "[image: chart]" in s[0].text and s[1].text.endswith("[image: same as slide 1]")


def test_model_failure_is_visible_not_guessed(monkeypatch):
    def boom(prompt, image=None):
        raise muse.MuseError("503")

    monkeypatch.setattr(muse, "ask_json", boom)
    s = _sec(CHART)
    report = images.run(s, "slide deck")
    assert report[0]["class"] == "error"
    assert "[image omitted: model unavailable]" in s[0].text


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


def test_network_failure_becomes_muse_error(monkeypatch):
    import httpx

    def down(*a, **k):
        raise httpx.ConnectError("refused")

    monkeypatch.setenv("SQUEEZE_BACKEND", "meta-api")
    monkeypatch.setenv("META_API_KEY", "test-key")
    monkeypatch.setattr(httpx, "post", down)
    report = images.run(_sec(CHART), "slide deck")
    assert report[0]["class"] == "error" and "test-key" not in report[0]["error"]


def test_missing_key_raises_clear_error(monkeypatch):
    monkeypatch.setenv("SQUEEZE_BACKEND", "meta-api")
    monkeypatch.delenv("META_API_KEY", raising=False)
    with pytest.raises(muse.MuseError, match="META_API_KEY"):
        muse.ask_json("hi")


def _reply(monkeypatch, status, body):
    import httpx

    monkeypatch.setenv("SQUEEZE_BACKEND", "meta-api")
    monkeypatch.setenv("META_API_KEY", "sk-secret-123")
    monkeypatch.setattr(httpx, "post", lambda *a, **k: httpx.Response(status, json=body) if isinstance(body, dict)
                        else httpx.Response(status, text=body))


def test_null_content_and_key_echo_are_safe_errors(monkeypatch):
    _reply(monkeypatch, 200, {"choices": [{"message": {"content": None}}]})
    assert images.run(_sec(CHART), "slide deck")[0]["class"] == "error"
    _reply(monkeypatch, 401, "Incorrect API key provided: sk-secret-123")
    err = images.run(_sec(CHART), "slide deck")[0]["error"]
    assert "sk-secret-123" not in err and "***" in err


def test_reply_parsing_and_class_spelling(monkeypatch):
    _reply(monkeypatch, 200, {"choices": [{"message": {"content": 'Sure! {"class": " Decorative ", "description": "logo"}'}}]})
    assert images.run(_sec(CHART), "slide deck")[0]["class"] == "decorative"
    _reply(monkeypatch, 200, {"choices": [{"message": {"content": "no json here"}}]})
    with pytest.raises(muse.MuseError, match="no JSON"):
        muse.ask_json("other prompt")


def test_unreadable_image_is_dropped_not_fatal():
    s = _sec((fx.chart_png()[:300], 1600, 900))  # truncated PNG: size is readable, pixels are not
    assert images.run(s, "slide deck")[0]["class"] == "unreadable"


def test_call_limit(monkeypatch):
    monkeypatch.setattr(images, "MAX_CALLS", 2)
    monkeypatch.setattr(muse, "ask_json", lambda p, i=None: ({"class": "informative", "description": "x"}, False))
    s = [Section(f"p{n}", "", [Image(fx.chart_png(800 + n, 600), 800 + n, 600)]) for n in range(4)]
    assert [r["class"] for r in images.run(s, "PDF")] == ["informative", "informative", "limit", "limit"]


def test_cache_key_includes_model(monkeypatch):
    monkeypatch.setenv("SQUEEZE_BACKEND", "mock")
    monkeypatch.setenv("META_MODEL", "a")
    assert muse.ask_json("p")[1] is False
    assert muse.ask_json("p")[1] is True
    monkeypatch.setenv("META_MODEL", "b")
    assert muse.ask_json("p")[1] is False


def test_usage_recorded_and_kept_through_cache(monkeypatch):
    _reply(monkeypatch, 200, {"choices": [{"message": {"content": '{"class": "informative", "description": "x"}'}}],
                              "usage": {"prompt_tokens": 900, "completion_tokens": 40}})
    ledger = muse.start_ledger()
    images.run(_sec(CHART), "slide deck")
    images.run(_sec(CHART), "slide deck")  # second run: answered from the disk cache
    assert ledger == [{"kind": "image", "cached": False, "input": 900, "output": 40},
                      {"kind": "image", "cached": True, "input": 900, "output": 40}]
