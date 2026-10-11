from fastapi.testclient import TestClient

from app import app, metrics, stock_hits
from guards import protected

client = TestClient(app)


def test_index_served():
    assert client.get("/").status_code == 200


def test_clean_endpoint():
    r = client.post("/api/clean", json={"text": "Furthermore, we leverage it — fast."}).json()
    assert r["text"] == "We use it, fast."
    assert r["after"]["stock_phrases"] == 0
    assert r["before"]["stock_phrases"] > r["after"]["stock_phrases"]


def test_metrics_and_helpers():
    m = metrics("Short one. This sentence is quite a bit longer than the first.")
    assert m["sentences"] == 2 and m["burstiness"] > 0
    assert "delve" in stock_hits("Let us delve in.")
    assert protected("Up 40% to 1,200")[0] == {"40", "1,200"}


def test_fiction_tells_only_flagged_in_fiction():
    text = "A shiver ran down her spine as the air was thick with dread."
    assert stock_hits(text) == []
    assert "shiver ran down" in stock_hits(text, fiction=True)


def test_cleanup_keeps_leading_dialogue_quote():
    from app import cleanup

    orig = '"Neither did I," she said.'
    assert cleanup('"Neither did I," she said.', False, orig) == orig
    assert cleanup('"The model wrapped this."', False, "The model wrapped this.") == "The model wrapped this."


def test_old_tones_map_to_general():
    from app import norm_tone

    assert [norm_tone(t) for t in ("natural", "casual", "professional", "academic", "")] == ["general"] * 5
    assert norm_tone("fiction") == "fiction"
