from squeeze import fidelity, muse


def test_numbers_kept():
    assert fidelity.numbers_kept("grew 31% to 1,200 in 2026", "grew 31% to 1,200") == round(2 / 3, 3)
    assert fidelity.numbers_kept("no digits here", "x") is None


def test_probe_qa_scores_matches(monkeypatch):
    replies = iter([
        ({"qa": [{"q": "Water cut?", "a": "31 percent"}, {"q": "Plots?", "a": "14"}]}, False),
        ({"answers": ["31%"]}, False),  # model skipped one answer: padded as "not stated"
        ({"match": [True, False]}, False),
    ])
    prompts = []
    monkeypatch.setattr(muse, "ask_json", lambda p, i=None: (prompts.append(p), next(replies))[1])
    r = fidelity.probe_qa("original text", "compressed text", n=2)
    assert r["score"] == 0.5
    assert r["checks"][1]["got"] == "not stated"
    assert "compressed text" in prompts[1] and "original text" not in prompts[1]
