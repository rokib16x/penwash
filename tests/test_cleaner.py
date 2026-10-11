from cleaner import clean


def run(text):
    return clean(text)[0]


def test_em_dash_becomes_comma():
    assert run("It works — mostly.") == "It works, mostly."


def test_emoji_and_spacing():
    assert run("Ship it 🚀.") == "Ship it."


def test_markdown_stripped():
    assert run("## Title\n\nThis is **bold** and *italic*.") == "Title\n\nThis is bold and italic."


def test_filler_openers_dropped_and_recapitalized():
    assert run("Furthermore, we agree. Moreover, it helps.") == "We agree. It helps."


def test_its_important_to_note():
    assert run("It is important to note that rain is wet.") == "Rain is wet."


def test_swaps_preserve_case():
    assert run("Utilize this. We leverage it.") == "Use this. We use it."


def test_numbers_and_wording_untouched():
    text = "Revenue grew 12.5% in 2025 across 3 regions."
    out, changes = clean(text)
    assert out == text and changes == []


def test_zero_width_removed():
    assert run("he\u200bllo") == "hello"


def test_changes_are_reported():
    _, changes = clean("Furthermore, it works — really.")
    labels = {c["label"] for c in changes}
    assert "Em dashes replaced with commas" in labels
    assert "Filler openers dropped" in labels
